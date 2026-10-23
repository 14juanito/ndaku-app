"""v3 : messagerie, adresse exacte, référentiel géographique, photo de profil, suspension, cache CDN, OSM."""
import io

import pytest
from psycopg.errors import UniqueViolation

from conftest import DB, avenue, commune_id, id_token, jpeg, listing_payload, publish, register, upload
from ndaku import osm
from ndaku.db import pool
from ndaku.demo import render_house


def sql(q, args=()):
    with pool(DB).connection() as con:
        cur = con.execute(q, args)
        return cur.fetchall() if cur.description else None


@pytest.fixture()
def world(client, new_client):
    """Un hôte avec une annonce, un client, un intrus."""
    host, cl, intruder = client, new_client(), new_client()
    register(host, "host@x.cd", "host")
    lid = publish(host, [1, 2, 3], house_number="12").json["id"]
    register(cl, "client@x.cd", "client", phone="+243 811 111 111")
    register(intruder, "intrus@x.cd", "client")
    return host, cl, intruder, lid


def start(c, lid, msg="Bonjour, je souhaite visiter ce bien.", **kw):
    return c.post(f"/api/listings/{lid}/conversation", json={"message": msg, **kw})


# ------------------------------------------------------------------- messagerie
def test_conversation_idor(world, app, keys, new_client):
    host, cl, intruder, lid = world
    cid = start(cl, lid).json["id"]
    for method, path, body in (("get", f"/api/conversations/{cid}", None),
                               ("post", f"/api/conversations/{cid}/messages", {"body": "coucou"}),
                               ("post", f"/api/conversations/{cid}/share-contact", {"email": True}),
                               ("post", f"/api/conversations/{cid}/block", {}),
                               ("post", f"/api/conversations/{cid}/report", {"category": "arnaque"})):
        r = getattr(intruder, method)(path, json=body) if body is not None else getattr(intruder, method)(path)
        assert r.status_code == 404, (path, r.json)
    assert intruder.get("/api/conversations").json["items"] == []
    # La modération elle-même ne lit pas une conversation non signalée.
    boss = new_client()
    n = boss.get("/api/auth/nonce").json["nonce"]
    boss.post("/api/auth/oauth/google", json={"credential": id_token(keys, nonce=n, email="boss@ndaku.test", sub="b"), "nonce": n})
    assert boss.get(f"/api/conversations/{cid}").status_code == 404


def test_visit_request_reuses_conversation_and_rules(world):
    host, cl, _, lid = world
    a, b = start(cl, lid).json["id"], start(cl, lid, "Je relance ma demande.").json["id"]
    assert a == b and len(cl.get(f"/api/conversations/{a}").json["messages"]) == 2
    assert start(host, lid).status_code == 400  # sa propre annonce
    assert start(cl, lid, "x").status_code == 400  # message vide/trop court
    assert start(cl, 999999).status_code == 404


def test_avatar_required_to_write(world, new_client):
    _, _, _, lid = world
    c = new_client()
    register(c, "noface@x.cd", avatar=False)
    r = start(c, lid)
    assert r.status_code == 403 and "photo" in r.json["error"]


def test_payment_warning_only_for_recipient(world):
    host, cl, _, lid = world
    cid = start(cl, lid).json["id"]
    host.post(f"/api/conversations/{cid}/messages", json={"body": "Envoyez d'abord un acompte par M-Pesa svp"})
    mine = host.get(f"/api/conversations/{cid}").json["messages"][-1]
    theirs = cl.get(f"/api/conversations/{cid}").json["messages"][-1]
    assert mine["warn"] is False and theirs["warn"] is True


def test_contact_sharing_is_explicit_and_own_data_only(world):
    host, cl, intruder, lid = world
    cid = start(cl, lid).json["id"]
    assert cl.post(f"/api/conversations/{cid}/share-contact", json={}).status_code == 400
    r = cl.post(f"/api/conversations/{cid}/share-contact", json={"phone": True, "email": True, "user_id": 1})
    assert r.status_code == 201
    last = host.get(f"/api/conversations/{cid}").json["messages"][-1]
    assert last["kind"] == "contact" and "+243 811 111 111" in last["body"] and "client@x.cd" in last["body"]
    # Le téléphone n'apparaît nulle part ailleurs
    assert "811" not in str(host.get(f"/api/listings/{lid}").json) and "811" not in str(intruder.get("/api/auth/me").json)


