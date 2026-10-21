"""Moteur anti-fraude (unitaire, sans base)."""
import io

import pytest
from PIL import Image, ImageOps

from conftest import jpeg
from ndaku import antifraud as af
from ndaku.demo import render_house

BASE = render_house(1)


def fp_of(img):
    return af.fingerprint(af.load_image(jpeg(img)))


@pytest.mark.parametrize("name,variant", [
    ("recompressée", lambda i: Image.open(io.BytesIO(jpeg(i, 40)))),
    ("redimensionnée", lambda i: i.resize((800, 533))),
    ("miroir", ImageOps.mirror),
    ("recadrée légèrement", lambda i: i.crop((10, 8, 1190, 790))),
    ("format PNG", lambda i: Image.open(io.BytesIO(_png(i))).convert("RGB")),
])
def test_same_photo_variants_are_detected(name, variant):
    assert af.match_image(fp_of(variant(BASE)), fp_of(BASE)), name


def _png(img):
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def test_distinct_photos_never_collide():
    fps = [fp_of(render_house(s)) for s in range(1, 40)]
    for i, a in enumerate(fps):
        for b in fps[i + 1:]:
            assert not af.match_image(a, b)


@pytest.mark.parametrize("raw,why", [
    (b"not an image", "texte"),
    (b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "SVG"),
    (b"GIF89a" + b"\x00" * 100, "GIF"),
    (b"%PDF-1.4\n%...", "PDF"),
])
def test_non_images_rejected(raw, why):
    with pytest.raises(af.ImageRejected):
        af.load_image(raw)


def test_small_blank_and_bomb_rejected():
    with pytest.raises(af.ImageRejected):
        af.load_image(jpeg(Image.new("RGB", (100, 100), "red")))
    with pytest.raises(af.ImageRejected):
        af.load_image(jpeg(Image.new("RGB", (800, 600), "white")))
    # Bombe de décompression : PNG minuscule déclarant 20000×20000 px.
    b = io.BytesIO()
    Image.new("L", (20000, 20000)).save(b, "PNG", optimize=True)
    with pytest.raises(af.ImageRejected):
        af.load_image(b.getvalue())


def test_exif_gps_is_stripped():
    img = BASE.copy()
    exif = Image.Exif()
    exif[0x8825] = {2: (4.0, 19.0, 0.0)}  # GPSInfo
    b = io.BytesIO()
    img.save(b, "JPEG", exif=exif)
    out = af.to_jpeg(af.load_image(b.getvalue()))
    assert not Image.open(io.BytesIO(out)).getexif()


@pytest.mark.parametrize("t", ["Appelez-moi au +243 812 345 678", "écrire à bob@mail.com", "contact WhatsApp",
                               "voir www.arnaque.com", "payez par M-Pesa"])
def test_contact_info_blocked(t):
    assert af.find_contact_info(t)


def test_clean_text_and_price_rules():
    assert not af.find_contact_info("Maison de 180 m², 3 chambres, avenue de la Justice 12")
    comps = [(1000, 100), (1100, 100), (900, 100)]
    assert af.price_anomaly(200, 100, comps)
    assert af.price_anomaly(1000, 100, comps) is None
