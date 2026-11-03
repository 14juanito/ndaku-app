"""Professionnels de l'immobilier : agents indépendants (dossier validé par l'administration) et agences
(créées par l'administration), leurs catalogues publics, l'espace agence et les statistiques."""
import io
import re
import unicodedata

from flask import Blueprint, abort, current_app, g, jsonify, request

from . import antifraud as af
from .auth import body, text
from .db import all_, one, run
from .notify import notify
from .security import audit, current_user, rate_limit, require

bp = Blueprint("pros", __name__, url_prefix="/api")
MANDATES = {"proprietaire": "Propriétaire direct", "simple": "Mandat simple", "exclusif": "Mandat exclusif"}
AGENT_FEATURED_QUOTA = 3
MAX_PRO_DOCS = 3
LOGO_SIZE = 400


# =========================================================================== droits
def membership(uid):
    """Agence active de l'utilisateur (ou None)."""
    return one("""SELECT m.role AS member_role, m.title, a.* FROM agency_members m JOIN agencies a ON a.id=m.agency_id
                  WHERE m.user_id=%s""", (uid,))


def publisher(u):
    """Peut-on publier, et pour qui ? → (ok, agency_id, motif du refus)."""
    if u["role"] == "host":
        return True, None, ""
    if u["role"] == "agent":
        m = membership(u["id"])
        if m:
            if m["status"] != "active":
                return False, None, "Votre agence est suspendue : publication impossible."
            return True, m["id"], ""
        if u["agent_status"] == "approved":
            return True, None, ""
        return False, None, ("Votre dossier d'agent est en cours d'examen par l'équipe Ndaku."
                             if u["agent_status"] == "pending" else
                             "Envoyez votre dossier d'agent immobilier pour pouvoir publier.")
    return False, None, "Seuls les hôtes et les agents vérifiés peuvent publier."


def require_publisher():
    ok, agency_id, why = publisher(current_user())
    if not ok:
        abort(403, why)
    return agency_id


def _my_agency(manager=False):
    m = membership(current_user()["id"])
    if not m:
        abort(404, "Vous ne faites partie d'aucune agence.")
    if m["status"] != "active":
        abort(403, "Cette agence est suspendue. Contactez l'équipe Ndaku.")
    if manager and m["member_role"] != "manager":
        abort(403, "Action réservée au gérant de l'agence.")
    return m


def _image_upload(file, what, min_w=300, min_h=200):
    if not file:
        abort(400, f"{what} manquant.")
    try:
        img = af.load_image(file.read(), min_w=min_w, min_h=min_h)
    except af.ImageRejected as e:
        abort(422, f"{what} : {e}")
    img.thumbnail((1600, 1600))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85)  # ré-encodé : métadonnées (GPS…) supprimées
    return out.getvalue()


def slugify(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60] or "agence"
    base, i = s, 2
    while one("SELECT 1 FROM agencies WHERE slug=%s", (s,)):
        s, i = f"{base}-{i}", i + 1
    return s


# ====================================================================== réactivité
def response_stats(where, args, days=90):
    """Délai médian de première réponse du professionnel et taux de réponse, sur des conversations."""
    r = one(f"""WITH f AS (
                  SELECT (SELECT min(m.created_at) FROM messages m WHERE m.conversation_id=c.id AND m.sender_id=c.client_id) AS q,
                         c.id, c.client_id, c.host_id
                  FROM conversations c JOIN listings l ON l.id=c.listing_id
                  WHERE {where} AND c.created_at > now() - make_interval(days => %s))
                SELECT COUNT(*)::int AS total,
                       COUNT(a.at)::int AS answered,
                       percentile_cont(0.5) WITHIN GROUP (ORDER BY extract(epoch FROM a.at - f.q))::float8 AS median_s
                FROM f LEFT JOIN LATERAL (SELECT min(m.created_at) AS at FROM messages m
                                          WHERE m.conversation_id=f.id AND m.sender_id=f.host_id AND m.created_at >= f.q) a ON TRUE
                WHERE f.q IS NOT NULL""", (*args, days))
    rate = round(r["answered"] / r["total"] * 100) if r["total"] else None
    return {"conversations": r["total"], "response_rate": rate,
            "response_minutes": round(r["median_s"] / 60) if r["median_s"] is not None else None}


# ====================================================================== affichages
@bp.post("/impressions")
def impressions():
    """Annonces réellement affichées à l'écran dans les résultats (base du taux de clic)."""
    from .security import client_ip
    rate_limit(f"impr:{client_ip()}", 300, 3600, "Trop de requêtes.")
    ids = (request.get_json(silent=True) or {}).get("ids")
    if not isinstance(ids, list) or not 0 < len(ids) <= 60 or not all(isinstance(i, int) and not isinstance(i, bool) for i in ids):
        abort(400, "Liste invalide.")
    run("""INSERT INTO listing_impressions (listing_id, n)
           SELECT id, 1 FROM listings WHERE id = ANY(%s) AND status='active'
           ON CONFLICT (listing_id, day) DO UPDATE SET n = listing_impressions.n + 1""", (list(set(ids)),))
    return jsonify(ok=True)


