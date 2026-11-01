"""Caractéristiques de couleur calculées sur les pixels du vêtement : complètent CLIP, peu sensible à la couleur brute."""
import numpy as np
from PIL import Image

def colour_features(img, size=64):
    arr = np.asarray(img.convert("RGB").resize((size, size)), dtype=np.float32) / 255
    m = size // 8; c = arr[m:size - m, m:size - m].reshape(-1, 3)          # centre : évite les bords
    keep = c.min(1) <= .92; g = c[keep] if keep.sum() >= 30 else c           # on écarte le fond blanc (photos découpées / catalogue)
    h, s, v = (np.asarray(Image.fromarray((g.reshape(1, -1, 3) * 255).astype(np.uint8), "RGB").convert("HSV"), dtype=np.float32).reshape(-1, 3) / 255).T
    hue = np.histogram(h, bins=12, range=(0, 1), weights=s)[0]; hue = hue / (hue.sum() + 1e-6)   # teinte pondérée par la saturation
    grey = s < .15
    return np.concatenate([hue, np.histogram(v, bins=5, range=(0, 1))[0] / len(v),
        [(v < .2).mean(), (grey & (v > .8)).mean(), (grey & (v >= .25) & (v <= .8)).mean(), s.mean(), s.std(), v.mean(), v.std()], g.mean(0)]).astype(np.float32)
