"""Catalogue d'articles. Schéma = contrat avec l'objectif 1 (classification des photos)."""
import os, random
from collections import defaultdict
from pathlib import Path

DATA = Path(os.getenv("DRESSME_DATA", "data"))
IMAGES = DATA / "images"
CROP = DATA / "images_crop"   # photos découpées (vêtement seul), générées par training.crop_dataset

FIELDS = ("name", "slot", "colour", "usage", "warmth", "formality", "waterproof", "open_toe")
# slot: top | bottom | footwear | outer | onepiece ; warmth 0-4 ; formality 0-3
BUILTIN = [
 ("T-shirt blanc","top","white","Casual",0.8,1,0,0), ("T-shirt noir","top","black","Casual",0.8,1,0,0),
 ("Polo marine","top","navy","Smart Casual",1.0,2,0,0), ("Chemise blanche","top","white","Formal",1.0,3,0,0),
 ("Chemise bleue","top","blue","Smart Casual",1.0,2,0,0), ("Pull gris","top","grey","Casual",2.5,1,0,0),
 ("Sweat à capuche","top","black","Casual",2.5,0,0,0), ("Maillot sport","top","red","Sports",0.5,0,0,0),
 ("Jean bleu","bottom","blue","Casual",1.5,1,0,0), ("Jean noir","bottom","black","Casual",1.5,1,0,0),
 ("Chino beige","bottom","beige","Smart Casual",1.3,2,0,0), ("Pantalon costume","bottom","navy","Formal",1.5,3,0,0),
 ("Short beige","bottom","beige","Casual",0.5,0,0,0), ("Jogging gris","bottom","grey","Sports",1.2,0,0,0),
 ("Baskets blanches","footwear","white","Casual",1.0,1,0,0), ("Chaussures de ville","footwear","black","Formal",1.2,3,0,0),
 ("Sandales","footwear","brown","Casual",0.3,0,0,1), ("Bottines","footwear","brown","Smart Casual",2.0,2,1,0),
 ("Running","footwear","grey","Sports",1.0,0,0,0), ("Balgha","footwear","yellow","Ethnic",1.0,3,0,0),
 ("Veste légère","outer","beige","Smart Casual",1.8,2,0,0), ("Blouson jean","outer","blue","Casual",1.8,1,0,0),
 ("Manteau long","outer","black","Formal",3.5,3,0,0), ("K-way","outer","navy","Casual",1.5,1,1,0),
 ("Blazer","outer","navy","Formal",1.8,3,0,0), ("Jebba blanche","onepiece","white","Ethnic",2.5,3,0,0),
 ("Jebba bordeaux","onepiece","red","Ethnic",2.5,3,0,0), ("Kaftan","onepiece","green","Ethnic",1.5,3,0,0),
 ("Robe d'été","onepiece","white","Casual",0.8,1,0,0), ("Robe de soirée","onepiece","black","Party",1.2,3,0,0),
 ("Sac à main noir","accessory","black","Smart Casual",0.1,2,0,0), ("Montre argent","accessory","silver","Smart Casual",0.1,2,0,0),
 ("Ceinture marron","accessory","brown","Smart Casual",0.1,2,0,0),
]
TYPE_PREFIX = [("T-shirt","Tshirts"),("Polo","Tshirts"),("Maillot","Tshirts"),("Chemise","Shirts"),("Pull","Sweaters"),
 ("Sweat","Sweatshirts"),("Jean","Jeans"),("Chino","Trousers"),("Pantalon","Trousers"),("Short","Shorts"),("Jogging","Track Pants"),
 ("Baskets","Casual Shoes"),("Chaussures","Formal Shoes"),("Sandales","Sandals"),("Bottines","Boots"),("Running","Sports Shoes"),
 ("Balgha","Balgha"),("Veste","Jackets"),("Blouson","Jackets"),("K-way","Jackets"),("Manteau","Coats"),("Blazer","Blazers"),
 ("Jebba","Jebba"),("Kaftan","Kaftan"),("Robe","Dresses"),("Sac","Handbags"),("Montre","Watches"),("Ceinture","Belts")]
