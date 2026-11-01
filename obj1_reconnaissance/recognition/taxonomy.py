"""Taxonomie de l'objectif 1 (17 catégories) + tables de normalisation. Reprise telle quelle du notebook."""
CATEGORIES = ["tshirt", "shirt", "top", "sweater", "jacket", "blazer", "coat", "dress", "skirt", "jeans", "pants", "shorts",
              "underwear", "shoes", "bag", "accessory", "traditional_garment"]
DEFINITIONS = {
    "tshirt": "knitted top with short or long sleeves, no buttons or only a small placket (includes polo shirts)",
    "shirt": "woven top with a full button front and a collar (dress shirts, casual shirts)",
    "top": "blouses, tank tops, camisoles, tunics, crop tops",
    "sweater": "knitted or fleece pullovers, sweatshirts, hoodies, cardigans",
    "jacket": "light outer garment with sleeves (bomber, denim, sports, rain jacket)",
    "blazer": "tailored formal jacket with lapels",
    "coat": "long or heavy outer garment for cold weather",
    "dress": "one-piece garment covering torso and legs",
    "skirt": "garment worn from the waist down, without leg separation",
    "jeans": "denim trousers",
    "pants": "non-denim trousers, chinos, track pants, leggings",
    "shorts": "short trousers ending above the knee",
    "underwear": "briefs, boxers, bras, innerwear vests",
    "shoes": "any footwear (sneakers, sandals, heels, flats, boots)",
    "bag": "handbags, backpacks, clutches, duffel bags",
    "accessory": "watch, belt, cap, scarf, sunglasses, wallet, tie, socks, jewellery",
    "traditional_garment": "traditional or ceremonial garment (jebba, farmla, blouza, kaftan, kurta)"}
COLORS = ["beige", "black", "blue", "brown", "green", "grey", "metallic", "multicolor", "orange", "pink", "purple", "red", "white", "yellow"]
GENDERS = ["male", "female", "unisex"]
SEASONS = ["summer", "winter", "spring", "fall", "all_season"]
OCCASIONS = ["casual", "formal", "sport", "party", "traditional", "home"]
COARSE = {"tshirt": "upper", "shirt": "upper", "top": "upper", "sweater": "upper", "jacket": "outer", "blazer": "outer", "coat": "outer",
          "jeans": "lower", "pants": "lower", "shorts": "lower", "skirt": "lower"}
def coarse(c): return COARSE.get(c, c)

# --- catalogue Fashion Product Images : articleType (minuscules) -> catégorie ; types ambigus exclus ---
ART = {"tshirts": "tshirt", "shirts": "shirt", "tops": "top", "tunics": "top", "sweatshirts": "sweater", "sweaters": "sweater", "jeans": "jeans",
       "trousers": "pants", "track pants": "pants", "leggings": "pants", "capris": "pants", "jeggings": "pants", "shorts": "shorts", "skirts": "skirt",
       "dresses": "dress", "jackets": "jacket", "rain jacket": "jacket", "blazers": "blazer", "casual shoes": "shoes", "sports shoes": "shoes",
       "formal shoes": "shoes", "sandals": "shoes", "sports sandals": "shoes", "heels": "shoes", "flats": "shoes", "flip flops": "shoes", "boots": "shoes",
       "handbags": "bag", "backpacks": "bag", "duffel bag": "bag", "clutches": "bag", "messenger bag": "bag", "briefs": "underwear", "bra": "underwear",
       "innerwear vests": "underwear", "boxers": "underwear", "watches": "accessory", "belts": "accessory", "caps": "accessory", "scarves": "accessory",
       "sunglasses": "accessory", "wallets": "accessory", "ties": "accessory", "socks": "accessory"}
COLOR_MAP = {"black": "black", "white": "white", "off white": "white", "cream": "beige", "beige": "beige", "nude": "beige", "skin": "beige", "khaki": "beige",
             "tan": "brown", "taupe": "brown", "brown": "brown", "coffee brown": "brown", "mushroom brown": "brown", "bronze": "brown", "copper": "brown",
             "blue": "blue", "navy blue": "blue", "turquoise blue": "blue", "teal": "blue", "grey": "grey", "grey melange": "grey", "charcoal": "grey", "steel": "grey",
             "silver": "metallic", "gold": "metallic", "metallic": "metallic", "red": "red", "maroon": "red", "burgundy": "red", "magenta": "pink", "pink": "pink",
             "rose": "pink", "peach": "pink", "mauve": "purple", "purple": "purple", "lavender": "purple", "orange": "orange", "rust": "orange", "yellow": "yellow",
             "mustard": "yellow", "green": "green", "olive": "green", "lime green": "green", "sea green": "green", "fluorescent green": "green", "multi": "multicolor"}
GENDER_MAP = {"men": "male", "women": "female", "unisex": "unisex", "boys": "male", "girls": "female"}
USAGE_MAP = {"casual": "casual", "smart casual": "casual", "travel": "casual", "ethnic": "traditional", "formal": "formal", "sports": "sport", "party": "party", "home": "home"}

# --- synonymes de sortie du LLM ---
CAT_SYN = {"t-shirt": "tshirt", "t_shirt": "tshirt", "tee": "tshirt", "polo": "tshirt", "hoodie": "sweater", "sweatshirt": "sweater", "pullover": "sweater",
           "cardigan": "sweater", "blouse": "top", "tank_top": "top", "trousers": "pants", "leggings": "pants", "sneakers": "shoes", "shoe": "shoes", "boots": "shoes",
           "sandals": "shoes", "heels": "shoes", "handbag": "bag", "backpack": "bag", "jean": "jeans", "skirts": "skirt", "dresses": "dress", "coats": "coat",
           "jackets": "jacket", "shirts": "shirt", "sweaters": "sweater", "accessories": "accessory", "traditional": "traditional_garment",
           "kaftan": "traditional_garment", "kurta": "traditional_garment"}
ATTR_SYN = {"color": {"multi_color": "multicolor", "multicolored": "multicolor", "navy": "blue", "gray": "grey", "khaki": "beige", "cream": "beige",
                      "silver": "metallic", "gold": "metallic"},
            "gender": {"men": "male", "man": "male", "boy": "male", "women": "female", "woman": "female", "girl": "female"},
            "season": {"autumn": "fall", "all_seasons": "all_season", "all": "all_season"},
            "occasion": {"sports": "sport", "smart_casual": "casual", "everyday": "casual", "ethnic": "traditional"}}
ATTR_ALLOWED = {"color": COLORS, "gender": GENDERS, "season": SEASONS, "occasion": OCCASIONS}

# --- pièces tunisiennes : sous-types (colonne `subtype` du jeu tunisien) et aide pour le prompt ---
TN_SUBTYPES = ["jebba", "farmla", "blouza", "kaftan", "fouta", "other"]
# !! Descriptions écrites de mémoire : À VALIDER / CORRIGER par quelqu'un qui connaît ces pièces (elles sont injectées dans le prompt).
TUNISIAN_HINTS = ("- Tunisian / Maghrebi garments all belong to traditional_garment: jebba (long loose tunic-like garment, sleeveless or short-sleeved), "
                  "farmla (short embroidered waistcoat or vest), blouza (long traditional dress, often embroidered), kaftan (long robe with wide sleeves), "
                  "fouta (striped or checked cotton wrap). Western vests, tunics and long dresses are NOT traditional_garment.")
