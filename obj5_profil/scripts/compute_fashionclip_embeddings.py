"""Calcule l'embedding FashionCLIP (512-d, norme 1) de chaque fiche article.

Décision n°1 de l'orchestration : FashionCLIP est l'embedding commun. Ce script
lit `image_crop` (sinon `image`) de chaque fiche et écrit le vecteur dans le
chemin du champ `embedding` (ex. emb/it_0042.npy), relatif à --assets.

Usage (Colab/Kaggle avec GPU conseillé, CPU possible) :
    pip install -r requirements-embed.txt
    python scripts/compute_fashionclip_embeddings.py \
        --catalog data/wardrobe.json --assets data
Puis : python -m dressme_profile train   (le modèle passe en espace "fashionclip")
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

MODEL_ID = "patrickjohncyh/fashion-clip"


@torch.no_grad()
def image_features(model, pixel_values):
    """Compatible avec les anciennes et nouvelles versions de transformers
    (certaines renvoient un objet BaseModelOutputWithPooling, cf. fiche obj. 5)."""
    out = model.get_image_features(pixel_values=pixel_values)
    if not isinstance(out, torch.Tensor):
        pooled = model.vision_model(pixel_values=pixel_values).pooler_output
        out = model.visual_projection(pooled)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", type=Path, default=Path("data/wardrobe.json"))
    ap.add_argument("--assets", type=Path, default=Path("data"),
                    help="dossier de base des chemins image_crop et embedding")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CLIPModel.from_pretrained(MODEL_ID).to(device).eval()
    proc = CLIPProcessor.from_pretrained(MODEL_ID)

    cards = json.loads(args.catalog.read_text(encoding="utf-8"))
    todo, missing = [], []
    for c in cards:
        out = args.assets / (c.get("embedding") or f"emb/{c['id']}.npy")
        if out.exists() and not args.overwrite:
            continue
        img = next((args.assets / p for p in (c.get("image_crop"), c.get("image"))
                    if p and (args.assets / p).exists()), None)
        (todo if img else missing).append((c["id"], img, out))
    print(f"{len(todo)} images à encoder, {len(missing)} sans image trouvée, device={device}")

    for s in range(0, len(todo), args.batch):
        chunk = todo[s:s + args.batch]
        imgs = [Image.open(p).convert("RGB") for _, p, _ in chunk]
        pv = proc(images=imgs, return_tensors="pt")["pixel_values"].to(device)
        feats = image_features(model, pv).float()
        feats = torch.nn.functional.normalize(feats, dim=-1).cpu().numpy()
        for (_, _, out), v in zip(chunk, feats):
            out.parent.mkdir(parents=True, exist_ok=True)
            np.save(out, v.astype(np.float32))
        print(f"  {min(s + args.batch, len(todo))}/{len(todo)}")
    if missing:
        print("Sans image :", ", ".join(i for i, _, _ in missing[:20]))


if __name__ == "__main__":
    main()
