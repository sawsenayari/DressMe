"""Table de correspondance Objectif 1  ->  ItemCard v1.

!! Tout ce qui est marqué  [A CONFIRMER]  doit être validé avec Amir (contrat) avant le gel v1.
"""
from __future__ import annotations

SLOTS = ("top", "bottom", "onepiece", "outer", "footwear", "bag", "accessory")

# 17 catégories de l'objectif 1  ->  7 emplacements communs.  None = pas d'emplacement (article non supporté).
CATEGORY_TO_SLOT: dict[str, str | None] = {
    "tshirt": "top", "shirt": "top", "top": "top", "sweater": "top",
    "jacket": "outer", "blazer": "outer", "coat": "outer",
    "dress": "onepiece",
    "skirt": "bottom", "jeans": "bottom", "pants": "bottom", "shorts": "bottom",
    "shoes": "footwear", "bag": "bag", "accessory": "accessory",
    # [A CONFIRMER] jebba / kaftan / farmla / blouza sont des pièces uniques longues -> onepiece (+ traditional=True)
    "traditional_garment": "onepiece",
    # [A CONFIRMER] sous-vêtements : hors périmètre des tenues -> aucun emplacement, pas de fiche produite
    "underwear": None,
}

# Type fin « façon Fashion Product Images » (liste de l'objectif 6)  [A CONFIRMER avec la liste exacte d'Amir].
# Sert uniquement de repli : le type fin est normalement lu dans le catalogue (voisins kNN).
CATEGORY_DEFAULT_TYPE = {
    "tshirt": "Tshirts", "shirt": "Shirts", "top": "Tops", "sweater": "Sweatshirts", "jacket": "Jackets",
    "blazer": "Blazers", "coat": "Jackets", "dress": "Dresses", "skirt": "Skirts", "jeans": "Jeans",
    "pants": "Trousers", "shorts": "Shorts", "shoes": "Casual Shoes", "bag": "Handbags",
    "accessory": "Accessories", "traditional_garment": "Traditional", "underwear": "Innerwear",
}

# warmth 0-4 / formality 0-3 : « fixés par type (dictionnaire de l'objectif 6) ».  [PLACEHOLDER]  -> remplacer par le
# dictionnaire d'Amir dès qu'il est disponible.  Valeurs par catégorie, volontairement neutres.
_WF = {"tshirt": (1, 0), "shirt": (1, 2), "top": (1, 1), "sweater": (3, 0), "jacket": (2, 1), "blazer": (2, 3),
       "coat": (4, 2), "dress": (1, 2), "skirt": (1, 1), "jeans": (2, 1), "pants": (2, 2), "shorts": (0, 0),
       "shoes": (2, 1), "bag": (0, 1), "accessory": (1, 1), "traditional_garment": (2, 3), "underwear": (1, 0)}

USAGE_OUT = {"casual": "Casual", "formal": "Formal", "sport": "Sports", "party": "Party", "traditional": "Ethnic",
             "home": "Casual", "unknown": "Casual"}
GENDER_OUT = {"male": "Men", "female": "Women", "unisex": "Unisex", "unknown": "Unisex"}   # [A CONFIRMER] valeurs exactes
SEASON_OUT = {"summer": "summer", "winter": "winter", "spring": "spring", "fall": "fall", "all_season": "all", "unknown": "all"}

OPEN_TOE_TYPES = {"sandals", "sports sandals", "flip flops", "heels"}
WATERPROOF_TYPES = {"rain jacket"}


def slot_of(category: str | None) -> str | None:
    return CATEGORY_TO_SLOT.get(category) if category else None


def default_type(category: str) -> str:
    return CATEGORY_DEFAULT_TYPE.get(category, "Accessories")


_DICT: dict | None = None


def load_type_dictionary(path: str | None = None) -> bool:
    """Charge le dictionnaire de l'objectif 6 (JSON : {"Jackets": {"warmth": 2, "formality": 1}, ...}).
    Chemin : argument, sinon variable d'environnement DRESSME_TYPE_DICT. Renvoie True si chargé."""
    global _DICT
    import json, os
    path = path or os.environ.get("DRESSME_TYPE_DICT")
    if path and os.path.exists(path):
        _DICT = json.load(open(path, encoding="utf-8")); return True
    return False


def warmth_formality(category: str, type_: str | None = None) -> tuple[int, int, bool]:
    """(warmth, formality, from_official_dictionary). Si le dictionnaire d'Amir n'est pas chargé, on renvoie un PLACEHOLDER
    neutre et False : le service ajoute alors la raison 'warmth_formality_placeholder' (rien n'est présenté comme officiel)."""
    if _DICT and type_ in _DICT:
        d = _DICT[type_]; return int(d["warmth"]), int(d["formality"]), True
    w, f = _WF.get(category, (1, 1)); return w, f, False


# Catégories dont le slot n'est PAS confirmé : la fiche est produite mais marquée 'needs_review' (revue humaine obligatoire).
SLOT_UNCONFIRMED = {"traditional_garment"}


def usage_out(v): return USAGE_OUT.get(v or "unknown", "Casual")
def gender_out(v): return GENDER_OUT.get(v or "unknown", "Unisex")
def season_out(v): return SEASON_OUT.get(v or "unknown", "all")

# Sous-types traditionnels (colonne `subtype` du jeu tunisien) -> slot.  [A CONFIRMER avec Amir et avec une personne qui connaît ces pièces]
TRADITIONAL_SUBTYPE_TO_SLOT = {"jebba": "onepiece", "blouza": "onepiece", "kaftan": "onepiece", "farmla": "outer", "fouta": "accessory", "other": "onepiece"}