def listing_stats(where, args, days):
    """Statistiques par annonce sur une période : affichages, vues, clics, favoris, contacts, visites."""
    return all_(f"""SELECT l.id, l.title, l.status, l.featured, l.cover_url AS cover, l.owner_id, u.name AS agent,
                           l.price::float8 AS price, l.deal, l.commune, l.fav_count AS favorites,
                           COALESCE((SELECT SUM(n) FROM listing_impressions i WHERE i.listing_id=l.id
                                     AND i.day > CURRENT_DATE - %s), 0)::int AS impressions,
                           (SELECT COUNT(*) FROM listing_views v WHERE v.listing_id=l.id AND v.day > CURRENT_DATE - %s)::int AS views,
                           (SELECT COUNT(*) FROM conversations c WHERE c.listing_id=l.id
                              AND c.created_at > now() - make_interval(days => %s))::int AS contacts,
                           (SELECT COUNT(*) FROM visit_slots s WHERE s.listing_id=l.id AND s.status='booked'
                              AND s.booked_at > now() - make_interval(days => %s))::int AS visits
                    FROM listings l JOIN users u ON u.id=l.owner_id
                    WHERE {where} ORDER BY l.created_at DESC LIMIT 500""", (days, days, days, days, *args))


def daily_series(where, args, days):
    return all_(f"""SELECT d::date::text AS day,
                      COALESCE((SELECT SUM(i.n) FROM listing_impressions i JOIN listings l ON l.id=i.listing_id
                                WHERE {where} AND i.day=d::date), 0)::int AS impressions,
                      (SELECT COUNT(*) FROM listing_views v JOIN listings l ON l.id=v.listing_id
                       WHERE {where} AND v.day=d::date)::int AS views,
                      (SELECT COUNT(*) FROM conversations c JOIN listings l ON l.id=c.listing_id
                       WHERE {where} AND c.created_at::date=d::date)::int AS contacts
                    FROM generate_series(CURRENT_DATE - (%s - 1), CURRENT_DATE, interval '1 day') d ORDER BY 1""",
                (*args, *args, *args, days))


def _days():
    try:
        d = int(request.args.get("days", 30))
    except ValueError:
        abort(400, "Période invalide.")
    if d not in (7, 30, 90):
        abort(400, "Période invalide (7, 30 ou 90 jours).")
    return d


def stats_payload(where, args, days):
    items = listing_stats(where, args, days)
    for x in items:
        x["ctr"] = round(x["views"] / x["impressions"] * 100, 1) if x["impressions"] else None
    tot = {k: sum(x[k] for x in items) for k in ("impressions", "views", "contacts", "visits", "favorites")}
    tot["ctr"] = round(tot["views"] / tot["impressions"] * 100, 1) if tot["impressions"] else None
    tot["listings"] = sum(1 for x in items if x["status"] == "active")
    return {"days": days, "totals": tot, "items": items, "daily": daily_series(where, args, days),
            "response": response_stats(where, args)}


@bp.get("/my/stats")
@require("host", "agent")
def my_stats():
    return jsonify(stats_payload("l.owner_id=%s", (current_user()["id"],), _days()))


# ====================================================================== dossier d'agent
@bp.get("/agent/application")
@require()
def my_application():
    u = current_user()
    app_ = one("""SELECT id, status, note, trade_name, license_no, zones, experience,
                         extract(epoch FROM created_at)::float8 AS created_at
                  FROM agent_applications WHERE user_id=%s ORDER BY created_at DESC LIMIT 1""", (u["id"],))
    invites = all_("""SELECT i.id, i.role, a.name AS agency, a.slug, a.logo_url AS logo FROM agency_invites i
                      JOIN agencies a ON a.id=i.agency_id WHERE lower(i.email)=lower(%s) AND i.status='pending'
                      AND a.status='active' ORDER BY i.created_at DESC""", (u["email"],))
    m = membership(u["id"])
    return jsonify(agent_status=u["agent_status"], application=app_, invites=invites,
                   agency={"name": m["name"], "slug": m["slug"], "role": m["member_role"], "status": m["status"]} if m else None)


