"""Annonces, photos (upload + anti-fraude), carte, favoris, avis, signalements."""
import json
import math
import re
from datetime import timedelta

from flask import Blueprint, abort, current_app, g, jsonify, request
from psycopg.errors import UniqueViolation

from . import antifraud as af
from . import photos, places
from .auth import body, text
from .db import all_, one, run
from .security import current_user, now, rate_limit, require
from .storage import StorageUnavailable

bp = Blueprint("listings", __name__, url_prefix="/api")

DEALS = ("location", "vente")
PTYPES = ("maison", "appartement", "villa", "studio", "terrain")
AMENITIES = ("Eau courante", "Électricité", "Groupe électrogène", "Parking", "Clôture", "Gardien",
             "Climatisation", "Internet", "Jardin", "Citerne", "Cuisine équipée", "Panneaux solaires")
REPORT_CATEGORIES = {
    "photos_volees": "Photos volées ou ne correspondant pas au bien",
    "prix_trompeur": "Prix trompeur ou frais cachés",
    "inexistante": "Le bien n'existe pas / déjà loué ou vendu",
    "arnaque": "Demande d'argent avant visite / arnaque",
    "adresse_fausse": "Adresse ou position fausse",
    "doublon": "Annonce en double",
    "autre": "Autre",
}
MIN_IMAGES, MAX_IMAGES = 3, 10
MAX_LISTINGS_PER_DAY = 5
REPORTS_TO_HIDE = 3
MAX_KM_FROM_COMMUNE = 20
DRC_BOUNDS = (-13.6, 11.9, 5.6, 31.5)  # sud, ouest, nord, est
SORTS = {"new": "l.created_at DESC", "price_asc": "l.price ASC", "price_desc": "l.price DESC"}
PLACE_FILTERS = ("province_id", "city_id", "commune_id", "quartier_id", "avenue_id")

# Compteurs dénormalisés (rating_sum/count, fav_count) : tri par score sans agrégat à chaque requête.
BASE_SQL = """
SELECT l.*, l.price::float8 AS price_f, extract(epoch FROM l.created_at)::float8 AS created_ts,
       u.name AS host_name, u.verified AS host_verified, u.avatar_url AS host_avatar,
       CASE WHEN l.rating_count > 0 THEN ROUND(l.rating_sum::numeric / l.rating_count, 2)::float8 END AS rating,
       l.rating_count AS reviews_count,
       ROUND(((3 * 3.5 + l.rating_sum)::numeric / (3 + l.rating_count) + 0.05 * l.fav_count
             + CASE WHEN u.verified THEN 0.3 ELSE 0 END), 2)::float8 AS score
FROM listings l
JOIN users u ON u.id = l.owner_id
"""
VISIBLE = "l.status = 'active' AND u.suspended_at IS NULL"


def storage():
    return current_app.config["STORAGE"]


def approx(v):
    """Position publique arrondie (~110 m) : l'emplacement exact n'est montré qu'après prise de contact."""
    return round(v, 3) if v is not None else None


def card(r, favs=()):
    return {"id": r["id"], "title": r["title"], "deal": r["deal"], "ptype": r["ptype"], "province": r["province"],
            "city": r["city"], "commune": r["commune"], "quartier": r["quartier"], "price": r["price_f"],
            "bedrooms": r["bedrooms"], "bathrooms": r["bathrooms"], "surface": r["surface"],
            "furnished": r["furnished"], "status": r["status"], "rating": r["rating"],
            "reviews_count": r["reviews_count"], "score": r["score"], "cover": r["cover_url"],
            "host_verified": r["host_verified"], "favorite": r["id"] in favs, "created_at": r["created_ts"],
            "is_demo": r["is_demo"], "lat": approx(r["lat"]), "lng": approx(r["lng"])}


def owned_listing(lid):
    u = current_user()
    r = one("SELECT * FROM listings WHERE id=%s", (lid,))
    if not r or (r["owner_id"] != u["id"] and u["role"] != "admin"):
        abort(404, "Annonce introuvable.")  # 404 plutôt que 403 : ne révèle pas l'existence
    return r


