"""Script COMMUN d'embedding : calcule l'embedding FashionCLIP (512, normalisé) de chaque fiche article du dossier,
l'écrit dans emb/<id>.npy et renseigne le champ `embedding` de la fiche. À utiliser par les objectifs 1, 3, 5 et 6.

    python embed_cards.py DOSSIER_DES_FICHES [--force]

- Image utilisée : `image_crop` si présent, sinon `image` (chemins relatifs au dossier des fiches).
- Prétraitement identique à l'étude (fond blanc, carré, 224 px). Modèle : patrickjohncyh/fashion-clip (pas le CLIP de base).
- Nécessite : pip install torch transformers pillow torchvision. Premier lancement : téléchargement du modèle (~600 Mo).
- NON testé ici avec le vrai modèle (pas d'accès au réseau dans mon environnement) ; même code que celui validé dans le test réel.
"""
import glob, json, os, sys
import numpy as np


def load_img(p):
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(p))
    if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
        im = im.convert('RGBA'); bg = Image.new('RGBA', im.size, (255, 255, 255, 255)); bg.alpha_composite(im); im = bg
    im = im.convert('RGB'); w, h = im.size; s = max(w, h)
    sq = Image.new('RGB', (s, s), (255, 255, 255)); sq.paste(im, ((s - w) // 2, (s - h) // 2)); return sq


def main(root, force=False, batch=16):
    import torch, torchvision.transforms as T
    from transformers import CLIPModel, CLIPImageProcessor
    name = "patrickjohncyh/fashion-clip"
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if dev == "cuda" else torch.float32
    model = CLIPModel.from_pretrained(name, torch_dtype=dtype).to(dev).eval(); proc = CLIPImageProcessor.from_pretrained(name)
    tf = T.Compose([T.Resize(224, interpolation=T.InterpolationMode.BICUBIC), T.CenterCrop(224), T.ToTensor(),
                    T.Normalize(proc.image_mean, proc.image_std)])
    todo = []
    for p in sorted(glob.glob(os.path.join(root, "*.json"))):
        c = json.load(open(p, encoding="utf-8"))
        if not (isinstance(c, dict) and "id" in c and "slot" in c): continue
        if c.get("embedding") and not force: continue
        img = c.get("image_crop") or c.get("image")
        if not img or not os.path.exists(os.path.join(root, img)):
            print(f"[ignoré] {c['id']} : image introuvable ({img})"); continue
        todo.append((p, c, os.path.join(root, img)))
    os.makedirs(os.path.join(root, "emb"), exist_ok=True)
    for s in range(0, len(todo), batch):
        part = todo[s:s + batch]
        x = torch.stack([tf(load_img(i)) for _, _, i in part]).to(dev, dtype)
        with torch.no_grad():
            o = model.get_image_features(pixel_values=x)
            o = o if isinstance(o, torch.Tensor) else (getattr(o, "image_embeds", None) if getattr(o, "image_embeds", None) is not None else o[0])
            e = (o / o.norm(dim=-1, keepdim=True)).float().cpu().numpy()
        for (p, c, _), v in zip(part, e):
            np.save(os.path.join(root, "emb", f"{c['id']}.npy"), v.astype(np.float32))
            c["embedding"] = f"emb/{c['id']}.npy"
            json.dump(c, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{len(todo)} fiches mises à jour dans {root}")


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1], force="--force" in sys.argv)