def test_block_stops_messages(world):
    host, cl, _, lid = world
    cid = start(cl, lid).json["id"]
    assert host.post(f"/api/conversations/{cid}/block", json={}).status_code == 200
    assert cl.post(f"/api/conversations/{cid}/messages", json={"body": "allo ?"}).status_code == 403
    assert start(cl, lid).status_code == 403
    # Seul celui qui a bloqué peut débloquer
    cl.post(f"/api/conversations/{cid}/block", json={"unblock": True})
    assert cl.post(f"/api/conversations/{cid}/messages", json={"body": "allo ?"}).status_code == 403
    host.post(f"/api/conversations/{cid}/block", json={"unblock": True})
    assert cl.post(f"/api/conversations/{cid}/messages", json={"body": "allo ?"}).status_code == 201


def test_unread_counter(world):
    host, cl, _, lid = world
    cid = start(cl, lid).json["id"]
    assert host.get("/api/auth/me").json["user"]["unread"] == 1
    host.get(f"/api/conversations/{cid}")
    assert host.get("/api/auth/me").json["user"]["unread"] == 0


def test_stored_xss_in_messages_is_inert_json(world):
    host, cl, _, lid = world
    cid = start(cl, lid, "<img src=x onerror=alert(1)> bonjour").json["id"]
    r = host.get(f"/api/conversations/{cid}")
    assert r.mimetype == "application/json" and r.json["messages"][0]["body"].startswith("<img")


# ------------------------------------------------------------- adresse exacte / carte
def test_exact_address_only_after_contact(world, new_client):
    host, cl, intruder, lid = world
    pub = new_client().get(f"/api/listings/{lid}").json
    assert pub["address"] is None and pub["exact_location"] is False and "12" not in pub["street"]
    assert pub["lat"] == round(pub["lat"], 3)
    assert intruder.get(f"/api/listings/{lid}").json["address"] is None
    start(cl, lid)
    seen = cl.get(f"/api/listings/{lid}").json
    assert seen["exact_location"] and "n° 12" in seen["address"] and seen["lat"] == -4.30
    assert host.get(f"/api/listings/{lid}").json["address"]


def test_map_points_and_bbox(world, new_client):
    _, _, _, lid = world
    c = new_client()
    pts = c.get("/api/listings/map?bbox=-5,15,-4,16").json["items"]
    assert [p["id"] for p in pts] == [lid] and pts[0]["lat"] == round(pts[0]["lat"], 3)
    assert c.get("/api/listings/map?bbox=-1,0,0,1").json["items"] == []
    assert c.get("/api/listings/map?bbox=a,b,c,d").status_code == 400
    assert c.get(f"/api/listings?commune_id={commune_id()}").json["total"] == 1
    assert c.get(f"/api/listings?commune_id={commune_id('Lemba')}").json["total"] == 0
    assert c.get("/api/listings?commune_id=abc").status_code == 400


# --------------------------------------------------------------------- unicité d'adresse
def test_address_unique_index_survives_race(world):
    host, _, _, lid = world
    key = sql("SELECT addr_key FROM listings WHERE id=%s", (lid,))[0]["addr_key"]
    with pytest.raises(UniqueViolation):  # même si deux requêtes passent le contrôle applicatif en même temps
        sql("""INSERT INTO listings (owner_id, title, description, deal, ptype, city, commune, address, price, bedrooms,
                 bathrooms, surface, status, addr_key) SELECT owner_id, title, description, deal, ptype, city, commune,
                 address, price, bedrooms, bathrooms, surface, 'active', addr_key FROM listings WHERE id=%s""", (lid,))
    assert key.endswith("|test|12|")


