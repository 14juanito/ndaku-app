"""Annonces, photos (upload + anti-fraude), favoris, demandes de visite, avis, signalements."""
import json
from datetime import date, timedelta

from flask import Blueprint, abort, current_app, jsonify, request

from . import antifraud as af
from .auth import body, text
from .db import all_, one, run
from .security import current_user, now, rate_limit, require

bp = Blueprint("listings", __name__, url_prefix="/api")

CITIES = {
    "Kinshasa": ["Gombe", "Limete", "Ngaliema", "Bandalungwa", "Lemba", "Kintambo", "Matete", "Masina",
                 "Kalamu", "Lingwala", "Mont-Ngafula", "Ngaba", "Kasa-Vubu", "Barumbu", "Selembao", "N'djili"],
    "Lubumbashi": ["Lubumbashi", "Golf", "Kenya", "Kamalondo", "Katuba", "Ruashi"],
    "Goma": ["Goma", "Himbi", "Katindo", "Les Volcans", "Mugunga"],
    "Kolwezi": ["Manika", "Dilala"],
    "Matadi": ["Matadi", "Mvuzi"],
    "Kisangani": ["Makiso", "Tshopo"],
    "Bukavu": ["Ibanda", "Kadutu", "Bagira"],
    "Mbuji-Mayi": ["Diulu", "Muya"],
}
DEALS = ("location", "vente")
PTYPES = ("maison", "appartement", "villa", "studio", "terrain")
AMENITIES = ("Eau courante", "Électricité", "Groupe électrogène", "Parking", "Clôture", "Gardien",
             "Climatisation", "Internet", "Jardin", "Citerne", "Cuisine équipée", "Panneaux solaires")
MIN_IMAGES, MAX_IMAGES = 3, 10
MAX_LISTINGS_PER_DAY = 5
REPORTS_TO_HIDE = 3
SORTS = {"new": "l.created_at DESC", "price_asc": "l.price ASC", "price_desc": "l.price DESC"}

BASE_SQL = """
SELECT l.*, l.price::float8 AS price_f, extract(epoch FROM l.created_at)::float8 AS created_ts,
       u.name AS host_name, u.verified AS host_verified,
       r.rating::float8 AS rating, COALESCE(r.n, 0) AS reviews_count,
       ROUND(((3 * 3.5 + COALESCE(r.s, 0)) / (3 + COALESCE(r.n, 0)) + 0.05 * COALESCE(f.n, 0)
             + CASE WHEN u.verified THEN 0.3 ELSE 0 END)::numeric, 2)::float8 AS score,
       (SELECT url FROM images i WHERE i.listing_id = l.id ORDER BY position LIMIT 1) AS cover
FROM listings l
JOIN users u ON u.id = l.owner_id
LEFT JOIN LATERAL (SELECT ROUND(AVG(rating), 2) AS rating, SUM(rating) AS s, COUNT(*) AS n
                   FROM reviews WHERE listing_id = l.id) r ON TRUE
LEFT JOIN LATERAL (SELECT COUNT(*) AS n FROM favorites WHERE listing_id = l.id) f ON TRUE
"""


def storage():
    return current_app.config["STORAGE"]


def card(r, favs=()):
    return {"id": r["id"], "title": r["title"], "deal": r["deal"], "ptype": r["ptype"], "city": r["city"],
            "commune": r["commune"], "price": r["price_f"], "bedrooms": r["bedrooms"], "bathrooms": r["bathrooms"],
            "surface": r["surface"], "furnished": r["furnished"], "status": r["status"], "rating": r["rating"],
            "reviews_count": r["reviews_count"], "score": r["score"], "cover": r["cover"],
            "host_verified": r["host_verified"], "favorite": r["id"] in favs, "created_at": r["created_ts"],
            "is_demo": r["is_demo"]}


def my_favs():
    u = current_user()
    return {x["listing_id"] for x in all_("SELECT listing_id FROM favorites WHERE user_id=%s", (u["id"],))} if u else set()


def owned_listing(lid):
    u = current_user()
    r = one("SELECT * FROM listings WHERE id=%s", (lid,))
    if not r or (r["owner_id"] != u["id"] and u["role"] != "admin"):
        abort(404, "Annonce introuvable.")  # 404 plutôt que 403 : ne révèle pas l'existence
    return r


