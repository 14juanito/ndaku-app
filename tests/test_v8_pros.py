"""v8 : agents immobiliers (dossier validé par l'administration) et agences (créées par l'administration)."""
import io

import pytest

from conftest import DB, avatar_bytes, id_token, listing_payload, register, upload, avenue
from ndaku.db import pool

AGENCY = {"name": "Kin Habitat Test", "rccm": "CD/KIN/RCCM/24-B-0001", "id_nat": "01-123-N45678",
          "docs_note": "RCCM, Id. Nat. et carte du gérant vérifiés le 01/11/2026", "city": "Kinshasa"}


def sql(q, args=()):
    with pool(DB).connection() as con:
        cur = con.execute(q, args)
        return cur.fetchall() if cur.description else None


def uid(email):
    return sql("SELECT id FROM users WHERE email=%s", (email,))[0]["id"]


def google(c, keys, email, sub):
    n = c.get("/api/auth/nonce").json["nonce"]
    r = c.post("/api/auth/oauth/google", json={"credential": id_token(keys, nonce=n, email=email, sub=sub), "nonce": n})
    assert r.status_code in (200, 201), r.json
    return r


def application(c, n_pro=1, **over):
    data = {"license_no": "RCCM-KIN-123", "zones": "Gombe, Ngaliema", "experience": "4", "trade_name": "Immo Pro",
            "id_doc": (io.BytesIO(avatar_bytes((20, 60, 90))), "id.jpg"), "selfie": (io.BytesIO(avatar_bytes()), "s.jpg"),
            "pro_doc": [(io.BytesIO(avatar_bytes((90 + i, 20, 20))), f"p{i}.jpg") for i in range(n_pro)], **over}
    return c.post("/api/agent/application", data=data, content_type="multipart/form-data")


def pro_payload(c, seeds, street, **over):
    ids = [upload(c, s).json["id"] for s in seeds]
    return listing_payload(ids, avenue(c, street), **over)


@pytest.fixture()
def world(client, new_client, keys):
    boss = new_client()
    google(boss, keys, "boss@ndaku.test", "boss")
    mgr, ag, cl = new_client(), new_client(), new_client()
    google(mgr, keys, "gerant@kinhabitat.cd", "mgr")   # adresses prouvées (Google)
    google(ag, keys, "agent@kinhabitat.cd", "ag")
    for c in (mgr, ag):
        r = c.post("/api/auth/me/avatar", data={"image": (io.BytesIO(avatar_bytes()), "a.jpg")}, content_type="multipart/form-data")
        assert r.status_code == 200
    register(cl, "client@x.cd", "client")
    return boss, mgr, ag, cl


# ------------------------------------------------------------------ agents indépendants
def test_agent_cannot_publish_before_approval(client, new_client, keys):
    a = client
    register(a, "indep@x.cd", "agent")
    assert a.get("/api/auth/me").json["user"]["agent_status"] == "none"
    r = upload(a, 31)
    assert r.status_code == 403 and "dossier" in r.json["error"]
    assert application(a, n_pro=0).status_code == 400
    assert application(a, n_pro=4).status_code == 400
    assert application(a, license_no="x").status_code == 400
    assert application(a, pro_doc=[(io.BytesIO(b"%PDF-1.4"), "x.pdf")]).status_code == 422
    assert application(a, n_pro=2).status_code == 201
    assert application(a).status_code == 409
    assert a.get("/api/agent/application").json["agent_status"] == "pending"
    assert upload(a, 31).status_code == 403
    boss = new_client()
    google(boss, keys, "boss@ndaku.test", "boss")
    items = boss.get("/api/admin/agents").json["items"]
    assert len(items) == 1 and [d["kind"] for d in items[0]["docs"]] == ["id_doc", "selfie", "pro_doc", "pro_doc"]
    did = items[0]["docs"][0]["id"]
    assert a.get(f"/api/admin/agent-docs/{did}").status_code == 403
    r = boss.get(f"/api/admin/agent-docs/{did}")
    assert r.status_code == 200 and r.headers["Cache-Control"] == "no-store"
    assert boss.post(f"/api/admin/agents/{items[0]['id']}/decision", json={"action": "approve"}).status_code == 200
    kinds = sql("SELECT kind, data IS NULL AS erased FROM agent_documents ORDER BY id")
    assert [k["erased"] for k in kinds] == [True, True, False, False]  # identité effacée, justificatifs gardés
    me = a.get("/api/auth/me").json["user"]
    assert me["role"] == "agent" and me["agent_status"] == "approved" and me["verified"]
    # publie avec mandat et honoraires obligatoires
    ids = [upload(a, s).json["id"] for s in (32, 33, 34)]
    loc = avenue(a, "Avenue Pro")
    assert a.post("/api/listings", json=listing_payload(ids, loc)).status_code == 400
    r = a.post("/api/listings", json=listing_payload(ids, loc, mandate="exclusif", agency_fee="1 mois de loyer"))
    assert r.status_code == 201, r.json
    d = a.get(f"/api/listings/{r.json['id']}").json
    assert d["mandate"] == "exclusif" and d["agency_fee"] == "1 mois de loyer" and d["pro"] and d["host"]["role"] == "agent"
    # mise en avant : 3 max pour un indépendant
    assert a.post(f"/api/listings/{r.json['id']}/feature", json={"featured": True}).json["featured"] is True


