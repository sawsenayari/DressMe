"""Calcule les embeddings FashionCLIP des photos de <APP_DATA>/wardrobe -> <APP_DATA>/emb.npz (clés ids, emb).
    python make_piece_embeddings.py app_data
Nécessite torch, transformers, pillow, torchvision (GPU conseillé). NON testé avec le vrai modèle dans mon environnement.
"""
import glob, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "obj2_compat"))
from embed_cards import load_img   # même prétraitement que l'étude (fond blanc, carré)


def main(root):
    import torch, torchvision.transforms as T
    from transformers import CLIPModel, CLIPImageProcessor
    name = "patrickjohncyh/fashion-clip"; dev = "cuda" if torch.cuda.is_available() else "cpu"
    dt = torch.float16 if dev == "cuda" else torch.float32
    model = CLIPModel.from_pretrained(name, torch_dtype=dt).to(dev).eval(); proc = CLIPImageProcessor.from_pretrained(name)
    tf = T.Compose([T.Resize(224, interpolation=T.InterpolationMode.BICUBIC), T.CenterCrop(224), T.ToTensor(),
                    T.Normalize(proc.image_mean, proc.image_std)])
    files = sorted(glob.glob(os.path.join(root, "wardrobe", "*.jpg")) + glob.glob(os.path.join(root, "wardrobe", "*.png")))
    ids, out = [os.path.basename(f) for f in files], []
    for s in range(0, len(files), 16):
        x = torch.stack([tf(load_img(f)) for f in files[s:s + 16]]).to(dev, dt)
        with torch.no_grad():
            o = model.get_image_features(pixel_values=x)
            o = o if isinstance(o, torch.Tensor) else (getattr(o, "image_embeds", None) if getattr(o, "image_embeds", None) is not None else o[0])
            out.append((o / o.norm(dim=-1, keepdim=True)).float().cpu().numpy())
    np.savez(os.path.join(root, "emb.npz"), ids=np.array(ids), emb=np.concatenate(out).astype(np.float32))
    print(len(ids), "embeddings ->", os.path.join(root, "emb.npz"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "app_data"))
