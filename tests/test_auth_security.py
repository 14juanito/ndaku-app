"""Tests d'attaque sur les comptes : brute force, énumération, sessions, CSRF, OAuth forgé, pré-détournement."""
import hashlib
import time

import pytest

from conftest import PW, id_token, register
from ndaku.db import pool
from conftest import DB


def sql(q, args=()):
    with pool(DB).connection() as con:
        cur = con.execute(q, args)
        return cur.fetchall() if cur.description else None


def nonce(c):
    return c.get("/api/auth/nonce").json["nonce"]


# ------------------------------------------------------------------ inscription
def test_password_policy_and_mass_assignment(client):
    weak = client.post("/api/auth/register", json={"name": "A B", "email": "a@x.cd", "password": "password", "role": "client"})
    assert weak.status_code == 400
    # Escalade de privilège par le corps de la requête : rôle admin et champs internes ignorés/refusés.
    r = client.post("/api/auth/register", json={"name": "Mallory", "email": "m@x.cd", "password": PW, "role": "admin"})
    assert r.status_code == 400
    r = client.post("/api/auth/register", json={"name": "Mallory", "email": "m@x.cd", "password": PW, "role": "host",
                                               "verified": True, "email_verified": True, "id": 1})
    assert r.status_code == 201 and r.json["user"]["role"] == "host"
    assert r.json["user"]["verified"] is False and r.json["user"]["email_verified"] is False


def test_email_is_case_insensitive_unique(client):
    register(client, "Jean@X.cd")
    r = client.post("/api/auth/register", json={"name": "Jean", "email": "jean@x.CD", "password": PW, "role": "client"})
    assert r.status_code == 409


def test_password_hash_never_exposed(client):
    u = register(client, "h@x.cd")
    assert "pw_hash" not in u and "pw_hash" not in client.get("/api/auth/me").json["user"]
    stored = sql("SELECT pw_hash FROM users WHERE id=%s", (u["id"],))[0]["pw_hash"]
    assert PW not in stored and stored.startswith("scrypt:")


# ------------------------------------------------------------------- connexion
def test_login_no_user_enumeration(client, new_client):
    register(client, "real@x.cd")
    a = new_client().post("/api/auth/login", json={"email": "real@x.cd", "password": "Wrong-pass-123"})
    b = new_client().post("/api/auth/login", json={"email": "ghost@x.cd", "password": "Wrong-pass-123"})
    assert a.status_code == b.status_code == 401 and a.json == b.json


def test_forgot_password_no_enumeration(client, new_client):
    register(client, "real@x.cd")
    a = new_client().post("/api/auth/password/forgot", json={"email": "real@x.cd"})
    b = new_client().post("/api/auth/password/forgot", json={"email": "ghost@x.cd"})
    assert a.status_code == b.status_code == 200 and a.json == b.json


def test_account_lockout_survives_failed_requests(client, new_client):
    register(client, "victim@x.cd")
    att = new_client()
    for _ in range(5):
        assert att.post("/api/auth/login", json={"email": "victim@x.cd", "password": "Guess-1234567"}).status_code == 401
    # Même le bon mot de passe est refusé pendant le verrouillage.
    r = att.post("/api/auth/login", json={"email": "victim@x.cd", "password": PW})
    assert r.status_code == 429
    assert sql("SELECT event FROM security_events WHERE event='account_locked'")


def test_ip_rate_limit_on_login(client):
    for i in range(30):
        client.post("/api/auth/login", json={"email": f"u{i}@x.cd", "password": "Whatever-123"})
    r = client.post("/api/auth/login", json={"email": "z@x.cd", "password": "Whatever-123"})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


