"""Services de confiance : notifications, alertes de recherche, agenda de visites, avis sur les hôtes,
vérification d'identité (pièce + selfie), statistiques hôte et prix du marché."""
import hashlib
import io
from datetime import datetime, timedelta, timezone

from flask import Blueprint, abort, current_app, g, jsonify, request

from . import antifraud as af
from .auth import body, text
from .db import all_, one, run
from .messages import add_message
from .notify import flush_pending, notify
from .security import audit, client_ip, current_user, now, rate_limit, require

bp = Blueprint("services", __name__, url_prefix="/api")
MAX_ALERTS = 10
MAX_OPEN_SLOTS = 60
ID_TYPES = {"electeur": "Carte d'électeur", "passeport": "Passeport", "permis": "Permis de conduire",
            "carte_id": "Carte d'identité"}


def _int(v, lo=None, hi=None):
    if v in (None, ""):
        return None
    if isinstance(v, bool):
        abort(400, "Valeur invalide.")
    try:
        v = int(v)
    except (TypeError, ValueError):
        abort(400, "Valeur invalide.")
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        abort(400, "Valeur hors limites.")
    return v


# ===================================================================== notifications
@bp.get("/notifications")
@require()
def notifications():
    uid = current_user()["id"]
    rows = all_("""SELECT id, kind, title, body, link, read_at IS NOT NULL AS read,
                          extract(epoch FROM created_at)::float8 AS created_at
                   FROM notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT 50""", (uid,))
    return jsonify(items=rows)


@bp.post("/notifications/read")
@require()
def notifications_read():
    run("UPDATE notifications SET read_at=now() WHERE user_id=%s AND read_at IS NULL", (current_user()["id"],))
    return jsonify(ok=True)


# ======================================================================== alertes
ALERT_FIELDS = ("deal", "ptype", "province_id", "city_id", "commune_id", "quartier_id", "min_price", "max_price",
                "min_bedrooms", "furnished", "min_elec", "min_water")


@bp.get("/alerts")
@require()
def alerts():
    rows = all_(f"""SELECT id, label, {', '.join(ALERT_FIELDS)}, extract(epoch FROM created_at)::float8 AS created_at
                    FROM search_alerts WHERE user_id=%s ORDER BY created_at DESC""", (current_user()["id"],))
    for r in rows:
        for k in ("min_price", "max_price"):
            r[k] = float(r[k]) if r[k] is not None else None
    return jsonify(items=rows)


@bp.post("/alerts")
@require()
def create_alert():
    u, d = current_user(), body()
    if one("SELECT COUNT(*)::int AS n FROM search_alerts WHERE user_id=%s", (u["id"],))["n"] >= MAX_ALERTS:
        abort(400, f"Maximum {MAX_ALERTS} alertes. Supprimez-en une pour en créer une autre.")
    deal = d.get("deal") if d.get("deal") in ("location", "vente") else None
    ptype = d.get("ptype") if d.get("ptype") in ("maison", "appartement", "villa", "studio", "terrain") else None
    vals = {"deal": deal, "ptype": ptype, "furnished": d.get("furnished") in (True, "1", 1),
            **{k: _int(d.get(k), 1) for k in ("province_id", "city_id", "commune_id", "quartier_id")},
            "min_price": _int(d.get("min_price"), 0, 10**9), "max_price": _int(d.get("max_price"), 0, 10**9),
            "min_bedrooms": _int(d.get("bedrooms"), 0, 20), "min_elec": _int(d.get("min_elec"), 1, 10),
            "min_water": _int(d.get("min_water"), 1, 10)}
    if not any(v for k, v in vals.items() if k != "furnished") and not vals["furnished"]:
        abort(400, "Précisez au moins un critère (lieu, type, budget…).")
    label = text(d, "label", 120) or "Ma recherche"
    row = one(f"""INSERT INTO search_alerts (user_id, label, {', '.join(ALERT_FIELDS)})
                  VALUES (%s,%s,{', '.join(['%s'] * len(ALERT_FIELDS))}) RETURNING id""",
              (u["id"], label, *[vals[k] for k in ALERT_FIELDS]))
    return jsonify(id=row["id"]), 201