def _num(a, key, lo, hi, cast=float):
    try:
        v = cast(a[key])
    except (TypeError, ValueError):
        abort(400, "Filtre numérique invalide.")
    if not lo <= v <= hi or v != v:
        abort(400, "Filtre numérique invalide.")
    return v


def search_filters(a):
    """WHERE paramétré à partir des filtres (noms de colonnes en liste blanche uniquement)."""
    where, args = [VISIBLE], []
    for key in PLACE_FILTERS:
        if a.get(key):
            where.append(f"l.{key} = %s")
            args.append(_num(a, key, 1, 2**62, int))
    for key in ("deal", "ptype"):
        if a.get(key):
            where.append(f"l.{key} = %s")
            args.append(a[key][:20])
    for key, col, op in (("min_price", "price", ">="), ("max_price", "price", "<="), ("bedrooms", "bedrooms", ">=")):
        if a.get(key):
            where.append(f"l.{col} {op} %s")
            args.append(_num(a, key, 0, 1e9))
    if a.get("furnished") == "1":
        where.append("l.furnished")
    if a.get("q"):
        q = a["q"][:60].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("(l.title ILIKE %s OR l.description ILIKE %s OR l.avenue ILIKE %s OR l.quartier ILIKE %s)")
        args += [f"%{q}%"] * 4
    if a.get("bbox"):
        try:
            s_, w_, n_, e_ = (float(x) for x in a["bbox"].split(",")[:4])
        except ValueError:
            abort(400, "Zone de carte invalide.")
        where.append("l.lat BETWEEN %s AND %s AND l.lng BETWEEN %s AND %s")
        args += [s_, n_, w_, e_]
    return " AND ".join(where), args


# ----------------------------------------------------------------------- catalogue
@bp.get("/meta")
def meta():
    g.cache_seconds = 300
    return jsonify(deals=DEALS, ptypes=PTYPES, amenities=AMENITIES, min_images=MIN_IMAGES, max_images=MAX_IMAGES,
                   report_categories=REPORT_CATEGORIES,
                   tiles={"url": current_app.config["NDAKU"].TILE_URL, "attribution": current_app.config["NDAKU"].TILE_ATTRIBUTION})


@bp.get("/listings")
def list_listings():
    """Recherche publique, identique pour tous : mise en cache 30 s par le CDN (favoris chargés à part)."""
    a = request.args
    w, args = search_filters(a)
    order = SORTS.get(a.get("sort"), "score DESC, l.created_at DESC")
    limit = _num(a, "limit", 1, 60, int) if a.get("limit") else 24
    offset = _num(a, "offset", 0, 10000, int) if a.get("offset") else 0
    rows = all_(f"{BASE_SQL} WHERE {w} ORDER BY {order}, l.id DESC LIMIT %s OFFSET %s", args + [limit, offset])
    total = one(f"SELECT COUNT(*)::int AS n FROM listings l JOIN users u ON u.id=l.owner_id WHERE {w}", args)["n"]
    g.cache_seconds = 30
    return jsonify(items=[card(r) for r in rows], total=total)


@bp.get("/listings/map")
def map_points():
    """Points légers pour la carte (zone visible), plafonnés à 500."""
    w, args = search_filters(request.args)
    rows = all_(f"""SELECT l.id, l.lat, l.lng, l.price::float8 AS price, l.deal, l.title, l.cover_url AS cover,
                      l.ptype, l.bedrooms FROM listings l JOIN users u ON u.id=l.owner_id
                    WHERE {w} AND l.lat IS NOT NULL ORDER BY l.created_at DESC LIMIT 500""", args)
    for r in rows:
        r["lat"], r["lng"] = approx(r["lat"]), approx(r["lng"])
    g.cache_seconds = 30
    return jsonify(items=rows)


def can_see_exact(u, r):
    if not u:
        return False
    if u["role"] == "admin" or u["id"] == r["owner_id"]:
        return True
    return bool(one("SELECT 1 FROM conversations WHERE listing_id=%s AND client_id=%s", (r["id"], u["id"])))


