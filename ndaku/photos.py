"""Enregistrement d'une photo avec contrôle de doublon — chemin unique pour les uploads des hôtes
et l'import de démo (mêmes seuils, même verrou)."""
import json

from flask import current_app

from . import antifraud as af
from .db import db, one, run

DUP_SQL = """
SELECT i.id, i.owner_id, i.listing_id, i.sha = %(sha)s AS exact FROM images i
WHERE i.sha = %(sha)s
   OR (bit_count((i.dhash # %(d)s)::bit(64)) <= %(dmax)s AND bit_count((i.phash # %(p)s)::bit(64)) <= %(pmax)s)
   OR (bit_count((i.dhash # %(dm)s)::bit(64)) <= %(dmax)s AND bit_count((i.phash # %(pm)s)::bit(64)) <= %(pmax)s)
ORDER BY exact DESC LIMIT 1"""
LOCK_KEY = 7001


class Duplicate(Exception):
    def __init__(self, clash):
        super().__init__("duplicate")
        self.clash = clash


def save(owner_id, img, credit=None):
    """Vérifie l'unicité puis stocke la photo. Retourne la ligne {id, url} ou lève Duplicate.

    Le verrou ne couvre que la vérification + l'insertion (transaction courte) ; l'envoi vers
    le stockage se fait après, verrou relâché, puis l'URL est renseignée."""
    fp = af.fingerprint(img)
    s = {k: af.signed64(fp[k]) for k in ("dhash", "phash", "dhash_m", "phash_m")}
    con = db()
    con.commit()  # isole cette transaction courte de ce qui précède dans la requête
    run("SELECT pg_advisory_xact_lock(%s)", (LOCK_KEY,))
    clash = one(DUP_SQL, {"sha": fp["sha"], "d": s["dhash"], "p": s["phash"], "dm": s["dhash_m"], "pm": s["phash_m"],
                          "dmax": af.DHASH_MAX, "pmax": af.PHASH_MAX})
    if clash:
        con.rollback()
        raise Duplicate(clash)
    row = one("""INSERT INTO images (owner_id, url, storage_key, sha, dhash, phash, dhash_m, phash_m, credit)
                 VALUES (%s,'','',%s,%s,%s,%s,%s,%s) RETURNING id""",
              (owner_id, fp["sha"], s["dhash"], s["phash"], s["dhash_m"], s["phash_m"],
               json.dumps(credit) if credit else None))
    con.commit()  # relâche le verrou : la photo est réservée (sha UNIQUE) avant l'envoi réseau
    try:
        url, key = current_app.config["STORAGE"].put(af.to_jpeg(img))
    except Exception:
        run("DELETE FROM images WHERE id=%s", (row["id"],))
        con.commit()
        raise
    run("UPDATE images SET url=%s, storage_key=%s WHERE id=%s", (url, key, row["id"]))
    con.commit()
    return {"id": row["id"], "url": url}
