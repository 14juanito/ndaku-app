"""Référentiel géographique de départ : les 26 provinces de la RDC, leurs principales villes et les communes
connues avec certitude. Les quartiers et avenues sont importés depuis OpenStreetMap (osm.py) et complétés
par les propositions des hôtes (validées en modération). Coordonnées : centres approximatifs, utilisés
uniquement pour centrer la carte."""

# province: {ville: (lat, lng, [communes] ou {commune: (lat, lng)})}
KINSHASA_COMMUNES = {
    "Bandalungwa": (-4.340, 15.287), "Barumbu": (-4.312, 15.323), "Bumbu": (-4.370, 15.290),
    "Gombe": (-4.302, 15.300), "Kalamu": (-4.343, 15.313), "Kasa-Vubu": (-4.338, 15.302),
    "Kimbanseke": (-4.430, 15.400), "Kinshasa": (-4.322, 15.312), "Kintambo": (-4.330, 15.270),
    "Kisenso": (-4.410, 15.340), "Lemba": (-4.400, 15.320), "Limete": (-4.360, 15.340),
    "Lingwala": (-4.320, 15.300), "Makala": (-4.380, 15.300), "Maluku": (-4.070, 15.550),
    "Masina": (-4.390, 15.400), "Matete": (-4.380, 15.340), "Mont-Ngafula": (-4.450, 15.270),
    "Ndjili": (-4.390, 15.370), "Ngaba": (-4.380, 15.320), "Ngaliema": (-4.370, 15.250),
    "Ngiri-Ngiri": (-4.350, 15.300), "Nsele": (-4.370, 15.550), "Selembao": (-4.380, 15.280),
}

GEO = {
    "Kinshasa": {"Kinshasa": (-4.325, 15.322, KINSHASA_COMMUNES)},
    "Kongo-Central": {"Matadi": (-5.817, 13.450, ["Matadi", "Mvuzi", "Nzanza"]),
                      "Boma": (-5.850, 13.050, ["Kabondo", "Kalamu", "Nzadi"]),
                      "Mbanza-Ngungu": (-5.250, 14.860, []), "Muanda": (-5.930, 12.350, [])},
    "Kwango": {"Kenge": (-4.800, 16.900, [])},
    "Kwilu": {"Bandundu": (-3.320, 17.380, []), "Kikwit": (-5.040, 18.820, ["Kazamba", "Lukemi", "Lukolela", "Nzinda"])},
    "Mai-Ndombe": {"Inongo": (-1.950, 18.270, [])},
    "Kasaï": {"Tshikapa": (-6.420, 20.800, [])},
    "Kasaï-Central": {"Kananga": (-5.900, 22.420, ["Kananga", "Katoka", "Lukonga", "Ndesha", "Nganza"])},
    "Kasaï-Oriental": {"Mbuji-Mayi": (-6.130, 23.600, ["Bipemba", "Dibindi", "Diulu", "Kanshi", "Muya"])},
    "Lomami": {"Kabinda": (-6.130, 24.480, []), "Mwene-Ditu": (-7.000, 23.450, [])},
    "Sankuru": {"Lusambo": (-4.970, 23.440, [])},
    "Maniema": {"Kindu": (-2.950, 25.920, ["Alunguli", "Kasuku", "Mikelenge"])},
    "Sud-Kivu": {"Bukavu": (-2.500, 28.860, ["Bagira", "Ibanda", "Kadutu"]), "Uvira": (-3.400, 29.140, [])},
    "Nord-Kivu": {"Goma": (-1.680, 29.220, ["Goma", "Karisimbi"]),
                  "Butembo": (0.140, 29.290, ["Bulengera", "Kimemi", "Mususa", "Vulamba"]),
                  "Beni": (0.490, 29.470, ["Beu", "Bungulu", "Mulekera", "Ruwenzori"])},
    "Ituri": {"Bunia": (1.560, 30.250, ["Mbunya", "Nyakasanza", "Shari"])},
    "Haut-Uele": {"Isiro": (2.770, 27.620, [])},
    "Bas-Uele": {"Buta": (2.790, 24.730, [])},
    "Tshopo": {"Kisangani": (0.520, 25.200, ["Kabondo", "Kisangani", "Lubunga", "Makiso", "Mangobo", "Tshopo"])},
    "Tshuapa": {"Boende": (-0.280, 20.880, [])},
    "Mongala": {"Lisala": (2.150, 21.510, [])},
    "Nord-Ubangi": {"Gbadolite": (4.280, 21.000, [])},
    "Sud-Ubangi": {"Gemena": (3.250, 19.770, []), "Zongo": (4.340, 18.590, [])},
    "Équateur": {"Mbandaka": (0.050, 18.260, ["Mbandaka", "Wangata"])},
    "Haut-Lomami": {"Kamina": (-8.740, 24.990, [])},
    "Lualaba": {"Kolwezi": (-10.720, 25.470, ["Dilala", "Manika"])},
    "Haut-Katanga": {"Lubumbashi": (-11.660, 27.480, ["Annexe", "Kamalondo", "Kampemba", "Katuba", "Kenya",
                                                       "Lubumbashi", "Rwashi"]),
                     "Likasi": (-10.980, 26.730, ["Kikula", "Likasi", "Panda", "Shituru"])},
    "Tanganyika": {"Kalemie": (-5.950, 29.190, [])},
}

# Variantes d'orthographe rencontrées dans OpenStreetMap (import des quartiers/avenues).
OSM_ALIASES = {"Ndjili": ["N'djili", "N'Djili", "Ndjili"], "Kasa-Vubu": ["Kasa-Vubu", "Kasavubu"],
               "Ngiri-Ngiri": ["Ngiri-Ngiri", "Ngiri Ngiri"], "Rwashi": ["Rwashi", "Ruashi"],
               "Mont-Ngafula": ["Mont-Ngafula", "Mont Ngafula"]}


def seed(con):
    """Insère le référentiel s'il est vide (idempotent)."""
    if con.execute("SELECT 1 FROM places LIMIT 1").fetchone():
        return
    ins = ("INSERT INTO places (kind, name, parent_id, lat, lng) VALUES (%s,%s,%s,%s,%s) "
           "ON CONFLICT DO NOTHING RETURNING id")
    for prov, cities in GEO.items():
        plat, plng = next(iter(cities.values()))[:2]
        pid = con.execute(ins, ("province", prov, None, plat, plng)).fetchone()["id"]
        for city, (lat, lng, communes) in cities.items():
            cid = con.execute(ins, ("city", city, pid, lat, lng)).fetchone()["id"]
            items = communes.items() if isinstance(communes, dict) else ((c, (lat, lng)) for c in communes)
            for name, (clat, clng) in items:
                con.execute(ins, ("commune", name, cid, clat, clng))
