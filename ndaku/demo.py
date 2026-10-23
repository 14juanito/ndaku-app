"""Annonces de démonstration.

- `commons` : vraies photos de maisons de RDC (Wikimedia Commons, licences libres, crédits conservés),
  téléchargées par le serveur (Vercel) puis passées par le même contrôle anti-fraude qu'un upload.
  Les annonces créées sont « en attente » : l'admin vérifie les photos avant publication.
- `illustrations` : images générées localement (développement / tests hors réseau).
"""
import json
import random
import re
import time
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw, ImageFilter

from . import antifraud as af
from . import photos
from .db import all_, db, one, run

UA = {"User-Agent": "NdakuDemo/1.0 (https://github.com/14juanito/ndaku-app)"}
API = "https://commons.wikimedia.org/w/api.php"
FREE = re.compile(r"^(CC0|CC BY|CC-BY|Public domain|PD)", re.I)
EXCLUDE = re.compile(r"map|carte|logo|flag|drapeau|portrait|church|église|eglise|cathedral|cathédrale|stade|stadium|"
                     r"market|marché|marche|statue|monument|aerial|satellite|diagram|people|ministère|ministry|"
                     r"embassy|ambassade|hospital|hôpital|school|école|university|université|airport|aéroport", re.I)
CITY_QUERIES = {
    "Kinshasa": ["Category:Houses in Kinshasa", "Category:Residential buildings in Kinshasa",
                 "Category:Gombe (Kinshasa)", "Kinshasa house", "Kinshasa villa", "Kinshasa maison", "Ngaliema"],
    "Lubumbashi": ["Category:Houses in Lubumbashi", "Lubumbashi house", "Lubumbashi maison"],
    "Goma": ["Category:Houses in Goma", "Goma house", "Goma maison"],
    "Bukavu": ["Category:Bukavu", "Bukavu house", "Bukavu maison"],
    "Kisangani": ["Category:Kisangani", "Kisangani house"],
    "Matadi": ["Category:Matadi", "Matadi house"],
    "Kolwezi": ["Category:Kolwezi", "Kolwezi house"],
}

# (ville, commune, offre, type, titre, prix USD, chambres, sdb, m², meublé, adresse)
LISTINGS = [
    ("Kinshasa", "Gombe", "location", "appartement", "Appartement moderne vue sur le fleuve Congo", 1800, 3, 2, 140, 1, "Avenue de la Justice 12"),
    ("Kinshasa", "Ngaliema", "location", "villa", "Villa avec piscine et jardin, quartier calme", 3500, 5, 4, 420, 1, "Avenue Mbakana 45"),
    ("Kinshasa", "Limete", "location", "maison", "Maison familiale proche du boulevard Lumumba", 650, 3, 2, 180, 0, "7e rue Limete Industriel 31"),
    ("Kinshasa", "Bandalungwa", "location", "studio", "Studio meublé idéal étudiant ou jeune actif", 220, 1, 1, 32, 1, "Avenue Kasa-Vubu 8"),
    ("Kinshasa", "Mont-Ngafula", "vente", "villa", "Villa neuve à vendre, titre foncier disponible", 185000, 4, 3, 380, 0, "Route de Matadi 2"),
    ("Kinshasa", "Lemba", "vente", "maison", "Maison à vendre près de l'université de Kinshasa", 72000, 4, 2, 250, 0, "Avenue Université 19"),
    ("Kinshasa", "Kintambo", "location", "maison", "Maison 4 chambres avec cour et parking", 900, 4, 2, 230, 0, "Avenue Lukusa 14"),
    ("Kinshasa", "Gombe", "vente", "appartement", "Appartement standing à vendre, immeuble sécurisé", 240000, 3, 2, 165, 0, "Boulevard du 30 Juin 101"),
    ("Lubumbashi", "Lubumbashi", "location", "maison", "Maison spacieuse au quartier Golf avec parking", 900, 4, 3, 300, 0, "Avenue Kasai 22"),
    ("Lubumbashi", "Kenya", "vente", "maison", "Maison à vendre, grande parcelle clôturée", 98000, 5, 3, 420, 0, "Avenue Kimbangu 54"),
    ("Goma", "Goma", "location", "villa", "Villa avec vue sur le lac Kivu", 1500, 4, 3, 330, 1, "Avenue du Lac 9"),
    ("Goma", "Karisimbi", "vente", "maison", "Maison familiale à vendre, quartier résidentiel", 64000, 3, 2, 210, 0, "Avenue des Aigles 17"),
    ("Bukavu", "Ibanda", "location", "maison", "Maison lumineuse près du lac à Ibanda", 600, 3, 2, 170, 1, "Avenue Patrice Lumumba 5"),
    ("Kisangani", "Makiso", "location", "maison", "Maison au bord du fleuve à Makiso", 450, 3, 2, 190, 0, "Avenue de l'Église 3"),
    ("Matadi", "Matadi", "vente", "maison", "Maison sur les hauteurs de Matadi", 55000, 3, 2, 200, 0, "Avenue du Port 11"),
    ("Kolwezi", "Manika", "location", "maison", "Maison 3 chambres avec groupe électrogène", 520, 3, 2, 160, 0, "Avenue Kolwezi 3"),
]
DESC = ("{t}. Situé à {c}, {v}, ce bien de {s} m² offre {b} chambre(s) et {ba} salle(s) de bain. "
        "Quartier calme, proche des commerces, écoles et services de santé. Visite sur rendez-vous via Ndaku. "
        "Annonce de démonstration illustrée par une photo réelle de {city} (voir crédits).")
