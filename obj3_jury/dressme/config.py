"""Chemins et réglages. Tout est surchargeable par variables d'environnement."""
import os

DATA_DIR = os.environ.get("DRESSME_DATA", os.path.join(os.getcwd(), "data_work"))
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")   # à adapter si besoin
TUNIS = (36.8065, 10.1815)   # latitude, longitude pour la météo automatique


def paths(data_dir=None):
    d = data_dir or DATA_DIR
    return {
        "root": d,
        "wardrobe": os.path.join(d, "wardrobe"),
        "truth": os.path.join(d, "truth.json"),
        "perception": os.path.join(d, "perception.json"),
        "survey": os.path.join(d, "survey"),
    }
