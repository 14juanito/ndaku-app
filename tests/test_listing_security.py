"""Tests d'attaque sur les annonces : IDOR, contournement anti-fraude, injections, upload, XSS stocké."""
import io

import pytest
from PIL import ImageOps

from conftest import avenue, commune_id, jpeg, listing_payload, publish, register, upload
from ndaku.demo import render_house


@pytest.fixture()
def two_hosts(client, new_client):
    a, b = client, new_client()
    register(a, "a@x.cd", "host")
    register(b, "b@x.cd", "host")
    return a, b


# ---------------------------------------------------------------- contrôle d'accès
def test_client_cannot_publish_or_upload(client):
    register(client, "c@x.cd", "client")
    assert upload(client, 1).status_code == 403
    assert client.post("/api/listings", json=listing_payload([1, 2, 3], {"commune_id": 1, "avenue_id": 1})).status_code == 403


def test_anonymous_writes_rejected(client):
    for path in ("/api/uploads", "/api/listings", "/api/listings/1/favorite", "/api/listings/1/report"):
        assert client.post(path, json={}).status_code == 401


def test_idor_other_host_listing(two_hosts):
    a, b = two_hosts
    lid = publish(a, [1, 2, 3]).json["id"]
    assert b.delete(f"/api/listings/{lid}").status_code == 404
    assert b.patch(f"/api/listings/{lid}", json={"status": "closed"}).status_code == 404
    assert a.get(f"/api/listings/{lid}").status_code == 200


def test_cannot_steal_other_hosts_pending_photos(two_hosts):
    a, b = two_hosts
    ids = [upload(a, s).json["id"] for s in (1, 2, 3)]
    r = b.post("/api/listings", json=listing_payload(ids, avenue(b, "Avenue B")))
    assert r.status_code == 400
    assert b.delete(f"/api/uploads/{ids[0]}").status_code == 404


def test_cannot_reuse_photos_already_attached(two_hosts):
    a, _ = two_hosts
    ids = [upload(a, s).json["id"] for s in (1, 2, 3)]
    loc = avenue(a)
    assert a.post("/api/listings", json=listing_payload(ids, loc)).status_code == 201
    r = a.post("/api/listings", json=listing_payload(ids, loc, house_number="9"))
    assert r.status_code == 400


def test_pending_listing_hidden_from_public(two_hosts, new_client):
    a, _ = two_hosts
    lid = publish(a, [1, 2, 3], price=50).json["id"]  # non vérifié + prix → peut être pending
    from conftest import DB
    from ndaku.db import pool
    with pool(DB).connection() as con:
        con.execute("UPDATE listings SET status='pending' WHERE id=%s", (lid,))
    assert new_client().get(f"/api/listings/{lid}").status_code == 404
    assert a.get(f"/api/listings/{lid}").status_code == 200
    assert lid not in [x["id"] for x in new_client().get("/api/listings").json["items"]]


def test_mass_assignment_on_listing(two_hosts):
    a, _ = two_hosts
    ids = [upload(a, s).json["id"] for s in (1, 2, 3)]
    r = a.post("/api/listings", json=listing_payload(ids, avenue(a), status="active", risk_score=-999, owner_id=999, is_demo=True,
                                                       addr_key="x", cover_url="javascript:alert(1)"))
    assert r.status_code == 201
    d = a.get(f"/api/listings/{r.json['id']}").json
    assert d["host"]["name"] == "Test User" and d["is_demo"] is False and d["risk_score"] >= 0


# ------------------------------------------------------------------ anti-fraude
def test_duplicate_photo_across_hosts_all_variants(two_hosts):
    a, b = two_hosts
    publish(a, [1, 2, 3])
    base = render_house(1)
    for variant in (base, ImageOps.mirror(base), base.resize((900, 600)), base.crop((12, 10, 1188, 790))):
        r = upload(b, raw=jpeg(variant, 55))
        assert r.status_code == 422 and "autre annonce" in r.json["error"]


def test_duplicate_within_own_pending_uploads(two_hosts):
    a, _ = two_hosts
    assert upload(a, 7).status_code == 201
    r = upload(a, 7)
    assert r.status_code == 422 and "en attente" in r.json["error"]


