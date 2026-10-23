"""Comptes : e-mail + mot de passe, Google, Apple (iCloud). Sessions web (cookie) et mobiles (Bearer)."""
import hmac
import re
import secrets
import time
from datetime import timedelta

from flask import Blueprint, abort, current_app, jsonify, request

from . import mailer, notify, oauth
from .db import all_, committed, one, run
from .security import (audit, cfg, check_password, client_ip, current_user, end_session, hash_password, now,
                       password_problem, rate_limit, require, revoke_all, sha, start_session)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")
LOCK_AFTER, LOCK_MINUTES = 5, 15
ROLES_SELF_SERVICE = ("client", "host")


def body():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        abort(400, "Corps JSON attendu.")
    return d


def text(d, key, n):
    v = d.get(key)
    return v.strip()[:n] if isinstance(v, str) else ""


def public_user(u):
    providers = [r["provider"] for r in
                 all_("SELECT provider FROM identities WHERE user_id=%s", (u["id"],))]
    unread = one("""SELECT COUNT(*)::int AS n FROM conversations c WHERE
                      (c.client_id=%(u)s AND c.last_message_at > c.client_read_at)
                   OR (c.host_id=%(u)s AND c.last_message_at > c.host_read_at)""", {"u": u["id"]})["n"]
    return {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"], "verified": u["verified"],
            "email_verified": u["email_verified"], "has_password": u["pw_hash"] is not None, "providers": providers,
            "avatar": u["avatar_url"], "phone": u["phone"], "phone_verified": u["phone_verified"], "unread": unread,
            "notif_unread": one("SELECT COUNT(*)::int AS n FROM notifications WHERE user_id=%s AND read_at IS NULL",
                                (u["id"],))["n"],
            "notify": {"email": u["notify_email"], "sms": u["notify_sms"], "whatsapp": u["notify_whatsapp"]}}


def session_response(user, kind, status=200):
    token = start_session(user["id"], kind)
    out = {"user": public_user(user)}
    if kind == "mobile":
        out["token"] = token  # les apps mobiles le stockent dans le Keychain / Keystore
    return jsonify(out), status


def kind_of(d):
    return "mobile" if d.get("client") == "mobile" else "web"


def maybe_promote_admin(user):
    if user["email_verified"] and user["email"].lower() in cfg().ADMIN_EMAILS and user["role"] != "admin":
        run("UPDATE users SET role='admin' WHERE id=%s", (user["id"],))
        audit("admin_promoted", user["id"])
        return one("SELECT * FROM users WHERE id=%s", (user["id"],))
    return user


def send_token_mail(user, purpose):
    tok = secrets.token_urlsafe(32)
    ttl = timedelta(hours=24) if purpose == "verify" else timedelta(hours=1)
    run("UPDATE email_tokens SET used_at=now() WHERE user_id=%s AND purpose=%s AND used_at IS NULL", (user["id"], purpose))
    run("INSERT INTO email_tokens (token_hash, user_id, purpose, expires_at) VALUES (%s,%s,%s,%s)",
        (sha(tok), user["id"], purpose, now() + ttl))
    link = f"{cfg().PUBLIC_URL}/#/{'verify' if purpose == 'verify' else 'reset'}?token={tok}"
    if purpose == "verify":
        mailer.send(cfg(), user["email"], "Confirmez votre adresse e-mail Ndaku",
                    f"Bonjour {user['name']},\n\nConfirmez votre adresse : {link}\n\nCe lien expire dans 24 h.")
    else:
        mailer.send(cfg(), user["email"], "Réinitialisation de votre mot de passe Ndaku",
                    f"Bonjour {user['name']},\n\nPour choisir un nouveau mot de passe : {link}\n\n"
                    "Ce lien expire dans 1 h. Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.")


def use_token(tok, purpose):
    if not isinstance(tok, str) or not 20 < len(tok) < 100:
        return None
    return one("""UPDATE email_tokens SET used_at=now() WHERE token_hash=%s AND purpose=%s AND used_at IS NULL
                  AND expires_at > now() RETURNING user_id""", (sha(tok), purpose))


# ---------------------------------------------------------------------------------
@bp.get("/config")
def config():
    c = cfg()
    return jsonify(google_client_id=(c.GOOGLE_CLIENT_IDS or [None])[0],
                   apple_client_id=(c.APPLE_CLIENT_IDS or [None])[0], apple_redirect_uri=c.APPLE_REDIRECT_URI,
                   email_verification=c.REQUIRE_EMAIL_VERIFICATION, notify_channels=notify.channels())


@bp.get("/me")
def me():
    u = current_user()
    return jsonify(user=public_user(u) if u else None)