@bp.get("/listings/<int:lid>")
def get_listing(lid):
    u = current_user()
    r = one(f"{BASE_SQL} WHERE l.id = %s", (lid,))
    if not r:
        abort(404, "Annonce introuvable.")
    is_staff = bool(u and (u["role"] == "admin" or u["id"] == r["owner_id"]))
    if (r["status"] != "active" or one("SELECT 1 FROM users WHERE id=%s AND suspended_at IS NOT NULL",
                                        (r["owner_id"],))) and not is_staff:
        abort(404, "Annonce introuvable.")
    favs = {lid} if u and one("SELECT 1 FROM favorites WHERE user_id=%s AND listing_id=%s", (u["id"], lid)) else set()
    d = card(r, favs)
    exact = can_see_exact(u, r)
    imgs = all_("SELECT url, credit FROM images WHERE listing_id=%s ORDER BY position", (lid,))
    street = ", ".join(x for x in (r["avenue"], r["quartier"], r["commune"], r["city"]) if x) or r["address"]
    d.update(description=r["description"], amenities=r["amenities"], avenue=r["avenue"],
             address=(f"{r['avenue']} n° {r['house_number']}" + (f", {r['unit']}" if r["unit"] else "")
                      if exact and r["house_number"] else None),
             street=street, exact_location=exact,
             host={"id": r["owner_id"], "name": r["host_name"], "verified": r["host_verified"],
                   "avatar": r["host_avatar"]},
             images=[i["url"] for i in imgs], credits=[i["credit"] for i in imgs if i["credit"]],
             reviews=all_("""SELECT r.rating, r.comment, extract(epoch FROM r.created_at)::float8 AS created_at, u.name,
                                    u.avatar_url AS avatar
                             FROM reviews r JOIN users u ON u.id=r.user_id WHERE r.listing_id=%s
                             ORDER BY r.created_at DESC LIMIT 50""", (lid,)))
    if exact:
        d["lat"], d["lng"] = r["lat"], r["lng"]
    if is_staff:
        d["risk_score"], d["risk_reasons"] = r["risk_score"], r["risk_reasons"]
    if u:
        conv = one("SELECT id FROM conversations WHERE listing_id=%s AND client_id=%s", (lid, u["id"]))
        d["conversation_id"] = conv["id"] if conv else None
        d["can_review"] = bool(conv and u["id"] != r["owner_id"]
                               and one("SELECT 1 FROM messages WHERE conversation_id=%s AND sender_id=%s LIMIT 1",
                                       (conv["id"], u["id"]))
                               and not one("SELECT 1 FROM reviews WHERE listing_id=%s AND user_id=%s", (lid, u["id"])))
    return jsonify(d)


# --------------------------------------------------------------------------- photos
@bp.post("/uploads")
@require("host", verified_email=True, avatar=True)
def upload():
    """Une photo par requête (compatible limite 4,5 Mo de Vercel et apps mobiles).
    La photo est vérifiée contre TOUTES les photos existantes avant d'être stockée."""
    u = current_user()
    rate_limit(f"upload:{u['id']}", 60, 3600, "Trop de photos envoyées. Réessayez dans une heure.")
    if one("SELECT COUNT(*)::int AS n FROM images WHERE owner_id=%s AND listing_id IS NULL", (u["id"],))["n"] >= 30:
        abort(429, "Trop de photos en attente : publiez ou supprimez-en avant d'en ajouter.")
    f = request.files.get("image")
    if not f:
        abort(400, "Fichier « image » manquant.")
    try:
        img = af.load_image(f.read())
    except af.ImageRejected as e:
        abort(422, str(e))
    try:
        row = photos.save(u["id"], img)
    except StorageUnavailable:
        abort(503, "Stockage des photos non configuré (connectez un store Blob au projet Vercel).")
    except photos.Duplicate as d:
        mine = d.clash["owner_id"] == u["id"]
        where = ("l'une de vos annonces" if d.clash["listing_id"] else "vos photos en attente") if mine else "une autre annonce"
        kind = "copie exacte" if d.clash["exact"] else "image quasi identique : recadrage, miroir ou retouche"
        abort(422, f"Photo déjà utilisée dans {where} ({kind}).")
    return jsonify(row), 201


@bp.delete("/uploads/<int:iid>")
@require("host")
def delete_upload(iid):
    r = one("DELETE FROM images WHERE id=%s AND owner_id=%s AND listing_id IS NULL RETURNING storage_key",
            (iid, current_user()["id"]))
    if not r:
        abort(404, "Photo introuvable.")
    storage().delete([r["storage_key"]])
    return jsonify(ok=True)