@bp.post("/agent/application")
@require(avatar=True)
def apply_agent():
    """Demande de statut d'agent indépendant : pièce d'identité, selfie et justificatif(s) professionnel(s)."""
    u = current_user()
    if u["role"] == "admin":
        abort(400, "Un administrateur ne peut pas être agent.")
    if u["agent_status"] == "approved":
        abort(400, "Vous êtes déjà agent vérifié.")
    if membership(u["id"]):
        abort(400, "Vous êtes déjà agent d'une agence.")
    f = request.form
    license_no, zones = (f.get("license_no") or "").strip()[:60], (f.get("zones") or "").strip()[:200]
    trade = (f.get("trade_name") or "").strip()[:80]
    motivation = (f.get("motivation") or "").strip()[:1000]
    try:
        experience = int(f.get("experience") or 0)
    except ValueError:
        abort(400, "Expérience invalide.")
    if not 0 <= experience <= 60:
        abort(400, "Expérience invalide.")
    if len(license_no) < 3 or len(zones) < 3:
        abort(400, "Indiquez votre numéro professionnel (RCCM, patente ou carte) et vos zones d'activité.")
    pro = request.files.getlist("pro_doc")
    if not 1 <= len(pro) <= MAX_PRO_DOCS:
        abort(400, f"Ajoutez de 1 à {MAX_PRO_DOCS} justificatifs professionnels.")
    docs = [("id_doc", _image_upload(request.files.get("id_doc"), "Photo de la pièce d'identité", 400, 300)),
            ("selfie", _image_upload(request.files.get("selfie"), "Selfie", 400, 300))]
    docs += [("pro_doc", _image_upload(x, "Justificatif professionnel", 400, 300)) for x in pro]
    if one("SELECT 1 FROM agent_applications WHERE user_id=%s AND status='pending'", (u["id"],)):
        abort(409, "Un dossier est déjà en cours d'examen.")
    rate_limit(f"agent-app:{u['id']}", 3, 86400, "Trop de dossiers envoyés aujourd'hui.")
    a = one("""INSERT INTO agent_applications (user_id, trade_name, license_no, zones, experience, motivation)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""", (u["id"], trade, license_no, zones, experience, motivation))
    for kind, data in docs:
        run("INSERT INTO agent_documents (application_id, kind, data) VALUES (%s,%s,%s)", (a["id"], kind, data))
    run("UPDATE users SET agent_status='pending' WHERE id=%s", (u["id"],))
    audit("agent_applied", u["id"])
    from .staff import notify_staff
    notify_staff("mod_agent", "Nouveau dossier d'agent immobilier", u["name"], "#/admin?tab=pros", admins_only=True)
    return jsonify(ok=True), 201


@bp.get("/admin/agents")
@require("admin")
def pending_agents():
    rows = all_("""SELECT a.id, a.trade_name, a.license_no, a.zones, a.experience, a.motivation,
                          extract(epoch FROM a.created_at)::float8 AS created_at, u.id AS user_id, u.name, u.email,
                          u.phone, u.avatar_url AS avatar,
                          (SELECT json_agg(json_build_object('id', d.id, 'kind', d.kind) ORDER BY d.id)
                           FROM agent_documents d WHERE d.application_id=a.id AND d.data IS NOT NULL) AS docs
                   FROM agent_applications a JOIN users u ON u.id=a.user_id
                   WHERE a.status='pending' ORDER BY a.created_at LIMIT 100""")
    return jsonify(items=rows)