@bp.post("/register")
def register():
    rate_limit(f"register:{client_ip()}", 10, 3600)
    d = body()
    name, email, pw, role = text(d, "name", 80), text(d, "email", 120).lower(), d.get("password"), d.get("role")
    if len(name) < 2 or "@" not in email or "." not in email.rsplit("@", 1)[-1] or " " in email:
        abort(400, "Nom ou e-mail invalide.")
    if role not in ROLES_SELF_SERVICE:
        abort(400, "Choisissez un type de compte : client ou hôte.")
    problem = password_problem(pw, email, name)
    if problem:
        abort(400, problem)
    if one("SELECT 1 FROM users WHERE lower(email)=%s", (email,)):
        abort(409, "Un compte existe déjà avec cet e-mail. Connectez-vous ou réinitialisez le mot de passe.")
    u = one("""INSERT INTO users (name, email, pw_hash, role, phone) VALUES (%s,%s,%s,%s,%s) RETURNING *""",
            (name, email, hash_password(pw), role, text(d, "phone", 30)))
    send_token_mail(u, "verify")
    audit("register", u["id"], method="password")
    return session_response(u, kind_of(d), 201)


@bp.post("/login")
def login():
    ip = client_ip()
    rate_limit(f"login-ip:{ip}", 30, 900, "Trop de tentatives depuis cette adresse. Réessayez dans 15 minutes.")
    d = body()
    email, pw = text(d, "email", 120).lower(), d.get("password")
    if not isinstance(pw, str):
        abort(400, "Mot de passe requis.")
    rate_limit(f"login-email:{email}", 10, 3600, "Trop de tentatives pour ce compte. Réessayez plus tard.")
    u = one("SELECT * FROM users WHERE lower(email)=%s", (email,))
    if u and u["suspended_at"] and check_password(u["pw_hash"], pw[:128]):
        abort(403, "Ce compte est suspendu. Contactez le support Ndaku.")
    if u and u["locked_until"] and u["locked_until"] > now():
        check_password(None, pw)
        abort(429, "Compte temporairement verrouillé après plusieurs échecs. Réessayez plus tard.")
    if not check_password(u["pw_hash"] if u else None, pw[:128]):
        if u:
            # Hors transaction : le compteur doit survivre au 401 qui suit.
            r = committed("""UPDATE users SET failed_logins = failed_logins + 1,
                               locked_until = CASE WHEN failed_logins + 1 >= %s THEN now() + make_interval(mins => %s) END
                             WHERE id=%s RETURNING failed_logins""", (LOCK_AFTER, LOCK_MINUTES, u["id"]))
            if r and r["failed_logins"] >= LOCK_AFTER:
                committed("UPDATE users SET failed_logins=0 WHERE id=%s", (u["id"],))
                audit("account_locked", u["id"], durable=True)
        abort(401, "E-mail ou mot de passe incorrect.")
    run("UPDATE users SET failed_logins=0, locked_until=NULL WHERE id=%s", (u["id"],))
    u = maybe_promote_admin(u)
    audit("login", u["id"], method="password")
    return session_response(u, kind_of(d))


@bp.post("/logout")
def logout():
    end_session()
    return jsonify(ok=True)


@bp.post("/logout-all")
@require()
def logout_all():
    revoke_all(current_user()["id"])
    end_session()
    return jsonify(ok=True)


@bp.post("/verify-email")
def verify_email():
    rate_limit(f"verify:{client_ip()}", 20, 3600)
    r = use_token(body().get("token"), "verify")
    if not r:
        abort(400, "Lien invalide ou expiré.")
    run("UPDATE users SET email_verified=TRUE WHERE id=%s", (r["user_id"],))
    maybe_promote_admin(one("SELECT * FROM users WHERE id=%s", (r["user_id"],)))
    return jsonify(ok=True)


@bp.post("/resend-verification")
@require()
def resend_verification():
    u = current_user()
    rate_limit(f"resend:{u['id']}", 3, 3600)
    if not u["email_verified"]:
        send_token_mail(u, "verify")
    return jsonify(ok=True)


FORGOT_MIN_SECONDS = 2.0


@bp.post("/password/forgot")
def forgot():
    started = time.monotonic()
    rate_limit(f"forgot:{client_ip()}", 5, 3600)
    email = text(body(), "email", 120).lower()
    u = one("SELECT * FROM users WHERE lower(email)=%s", (email,))
    if u:
        rate_limit(f"forgot-user:{u['id']}", 3, 3600)
        send_token_mail(u, "reset")
    # Même réponse ET même durée minimale que le compte existe ou non (pas d'énumération par le temps).
    time.sleep(max(0.0, FORGOT_MIN_SECONDS - (time.monotonic() - started)))
    return jsonify(ok=True, message="Si un compte existe, un e-mail vient d'être envoyé.")