# ------------------------------------------------------------------------- annonces
_HOUSE_NO = re.compile(r"^[0-9]{1,5}( ?(bis|ter|[a-z]))?(/[0-9a-z]{1,4})?$", re.I)


def _pid(d, key, required=True):
    v = d.get(key)
    if v in (None, "") and not required:
        return None
    if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
        abort(400, "Localisation incomplète : choisissez province, ville, commune, quartier et avenue.")
    return v


def parse_location(d, u):
    """Valide la chaîne province > ville > commune > (quartier) > avenue, le numéro et la position GPS."""
    commune_id, quartier_id, avenue_id = _pid(d, "commune_id"), _pid(d, "quartier_id", False), _pid(d, "avenue_id")
    c = places.chain(avenue_id=avenue_id)
    av, com = c.get("avenue"), c.get("commune")
    if not av or not com or com["id"] != commune_id or av["id"] != avenue_id:
        abort(400, "Avenue introuvable dans cette commune.")
    q = c.get("quartier")
    if quartier_id and (not q or q["id"] != quartier_id):
        abort(400, "Cette avenue n'appartient pas au quartier choisi.")
    for p_ in c.values():  # un lieu proposé (en attente) reste utilisable ; un lieu refusé par la modération, non
        if p_["status"] == "rejected":
            abort(400, "Ce quartier ou cette avenue a été refusé par la modération : choisissez-en un autre.")
    number = text(d, "house_number", 12)
    if not _HOUSE_NO.match(number):
        abort(400, "Numéro de la maison invalide (ex. 12, 12 bis, 45/B).")
    unit = text(d, "unit", 30)
    try:
        lat, lng = float(d.get("lat")), float(d.get("lng"))
    except (TypeError, ValueError):
        abort(400, "Placez le bien sur la carte.")
    s_, w_, n_, e_ = DRC_BOUNDS
    if not (s_ <= lat <= n_ and w_ <= lng <= e_):
        abort(400, "La position doit se trouver en RDC.")
    return {"province": c["province"], "city": c["city"], "commune": com, "quartier": q, "avenue": av,
            "house_number": number.lower(), "unit": unit, "lat": lat, "lng": lng}


def street_key(name):
    """« Av. de la Justice », « avenue De La Justice » → « de la justice »."""
    words = af.norm_text(name)
    while words and words[0] in ("avenue", "av", "rue", "boulevard", "bd", "blvd", "route", "chaussee", "allee"):
        words = words[1:]
    return " ".join(words)


def addr_key(loc):
    return "|".join((str(loc["commune"]["id"]), street_key(loc["avenue"]["name"]),
                     " ".join(af.norm_text(loc["house_number"])), " ".join(af.norm_text(loc["unit"]))))


def km(lat1, lng1, lat2, lng2):
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lng2 - lng1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def parse_listing(d):
    title, desc = text(d, "title", 120), text(d, "description", 3000)
    deal, ptype = d.get("deal"), d.get("ptype")
    if deal not in DEALS or ptype not in PTYPES:
        abort(400, "Type d'offre ou de bien invalide.")
    if len(title) < 8:
        abort(400, "Titre trop court (8 caractères minimum).")
    if len(desc) < 60:
        abort(400, "Description trop courte (60 caractères minimum) : décrivez le bien précisément.")
    try:
        price = float(d.get("price"))
        bedrooms, bathrooms, surface = int(d.get("bedrooms", 0)), int(d.get("bathrooms", 0)), int(d.get("surface"))
    except (TypeError, ValueError):
        abort(400, "Prix, chambres, salles de bain et surface doivent être des nombres.")
    lo, hi = (20, 20_000) if deal == "location" else (3_000, 20_000_000)
    if not lo <= price <= hi:
        abort(400, f"Prix hors limites réalistes ({lo}–{hi} USD).")
    if not 9 <= surface <= 50_000 or not 0 <= bedrooms <= 20 or not 0 <= bathrooms <= 20:
        abort(400, "Surface ou nombre de pièces irréaliste.")
    if ptype != "terrain" and bedrooms and surface / bedrooms < 8:
        abort(400, "Incohérence : surface trop petite pour ce nombre de chambres.")
    am = d.get("amenities") if isinstance(d.get("amenities"), list) else []
    return dict(title=title, description=desc, deal=deal, ptype=ptype, price=round(price, 2), bedrooms=bedrooms,
                bathrooms=bathrooms, surface=surface, furnished=d.get("furnished") in (True, 1, "1", "true", "on"),
                amenities=[x for x in dict.fromkeys(am) if x in AMENITIES])


