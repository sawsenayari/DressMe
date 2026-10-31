"""Paramètres de l'objectif 5 (profil de style).

Les valeurs de re-ranking et la marge « mixte » reprennent la fiche technique
de l'objectif 5 (section 4, hyperparamètres de référence).
"""
from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGE_DIR.parent

# Fichiers par défaut (surchargeables par variables d'environnement)
CATALOG_PATH = Path(os.getenv("DRESSME_CATALOG", ROOT_DIR / "data" / "wardrobe.json"))
MODEL_PATH = Path(os.getenv("DRESSME_PROFILE_MODEL", ROOT_DIR / "models" / "style_model.joblib"))
# Dossier de base pour résoudre les chemins relatifs "emb/it_xxxx.npy" des fiches
ASSETS_DIR = Path(os.getenv("DRESSME_ASSETS_DIR", ROOT_DIR / "data"))
USE_MOCK = os.getenv("DRESSME_PROFILE_MOCK", "0") == "1"

PROFILE_VERSION = "obj5-profile-v1"
SEED = 42

# Sept emplacements communs (contrat ItemCard v1)
SLOTS = ["top", "bottom", "onepiece", "outer", "footwear", "bag", "accessory"]
USAGES = ["Casual", "Smart Casual", "Formal", "Sports", "Ethnic", "Party"]

# Persona
PERSONAS = ["efficacite", "economie", "image"]
MIXED_MARGIN = 0.08            # écart < 0,08 entre les deux meilleurs = « mixte »

# Qualité des fiches
MIN_SLOT_CONFIDENCE = 0.30      # fiche ignorée en dessous (ex. confidence.slot = 0.0)
DUPLICATE_COSINE = 0.995        # deux fiches plus proches que ça = doublon
MIN_PRICE_COVERAGE = 0.30       # part de prix connus pour calculer l'économie

# Couleurs
NEUTRAL_COLOURS = {"black", "white", "beige", "grey", "gray", "navy", "brown", "cream", "khaki"}
STATEMENT_COLOURS = {"red", "multicolor", "metallic", "pink", "purple", "yellow", "orange", "gold"}
BASIC_TYPES = {"Tshirts", "Shirts", "Tops", "Jeans", "Trousers", "Skirts", "Socks", "Belts",
               "Flats", "Sneakers", "Casual Shoes"}

# Clustering (fiche : k dans [6, 16], n_init = 10, choix par silhouette, PCA 64)
K_MIN, K_MAX = 6, 16
PCA_DIM = 64
N_INIT = 10

# Re-ranking (fiche, section 4)
RERANK = {
    "efficacite": {"neutral": 0.10, "basic": 0.05},
    "economie": {"price_percentile": -0.15},
    "image": {"dominant_cluster": 0.10},
}
