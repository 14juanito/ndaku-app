"""Mécanismes anti-fraude de Ndaku.

Images : empreinte exacte (pixels normalisés) + empreintes perceptuelles
(dHash, pHash) comparées aussi en miroir. Texte : détection des coordonnées
hors-plateforme, quasi-doublons de description, conflit d'adresse.
Prix : écart au prix médian du marché local.
"""
import hashlib
import io
import re
import statistics
import unicodedata

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

Image.MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MIN_W, MIN_H = 480, 320
MAX_SIDE = 1600
DHASH_MAX, PHASH_MAX = 6, 8  # distances de Hamming (sur 64 bits) = quasi-doublon
RISK_PENDING_THRESHOLD = 40


class ImageRejected(ValueError):
    pass


# --------------------------------------------------------------------- images
def _dct_matrix(n):
    k = np.arange(n)[:, None]
    i = np.arange(n)[None, :]
    m = np.cos(np.pi * (2 * i + 1) * k / (2 * n))
    m[0] *= 1 / np.sqrt(2)
    return m * np.sqrt(2 / n)


_DCT32 = _dct_matrix(32)


def _bits_to_int(bits):
    return int("".join("1" if b else "0" for b in bits.flatten()), 2)


def _dhash(img):
    g = np.asarray(img.convert("L").resize((9, 8), Image.LANCZOS), dtype=np.float32)
    return _bits_to_int(g[:, 1:] > g[:, :-1])


def _phash(img):
    g = np.asarray(img.convert("L").resize((32, 32), Image.LANCZOS), dtype=np.float32)
    low = (_DCT32 @ g @ _DCT32.T)[:8, :8]
    return _bits_to_int(low > np.median(low.flatten()[1:]))


def load_image(raw, min_w=MIN_W, min_h=MIN_H):
    """Décode et valide un fichier image ; retourne une image RGB normalisée."""
    try:
        # Seuls les décodeurs JPEG/PNG/WebP sont autorisés (surface d'attaque réduite).
        probe = Image.open(io.BytesIO(raw), formats=sorted(ALLOWED_FORMATS))
        if probe.width * probe.height > Image.MAX_IMAGE_PIXELS:  # bombe de décompression
            raise ImageRejected("Image aux dimensions excessives.")
        probe.verify()
        img = Image.open(io.BytesIO(raw), formats=sorted(ALLOWED_FORMATS))
        img = ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError):
        raise ImageRejected("Fichier illisible ou format non accepté (JPEG, PNG ou WebP uniquement).")
    if img.width < min_w or img.height < min_h:
        raise ImageRejected(f"Image trop petite (minimum {min_w}×{min_h}px).")
    if np.asarray(img.convert("L")).std() < 6:
        raise ImageRejected("Image quasi uniforme (vide ou placeholder) refusée.")
    return img


def fingerprint(img):
    # Taille normalisée : une simple recompression/redimensionnement ne change pas l'empreinte exacte.
    norm = img.resize((256, 256), Image.LANCZOS)
    mirror = ImageOps.mirror(img)
    return {
        "sha": hashlib.sha256(norm.tobytes()).hexdigest(),
        "dhash": _dhash(img),
        "phash": _phash(img),
        "dhash_m": _dhash(mirror),
        "phash_m": _phash(mirror),
    }


def signed64(x):
    """Entier 64 bits non signé → BIGINT PostgreSQL (signé)."""
    return x - (1 << 64) if x >= (1 << 63) else x


def hamming(a, b):
    return (a ^ b).bit_count()


def match_image(fp, other):
    """`other` = empreinte (sha, dhash, phash en int ou hex). Retourne 'exact', 'similar' ou None."""
    if fp["sha"] == other["sha"]:
        return "exact"
    od, op = (int(other[k], 16) if isinstance(other[k], str) else other[k] & ((1 << 64) - 1)
              for k in ("dhash", "phash"))
    for d, p in ((fp["dhash"], fp["phash"]), (fp["dhash_m"], fp["phash_m"])):
        if hamming(d, od) <= DHASH_MAX and hamming(p, op) <= PHASH_MAX:
            return "similar"
    return None


def to_jpeg(img):
    if max(img.size) > MAX_SIDE:
        img = img.copy()
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=85, optimize=True)  # ré-encodage : métadonnées/EXIF supprimées
    return out.getvalue()


# ---------------------------------------------------------------------- texte
def norm_text(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s).split()


def addr_key(city, commune, address):
    return "|".join(" ".join(norm_text(x)) for x in (city, commune, address))


_CONTACT = re.compile(
    r"(\+?\d[\d\s().-]{7,}\d)|([\w.+-]+@[\w-]+\.\w+)|(https?://|www\.)|"
    r"\b(whats?app|telegram|wa\.me|messenger|facebook|mpesa|m-pesa|airtel money|orange money|western union)\b",
    re.I,
)


def find_contact_info(text):
    m = _CONTACT.search(text or "")
    return m.group(0).strip() if m else None


def shingles(text, k=3):
    w = norm_text(text)
    return {" ".join(w[i:i + k]) for i in range(max(1, len(w) - k + 1))}


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


# ----------------------------------------------------------------------- prix
def price_anomaly(price, surface, comparables):
    """comparables : liste de (prix, surface) d'annonces actives similaires (même ville et type d'offre)."""
    ppm = [p / s for p, s in comparables if s]
    if len(ppm) < 3 or not surface:
        return None
    med = statistics.median(ppm)
    ratio = (price / surface) / med
    if ratio < 0.4:
        return f"Prix {round((1 - ratio) * 100)}% sous la médiane locale (« trop beau pour être vrai »)"
    if ratio > 3:
        return f"Prix {ratio:.1f}× supérieur à la médiane locale"
    return None