def test_rejected_agent_and_admin_only_review(client, new_client, keys):
    register(client, "x@x.cd", "client")
    assert application(client).status_code == 201  # un client peut demander à devenir agent
    assert client.get("/api/admin/agents").status_code == 403
    boss = new_client()
    google(boss, keys, "boss@ndaku.test", "boss")
    aid = boss.get("/api/admin/agents").json["items"][0]["id"]
    assert boss.post(f"/api/admin/agents/{aid}/decision", json={"action": "reject", "note": "Carte illisible"}).status_code == 200
    me = client.get("/api/auth/me").json["user"]
    assert me["agent_status"] == "rejected" and me["role"] == "client"
    assert sql("SELECT COUNT(*)::int AS n FROM agent_documents WHERE data IS NOT NULL AND kind IN ('id_doc','selfie')")[0]["n"] == 0


# ------------------------------------------------------------------ agences
def test_only_admins_create_agencies(world):
    boss, mgr, ag, cl = world
    for c in (mgr, ag, cl):
        assert c.post("/api/admin/agencies", json={**AGENCY, "manager_email": "gerant@kinhabitat.cd"}).status_code == 403
    assert boss.post("/api/admin/agencies", json={**AGENCY, "docs_note": "ok", "manager_email": "gerant@kinhabitat.cd"}).status_code == 400
    assert boss.post("/api/admin/agencies", json={**AGENCY, "manager_email": "inconnu@x.cd"}).status_code == 400
    assert boss.post("/api/admin/agencies", json={**AGENCY, "manager_email": "boss@ndaku.test"}).status_code == 400
    r = boss.post("/api/admin/agencies", json={**AGENCY, "manager_email": "gerant@kinhabitat.cd"})
    assert r.status_code == 201 and r.json["slug"] == "kin-habitat-test"
    me = mgr.get("/api/auth/me").json["user"]
    assert me["role"] == "agent" and me["agency"]["role"] == "manager"
    r2 = boss.post("/api/admin/agencies", json={**AGENCY, "manager_email": "agent@kinhabitat.cd"})
    assert r2.json["slug"] == "kin-habitat-test-2"
    assert boss.post("/api/admin/agencies", json={**AGENCY, "manager_email": "agent@kinhabitat.cd"}).status_code == 409


def make_agency(boss):
    r = boss.post("/api/admin/agencies", json={**AGENCY, "manager_email": "gerant@kinhabitat.cd"})
    assert r.status_code == 201
    return r.json