@bp.delete("/alerts/<int:aid>")
@require()
def delete_alert(aid):
    if not one("DELETE FROM search_alerts WHERE id=%s AND user_id=%s RETURNING id", (aid, current_user()["id"])):
        abort(404, "Alerte introuvable.")
    return jsonify(ok=True)


def match_alerts(lid):
    """Prévient les utilisateurs dont une alerte correspond à une annonce qui vient d'être mise en ligne."""
    # alerted_at : une annonce ne déclenche les alertes qu'une fois (pas de renvoi après re-modération)
    l = one("UPDATE listings SET alerted_at=now() WHERE id=%s AND status='active' AND alerted_at IS NULL "
            "AND NOT is_demo RETURNING *", (lid,))
    if not l:
        return 0
    rows = all_("""SELECT DISTINCT ON (a.user_id) a.user_id, a.label FROM search_alerts a
                   JOIN users u ON u.id=a.user_id AND u.suspended_at IS NULL
                   WHERE a.user_id <> %(owner)s
                     AND (a.deal IS NULL OR a.deal=%(deal)s) AND (a.ptype IS NULL OR a.ptype=%(ptype)s)
                     AND (a.province_id IS NULL OR a.province_id=%(province_id)s)
                     AND (a.city_id IS NULL OR a.city_id=%(city_id)s)
                     AND (a.commune_id IS NULL OR a.commune_id=%(commune_id)s)
                     AND (a.quartier_id IS NULL OR a.quartier_id=%(quartier_id)s)
                     AND (a.min_price IS NULL OR %(price)s >= a.min_price)
                     AND (a.max_price IS NULL OR %(price)s <= a.max_price)
                     AND (a.min_bedrooms IS NULL OR %(bedrooms)s >= a.min_bedrooms)
                     AND (NOT a.furnished OR %(furnished)s)
                     AND (a.min_elec IS NULL OR COALESCE(%(elec)s, 0) >= a.min_elec)
                     AND (a.min_water IS NULL OR COALESCE(%(water)s, 0) >= a.min_water)
                   LIMIT 300""",
                {"owner": l["owner_id"], "deal": l["deal"], "ptype": l["ptype"], "province_id": l["province_id"],
                 "city_id": l["city_id"], "commune_id": l["commune_id"], "quartier_id": l["quartier_id"],
                 "price": l["price"], "bedrooms": l["bedrooms"], "furnished": l["furnished"],
                 "elec": l["elec_score"], "water": l["water_score"]})
    for r in rows:
        notify(r["user_id"], "alert", f"Nouvelle annonce pour « {r['label']} »",
               f"{l['title']} — {l['commune']}, {l['city']}", f"#/listing/{lid}", defer=True)
    flush_pending(limit=20, budget=3.0)
    return len(rows)


# =================================================================== agenda de visites
def _iso(v, what):
    try:
        t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        abort(400, f"{what} invalide.")
    if t.tzinfo is None:
        abort(400, f"{what} : fuseau horaire manquant.")
    return t.astimezone(timezone.utc)


def _slot_out(r, uid=None):
    return {"id": r["id"], "starts_at": r["starts_at"].timestamp(), "ends_at": r["ends_at"].timestamp(),
            "status": r["status"], "mine": uid is not None and r["booked_by"] == uid}


@bp.get("/listings/<int:lid>/slots")
def slots(lid):
    u = current_user()
    l = one("SELECT owner_id, status FROM listings WHERE id=%s", (lid,))
    if not l or (l["status"] != "active" and not (u and u["id"] == l["owner_id"])):
        abort(404, "Annonce introuvable.")
    is_owner = bool(u and u["id"] == l["owner_id"])
    rows = all_("""SELECT s.*, b.name AS booker FROM visit_slots s LEFT JOIN users b ON b.id=s.booked_by
                   WHERE s.listing_id=%s AND s.ends_at > now() AND s.status <> 'cancelled'
                   ORDER BY s.starts_at LIMIT 100""", (lid,))
    out = []
    for r in rows:
        if r["status"] == "booked" and not is_owner and not (u and r["booked_by"] == u["id"]):
            continue  # les créneaux pris par d'autres ne sont pas exposés
        s = _slot_out(r, u["id"] if u else None)
        if is_owner and r["status"] == "booked":
            s["booker"], s["conversation_id"] = r["booker"], r["conversation_id"]
        out.append(s)
    return jsonify(items=out, owner=is_owner)


