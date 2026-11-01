"""Découpe en lot les photos portées du catalogue pour un affichage propre (reprise possible, barre de progression).
python -m training.crop_dataset --limit 1500    (CPU : lent ; GPU Colab/Kaggle : rapide)"""
import argparse
from pathlib import Path
from PIL import Image
from tqdm import tqdm
from app import segment
from app.catalog import CROP, DATA, IMAGES, load_styles

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--styles", default=str(DATA / "styles.csv")); ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv); CROP.mkdir(parents=True, exist_ok=True); log = CROP / "_done.txt"
    done = set(log.read_text().split()) if log.exists() else set()
    items = [i for i in load_styles(a.styles) if i["id"] not in done]; items = items[:a.limit] if a.limit else items
    with open(log, "a") as f:
        for it in tqdm(items, desc="Découpe des vêtements", unit="img"):
            try:
                worn, parts = segment.extract_parts(Image.open(IMAGES / f"{it['id']}.jpg").convert("RGB"), it["slot"], cut_flat=False)
                if worn and parts: next(iter(parts.values())).save(CROP / f"{it['id']}.jpg", quality=92)
            except Exception as e: print(it["id"], repr(e)[:80])
            f.write(it["id"] + "\n"); f.flush()

if __name__ == "__main__": main()
