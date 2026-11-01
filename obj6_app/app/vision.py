"""Inférence vision : photo -> {articleType, colour, usage, season} (têtes entraînées par training/vision.py)."""
import io, os
from pathlib import Path
import joblib, numpy as np
from PIL import Image
from .colour import colour_features
from .embed import get_embedder

M = Path(os.getenv("DRESSME_MODELS", "models")); _st = {}

def available(): return (M / "vision_heads.joblib").exists()

def analyze(data: bytes):
    return analyze_image(Image.open(io.BytesIO(data)).convert("RGB"))

def analyze_image(img):
    if not _st:
        blob = joblib.load(M / "vision_heads.joblib"); ft = M / "clip_visual_ft.pt"
        _st.update(blob=blob, emb=get_embedder(blob["backend"], ft if blob.get("ft") and ft.exists() else None))
    z = _st["emb"]([img]); out = {}
    for task, clf in _st["blob"]["heads"].items():
        x = np.hstack([z, colour_features(img)[None]]) if task == "colour" and _st["blob"].get("colour_pixels") else z
        p = clf.predict_proba(x)[0]; i = int(p.argmax()); out[task] = {"label": str(clf.classes_[i]), "conf": round(float(p[i]), 3)}
    return out