@bp.post("/listings/<int:lid>/slots")
@require("host")
def add_slots(lid):
    u, d = current_user(), body()
    if not one("SELECT 1 FROM listings WHERE id=%s AND owner_id=%s AND status IN ('active','pending')", (lid, u["id"])):
        abort(404, "Annonce introuvable.")
    starts = d.get("starts") if isinstance(d.get("starts"), list) else [d.get("starts_at")]
    minutes = _int(d.get("duration", 30), 15, 180)
    if not starts or len(starts) > 20:
        abort(400, "Indiquez entre 1 et 20 créneaux.")
    if one("SELECT COUNT(*)::int AS n FROM visit_slots WHERE listing_id=%s AND status='open' AND ends_at > now()",
           (lid,))["n"] + len(starts) > MAX_OPEN_SLOTS:
        abort(400, f"Maximum {MAX_OPEN_SLOTS} créneaux ouverts par annonce.")
    created = 0
    for v in starts:
        t = _iso(v, "Date du créneau")
        if not now() + timedelta(minutes=30) <= t <= now() + timedelta(days=90):
            abort(400, "Les créneaux doivent être entre 30 minutes et 90 jours à l'avance.")
        created += run("""INSERT INTO visit_slots (listing_id, starts_at, ends_at) VALUES (%s,%s,%s)
                          ON CONFLICT (listing_id, starts_at) DO UPDATE
                          SET status='open', ends_at=EXCLUDED.ends_at, booked_by=NULL, booked_at=NULL, conversation_id=NULL
                          WHERE visit_slots.status='cancelled'""",
                       (lid, t, t + timedelta(minutes=minutes))).rowcount
    return jsonify(created=created), 201


def _slot(sid):
    s = one("""SELECT s.*, l.owner_id, l.title, l.status AS listing_status FROM visit_slots s
               JOIN listings l ON l.id=s.listing_id WHERE s.id=%s""", (sid,))
    if not s:
        abort(404, "Créneau introuvable.")
    return s


def _fmt(t):
    return t.astimezone(timezone(timedelta(hours=1))).strftime("%d/%m/%Y à %Hh%M") + " (heure de Kinshasa)"


@bp.post("/slots/<int:sid>/book")
@require(avatar=True)
def book(sid):
    u = current_user()
    s = _slot(sid)
    if s["listing_status"] != "active" or s["owner_id"] == u["id"]:
        abort(404, "Créneau introuvable.")
    rate_limit(f"book:{u['id']}", 10, 86400, "Trop de réservations aujourd'hui.")
    # Verrou (annonce, client) : deux réservations simultanées du même client ne passent pas toutes les deux.
    run("SELECT pg_advisory_xact_lock(7003, hashtext(%s))", (f"{s['listing_id']}:{u['id']}",))
    if one("""SELECT 1 FROM visit_slots WHERE listing_id=%s AND booked_by=%s AND status='booked' AND ends_at > now()""",
           (s["listing_id"], u["id"])):
        abort(409, "Vous avez déjà une visite réservée pour ce bien.")
    # Réservation atomique : un seul client peut prendre le créneau, même en cas de clics simultanés.
    if not one("""UPDATE visit_slots SET status='booked', booked_by=%s, booked_at=now()
                  WHERE id=%s AND status='open' AND starts_at > now() RETURNING id""", (u["id"], sid)):
        abort(409, "Ce créneau vient d'être réservé ou n'est plus disponible.")
    c = one("""INSERT INTO conversations (listing_id, client_id, host_id) VALUES (%s,%s,%s)
               ON CONFLICT (listing_id, client_id) DO UPDATE SET listing_id=EXCLUDED.listing_id RETURNING *""",
            (s["listing_id"], u["id"], s["owner_id"]))
    if c["blocked_by"]:
        abort(403, "Cette conversation a été bloquée.")
    run("UPDATE visit_slots SET conversation_id=%s WHERE id=%s", (c["id"], sid))
    note = text(request.get_json(silent=True) or {}, "message", 500)
    add_message(c, u["id"], f"J'ai réservé une visite le {_fmt(s['starts_at'])}." + (f"\n{note}" if note else ""),
                "visit", {"slot_id": sid, "date": s["starts_at"].date().isoformat()})
    notify(s["owner_id"], "visit", f"Visite réservée : {s['title']}", _fmt(s["starts_at"]), f"#/messages/{c['id']}")
    return jsonify(ok=True, conversation_id=c["id"])


