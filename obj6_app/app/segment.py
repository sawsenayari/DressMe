"""Isole chaque vêtement d'une photo portée (SegFormer « clothes », Hugging Face) : découpe + fond blanc."""
import base64, importlib.util, io, os
import numpy as np
from PIL import Image

MODEL_ID = "mattmdjaga/segformer_b2_clothes"
PARTS = {"haut": ["Upper-clothes"], "bas": ["Pants", "Skirt"], "robe": ["Dress"], "chaussures": ["Left-shoe", "Right-shoe"],
         "sac": ["Bag"], "ceinture": ["Belt"], "chapeau": ["Hat"], "écharpe": ["Scarf"], "lunettes": ["Sunglasses"]}
SLOT_PARTS = {"top": ["haut"], "outer": ["haut"], "bottom": ["bas"], "onepiece": ["robe", "haut"], "footwear": ["chaussures"],
              "accessory": ["sac", "ceinture", "chapeau", "écharpe", "lunettes"]}
PERSON = ["Face", "Hair", "Left-arm", "Right-arm", "Left-leg", "Right-leg"]
_st = {}

def _has(m): return importlib.util.find_spec(m) is not None

def available(): return _has("transformers") or _has("rembg")

def _segment(img):
    import torch
    from transformers import AutoModelForSemanticSegmentation, SegformerImageProcessor
    if not _st:
        _st["proc"] = SegformerImageProcessor.from_pretrained(MODEL_ID)
        _st["m"] = AutoModelForSemanticSegmentation.from_pretrained(MODEL_ID).eval()
    with torch.no_grad():
        lg = _st["m"](**_st["proc"](images=img, return_tensors="pt")).logits
        up = torch.nn.functional.interpolate(lg, size=img.size[::-1], mode="bilinear", align_corners=False)
    return up.argmax(1)[0].numpy(), _st["m"].config.id2label

def _cut(img, mask, pad=.04):
    ys, xs = np.where(mask); y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    py, px = int((y1 - y0) * pad), int((x1 - x0) * pad)
    y0, y1, x0, x1 = max(0, y0 - py), min(mask.shape[0], y1 + py), max(0, x0 - px), min(mask.shape[1], x1 + px)
    a = np.asarray(img.convert("RGB"))[y0:y1, x0:x1].copy(); a[~mask[y0:y1, x0:x1]] = 255   # tout ce qui n'est pas le vêtement -> blanc
    return Image.fromarray(a)

def split(img, seg, id2label, min_area=.015):
    """(photo portée ?, {pièce: image découpée}) triées de la plus grande à la plus petite."""
    n2i = {v: k for k, v in id2label.items()}; tot = seg.size
    worn = bool(sum((seg == n2i[n]).sum() for n in PERSON if n in n2i) / tot >= .02)
    out = []
    for part, labels in PARTS.items():
        m = np.isin(seg, [n2i[l] for l in labels if l in n2i])
        if m.sum() / tot >= min_area: out.append((m.sum(), part, _cut(img, m)))
    return worn, {p: c for _, p, c in sorted(out, key=lambda x: -x[0])}

def cutout(img):
    """Photo à plat sur fond chargé (lit, sol…) : isole l'objet principal (U²-Net via rembg), garde la plus grande zone, fond blanc."""
    from rembg import new_session, remove
    from scipy import ndimage as ndi
    if "rembg" not in _st: _st["rembg"] = new_session(os.getenv("DRESSME_REMBG_MODEL", "u2netp"))
    small = img.convert("RGB"); small.thumbnail((768, 768))
    m = ndi.binary_opening(np.asarray(remove(small, session=_st["rembg"], only_mask=True)) > 128, iterations=2)
    lab, n = ndi.label(m)
    if n == 0: return img
    big = ndi.binary_fill_holes(lab == int(np.argmax(ndi.sum(m, lab, range(1, n + 1)))) + 1)
    return _cut(small, big) if big.mean() >= .05 else img   # rien de net : on garde la photo telle quelle

def extract_parts(img, want_slot=None, cut_flat=True):
    """Photo à plat (sans personne) : inchangée. Photo portée : pièces découpées (ou la seule pièce du type voulu)."""
    flat = lambda: {"photo": cutout(img) if cut_flat and _has("rembg") else img}
    if not _has("transformers"): return False, flat()
    seg, id2l = _segment(img); worn, parts = split(img, seg, id2l)
    if not worn or not parts: return False, flat()
    if want_slot:
        parts = dict(list({k: v for k, v in parts.items() if k in SLOT_PARTS.get(want_slot, [])}.items())[:1])
    return True, parts

def thumb(im, w=96, h=120):
    im = im.copy(); im.thumbnail((w, h)); bg = Image.new("RGB", (w, h), "white"); bg.paste(im, ((w - im.width) // 2, (h - im.height) // 2))
    buf = io.BytesIO(); bg.save(buf, "JPEG", quality=80)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
