"""Administration (web) : tableau de bord, gestion des comptes, modérateurs, journal, alertes à l'équipe."""
from flask import Blueprint, abort, jsonify, request

from .auth import body
from .db import all_, one, run
from .notify import flush_pending, notify
from .security import audit, current_user, require

bp = Blueprint("staff", __name__, url_prefix="/api/admin")
PAGE = 50


def notify_staff(kind, title, body_text="", link="#/admin", admins_only=False):
    """Prévient l'équipe (administrateurs, et modérateurs sauf admins_only).
    Au plus une alerte non lue du même type par personne et par 30 minutes : pas de rafale d'e-mails."""
    staff = all_(f"""SELECT u.id FROM users u WHERE u.suspended_at IS NULL
                       AND (u.role='admin' {'' if admins_only else 'OR u.moderator'})
                       AND NOT EXISTS (SELECT 1 FROM notifications n WHERE n.user_id=u.id AND n.kind=%s
                                       AND n.read_at IS NULL AND n.created_at > now() - interval '30 minutes')""",
                 (kind,))
    for s in staff:
        notify(s["id"], kind, title, body_text, link, defer=True)
    if staff:
        flush_pending(limit=5, budget=1.5)


# ------------------------------------------------------------------------ tableau de bord
@bp.get("/stats")
@require("admin", "moderator")
def stats():
    c = one("""SELECT
        (SELECT COUNT(*) FROM users)::int AS users,
        (SELECT COUNT(*) FROM users WHERE created_at > now() - interval '7 days')::int AS users_7d,
        (SELECT COUNT(*) FROM users WHERE role='host')::int AS hosts,
        (SELECT COUNT(*) FROM users WHERE verified)::int AS verified_hosts,
        (SELECT COUNT(*) FROM users WHERE suspended_at IS NOT NULL)::int AS suspended,
        (SELECT COUNT(*) FROM listings WHERE status='active' AND NOT is_demo)::int AS active,
        (SELECT COUNT(*) FROM listings WHERE status='active' AND is_demo)::int AS demo,
        (SELECT COUNT(*) FROM listings WHERE status='pending')::int AS pending,
        (SELECT COUNT(*) FROM listings WHERE created_at > now() - interval '7 days')::int AS listings_7d,
        (SELECT COUNT(DISTINCT listing_id) FROM reports WHERE status='open')::int AS reports,
        (SELECT COUNT(*) FROM user_reports WHERE status='open')::int AS user_reports,
        (SELECT COUNT(*) FROM id_verifications WHERE status='pending')::int AS kyc,
        (SELECT COUNT(*) FROM places WHERE status='pending')::int AS places,
        (SELECT COUNT(*) FROM conversations WHERE created_at > now() - interval '7 days')::int AS conversations_7d,
        (SELECT COUNT(*) FROM messages WHERE created_at > now() - interval '7 days')::int AS messages_7d,
        (SELECT COUNT(*) FROM visit_slots WHERE status='booked' AND booked_at > now() - interval '7 days')::int AS visits_7d""")
    series = lambda table: all_(f"""SELECT d::date::text AS day, COUNT(t.id)::int AS n
        FROM generate_series(CURRENT_DATE - 29, CURRENT_DATE, interval '1 day') d
        LEFT JOIN {table} t ON t.created_at::date = d::date GROUP BY 1 ORDER BY 1""")
    return jsonify(counts=c, signups=series("users"), listings=series("listings"))


# ------------------------------------------------------------------------ comptes
FILTERS = {"all": "TRUE", "host": "u.role='host'", "client": "u.role='client'", "admin": "u.role='admin'",
           "moderator": "u.moderator", "verified": "u.verified", "suspended": "u.suspended_at IS NOT NULL",
           "reported": "EXISTS (SELECT 1 FROM user_reports r WHERE r.target_id=u.id AND r.status='open')"}


@bp.get("/users")
@require("admin")
def users():
    a = request.args
    where = FILTERS.get(a.get("filter", "all"), "TRUE")
    q = (a.get("q") or "")[:80].strip()
    try:
        offset = max(0, min(int(a.get("offset", 0)), 100_000))
    except ValueError:
        abort(400, "Paramètre invalide.")
    args = []
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where += " AND (u.name ILIKE %s OR u.email ILIKE %s OR u.phone ILIKE %s OR u.id::text = %s)"
        args += [like, like, like, q]
    rows = all_(f"""SELECT u.id, u.name, u.email, u.role, u.verified, u.moderator, u.avatar_url AS avatar,
                           u.suspended_at IS NOT NULL AS suspended, extract(epoch FROM u.created_at)::float8 AS created_at,
                           (SELECT COUNT(*) FROM listings l WHERE l.owner_id=u.id)::int AS listings,
                           (SELECT COUNT(*) FROM user_reports r WHERE r.target_id=u.id AND r.status='open')::int AS reports
                    FROM users u WHERE {where} ORDER BY u.created_at DESC LIMIT %s OFFSET %s""",
                args + [PAGE + 1, offset])
    return jsonify(items=rows[:PAGE], more=len(rows) > PAGE)


