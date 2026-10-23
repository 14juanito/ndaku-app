"""Messagerie client ↔ hôte. Une demande de visite ouvre (ou rouvre) la conversation liée à l'annonce ;
les deux parties peuvent ensuite discuter et, si elles le souhaitent, partager leurs coordonnées.

Accès strictement limité aux deux participants (404 pour tout autre compte, admin compris : la
modération ne lit une conversation que si elle a été signalée)."""
import json
import re
from datetime import date, timedelta

from flask import Blueprint, abort, jsonify, request

from .auth import body, text
from .db import all_, one, run
from .security import current_user, rate_limit, require

bp = Blueprint("messages", __name__, url_prefix="/api")
MAX_BODY = 2000
# Mentions de paiement / transfert : le destinataire voit un avertissement (arnaque à l'acompte).
PAYMENT = re.compile(r"\b(acompte|avance|caution|western union|moneygram|m-?pesa|airtel money|orange money|"
                     r"virement|transf[eé]r|envoy(?:er|ez) (?:l'|de l')?argent|payer avant|frais de dossier|"
                     r"frais de visite)\b", re.I)
USER_REPORT_CATEGORIES = {"arnaque": "Demande d'argent / arnaque", "harcelement": "Harcèlement ou propos déplacés",
                          "faux_profil": "Faux profil", "autre": "Autre"}


def participant(cid):
    """Conversation dont l'utilisateur est participant, avec son rôle ; 404 sinon."""
    u = current_user()
    c = one("""SELECT c.*, l.title, l.cover_url, l.status AS listing_status FROM conversations c
               JOIN listings l ON l.id=c.listing_id WHERE c.id=%s AND (c.client_id=%s OR c.host_id=%s)""",
            (cid, u["id"], u["id"]))
    if not c:
        abort(404, "Conversation introuvable.")
    c["me"] = "client" if c["client_id"] == u["id"] else "host"
    return c


def add_message(c, sender_id, body_text, kind="text", meta=None):
    flagged = bool(PAYMENT.search(body_text))
    m = one("""INSERT INTO messages (conversation_id, sender_id, kind, body, meta, flagged)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING id, extract(epoch FROM created_at)::float8 AS created_at""",
            (c["id"], sender_id, kind, body_text, json.dumps(meta or {}), flagged))
    read_col = "client_read_at" if sender_id == c["client_id"] else "host_read_at"
    run(f"UPDATE conversations SET last_message_at=now(), {read_col}=now() WHERE id=%s", (c["id"],))
    return m


def _message_rate(u):
    rate_limit(f"msg:{u['id']}", 40, 600, "Vous envoyez trop de messages. Patientez quelques minutes.")


@bp.post("/listings/<int:lid>/conversation")
@require(avatar=True)
def start(lid):
    """Demande de visite : crée la conversation (ou réutilise l'existante) avec un premier message."""
    u, d = current_user(), body()
    lst = one("""SELECT l.id, l.owner_id FROM listings l JOIN users h ON h.id=l.owner_id
                 WHERE l.id=%s AND l.status='active' AND h.suspended_at IS NULL""", (lid,))
    if not lst:
        abort(404, "Annonce introuvable.")
    if lst["owner_id"] == u["id"]:
        abort(400, "C'est votre propre annonce.")
    _message_rate(u)
    rate_limit(f"conv-new:{u['id']}", 20, 86400, "Trop de nouvelles conversations aujourd'hui.")
    msg = text(d, "message", MAX_BODY)
    if len(msg) < 5:
        abort(400, "Écrivez un message à l'hôte.")
    meta = {}
    if d.get("date"):
        try:
            when = date.fromisoformat(str(d["date"])[:10])
        except ValueError:
            abort(400, "Date invalide.")
        if not date.today() <= when <= date.today() + timedelta(days=365):
            abort(400, "Date de visite hors limites.")
        meta["date"] = when.isoformat()
    c = one("""INSERT INTO conversations (listing_id, client_id, host_id) VALUES (%s,%s,%s)
               ON CONFLICT (listing_id, client_id) DO UPDATE SET listing_id=EXCLUDED.listing_id RETURNING *""",
            (lid, u["id"], lst["owner_id"]))
    if c["blocked_by"]:
        abort(403, "Cette conversation a été bloquée.")
    add_message(c, u["id"], msg, "visit" if meta else "text", meta)
    return jsonify(id=c["id"]), 201


