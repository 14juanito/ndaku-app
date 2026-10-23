"""v5 : scores courant/eau/accès, alertes, agenda de visites, avis hôtes, vérification d'identité,
notifications, statistiques, prix du marché."""
import io
import threading
from datetime import datetime, timedelta, timezone

import pytest

from conftest import DB, avatar_bytes, id_token, listing_payload, publish, register, upload, avenue
from ndaku import notify as notify_mod
from ndaku.db import pool


def sql(q, args=()):
    with pool(DB).connection() as con:
        cur = con.execute(q, args)
        return cur.fetchall() if cur.description else None


def admin(new_client, keys):
    boss = new_client()
    n = boss.get("/api/auth/nonce").json["nonce"]
    r = boss.post("/api/auth/oauth/google",
                  json={"credential": id_token(keys, nonce=n, email="boss@ndaku.test", sub="boss"), "nonce": n})
    assert r.status_code in (200, 201), r.json
    return boss


@pytest.fixture()
def world(client, new_client):
    host, cl, intruder = client, new_client(), new_client()
    register(host, "host@x.cd", "host")
    lid = publish(host, [1, 2, 3], house_number="12").json["id"]
    register(cl, "client@x.cd", "client")
    register(intruder, "intrus@x.cd", "client")
    return host, cl, intruder, lid


def iso(hours):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


# ------------------------------------------------------------------ scores et filtres
def test_scores_required_and_validated(client):
    register(client, "h@x.cd", "host")
    ids = [upload(client, s).json["id"] for s in (11, 12, 13)]
    loc = avenue(client)
    for bad in ({"elec_score": 0}, {"water_score": 11}, {"access_score": "7.5"}, {"elec_score": True},
                {"access_type": "autoroute"}, {"rain_access": "oui"}, {"elec_score": None}):
        r = client.post("/api/listings", json=listing_payload(ids, loc, **bad))
        assert r.status_code == 400, bad
    r = client.post("/api/listings", json=listing_payload(ids, loc, elec_score="4"))
    assert r.status_code == 201, r.json
    d = client.get(f"/api/listings/{r.json['id']}").json
    assert (d["elec_score"], d["water_score"], d["access_score"], d["access_type"], d["rain_access"]) == \
        (4, 8, 6, "goudron", True)


def test_score_filters(world, client):
    _, cl, _, lid = world
    assert [x["id"] for x in cl.get("/api/listings?min_elec=7").json["items"]] == [lid]
    assert cl.get("/api/listings?min_elec=8").json["items"] == []
    assert cl.get("/api/listings?min_water=11").status_code == 400
    assert cl.get("/api/listings?min_access=abc").status_code == 400


# ----------------------------------------------------------------------- alertes
def test_alert_match_notifies_once_and_is_private(world, new_client):
    host, cl, intruder, _ = world
    cid = sql("SELECT commune_id FROM listings LIMIT 1")[0]["commune_id"]
    assert cl.post("/api/alerts", json={}).status_code == 400  # aucun critère
    a = cl.post("/api/alerts", json={"label": "3 ch. Gombe", "commune_id": cid, "max_price": 900, "bedrooms": 3,
                                     "min_elec": 5}).json["id"]
    cl.post("/api/alerts", json={"commune_id": cid, "max_price": 500})  # ne correspond pas (prix)
    assert intruder.delete(f"/api/alerts/{a}").status_code == 404  # IDOR
    assert intruder.get("/api/alerts").json["items"] == []
    lid = publish(host, [4, 5, 6], "Avenue Deux", house_number="3").json["id"]
    notes = cl.get("/api/notifications").json["items"]
    assert [n["link"] for n in notes] == [f"#/listing/{lid}"]
    assert host.get("/api/notifications").json["items"] == [] or \
        all(n["kind"] != "alert" for n in host.get("/api/notifications").json["items"])
    # Une re-modération ne renvoie pas l'alerte
    from ndaku.services import match_alerts
    with host.c.application.test_request_context():
        assert match_alerts(lid) == 0
    assert cl.get("/api/auth/me").json["user"]["notif_unread"] == 1
    cl.post("/api/notifications/read")
    assert cl.get("/api/auth/me").json["user"]["notif_unread"] == 0


def test_alert_limit(world):
    _, cl, _, _ = world
    for i in range(10):
        assert cl.post("/api/alerts", json={"deal": "vente", "max_price": 1000 + i}).status_code == 201
    assert cl.post("/api/alerts", json={"deal": "vente"}).status_code == 400


