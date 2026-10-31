"""Vocabulaire commun : catégories, couleurs, verdicts, critères, occasions."""

CATEGORIES = ["haut", "bas", "robe", "veste", "chaussures", "sac", "accessoire"]

# Liste fermée donnée à Gemini (noms anglais, comme dans le dataset)
COLORS = ["Black", "White", "Grey", "Navy Blue", "Blue", "Light Blue", "Red", "Maroon",
          "Pink", "Orange", "Yellow", "Green", "Olive", "Teal", "Purple", "Brown",
          "Beige", "Cream", "Khaki", "Gold", "Silver", "Multi"]

# nom de couleur (minuscule) -> famille
COLOR_FAMILY = {
    "black": "black", "white": "white", "off white": "white", "cream": "beige",
    "grey": "grey", "grey melange": "grey", "charcoal": "grey", "steel": "grey",
    "navy blue": "navy", "blue": "blue", "light blue": "blue", "turquoise blue": "blue",
    "teal": "blue", "red": "red", "maroon": "red", "burgundy": "red", "rust": "red",
    "pink": "pink", "rose": "pink", "magenta": "pink", "peach": "pink",
    "orange": "orange", "yellow": "yellow", "mustard": "yellow", "lime green": "green",
    "green": "green", "olive": "green", "sea green": "green", "fluorescent green": "green",
    "purple": "purple", "lavender": "purple", "mauve": "purple",
    "brown": "brown", "coffee brown": "brown", "mushroom brown": "brown",
    "copper": "brown", "bronze": "brown",
    "beige": "beige", "khaki": "beige", "tan": "beige", "taupe": "beige",
    "nude": "beige", "skin": "beige",
    "gold": "metal", "silver": "metal", "metallic": "metal", "multi": "multi",
}
NEUTRAL_FAMILIES = {"black", "white", "grey", "beige", "brown", "navy", "metal"}
CHROMATIC_FAMILIES = {"red", "pink", "orange", "yellow", "green", "blue", "purple"}
CLASHES = [frozenset(p) for p in
           [("red", "pink"), ("red", "orange"), ("orange", "pink"),
            ("red", "green"), ("orange", "purple")]]


def colour_family(name):
    return COLOR_FAMILY.get(str(name or "").strip().lower(), "other")


# 0 = déconseillé, 1 = à améliorer, 2 = convient
VERDICTS = ["déconseillé", "à améliorer", "convient"]
CRITERIA = ["couleurs", "formalite", "meteo", "coherence"]

# occasion -> intervalle de formalité attendu (échelle 1..5)
OCCASIONS = {
    "décontracté": (1.0, 2.5),
    "sport": (1.0, 1.5),
    "travail": (3.0, 4.0),
    "soirée": (3.0, 5.0),
    "cérémonie": (4.0, 5.0),
}

# Dataset : articleType -> catégorie du projet, et usage -> formalité (vérité terrain)
ARTICLE_TO_CAT = {
    "Tshirts": "haut", "Shirts": "haut", "Tops": "haut", "Sweaters": "haut",
    "Jeans": "bas", "Trousers": "bas", "Skirts": "bas", "Dresses": "robe",
    "Jackets": "veste", "Casual Shoes": "chaussures", "Formal Shoes": "chaussures",
    "Sports Shoes": "chaussures", "Handbags": "sac", "Watches": "accessoire",
    "Belts": "accessoire",
}
USAGE_TO_FORMALITY = {"Sports": 1, "Casual": 2, "Travel": 2, "Ethnic": 3,
                      "Smart Casual": 3, "Party": 4, "Formal": 5}


def verdict_name(level):
    return VERDICTS[max(0, min(2, int(level)))]


def verdict_level(name):
    name = str(name or "").strip().lower()
    for i, v in enumerate(VERDICTS):
        if name == v:
            return i
    return None


def piece_label(p):
    return f"{p.get('type', p.get('categorie', '?'))} {str(p.get('couleur', '')).lower()}".strip()