@bp.post("/slots/<int:sid>/cancel")
@require()
def cancel(sid):
    """Le client annule sa réservation (le créneau redevient libre) ; l'hôte supprime un créneau."""
    u = current_user()
    s = _slot(sid)
    if s["booked_by"] == u["id"] and s["status"] == "booked":
        run("UPDATE visit_slots SET status='open', booked_by=NULL, booked_at=NULL, conversation_id=NULL WHERE id=%s", (sid,))
        if s["conversation_id"]:
            c = one("SELECT * FROM conversations WHERE id=%s", (s["conversation_id"],))
            add_message(c, u["id"], f"J'ai annulé ma visite du {_fmt(s['starts_at'])}.")
        notify(s["owner_id"], "visit", f"Visite annulée : {s['title']}", _fmt(s["starts_at"]), "#/host")
        return jsonify(ok=True)
    if s["owner_id"] == u["id"]:
        run("UPDATE visit_slots SET status='cancelled' WHERE id=%s", (sid,))
        if s["status"] == "booked" and s["booked_by"]:
            if s["conversation_id"]:
                c = one("SELECT * FROM conversations WHERE id=%s", (s["conversation_id"],))
                add_message(c, u["id"], f"Je dois annuler la visite du {_fmt(s['starts_at'])}. Choisissons un autre créneau.")
            notify(s["booked_by"], "visit", f"Visite annulée par l'hôte : {s['title']}", _fmt(s["starts_at"]),
                   f"#/listing/{s['listing_id']}")
        return jsonify(ok=True)
    abort(404, "Créneau introuvable.")


# ===================================================================== profil public de l'hôte
@bp.get("/hosts/<int:hid>")
def host_profile(hid):
    from .listings import BASE_SQL, VISIBLE, card
    h = one("""SELECT id, name, avatar_url, verified, extract(epoch FROM created_at)::float8 AS since,
                      host_rating_sum, host_rating_count FROM users WHERE id=%s AND role IN ('host','admin')
                      AND suspended_at IS NULL""", (hid,))
    if not h:
        abort(404, "Hôte introuvable.")
    u = current_user()
    listings = all_(f"{BASE_SQL} WHERE l.owner_id=%s AND {VISIBLE} ORDER BY l.created_at DESC LIMIT 30", (hid,))
    reviews = all_("""SELECT r.rating, r.comment, extract(epoch FROM r.created_at)::float8 AS created_at,
                             u.name, u.avatar_url AS avatar
                      FROM host_reviews r JOIN users u ON u.id=r.user_id WHERE r.host_id=%s
                      ORDER BY r.created_at DESC LIMIT 30""", (hid,))
    n = h["host_rating_count"]
    return jsonify(id=h["id"], name=h["name"], avatar=h["avatar_url"], verified=h["verified"], since=h["since"],
                   rating=round(h["host_rating_sum"] / n, 2) if n else None, reviews_count=n,
                   listings=[card(r) for r in listings], reviews=reviews,
                   can_review=bool(u and _can_review_host(u["id"], hid)))


def _can_review_host(uid, hid):
    """Avoir écrit dans une conversation avec cet hôte, et ne pas l'avoir déjà noté."""
    return uid != hid and bool(one("""SELECT 1 FROM conversations c WHERE c.client_id=%s AND c.host_id=%s
                                        AND EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id=c.id AND m.sender_id=%s)
                                        AND NOT EXISTS (SELECT 1 FROM host_reviews r WHERE r.host_id=%s AND r.user_id=%s)""",
                                   (uid, hid, uid, hid, uid)))


@bp.post("/hosts/<int:hid>/reviews")
@require(avatar=True)
def review_host(hid):
    u, d = current_user(), body()
    if not _can_review_host(u["id"], hid):
        abort(403, "Seuls les clients ayant échangé avec cet hôte peuvent le noter, une seule fois.")
    rating, comment = d.get("rating"), text(d, "comment", 800)
    if isinstance(rating, str) and rating.isdigit():
        rating = int(rating)
    if not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 5 or len(comment) < 10:
        abort(400, "Note de 1 à 5 et commentaire de 10 caractères minimum.")
    if not one("""INSERT INTO host_reviews (host_id, user_id, rating, comment) VALUES (%s,%s,%s,%s)
                  ON CONFLICT (host_id, user_id) DO NOTHING RETURNING id""", (hid, u["id"], rating, comment)):
        abort(409, "Vous avez déjà noté cet hôte.")
    run("UPDATE users SET host_rating_sum=host_rating_sum+%s, host_rating_count=host_rating_count+1 WHERE id=%s",
        (rating, hid))
    notify(hid, "review", "Vous avez reçu un nouvel avis", f"{rating}/5", f"#/hote/{hid}", external=False)
    return jsonify(ok=True), 201