# ----------------------------------------------------------------- agenda de visites
def test_slots_owner_only_and_validation(world):
    host, cl, _, lid = world
    assert cl.post(f"/api/listings/{lid}/slots", json={"starts": [iso(24)]}).status_code in (403, 404)
    assert host.post(f"/api/listings/{lid}/slots", json={"starts": ["2026-13-01T10:00"]}).status_code == 400
    assert host.post(f"/api/listings/{lid}/slots", json={"starts": ["2030-01-01T10:00:00"]}).status_code == 400  # sans fuseau
    assert host.post(f"/api/listings/{lid}/slots", json={"starts": [iso(0.1)]}).status_code == 400  # trop tôt
    assert host.post(f"/api/listings/{lid}/slots", json={"starts": [iso(24 * 100)]}).status_code == 400
    assert host.post(f"/api/listings/{lid}/slots", json={"starts": [iso(24)] * 21}).status_code == 400
    r = host.post(f"/api/listings/{lid}/slots", json={"starts": [iso(24), iso(26)], "duration": 45})
    assert r.status_code == 201 and r.json["created"] == 2


def test_booking_flow_and_privacy(world, new_client):
    host, cl, intruder, lid = world
    host.post(f"/api/listings/{lid}/slots", json={"starts": [iso(24), iso(26)]})
    s1, s2 = [s["id"] for s in cl.get(f"/api/listings/{lid}/slots").json["items"]]
    assert host.post(f"/api/slots/{s1}/book").status_code == 404  # l'hôte ne réserve pas chez lui
    r = cl.post(f"/api/slots/{s1}/book", json={"message": "J'arrive avec mon épouse."})
    assert r.status_code == 200, r.json
    conv = cl.get(f"/api/conversations/{r.json['conversation_id']}").json
    assert conv["messages"][-1]["kind"] == "visit"
    assert cl.post(f"/api/slots/{s2}/book").status_code == 409  # une seule visite active par bien
    assert intruder.post(f"/api/slots/{s1}/book").status_code == 409  # déjà pris
    # Les autres clients ne voient pas le créneau réservé ; l'hôte voit qui l'a pris
    assert [s["id"] for s in intruder.get(f"/api/listings/{lid}/slots").json["items"]] == [s2]
    hs = {s["id"]: s for s in host.get(f"/api/listings/{lid}/slots").json["items"]}
    assert hs[s1]["booker"] == "Test User" and "booker" not in hs[s2]
    assert any(n["kind"] == "visit" for n in host.get("/api/notifications").json["items"])
    # Un intrus ne peut pas annuler la réservation d'un autre
    assert intruder.post(f"/api/slots/{s1}/cancel").status_code == 404
    assert cl.post(f"/api/slots/{s1}/cancel").status_code == 200
    assert intruder.post(f"/api/slots/{s1}/book").status_code == 200  # le créneau est redevenu libre
    # L'hôte annule : le client est prévenu, le créneau disparaît
    assert host.post(f"/api/slots/{s1}/cancel").status_code == 200
    assert s1 not in [s["id"] for s in cl.get(f"/api/listings/{lid}/slots").json["items"]]
    assert any(n["kind"] == "visit" for n in intruder.get("/api/notifications").json["items"])


def test_booking_race_single_winner(world, new_client):
    host, _, _, lid = world
    host.post(f"/api/listings/{lid}/slots", json={"starts": [iso(30)]})
    sid = host.get(f"/api/listings/{lid}/slots").json["items"][0]["id"]
    clients = []
    for i in range(6):
        c = new_client()
        register(c, f"race{i}@x.cd", "client")
        clients.append(c)
    codes = []
    ths = [threading.Thread(target=lambda c=c: codes.append(c.post(f"/api/slots/{sid}/book").status_code))
           for c in clients]
    [t.start() for t in ths]
    [t.join() for t in ths]
    assert sorted(codes) == [200] + [409] * 5
    assert sql("SELECT COUNT(*)::int AS n FROM messages WHERE kind='visit'")[0]["n"] == 1


def test_same_client_two_slots_race(world):
    host, cl, _, lid = world
    host.post(f"/api/listings/{lid}/slots", json={"starts": [iso(30), iso(32)]})
    ids = [s["id"] for s in cl.get(f"/api/listings/{lid}/slots").json["items"]]
    codes = []
    ths = [threading.Thread(target=lambda s=s: codes.append(cl.post(f"/api/slots/{s}/book").status_code)) for s in ids]
    [t.start() for t in ths]
    [t.join() for t in ths]
    assert sorted(codes) == [200, 409]