GENDER_OF = {"Jebba blanche": "Men", "Jebba bordeaux": "Men", "Balgha": "Men",
             "Kaftan": "Women", "Robe d'été": "Women", "Robe de soirée": "Women", "Sac à main noir": "Women"}  # le reste = Unisex

def builtin_catalog():
    return [dict(zip(FIELDS, r), id=f"b{i}", waterproof=bool(r[6]), open_toe=bool(r[7]),
                 gender=GENDER_OF.get(r[0], "Unisex"),
                 type=next((t for p, t in TYPE_PREFIX if r[0].startswith(p)), None)) for i, r in enumerate(BUILTIN)]

# Kaggle "Fashion Product Images" (styles.csv): articleType -> (slot, warmth, formality, open_toe)
ART = {"Tshirts":("top",.8,1,0),"Shirts":("top",1,2,0),"Tops":("top",.8,1,0),"Tunics":("top",1,1,0),"Kurtis":("top",1.2,2,0),
 "Sweaters":("top",2.5,1,0),"Sweatshirts":("top",2.3,1,0),"Jackets":("outer",2,1,0),"Rain Jacket":("outer",1.8,1,0),
 "Blazers":("outer",1.8,3,0),"Waistcoat":("outer",1.2,3,0),"Shrug":("outer",1,1,0),
 "Jeans":("bottom",1.5,1,0),"Trousers":("bottom",1.4,2,0),"Shorts":("bottom",.5,0,0),"Track Pants":("bottom",1.2,0,0),
 "Skirts":("bottom",.8,2,0),"Capris":("bottom",.8,1,0),"Leggings":("bottom",.9,1,0),"Jeggings":("bottom",1,1,0),
 "Casual Shoes":("footwear",1,1,0),"Formal Shoes":("footwear",1.2,3,0),"Sports Shoes":("footwear",1,0,0),"Heels":("footwear",.8,3,0),
 "Flats":("footwear",.7,2,0),"Boots":("footwear",2,2,0),"Sandals":("footwear",.3,0,1),"Sports Sandals":("footwear",.4,0,1),
 "Flip Flops":("footwear",.2,0,1),"Dresses":("onepiece",.9,2,0),"Jumpsuit":("onepiece",1,2,0),"Kurtas":("onepiece",1.3,2,0),
 "Handbags":("accessory",.1,2,0),"Clutches":("accessory",.1,3,0),"Belts":("accessory",.1,2,0),"Watches":("accessory",.1,2,0),
 "Scarves":("accessory",.5,1,0),"Caps":("accessory",.1,0,0),"Sunglasses":("accessory",.1,1,0),"Ties":("accessory",.1,3,0)}
WATERPROOF = {"Rain Jacket"}
USAGES = {"Casual","Ethnic","Formal","Sports","Smart Casual","Party"}

def load_styles(path, limit=6000):
    """Charge Men + Women + Unisex ; le filtrage par genre se fait à l'échantillonnage."""
    import pandas as pd
    df = pd.read_csv(path, on_bad_lines="skip")
    df = df[df.articleType.isin(ART) & df.gender.isin(["Men", "Women", "Unisex"])].dropna(subset=["baseColour"])
    has_img = IMAGES.exists()
    if has_img:  # ne garder que les articles dont la photo existe
        df = df[df.id.map(lambda i: (IMAGES / f"{i}.jpg").exists())]
    df = df.sample(min(limit, len(df)), random_state=0)
    out = []
    for r in df.itertuples():
        slot, w, f, o = ART[r.articleType]
        w += {"Winter": .4, "Summer": -.2}.get(getattr(r, "season", None), 0)
        name = getattr(r, "productDisplayName", None)
        out.append(dict(id=str(r.id), name=str(name) if pd.notna(name) else r.articleType, slot=slot,
            colour=str(r.baseColour).lower().replace("navy blue", "navy"), gender=r.gender, type=r.articleType,
            usage=r.usage if r.usage in USAGES else "Casual", warmth=max(.2, w), formality=f,
            waterproof=r.articleType in WATERPROOF, open_toe=bool(o), image=(f"/images_crop/{r.id}.jpg" if (CROP / f"{r.id}.jpg").exists() else f"/images/{r.id}.jpg") if has_img else None))
    return out

