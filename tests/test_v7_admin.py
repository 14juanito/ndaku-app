"""v7 : tableau de bord, gestion des comptes, modérateurs, journal, alertes à l'équipe."""
import io

import pytest

from conftest import DB, avatar_bytes, id_token, publish, register
from ndaku.db import pool


def sql(q, args=()):
    with pool(DB).connection() as con:
        cur = con.execute(q, args)
        return cur.fetchall() if cur.description else None


def uid(email):
    return sql("SELECT id FROM users WHERE email=%s", (email,))[0]["id"]


@pytest.fixture()
def team(client, new_client, keys):
    boss = new_client()
    n = boss.get("/api/auth/nonce").json["nonce"]
    assert boss.post("/api/auth/oauth/google", json={"credential": id_token(keys, nonce=n, email="boss@ndaku.test", sub="boss"),
                                                     "nonce": n}).status_code in (200, 201)
    host, mod, cl = client, new_client(), new_client()
    register(host, "host@x.cd", "host")
    register(mod, "mod@x.cd", "client")
    register(cl, "client@x.cd", "client")
    return boss, host, mod, cl


ADMIN_ONLY = [("get", "/api/admin/users"), ("get", "/api/admin/logs"), ("get", "/api/admin/verifications"),
              ("post", "/api/admin/users/1/moderator"), ("post", "/api/admin/users/1/verify"), ("post", "/api/admin/demo")]
MODERATION = [("get", "/api/admin/stats"), ("get", "/api/admin/queue"), ("get", "/api/admin/reports"),
              ("get", "/api/admin/user-reports"), ("get", "/api/admin/places/pending")]


def call(c, m, path):
    return c.post(path, json={"moderator": True}) if m == "post" else c.get(path)


def test_roles_and_access(team):
    boss, host, mod, cl = team
    for c in (host, mod, cl):
        for m, p in ADMIN_ONLY + MODERATION:
            assert call(c, m, p).status_code == 403, p
    assert mod.post(f"/api/admin/users/{uid('mod@x.cd')}/moderator", json={"moderator": True}).status_code == 403  # auto-promotion
    assert boss.post(f"/api/admin/users/{uid('mod@x.cd')}/moderator", json={"moderator": True}).status_code == 200
    assert mod.get("/api/auth/me").json["user"]["moderator"] is True
    for m, p in MODERATION:
        assert call(mod, m, p).status_code == 200, p
    for m, p in ADMIN_ONLY:
        assert call(mod, m, p).status_code == 403, p  # pas d'identités, de journal ni de gestion des comptes
    # un modérateur ne suspend ni un administrateur ni un autre modérateur
    assert boss.post(f"/api/admin/users/{uid('client@x.cd')}/moderator", json={"moderator": True}).status_code == 200
    assert mod.post(f"/api/admin/users/{uid('client@x.cd')}/suspend", json={"suspend": True}).status_code == 403
    assert mod.post(f"/api/admin/users/{uid('boss@ndaku.test')}/suspend", json={"suspend": True}).status_code == 404
    assert mod.post(f"/api/admin/users/{uid('host@x.cd')}/suspend", json={"suspend": True}).status_code == 200
    assert boss.post(f"/api/admin/users/{uid('boss@ndaku.test')}/moderator", json={"moderator": False}).status_code == 404
    assert boss.post(f"/api/admin/users/{uid('mod@x.cd')}/moderator", json={"moderator": "oui"}).status_code == 400


def test_dashboard_users_detail_logs(team):
    boss, host, _, cl = team
    lid = publish(host, [1, 2, 3], house_number="9").json["id"]
    s = boss.get("/api/admin/stats").json
    assert s["counts"]["users"] == 4 and s["counts"]["hosts"] == 1 and len(s["signups"]) == 30
    assert s["signups"][-1]["n"] == 4
    r = boss.get("/api/admin/users?q=host@x").json
    assert [x["email"] for x in r["items"]] == ["host@x.cd"] and r["items"][0]["listings"] == 1
    assert [x["email"] for x in boss.get("/api/admin/users?filter=host").json["items"]] == ["host@x.cd"]
    assert boss.get("/api/admin/users?q=%25").json["items"] == []  # joker SQL neutralisé
    assert boss.get("/api/admin/users?offset=abc").status_code == 400
    d = boss.get(f"/api/admin/users/{uid('host@x.cd')}").json
    assert d["listings"][0]["id"] == lid and "pw_hash" not in d and any(e["event"] == "register" for e in d["events"])
    assert boss.post(f"/api/admin/users/{uid('host@x.cd')}/verify").status_code == 200
    assert host.get("/api/auth/me").json["user"]["verified"] is True
    assert boss.post(f"/api/admin/users/{uid('host@x.cd')}/verify", json={"verified": False}).status_code == 200
    assert host.get("/api/auth/me").json["user"]["verified"] is False
    logs = boss.get("/api/admin/logs?event=host_").json["items"]
    assert [e["event"] for e in logs] == ["host_unverified", "host_verified"]
    assert boss.get(f"/api/admin/logs?user_id={uid('host@x.cd')}").json["items"]
    assert boss.get("/api/admin/logs?before=x").status_code == 400
    assert boss.get("/api/admin/users/999999").status_code == 404


def test_staff_alerts_throttled(team, new_client):
    boss, host, mod, cl = team
    boss.post(f"/api/admin/users/{uid('mod@x.cd')}/moderator", json={"moderator": True})
    # KYC : administrateurs uniquement
    host.post("/api/verification", data={"id_type": "passeport", "id_doc": (io.BytesIO(avatar_bytes((9, 9, 90))), "a.jpg"),
                                         "selfie": (io.BytesIO(avatar_bytes()), "s.jpg")}, content_type="multipart/form-data")
    kinds = lambda c: [n["kind"] for n in c.get("/api/notifications").json["items"]]
    assert "mod_kyc" in kinds(boss) and "mod_kyc" not in kinds(mod)
    # annonce masquée après 3 signalements : admins + modérateurs, une seule alerte
    lid = publish(host, [4, 5, 6], "Avenue Deux", house_number="3").json["id"]
    for i in range(3):
        c = new_client()
        register(c, f"r{i}@x.cd", "client", avatar=False)
        assert c.post(f"/api/listings/{lid}/report", json={"category": "arnaque"}).status_code == 200
    assert kinds(boss).count("mod_report") == 1 and kinds(mod).count("mod_report") == 1
    assert "mod_report" not in kinds(cl)
