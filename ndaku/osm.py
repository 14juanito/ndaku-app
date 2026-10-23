"""Import des quartiers et avenues d'une commune depuis OpenStreetMap (API Overpass, données ODbL).

Exécuté côté serveur (Vercel) par un administrateur, une commune par appel. Les quartiers sont les limites
administratives de niveau 9/10 contenues dans la commune ; chaque avenue nommée est rattachée au quartier
qui la contient, ou directement à la commune quand OSM ne connaît pas le découpage en quartiers.
"""
import json
import re
import urllib.parse
import urllib.request

from .db import all_, one, run
from .places_seed import OSM_ALIASES

OVERPASS = "https://overpass-api.de/api/interpreter"
UA = {"User-Agent": "NdakuGazetteer/1.0 (https://github.com/14juanito/ndaku-app)"}
HIGHWAYS = "residential|primary|secondary|tertiary|unclassified|living_street|trunk|service|pedestrian"
_SAFE_NAME = re.compile(r"^[\w'’ .\-()/]{2,80}$", re.UNICODE)


def _names_regex(name):
    names = OSM_ALIASES.get(name, [name])
    return "^(" + "|".join(re.escape(n).replace('"', "") for n in names) + ")$"


def build_query(city, commune):
    return f"""[out:json][timeout:50];
rel["boundary"="administrative"]["name"~"{_names_regex(city)}",i]->.cr;
.cr map_to_area->.ca;
rel["boundary"="administrative"]["name"~"{_names_regex(commune)}",i](area.ca)->.cm;
.cm map_to_area->.c;
rel["boundary"="administrative"]["admin_level"~"^(9|10)$"](area.c)->.qs;
foreach.qs->.q(
  .q out tags center;
  .q map_to_area->.qa;
  way["highway"~"^({HIGHWAYS})$"]["name"](area.qa);
  out tags center;
);
make marker name="commune";
out;
way["highway"~"^({HIGHWAYS})$"]["name"](area.c);
out tags center;
make marker name="places";
out;
node["place"~"^(suburb|quarter|neighbourhood)$"](area.c);
out tags;"""


def _center(el):
    c = el.get("center") or el
    return c.get("lat"), c.get("lon")


def clean_name(n):
    n = re.sub(r"\s+", " ", (n or "").strip())
    return n if _SAFE_NAME.match(n) else None


def parse(elements):
    """Transforme la réponse Overpass en {quartiers: {nom: {lat,lng,avenues:{nom:(lat,lng)}}}, loose: {...}}."""
    quartiers, loose, section, current = {}, {}, "quartiers", None
    for el in elements:
        t, tags = el.get("type"), el.get("tags", {})
        if t == "marker":
            section, current = tags.get("name"), None
            continue
        name = clean_name(tags.get("name"))
        if not name:
            continue
        lat, lng = _center(el)
        if section == "quartiers":
            if t == "relation":
                current = quartiers.setdefault(name, {"lat": lat, "lng": lng, "avenues": {}})
            elif t == "way" and current is not None:
                current["avenues"].setdefault(name, (lat, lng))
        elif section == "commune" and t == "way":
            loose.setdefault(name, (lat, lng))
        elif section == "places" and t == "node" and not quartiers:
            # Pas de limites de quartiers dans OSM : on garde au moins les noms de quartiers (sans avenues).
            quartiers.setdefault(name, {"lat": lat, "lng": lng, "avenues": {}})
    in_quartier = {a.lower() for q in quartiers.values() for a in q["avenues"]}
    loose = {n: c for n, c in loose.items() if n.lower() not in in_quartier}
    return {"quartiers": quartiers, "loose": loose}


def fetch(city, commune, timeout=55):
    data = urllib.parse.urlencode({"data": build_query(city, commune)}).encode()
    with urllib.request.urlopen(urllib.request.Request(OVERPASS, data=data, headers=UA), timeout=timeout) as r:
        return json.loads(r.read())["elements"]


_INS = """INSERT INTO places (kind, name, parent_id, lat, lng, source) VALUES (%s,%s,%s,%s,%s,'osm')
          ON CONFLICT (COALESCE(parent_id, 0), kind, lower(name)) DO NOTHING"""


def store(commune_id, parsed):
    """Insère (sans doublon) quartiers et avenues sous la commune. Retourne les compteurs ajoutés."""
    added = {"quartiers": 0, "avenues": 0}
    for qname, q in parsed["quartiers"].items():
        added["quartiers"] += run(_INS, ("quartier", qname, commune_id, q["lat"], q["lng"])).rowcount
        qid = one("SELECT id FROM places WHERE parent_id=%s AND kind='quartier' AND lower(name)=lower(%s)",
                  (commune_id, qname))["id"]
        for aname, (lat, lng) in q["avenues"].items():
            added["avenues"] += run(_INS, ("avenue", aname, qid, lat, lng)).rowcount
    for aname, (lat, lng) in parsed["loose"].items():
        added["avenues"] += run(_INS, ("avenue", aname, commune_id, lat, lng)).rowcount
    return added


def import_commune(commune_id):
    c = one("""SELECT c.id, c.name, v.name AS city FROM places c JOIN places v ON v.id=c.parent_id
               WHERE c.id=%s AND c.kind='commune'""", (commune_id,))
    if not c:
        raise ValueError("Commune inconnue.")
    return store(c["id"], parse(fetch(c["city"], c["name"])))


def coverage(city_id):
    return all_("""SELECT c.id, c.name,
                     (SELECT COUNT(*) FROM places q WHERE q.parent_id=c.id AND q.kind='quartier')::int AS quartiers,
                     (SELECT COUNT(*) FROM places a WHERE a.kind='avenue' AND (a.parent_id=c.id OR a.parent_id IN
                        (SELECT id FROM places WHERE parent_id=c.id AND kind='quartier')))::int AS avenues
                   FROM places c WHERE c.parent_id=%s AND c.kind='commune' ORDER BY c.name""", (city_id,))