# ----------------------------------------------------------------------- catalogue
@bp.get("/meta")
def meta():
    counts = all_("SELECT city, deal, COUNT(*)::int AS n FROM listings WHERE status='active' GROUP BY 1, 2")
    return jsonify(cities=CITIES, deals=DEALS, ptypes=PTYPES, amenities=AMENITIES, min_images=MIN_IMAGES,
                   max_images=MAX_IMAGES, counts=counts)


@bp.get("/listings")
def list_listings():
    a, where, args = request.args, ["l.status='active'"], []
    for key in ("city", "commune", "deal", "ptype"):
        if a.get(key):
            where.append(f"l.{key} = %s")  # nom de colonne issu d'une liste blanche, valeur paramétrée
            args.append(a[key][:60])
    for key, col, op in (("min_price", "price", ">="), ("max_price", "price", "<="), ("bedrooms", "bedrooms", ">=")):
        if a.get(key):
            try:
                v = float(a[key])
            except ValueError:
                abort(400, "Filtre numérique invalide.")
            if not 0 <= v <= 1e9:
                abort(400, "Filtre numérique invalide.")
            where.append(f"l.{col} {op} %s")
            args.append(v)
    if a.get("furnished") == "1":
        where.append("l.furnished")
    if a.get("q"):
        q = a["q"][:60].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where.append("(l.title ILIKE %s OR l.description ILIKE %s OR l.address ILIKE %s)")
        args += [f"%{q}%"] * 3
    order = SORTS.get(a.get("sort"), "score DESC, l.created_at DESC")
    try:
        limit, offset = min(max(int(a.get("limit", 24)), 1), 60), min(max(int(a.get("offset", 0)), 0), 10000)
    except ValueError:
        abort(400, "Pagination invalide.")
    w = " AND ".join(where)
    rows = all_(f"{BASE_SQL} WHERE {w} ORDER BY {order} LIMIT %s OFFSET %s", args + [limit, offset])
    total = one(f"SELECT COUNT(*)::int AS n FROM listings l WHERE {w}", args)["n"]
    favs = my_favs()
    return jsonify(items=[card(r, favs) for r in rows], total=total)


@bp.get("/listings/<int:lid>")
def get_listing(lid):
    u = current_user()
    r = one(f"{BASE_SQL} WHERE l.id = %s", (lid,))
    if not r:
        abort(404, "Annonce introuvable.")
    is_staff = bool(u and (u["role"] == "admin" or u["id"] == r["owner_id"]))
    if r["status"] != "active" and not is_staff:
        abort(404, "Annonce introuvable.")
    d = card(r, my_favs())
    imgs = all_("SELECT url, credit FROM images WHERE listing_id=%s ORDER BY position", (lid,))
    d.update(description=r["description"], address=r["address"], amenities=r["amenities"],
             host={"id": r["owner_id"], "name": r["host_name"], "verified": r["host_verified"]},
             images=[i["url"] for i in imgs], credits=[i["credit"] for i in imgs if i["credit"]],
             reviews=all_("""SELECT r.rating, r.comment, extract(epoch FROM r.created_at)::float8 AS created_at, u.name
                             FROM reviews r JOIN users u ON u.id=r.user_id WHERE r.listing_id=%s
                             ORDER BY r.created_at DESC LIMIT 50""", (lid,)))
    if is_staff:
        d["risk_score"], d["risk_reasons"] = r["risk_score"], r["risk_reasons"]
    if u:
        d["can_review"] = bool(
            u["id"] != r["owner_id"]
            and one("SELECT 1 FROM inquiries WHERE listing_id=%s AND user_id=%s", (lid, u["id"]))
            and not one("SELECT 1 FROM reviews WHERE listing_id=%s AND user_id=%s", (lid, u["id"])))
    return jsonify(d)


