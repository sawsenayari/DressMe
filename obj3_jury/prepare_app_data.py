"""Prépare app_data/ pour l'interface, à partir de ton dossier dressme_data/ (à lancer une fois).

    python prepare_app_data.py <dressme_data> <app_data>

Copie les photos décrites (wardrobe/), les descriptions CLIP (perception_clip.json), la table truth.json
réduite (catégorie, sexe) et les tenues annotées (shots.json : exemples du prompt LLM). Aucune clé n'est copiée.
"""
import glob
import json
import os
import shutil
import sys
from statistics import median_low

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dressme.schema import verdict_level  # noqa: E402

SRC = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DRESSME_DATA", "/content/drive/MyDrive/dressme_data")
DST = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "app_data")


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_labeled(survey_dir):
    """outfits.json + questionnaire_*.csv -> tenues annotées (médiane des évaluateurs, le plus prudent à 2)."""
    outs_path = os.path.join(survey_dir, "outfits.json")
    if not os.path.exists(outs_path):
        return []
    outs = {o["outfit_id"]: o for o in load_json(outs_path)}
    cols = []
    for path in sorted(glob.glob(os.path.join(survey_dir, "questionnaire_*.csv"))):
        df = pd.read_csv(path, encoding="utf-8-sig")
        col = [c for c in df.columns if c.startswith("verdict_humain")][0]
        s = df.set_index("outfit_id")[col].map(verdict_level).dropna().astype(int)
        cols.append(s.rename(os.path.basename(path)))
    if not cols:
        return []
    table = pd.concat(cols, axis=1)
    labeled = []
    for oid, row in table.iterrows():
        vals = [int(v) for v in row.dropna()]
        if oid in outs and vals:
            labeled.append({**outs[oid], "humain": int(median_low(vals)), "n_annotateurs": len(vals)})
    return labeled


def main():
    truth = load_json(os.path.join(SRC, "truth.json"))
    perc = load_json(os.path.join(SRC, "perception_clip.json"))
    wardrobe = os.path.join(SRC, "wardrobe")
    ids = [f for f in truth if f in perc and os.path.exists(os.path.join(wardrobe, f))]
    if not ids:
        sys.exit("Aucune pièce décrite : lance d'abord la perception CLIP sur toute la garde-robe.")
    os.makedirs(os.path.join(DST, "wardrobe"), exist_ok=True)
    for f in ids:
        shutil.copy(os.path.join(wardrobe, f), os.path.join(DST, "wardrobe", f))
    keep = ("articleType", "categorie", "gender")
    with open(os.path.join(DST, "truth.json"), "w", encoding="utf-8") as f:
        json.dump({i: {k: truth[i].get(k) for k in keep} for i in ids}, f, ensure_ascii=False)
    with open(os.path.join(DST, "perception_clip.json"), "w", encoding="utf-8") as f:
        json.dump({i: perc[i] for i in ids}, f, ensure_ascii=False)
    shots = []
    for d in sorted(glob.glob(os.path.join(SRC, "survey*"))):
        shots += load_labeled(d)
    with open(os.path.join(DST, "shots.json"), "w", encoding="utf-8") as f:
        json.dump(shots, f, ensure_ascii=False)
    size = sum(os.path.getsize(os.path.join(DST, "wardrobe", f)) for f in ids) / 1e6
    print(f"{len(ids)} pièces (sur {len(truth)} dans truth.json) | {len(shots)} tenues annotées | photos : {size:.0f} Mo")
    if len(ids) < len(truth):
        print(f"⚠️ {len(truth) - len(ids)} pièces sans description : relance la perception pour les inclure.")
    print("app_data prêt dans", DST)


if __name__ == "__main__":
    main()