def test_same_number_different_unit_allowed_for_buildings(client):
    register(client, "h@x.cd", "host")
    assert publish(client, [1, 2, 3], ptype="appartement", house_number="5", unit="Appt 1").status_code == 201
    assert publish(client, [4, 5, 6], ptype="appartement", house_number="5", unit="Appt 2").status_code == 201
    assert publish(client, [7, 8, 9], ptype="appartement", house_number="5", unit="appt  1").status_code == 409


def test_closed_listing_frees_address_but_cannot_reactivate_over_new_one(client):
    register(client, "h@x.cd", "host")
    lid = publish(client, [1, 2, 3]).json["id"]
    client.patch(f"/api/listings/{lid}", json={"status": "closed"})
    assert publish(client, [4, 5, 6]).status_code == 201  # même adresse, l'ancienne est louée
    assert client.patch(f"/api/listings/{lid}", json={"status": "active"}).status_code == 409


# ------------------------------------------------------------------- référentiel
def test_places_cascade_and_cache(client):
    r = client.get("/api/places")
    assert len(r.json["items"]) == 26 and "s-maxage" in r.headers["Cache-Control"]
    kin = next(p for p in r.json["items"] if p["name"] == "Kinshasa")
    city = client.get(f"/api/places?parent_id={kin['id']}").json["items"][0]
    communes = client.get(f"/api/places?parent_id={city['id']}").json["items"]
    assert len(communes) == 24 and {"Gombe", "Ngaliema", "Limete"} <= {c["name"] for c in communes}
    assert client.get("/api/places?parent_id=x").status_code == 400


def test_place_suggestions_rules(client, new_client):
    register(client, "h@x.cd", "host")
    gombe = commune_id()
    prov = sql("SELECT id FROM places WHERE kind='province' LIMIT 1")[0]["id"]
    for body in ({"parent_id": prov, "kind": "avenue", "name": "Avenue X"},       # pas d'avenue sous une province
                 {"parent_id": gombe, "kind": "commune", "name": "Fausse"},        # pas de commune créée par un hôte
                 {"parent_id": gombe, "kind": "avenue", "name": "<script>x</script>"},
                 {"parent_id": gombe, "kind": "avenue", "name": "1234"},
                 {"parent_id": "1", "kind": "avenue", "name": "Avenue Y"}):
        assert client.post("/api/places", json=body).status_code == 400, body
    r = client.post("/api/places", json={"parent_id": gombe, "kind": "quartier", "name": "Quartier Test"})
    assert r.status_code == 201 and r.json["status"] == "pending"
    # Visible par son auteur seulement, jamais dans la liste publique
    assert r.json["id"] not in [p["id"] for p in client.get(f"/api/places?parent_id={gombe}").json["items"]]
    assert r.json["id"] in [p["id"] for p in client.get(f"/api/places/mine?parent_id={gombe}").json["items"]]
    other = new_client()
    register(other, "h2@x.cd", "host")
    assert other.get(f"/api/places/mine?parent_id={gombe}").json["items"] == []
    cl = new_client()
    register(cl, "c@x.cd")
    assert cl.post("/api/places", json={"parent_id": gombe, "kind": "avenue", "name": "Avenue Z"}).status_code == 403


def test_rejected_place_cannot_be_used(client, new_client, keys):
    register(client, "h@x.cd", "host")
    loc = avenue(client, "Avenue Bidon")
    sql("UPDATE places SET status='rejected' WHERE id=%s", (loc["avenue_id"],))
    ids = [upload(client, s).json["id"] for s in (1, 2, 3)]
    r = client.post("/api/listings", json=listing_payload(ids, loc))
    assert r.status_code == 400 and "refusé" in r.json["error"]


def test_pin_far_from_commune_goes_to_moderation(client):
    register(client, "h@x.cd", "host")
    sql("UPDATE users SET verified=TRUE, created_at=now() - interval '30 days'")
    r = publish(client, [1, 2, 3], lat=-11.66, lng=27.48)  # Lubumbashi, pour une maison déclarée à Gombe
    assert r.status_code == 201 and r.json["status"] == "pending"
    assert any("km" in x for x in r.json["reasons"])


