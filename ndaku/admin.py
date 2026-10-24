"""Modération et tâches planifiées."""
import hmac

from flask import Blueprint, abort, current_app, jsonify, request

from .auth import body
from .db import all_, one, run
from .listings import BASE_SQL, REPORT_CATEGORIES, card
from .notify import flush_pending, notify
from .services import match_alerts
from .security import revoke_all
from .security import audit, cfg, current_user, require

bp = Blueprint("admin", __name__, url_prefix="/api")


@bp.get("/admin/queue")
@require("admin", "moderator")
def queue():
    rows = all_(f"{BASE_SQL} WHERE l.status='pending' ORDER BY l.risk_score DESC LIMIT 100")
    reports = {}
    for r in all_("SELECT listing_id, category, reason FROM reports WHERE listing_id = ANY(%s) AND status='open'",
                  ([r["id"] for r in rows],)):
        reports.setdefault(r["listing_id"], []).append(f"{REPORT_CATEGORIES.get(r['category'], r['category'])} — {r['reason']}")
    return jsonify(items=[{**card(r), "risk_score": r["risk_score"], "risk_reasons": r["risk_reasons"],
                           "host": r["host_name"], "host_id": r["owner_id"], "reports": reports.get(r["id"], [])}
                          for r in rows])


@bp.post("/admin/listings/<int:lid>/decision")
@require("admin", "moderator")
def decide(lid):
    act = body().get("action")
    if act not in ("approve", "reject"):
        abort(400, "Action invalide.")
    r = one("UPDATE listings SET status=%s WHERE id=%s AND status='pending' RETURNING owner_id, title, is_demo",
            ("active" if act == "approve" else "rejected", lid))
    if not r:
        abort(404, "Annonce non en attente.")
    run("UPDATE reports SET status=%s WHERE listing_id=%s AND status='open'",
        ("dismissed" if act == "approve" else "actioned", lid))
    audit(f"moderation_{act}", current_user()["id"], listing_id=lid)
    if not r["is_demo"]:
        notify(r["owner_id"], "listing", ("Annonce publiée : " if act == "approve" else "Annonce refusée : ") + r["title"],
               "" if act == "approve" else "Elle ne respecte pas nos règles. Contactez le support pour en savoir plus.",
               f"#/listing/{lid}" if act == "approve" else "#/host")
    if act == "approve":
        match_alerts(lid)
    return jsonify(ok=True)


@bp.post("/admin/users/<int:uid>/verify")
@require("admin")
def verify_user(uid):
    """Accorde ou retire le badge « hôte vérifié »."""
    on = (request.get_json(silent=True) or {}).get("verified") is not False
    if not one("UPDATE users SET verified=%s WHERE id=%s RETURNING id", (on, uid)):
        abort(404, "Utilisateur introuvable.")
    audit("host_verified" if on else "host_unverified", current_user()["id"], target=uid)
    return jsonify(ok=True)


@bp.get("/cron/cleanup")
def cleanup():
    """Appelé chaque jour par Vercel Cron (en-tête Authorization: Bearer $CRON_SECRET)."""
    secret = cfg().CRON_SECRET
    if not secret or not hmac.compare_digest(request.headers.get("Authorization", ""), f"Bearer {secret}"):
        abort(401, "Non autorisé.")
    stale = all_("DELETE FROM images WHERE listing_id IS NULL AND created_at < now() - interval '1 day' "
                 "RETURNING storage_key")
    current_app.config["STORAGE"].delete([r["storage_key"] for r in stale])
    run("DELETE FROM sessions WHERE expires_at < now()")
    run("DELETE FROM rate_limits WHERE window_start < now() - interval '2 days'")
    run("DELETE FROM email_tokens WHERE expires_at < now() - interval '7 days'")
    run("DELETE FROM oauth_nonces WHERE expires_at < now()")
    run("DELETE FROM listing_views WHERE day < CURRENT_DATE - 90")
    run("DELETE FROM notifications WHERE created_at < now() - interval '90 days'")
    # Pièces d'identité jamais examinées : effacées après 30 jours (minimisation)
    run("UPDATE id_verifications SET status='rejected', note='Expirée', id_doc=NULL, selfie=NULL, decided_at=now() "
        "WHERE status='pending' AND created_at < now() - interval '30 days'")
    sent = flush_pending(limit=200, budget=20.0)
    return jsonify(ok=True, images_removed=len(stale), notifications_sent=sent)