# ================================================================ vérification d'identité
def _doc(file, what):
    if not file:
        abort(400, f"{what} manquant.")
    try:
        img = af.load_image(file.read(), min_w=400, min_h=300)
    except af.ImageRejected as e:
        abort(422, f"{what} : {e}")
    img.thumbnail((1600, 1600))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)  # ré-encodé : métadonnées (GPS…) supprimées
    return out.getvalue()


@bp.get("/verification")
@require("host")
def my_verification():
    r = one("""SELECT status, note, extract(epoch FROM created_at)::float8 AS created_at FROM id_verifications
               WHERE user_id=%s ORDER BY created_at DESC LIMIT 1""", (current_user()["id"],))
    return jsonify(verified=current_user()["verified"], request=r, id_types=ID_TYPES)


@bp.post("/verification")
@require("host", avatar=True)
def submit_verification():
    u = current_user()
    if u["verified"]:
        abort(400, "Votre identité est déjà vérifiée.")
    rate_limit(f"kyc:{u['id']}", 3, 86400, "Trop de demandes aujourd'hui.")
    id_type = request.form.get("id_type")
    if id_type not in ID_TYPES:
        abort(400, "Type de pièce invalide.")
    id_doc, selfie = _doc(request.files.get("id_doc"), "Photo de la pièce"), _doc(request.files.get("selfie"), "Selfie")
    if one("SELECT 1 FROM id_verifications WHERE user_id=%s AND status='pending'", (u["id"],)):
        abort(409, "Une demande est déjà en cours d'examen.")
    run("INSERT INTO id_verifications (user_id, id_type, id_doc, selfie) VALUES (%s,%s,%s,%s)",
        (u["id"], id_type, id_doc, selfie))
    audit("kyc_submitted", u["id"])
    return jsonify(ok=True), 201


@bp.get("/admin/verifications")
@require("admin")
def pending_verifications():
    return jsonify(items=all_("""SELECT v.id, v.id_type, extract(epoch FROM v.created_at)::float8 AS created_at,
                                   u.id AS user_id, u.name, u.email, u.avatar_url AS avatar,
                                   (SELECT COUNT(*) FROM listings l WHERE l.owner_id=u.id)::int AS listings
                                 FROM id_verifications v JOIN users u ON u.id=v.user_id
                                 WHERE v.status='pending' ORDER BY v.created_at LIMIT 100"""), id_types=ID_TYPES)