# ----------------------------------------------------------------------- avis hôtes
def test_host_review_requires_conversation_once(world):
    host, cl, intruder, lid = world
    hid = sql("SELECT owner_id FROM listings WHERE id=%s", (lid,))[0]["owner_id"]
    review = {"rating": 5, "comment": "Hôte ponctuel et très honnête."}
    assert intruder.post(f"/api/hosts/{hid}/reviews", json=review).status_code == 403
    assert host.post(f"/api/hosts/{hid}/reviews", json=review).status_code == 403  # s'auto-noter
    cl.post(f"/api/listings/{lid}/conversation", json={"message": "Bonjour, est-ce disponible ?"})
    assert cl.get(f"/api/hosts/{hid}").json["can_review"] is True
    assert cl.post(f"/api/hosts/{hid}/reviews", json={"rating": 6, "comment": "x" * 20}).status_code == 400
    assert cl.post(f"/api/hosts/{hid}/reviews", json=review).status_code == 201
    assert cl.post(f"/api/hosts/{hid}/reviews", json=review).status_code == 200  # modification, pas de doublon
    p = cl.get(f"/api/hosts/{hid}").json
    assert p["rating"] == 5 and p["reviews_count"] == 1 and len(p["listings"]) == 1 and "email" not in p
    assert cl.get(f"/api/listings/{lid}").json["host"]["rating"] == 5
    cid = sql("SELECT id FROM users WHERE email='client@x.cd'")[0]["id"]
    assert cl.get(f"/api/hosts/{cid}").status_code == 404  # un client n'a pas de profil d'hôte


# ---------------------------------------------------------------- vérification d'identité
def kyc(c, id_type="electeur"):
    return c.post("/api/verification", data={"id_type": id_type, "id_doc": (io.BytesIO(avatar_bytes((10, 90, 30))), "id.jpg"),
                                             "selfie": (io.BytesIO(avatar_bytes()), "s.jpg")},
                  content_type="multipart/form-data")


def test_kyc_documents_admin_only_and_erased(world, new_client, keys):
    host, cl, _, _ = world
    assert kyc(cl).status_code == 403  # réservé aux hôtes
    assert kyc(host, "faux").status_code == 400
    assert kyc(host).status_code == 201
    assert kyc(host).status_code == 409  # une demande à la fois
    vid = sql("SELECT id FROM id_verifications")[0]["id"]
    for c in (host, cl):
        assert c.get(f"/api/admin/verifications/{vid}/id_doc").status_code in (403, 404)
        assert c.get("/api/admin/verifications").status_code in (403, 404)
    boss = admin(new_client, keys)
    assert boss.get(f"/api/admin/verifications/{vid}/passwd").status_code == 404
    r = boss.get(f"/api/admin/verifications/{vid}/selfie")
    assert r.status_code == 200 and r.mimetype == "image/jpeg" and r.headers["Cache-Control"] == "no-store"
    assert sql("SELECT 1 FROM security_events WHERE event='kyc_viewed'")
    assert boss.post(f"/api/admin/verifications/{vid}/decision", json={"action": "approve"}).status_code == 200
    row = sql("SELECT id_doc, selfie, status FROM id_verifications WHERE id=%s", (vid,))[0]
    assert row == {"id_doc": None, "selfie": None, "status": "approved"}
    assert boss.get(f"/api/admin/verifications/{vid}/selfie").status_code == 404
    assert host.get("/api/auth/me").json["user"]["verified"] is True
    assert kyc(host).status_code == 400  # déjà vérifié


def test_kyc_rejects_non_images(world):
    host = world[0]
    r = host.post("/api/verification", data={"id_type": "passeport", "id_doc": (io.BytesIO(b"%PDF-1.4 x"), "a.jpg"),
                                             "selfie": (io.BytesIO(avatar_bytes()), "s.jpg")},
                  content_type="multipart/form-data")
    assert r.status_code == 422