# --------------------------------------------------------------------- profil
def test_avatar_validation(client):
    register(client, "a@x.cd", avatar=False)
    bad = [b"<svg onload=alert(1)>", jpeg(render_house(1).resize((100, 100)))]
    for raw in bad:
        r = client.post("/api/auth/me/avatar", data={"image": (io.BytesIO(raw), "a.jpg")}, content_type="multipart/form-data")
        assert r.status_code == 422
    from conftest import set_avatar
    url = set_avatar(client)
    assert url.startswith("/uploads/") and client.get("/api/auth/me").json["user"]["avatar"] == url
    assert client.patch("/api/auth/me", json={"phone": "<b>1</b>"}).status_code == 400
    assert client.patch("/api/auth/me", json={"role": "admin", "name": "Nouveau"}).json["user"]["role"] == "client"


def test_google_picture_only_from_google_cdn(client, new_client, keys):
    for pic, expected in (("https://lh3.googleusercontent.com/a/xyz", True), ("https://evil.example/x.png", False),
                          ("javascript:alert(1)", False)):
        c = new_client()
        n = c.get("/api/auth/nonce").json["nonce"]
        u = c.post("/api/auth/oauth/google", json={"credential": id_token(keys, nonce=n, sub=pic, email=f"{len(pic)}@g.com",
                                                                          picture=pic), "nonce": n}).json["user"]
        assert (u["avatar"] == pic) is expected


# ------------------------------------------------------------------ suspension
def test_suspended_host_is_cut_off(world, new_client, keys):
    host, cl, _, lid = world
    host_id = host.get("/api/auth/me").json["user"]["id"]
    boss = new_client()
    n = boss.get("/api/auth/nonce").json["nonce"]
    boss.post("/api/auth/oauth/google", json={"credential": id_token(keys, nonce=n, email="boss@ndaku.test", sub="b"), "nonce": n})
    assert cl.post(f"/api/admin/users/{host_id}/suspend", json={}).status_code == 403
    assert boss.post(f"/api/admin/users/{host_id}/suspend", json={"suspend": True}).status_code == 200
    assert host.get("/api/auth/me").json["user"] is None
    assert host.post("/api/auth/login", json={"email": "host@x.cd", "password": "Kinshasa-2026x"}).status_code == 403
    assert new_client().get(f"/api/listings/{lid}").status_code == 404
    assert new_client().get("/api/listings").json["total"] == 0
    assert start(cl, lid).status_code == 404
    # un admin ne peut pas être suspendu
    boss_id = boss.get("/api/auth/me").json["user"]["id"]
    assert boss.post(f"/api/admin/users/{boss_id}/suspend", json={}).status_code == 400


# ------------------------------------------------------------- signalements v3
def test_report_categories_and_admin_flow(world, new_client, keys):
    host, cl, _, lid = world
    assert cl.post(f"/api/listings/{lid}/report", json={"category": "pirate"}).status_code == 400
    assert cl.post(f"/api/listings/{lid}/report", json={"category": "autre"}).status_code == 400
    assert cl.post(f"/api/listings/{lid}/report", json={"category": "arnaque"}).status_code == 200
    boss = new_client()
    n = boss.get("/api/auth/nonce").json["nonce"]
    boss.post("/api/auth/oauth/google", json={"credential": id_token(keys, nonce=n, email="boss@ndaku.test", sub="b"), "nonce": n})
    g = boss.get("/api/admin/reports").json["items"]
    assert g[0]["listing_id"] == lid and g[0]["items"][0]["category"] == "arnaque"
    assert boss.post(f"/api/admin/reports/{lid}/close", json={"action": "hide"}).status_code == 200
    assert new_client().get(f"/api/listings/{lid}").status_code == 404


def test_user_report_from_conversation(world, new_client, keys):
    host, cl, _, lid = world
    cid = start(cl, lid).json["id"]
    assert cl.post(f"/api/conversations/{cid}/report", json={"category": "arnaque", "reason": "demande un acompte"}).status_code == 200
    assert cl.post(f"/api/conversations/{cid}/messages", json={"body": "?"}).status_code == 403  # bloquée d'office
    boss = new_client()
    n = boss.get("/api/auth/nonce").json["nonce"]
    boss.post("/api/auth/oauth/google", json={"credential": id_token(keys, nonce=n, email="boss@ndaku.test", sub="b"), "nonce": n})
    items = boss.get("/api/admin/user-reports").json["items"]
    assert items[0]["target"] == "Test User" and items[0]["messages"]


