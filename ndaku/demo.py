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
import zlib

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

# Professionnels de démonstration (noms fictifs, marqués « démo », adresses e-mail non routables).
DEMO_AGENCIES = {
    "kpi": {"name": "Kin Prestige Immobilier (démo)", "city": "Kinshasa", "color": (242, 97, 34),
            "description": "Agence de démonstration : location et vente de villas et appartements à Gombe, Ngaliema et "
                           "Limete. Visites accompagnées, état des lieux contradictoire, aucun frais avant visite.",
            "address": "Boulevard du 30 Juin (adresse fictive), Gombe", "phone": "+243 000 000 001",
            "team": [("Sarah N. (démo)", "manager", "Gérante"), ("Didier K. (démo)", "agent", "Agent senior"),
                     ("Ruth M. (démo)", "agent", "Agente location")]},
    "kh": {"name": "Katanga Habitat (démo)", "city": "Lubumbashi", "color": (24, 112, 140),
           "description": "Agence de démonstration à Lubumbashi : maisons familiales et parcelles clôturées au Golf, "
                          "à Kampemba et à Kenya. Gestion locative pour propriétaires.",
           "address": "Avenue Lumumba (adresse fictive), Lubumbashi", "phone": "+243 000 000 002",
           "team": [("Joseph T. (démo)", "manager", "Gérant"), ("Esther B. (démo)", "agent", "Agente")]},
    "km": {"name": "Kivu Maisons (démo)", "city": "Goma", "color": (46, 125, 50),
           "description": "Agence de démonstration à Goma : villas avec vue sur le lac Kivu et maisons familiales.",
           "address": "Avenue du Lac (adresse fictive), Goma", "phone": "+243 000 000 003",
           "team": [("Aline M. (démo)", "manager", "Gérante")]},
}
DEMO_AGENTS = {"ind1": ("Christian L. (démo)", "Agent indépendant depuis 8 ans à Kinshasa (Kintambo, Bandalungwa, Lingwala). "
                                              "Je visite chaque bien avant de le publier."),
               "ind2": ("Nadège O. (démo)", "Agente indépendante : studios et appartements meublés pour étudiants "
                                            "et jeunes actifs à Lemba et Ngaba.")}
DEMO_CLIENTS = ["Patience K. (démo)", "Merveille T. (démo)", "Gédéon B. (démo)"]
# (ville, commune, offre, type, titre, prix, ch., sdb, m², meublé, adresse, professionnel, mandat, honoraires, en avant)
PRO_LISTINGS = [
    ("Kinshasa", "Gombe", "location", "appartement", "Penthouse meublé avec terrasse au centre-ville", 2800, 3, 3, 190, 1, "Avenue des Aviateurs 7", "kpi/1", "exclusif", "1 mois de loyer", True),
    ("Kinshasa", "Ngaliema", "vente", "villa", "Villa contemporaine 5 chambres, titre foncier", 320000, 5, 5, 520, 0, "Avenue Pumbu 33", "kpi/0", "exclusif", "3 % du prix de vente", True),
    ("Kinshasa", "Limete", "location", "maison", "Maison 3 chambres sécurisée, quartier résidentiel", 950, 3, 2, 210, 0, "10e rue Limete Résidentiel 4", "kpi/2", "simple", "1 mois de loyer", False),
    ("Kinshasa", "Gombe", "location", "appartement", "Appartement 2 chambres, immeuble avec groupe électrogène", 1400, 2, 2, 110, 1, "Avenue Kalemie 21", "kpi/2", "simple", "1 mois de loyer", False),
    ("Lubumbashi", "Kampemba", "location", "maison", "Maison familiale avec grande cour à Kampemba", 700, 4, 2, 240, 0, "Avenue des Chutes 15", "kh/0", "exclusif", "1 mois de loyer", True),
    ("Lubumbashi", "Kenya", "vente", "terrain", "Parcelle clôturée 30 x 40 avec titre", 45000, 0, 0, 1200, 0, "Avenue Kilela 8", "kh/1", "simple", "5 % du prix de vente", False),
    ("Lubumbashi", "Lubumbashi", "location", "villa", "Villa au quartier Golf avec piscine", 2600, 5, 4, 450, 1, "Avenue Mama Yemo 40", "kh/1", "exclusif", "1 mois de loyer", False),
    ("Goma", "Goma", "location", "maison", "Maison 3 chambres à deux pas du lac", 800, 3, 2, 180, 0, "Avenue Kituku 6", "km/0", "simple", "1 mois de loyer", True),
    ("Goma", "Karisimbi", "vente", "villa", "Villa avec jardin et vue sur le Nyiragongo", 135000, 4, 3, 350, 0, "Avenue de la Paix 18", "km/0", "exclusif", "3 % du prix de vente", False),
    ("Kinshasa", "Kintambo", "location", "maison", "Maison 4 chambres avec parking pour 2 voitures", 1100, 4, 3, 260, 0, "Avenue Nguma 12", "ind1", "proprietaire", "Aucun", True),
    ("Kinshasa", "Bandalungwa", "location", "appartement", "Appartement 2 chambres refait à neuf", 480, 2, 1, 85, 0, "Avenue Lubudi 26", "ind1", "simple", "1 mois de loyer", False),
    ("Kinshasa", "Lemba", "location", "studio", "Studio meublé près de l'université", 250, 1, 1, 30, 1, "Avenue By-pass 41", "ind2", "simple", "50 % du premier loyer", True),
    ("Kinshasa", "Ngaba", "location", "appartement", "Appartement meublé pour colocation étudiante", 420, 2, 1, 70, 1, "Avenue Mbuji-Mayi 9", "ind2", "simple", "1 mois de loyer", False),
]
REVIEWS = [(5, "Agent très professionnel, la maison correspondait exactement aux photos."),
           (4, "Visite à l'heure et bien organisée. Bon suivi après la visite."),
           (5, "Rien à payer avant la visite, tout s'est passé par la messagerie Ndaku. Je recommande."),
           (3, "Bien conforme mais réponses un peu lentes au début.")]


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