def test_invitations_and_membership(world, new_client):
    boss, mgr, ag, cl = world
    a = make_agency(boss)
    assert ag.post("/api/agency/invites", json={"email": "x@x.cd"}).status_code in (403, 404)  # pas gérant
    r = mgr.post("/api/agency/invites", json={"email": "Agent@KinHabitat.cd"})
    assert r.status_code == 201 and r.json["existing_account"]
    assert mgr.post("/api/agency/invites", json={"email": "agent@kinhabitat.cd"}).status_code == 409
    inv = ag.get("/api/agent/application").json["invites"]
    assert len(inv) == 1 and inv[0]["agency"] == AGENCY["name"]
    assert cl.post(f"/api/agency/invites/{inv[0]['id']}/accept").status_code == 404  # invitation d'un autre
    # une adresse non prouvée ne peut pas accepter (sinon on s'inscrit avec l'e-mail invité)
    sneaky = new_client()
    register(sneaky, "piege@x.cd", "client")
    mgr.post("/api/agency/invites", json={"email": "piege@x.cd"})
    iid = sneaky.get("/api/agent/application").json["invites"][0]["id"]
    assert sneaky.post(f"/api/agency/invites/{iid}/accept").status_code == 403
    assert ag.post(f"/api/agency/invites/{inv[0]['id']}/accept").status_code == 200
    me = ag.get("/api/auth/me").json["user"]
    assert me["role"] == "agent" and me["agency"]["slug"] == a["slug"] and me["agency"]["role"] == "agent"
    # l'agent publie pour l'agence
    r = ag.post("/api/listings", json=pro_payload(ag, (41, 42, 43), "Avenue Agence", mandate="simple", agency_fee="10 %"))
    assert r.status_code == 201, r.json
    lid = r.json["id"]
    page = cl.get(f"/api/agencies/{a['slug']}").json
    assert [x["id"] for x in page["listings"]] == [lid] and len(page["team"]) == 2 and "nif" not in page
    assert cl.get(f"/api/listings/{lid}").json["agency"]["slug"] == a["slug"]
    # espace agence : l'agent ne voit que ses biens, ne gère pas l'équipe
    assert ag.get("/api/agency/stats").status_code == 403
    assert ag.get("/api/agency/conversations").status_code == 403
    assert ag.patch("/api/agency", json={"description": "pirate"}).status_code == 403
    assert len(ag.get("/api/agency/listings").json["items"]) == 1
    # le gérant supervise les discussions des biens de l'agence (lecture seule)
    cid = cl.post(f"/api/listings/{lid}/conversation", json={"message": "Bonjour, toujours disponible ?"}).json["id"]
    assert mgr.get(f"/api/agency/conversations/{cid}").json["messages"][0]["body"].startswith("Bonjour")
    assert cl.get(f"/api/agency/conversations/{cid}").status_code in (403, 404)
    # retrait de l'agent : ses biens et discussions passent au gérant
    assert mgr.delete(f"/api/agency/members/{uid('agent@kinhabitat.cd')}").status_code == 200
    assert sql("SELECT owner_id FROM listings WHERE id=%s", (lid,))[0]["owner_id"] == uid("gerant@kinhabitat.cd")
    assert mgr.get(f"/api/conversations/{cid}").status_code == 200
    assert ag.get(f"/api/conversations/{cid}").status_code == 404
    me = ag.get("/api/auth/me").json["user"]
    assert me["agency"] is None and me["role"] == "host"  # redevient particulier : plus rien au nom de l'agence


def test_manager_scope_and_other_agency_isolation(world, new_client, keys):
    boss, mgr, ag, cl = world
    a = make_agency(boss)
    other = new_client()
    google(other, keys, "autre@agence2.cd", "o")
    other.post("/api/auth/me/avatar", data={"image": (io.BytesIO(avatar_bytes()), "a.jpg")}, content_type="multipart/form-data")
    boss.post("/api/admin/agencies", json={**AGENCY, "name": "Autre Agence", "manager_email": "autre@agence2.cd"})
    lid = mgr.post("/api/listings", json=pro_payload(mgr, (51, 52, 53), "Avenue Une", mandate="exclusif", agency_fee="Aucun")).json["id"]
    # un gérant d'une autre agence ne touche à rien
    assert other.post(f"/api/listings/{lid}/feature", json={"featured": True}).status_code == 404
    assert other.post(f"/api/agency/listings/{lid}/assign", json={"user_id": uid("autre@agence2.cd")}).status_code == 404
    assert other.patch(f"/api/listings/{lid}", json={"status": "closed"}).status_code == 404
    assert other.delete(f"/api/agency/members/{uid('gerant@kinhabitat.cd')}").status_code == 404
    # quota de mise en avant de l'agence
    boss.patch(f"/api/admin/agencies/{sql('SELECT id FROM agencies WHERE slug=%s', (a['slug'],))[0]['id']}", json={"featured_quota": 0})
    assert mgr.post(f"/api/listings/{lid}/feature", json={"featured": True}).status_code == 400
    assert mgr.delete(f"/api/agency/members/{uid('gerant@kinhabitat.cd')}").status_code == 400  # pas soi-même
    assert mgr.patch(f"/api/agency/members/{uid('gerant@kinhabitat.cd')}", json={"role": "agent"}).status_code == 400
    assert mgr.patch("/api/agency", json={"website": "javascript:alert(1)"}).status_code == 400
    assert mgr.patch("/api/agency", json={"description": "Agence familiale à Gombe.", "phone": "+243 81"}).status_code == 200