# ------------------------------------------------------------------ avis & compteurs
def test_review_after_conversation_updates_score(world):
    host, cl, _, lid = world
    assert cl.post(f"/api/listings/{lid}/reviews", json={"rating": 5, "comment": "Très bon contact."}).status_code == 403
    start(cl, lid)
    assert cl.post(f"/api/listings/{lid}/reviews", json={"rating": 5, "comment": "Très bon contact."}).status_code == 201
    d = cl.get(f"/api/listings/{lid}").json
    assert d["rating"] == 5 and d["reviews_count"] == 1
    cl.post(f"/api/listings/{lid}/favorite")
    assert sql("SELECT fav_count FROM listings WHERE id=%s", (lid,))[0]["fav_count"] == 1
    cl.post(f"/api/listings/{lid}/favorite")
    assert sql("SELECT fav_count FROM listings WHERE id=%s", (lid,))[0]["fav_count"] == 0


# ----------------------------------------------------------------------- cache CDN
def test_cdn_cache_never_on_personal_data(world):
    host, cl, _, lid = world
    cl.post(f"/api/listings/{lid}/favorite")
    r = cl.get("/api/listings")
    assert "s-maxage" in r.headers["Cache-Control"] and "Set-Cookie" not in r.headers
    assert all(item["favorite"] is False for item in r.json["items"])  # la réponse partagée ne contient rien de personnel
    for path in ("/api/auth/me", "/api/conversations", "/api/favorites", "/api/favorites/ids", f"/api/listings/{lid}"):
        assert cl.get(path).headers["Cache-Control"] == "no-store", path
    assert cl.get("/api/favorites/ids").json["ids"] == [lid]


# ------------------------------------------------------------------------------ OSM
def test_osm_parse_and_store(app):
    elements = [
        {"type": "relation", "id": 1, "tags": {"name": "Golf", "admin_level": "10"}, "center": {"lat": -4.3, "lon": 15.3}},
        {"type": "way", "id": 2, "tags": {"name": "Avenue de la Justice", "highway": "residential"}, "center": {"lat": -4.31, "lon": 15.29}},
        {"type": "way", "id": 3, "tags": {"name": "<script>alert(1)</script>", "highway": "residential"}, "center": {"lat": 0, "lon": 0}},
        {"type": "marker", "tags": {"name": "commune"}},
        {"type": "way", "id": 2, "tags": {"name": "Avenue de la Justice"}, "center": {"lat": -4.31, "lon": 15.29}},
        {"type": "way", "id": 4, "tags": {"name": "Boulevard du 30 Juin"}, "center": {"lat": -4.30, "lon": 15.31}},
        {"type": "marker", "tags": {"name": "places"}},
        {"type": "node", "id": 5, "tags": {"name": "Quartier ignoré"}, "lat": -4.3, "lon": 15.3},
    ]
    parsed = osm.parse(elements)
    assert list(parsed["quartiers"]) == ["Golf"] and list(parsed["quartiers"]["Golf"]["avenues"]) == ["Avenue de la Justice"]
    assert list(parsed["loose"]) == ["Boulevard du 30 Juin"]  # pas de doublon, pas de nom dangereux
    with app.test_request_context():
        gombe = commune_id()
        added = osm.store(gombe, parsed)
        again = osm.store(gombe, parsed)
        from ndaku.db import close
        close(None)
    assert added == {"quartiers": 1, "avenues": 2} and again == {"quartiers": 0, "avenues": 0}
    q = 'rel["boundary"="administrative"]["name"~"^(N\'djili|N\'Djili|Ndjili)$",i]'
    assert q in osm.build_query("Kinshasa", "Ndjili") or "Ndjili" in osm.build_query("Kinshasa", "Ndjili")
    assert '"' not in osm._names_regex('Evil"]; out; (')
