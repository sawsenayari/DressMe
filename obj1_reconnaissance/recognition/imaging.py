from __future__ import annotations
import hashlib
import numpy as np
from PIL import Image
try:                                   # photos iPhone (HEIC) : pip install pillow-heif  (facultatif)
    import pillow_heif; pillow_heif.register_heif_opener()
except Exception: pass


def open_rgb(src) -> Image.Image:
    """Ouvre une image ; un PNG transparent est composé sur fond blanc (format du crop partagé)."""
    im = src if isinstance(src, Image.Image) else Image.open(src)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA"); bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im); im = bg
    return im.convert("RGB")


def load_image(src, min_side: int = 384, max_side: int = 1024) -> Image.Image:
    im = open_rgb(src); w, h = im.size; s = min(w, h)
    if s < min_side:
        k = min_side / s; im = im.resize((round(w * k), round(h * k)), Image.LANCZOS)
    if max(im.size) > max_side: im.thumbnail((max_side, max_side), Image.LANCZOS)
    return im


def pad_square(im: Image.Image, fill=(255, 255, 255)) -> Image.Image:
    w, h = im.size; s = max(w, h); bg = Image.new("RGB", (s, s), fill); bg.paste(im, ((s - w) // 2, (s - h) // 2)); return bg


def normalise_crop(im: Image.Image, size: int = 512) -> Image.Image:
    """Format du contrat : carré, fond blanc, 512 px."""
    return pad_square(open_rgb(im)).resize((size, size), Image.LANCZOS)


def img_key(im: Image.Image) -> str:
    return hashlib.md5(im.resize((64, 64)).tobytes()).hexdigest()[:16]


def check_crop(src, min_px: int = 224) -> dict:
    """Contrôle qualité du crop reçu (tâche 2) : renvoie {ok, reasons, coverage}.  Bloquant => la fiche sera 'needs_review'."""
    im = open_rgb(src); a = np.asarray(im); mask = ~(a >= 240).all(-1); cov = float(mask.mean()); reasons = []
    if min(im.size) < min_px: reasons.append("low_resolution")
    if cov < 0.03: reasons.append("garment_too_small_or_empty")        # (un vêtement blanc sur blanc déclenche aussi ceci)
    if cov > 0.92: reasons.append("background_not_removed")
    return dict(ok=not reasons, reasons=reasons, coverage=round(cov, 3), size=im.size)