ADDRESS_TAKEN = "Cette adresse (avenue + numéro{}) est déjà publiée dans une autre annonce."


@bp.post("/listings")
@require("host", verified_email=True, avatar=True)
def create_listing():
    u, d = current_user(), body()
    run("SELECT pg_advisory_xact_lock(7002, %s)", (u["id"] % 2_000_000_000,))  # quota atomique par hôte
    if one("SELECT COUNT(*)::int AS n FROM listings WHERE owner_id=%s AND created_at > now() - interval '1 day'",
           (u["id"],))["n"] >= MAX_LISTINGS_PER_DAY:
        abort(429, f"Limite de {MAX_LISTINGS_PER_DAY} annonces par 24 h atteinte.")
    data, loc = parse_listing(d), parse_location(d, u)

    for field in ("title", "description"):
        hit = af.find_contact_info(data[field])
        if hit:
            abort(400, f"Coordonnées interdites dans « {field} » ({hit}). Les échanges se font par la messagerie Ndaku.")
    key = addr_key(loc)
    unit_hint = " + logement" if loc["unit"] else ""
    if one("SELECT 1 FROM listings WHERE addr_key=%s AND status IN ('active','pending')", (key,)):
        abort(409, ADDRESS_TAKEN.format(unit_hint))

    ids = d.get("image_ids")
    if (not isinstance(ids, list) or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids)
            or len(set(ids)) != len(ids)):
        abort(400, "Liste de photos invalide.")
    if not MIN_IMAGES <= len(ids) <= MAX_IMAGES:
        abort(400, f"Ajoutez entre {MIN_IMAGES} et {MAX_IMAGES} photos.")
    owned = {r["id"]: r["url"] for r in all_(
        "SELECT id, url FROM images WHERE id = ANY(%s) AND owner_id=%s AND listing_id IS NULL FOR UPDATE", (ids, u["id"]))}
    if len(owned) != len(ids):
        abort(400, "Certaines photos n'existent pas, ne vous appartiennent pas ou sont déjà utilisées.")

    score, reasons = 0, []
    comps = all_("SELECT price::float8 AS price, surface FROM listings WHERE status='active' AND city_id=%s AND deal=%s "
                 "AND ptype=%s ORDER BY created_at DESC LIMIT 500", (loc["city"]["id"], data["deal"], data["ptype"]))
    why = af.price_anomaly(data["price"], data["surface"], [(c["price"], c["surface"]) for c in comps])
    if why:
        score += 45
        reasons.append(why)
    sh = af.shingles(data["description"])
    for o in all_("SELECT description FROM listings WHERE owner_id<>%s AND status IN ('active','pending') "
                  "ORDER BY created_at DESC LIMIT 2000", (u["id"],)):
        if af.jaccard(sh, af.shingles(o["description"])) >= 0.6:
            score += 50
            reasons.append("Description quasi identique à celle d'une annonce d'un autre hôte")
            break
    ref = loc["avenue"] if loc["avenue"]["lat"] is not None else loc["commune"]
    if ref["lat"] is not None:
        dist = km(loc["lat"], loc["lng"], ref["lat"], ref["lng"])
        limit_km = 3 if ref is loc["avenue"] else MAX_KM_FROM_COMMUNE
        if dist > limit_km:
            score += 25
            reasons.append(f"Position sur la carte à {dist:.0f} km de {'l’avenue' if ref is loc['avenue'] else 'la commune'} déclarée")
    if any(p_["status"] == "pending" for p_ in (loc["quartier"] or {}, loc["avenue"]) if p_):
        score += 15
        reasons.append("Quartier ou avenue proposé par l'hôte, pas encore vérifié")
    if now() - u["created_at"] < timedelta(hours=1):
        score += 10
        reasons.append("Compte créé il y a moins d'une heure")
    if not u["verified"]:
        score += 10
        reasons.append("Hôte non vérifié")
    status = "pending" if score >= af.RISK_PENDING_THRESHOLD else "active"

    q = loc["quartier"]
    try:
        row = one("""INSERT INTO listings (owner_id, title, description, deal, ptype, province, city, commune, quartier,
                       avenue, house_number, unit, address, province_id, city_id, commune_id, quartier_id, avenue_id,
                       lat, lng, price, bedrooms, bathrooms, surface, furnished, amenities, status, risk_score,
                       risk_reasons, addr_key, cover_url)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                     RETURNING id""",
                  (u["id"], data["title"], data["description"], data["deal"], data["ptype"], loc["province"]["name"],
                   loc["city"]["name"], loc["commune"]["name"], q["name"] if q else None, loc["avenue"]["name"],
                   loc["house_number"], loc["unit"] or None, f"{loc['avenue']['name']} n° {loc['house_number']}",
                   loc["province"]["id"], loc["city"]["id"], loc["commune"]["id"], q["id"] if q else None,
                   loc["avenue"]["id"], loc["lat"], loc["lng"], data["price"], data["bedrooms"], data["bathrooms"],
                   data["surface"], data["furnished"], json.dumps(data["amenities"]), status, score,
                   json.dumps(reasons), key, owned[ids[0]]))
    except UniqueViolation:  # publication simultanée de la même adresse : l'index unique tranche
        abort(409, ADDRESS_TAKEN.format(unit_hint))
    for pos, iid in enumerate(ids):
        run("UPDATE images SET listing_id=%s, position=%s WHERE id=%s", (row["id"], pos, iid))
    return jsonify(id=row["id"], status=status, reasons=reasons), 201