@bp.get("/admin/verifications/<int:vid>/<doc>")
@require("admin")
def verification_doc(vid, doc):
    """Documents servis uniquement aux administrateurs, jamais mis en cache."""
    if doc not in ("id_doc", "selfie"):
        abort(404)
    r = one(f"SELECT {doc} AS data FROM id_verifications WHERE id=%s AND status='pending'", (vid,))
    if not r or not r["data"]:
        abort(404)
    resp = current_app.response_class(bytes(r["data"]), mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Content-Security-Policy"] = "default-src 'none'"
    audit("kyc_viewed", current_user()["id"], verification_id=vid, doc=doc)
    return resp


@bp.post("/admin/verifications/<int:vid>/decision")
@require("admin")
def decide_verification(vid):
    d = body()
    act, note = d.get("action"), text(d, "note", 300)
    if act not in ("approve", "reject"):
        abort(400, "Action invalide.")
    # Les documents sont effacés dès la décision (minimisation des données personnelles).
    r = one("""UPDATE id_verifications SET status=%s, note=%s, decided_at=now(), decided_by=%s, id_doc=NULL, selfie=NULL
               WHERE id=%s AND status='pending' RETURNING user_id""",
            ("approved" if act == "approve" else "rejected", note, current_user()["id"], vid))
    if not r:
        abort(404, "Demande introuvable.")
    if act == "approve":
        run("UPDATE users SET verified=TRUE WHERE id=%s", (r["user_id"],))
    notify(r["user_id"], "kyc", "Identité vérifiée ✓" if act == "approve" else "Vérification d'identité refusée",
           note or ("Le badge « Hôte vérifié » apparaît sur vos annonces." if act == "approve"
                    else "Vous pouvez renvoyer une demande avec des photos nettes."), "#/profile")
    audit(f"kyc_{act}", current_user()["id"], target=r["user_id"])
    return jsonify(ok=True)


# ======================================================================= statistiques
def record_view(lid, owner_id):
    """Vue unique par visiteur et par jour ; le visiteur est identifié par un hachage (pas d'IP stockée)."""
    u = current_user()
    if u and u["id"] == owner_id:
        return
    who = f"u{u['id']}" if u else f"{client_ip()}|{request.user_agent.string[:120]}"
    viewer = hashlib.sha256(f"{who}|{datetime.now(timezone.utc).date()}".encode()).hexdigest()[:32]
    if run("INSERT INTO listing_views (listing_id, viewer) VALUES (%s,%s) ON CONFLICT DO NOTHING",
           (lid, viewer)).rowcount:
        run("UPDATE listings SET views = views + 1 WHERE id=%s", (lid,))


@bp.get("/my/stats")
@require("host")
def my_stats():
    uid = current_user()["id"]
    rows = all_("""SELECT l.id, l.title, l.status, l.views, l.fav_count,
                          (SELECT COUNT(*) FROM conversations c WHERE c.listing_id=l.id)::int AS contacts,
                          (SELECT COUNT(*) FROM visit_slots s WHERE s.listing_id=l.id AND s.status='booked')::int AS visits
                   FROM listings l WHERE l.owner_id=%s ORDER BY l.created_at DESC""", (uid,))
    days = all_("""SELECT v.day::text AS day, COUNT(*)::int AS n FROM listing_views v JOIN listings l ON l.id=v.listing_id
                   WHERE l.owner_id=%s AND v.day > CURRENT_DATE - 30 GROUP BY 1 ORDER BY 1""", (uid,))
    return jsonify(items=rows, daily=days)


@bp.get("/stats/prices")
def price_stats():
    """Prix médians par mois (12 derniers mois) pour une commune ou une ville, et par commune d'une ville."""
    a = request.args
    deal = a.get("deal") if a.get("deal") in ("location", "vente") else "location"
    commune_id, city_id = _int(a.get("commune_id"), 1), _int(a.get("city_id"), 1)
    if not commune_id and not city_id:
        abort(400, "Précisez une ville ou une commune.")
    col, val = ("commune_id", commune_id) if commune_id else ("city_id", city_id)
    metric = "l.price" if deal == "location" else "l.price / NULLIF(l.surface, 0)"
    monthly = all_(f"""SELECT to_char(date_trunc('month', l.created_at), 'YYYY-MM') AS month,
                              percentile_cont(0.5) WITHIN GROUP (ORDER BY {metric})::float8 AS median, COUNT(*)::int AS n
                       FROM listings l WHERE l.{col}=%s AND l.deal=%s AND l.status IN ('active','closed')
                         AND l.created_at > now() - interval '12 months' AND NOT l.is_demo
                       GROUP BY 1 ORDER BY 1""", (val, deal))
    current = one(f"""SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY {metric})::float8 AS median, COUNT(*)::int AS n
                      FROM listings l WHERE l.{col}=%s AND l.deal=%s AND l.status='active' AND NOT l.is_demo""",
                  (val, deal))
    by_commune = []
    if city_id and not commune_id:
        by_commune = all_(f"""SELECT l.commune, percentile_cont(0.5) WITHIN GROUP (ORDER BY {metric})::float8 AS median,
                                     COUNT(*)::int AS n
                              FROM listings l WHERE l.city_id=%s AND l.deal=%s AND l.status='active' AND NOT l.is_demo
                              GROUP BY 1 HAVING COUNT(*) >= 2 ORDER BY median DESC""", (city_id, deal))
    g.cache_seconds = 3600
    return jsonify(deal=deal, unit="mois" if deal == "location" else "m²", monthly=monthly, current=current,
                   by_commune=by_commune)

