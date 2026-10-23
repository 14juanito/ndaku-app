"""Référentiel géographique : listes en cascade (province > ville > commune > quartier > avenue),
propositions des hôtes (modérées) et import OpenStreetMap."""
from flask import Blueprint, abort, g, jsonify, request

from . import osm
from .auth import body, text
from .db import all_, one
from .security import audit, current_user, rate_limit, require

bp = Blueprint("places", __name__, url_prefix="/api")
CHILD = {None: "province", "province": "city", "city": "commune", "commune": "quartier", "quartier": "avenue"}


def place(pid):
    return one("SELECT * FROM places WHERE id=%s", (pid,)) if pid else None


def chain(avenue_id=None, quartier_id=None, commune_id=None):
    """Remonte la hiérarchie depuis l'élément le plus précis : {province, city, commune, quartier, avenue}."""
    start = avenue_id or quartier_id or commune_id
    rows = all_("""WITH RECURSIVE up AS (SELECT * FROM places WHERE id=%s
                     UNION ALL SELECT p.* FROM places p JOIN up ON p.id = up.parent_id)
                   SELECT id, kind, name, lat, lng, status, created_by FROM up""", (start,))
    return {r["kind"]: r for r in rows}


@bp.get("/places")
def children():
    """Enfants actifs d'un lieu (provinces si parent_id absent). Réponse mise en cache par le CDN."""
    raw = request.args.get("parent_id")
    try:
        parent_id = int(raw) if raw else None
    except ValueError:
        abort(400, "Paramètre invalide.")
    if parent_id is None:
        rows = all_("SELECT id, kind, name, lat, lng FROM places WHERE parent_id IS NULL AND status='active' ORDER BY name")
    else:
        rows = all_("""SELECT id, kind, name, lat, lng FROM places WHERE parent_id=%s AND status='active'
                       ORDER BY kind, name LIMIT 3000""", (parent_id,))
    g.cache_seconds = 3600
    return jsonify(items=rows)


@bp.get("/places/mine")
@require("host")
def mine():
    """Quartiers / avenues proposés par l'hôte et encore en attente de validation (visibles par lui seul)."""
    try:
        parent_id = int(request.args.get("parent_id", ""))
    except ValueError:
        abort(400, "Paramètre invalide.")
    return jsonify(items=all_("""SELECT id, kind, name, lat, lng FROM places WHERE parent_id=%s AND status='pending'
                                 AND created_by=%s ORDER BY name""", (parent_id, current_user()["id"])))


@bp.post("/places")
@require("host")
def suggest():
    """Un hôte ne trouve pas son quartier / avenue : il le propose. Visible par tous après validation."""
    u, d = current_user(), body()
    rate_limit(f"place-suggest:{u['id']}", 20, 86400, "Trop de propositions aujourd'hui.")
    parent = place(d.get("parent_id") if isinstance(d.get("parent_id"), int) else None)
    kind = d.get("kind")
    if not parent or parent["status"] == "rejected":
        abort(400, "Lieu parent invalide.")
    allowed = {"commune": ("quartier", "avenue"), "quartier": ("avenue",)}.get(parent["kind"], ())
    if kind not in allowed:
        abort(400, "Type de lieu invalide à cet endroit.")
    name = osm.clean_name(text(d, "name", 80))
    if not name or not any(ch.isalpha() for ch in name):
        abort(400, "Nom invalide (2 à 80 caractères, lettres et chiffres).")
    existing = one("""SELECT id, kind, name, lat, lng, status FROM places WHERE COALESCE(parent_id,0)=%s AND kind=%s
                      AND lower(name)=lower(%s)""", (parent["id"], kind, name))
    if existing:
        return jsonify(existing)
    row = one("""INSERT INTO places (kind, name, parent_id, source, status, created_by)
                 VALUES (%s,%s,%s,'user','pending',%s) RETURNING id, kind, name, lat, lng, status""",
              (kind, name, parent["id"], u["id"]))
    return jsonify(row), 201


# ------------------------------------------------------------------ administration
@bp.get("/admin/places/pending")
@require("admin")
def pending():
    return jsonify(items=all_("""SELECT p.id, p.kind, p.name, par.name AS parent, par.kind AS parent_kind,
                                   u.name AS author, extract(epoch FROM p.created_at)::float8 AS created_at,
                                   (SELECT COUNT(*) FROM listings l WHERE l.quartier_id=p.id OR l.avenue_id=p.id)::int AS uses
                                 FROM places p JOIN places par ON par.id=p.parent_id
                                 LEFT JOIN users u ON u.id=p.created_by
                                 WHERE p.status='pending' ORDER BY p.created_at LIMIT 200"""))


@bp.post("/admin/places/<int:pid>/decision")
@require("admin")
def decide(pid):
    act = body().get("action")
    if act not in ("approve", "reject"):
        abort(400, "Action invalide.")
    if not one("UPDATE places SET status=%s WHERE id=%s AND status='pending' RETURNING id",
               ("active" if act == "approve" else "rejected", pid)):
        abort(404, "Lieu non en attente.")
    audit(f"place_{act}", current_user()["id"], place_id=pid)
    return jsonify(ok=True)


@bp.get("/admin/osm/coverage")
@require("admin")
def coverage():
    try:
        city_id = int(request.args.get("city_id", ""))
    except ValueError:
        abort(400, "Ville invalide.")
    return jsonify(items=osm.coverage(city_id))


@bp.post("/admin/osm/<int:commune_id>")
@require("admin")
def osm_import(commune_id):
    """Importe quartiers et avenues d'une commune depuis OpenStreetMap (une commune par appel)."""
    rate_limit(f"osm:{current_user()['id']}", 120, 3600)
    try:
        added = osm.import_commune(commune_id)
    except ValueError as e:
        abort(404, str(e))
    except OSError:
        abort(502, "OpenStreetMap (Overpass) ne répond pas, réessayez dans un instant.")
    audit("osm_import", current_user()["id"], commune_id=commune_id, **added)
    return jsonify(ok=True, **added)