def test_suspended_agency_hides_everything(world):
    boss, mgr, ag, cl = world
    a = make_agency(boss)
    lid = mgr.post("/api/listings", json=pro_payload(mgr, (61, 62, 63), "Avenue S", mandate="simple", agency_fee="1 mois")).json["id"]
    aid = sql("SELECT id FROM agencies WHERE slug=%s", (a["slug"],))[0]["id"]
    assert boss.patch(f"/api/admin/agencies/{aid}", json={"status": "suspended"}).status_code == 200
    assert cl.get(f"/api/listings/{lid}").status_code == 404
    assert cl.get(f"/api/agencies/{a['slug']}").status_code == 404
    assert all(x["id"] != lid for x in cl.get("/api/listings").json["items"])
    assert mgr.get("/api/agency").status_code == 403
    assert upload(mgr, 64).status_code == 403


def test_stats_impressions_and_response(world):
    boss, mgr, ag, cl = world
    make_agency(boss)
    lid = mgr.post("/api/listings", json=pro_payload(mgr, (71, 72, 73), "Avenue St", mandate="simple", agency_fee="1 mois")).json["id"]
    for _ in range(4):
        assert cl.post("/api/impressions", json={"ids": [lid, 999999]}).status_code == 200
    assert cl.post("/api/impressions", json={"ids": "x"}).status_code == 400
    assert cl.post("/api/impressions", json={"ids": list(range(61))}).status_code == 400
    cl.get(f"/api/listings/{lid}")
    cid = cl.post(f"/api/listings/{lid}/conversation", json={"message": "Bonjour, toujours disponible ?"}).json["id"]
    mgr.post(f"/api/conversations/{cid}/messages", json={"body": "Oui, quand voulez-vous visiter ?"})
    s = mgr.get("/api/agency/stats?days=30").json
    assert s["totals"]["impressions"] == 4 and s["totals"]["views"] == 1 and s["totals"]["ctr"] == 25.0
    assert s["totals"]["contacts"] == 1 and s["response"]["response_rate"] == 100
    assert s["agents"][0]["contacts"] == 1 and len(s["daily"]) == 30
    assert mgr.get("/api/agency/stats?days=12").status_code == 400
    assert mgr.get("/api/my/stats?days=7").json["totals"]["impressions"] == 4
    hp = cl.get(f"/api/hosts/{uid('gerant@kinhabitat.cd')}").json
    assert hp["pro"] and hp["agency"]["name"] == AGENCY["name"] and hp["response"]["response_rate"] == 100


def test_directory_and_account_deletion_keeps_agency_listings(world):
    boss, mgr, ag, cl = world
    a = make_agency(boss)
    mgr.post("/api/agency/invites", json={"email": "agent@kinhabitat.cd"})
    ag.post(f"/api/agency/invites/{ag.get('/api/agent/application').json['invites'][0]['id']}/accept")
    lid = ag.post("/api/listings", json=pro_payload(ag, (81, 82, 83), "Avenue D", mandate="simple", agency_fee="1 mois")).json["id"]
    d = cl.get("/api/agencies").json
    assert [x["slug"] for x in d["items"]] == [a["slug"]] and d["items"][0]["listings"] == 1
    # l'agent supprime son compte : le bien reste à l'agence (au gérant)
    assert ag.post("/api/auth/me/delete", json={"confirm": "SUPPRIMER"}).status_code == 200
    assert sql("SELECT owner_id FROM listings WHERE id=%s", (lid,))[0]["owner_id"] == uid("gerant@kinhabitat.cd")


