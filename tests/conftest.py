import io
import os
import sys
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ndaku import create_app, oauth  # noqa: E402
from ndaku.db import pool  # noqa: E402
from ndaku.demo import render_house  # noqa: E402

DB = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@localhost:5433/ndaku_test")
GOOGLE_AUD, APPLE_AUD = "web-client.apps.googleusercontent.com", "app.ndaku.web"
PW = "Kinshasa-2026x"


@pytest.fixture(scope="session")
def keys():
    return {"good": rsa.generate_private_key(public_exponent=65537, key_size=2048),
            "evil": rsa.generate_private_key(public_exponent=65537, key_size=2048)}


@pytest.fixture()
def app(tmp_path, keys, monkeypatch):
    a = create_app(DATABASE_URL=DB, LOCAL_UPLOADS=str(tmp_path / "up"), GOOGLE_CLIENT_IDS=[GOOGLE_AUD],
                   APPLE_CLIENT_IDS=[APPLE_AUD], ADMIN_EMAILS={"boss@ndaku.test"}, CRON_SECRET="cron-secret-123",
                   REQUIRE_EMAIL_VERIFICATION=False)
    a.config["STORAGE"].cfg.LOCAL_UPLOADS = str(tmp_path / "up")
    os.makedirs(tmp_path / "up", exist_ok=True)
    with pool(DB).connection() as con:
        tables = [r["tablename"] for r in con.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")]
        con.execute("TRUNCATE " + ", ".join(tables) + " RESTART IDENTITY CASCADE")
    # Les JWKS Google/Apple sont remplacés par notre clé de test (aucun accès réseau).
    monkeypatch.setattr(oauth, "_signing_key", lambda provider, token: keys["good"].public_key())
    return a


class Client:
    def __init__(self, app):
        self.c = app.test_client()
        self.headers = {"X-Ndaku": "1"}

    def __getattr__(self, method):
        def call(path, **kw):
            kw.setdefault("headers", {})
            kw["headers"] = {**self.headers, **kw["headers"]}
            return getattr(self.c, method)(path, **kw)
        return call


@pytest.fixture()
def client(app):
    return Client(app)


@pytest.fixture()
def new_client(app):
    return lambda: Client(app)


def register(c, email, role="client", name="Test User", pw=PW):
    r = c.post("/api/auth/register", json={"name": name, "email": email, "password": pw, "role": role})
    assert r.status_code == 201, r.json
    return r.json["user"]


def jpeg(img, q=90):
    b = io.BytesIO()
    img.save(b, "JPEG", quality=q)
    return b.getvalue()


def upload(c, seed=None, raw=None, name="p.jpg"):
    data = raw if raw is not None else jpeg(render_house(seed))
    return c.post("/api/uploads", data={"image": (io.BytesIO(data), name)}, content_type="multipart/form-data")


def listing_payload(image_ids, **over):
    return {"title": "Belle maison familiale", "description": "Maison lumineuse, quartier calme et sécurisé, "
            "proche des écoles et commerces, eau et électricité.", "deal": "location", "ptype": "maison",
            "city": "Kinshasa", "commune": "Gombe", "address": "Avenue Test 1", "price": 800, "bedrooms": 3,
            "bathrooms": 2, "surface": 150, "image_ids": image_ids, **over}


def publish(c, seeds, **over):
    ids = []
    for s in seeds:
        r = upload(c, s)
        assert r.status_code == 201, r.json
        ids.append(r.json["id"])
    return c.post("/api/listings", json=listing_payload(ids, **over))


def id_token(keys, provider="google", key="good", alg="RS256", **claims):
    now = int(time.time())
    base = {"iss": "https://accounts.google.com" if provider == "google" else "https://appleid.apple.com",
            "aud": GOOGLE_AUD if provider == "google" else APPLE_AUD, "sub": "sub-123", "iat": now, "exp": now + 600,
            "email": "victim@gmail.com", "email_verified": True, "name": "Victime"}
    base.update(claims)
    base = {k: v for k, v in base.items() if v is not None}
    return jwt.encode(base, keys[key], algorithm=alg)