# --------------------------------------------------------------------------- photos
DUP_SQL = """
SELECT i.id, i.owner_id, i.listing_id, i.sha = %(sha)s AS exact FROM images i
WHERE i.sha = %(sha)s
   OR (bit_count((i.dhash # %(d)s)::bit(64)) <= %(dmax)s AND bit_count((i.phash # %(p)s)::bit(64)) <= %(pmax)s)
   OR (bit_count((i.dhash # %(dm)s)::bit(64)) <= %(dmax)s AND bit_count((i.phash # %(pm)s)::bit(64)) <= %(pmax)s)
ORDER BY exact DESC LIMIT 1"""


@bp.post("/uploads")
@require("host", verified_email=True)
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
    fp = af.fingerprint(img)
    s = {k: af.signed64(fp[k]) for k in ("dhash", "phash", "dhash_m", "phash_m")}
    # Sérialise les uploads : deux photos quasi identiques envoyées en même temps ne passent pas toutes les deux.
    run("SELECT pg_advisory_xact_lock(7001)")
    clash = one(DUP_SQL, {"sha": fp["sha"], "d": s["dhash"], "p": s["phash"], "dm": s["dhash_m"],
                          "pm": s["phash_m"], "dmax": af.DHASH_MAX, "pmax": af.PHASH_MAX})
    if clash:
        mine = clash["owner_id"] == u["id"]
        where = ("l'une de vos annonces" if clash["listing_id"] else "vos photos en attente") if mine else "une autre annonce"
        kind = "copie exacte" if clash["exact"] else "image quasi identique : recadrage, miroir ou retouche"
        abort(422, f"Photo déjà utilisée dans {where} ({kind}).")
    url, key = storage().put(af.to_jpeg(img))
    row = one("""INSERT INTO images (owner_id, url, storage_key, sha, dhash, phash, dhash_m, phash_m)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id, url""",
              (u["id"], url, key, fp["sha"], s["dhash"], s["phash"], s["dhash_m"], s["phash_m"]))
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
def parse_listing(d):
    title, desc = text(d, "title", 120), text(d, "description", 3000)
    city, commune, deal, ptype = d.get("city"), d.get("commune"), d.get("deal"), d.get("ptype")
    address = text(d, "address", 160)
    if deal not in DEALS or ptype not in PTYPES:
        abort(400, "Type d'offre ou de bien invalide.")
    if city not in CITIES or commune not in CITIES[city]:
        abort(400, "Localisation invalide (ville / commune).")
    if len(title) < 8 or len(address) < 5:
        abort(400, "Titre (8+ caractères) et adresse (5+) requis.")
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
    return dict(title=title, description=desc, deal=deal, ptype=ptype, city=city, commune=commune, address=address,
                price=round(price, 2), bedrooms=bedrooms, bathrooms=bathrooms, surface=surface,
                furnished=d.get("furnished") in (True, 1, "1", "true", "on"),
                amenities=[x for x in dict.fromkeys(am) if x in AMENITIES])


