"""Nettoyage de styles.csv -> data/clean.csv (+ rapport). python -m training.prepare_data --cap 1500"""
import argparse, json
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from pathlib import Path
import pandas as pd
from PIL import Image
from sklearn.model_selection import train_test_split
from app.catalog import ART

COLOUR_MAP = {"navy blue": "navy", "charcoal": "grey", "steel": "grey", "silver": "grey", "off white": "white", "cream": "beige", "khaki": "beige", "tan": "beige",
 "nude": "beige", "skin": "beige", "maroon": "red", "burgundy": "red", "rust": "brown", "coffee brown": "brown", "taupe": "brown", "bronze": "brown", "copper": "brown",
 "olive": "green", "lime green": "green", "sea green": "green", "fluorescent green": "green", "teal": "blue", "turquoise blue": "blue", "lavender": "purple",
 "mauve": "purple", "magenta": "pink", "rose": "pink", "peach": "pink", "mustard": "yellow"}   # couleurs proches fusionnées : étiquettes moins bruitées
USAGE_MAP = {"Travel": "Casual", "Home": "Casual", "Party": "Formal", "Smart Casual": "Casual"}   # classes trop rares (15 et 41 exemples) fusionnées

def _ok(p):
    try:
        with Image.open(p) as im: im.verify()
        return True
    except Exception: return False

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="data/styles.csv"); ap.add_argument("--images", default="data/images")
    ap.add_argument("--out", default="data/clean.csv"); ap.add_argument("--report", default="data/data_report.json")
    ap.add_argument("--cap", type=int, default=1500, help="max images par articleType (équilibrage + temps CPU)")
    ap.add_argument("--min-class", type=int, default=40); ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv); rep = {}
    df = pd.read_csv(a.csv, on_bad_lines="skip"); rep["1_lignes_brutes"] = len(df)
    df = df[df.masterCategory.isin(["Apparel", "Footwear", "Accessories"]) & ~df.subCategory.isin(["Innerwear", "Loungewear and Nightwear", "Socks"])]
    rep["2_hors_soins_parfums_sous_vetements"] = len(df)
    df = df[df.gender.isin(["Men", "Women", "Unisex"]) & df.articleType.isin(ART)]; rep["3_genres_et_types_geres"] = len(df)
    df = df.dropna(subset=["baseColour", "usage", "season"]); rep["4_sans_valeurs_manquantes"] = len(df)
    df = df.assign(usage=df.usage.replace(USAGE_MAP), colour=df.baseColour.str.lower().replace(COLOUR_MAP)
                   ).drop_duplicates(["productDisplayName", "baseColour", "articleType"])   # même nom ET même couleur ET même type
    rep["5_sans_doublons"] = len(df)
    img = Path(a.images)
    with ThreadPoolExecutor(8) as ex:
        good = list(tqdm(ex.map(lambda i: _ok(img / f"{i}.jpg"), df.id), total=len(df), desc="Vérification des images", unit="img"))
    df = df[good]; rep["6_image_valide"] = len(df)
    vc = df.articleType.value_counts(); df = df[df.articleType.isin(vc[vc >= a.min_class].index)]
    rare = df.colour.value_counts(); df.loc[df.colour.isin(rare[rare < a.min_class].index), "colour"] = "other"
    df = df.sample(frac=1, random_state=a.seed).groupby("articleType").head(a.cap)
    tr, rest = train_test_split(df, test_size=.3, stratify=df.articleType, random_state=a.seed)
    va, te = train_test_split(rest, test_size=.5, stratify=rest.articleType, random_state=a.seed)
    out = pd.concat([tr.assign(split="train"), va.assign(split="val"), te.assign(split="test")])
    out[["id", "gender", "articleType", "colour", "usage", "season", "productDisplayName", "split"]].to_csv(a.out, index=False)
    rep["7_final"] = {s: int((out.split == s).sum()) for s in ("train", "val", "test")}
    for t in ("articleType", "colour", "usage", "season"): rep[f"distribution_{t}"] = out[t].value_counts().to_dict()
    Path(a.report).write_text(json.dumps(rep, indent=2, ensure_ascii=False)); print(json.dumps(rep, indent=2, ensure_ascii=False))

if __name__ == "__main__": main()