@bp.patch("/listings/<int:lid>")
@require()
def patch_listing(lid):
    r = owned_listing(lid)
    status = body().get("status")
    if status not in ("closed", "active") or r["status"] in ("pending", "rejected"):
        abort(400, "Changement de statut non autorisé.")
    if status == "active" and one("SELECT 1 FROM listings WHERE addr_key=%s AND id<>%s AND status IN ('active','pending')",
                                  (r["addr_key"], lid)):
        abort(409, ADDRESS_TAKEN.format(""))
    run("UPDATE listings SET status=%s WHERE id=%s", (status, lid))
    return jsonify(ok=True)


@bp.delete("/listings/<int:lid>")
@require()
def delete_listing(lid):
    r = owned_listing(lid)
    if r["status"] in ("rejected", "pending") and current_user()["role"] != "admin":
        # Une annonce signalée ou en modération ne peut pas être effacée par son auteur :
        # sinon il libérerait ses photos et l'adresse pour republier aussitôt.
        abort(400, "Annonce en cours de modération ou rejetée : elle ne peut pas être supprimée.")
    keys = [x["storage_key"] for x in all_("SELECT storage_key FROM images WHERE listing_id=%s", (lid,))]
    run("DELETE FROM listings WHERE id=%s", (lid,))
    storage().delete(keys)
    return jsonify(ok=True)


@bp.get("/my/listings")
@require("host")
def my_listings():
    uid = current_user()["id"]
    rows = all_(f"{BASE_SQL} WHERE l.owner_id=%s ORDER BY l.created_at DESC", (uid,))
    counts = {r["listing_id"]: r["n"] for r in all_(
        "SELECT listing_id, COUNT(*)::int AS n FROM conversations WHERE host_id=%s GROUP BY 1", (uid,))}
    return jsonify(items=[{**card(r), "risk_reasons": r["risk_reasons"], "conversations": counts.get(r["id"], 0),
                           "address": f"{r['avenue'] or r['address']} n° {r['house_number']}" if r["house_number"] else r["address"]}
                          for r in rows])


# -------------------------------------------------------------- favoris / avis / signalements
def active_or_404(lid):
    r = one(f"SELECT l.id, l.owner_id FROM listings l JOIN users u ON u.id=l.owner_id WHERE l.id=%s AND {VISIBLE}", (lid,))
    if not r:
        abort(404, "Annonce introuvable.")
    return r