AMS = [["Eau courante", "Électricité", "Parking", "Gardien", "Internet"],
       ["Eau courante", "Groupe électrogène", "Clôture", "Citerne", "Jardin"],
       ["Électricité", "Climatisation", "Cuisine équipée", "Panneaux solaires", "Parking"]]
PHOTOS_PER_LISTING = 3


# ---------------------------------------------------------------- Wikimedia Commons
def _get(url, timeout=10):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def _api(**params):
    return json.loads(_get(API + "?" + urllib.parse.urlencode({**params, "format": "json"})))


def commons_candidates(city, want):
    """Fichiers JPEG paysage, ≥ 1000 px, licence libre, titre plausible — pour une ville."""
    seen, out = set(), []
    for q in CITY_QUERIES.get(city, [city + " house"]):
        if q.startswith("Category:"):
            gen = {"generator": "categorymembers", "gcmtitle": q, "gcmtype": "file", "gcmlimit": 100}
        else:
            gen = {"generator": "search", "gsrnamespace": 6, "gsrsearch": q, "gsrlimit": 50}
        try:
            data = _api(action="query", prop="imageinfo", iiprop="url|size|mime|extmetadata", iiurlwidth=1600,
                        iiextmetadatafilter="LicenseShortName|Artist", **gen)
        except OSError:
            continue
        for p in (data.get("query", {}).get("pages") or {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            meta = ii.get("extmetadata", {})
            lic = meta.get("LicenseShortName", {}).get("value", "")
            title = p.get("title", "")
            if (title in seen or ii.get("mime") != "image/jpeg" or not FREE.match(lic) or EXCLUDE.search(title)
                    or ii.get("width", 0) < 1000 or ii.get("width", 0) <= ii.get("height", 0)):
                continue
            url = ii.get("thumburl") or ii.get("url") or ""
            if urllib.parse.urlsplit(url).netloc != "upload.wikimedia.org":  # anti-SSRF : hôte attendu uniquement
                continue
            seen.add(title)
            author = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip()[:120] or "Inconnu"
            out.append({"title": title, "url": url, "page": ii.get("descriptionurl"),
                        "license": lic, "author": author, "city": city})
            if len(out) >= want:
                return out
    return out


# --------------------------------------------------------------- illustrations
def render_house(seed, w=1200, h=800):
    """Illustration procédurale unique (ciel, maison, arbres, grain)."""
    r = random.Random(seed)
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    top, bot = (r.randint(90, 170), r.randint(150, 210), r.randint(200, 255)), (255, r.randint(200, 245), r.randint(170, 230))
    for y in range(int(h * 0.7)):
        t = y / (h * 0.7)
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3)))
    d.rectangle([0, int(h * 0.7), w, h], fill=(r.randint(60, 130), r.randint(120, 170), r.randint(50, 100)))
    for _ in range(r.randint(1, 4)):
        cx, cy = r.randint(0, w), r.randint(20, int(h * 0.35))
        for _ in range(5):
            rx, ry, ox = r.randint(40, 110), r.randint(20, 45), cx + r.randint(-80, 80)
            d.ellipse([ox - rx, cy - ry, ox + rx, cy + ry], fill=(255, 255, 255))
    hw, hh = r.randint(int(w * .3), int(w * .6)), r.randint(int(h * .22), int(h * .4))
    x0, y1 = r.randint(30, w - hw - 30), int(h * .85) - r.randint(0, 40)
    y0 = y1 - hh
    d.rectangle([x0, y0, x0 + hw, y1], fill=tuple(r.randint(120, 245) for _ in range(3)))
    roof = (r.randint(60, 200), r.randint(30, 90), r.randint(20, 80))
    if r.random() < .5:
        d.polygon([(x0 - 25, y0), (x0 + hw // 2, y0 - r.randint(80, 190)), (x0 + hw + 25, y0)], fill=roof)
    else:
        d.rectangle([x0 - 20, y0 - r.randint(25, 60), x0 + hw + 20, y0], fill=roof)
    cols, rows = r.randint(2, 5), r.randint(1, 3)
    for i in range(cols):
        for j in range(rows):
            wx, wy = x0 + 30 + i * (hw - 60) // cols, y0 + 25 + j * (hh - 50) // rows
            d.rectangle([wx, wy, wx + 42, wy + 52], fill=(r.randint(30, 120), r.randint(90, 190), r.randint(150, 240)),
                        outline=(255, 255, 255), width=4)
    dx = x0 + r.randint(20, hw - 90)
    d.rectangle([dx, y1 - 110, dx + 60, y1], fill=(r.randint(40, 140), r.randint(20, 80), r.randint(10, 60)))
    for _ in range(r.randint(2, 7)):
        tx, ts = r.randint(0, w), r.randint(50, 130)
        ty = int(h * .88) + r.randint(-20, 40)
        d.rectangle([tx - 8, ty - ts, tx + 8, ty], fill=(90, 60, 30))
        d.ellipse([tx - ts // 2, ty - ts * 2, tx + ts // 2, ty - ts // 2 + 20],
                  fill=(r.randint(20, 80), r.randint(100, 180), r.randint(20, 80)))
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    px = img.load()
    for _ in range(w * h // 18):
        x, y = r.randrange(w), r.randrange(h)
        v, c = r.randint(-18, 18), px[x, y]
        px[x, y] = tuple(max(0, min(255, c[k] + v)) for k in range(3))
    return img


# ------------------------------------------------------------------- création
def _store_photo(owner_id, img, credit):
    try:
        return photos.save(owner_id, img, credit)["id"]
    except photos.Duplicate:
        return None  # même règle que pour les hôtes : jamais deux fois la même photo


def demo_host(n):
    email = f"hote-demo-{n}@demo.ndaku.invalid"
    u = one("SELECT id FROM users WHERE email=%s", (email,))
    if u:
        return u["id"]
    return one("""INSERT INTO users (name, email, email_verified, role, verified) VALUES (%s,%s,TRUE,'host',TRUE)
                  RETURNING id""", (["Jean M. (démo)", "Grace K. (démo)", "Patrick I. (démo)"][n % 3], email))["id"]


def _insert_demo_listing(owner, title, desc, deal, pt, city, com, addr, price, bed, bath, m2, furn, r, status,
                         photo_ids):
    """Rattache l'annonce de démo au référentiel. L'avenue de démo est créée « en attente » au nom de l'hôte
    de démo : elle n'apparaît jamais dans les listes publiques du référentiel."""
    c = one("""SELECT co.id AS commune_id, co.lat, co.lng, ci.id AS city_id, pr.id AS province_id, pr.name AS province
               FROM places co JOIN places ci ON ci.id=co.parent_id JOIN places pr ON pr.id=ci.parent_id
               WHERE co.kind='commune' AND co.name=%s AND ci.name=%s""", (com, city))
    m = re.match(r"^(.*?)[ ,]+(\d+)$", addr)
    avenue, number = (m.group(1).strip(), m.group(2)) if m else (addr, str(r.randint(1, 99)))
    av = one("""INSERT INTO places (kind, name, parent_id, source, status, created_by) VALUES ('avenue',%s,%s,'user','pending',%s)
                ON CONFLICT (COALESCE(parent_id, 0), kind, lower(name)) DO UPDATE SET name=EXCLUDED.name RETURNING id""",
             (avenue, c["commune_id"], owner))
    lat, lng = c["lat"] + r.uniform(-0.008, 0.008), c["lng"] + r.uniform(-0.008, 0.008)
    from .listings import street_key
    key = f"{c['commune_id']}|{street_key(avenue)}|{number}|"
    cover = one("SELECT url FROM images WHERE id=%s", (photo_ids[0],))["url"]
    return one("""INSERT INTO listings (owner_id, title, description, deal, ptype, province, city, commune, avenue,
                    house_number, address, province_id, city_id, commune_id, avenue_id, lat, lng, price, bedrooms,
                    bathrooms, surface, furnished, amenities, status, addr_key, is_demo, cover_url)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s) RETURNING id""",
               (owner, title, desc, deal, pt, c["province"], city, com, avenue, number, f"{avenue} n° {number}",
                c["province_id"], c["city_id"], c["commune_id"], av["id"], lat, lng, price, bed, bath, m2, bool(furn),
                json.dumps(r.choice(AMS)), status, key, cover))["id"]


def create_demo(storage, source="illustrations", max_listings=4, status=None, budget_s=40.0):
    """Crée jusqu'à `max_listings` annonces de démo manquantes, dans un budget de temps (limite des
    fonctions Vercel). Chaque annonce est validée dès sa création. Idempotent : rappeler jusqu'à done."""
    status = status or ("pending" if source == "commons" else "active")
    deadline = time.monotonic() + budget_s
    existing = {r["title"] for r in all_("SELECT title FROM listings WHERE is_demo")}
    todo = [x for x in LISTINGS if x[4] not in existing]
    created, skipped, pool, attempted = [], [], {}, 0
    for city, com, deal, pt, title, price, bed, bath, m2, furn, addr in todo:
        if len(created) >= max_listings or time.monotonic() > deadline:
            break
        attempted += 1
        idx = next(i for i, x in enumerate(LISTINGS) if x[4] == title)
        owner = demo_host(idx % 3)
        photo_ids = []
        if source == "commons":
            if city not in pool:
                used = {r["t"] for r in all_("SELECT credit->>'title' AS t FROM images WHERE credit IS NOT NULL")}
                pool[city] = [c for c in commons_candidates(city, 40) if c["title"] not in used]
            while pool[city] and len(photo_ids) < PHOTOS_PER_LISTING and time.monotonic() < deadline:
                c = pool[city].pop(0)
                try:
                    img = af.load_image(_get(c["url"], 15))
                except (OSError, af.ImageRejected):
                    continue
                pid = _store_photo(owner, img, {k: c[k] for k in ("title", "page", "license", "author")})
                if pid:
                    photo_ids.append(pid)
        else:
            k = 0
            while len(photo_ids) < PHOTOS_PER_LISTING and k < 50:
                k += 1
                pid = _store_photo(owner, render_house(idx * 1000 + k + 7), None)
                if pid:
                    photo_ids.append(pid)
        if len(photo_ids) < PHOTOS_PER_LISTING:
            if photo_ids:
                gone = all_("DELETE FROM images WHERE id = ANY(%s) RETURNING storage_key", (photo_ids,))
                db().commit()
                storage.delete([g["storage_key"] for g in gone])
            skipped.append(f"{title} : pas assez de photos libres trouvées pour {city}")
            continue
        r = random.Random(idx)
        desc = DESC.format(t=title, c=com, city=city, s=m2, b=bed, ba=bath,
                           v=r.choice(["à deux pas du centre", "dans une rue résidentielle", "près de l'avenue principale"]))
        if source != "commons":
            desc = desc.replace("illustrée par une photo réelle de", "illustrée par des images générées —")
        lid = _insert_demo_listing(owner, title, desc, deal, pt, city, com, addr, price, bed, bath, m2, furn,
                                   r, status, photo_ids)
        for pos, pid in enumerate(photo_ids):
            run("UPDATE images SET listing_id=%s, position=%s WHERE id=%s", (lid, pos, pid))
        db().commit()
        created.append(title)
    # Terminé quand toute la liste a été tentée dans cet appel (les échecs ne bloquent pas la suite).
    done = attempted == len(todo)
    return {"created": created, "skipped": skipped, "remaining": len(todo) - len(created), "done": done}
