"""Tests d'attaque sur les annonces : IDOR, contournement anti-fraude, injections, upload, XSS stocké."""
import io

import pytest
from PIL import ImageOps

from conftest import jpeg, listing_payload, publish, register, upload
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
    assert client.post("/api/listings", json=listing_payload([1, 2, 3])).status_code == 403


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
    r = b.post("/api/listings", json=listing_payload(ids, address="Avenue B 2"))
    assert r.status_code == 400
    assert b.delete(f"/api/uploads/{ids[0]}").status_code == 404


def test_cannot_reuse_photos_already_attached(two_hosts):
    a, _ = two_hosts
    ids = [upload(a, s).json["id"] for s in (1, 2, 3)]
    assert a.post("/api/listings", json=listing_payload(ids)).status_code == 201
    r = a.post("/api/listings", json=listing_payload(ids, address="Autre adresse 9"))
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
    r = a.post("/api/listings", json=listing_payload(ids, status="active", risk_score=-999, owner_id=999, is_demo=True))
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
    r = publish(b, [4, 5, 6], address="  avenue TEST 1 ")  # normalisation : casse/espaces
    assert r.status_code == 409


def test_contact_info_and_unrealistic_values_blocked(two_hosts):
    a, _ = two_hosts
    ids = [upload(a, s).json["id"] for s in (1, 2, 3)]
    assert a.post("/api/listings", json=listing_payload(ids, description="Appelez le 0812345678 " + "x" * 60)).status_code == 400
    assert a.post("/api/listings", json=listing_payload(ids, price=1)).status_code == 400
    assert a.post("/api/listings", json=listing_payload(ids, bedrooms=10, surface=40)).status_code == 400
    assert a.post("/api/listings", json=listing_payload(ids, city="Paris")).status_code == 400
    assert a.post("/api/listings", json=listing_payload(ids[:2])).status_code == 400


def test_daily_listing_quota(two_hosts):
    a, _ = two_hosts
    for i in range(5):
        assert publish(a, [10 * i + 1, 10 * i + 2, 10 * i + 3], address=f"Avenue Q {i}").status_code == 201
    assert publish(a, [91, 92, 93], address="Avenue Q 9").status_code == 429


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
    assert c.post(f"/api/listings/{lid}/inquiries", json={"message": "Bonjour, toujours disponible ?"}).status_code == 201
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


def test_host_phone_only_visible_to_concerned_host(two_hosts, new_client):
    a, b = two_hosts
    lid = publish(a, [1, 2, 3]).json["id"]
    c = new_client()
    c.post("/api/auth/register", json={"name": "Client", "email": "c@x.cd", "password": "Kinshasa-2026x",
                                       "role": "client", "phone": "+243 800 000 000"})
    c.post(f"/api/listings/{lid}/inquiries", json={"message": "Bonjour, je voudrais visiter."})
    assert a.get("/api/my/inquiries").json["items"][0]["who_phone"] == "+243 800 000 000"
    assert b.get("/api/my/inquiries").json["items"] == []


def test_inquiry_date_validation(two_hosts, new_client):
    a, _ = two_hosts
    lid = publish(a, [1, 2, 3]).json["id"]
    c = new_client()
    register(c, "c@x.cd")
    for d in ("2001-01-01", "pas-une-date", "9999-12-31"):
        assert c.post(f"/api/listings/{lid}/inquiries", json={"message": "Bonjour visite ?", "preferred_date": d}).status_code == 400


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