@bp.get("/admin/agent-docs/<int:did>")
@require("admin")
def agent_doc(did):
    r = one("SELECT data, application_id FROM agent_documents WHERE id=%s AND data IS NOT NULL", (did,))
    if not r:
        abort(404)
    resp = current_app.response_class(bytes(r["data"]), mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "no-store"
    resp.headers["Content-Security-Policy"] = "default-src 'none'"
    audit("agent_doc_viewed", current_user()["id"], document=did, application=r["application_id"])
    return resp


@bp.post("/admin/agents/<int:aid>/decision")
@require("admin")
def decide_agent(aid):
    d = body()
    act, note = d.get("action"), text(d, "note", 300)
    if act not in ("approve", "reject"):
        abort(400, "Action invalide.")
    r = one("""UPDATE agent_applications SET status=%s, note=%s, decided_at=now(), decided_by=%s
               WHERE id=%s AND status='pending' RETURNING user_id""",
            ("approved" if act == "approve" else "rejected", note, current_user()["id"], aid))
    if not r:
        abort(404, "Dossier introuvable.")
    # Pièce d'identité et selfie effacés dès la décision ; les justificatifs professionnels sont conservés.
    run("UPDATE agent_documents SET data=NULL WHERE application_id=%s AND kind IN ('id_doc','selfie')", (aid,))
    if act == "approve":
        run("""UPDATE users SET role=CASE WHEN role='admin' THEN role ELSE 'agent' END, agent_status='approved',
                      verified=TRUE WHERE id=%s""", (r["user_id"],))
    else:
        run("UPDATE users SET agent_status='rejected' WHERE id=%s", (r["user_id"],))
    notify(r["user_id"], "kyc", "Vous êtes agent immobilier vérifié sur Ndaku" if act == "approve"
           else "Dossier d'agent refusé", note or ("Vous pouvez maintenant publier des biens." if act == "approve"
                                                   else "Vous pouvez envoyer un nouveau dossier complet."),
           "#/host" if act == "approve" else "#/profile/agent")
    audit(f"agent_{act}", current_user()["id"], target=r["user_id"], application=aid)
    return jsonify(ok=True)


# ====================================================================== invitations
@bp.post("/agency/invites/<int:iid>/<action>")
@require(avatar=True)
def answer_invite(iid, action):
    u = current_user()
    if action not in ("accept", "decline"):
        abort(404)
    inv = one("""SELECT i.*, a.name, a.status AS agency_status FROM agency_invites i JOIN agencies a ON a.id=i.agency_id
                 WHERE i.id=%s AND i.status='pending' AND lower(i.email)=lower(%s)""", (iid, u["email"]))
    if not inv:
        abort(404, "Invitation introuvable.")
    if action == "decline":
        run("UPDATE agency_invites SET status='declined' WHERE id=%s", (iid,))
        return jsonify(ok=True)
    # L'adresse doit être prouvée : sinon n'importe qui créerait un compte avec l'e-mail invité.
    if not u["email_verified"]:
        abort(403, "Confirmez d'abord votre adresse e-mail (ou connectez-vous avec Google) pour rejoindre une agence.")
    if u["role"] == "admin":
        abort(400, "Un administrateur ne peut pas rejoindre une agence.")
    if inv["agency_status"] != "active":
        abort(403, "Cette agence est suspendue.")
    if membership(u["id"]):
        abort(409, "Vous faites déjà partie d'une agence.")
    run("INSERT INTO agency_members (agency_id, user_id, role) VALUES (%s,%s,%s)", (inv["agency_id"], u["id"], inv["role"]))
    run("UPDATE agency_invites SET status='accepted' WHERE id=%s", (iid,))
    run("UPDATE users SET role='agent' WHERE id=%s", (u["id"],))
    audit("agency_joined", u["id"], agency=inv["agency_id"], role=inv["role"])
    for mgr in all_("SELECT user_id FROM agency_members WHERE agency_id=%s AND role='manager' AND user_id<>%s",
                    (inv["agency_id"], u["id"])):
        notify(mgr["user_id"], "account", f"{u['name']} a rejoint l'agence", inv["name"], "#/agence-pro/agents", external=False)
    return jsonify(ok=True)


# ====================================================================== catalogues publics
def _agency_public(a):
    return {"slug": a["slug"], "name": a["name"], "logo": a["logo_url"], "city": a["city"], "verified": True}


@bp.get("/agencies")
def agencies():
    q = (request.args.get("q") or "")[:60].strip()
    args, where = [], ""
    if q:
        where = "AND (a.name ILIKE %s OR a.city ILIKE %s)"
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        args = [like, like]
    rows = all_(f"""SELECT a.slug, a.name, a.logo_url AS logo, a.city, a.description, a.is_demo,
                           (SELECT COUNT(*) FROM agency_members m JOIN users u ON u.id=m.user_id
                            WHERE m.agency_id=a.id AND u.suspended_at IS NULL)::int AS agents,
                           (SELECT COUNT(*) FROM listings l WHERE l.agency_id=a.id AND l.status='active')::int AS listings,
                           (SELECT l.cover_url FROM listings l WHERE l.agency_id=a.id AND l.status='active'
                            ORDER BY l.featured DESC, l.created_at DESC LIMIT 1) AS cover
                    FROM agencies a WHERE a.status='active' {where} ORDER BY listings DESC, a.name LIMIT 200""", args)
    independents = all_("""SELECT u.id, u.name, u.avatar_url AS avatar, u.bio,
                                  (SELECT COUNT(*) FROM listings l WHERE l.owner_id=u.id AND l.status='active')::int AS listings
                           FROM users u WHERE u.role='agent' AND u.agent_status='approved' AND u.suspended_at IS NULL
                             AND NOT EXISTS (SELECT 1 FROM agency_members m WHERE m.user_id=u.id)
                           ORDER BY listings DESC, u.name LIMIT 100""")
    g.cache_seconds = 60
    return jsonify(items=rows, agents=independents)


@bp.get("/agencies/<slug>")
def agency_page(slug):
    from .listings import BASE_SQL, VISIBLE, card
    a = one("SELECT * FROM agencies WHERE slug=%s AND status='active'", (slug[:80],))
    if not a:
        abort(404, "Agence introuvable.")
    team = all_("""SELECT u.id, u.name, u.avatar_url AS avatar, m.role, m.title,
                          (SELECT COUNT(*) FROM listings l WHERE l.owner_id=u.id AND l.agency_id=%s AND l.status='active')::int AS listings
                   FROM agency_members m JOIN users u ON u.id=m.user_id
                   WHERE m.agency_id=%s AND u.suspended_at IS NULL ORDER BY m.role DESC, u.name""", (a["id"], a["id"]))
    rows = all_(f"{BASE_SQL} WHERE l.agency_id=%s AND {VISIBLE} ORDER BY l.featured DESC, l.created_at DESC LIMIT 120",
                (a["id"],))
    rating = one("""SELECT SUM(host_rating_sum)::int AS s, SUM(host_rating_count)::int AS n FROM users u
                    JOIN agency_members m ON m.user_id=u.id WHERE m.agency_id=%s""", (a["id"],))
    g.cache_seconds = 60
    return jsonify(slug=a["slug"], name=a["name"], description=a["description"], logo=a["logo_url"], phone=a["phone"],
                   email=a["email"], website=a["website"], address=a["address"], city=a["city"], rccm=a["rccm"],
                   id_nat=a["id_nat"], since=a["created_at"].timestamp(), is_demo=a["is_demo"], team=team,
                   listings=[card(r) for r in rows],
                   rating=round(rating["s"] / rating["n"], 2) if rating["n"] else None, reviews_count=rating["n"] or 0,
                   response=response_stats("l.agency_id=%s", (a["id"],)))


# ====================================================================== espace agence
@bp.get("/agency")
@require("agent")
def agency_home():
    m = _my_agency()
    out = {"id": m["id"], "slug": m["slug"], "name": m["name"], "description": m["description"], "logo": m["logo_url"],
           "phone": m["phone"], "email": m["email"], "website": m["website"], "address": m["address"],
           "city": m["city"], "rccm": m["rccm"], "id_nat": m["id_nat"], "featured_quota": m["featured_quota"],
           "my_role": m["member_role"]}
    out["members"] = all_("""SELECT u.id, u.name, u.email, u.avatar_url AS avatar, m.role, m.title,
                                    extract(epoch FROM m.joined_at)::float8 AS joined_at, u.suspended_at IS NOT NULL AS suspended,
                                    (SELECT COUNT(*) FROM listings l WHERE l.owner_id=u.id AND l.agency_id=m.agency_id
                                       AND l.status='active')::int AS listings
                             FROM agency_members m JOIN users u ON u.id=m.user_id WHERE m.agency_id=%s
                             ORDER BY m.role DESC, u.name""", (m["id"],))
    if m["member_role"] == "manager":
        out["invites"] = all_("""SELECT id, email, role, extract(epoch FROM created_at)::float8 AS created_at
                                 FROM agency_invites WHERE agency_id=%s AND status='pending' ORDER BY created_at DESC""", (m["id"],))
    out["featured_count"] = one("SELECT COUNT(*)::int AS n FROM listings WHERE agency_id=%s AND featured AND status='active'",
                                (m["id"],))["n"]
    return jsonify(out)


AGENCY_FIELDS = {"description": 2000, "phone": 30, "email": 120, "website": 200, "address": 200, "city": 60}


@bp.patch("/agency")
@require("agent")
def agency_update():
    m, d = _my_agency(manager=True), body()
    vals = {k: text(d, k, n) for k, n in AGENCY_FIELDS.items() if k in d}
    if vals.get("website") and not re.match(r"^https://[\w.-]+\.[a-z]{2,}(/\S*)?$", vals["website"], re.I):
        abort(400, "Site web invalide (doit commencer par https://).")
    if vals.get("email") and not re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", vals["email"], re.I):
        abort(400, "E-mail invalide.")
    if vals:
        run(f"UPDATE agencies SET {', '.join(f'{k}=%s' for k in vals)} WHERE id=%s", (*vals.values(), m["id"]))
        audit("agency_updated", current_user()["id"], agency=m["id"], fields=list(vals))
    return jsonify(ok=True)


@bp.post("/agency/logo")
@require("agent")
def agency_logo():
    from PIL import Image, ImageOps

    from .storage import StorageUnavailable
    m = _my_agency(manager=True)
    rate_limit(f"logo:{m['id']}", 10, 3600)
    f = request.files.get("image")
    if not f:
        abort(400, "Fichier « image » manquant.")
    try:
        img = af.load_image(f.read(), min_w=200, min_h=200)
    except af.ImageRejected as e:
        abort(422, str(e))
    img = ImageOps.pad(img, (LOGO_SIZE, LOGO_SIZE), Image.LANCZOS, color=(255, 255, 255))
    st = current_app.config["STORAGE"]
    try:
        url, key = st.put(af.to_jpeg(img), folder="avatars")
    except StorageUnavailable:
        abort(503, "Stockage des photos non configuré.")
    run("UPDATE agencies SET logo_url=%s, logo_key=%s WHERE id=%s", (url, key, m["id"]))
    if m["logo_key"]:
        st.delete([m["logo_key"]])
    return jsonify(logo=url)


@bp.post("/agency/invites")
@require("agent")
def agency_invite():
    m, d = _my_agency(manager=True), body()
    email = text(d, "email", 120).lower()
    role = d.get("role", "agent")
    if role not in ("agent", "manager") or not re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", email, re.I):
        abort(400, "E-mail ou rôle invalide.")
    rate_limit(f"invite:{m['id']}", 30, 86400, "Trop d'invitations aujourd'hui.")
    if one("""SELECT 1 FROM agency_members am JOIN users u ON u.id=am.user_id
              WHERE am.agency_id=%s AND lower(u.email)=%s""", (m["id"], email)):
        abort(409, "Cette personne fait déjà partie de l'agence.")
    if not one("""INSERT INTO agency_invites (agency_id, email, role, invited_by) VALUES (%s,%s,%s,%s)
                  ON CONFLICT DO NOTHING RETURNING id""", (m["id"], email, role, current_user()["id"])):
        abort(409, "Une invitation est déjà en attente pour cette adresse.")
    target = one("SELECT id FROM users WHERE lower(email)=%s AND suspended_at IS NULL", (email,))
    if target:
        notify(target["id"], "account", f"Invitation à rejoindre l'agence {m['name']}",
               "Acceptez-la depuis vos paramètres pour publier au nom de l'agence.", "#/profile/agent")
    audit("agency_invited", current_user()["id"], agency=m["id"], role=role)
    return jsonify(ok=True, existing_account=bool(target)), 201


@bp.delete("/agency/invites/<int:iid>")
@require("agent")
def agency_revoke(iid):
    m = _my_agency(manager=True)
    if not one("UPDATE agency_invites SET status='revoked' WHERE id=%s AND agency_id=%s AND status='pending' RETURNING id",
               (iid, m["id"])):
        abort(404, "Invitation introuvable.")
    return jsonify(ok=True)


def transfer_listings(agency_id, from_uid, to_uid):
    """Les annonces (et discussions en cours) d'un agent qui part restent à l'agence."""
    run("""UPDATE conversations SET host_id=%s WHERE host_id=%s
           AND listing_id IN (SELECT id FROM listings WHERE agency_id=%s AND owner_id=%s)""", (to_uid, from_uid, agency_id, from_uid))
    run("UPDATE listings SET owner_id=%s WHERE agency_id=%s AND owner_id=%s", (to_uid, agency_id, from_uid))


@bp.patch("/agency/members/<int:uid>")
@require("agent")
def agency_member_update(uid):
    m, d = _my_agency(manager=True), body()
    role = d.get("role")
    if role is not None and role not in ("agent", "manager"):
        abort(400, "Rôle invalide.")
    if uid == current_user()["id"] and role == "agent" and one(
            "SELECT COUNT(*)::int AS n FROM agency_members WHERE agency_id=%s AND role='manager'", (m["id"],))["n"] < 2:
        abort(400, "L'agence doit garder au moins un gérant.")
    if not one("""UPDATE agency_members SET role=COALESCE(%s, role), title=COALESCE(%s, title)
                  WHERE agency_id=%s AND user_id=%s RETURNING user_id""",
               (role, text(d, "title", 60) if "title" in d else None, m["id"], uid)):
        abort(404, "Membre introuvable.")
    audit("agency_member_updated", current_user()["id"], agency=m["id"], target=uid, role=role)
    return jsonify(ok=True)


@bp.delete("/agency/members/<int:uid>")
@require("agent")
def agency_member_remove(uid):
    m, me = _my_agency(manager=True), current_user()
    if uid == me["id"]:
        abort(400, "Un gérant ne peut pas se retirer lui-même : nommez un autre gérant, ou contactez Ndaku.")
    if not one("DELETE FROM agency_members WHERE agency_id=%s AND user_id=%s RETURNING user_id", (m["id"], uid)):
        abort(404, "Membre introuvable.")
    transfer_listings(m["id"], uid, me["id"])
    audit("agency_member_removed", me["id"], agency=m["id"], target=uid)
    notify(uid, "account", f"Vous ne faites plus partie de l'agence {m['name']}", "", "#/profile", external=False)
    return jsonify(ok=True)


@bp.get("/agency/listings")
@require("agent")
def agency_listings():
    m = _my_agency()
    days = _days()
    where, args = "l.agency_id=%s", [m["id"]]
    if m["member_role"] != "manager":  # un agent ne voit que ses biens
        where += " AND l.owner_id=%s"
        args.append(current_user()["id"])
    return jsonify(stats_payload(where, args, days))


@bp.get("/agency/stats")
@require("agent")
def agency_stats():
    m = _my_agency(manager=True)
    days = _days()
    out = stats_payload("l.agency_id=%s", (m["id"],), days)
    agents = {}
    for x in out["items"]:
        a = agents.setdefault(x["owner_id"], {"id": x["owner_id"], "name": x["agent"], "listings": 0,
                                              "impressions": 0, "views": 0, "contacts": 0, "visits": 0})
        a["listings"] += x["status"] == "active"
        for k in ("impressions", "views", "contacts", "visits"):
            a[k] += x[k]
    for a in agents.values():
        a["response"] = response_stats("l.agency_id=%s AND c.host_id=%s", (m["id"], a["id"]))
    out["agents"] = sorted(agents.values(), key=lambda a: -a["contacts"])
    out["items"] = sorted(out["items"], key=lambda x: -x["views"])
    return jsonify(out)


@bp.post("/agency/listings/<int:lid>/assign")
@require("agent")
def agency_assign(lid):
    m = _my_agency(manager=True)
    to = body().get("user_id")
    if not isinstance(to, int) or not one("SELECT 1 FROM agency_members WHERE agency_id=%s AND user_id=%s", (m["id"], to)):
        abort(400, "Choisissez un agent de l'agence.")
    l = one("SELECT owner_id FROM listings WHERE id=%s AND agency_id=%s", (lid, m["id"]))
    if not l:
        abort(404, "Annonce introuvable.")
    run("UPDATE conversations SET host_id=%s WHERE listing_id=%s", (to, lid))
    run("UPDATE listings SET owner_id=%s WHERE id=%s", (to, lid))
    audit("agency_listing_assigned", current_user()["id"], listing_id=lid, target=to)
    notify(to, "listing", "Une annonce vous a été attribuée", "", f"#/listing/{lid}", external=False)
    return jsonify(ok=True)


@bp.post("/listings/<int:lid>/feature")
@require("agent")
def feature(lid):
    """Mise en avant : par le gérant pour l'agence, ou par un agent indépendant pour ses biens."""
    u, on = current_user(), body().get("featured") is True
    l = one("SELECT id, owner_id, agency_id, status FROM listings WHERE id=%s", (lid,))
    if not l:
        abort(404, "Annonce introuvable.")
    m = membership(u["id"])
    if l["agency_id"]:
        if not m or m["id"] != l["agency_id"] or m["member_role"] != "manager" or m["status"] != "active":
            abort(404, "Annonce introuvable.")
        quota, scope, sargs = m["featured_quota"], "agency_id=%s", (l["agency_id"],)
    else:
        if l["owner_id"] != u["id"] or u["agent_status"] != "approved":
            abort(404, "Annonce introuvable.")
        quota, scope, sargs = AGENT_FEATURED_QUOTA, "owner_id=%s AND agency_id IS NULL", (u["id"],)
    if on:
        if l["status"] != "active":
            abort(400, "Seule une annonce en ligne peut être mise en avant.")
        n = one(f"SELECT COUNT(*)::int AS n FROM listings WHERE {scope} AND featured AND status='active' AND id<>%s",
                (*sargs, lid))["n"]
        if n >= quota:
            abort(400, f"Limite de {quota} biens mis en avant atteinte : retirez-en un d'abord.")
    run("UPDATE listings SET featured=%s WHERE id=%s", (on, lid))
    return jsonify(ok=True, featured=on)


@bp.get("/agency/conversations")
@require("agent")
def agency_conversations():
    """Supervision par le gérant : discussions des biens de l'agence (lecture seule)."""
    m = _my_agency(manager=True)
    rows = all_("""SELECT c.id, l.id AS listing_id, l.title, ag.name AS agent, cl.name AS client,
                          extract(epoch FROM c.last_message_at)::float8 AS last_at,
                          (SELECT m.sender_id = c.host_id FROM messages m WHERE m.conversation_id=c.id ORDER BY m.id DESC LIMIT 1)
                            AS answered
                   FROM conversations c JOIN listings l ON l.id=c.listing_id JOIN users ag ON ag.id=c.host_id
                   JOIN users cl ON cl.id=c.client_id
                   WHERE l.agency_id=%s ORDER BY c.last_message_at DESC LIMIT 200""", (m["id"],))
    return jsonify(items=rows)


@bp.get("/agency/conversations/<int:cid>")
@require("agent")
def agency_conversation(cid):
    m = _my_agency(manager=True)
    c = one("""SELECT c.id, l.title, l.id AS listing_id, ag.name AS agent, cl.name AS client FROM conversations c
               JOIN listings l ON l.id=c.listing_id JOIN users ag ON ag.id=c.host_id JOIN users cl ON cl.id=c.client_id
               WHERE c.id=%s AND l.agency_id=%s""", (cid, m["id"]))
    if not c:
        abort(404, "Discussion introuvable.")
    c["messages"] = all_("""SELECT m.kind, m.body, m.sender_id = (SELECT host_id FROM conversations WHERE id=%s) AS from_agent,
                                   extract(epoch FROM m.created_at)::float8 AS created_at
                            FROM messages m WHERE m.conversation_id=%s ORDER BY m.id LIMIT 300""", (cid, cid))
    audit("agency_conversation_viewed", current_user()["id"], conversation=cid)
    return jsonify(c)


# ====================================================================== administration des agences
@bp.get("/admin/agencies")
@require("admin")
def admin_agencies():
    return jsonify(items=all_("""SELECT a.id, a.slug, a.name, a.logo_url AS logo, a.city, a.status, a.rccm, a.is_demo,
                                        extract(epoch FROM a.created_at)::float8 AS created_at,
                                        (SELECT COUNT(*) FROM agency_members m WHERE m.agency_id=a.id)::int AS members,
                                        (SELECT COUNT(*) FROM listings l WHERE l.agency_id=a.id AND l.status='active')::int AS listings
                                 FROM agencies a ORDER BY a.created_at DESC LIMIT 500"""))


ADMIN_AGENCY_FIELDS = {"name": 120, "description": 2000, "phone": 30, "email": 120, "website": 200, "address": 200,
                       "city": 60, "rccm": 60, "id_nat": 60, "nif": 60, "docs_note": 500}


@bp.post("/admin/agencies")
@require("admin")
def admin_create_agency():
    """Création d'une agence après étude de ses documents ; le gérant est un compte Ndaku existant."""
    d = body()
    vals = {k: text(d, k, n) for k, n in ADMIN_AGENCY_FIELDS.items()}
    if len(vals["name"]) < 3 or len(vals["rccm"]) < 3 or len(vals["docs_note"]) < 10:
        abort(400, "Nom, RCCM et note de vérification des documents (10 caractères min.) sont obligatoires.")
    if vals["website"] and not re.match(r"^https://[\w.-]+\.[a-z]{2,}(/\S*)?$", vals["website"], re.I):
        abort(400, "Site web invalide (doit commencer par https://).")
    mgr = one("SELECT * FROM users WHERE lower(email)=lower(%s)", (text(d, "manager_email", 120),))
    if not mgr or mgr["suspended_at"] or mgr["role"] == "admin":
        abort(400, "Le gérant doit avoir un compte Ndaku actif (non administrateur) avec cet e-mail.")
    if membership(mgr["id"]):
        abort(409, "Ce compte fait déjà partie d'une agence.")
    a = one(f"""INSERT INTO agencies (slug, {', '.join(vals)}, created_by) VALUES (%s, {', '.join(['%s'] * len(vals))}, %s)
                RETURNING id, slug""", (slugify(vals["name"]), *vals.values(), current_user()["id"]))
    run("INSERT INTO agency_members (agency_id, user_id, role) VALUES (%s,%s,'manager')", (a["id"], mgr["id"]))
    run("UPDATE users SET role='agent', verified=TRUE WHERE id=%s", (mgr["id"],))
    audit("agency_created", current_user()["id"], agency=a["id"], manager=mgr["id"])
    notify(mgr["id"], "account", f"Votre agence {vals['name']} est ouverte sur Ndaku",
           "Gérez-la depuis l'espace agence sur le site web.", "#/agence-pro")
    return jsonify(id=a["id"], slug=a["slug"]), 201


@bp.get("/admin/agencies/<int:aid>")
@require("admin")
def admin_agency(aid):
    a = one("SELECT * FROM agencies WHERE id=%s", (aid,))
    if not a:
        abort(404, "Agence introuvable.")
    a["created_at"] = a["created_at"].timestamp()
    a["members"] = all_("""SELECT u.id, u.name, u.email, m.role FROM agency_members m JOIN users u ON u.id=m.user_id
                           WHERE m.agency_id=%s ORDER BY m.role DESC, u.name""", (aid,))
    return jsonify(a)


@bp.patch("/admin/agencies/<int:aid>")
@require("admin")
def admin_update_agency(aid):
    d = body()
    vals = {k: text(d, k, n) for k, n in ADMIN_AGENCY_FIELDS.items() if k in d}
    if "status" in d:
        if d["status"] not in ("active", "suspended"):
            abort(400, "Statut invalide.")
        vals["status"] = d["status"]
    if "featured_quota" in d:
        q = d["featured_quota"]
        if not isinstance(q, int) or isinstance(q, bool) or not 0 <= q <= 100:
            abort(400, "Quota invalide.")
        vals["featured_quota"] = q
    if not vals:
        abort(400, "Rien à modifier.")
    if not one(f"UPDATE agencies SET {', '.join(f'{k}=%s' for k in vals)} WHERE id=%s RETURNING id", (*vals.values(), aid)):
        abort(404, "Agence introuvable.")
    audit("agency_admin_updated", current_user()["id"], agency=aid, fields=list(vals))
    return jsonify(ok=True)


@bp.post("/admin/agencies/<int:aid>/members")
@require("admin")
def admin_add_member(aid):
    d = body()
    role = d.get("role", "manager")
    if role not in ("manager", "agent"):
        abort(400, "Rôle invalide.")
    if not one("SELECT 1 FROM agencies WHERE id=%s", (aid,)):
        abort(404, "Agence introuvable.")
    u = one("SELECT * FROM users WHERE lower(email)=lower(%s)", (text(d, "email", 120),))
    if not u or u["suspended_at"] or u["role"] == "admin":
        abort(400, "Compte introuvable, suspendu ou administrateur.")
    if membership(u["id"]):
        abort(409, "Ce compte fait déjà partie d'une agence.")
    run("INSERT INTO agency_members (agency_id, user_id, role) VALUES (%s,%s,%s)", (aid, u["id"], role))
    run("UPDATE users SET role='agent' WHERE id=%s", (u["id"],))
    audit("agency_member_added", current_user()["id"], agency=aid, target=u["id"], role=role)
    return jsonify(ok=True), 201
