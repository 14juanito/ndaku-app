"""Sessions (cookie web + Bearer mobile), CSRF, limitation de débit, contrôle d'accès."""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from urllib.parse import urlsplit

from flask import abort, current_app, g, request
from werkzeug.security import check_password_hash, generate_password_hash

from .db import committed, one, run

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
_DUMMY_HASH = generate_password_hash("timing-equalizer-not-a-password")


def cfg():
    return current_app.config["NDAKU"]


def now():
    return datetime.now(timezone.utc)


def sha(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def client_ip():
    c = cfg()
    if c.ON_VERCEL:
        # Vercel écrase x-real-ip avec l'IP du client : valeur non falsifiable.
        return (request.headers.get("x-real-ip") or request.remote_addr or "")[:64]
    if c.TRUST_PROXY:
        # Derrière un proxy de confiance qui AJOUTE à X-Forwarded-For : seule l'entrée la plus à droite
        # est fiable ; celles de gauche sont fournies par le client.
        xff = [x.strip() for x in request.headers.get("x-forwarded-for", "").split(",") if x.strip()]
        return (xff[-1] if xff else request.remote_addr or "")[:64]
    return (request.remote_addr or "")[:64]


# ----------------------------------------------------------------- mots de passe
def hash_password(pw):
    return generate_password_hash(pw)


def check_password(pw_hash, pw):
    # Toujours exécuter un hachage, même sans compte : pas d'énumération par mesure de temps.
    ok = check_password_hash(pw_hash or _DUMMY_HASH, pw)
    return ok and pw_hash is not None


def password_problem(pw, email="", name=""):
    if not isinstance(pw, str) or len(pw) < 10 or len(pw) > 128:
        return "Mot de passe : 10 à 128 caractères."
    if pw.lower() == pw or pw.upper() == pw or not any(c.isdigit() for c in pw):
        return "Mot de passe : au moins une majuscule, une minuscule et un chiffre."
    low = pw.lower()
    if (email and email.split("@")[0].lower() in low and len(email.split("@")[0]) >= 4) or low in COMMON:
        return "Mot de passe trop facile à deviner."
    return None


COMMON = {"motdepasse1", "password123", "azerty1234", "qwerty1234", "ndaku12345", "kinshasa123", "1234567890a"}


# ---------------------------------------------------------------------- sessions
def start_session(user_id, kind="web"):
    token = secrets.token_urlsafe(32)
    run("INSERT INTO sessions (token_hash, user_id, kind, user_agent, ip, expires_at) VALUES (%s,%s,%s,%s,%s,%s)",
        (sha(token), user_id, kind, (request.user_agent.string or "")[:200], client_ip(),
         now() + timedelta(days=cfg().SESSION_DAYS)))
    g.new_session = (token, kind)
    return token


def end_session():
    tok = _presented_token()
    if tok:
        run("DELETE FROM sessions WHERE token_hash=%s", (sha(tok),))
    g.clear_cookie = True


def revoke_all(user_id, except_current=False):
    tok = _presented_token() if except_current else None
    run("DELETE FROM sessions WHERE user_id=%s AND token_hash IS DISTINCT FROM %s",
        (user_id, sha(tok) if tok else None))


def _presented_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        g.auth_via = "bearer"
        return auth[7:].strip() or None
    g.auth_via = "cookie"
    return request.cookies.get(cfg().cookie_name)


def current_user():
    if "user" in g:
        return g.user
    g.user = None
    tok = _presented_token()
    if tok and len(tok) < 200:
        u = one("""SELECT u.*, s.id AS session_id, s.last_seen FROM sessions s JOIN users u ON u.id=s.user_id
                   WHERE s.token_hash=%s AND s.expires_at > now() AND u.suspended_at IS NULL""", (sha(tok),))
        if u:
            if now() - u["last_seen"] > timedelta(hours=1):
                run("UPDATE sessions SET last_seen=now() WHERE id=%s", (u["session_id"],))
            g.user = u
    return g.user


def apply_session_cookie(resp):
    c = cfg()
    if g.get("new_session") and g.new_session[1] == "web":
        resp.set_cookie(c.cookie_name, g.new_session[0], max_age=c.SESSION_DAYS * 86400, httponly=True,
                        secure=c.SECURE_COOKIES, samesite="Lax", path="/")
    elif g.get("clear_cookie"):
        resp.delete_cookie(c.cookie_name, path="/", secure=c.SECURE_COOKIES, httponly=True, samesite="Lax")
    return resp


def require(*roles, verified_email=False, avatar=False):
    def deco(fn):
        @wraps(fn)
        def inner(*a, **kw):
            u = current_user()
            if not u:
                abort(401, "Connexion requise.")
            # « moderator » : rôle supplémentaire accordé par un administrateur, cumulable avec client/hôte.
            if roles and u["role"] not in roles and not ("moderator" in roles and u["moderator"]):
                abort(403, "Action réservée à un autre type de compte.")
            if verified_email and cfg().REQUIRE_EMAIL_VERIFICATION and not u["email_verified"]:
                abort(403, "Confirmez d'abord votre adresse e-mail.")
            if avatar and not u["avatar_url"]:
                abort(403, "Ajoutez d'abord une photo de profil.")
            return fn(*a, **kw)
        return inner
    return deco


# -------------------------------------------------------------------------- CSRF
def csrf_check():
    """Requêtes authentifiées par cookie : en-tête personnalisé + Origin même site.
    Un en-tête personnalisé force un pré-vol CORS ; aucune origine tierce n'est autorisée."""
    if request.method not in UNSAFE or request.headers.get("Authorization", "").startswith("Bearer "):
        return
    if request.path.startswith("/api/cron/"):
        return
    if request.headers.get("X-Ndaku") != "1":
        abort(403, "Requête refusée (en-tête de sécurité manquant).")
    origin = request.headers.get("Origin")
    if origin and urlsplit(origin).netloc != request.host:
        abort(403, "Origine non autorisée.")


# ------------------------------------------------------------- limitation de débit
def rate_limit(key, limit, window_s, message="Trop de requêtes. Réessayez plus tard."):
    """Compteur à fenêtre fixe partagé entre toutes les instances (stocké dans Postgres)."""
    start = datetime.fromtimestamp(int(now().timestamp()) // window_s * window_s, timezone.utc)
    n = committed("""INSERT INTO rate_limits (key, window_start, count) VALUES (%s,%s,1)
               ON CONFLICT (key, window_start) DO UPDATE SET count = rate_limits.count + 1 RETURNING count""",
            (key, start))["count"]
    if n > limit:
        resp_retry = int(window_s - (now() - start).total_seconds())
        g.retry_after = max(1, resp_retry)
        abort(429, message)


def audit(event, user_id=None, durable=False, **detail):
    """Journal d'audit. durable=True : écrit hors transaction (survit à l'erreur qui suit)."""
    import json
    (committed if durable else run)("INSERT INTO security_events (user_id, event, detail, ip) VALUES (%s,%s,%s,%s)",
        (user_id, event, json.dumps(detail), client_ip()))
