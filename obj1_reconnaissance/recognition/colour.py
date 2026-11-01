"""Témoin de couleur par pixels (expérimental).  La couleur est l'attribut le plus faible (72,5 % sur le catalogue ;
61-62 % dans les autres fiches). Sur un crop à fond blanc, un histogramme HSV est un second avis indépendant du LLM.
Règles écrites à la main, NON validées : ne sert qu'à nourrir la confiance (et, si activé, la couleur secondaire)."""
from __future__ import annotations
import numpy as np
from PIL import Image
from .imaging import open_rgb

NAMES = ["black", "white", "grey", "beige", "brown", "red", "orange", "yellow", "green", "blue", "purple", "pink"]


def _classify(h, s, v):
    h = h * 360.0 / 255.0; s = s / 255.0; v = v / 255.0
    conds = [v < 0.18, (s < 0.12) & (v >= 0.85), s < 0.12,
             (h >= 20) & (h < 60) & (s < 0.35) & (v >= 0.6), (h >= 8) & (h < 50) & (v < 0.6),
             (h < 15) | (h >= 345), h < 40, h < 70, h < 165, h < 255, h < 300]
    return np.select(conds, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10], default=11)   # 11 = pink


def dominant_colours(src, top: int = 2) -> list[tuple[str, float]]:
    im = open_rgb(src); rgb = np.asarray(im); mask = ~(rgb >= 240).all(-1)
    if mask.mean() < 0.02: return [("white", 1.0)]
    hsv = np.asarray(im.convert("HSV"))[mask]
    idx = _classify(hsv[:, 0].astype(float), hsv[:, 1].astype(float), hsv[:, 2].astype(float))
    share = np.bincount(idx, minlength=len(NAMES)) / len(idx); order = np.argsort(-share)
    out = [(NAMES[i], float(share[i])) for i in order[:max(top, 3)] if share[i] > 0.02]
    if len(out) >= 3 and out[0][1] < 0.40 and out[2][1] >= 0.15: return [("multicolor", out[0][1])] + out[:1]
    return out[:top]