@bp.get("/conversations")
@require()
def inbox():
    uid = current_user()["id"]
    rows = all_("""
        SELECT c.id, c.listing_id, l.title, l.cover_url AS cover,
               CASE WHEN c.client_id=%(u)s THEN 'client' ELSE 'host' END AS me,
               o.id AS other_id, o.name AS other_name, o.avatar_url AS other_avatar, o.verified AS other_verified,
               extract(epoch FROM c.last_message_at)::float8 AS last_at, c.blocked_by IS NOT NULL AS blocked,
               (c.last_message_at > CASE WHEN c.client_id=%(u)s THEN c.client_read_at ELSE c.host_read_at END) AS unread,
               lm.body AS last_body, lm.kind AS last_kind, lm.sender_id = %(u)s AS last_mine
        FROM conversations c
        JOIN listings l ON l.id=c.listing_id
        JOIN users o ON o.id = CASE WHEN c.client_id=%(u)s THEN c.host_id ELSE c.client_id END
        LEFT JOIN LATERAL (SELECT body, kind, sender_id FROM messages WHERE conversation_id=c.id
                           ORDER BY id DESC LIMIT 1) lm ON TRUE
        WHERE c.client_id=%(u)s OR c.host_id=%(u)s
        ORDER BY c.last_message_at DESC LIMIT 200""", {"u": uid})
    return jsonify(items=rows)


@bp.get("/conversations/<int:cid>")
@require()
def thread(cid):
    """Messages d'une conversation ; `after` (id) pour ne récupérer que les nouveaux (rafraîchissement)."""
    c, uid = participant(cid), current_user()["id"]
    try:
        after = int(request.args.get("after", 0))
    except ValueError:
        abort(400, "Paramètre invalide.")
    msgs = all_("""SELECT m.id, m.sender_id, m.kind, m.body, m.meta, m.flagged,
                          extract(epoch FROM m.created_at)::float8 AS created_at
                   FROM messages m WHERE m.conversation_id=%s AND m.id > %s ORDER BY m.id LIMIT 300""", (cid, after))
    read_col = "client_read_at" if c["me"] == "client" else "host_read_at"
    run(f"UPDATE conversations SET {read_col}=now() WHERE id=%s", (cid,))
    other_id = c["host_id"] if c["me"] == "client" else c["client_id"]
    other = one("SELECT id, name, avatar_url AS avatar, verified FROM users WHERE id=%s", (other_id,))
    for m in msgs:
        m["mine"] = m["sender_id"] == uid
        m["warn"] = m["flagged"] and not m["mine"]
        del m["flagged"]
    return jsonify(id=cid, listing_id=c["listing_id"], title=c["title"], cover=c["cover_url"], me=c["me"],
                   other=other, blocked=c["blocked_by"] is not None, blocked_by_me=c["blocked_by"] == uid,
                   messages=msgs)


@bp.post("/conversations/<int:cid>/messages")
@require(avatar=True)
def send(cid):
    c, u = participant(cid), current_user()
    if c["blocked_by"]:
        abort(403, "Cette conversation est bloquée.")
    _message_rate(u)
    msg = text(body(), "body", MAX_BODY)
    if not msg:
        abort(400, "Message vide.")
    return jsonify(add_message(c, u["id"], msg)), 201


@bp.post("/conversations/<int:cid>/share-contact")
@require(avatar=True)
def share_contact(cid):
    """Partage volontaire de ses coordonnées (téléphone et/ou e-mail) avec l'autre participant."""
    c, u = participant(cid), current_user()
    if c["blocked_by"]:
        abort(403, "Cette conversation est bloquée.")
    _message_rate(u)
    d = body()
    parts = {}
    if d.get("phone") and u["phone"]:
        parts["phone"] = u["phone"]
    if d.get("email"):
        parts["email"] = u["email"]
    if not parts:
        abort(400, "Ajoutez un numéro de téléphone à votre profil ou partagez votre e-mail.")
    text_ = "Mes coordonnées : " + " · ".join(parts.values())
    return jsonify(add_message(c, u["id"], text_, "contact", parts)), 201


@bp.post("/conversations/<int:cid>/block")
@require()
def block(cid):
    c, uid = participant(cid), current_user()["id"]
    unblock = body().get("unblock") is True
    if unblock:
        run("UPDATE conversations SET blocked_by=NULL WHERE id=%s AND blocked_by=%s", (cid, uid))
    elif not c["blocked_by"]:
        run("UPDATE conversations SET blocked_by=%s WHERE id=%s", (uid, cid))
    return jsonify(ok=True)


@bp.post("/conversations/<int:cid>/report")
@require()
def report_user(cid):
    c, u, d = participant(cid), current_user(), body()
    rate_limit(f"user-report:{u['id']}", 10, 86400)
    category, reason = d.get("category"), text(d, "reason", 500)
    if category not in USER_REPORT_CATEGORIES:
        abort(400, "Motif invalide.")
    target = c["host_id"] if c["me"] == "client" else c["client_id"]
    if not one("""INSERT INTO user_reports (reporter_id, target_id, conversation_id, category, reason)
                  VALUES (%s,%s,%s,%s,%s) ON CONFLICT (reporter_id, target_id) DO NOTHING RETURNING id""",
               (u["id"], target, cid, category, reason or USER_REPORT_CATEGORIES[category])):
        abort(409, "Vous avez déjà signalé cet utilisateur.")
    run("UPDATE conversations SET blocked_by=COALESCE(blocked_by, %s) WHERE id=%s", (u["id"], cid))
    return jsonify(ok=True)
