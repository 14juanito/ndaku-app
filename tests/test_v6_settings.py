"""v6 : confirmation de lecture, avis modifiables, paramètres du compte (mot de passe, suppression)."""
import pytest

from conftest import DB, PW, publish, register
from ndaku.db import pool


def sql(q, args=()):
    with pool(DB).connection() as con:
        cur = con.execute(q, args)
        return cur.fetchall() if cur.description else None


@pytest.fixture()
def world(client, new_client):
    host, cl, other = client, new_client(), new_client()
    register(host, "host@x.cd", "host")
    lid = publish(host, [1, 2, 3], house_number="12").json["id"]
    register(cl, "client@x.cd", "client")
    register(other, "autre@x.cd", "client")
    cid = cl.post(f"/api/listings/{lid}/conversation", json={"message": "Bonjour, est-ce disponible ?"}).json["id"]
    hid = sql("SELECT owner_id FROM listings WHERE id=%s", (lid,))[0]["owner_id"]
    return host, cl, other, lid, cid, hid


def test_read_receipt(world):
    host, cl, _, _, cid, _ = world
    assert cl.get(f"/api/conversations/{cid}").json["other_read_at"] is None  # l'hôte n'a pas encore ouvert
    sent = cl.get(f"/api/conversations/{cid}").json["messages"][0]["created_at"]
    host.get(f"/api/conversations/{cid}")
    seen = cl.get(f"/api/conversations/{cid}").json["other_read_at"]
    assert seen and seen >= sent
    assert world[2].get(f"/api/conversations/{cid}").status_code == 404


def test_listing_review_edit_and_delete(world):
    _, cl, other, lid, _, _ = world
    assert cl.post(f"/api/listings/{lid}/reviews", json={"rating": 5, "comment": "Très belle maison, conforme."}).status_code == 201
    r = cl.post(f"/api/listings/{lid}/reviews", json={"rating": 1, "comment": "Finalement beaucoup de coupures."})
    assert r.status_code == 200 and r.json["created"] is False
    d = cl.get(f"/api/listings/{lid}").json
    assert d["rating"] == 1 and d["reviews_count"] == 1 and d["my_review"]["rating"] == 1 and d["reviews"][0]["edited"]
    assert cl.post(f"/api/listings/{lid}/reviews", json={"rating": 0, "comment": "x" * 20}).status_code == 400
    assert other.delete(f"/api/listings/{lid}/reviews/mine").status_code == 404  # pas d'avis à lui
    assert cl.delete(f"/api/listings/{lid}/reviews/mine").status_code == 200
    d = cl.get(f"/api/listings/{lid}").json
    assert d["rating"] is None and d["reviews_count"] == 0 and d["my_review"] is None


def test_host_review_edit(world):
    _, cl, _, _, _, hid = world
    cl.post(f"/api/hosts/{hid}/reviews", json={"rating": 2, "comment": "Hôte peu disponible au début."})
    assert cl.post(f"/api/hosts/{hid}/reviews", json={"rating": 4, "comment": "Hôte finalement très arrangeant."}).status_code == 200
    p = cl.get(f"/api/hosts/{hid}").json
    assert p["rating"] == 4 and p["reviews_count"] == 1 and p["my_review"]["rating"] == 4
    assert sql("SELECT COUNT(*)::int AS n FROM notifications WHERE kind='review'")[0]["n"] == 1  # pas de doublon


def test_change_password(world, new_client):
    _, cl, _, _, _, _ = world
    assert cl.post("/api/auth/password/change", json={"current_password": "faux", "new_password": "Nouveau-Mdp-2027"}).status_code == 403
    assert cl.post("/api/auth/password/change", json={"current_password": PW, "new_password": "court"}).status_code == 400
    assert cl.post("/api/auth/password/change", json={"current_password": PW, "new_password": "Nouveau-Mdp-2027"}).status_code == 200
    c2 = new_client()
    assert c2.post("/api/auth/login", json={"email": "client@x.cd", "password": PW}).status_code == 401
    assert c2.post("/api/auth/login", json={"email": "client@x.cd", "password": "Nouveau-Mdp-2027"}).status_code == 200


def test_delete_account(world):
    host, cl, other, lid, cid, hid = world
    cl.post(f"/api/listings/{lid}/reviews", json={"rating": 5, "comment": "Très belle maison, conforme."})
    cl.post(f"/api/hosts/{hid}/reviews", json={"rating": 5, "comment": "Hôte ponctuel et honnête."})
    assert cl.post("/api/auth/me/delete", json={"password": "faux"}).status_code == 403
    assert cl.post("/api/auth/me/delete", json={"password": PW}).status_code == 200
    assert cl.get("/api/auth/me").json["user"] is None  # session fermée
    assert not sql("SELECT 1 FROM users WHERE email='client@x.cd'")
    assert host.get(f"/api/listings/{lid}").json["reviews_count"] == 0  # moyennes recalculées
    assert host.get(f"/api/hosts/{hid}").json["reviews_count"] == 0
    assert host.get(f"/api/conversations/{cid}").status_code == 404
    # Un hôte supprimé emporte ses annonces
    assert host.post("/api/auth/me/delete", json={"password": PW}).status_code == 200
    assert other.get(f"/api/listings/{lid}").status_code == 404
