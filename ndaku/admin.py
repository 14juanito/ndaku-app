"""Modération et tâches planifiées."""
import hmac

from flask import Blueprint, abort, current_app, jsonify, request

from .auth import body
from .db import all_, one, run
from .listings import BASE_SQL, card
from .security import audit, cfg, current_user, require

bp = Blueprint("admin", __name__, url_prefix="/api")


@bp.get("/admin/queue")
@require("admin")
def queue():
    rows = all_(f"{BASE_SQL} WHERE l.status='pending' ORDER BY l.risk_score DESC LIMIT 100")
    reports = {}
    for r in all_("SELECT listing_id, reason FROM reports WHERE listing_id = ANY(%s)", ([r["id"] for r in rows],)):
        reports.setdefault(r["listing_id"], []).append(r["reason"])
    return jsonify(items=[{**card(r), "risk_score": r["risk_score"], "risk_reasons": r["risk_reasons"],
                           "host": r["host_name"], "host_id": r["owner_id"], "reports": reports.get(r["id"], [])}
                          for r in rows])


@bp.post("/admin/listings/<int:lid>/decision")
@require("admin")
def decide(lid):
    act = body().get("action")
    if act not in ("approve", "reject"):
        abort(400, "Action invalide.")
    if not one("UPDATE listings SET status=%s WHERE id=%s AND status='pending' RETURNING id",
               ("active" if act == "approve" else "rejected", lid)):
        abort(404, "Annonce non en attente.")
    if act == "approve":
        run("DELETE FROM reports WHERE listing_id=%s", (lid,))
    audit(f"moderation_{act}", current_user()["id"], listing_id=lid)
    return jsonify(ok=True)


@bp.post("/admin/users/<int:uid>/verify")
@require("admin")
def verify_user(uid):
    if not one("UPDATE users SET verified=TRUE WHERE id=%s RETURNING id", (uid,)):
        abort(404, "Utilisateur introuvable.")
    audit("host_verified", current_user()["id"], target=uid)
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
    return jsonify(ok=True, images_removed=len(stale))


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