def test_spoofed_forwarded_for_is_ignored_off_vercel(client):
    for i in range(30):
        client.post("/api/auth/login", json={"email": f"u{i}@x.cd", "password": "W-123456789a"},
                    headers={"X-Forwarded-For": f"10.0.0.{i}", "X-Real-IP": f"10.0.1.{i}"})
    assert client.post("/api/auth/login", json={"email": "z@x.cd", "password": "W-123456789a"},
                       headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 429


# --------------------------------------------------------------------- sessions
def test_session_cookie_flags_and_hashed_storage(client):
    r = client.post("/api/auth/register", json={"name": "Ana", "email": "ana@x.cd", "password": PW, "role": "client"})
    cookie = r.headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie and "Path=/" in cookie
    token = cookie.split("=", 1)[1].split(";")[0]
    stored = sql("SELECT token_hash FROM sessions")[0]["token_hash"]
    assert bytes(stored) == hashlib.sha256(token.encode()).digest()  # base volée ≠ sessions volées


def test_logout_revokes_server_side(client, new_client):
    r = client.post("/api/auth/register", json={"name": "Ana", "email": "ana@x.cd", "password": PW, "role": "client",
                                               "client": "mobile"})
    token = r.json["token"]
    mob = new_client()
    mob.headers = {"Authorization": f"Bearer {token}"}
    assert mob.get("/api/auth/me").json["user"]["email"] == "ana@x.cd"
    assert mob.post("/api/auth/logout").status_code == 200
    assert mob.get("/api/auth/me").json["user"] is None  # jeton rejoué après déconnexion : refusé


def test_forged_and_expired_tokens_rejected(client, new_client):
    register(client, "ana@x.cd")
    bad = new_client()
    for tok in ("x" * 43, "", "' OR 1=1 --", "A" * 5000):
        bad.headers = {"Authorization": f"Bearer {tok}"}
        assert bad.get("/api/auth/me").json["user"] is None
    sql("UPDATE sessions SET expires_at = now() - interval '1 second'")
    assert client.get("/api/auth/me").json["user"] is None


def test_password_reset_revokes_all_sessions_and_token_single_use(client, new_client, app, monkeypatch):
    sent = {}
    from ndaku import mailer
    monkeypatch.setattr(mailer, "send", lambda cfg, to, subject, text: sent.update(text=text))
    register(client, "ana@x.cd")
    other = new_client()
    assert other.post("/api/auth/password/forgot", json={"email": "ana@x.cd"}).status_code == 200
    token = sent["text"].split("token=")[1].split()[0]
    new_pw = "Nouveau-Pass-2027"
    assert other.post("/api/auth/password/reset", json={"token": token, "password": new_pw}).status_code == 200
    assert client.get("/api/auth/me").json["user"] is None  # l'ancienne session est coupée
    assert other.post("/api/auth/password/reset", json={"token": token, "password": "Autre-Pass-2028"}).status_code == 400
    assert other.post("/api/auth/login", json={"email": "ana@x.cd", "password": new_pw}).status_code == 200


def test_session_fixation_new_token_on_login(client):
    register(client, "ana@x.cd")
    before = client.c.get_cookie("ndaku_session").value
    client.post("/api/auth/login", json={"email": "ana@x.cd", "password": PW})
    assert client.c.get_cookie("ndaku_session").value != before


# ------------------------------------------------------------------------- CSRF
def test_csrf_custom_header_required_for_cookie_auth(client):
    register(client, "ana@x.cd")
    r = client.c.post("/api/auth/logout")  # navigateur tiers : pas d'en-tête X-Ndaku
    assert r.status_code == 403
    r = client.post("/api/auth/logout", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert client.post("/api/auth/logout", headers={"Origin": "http://localhost"}).status_code == 200


def test_cors_not_enabled(client):
    r = client.c.options("/api/auth/me", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "Access-Control-Allow-Origin" not in r.headers


# ------------------------------------------------------------------ Google / Apple
@pytest.mark.parametrize("provider", ["google", "apple"])
def test_oauth_happy_path_creates_verified_account(client, keys, provider):
    n = nonce(client)
    tok = id_token(keys, provider, nonce=n, email="new@icloud.com", sub=f"{provider}-1")
    r = client.post(f"/api/auth/oauth/{provider}", json={"id_token": tok, "nonce": n, "role": "host"})
    assert r.status_code == 200, r.json
    assert r.json["user"]["email_verified"] and r.json["user"]["role"] == "host" and provider in r.json["user"]["providers"]


@pytest.mark.parametrize("label,claims,key,alg", [
    ("signé par un attaquant", {}, "evil", "RS256"),
    ("mauvaise audience", {"aud": "other-app.apps.googleusercontent.com"}, "good", "RS256"),
    ("mauvais émetteur", {"iss": "https://evil.example"}, "good", "RS256"),
    ("expiré", {"exp": int(time.time()) - 3600, "iat": int(time.time()) - 7200}, "good", "RS256"),
    ("sans sub", {"sub": None}, "good", "RS256"),
])
def test_oauth_forged_tokens_rejected(client, keys, label, claims, key, alg):
    n = nonce(client)
    tok = id_token(keys, "google", key=key, alg=alg, nonce=n, **claims)
    assert client.post("/api/auth/oauth/google", json={"credential": tok, "nonce": n}).status_code == 401, label


def test_oauth_alg_none_and_hs256_confusion_rejected(client, keys):
    import jwt
    from cryptography.hazmat.primitives import serialization
    n = nonce(client)
    claims = {"iss": "https://accounts.google.com", "aud": "web-client.apps.googleusercontent.com", "sub": "x",
              "iat": int(time.time()), "exp": int(time.time()) + 600, "nonce": n, "email": "a@b.c", "email_verified": True}
    none_tok = jwt.encode(claims, None, algorithm="none")
    pub_pem = keys["good"].public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    import hmac, base64, json  # noqa: E401 — jeton HS256 « signé » avec la clé publique (attaque classique)
    seg = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=")  # noqa: E731
    head = seg({"alg": "HS256", "typ": "JWT"}) + b"." + seg(claims)
    hs_tok = (head + b"." + base64.urlsafe_b64encode(hmac.new(pub_pem, head, "sha256").digest()).rstrip(b"=")).decode()
    for tok in (none_tok, hs_tok):
        assert client.post("/api/auth/oauth/google", json={"credential": tok, "nonce": n}).status_code == 401


def test_oauth_nonce_replay_and_missing_nonce(client, keys):
    n = nonce(client)
    tok = id_token(keys, "google", nonce=n)
    assert client.post("/api/auth/oauth/google", json={"credential": tok, "nonce": n}).status_code == 200
    assert client.post("/api/auth/oauth/google", json={"credential": tok, "nonce": n}).status_code == 401  # rejeu
    tok2 = id_token(keys, "google", nonce=None)
    assert client.post("/api/auth/oauth/google", json={"credential": tok2, "nonce": "x"}).status_code == 401
    tok3 = id_token(keys, "google", nonce="nonce-jamais-emis")
    assert client.post("/api/auth/oauth/google", json={"credential": tok3, "nonce": "nonce-jamais-emis"}).status_code == 401


def test_oauth_ios_hashed_nonce_accepted(client, keys):
    n = nonce(client)
    tok = id_token(keys, "apple", nonce=hashlib.sha256(n.encode()).hexdigest(), sub="ios-1", email="i@icloud.com")
    assert client.post("/api/auth/oauth/apple", json={"id_token": tok, "nonce": n, "client": "mobile"}).json["token"]


def test_oauth_unverified_email_never_links_to_existing_account(client, new_client, keys):
    register(client, "victim@gmail.com")
    sql("UPDATE users SET email_verified=TRUE")
    att = new_client()
    n = nonce(att)
    tok = id_token(keys, "google", nonce=n, email="victim@gmail.com", email_verified=False, sub="attacker")
    r = att.post("/api/auth/oauth/google", json={"credential": tok, "nonce": n})
    assert r.status_code == 400  # pas d'e-mail vérifié → pas de compte, pas de liaison
    assert not sql("SELECT 1 FROM identities")


def test_prehijack_attack_neutralized(client, new_client, keys):
    """Un attaquant crée un compte à mot de passe avec l'e-mail de la victime (non vérifié) et garde
    une session ouverte. La victime se connecte ensuite avec Google : l'attaquant doit tout perdre."""
    attacker = new_client()
    register(attacker, "victim@gmail.com", name="Attaquant")
    victim = new_client()
    n = nonce(victim)
    r = victim.post("/api/auth/oauth/google", json={"credential": id_token(keys, "google", nonce=n), "nonce": n})
    assert r.status_code == 200 and r.json["user"]["has_password"] is False
    assert attacker.get("/api/auth/me").json["user"] is None
    assert attacker.post("/api/auth/login", json={"email": "victim@gmail.com", "password": PW}).status_code == 401
    assert sql("SELECT 1 FROM security_events WHERE event='prehijack_neutralized'")


def test_admin_only_via_verified_allowlisted_email(client, new_client, keys):
    # Inscription par mot de passe avec l'e-mail admin : pas admin tant que l'e-mail n'est pas prouvé.
    u = register(client, "boss@ndaku.test")
    assert u["role"] == "client"
    assert client.get("/api/admin/queue").status_code == 403
    boss = new_client()
    n = nonce(boss)
    r = boss.post("/api/auth/oauth/google", json={"credential": id_token(keys, "google", nonce=n, email="boss@ndaku.test",
                                                                           sub="boss"), "nonce": n})
    assert r.json["user"]["role"] == "admin" and boss.get("/api/admin/queue").status_code == 200


def test_cron_requires_secret(client):
    assert client.get("/api/cron/cleanup").status_code == 401
    assert client.get("/api/cron/cleanup", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/cron/cleanup", headers={"Authorization": "Bearer cron-secret-123"}).status_code == 200


def test_security_headers(client):
    r = client.get("/api/auth/me")
    for h in ("Content-Security-Policy", "X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy"):
        assert h in r.headers
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["Cache-Control"] == "no-store"