def test_same_address_by_another_host_blocked(two_hosts):
    a, b = two_hosts
    publish(a, [1, 2, 3])
    r = publish(b, [4, 5, 6], avenue_name="  avenue TEST ")  # même avenue, casse/espaces différents
    assert r.status_code == 409
    r = publish(b, [7, 8, 9], avenue_name="Av. Test")  # autre écriture → autre lieu, mais même adresse normalisée
    assert r.status_code == 409 and "déjà publiée" in r.json["error"]


def test_contact_info_and_unrealistic_values_blocked(two_hosts):
    a, _ = two_hosts
    ids = [upload(a, s).json["id"] for s in (1, 2, 3)]
    loc = avenue(a)
    assert a.post("/api/listings", json=listing_payload(ids, loc, description="Appelez le 0812345678 " + "x" * 60)).status_code == 400
    assert a.post("/api/listings", json=listing_payload(ids, loc, price=1)).status_code == 400
    assert a.post("/api/listings", json=listing_payload(ids, loc, bedrooms=10, surface=40)).status_code == 400
    assert a.post("/api/listings", json=listing_payload(ids, {**loc, "commune_id": commune_id("Lemba")})).status_code == 400
    assert a.post("/api/listings", json=listing_payload(ids, {**loc, "lat": 48.85, "lng": 2.35})).status_code == 400  # Paris
    assert a.post("/api/listings", json=listing_payload(ids, {**loc, "avenue_id": 999999})).status_code == 400
    assert a.post("/api/listings", json=listing_payload(ids, loc, house_number="<script>")).status_code == 400
    assert a.post("/api/listings", json=listing_payload(ids[:2], loc)).status_code == 400


def test_daily_listing_quota(two_hosts):
    a, _ = two_hosts
    for i in range(5):
        assert publish(a, [10 * i + 1, 10 * i + 2, 10 * i + 3], house_number=str(i + 1)).status_code == 201
    assert publish(a, [91, 92, 93], house_number="99").status_code == 429


# ------------------------------------------------------------------- upload abusif
@pytest.mark.parametrize("raw", [b"<?php system($_GET['c']); ?>", b"\x89PNG\r\n\x1a\n" + b"\x00" * 64,
                                 b"<svg onload=alert(1)>", b"GIF89a;<script>alert(1)</script>"])
def test_malicious_files_rejected(two_hosts, raw):
    a, _ = two_hosts
    assert upload(a, raw=raw, name="x.jpg").status_code == 422


def test_polyglot_jpeg_is_reencoded(two_hosts, app):
    a, _ = two_hosts
    raw = jpeg(render_house(3)) + b"<script>alert(1)</script>"  # charge utile en fin de JPEG
    r = upload(a, raw=raw)
    assert r.status_code == 201
    stored = a.get(r.json["url"]).data
    assert b"<script>" not in stored
    assert a.get(r.json["url"]).headers["Content-Security-Policy"] == "default-src 'none'"


def test_oversized_body_rejected(two_hosts):
    a, _ = two_hosts
    assert upload(a, raw=b"\xff\xd8" + b"0" * 5_000_000).status_code == 413


@pytest.mark.parametrize("name", ["../../etc/passwd", "..%2f..%2fapp.py", "x.jpg/../../app.py", "a" * 32 + ".jpg.."])
def test_path_traversal_on_uploads(client, name):
    r = client.get(f"/uploads/{name}")
    assert r.status_code == 404 and b"root:" not in r.data and b"create_app" not in r.data


# ---------------------------------------------------------------------- injections
@pytest.mark.parametrize("qs", ["city=Kinshasa'%20OR%20'1'='1", "q=%25'%3B%20DROP%20TABLE%20users%3B--",
                                "sort=price%3B%20DROP%20TABLE%20users", "min_price=1%20OR%201=1", "limit=-1",
                                "offset=99999999999", "bedrooms=nan", "q=%5C%25%5C_"])
def test_sql_injection_in_filters(two_hosts, new_client, qs):
    a, _ = two_hosts
    publish(a, [1, 2, 3])
    r = new_client().get(f"/api/listings?{qs}")
    assert r.status_code in (200, 400)
    if r.status_code == 200:
        assert r.json["total"] in (0, 1)
    assert new_client().get("/api/listings").json["total"] == 1  # table intacte


def test_stored_xss_payload_is_inert_json(two_hosts, new_client):
    a, _ = two_hosts
    lid = publish(a, [1, 2, 3], title="<img src=x onerror=alert(1)> Villa").json["id"]
    r = new_client().get(f"/api/listings/{lid}")
    assert r.mimetype == "application/json" and r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.json["title"].startswith("<img")  # stocké tel quel ; le front l'échappe (voir test e2e)