_cache = {}
SIZES = {"top": (3, 6), "bottom": (3, 5), "footwear": (2, 4), "outer": (1, 3), "onepiece": (0, 2)}

def sample_wardrobe(catalog, rng: random.Random, tunisian=(), gender=None, sizes=None, dressy=0, sporty=0):
    """gender : 'Men' | 'Women' | None. dressy : nb min d'articles Formal/Smart Casual par catégorie (démo)."""
    ok = (lambda i: i.get("gender", "Unisex") in (gender, "Unisex")) if gender else (lambda i: True)
    by = defaultdict(list)
    for i in catalog:
        if ok(i): by[i["slot"]].append(i)
    w = []
    for s, (a, b) in (sizes or SIZES).items():
        pool = by.get(s, []); pick = rng.sample(pool, min(len(pool), rng.randint(a, b)))
        for usages, n, slots in ((("Formal", "Smart Casual"), dressy, None), (("Sports",), sporty, ("top", "bottom", "footwear"))):
            if n and (slots is None or s in slots):   # garantit un minimum de pièces habillées / sportives (démo)
                extra = [i for i in pool if i["usage"] in usages and i not in pick]
                pick += rng.sample(extra, min(len(extra), max(0, n - sum(i["usage"] in usages for i in pick))))
        w += pick
    tun = [i for i in tunisian if ok(i)]
    if tun and rng.random() < .4: w += rng.sample(tun, min(len(tun), rng.randint(1, 3)))
    return list({i["id"]: i for i in w}.values())

def demo_wardrobe(seed=0, gender="Women"):
    """Garde-robe de démo (~30 articles du dataset Kaggle, avec photos) pour le genre choisi."""
    styles = DATA / "styles.csv"
    if not styles.exists(): return [i for i in builtin_catalog() if i["gender"] in (gender, "Unisex")]
    if "cat" not in _cache: _cache["cat"] = load_styles(styles)
    tun = [i for i in builtin_catalog() if i["usage"] == "Ethnic"]
    sizes = {"top": (6, 8), "bottom": (4, 6), "footwear": (4, 5), "outer": (2, 3), "onepiece": (2, 3), "accessory": (3, 5)}
    return sample_wardrobe(_cache["cat"], random.Random(seed), tun, gender=gender, sizes=sizes, dressy=2, sporty=1)

def item_from_prediction(p):
    """Prédiction vision (articleType, colour, usage, season) -> article au format du contrat."""
    t, season = p["articleType"]["label"], p["season"]["label"]
    slot, w, f, o = ART[t]
    colour, usage = p["colour"]["label"], p["usage"]["label"]
    if usage == "Casual" and f >= 2: usage = "Formal" if f >= 3 else "Smart Casual"   # la tête « usage » ne connaît plus Smart Casual / Party : déduit du type
    sw = {"Winter": .4, "Summer": -.2}.get(season, 0) if p["season"]["conf"] >= .7 else 0    # la saison n'est fiable qu'avec une confiance élevée
    return dict(id="u" + os.urandom(4).hex(), name=f"{t} {colour}", slot=slot, colour=colour, usage=usage,
        warmth=max(.2, w + sw), formality=f, waterproof=t in WATERPROOF,
        open_toe=bool(o), type=t, gender="Unisex", image=None)