# -------------------------------------------------------------- portraits et logos
def render_avatar(seed, size=400):
    """Portrait illustré (pas une vraie personne) : fond, visage, cheveux, vêtement."""
    r = random.Random(seed)
    img = Image.new("RGB", (size, size), tuple(r.randint(150, 235) for _ in range(3)))
    d = ImageDraw.Draw(img)
    skin = r.choice([(92, 58, 38), (120, 78, 50), (141, 94, 62), (166, 115, 78), (78, 50, 34)])
    cloth = tuple(r.randint(20, 200) for _ in range(3))
    d.ellipse([size * .12, size * .66, size * .88, size * 1.3], fill=cloth)
    d.rectangle([size * .42, size * .55, size * .58, size * .72], fill=skin)
    d.ellipse([size * .28, size * .18, size * .72, size * .66], fill=skin)
    hair = (r.randint(10, 40),) * 3
    if r.random() < .5:
        d.chord([size * .26, size * .12, size * .74, size * .5], 180, 360, fill=hair)
    else:
        d.ellipse([size * .24, size * .1, size * .76, size * .42], fill=hair)
        d.rectangle([size * .24, size * .26, size * .3, size * .5], fill=hair)
        d.rectangle([size * .7, size * .26, size * .76, size * .5], fill=hair)
    for ex in (.41, .59):
        d.ellipse([size * (ex - .025), size * .4, size * (ex + .025), size * .45], fill=(25, 20, 20))
    d.arc([size * .43, size * .48, size * .57, size * .57], 20, 160, fill=(60, 30, 30), width=max(2, size // 100))
    return img


def render_logo(name, color, size=400):
    """Logo fictif : carré arrondi coloré, maison stylisée et initiales."""
    img = Image.new("RGB", (size, size), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([20, 20, size - 20, size - 20], radius=70, fill=color)
    w = size
    d.polygon([(w * .25, w * .48), (w * .5, w * .24), (w * .75, w * .48)], fill=(255, 255, 255))
    d.rectangle([w * .32, w * .46, w * .68, w * .7], fill=(255, 255, 255))
    d.rectangle([w * .45, w * .56, w * .55, w * .7], fill=color)
    initials = "".join(p[0] for p in re.sub(r"\(.*?\)", "", name).split()[:3]).upper()
    try:
        from PIL import ImageFont
        font = ImageFont.load_default(size=int(w * .13))
    except (TypeError, OSError):
        font = None
    d.text((w * .5, w * .82), initials, fill=(255, 255, 255), anchor="mm", font=font)
    return img


def _put_image(storage, img):
    try:
        return storage.put(af.to_jpeg(img), folder="avatars")
    except Exception:  # noqa: BLE001 — stockage indisponible : la démo reste utilisable sans image
        return None, None


def _demo_user(storage, name, email, role, seed, **extra):
    u = one("SELECT id, avatar_url FROM users WHERE email=%s", (email,))
    if not u:
        u = one(f"""INSERT INTO users (name, email, email_verified, role, verified{''.join(', ' + k for k in extra)})
                    VALUES (%s,%s,TRUE,%s,TRUE{', %s' * len(extra)}) RETURNING id, avatar_url""",
                (name, email, role, *extra.values()))
    if not u["avatar_url"]:
        url, key = _put_image(storage, render_avatar(seed))
        if url:
            run("UPDATE users SET avatar_url=%s, avatar_key=%s WHERE id=%s", (url, key, u["id"]))
    return u["id"]


def ensure_demo_pros(storage):
    """Agences, agents et clients de démonstration (idempotent). Renvoie {clé: (id utilisateur, id agence)}."""
    out = {}
    for key, a in DEMO_AGENCIES.items():
        ag = one("SELECT id, logo_url FROM agencies WHERE slug=%s", (f"demo-{key}",))
        if not ag:
            ag = one("""INSERT INTO agencies (slug, name, description, phone, address, city, rccm, id_nat, docs_note, is_demo)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE) RETURNING id, logo_url""",
                     (f"demo-{key}", a["name"], a["description"], a["phone"], a["address"], a["city"],
                      f"DEMO-RCCM-{key.upper()}", f"DEMO-IDNAT-{key.upper()}", "Agence de démonstration (fictive)."))
        if not ag["logo_url"]:
            url, k = _put_image(storage, render_logo(a["name"], a["color"]))
            if url:
                run("UPDATE agencies SET logo_url=%s, logo_key=%s WHERE id=%s", (url, k, ag["id"]))
        for i, (name, role, title) in enumerate(a["team"]):
            uid = _demo_user(storage, name, f"agent-{key}-{i}@demo.ndaku.invalid", "agent", zlib.crc32(f"{key}{i}".encode()) % 10**6,
                             bio=f"{title} chez {a['name']}.")
            run("""INSERT INTO agency_members (agency_id, user_id, role, title) VALUES (%s,%s,%s,%s)
                   ON CONFLICT DO NOTHING""", (ag["id"], uid, role, title))
            out[f"{key}/{i}"] = (uid, ag["id"])
    for key, (name, bio) in DEMO_AGENTS.items():
        uid = _demo_user(storage, name, f"{key}@demo.ndaku.invalid", "agent", zlib.crc32(key.encode()) % 10**6, bio=bio,
                         agent_status="approved")
        out[key] = (uid, None)
    for n in range(3):  # photos de profil des hôtes de démo existants
        uid = demo_host(n)
        if not one("SELECT avatar_url FROM users WHERE id=%s", (uid,))["avatar_url"]:
            url, k = _put_image(storage, render_avatar(9000 + n))
            if url:
                run("UPDATE users SET avatar_url=%s, avatar_key=%s WHERE id=%s", (url, k, uid))
    out["clients"] = [_demo_user(storage, name, f"client-demo-{i}@demo.ndaku.invalid", "client", 7000 + i)
                      for i, name in enumerate(DEMO_CLIENTS)]
    return out


def _demo_reviews(lid, owner, clients, r):
    """Quelques avis de démonstration (comptes clients de démo), compteurs tenus à jour."""
    for cid in r.sample(clients, k=r.randint(1, 2)):
        rating, comment = r.choice(REVIEWS)
        if one("""INSERT INTO host_reviews (host_id, user_id, rating, comment) VALUES (%s,%s,%s,%s)
                  ON CONFLICT DO NOTHING RETURNING id""", (owner, cid, rating, comment)):
            run("UPDATE users SET host_rating_sum=host_rating_sum+%s, host_rating_count=host_rating_count+1 WHERE id=%s",
                (rating, owner))
        if one("""INSERT INTO reviews (listing_id, user_id, rating, comment) VALUES (%s,%s,%s,%s)
                  ON CONFLICT DO NOTHING RETURNING id""", (lid, cid, rating, comment)):
            run("UPDATE listings SET rating_sum=rating_sum+%s, rating_count=rating_count+1 WHERE id=%s", (rating, lid))


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
                    bathrooms, surface, furnished, amenities, status, addr_key, is_demo, cover_url,
                    elec_score, water_score, access_score, access_type, rain_access)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s,
                          %s,%s,%s,%s,%s) RETURNING id""",
               (owner, title, desc, deal, pt, c["province"], city, com, avenue, number, f"{avenue} n° {number}",
                c["province_id"], c["city_id"], c["commune_id"], av["id"], lat, lng, price, bed, bath, m2, bool(furn),
                json.dumps(r.choice(AMS)), status, key, cover, r.randint(3, 9), r.randint(4, 10), r.randint(4, 10),
                r.choice(("goudron", "pavee", "terre", "sable")), r.random() < 0.75))["id"]


def create_demo(storage, source="illustrations", max_listings=4, status=None, budget_s=40.0):
    """Crée jusqu'à `max_listings` annonces de démo manquantes, dans un budget de temps (limite des
    fonctions Vercel). Chaque annonce est validée dès sa création. Idempotent : rappeler jusqu'à done."""
    status = status or ("pending" if source == "commons" else "active")
    deadline = time.monotonic() + budget_s
    existing = {r["title"] for r in all_("SELECT title FROM listings WHERE is_demo")}
    specs = [(*x, None, None, None, False) for x in LISTINGS] + list(PRO_LISTINGS)
    todo = [x for x in specs if x[4] not in existing]
    pros = ensure_demo_pros(storage)
    db().commit()
    created, skipped, pool, attempted = [], [], {}, 0
    for city, com, deal, pt, title, price, bed, bath, m2, furn, addr, pro, mandate, fee, featured in todo:
        if len(created) >= max_listings or time.monotonic() > deadline:
            break
        attempted += 1
        idx = next(i for i, x in enumerate(specs) if x[4] == title)
        owner, agency_id = pros[pro] if pro else (demo_host(idx % 3), None)
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
        if pro:
            run("UPDATE listings SET agency_id=%s, mandate=%s, agency_fee=%s, featured=%s WHERE id=%s",
                (agency_id, mandate, fee, featured, lid))
        _demo_reviews(lid, owner, pros["clients"], r)
        db().commit()
        created.append(title)
    # Terminé quand toute la liste a été tentée dans cet appel (les échecs ne bloquent pas la suite).
    done = attempted == len(todo)
    return {"created": created, "skipped": skipped, "remaining": len(todo) - len(created), "done": done}