@bp.post("/password/reset")
def reset():
    rate_limit(f"reset:{client_ip()}", 10, 3600)
    d = body()
    r = use_token(d.get("token"), "reset")
    if not r:
        abort(400, "Lien invalide ou expiré.")
    u = one("SELECT * FROM users WHERE id=%s", (r["user_id"],))
    problem = password_problem(d.get("password"), u["email"], u["name"])
    if problem:
        abort(400, problem)
    # Réinitialiser prouve la possession de l'e-mail : on le marque vérifié et on coupe toutes les sessions.
    run("UPDATE users SET pw_hash=%s, email_verified=TRUE, failed_logins=0, locked_until=NULL WHERE id=%s",
        (hash_password(d["password"]), u["id"]))
    revoke_all(u["id"])
    audit("password_reset", u["id"])
    return jsonify(ok=True)


@bp.post("/password/change")
@require()
def change_password():
    u, d = current_user(), body()
    rate_limit(f"pwchange:{u['id']}", 10, 3600)
    if u["pw_hash"] and not check_password(u["pw_hash"], str(d.get("current_password", ""))[:128]):
        abort(403, "Mot de passe actuel incorrect.")
    problem = password_problem(d.get("new_password"), u["email"], u["name"])
    if problem:
        abort(400, problem)
    run("UPDATE users SET pw_hash=%s WHERE id=%s", (hash_password(d["new_password"]), u["id"]))
    revoke_all(u["id"], except_current=True)
    audit("password_changed", u["id"])
    return jsonify(ok=True)


# ------------------------------------------------------------------ Google / Apple
@bp.get("/nonce")
def nonce():
    rate_limit(f"nonce:{client_ip()}", 60, 600)
    return jsonify(nonce=oauth.issue_nonce())


@bp.post("/oauth/<provider>")
def oauth_login(provider):
    rate_limit(f"oauth:{client_ip()}", 30, 900)
    d = body()
    token = d.get("id_token") or d.get("credential")
    audiences = cfg().GOOGLE_CLIENT_IDS if provider == "google" else cfg().APPLE_CLIENT_IDS if provider == "apple" else []
    try:
        info = oauth.verify(provider, token, d.get("nonce"), audiences)
    except oauth.OAuthError as e:
        audit("oauth_rejected", None, durable=True, provider=provider, reason=str(e))
        abort(401, str(e))

    ident = one("SELECT u.* FROM identities i JOIN users u ON u.id=i.user_id WHERE i.provider=%s AND i.subject=%s",
                (provider, info["sub"]))
    if ident:
        user = ident
    else:
        email = info["email"] if info["email_verified"] else None
        existing = one("SELECT * FROM users WHERE lower(email)=%s", (email,)) if email else None
        if existing:
            if not existing["email_verified"]:
                # Défense « pré-détournement de compte » : quelqu'un a pu créer un compte à mot de passe
                # avec cet e-mail sans le posséder. Le fournisseur prouve la possession → on retire le
                # mot de passe inconnu et on coupe toutes les sessions existantes.
                run("UPDATE users SET pw_hash=NULL, email_verified=TRUE WHERE id=%s", (existing["id"],))
                revoke_all(existing["id"])
                audit("prehijack_neutralized", existing["id"], provider=provider)
            user = existing
        else:
            if not email:
                abort(400, "Votre compte " + provider.title() + " ne fournit pas d'e-mail vérifié.")
            role = d.get("role") if d.get("role") in ROLES_SELF_SERVICE else "client"
            name = (text(d, "name", 80) or (info["name"] or "")[:80] or email.split("@")[0])
            user = one("INSERT INTO users (name, email, email_verified, role) VALUES (%s,%s,TRUE,%s) RETURNING *",
                       (name, email, role))
            audit("register", user["id"], method=provider)
        run("INSERT INTO identities (user_id, provider, subject, email) VALUES (%s,%s,%s,%s)",
            (user["id"], provider, info["sub"], info["email"]))
        audit("identity_linked", user["id"], provider=provider)
        user = one("SELECT * FROM users WHERE id=%s", (user["id"],))
    if user["suspended_at"]:
        abort(403, "Ce compte est suspendu. Contactez le support Ndaku.")
    if info.get("picture") and not user["avatar_url"]:
        run("UPDATE users SET avatar_url=%s WHERE id=%s", (info["picture"], user["id"]))
        user = one("SELECT * FROM users WHERE id=%s", (user["id"],))
    user = maybe_promote_admin(user)
    audit("login", user["id"], method=provider)
    return session_response(user, kind_of(d))


@bp.get("/sessions")
@require()
def sessions():
    rows = all_(
        "SELECT id, kind, user_agent, created_at, last_seen FROM sessions WHERE user_id=%s AND expires_at>now() "
        "ORDER BY last_seen DESC", (current_user()["id"],))
    return jsonify(items=rows)