@bp.post("/listings")
@require("host", verified_email=True)
def create_listing():
    u, d = current_user(), body()
    run("SELECT pg_advisory_xact_lock(7002, %s)", (u["id"] % 2_000_000_000,))  # quota atomique par hôte
    if one("SELECT COUNT(*)::int AS n FROM listings WHERE owner_id=%s AND created_at > now() - interval '1 day'",
           (u["id"],))["n"] >= MAX_LISTINGS_PER_DAY:
        abort(429, f"Limite de {MAX_LISTINGS_PER_DAY} annonces par 24 h atteinte.")
    data = parse_listing(d)

    for field in ("title", "description"):
        hit = af.find_contact_info(data[field])
        if hit:
            abort(400, f"Coordonnées interdites dans « {field} » ({hit}). Les échanges doivent rester sur Ndaku.")
    key = af.addr_key(data["city"], data["commune"], data["address"])
    clash = all_("SELECT owner_id FROM listings WHERE addr_key=%s AND deal=%s AND status IN ('active','pending')",
                 (key, data["deal"]))
    if any(r["owner_id"] != u["id"] for r in clash):
        abort(409, "Ce bien est déjà publié par un autre hôte à cette adresse. Contactez le support si c'est une erreur.")
    if clash:
        abort(409, "Vous avez déjà une annonce active pour cette adresse.")

    ids = d.get("image_ids")
    if not isinstance(ids, list) or not all(isinstance(i, int) for i in ids) or len(set(ids)) != len(ids):
        abort(400, "Liste de photos invalide.")
    if not MIN_IMAGES <= len(ids) <= MAX_IMAGES:
        abort(400, f"Ajoutez entre {MIN_IMAGES} et {MAX_IMAGES} photos.")
    owned = all_("SELECT id FROM images WHERE id = ANY(%s) AND owner_id=%s AND listing_id IS NULL FOR UPDATE",
                 (ids, u["id"]))
    if len(owned) != len(ids):
        abort(400, "Certaines photos n'existent pas, ne vous appartiennent pas ou sont déjà utilisées.")

    score, reasons = 0, []
    comps = all_("SELECT price::float8 AS price, surface FROM listings WHERE status='active' AND city=%s AND deal=%s "
                 "AND ptype=%s ORDER BY created_at DESC LIMIT 500", (data["city"], data["deal"], data["ptype"]))
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
    if now() - u["created_at"] < timedelta(hours=1):
        score += 10
        reasons.append("Compte créé il y a moins d'une heure")
    if not u["verified"]:
        score += 10
        reasons.append("Hôte non vérifié")
    status = "pending" if score >= af.RISK_PENDING_THRESHOLD else "active"

    row = one("""INSERT INTO listings (owner_id, title, description, deal, ptype, city, commune, address, price,
                   bedrooms, bathrooms, surface, furnished, amenities, status, risk_score, risk_reasons, addr_key)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
              (u["id"], data["title"], data["description"], data["deal"], data["ptype"], data["city"],
               data["commune"], data["address"], data["price"], data["bedrooms"], data["bathrooms"], data["surface"],
               data["furnished"], json.dumps(data["amenities"]), status, score, json.dumps(reasons), key))
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
    run("UPDATE listings SET status=%s WHERE id=%s", (status, lid))
    return jsonify(ok=True)


@bp.delete("/listings/<int:lid>")
@require()
def delete_listing(lid):
    r = owned_listing(lid)
    if r["status"] == "rejected" and current_user()["role"] != "admin":
        abort(400, "Une annonce rejetée par la modération est conservée (ses photos restent bannies).")
    keys = [x["storage_key"] for x in all_("SELECT storage_key FROM images WHERE listing_id=%s", (lid,))]
    run("DELETE FROM listings WHERE id=%s", (lid,))
    storage().delete(keys)
    return jsonify(ok=True)


@bp.get("/my/listings")
@require("host")
def my_listings():
    rows = all_(f"""{BASE_SQL} WHERE l.owner_id=%s ORDER BY l.created_at DESC""", (current_user()["id"],))
    counts = {r["listing_id"]: r["n"] for r in all_(
        "SELECT listing_id, COUNT(*)::int AS n FROM inquiries WHERE listing_id IN "
        "(SELECT id FROM listings WHERE owner_id=%s) GROUP BY 1", (current_user()["id"],))}
    return jsonify(items=[{**card(r), "risk_reasons": r["risk_reasons"], "inquiries": counts.get(r["id"], 0)}
                          for r in rows])


# ----------------------------------------------------- favoris / visites / avis / signalements
def active_or_404(lid):
    r = one("SELECT id, owner_id FROM listings WHERE id=%s AND status='active'", (lid,))
    if not r:
        abort(404, "Annonce introuvable.")
    return r


@bp.post("/listings/<int:lid>/favorite")
@require()
def toggle_fav(lid):
    active_or_404(lid)
    uid = current_user()["id"]
    if run("DELETE FROM favorites WHERE user_id=%s AND listing_id=%s", (uid, lid)).rowcount:
        return jsonify(favorite=False)
    run("INSERT INTO favorites VALUES (%s,%s) ON CONFLICT DO NOTHING", (uid, lid))
    return jsonify(favorite=True)


@bp.get("/favorites")
@require()
def favorites():
    rows = all_(f"{BASE_SQL} WHERE l.status='active' AND l.id IN (SELECT listing_id FROM favorites WHERE user_id=%s)",
                (current_user()["id"],))
    return jsonify(items=[card(r, {r["id"] for r in rows}) for r in rows])


@bp.post("/listings/<int:lid>/inquiries")
@require("client")
def inquire(lid):
    active_or_404(lid)
    u, d = current_user(), body()
    rate_limit(f"inquiry:{u['id']}", 10, 3600, "Trop de messages envoyés. Patientez un peu.")
    msg = text(d, "message", 1000)
    if len(msg) < 10:
        abort(400, "Message trop court.")
    pref = None
    if d.get("preferred_date"):
        try:
            pref = date.fromisoformat(str(d["preferred_date"])[:10])
        except ValueError:
            abort(400, "Date invalide.")
        if not date.today() <= pref <= date.today() + timedelta(days=365):
            abort(400, "Date de visite hors limites.")
    run("INSERT INTO inquiries (listing_id, user_id, message, preferred_date) VALUES (%s,%s,%s,%s)",
        (lid, u["id"], msg, pref))
    return jsonify(ok=True), 201


@bp.get("/my/inquiries")
@require()
def my_inquiries():
    u = current_user()
    if u["role"] == "host":
        # Le téléphone du client n'est montré qu'à l'hôte de l'annonce concernée.
        sql = """SELECT q.id, q.listing_id, q.message, q.preferred_date::text, extract(epoch FROM q.created_at)::float8
                   AS created_at, l.title, c.name AS who, c.phone AS who_phone
                 FROM inquiries q JOIN listings l ON l.id=q.listing_id JOIN users c ON c.id=q.user_id
                 WHERE l.owner_id=%s ORDER BY q.created_at DESC LIMIT 200"""
    else:
        sql = """SELECT q.id, q.listing_id, q.message, q.preferred_date::text, extract(epoch FROM q.created_at)::float8
                   AS created_at, l.title, h.name AS who, NULL AS who_phone
                 FROM inquiries q JOIN listings l ON l.id=q.listing_id JOIN users h ON h.id=l.owner_id
                 WHERE q.user_id=%s ORDER BY q.created_at DESC LIMIT 200"""
    return jsonify(items=all_(sql, (u["id"],)))


@bp.post("/listings/<int:lid>/reviews")
@require("client")
def review(lid):
    active_or_404(lid)
    u, d = current_user(), body()
    if not one("SELECT 1 FROM inquiries WHERE listing_id=%s AND user_id=%s", (lid, u["id"])):
        abort(403, "Seuls les clients ayant contacté l'hôte peuvent laisser un avis vérifié.")
    rating, comment = d.get("rating"), text(d, "comment", 800)
    if isinstance(rating, str) and rating.isdigit():
        rating = int(rating)
    if not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 5 or len(comment) < 10:
        abort(400, "Note de 1 à 5 et commentaire de 10 caractères minimum.")
    if not one("""INSERT INTO reviews (listing_id, user_id, rating, comment) VALUES (%s,%s,%s,%s)
                  ON CONFLICT (listing_id, user_id) DO NOTHING RETURNING id""", (lid, u["id"], rating, comment)):
        abort(409, "Vous avez déjà noté cette annonce.")
    return jsonify(ok=True), 201


@bp.post("/listings/<int:lid>/report")
@require()
def report(lid):
    r = active_or_404(lid)
    u = current_user()
    if r["owner_id"] == u["id"]:
        abort(404, "Annonce introuvable.")
    rate_limit(f"report:{u['id']}", 20, 86400)
    reason = text(body(), "reason", 300)
    if len(reason) < 5:
        abort(400, "Précisez le motif du signalement.")
    if not one("""INSERT INTO reports (listing_id, user_id, reason) VALUES (%s,%s,%s)
                  ON CONFLICT (listing_id, user_id) DO NOTHING RETURNING id""", (lid, u["id"], reason)):
        abort(409, "Vous avez déjà signalé cette annonce.")
    n = one("SELECT COUNT(*)::int AS n FROM reports WHERE listing_id=%s", (lid,))["n"]
    if n >= REPORTS_TO_HIDE:  # masquage automatique en attendant la modération
        run("""UPDATE listings SET status='pending', risk_score=risk_score+50,
                 risk_reasons = risk_reasons || %s::jsonb WHERE id=%s""",
            (json.dumps([f"{n} signalements d'utilisateurs"]), lid))
    return jsonify(ok=True)