@bp.post("/admin/demo")
@require("admin")
def demo_import():
    """Crée les annonces de démonstration par petits lots (limite de durée des fonctions Vercel).
    source=commons : vraies photos de RDC sous licence libre, annonces en attente de validation."""
    from .demo import create_demo
    source = body().get("source", "commons")
    if source not in ("commons", "illustrations"):
        abort(400, "Source invalide.")
    res = create_demo(current_app.config["STORAGE"], source=source, max_listings=3)
    audit("demo_import", current_user()["id"], source=source, created=len(res["created"]))
    return jsonify(res)


@bp.get("/admin/reports")
@require("admin", "moderator")
def listing_reports():
    """Signalements ouverts sur des annonces (y compris encore en ligne), regroupés par annonce."""
    rows = all_("""SELECT r.listing_id, l.title, l.status, l.owner_id, u.name AS host, COUNT(*)::int AS n,
                          json_agg(json_build_object('category', r.category, 'reason', r.reason,
                                   'at', extract(epoch FROM r.created_at)) ORDER BY r.created_at) AS items
                   FROM reports r JOIN listings l ON l.id=r.listing_id JOIN users u ON u.id=l.owner_id
                   WHERE r.status='open' GROUP BY 1,2,3,4,5 ORDER BY n DESC, MAX(r.created_at) DESC LIMIT 200""")
    return jsonify(items=rows, categories=REPORT_CATEGORIES)


@bp.post("/admin/reports/<int:lid>/close")
@require("admin", "moderator")
def close_reports(lid):
    act = body().get("action")
    if act not in ("dismiss", "hide"):
        abort(400, "Action invalide.")
    run("UPDATE reports SET status=%s WHERE listing_id=%s AND status='open'",
        ("dismissed" if act == "dismiss" else "actioned", lid))
    if act == "hide":
        run("UPDATE listings SET status='rejected' WHERE id=%s", (lid,))
    audit(f"reports_{act}", current_user()["id"], listing_id=lid)
    return jsonify(ok=True)


@bp.get("/admin/user-reports")
@require("admin", "moderator")
def user_reports():
    """Utilisateurs signalés depuis la messagerie : la modération ne voit que les conversations signalées."""
    rows = all_("""SELECT ur.id, ur.category, ur.reason, extract(epoch FROM ur.created_at)::float8 AS at,
                          t.id AS target_id, t.name AS target, t.suspended_at IS NOT NULL AS suspended,
                          rp.name AS reporter, ur.conversation_id
                   FROM user_reports ur JOIN users t ON t.id=ur.target_id JOIN users rp ON rp.id=ur.reporter_id
                   WHERE ur.status='open' ORDER BY ur.created_at DESC LIMIT 100""")
    for r in rows:
        r["messages"] = all_("""SELECT u.name AS sender, m.body, extract(epoch FROM m.created_at)::float8 AS at
                                FROM messages m JOIN users u ON u.id=m.sender_id WHERE m.conversation_id=%s
                                ORDER BY m.id DESC LIMIT 20""", (r["conversation_id"],)) if r["conversation_id"] else []
    return jsonify(items=rows)


@bp.post("/admin/users/<int:uid>/suspend")
@require("admin", "moderator")
def suspend(uid):
    """Suspend (ou rétablit) un compte : sessions coupées, annonces masquées, signalements clos."""
    on = body().get("suspend") is not False
    me = current_user()
    if uid == me["id"]:
        abort(400, "Vous ne pouvez pas vous suspendre vous-même.")
    if me["role"] != "admin" and one("SELECT 1 FROM users WHERE id=%s AND moderator", (uid,)):
        abort(403, "Seul un administrateur peut suspendre un modérateur.")
    if not one("UPDATE users SET suspended_at = CASE WHEN %s THEN now() END WHERE id=%s AND role<>'admin' RETURNING id",
               (on, uid)):
        abort(404, "Utilisateur introuvable.")
    if on:
        revoke_all(uid)
    run("UPDATE user_reports SET status='actioned' WHERE target_id=%s AND status='open'", (uid,))
    audit("user_suspended" if on else "user_restored", current_user()["id"], target=uid)
    return jsonify(ok=True)


@bp.post("/admin/user-reports/<int:rid>/dismiss")
@require("admin", "moderator")
def dismiss_user_report(rid):
    if not one("UPDATE user_reports SET status='dismissed' WHERE id=%s AND status='open' RETURNING id", (rid,)):
        abort(404, "Signalement introuvable.")
    return jsonify(ok=True)