@bp.get("/users/<int:uid>")
@require("admin")
def user_detail(uid):
    u = one("""SELECT id, name, email, phone, role, verified, moderator, email_verified, avatar_url AS avatar,
                      suspended_at IS NOT NULL AS suspended, extract(epoch FROM created_at)::float8 AS created_at,
                      host_rating_sum, host_rating_count FROM users WHERE id=%s""", (uid,))
    if not u:
        abort(404, "Utilisateur introuvable.")
    u["providers"] = [r["provider"] for r in all_("SELECT provider FROM identities WHERE user_id=%s", (uid,))]
    u["listings"] = all_("""SELECT id, title, status, price::float8 AS price, deal, commune, risk_score,
                                   extract(epoch FROM created_at)::float8 AS created_at
                            FROM listings WHERE owner_id=%s ORDER BY created_at DESC LIMIT 50""", (uid,))
    u["reports"] = all_("""SELECT r.category, r.reason, r.status, rp.name AS reporter,
                                  extract(epoch FROM r.created_at)::float8 AS at
                           FROM user_reports r JOIN users rp ON rp.id=r.reporter_id WHERE r.target_id=%s
                           ORDER BY r.created_at DESC LIMIT 30""", (uid,))
    u["kyc"] = all_("""SELECT status, id_type, note, extract(epoch FROM created_at)::float8 AS at FROM id_verifications
                       WHERE user_id=%s ORDER BY created_at DESC LIMIT 10""", (uid,))
    u["events"] = all_("""SELECT event, detail, ip, extract(epoch FROM created_at)::float8 AS at FROM security_events
                          WHERE user_id=%s OR detail->>'target' = %s ORDER BY id DESC LIMIT 50""", (uid, str(uid)))
    u["stats"] = one("""SELECT (SELECT COUNT(*) FROM conversations WHERE client_id=%(u)s OR host_id=%(u)s)::int AS conversations,
                               (SELECT COUNT(*) FROM messages WHERE sender_id=%(u)s)::int AS messages,
                               (SELECT COUNT(*) FROM reviews WHERE user_id=%(u)s)::int AS reviews_given""", {"u": uid})
    return jsonify(u)


@bp.post("/users/<int:uid>/moderator")
@require("admin")
def set_moderator(uid):
    on = body().get("moderator")
    if not isinstance(on, bool):
        abort(400, "Valeur invalide.")
    if not one("UPDATE users SET moderator=%s WHERE id=%s AND role<>'admin' AND suspended_at IS NULL RETURNING id",
               (on, uid)):
        abort(404, "Utilisateur introuvable, administrateur ou suspendu.")
    audit("moderator_granted" if on else "moderator_revoked", current_user()["id"], target=uid)
    notify(uid, "account", "Vous êtes modérateur sur Ndaku" if on else "Votre rôle de modérateur a été retiré",
           "La modération est accessible depuis le site web, menu « Modération »." if on else "", "#/admin" if on else "#/profile")
    return jsonify(ok=True)


# ------------------------------------------------------------------------ journal
@bp.get("/logs")
@require("admin")
def logs():
    a = request.args
    where, args = ["TRUE"], []
    if a.get("event"):
        where.append("e.event LIKE %s")
        args.append(a["event"][:40].replace("%", "").replace("_", "\\_") + "%")
    if a.get("user_id"):
        try:
            uid = int(a["user_id"])
        except ValueError:
            abort(400, "Paramètre invalide.")
        where.append("(e.user_id=%s OR e.detail->>'target' = %s)")
        args += [uid, str(uid)]
    if a.get("before"):
        try:
            where.append("e.id < %s")
            args.append(int(a["before"]))
        except ValueError:
            abort(400, "Paramètre invalide.")
    rows = all_(f"""SELECT e.id, e.event, e.detail, e.ip, extract(epoch FROM e.created_at)::float8 AS at,
                           e.user_id, u.name AS user_name
                    FROM security_events e LEFT JOIN users u ON u.id=e.user_id
                    WHERE {' AND '.join(where)} ORDER BY e.id DESC LIMIT %s""", args + [PAGE + 1])
    return jsonify(items=rows[:PAGE], more=len(rows) > PAGE)