# ------------------------------------------------------------------------ profil
AVATAR_SIZE = 400


@bp.post("/me/avatar")
@require()
def set_avatar():
    """Photo de profil (obligatoire pour publier, écrire ou noter) : recadrée en carré, ré-encodée."""
    from PIL import Image, ImageOps

    from . import antifraud as af
    from .storage import StorageUnavailable
    u = current_user()
    rate_limit(f"avatar:{u['id']}", 10, 3600)
    f = request.files.get("image")
    if not f:
        abort(400, "Fichier « image » manquant.")
    try:
        img = af.load_image(f.read(), min_w=200, min_h=200)
    except af.ImageRejected as e:
        abort(422, str(e))
    img = ImageOps.fit(img, (AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)
    st = current_app.config["STORAGE"]
    try:
        url, key = st.put(af.to_jpeg(img), folder="avatars")
    except StorageUnavailable:
        abort(503, "Stockage des photos non configuré.")
    old = u["avatar_key"]
    run("UPDATE users SET avatar_url=%s, avatar_key=%s WHERE id=%s", (url, key, u["id"]))
    if old:
        st.delete([old])
    return jsonify(avatar=url)


@bp.patch("/me")
@require()
def update_me():
    u, d = current_user(), body()
    name = text(d, "name", 80) if "name" in d else u["name"]
    phone = text(d, "phone", 30) if "phone" in d else u["phone"]
    if len(name) < 2:
        abort(400, "Nom invalide.")
    if phone and not re.fullmatch(r"\+?[0-9 ().-]{6,30}", phone):
        abort(400, "Numéro de téléphone invalide.")
    prefs = {}
    for ch in ("email", "sms", "whatsapp"):
        v = d.get("notify", {}).get(ch) if isinstance(d.get("notify"), dict) else None
        if v is not None:
            if not isinstance(v, bool):
                abort(400, "Préférence invalide.")
            prefs[ch] = v
    phone_changed = notify.e164(phone) != notify.e164(u["phone"])
    phone_ok = u["phone_verified"] and not phone_changed
    if (prefs.get("sms") or prefs.get("whatsapp")) and not phone_ok:
        abort(400, "Confirmez d'abord votre numéro de téléphone (code par SMS).")
    sms = prefs.get("sms", u["notify_sms"]) and phone_ok
    wa = prefs.get("whatsapp", u["notify_whatsapp"]) and phone_ok
    run("""UPDATE users SET name=%s, phone=%s, notify_email=%s, notify_sms=%s, notify_whatsapp=%s,
                  phone_verified=%s WHERE id=%s""",
        (name, phone, prefs.get("email", u["notify_email"]), sms, wa, phone_ok, u["id"]))
    return jsonify(user=public_user(one("SELECT * FROM users WHERE id=%s", (u["id"],))))


@bp.post("/me/phone/code")
@require()
def phone_code():
    u = current_user()
    to = notify.e164(u["phone"])
    if not to or len(to) < 9:
        abort(400, "Enregistrez d'abord un numéro de téléphone.")
    if not notify.channels()["sms"]:
        abort(503, "L'envoi de SMS n'est pas configuré.")
    rate_limit(f"phone-code:{u['id']}", 3, 3600, "Trop de codes demandés. Réessayez dans une heure.")
    rate_limit(f"phone-code-to:{to}", 5, 86400, "Trop de codes envoyés à ce numéro aujourd'hui.")
    code = f"{secrets.randbelow(10**6):06d}"
    run("UPDATE users SET phone_code_hash=%s, phone_code_expires=now() + interval '10 minutes' WHERE id=%s",
        (sha(f"{u['id']}:{to}:{code}").hex(), u["id"]))
    notify._twilio(to, f"Ndaku : votre code de confirmation est {code}. Il expire dans 10 minutes.")
    return jsonify(ok=True)


@bp.post("/me/phone/verify")
@require()
def phone_verify():
    u, d = current_user(), body()
    rate_limit(f"phone-verify:{u['id']}", 5, 3600, "Trop d'essais. Demandez un nouveau code plus tard.")
    code = d.get("code")
    to = notify.e164(u["phone"])
    if (not isinstance(code, str) or not code.isdigit() or not to or not u["phone_code_hash"]
            or u["phone_code_expires"] < now()
            or not hmac.compare_digest(u["phone_code_hash"], sha(f"{u['id']}:{to}:{code}").hex())):
        abort(400, "Code invalide ou expiré.")
    run("UPDATE users SET phone_verified=TRUE, phone_code_hash=NULL WHERE id=%s", (u["id"],))
    return jsonify(user=public_user(one("SELECT * FROM users WHERE id=%s", (u["id"],))))