# ------------------------------------------------------------------ non-régressions (revue de code)
def test_departing_agent_keeps_agency_photos_messages_and_manager(world):
    boss, mgr, ag, cl = world
    make_agency(boss)
    mgr.post("/api/agency/invites", json={"email": "agent@kinhabitat.cd"})
    ag.post(f"/api/agency/invites/{ag.get('/api/agent/application').json['invites'][0]['id']}/accept")
    lid = mgr.post("/api/listings", json=pro_payload(mgr, (91, 92, 93), "Avenue G", mandate="simple", agency_fee="1 mois")).json["id"]
    cid = cl.post(f"/api/listings/{lid}/conversation", json={"message": "Bonjour, toujours disponible ?"}).json["id"]
    mgr.post(f"/api/conversations/{cid}/messages", json={"body": "Oui, passez samedi."})
    # le seul gérant supprime son compte : l'agent reprend, devient gérant, rien n'est perdu
    assert mgr.post("/api/auth/me/delete", json={"confirm": "SUPPRIMER"}).status_code == 200
    heir = uid("agent@kinhabitat.cd")
    assert sql("SELECT COUNT(*)::int AS n FROM images WHERE listing_id=%s AND owner_id=%s", (lid, heir))[0]["n"] == 3
    msgs = ag.get(f"/api/conversations/{cid}").json["messages"]
    assert [m["body"] for m in msgs] == ["Bonjour, toujours disponible ?", "Oui, passez samedi."]
    assert ag.get("/api/auth/me").json["user"]["agency"]["role"] == "manager"
    assert ag.get("/api/agency/stats").status_code == 200


def test_removed_member_gets_host_role_back_and_photos_follow_reassign(world):
    boss, mgr, ag, cl = world
    make_agency(boss)
    mgr.post("/api/agency/invites", json={"email": "agent@kinhabitat.cd"})
    ag.post(f"/api/agency/invites/{ag.get('/api/agent/application').json['invites'][0]['id']}/accept")
    lid = ag.post("/api/listings", json=pro_payload(ag, (94, 95, 96), "Avenue H", mandate="simple", agency_fee="1 mois")).json["id"]
    assert mgr.post(f"/api/agency/listings/{lid}/assign", json={"user_id": uid("gerant@kinhabitat.cd")}).status_code == 200
    assert sql("SELECT DISTINCT owner_id FROM images WHERE listing_id=%s", (lid,)) == [{"owner_id": uid("gerant@kinhabitat.cd")}]
    mgr.delete(f"/api/agency/members/{uid('agent@kinhabitat.cd')}")
    me = ag.get("/api/auth/me").json["user"]
    assert me["role"] == "host" and me["agency"] is None
    assert upload(ag, 97).status_code == 201  # peut de nouveau publier comme particulier


def test_unvetted_agent_is_not_shown_as_professional(client, new_client):
    register(client, "faux-agent@x.cd", "agent")
    me = client.get("/api/auth/me").json["user"]
    assert client.get(f"/api/hosts/{me['id']}").json["pro"] is False


def test_featured_quota_counts_closed_then_reactivated(client, new_client, keys):
    boss = new_client()
    google(boss, keys, "boss@ndaku.test", "boss")
    register(client, "indep@x.cd", "agent")
    application(client)
    boss.post(f"/api/admin/agents/{boss.get('/api/admin/agents').json['items'][0]['id']}/decision", json={"action": "approve"})
    ids = []
    for k in range(4):
        r = client.post("/api/listings", json=pro_payload(client, (100 + 3 * k, 101 + 3 * k, 102 + 3 * k), f"Avenue Q{k}",
                                                          mandate="simple", agency_fee="1 mois"))
        assert r.status_code == 201, r.json
        ids.append(r.json["id"])
    for i in ids[:3]:
        assert client.post(f"/api/listings/{i}/feature", json={"featured": True}).status_code == 200
    assert client.patch(f"/api/listings/{ids[0]}", json={"status": "closed"}).status_code == 200
    assert client.post(f"/api/listings/{ids[3]}/feature", json={"featured": True}).status_code == 200
    client.patch(f"/api/listings/{ids[0]}", json={"status": "active"})
    assert sql("SELECT COUNT(*)::int AS n FROM listings WHERE featured")[0]["n"] == 3  # jamais plus que le quota