# ------------------------------------------------------------- avis / signalements
def test_review_requires_inquiry_and_one_per_user(two_hosts, new_client):
    a, _ = two_hosts
    lid = publish(a, [1, 2, 3]).json["id"]
    c = new_client()
    register(c, "c@x.cd", "client")
    assert c.post(f"/api/listings/{lid}/reviews", json={"rating": 5, "comment": "Excellent bien !"}).status_code == 403
    assert c.post(f"/api/listings/{lid}/conversation", json={"message": "Bonjour, toujours disponible ?"}).status_code == 201
    assert c.post(f"/api/listings/{lid}/reviews", json={"rating": 9, "comment": "Excellent bien !"}).status_code == 400
    assert c.post(f"/api/listings/{lid}/reviews", json={"rating": True, "comment": "Excellent bien !"}).status_code == 400
    assert c.post(f"/api/listings/{lid}/reviews", json={"rating": 5, "comment": "Excellent bien !"}).status_code == 201
    assert c.post(f"/api/listings/{lid}/reviews", json={"rating": 5, "comment": "Encore 5 étoiles !"}).status_code == 409


def test_host_cannot_review_or_report_own_listing(two_hosts):
    a, _ = two_hosts
    lid = publish(a, [1, 2, 3]).json["id"]
    assert a.post(f"/api/listings/{lid}/reviews", json={"rating": 5, "comment": "Mon bien est top"}).status_code == 403
    assert a.post(f"/api/listings/{lid}/report", json={"reason": "test"}).status_code == 404


def test_three_reports_hide_listing(two_hosts, new_client):
    a, _ = two_hosts
    lid = publish(a, [1, 2, 3]).json["id"]
    for i in range(3):
        c = new_client()
        register(c, f"r{i}@x.cd")
        assert c.post(f"/api/listings/{lid}/report", json={"reason": "Photos volées"}).status_code == 200
        assert c.post(f"/api/listings/{lid}/report", json={"reason": "encore"}).status_code in (409, 404)
    assert new_client().get(f"/api/listings/{lid}").status_code == 404


def test_inquiry_date_validation(two_hosts, new_client):
    a, _ = two_hosts
    lid = publish(a, [1, 2, 3]).json["id"]
    c = new_client()
    register(c, "c@x.cd")
    for d in ("2001-01-01", "pas-une-date", "9999-12-31"):
        assert c.post(f"/api/listings/{lid}/conversation", json={"message": "Bonjour visite ?", "date": d}).status_code == 400


# ------------------------------------------------------------------------- modération
def test_admin_moderation_flow(two_hosts, new_client, keys):
    from conftest import id_token
    a, _ = two_hosts
    lid = publish(a, [1, 2, 3]).json["id"]
    assert a.post(f"/api/admin/listings/{lid}/decision", json={"action": "approve"}).status_code == 403
    assert a.post("/api/admin/users/1/verify").status_code == 403
    assert a.post("/api/admin/demo", json={"source": "illustrations"}).status_code == 403
    boss = new_client()
    n = boss.get("/api/auth/nonce").json["nonce"]
    boss.post("/api/auth/oauth/google", json={"credential": id_token(keys, nonce=n, email="boss@ndaku.test", sub="b"), "nonce": n})
    r = boss.post("/api/admin/demo", json={"source": "illustrations"})
    assert r.status_code == 200 and len(r.json["created"]) == 3
    _ = io


def test_owner_cannot_delete_listing_under_moderation(two_hosts):
    """Sinon un fraudeur signalé efface l'annonce, libère ses photos volées et republie aussitôt."""
    a, b = two_hosts
    lid = publish(a, [1, 2, 3]).json["id"]
    from conftest import DB
    from ndaku.db import pool
    with pool(DB).connection() as con:
        con.execute("UPDATE listings SET status='pending' WHERE id=%s", (lid,))
    assert a.delete(f"/api/listings/{lid}").status_code == 400
    assert upload(b, 1).status_code == 422  # les photos restent bannies


def test_boolean_image_ids_and_contact_in_address(two_hosts):
    a, _ = two_hosts
    ids = [upload(a, s).json["id"] for s in (1, 2, 3)]
    loc = avenue(a)
    assert a.post("/api/listings", json=listing_payload([True, 2, 3], loc)).status_code == 400
    assert a.post("/api/listings", json=listing_payload(ids, loc, house_number="0812345678")).status_code == 400