# ------------------------------------------------------------------- notifications
def test_notifications_private_and_throttled(world, monkeypatch):
    host, cl, intruder, lid = world
    sent = []
    monkeypatch.setattr(notify_mod.mailer, "send", lambda cfg, to, subj, text: sent.append((to, subj, text)))
    cid = cl.post(f"/api/listings/{lid}/conversation", json={"message": "Bonjour, code secret 4242 ?"}).json["id"]
    for _ in range(3):
        cl.post(f"/api/conversations/{cid}/messages", json={"body": "Relance"})
    assert [t for t, _, _ in sent] == ["host@x.cd"]  # une seule notification en 10 min
    assert "4242" not in sent[0][2]  # le contenu privé ne sort pas de Ndaku
    assert intruder.get("/api/notifications").json["items"] == []
    intruder.post("/api/notifications/read")
    assert host.get("/api/auth/me").json["user"]["notif_unread"] == 1


def test_sms_requires_verified_phone(world, app, monkeypatch):
    _, cl, _, _ = world
    assert cl.patch("/api/auth/me", json={"notify": {"sms": True}}).status_code == 400
    assert cl.patch("/api/auth/me", json={"notify": {"email": "yes"}}).status_code == 400
    r = cl.patch("/api/auth/me", json={"notify": {"email": False}})
    assert r.json["user"]["notify"] == {"email": False, "sms": False, "whatsapp": False}
    cfg = app.config["NDAKU"]
    monkeypatch.setattr(cfg, "TWILIO_ACCOUNT_SID", "AC1", raising=False)
    monkeypatch.setattr(cfg, "TWILIO_AUTH_TOKEN", "t", raising=False)
    monkeypatch.setattr(cfg, "TWILIO_FROM", "+15550000", raising=False)
    codes = []
    monkeypatch.setattr(notify_mod, "_twilio", lambda to, text, whatsapp=False: codes.append((to, text)) or True)
    assert cl.post("/api/auth/me/phone/code").status_code == 400  # pas de numéro
    cl.patch("/api/auth/me", json={"phone": "0812345678"})
    assert cl.post("/api/auth/me/phone/code").status_code == 200
    to, txt = codes[-1]
    code = txt.split("est ")[1][:6]
    assert to == "+243812345678"
    assert cl.post("/api/auth/me/phone/verify", json={"code": "000000" if code != "000000" else "111111"}).status_code == 400
    assert cl.post("/api/auth/me/phone/verify", json={"code": code}).json["user"]["phone_verified"] is True
    assert cl.patch("/api/auth/me", json={"notify": {"sms": True}}).json["user"]["notify"]["sms"] is True
    # Changer de numéro coupe les SMS et retire la vérification
    u = cl.patch("/api/auth/me", json={"phone": "0899999999"}).json["user"]
    assert u["phone_verified"] is False and u["notify"]["sms"] is False


def test_phone_code_bruteforce_limited(world, app, monkeypatch):
    _, cl, _, _ = world
    cfg = app.config["NDAKU"]
    for k, v in (("TWILIO_ACCOUNT_SID", "AC1"), ("TWILIO_AUTH_TOKEN", "t"), ("TWILIO_FROM", "+1555")):
        monkeypatch.setattr(cfg, k, v, raising=False)
    monkeypatch.setattr(notify_mod, "_twilio", lambda *a, **k: True)
    cl.patch("/api/auth/me", json={"phone": "0812345678"})
    cl.post("/api/auth/me/phone/code")
    codes = [cl.post("/api/auth/me/phone/verify", json={"code": f"{i:06d}"}).status_code for i in range(7)]
    assert codes[-1] == 429


# ------------------------------------------------------------------------- statistiques
def test_views_counted_once_per_day_not_for_owner(world, new_client):
    host, cl, intruder, lid = world
    for c in (cl, cl, intruder, host):
        c.get(f"/api/listings/{lid}")
    st = host.get("/api/my/stats").json
    assert st["items"][0]["views"] == 2
    assert cl.get("/api/my/stats").status_code == 403
    assert cl.get(f"/api/listings/{lid}").json["views"] is None  # chiffre réservé à l'hôte


def test_price_stats(world, client):
    host, cl, _, lid = world
    cid = sql("SELECT commune_id, city_id FROM listings WHERE id=%s", (lid,))[0]
    r = cl.get(f"/api/stats/prices?city_id={cid['city_id']}&deal=location").json
    assert r["current"]["n"] == 1 and r["current"]["median"] == 800
    assert cl.get("/api/stats/prices").status_code == 400
    assert cl.get("/api/stats/prices?commune_id=x").status_code == 400