@bp.post("/listings/<int:lid>/favorite")
@require()
def toggle_fav(lid):
    active_or_404(lid)
    uid = current_user()["id"]
    if run("DELETE FROM favorites WHERE user_id=%s AND listing_id=%s", (uid, lid)).rowcount:
        run("UPDATE listings SET fav_count = GREATEST(fav_count - 1, 0) WHERE id=%s", (lid,))
        return jsonify(favorite=False)
    if run("INSERT INTO favorites VALUES (%s,%s) ON CONFLICT DO NOTHING", (uid, lid)).rowcount:
        run("UPDATE listings SET fav_count = fav_count + 1 WHERE id=%s", (lid,))
    return jsonify(favorite=True)


@bp.get("/favorites")
@require()
def favorites():
    rows = all_(f"""{BASE_SQL} JOIN favorites f ON f.listing_id=l.id AND f.user_id=%s WHERE {VISIBLE}
                    ORDER BY l.created_at DESC""", (current_user()["id"],))
    return jsonify(items=[card(r, {r["id"] for r in rows}) for r in rows])


@bp.get("/favorites/ids")
@require()
def favorite_ids():
    return jsonify(ids=[r["listing_id"] for r in all_("SELECT listing_id FROM favorites WHERE user_id=%s",
                                                       (current_user()["id"],))])


@bp.post("/listings/<int:lid>/reviews")
@require(avatar=True)
def review(lid):
    r = active_or_404(lid)
    u, d = current_user(), body()
    conv = one("SELECT id FROM conversations WHERE listing_id=%s AND client_id=%s", (lid, u["id"]))
    if r["owner_id"] == u["id"] or not conv or not one(
            "SELECT 1 FROM messages WHERE conversation_id=%s AND sender_id=%s LIMIT 1", (conv["id"], u["id"])):
        abort(403, "Seuls les clients ayant échangé avec l'hôte peuvent laisser un avis vérifié.")
    rating, comment = d.get("rating"), text(d, "comment", 800)
    if isinstance(rating, str) and rating.isdigit():
        rating = int(rating)
    if not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 5 or len(comment) < 10:
        abort(400, "Note de 1 à 5 et commentaire de 10 caractères minimum.")
    if not one("""INSERT INTO reviews (listing_id, user_id, rating, comment) VALUES (%s,%s,%s,%s)
                  ON CONFLICT (listing_id, user_id) DO NOTHING RETURNING id""", (lid, u["id"], rating, comment)):
        abort(409, "Vous avez déjà noté cette annonce.")
    run("UPDATE listings SET rating_sum = rating_sum + %s, rating_count = rating_count + 1 WHERE id=%s", (rating, lid))
    return jsonify(ok=True), 201


@bp.post("/listings/<int:lid>/report")
@require()
def report(lid):
    r = active_or_404(lid)
    u, d = current_user(), body()
    if r["owner_id"] == u["id"]:
        abort(404, "Annonce introuvable.")
    rate_limit(f"report:{u['id']}", 20, 86400)
    category, reason = d.get("category", "autre"), text(d, "reason", 500)
    if category not in REPORT_CATEGORIES:
        abort(400, "Motif de signalement invalide.")
    if category == "autre" and len(reason) < 5:
        abort(400, "Précisez le motif du signalement.")
    if not one("""INSERT INTO reports (listing_id, user_id, category, reason) VALUES (%s,%s,%s,%s)
                  ON CONFLICT (listing_id, user_id) DO NOTHING RETURNING id""",
               (lid, u["id"], category, reason or REPORT_CATEGORIES[category])):
        abort(409, "Vous avez déjà signalé cette annonce.")
    n = one("SELECT COUNT(*)::int AS n FROM reports WHERE listing_id=%s AND status='open'", (lid,))["n"]
    if n >= REPORTS_TO_HIDE:  # masquage automatique en attendant la modération
        run("""UPDATE listings SET status='pending', risk_score=risk_score+50,
                 risk_reasons = risk_reasons || %s::jsonb WHERE id=%s""",
            (json.dumps([f"{n} signalements d'utilisateurs"]), lid))
    return jsonify(ok=True)