def test_demo_import_skips_failures_and_continues(app, monkeypatch, client):
    from ndaku import demo
    calls = []

    def fake_candidates(city, want):
        calls.append(city)
        return []  # aucune photo libre trouvée pour aucune ville
    monkeypatch.setattr(demo, "commons_candidates", fake_candidates)
    with app.test_request_context():
        res = demo.create_demo(app.config["STORAGE"], source="commons", max_listings=3)
        from ndaku.db import close
        close(None)
    assert res["done"] and not res["created"] and len(res["skipped"]) == len(demo.LISTINGS)
    assert set(calls) == {x[0] for x in demo.LISTINGS}  # toutes les villes tentées, pas seulement les 3 premières


def test_private_blob_store_photos_served_via_media(app, client, monkeypatch):
    """Store Vercel Blob privé : photo écrite en privé, servie par /media/ avec cache CDN, noms validés."""
    import vercel.blob.sync as vb
    store = {}

    class Res:
        def __init__(self, body):
            self.body = body

    def get(path, access):
        if path not in store:
            raise vb.BlobNotFoundError("absent")
        return Res(store[path][0])
    monkeypatch.setattr(vb, "put_blob", lambda path, body, **kw: store.update({path: (bytes(body), kw["access"])}))
    monkeypatch.setattr(vb, "get_blob", get)
    monkeypatch.setattr(vb, "delete_blob", lambda keys: [store.pop(k, None) for k in keys])
    register(client, "h@x.cd", "host")  # avatar stocké en local avant de basculer sur le store privé
    st = app.config["STORAGE"]
    st.blob, st.cfg.BLOB_ACCESS = True, "private"
    r = upload(client, 1)
    assert r.status_code == 201 and r.json["url"].startswith("/media/")
    assert all(acc == "private" for _, acc in store.values())
    img = client.get(r.json["url"])
    assert img.status_code == 200 and img.mimetype == "image/jpeg" and "immutable" in img.headers["Cache-Control"]
    assert "Set-Cookie" not in img.headers
    for bad in ("../secret.jpg", "x" * 32 + ".png", "listings%2F" + "a" * 32 + ".jpg"):
        assert client.get(f"/media/{bad}").status_code == 404
    assert client.delete(f"/api/uploads/{r.json['id']}").status_code == 200 and not store


def test_vercel_without_blob_starts_and_refuses_uploads_cleanly(app):  # fixture app : base remise à zéro
    """Disque Vercel en lecture seule : l'app doit démarrer sans store Blob et répondre 503 aux uploads."""
    from conftest import DB, Client
    from ndaku import create_app
    vapp = create_app(DATABASE_URL=DB, ON_VERCEL=True, BLOB_TOKEN=None, LOCAL_UPLOADS="/proc/interdit",
                     REQUIRE_EMAIL_VERIFICATION=False)
    c = Client(vapp)
    register(c, "h@x.cd", "host", avatar=False)
    assert c.post("/api/auth/me/avatar", data={"image": (io.BytesIO(jpeg(render_house(9))), "a.jpg")},
                  content_type="multipart/form-data").status_code == 503
    from ndaku.db import pool
    with pool(DB).connection() as con:
        con.execute("UPDATE users SET avatar_url='/media/a/' || repeat('a', 32) || '.jpg'")
    r = upload(c, 1)
    assert r.status_code == 503 and "Blob" in r.json["error"]


@pytest.mark.parametrize("env,mode", [
    ({"BLOB_STORE_ID": "store_abc123"}, "blob-oidc"),                       # stores récents (OIDC)
    ({"BLOB_READ_WRITE_TOKEN": "vercel_blob_rw_abc_secret"}, "blob-token"),  # anciens stores
    ({"NDAKU_READ_WRITE_TOKEN": "vercel_blob_rw_abc_secret"}, "blob-token"),  # préfixe personnalisé
    ({}, "none"),
])
def test_blob_store_detection_on_vercel(monkeypatch, env, mode):
    from ndaku.config import Config
    from ndaku.storage import Storage
    for k in ("BLOB_STORE_ID", "BLOB_READ_WRITE_TOKEN", "VERCEL_BLOB_READ_WRITE_TOKEN"):
        monkeypatch.setenv(k, "")  # enregistre l'état d'origine : Storage() y recopie des valeurs, restaurées ensuite
        monkeypatch.delenv(k)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x@localhost/x")
    assert Storage(Config()).mode == mode
