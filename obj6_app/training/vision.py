"""Apprentissage vision sur photos : python -m training.vision [--backend clip] [--finetune --epochs 3 --unfreeze 2]
1) embeddings figés + têtes logistiques (sonde linéaire)  2) option : fine-tuning des derniers blocs de CLIP, puis comparaison."""
import argparse, json
from pathlib import Path
import joblib, numpy as np, pandas as pd
from PIL import Image
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight
from app.colour import colour_features
from tqdm import tqdm
from app.embed import get_embedder

TASKS = ["articleType", "colour", "usage", "season"]

def embed_df(df, emb, img_dir, bs=64):
    return np.vstack([emb([Image.open(Path(img_dir) / f"{i}.jpg") for i in df.id.iloc[s:s + bs]]) for s in tqdm(range(0, len(df), bs), desc="Embeddings", unit="lot")])

def cached(path, df, fn):
    """Cache par identifiant d'image : ne recalcule que les images nouvelles (sûr même si le jeu de données change)."""
    have = {}
    if Path(path).exists():
        d = np.load(path); have = dict(zip(d["ids"].tolist(), d["Z"]))
    miss = df[~df.id.isin(have)]
    if len(miss):
        have.update(zip(miss.id.tolist(), fn(miss))); np.savez(path, ids=np.array(list(have)), Z=np.vstack(list(have.values())))
    return np.vstack([have[i] for i in df.id.tolist()])

def colour_df(df, img_dir):
    crop = Path(img_dir).parent / "images_crop"; out = []
    for i in tqdm(df.id, desc="Couleur (pixels)", unit="img"):
        p = crop / f"{i}.jpg"; out.append(colour_features(Image.open(p if p.exists() else Path(img_dir) / f"{i}.jpg")))
    return np.vstack(out)

def probe(df, Z, C, Zc=None):
    m = {s: (df.split == s).values for s in ("train", "val", "test")}; heads, met = {}, {}
    def fit(X, y, scale=False):
        if len(np.unique(y[m["train"]])) < 2: return DummyClassifier(strategy="most_frequent").fit(X[m["train"]], y[m["train"]])
        lr = LogisticRegression(max_iter=3000, C=C, class_weight="balanced")
        return (make_pipeline(StandardScaler(), lr) if scale else lr).fit(X[m["train"]], y[m["train"]])
    def report(clf, X, y):
        p = clf.predict(X[m["test"]]); base = DummyClassifier(strategy="most_frequent").fit(X[m["train"]], y[m["train"]])
        return {"test_acc": round(accuracy_score(y[m["test"]], p), 4), "test_macro_f1": round(f1_score(y[m["test"]], p, average="macro"), 4),
                "val_macro_f1": round(f1_score(y[m["val"]], clf.predict(X[m["val"]]), average="macro"), 4),
                "baseline_majority_acc": round(accuracy_score(y[m["test"]], base.predict(X[m["test"]])), 4),
                "per_class_f1": {c: round(v["f1-score"], 3) for c, v in classification_report(y[m["test"]], p, output_dict=True, zero_division=0).items() if isinstance(v, dict) and c not in ("macro avg", "weighted avg")}}
    for t in TASKS:
        y = df[t].values; heads[t] = fit(Z, y); met[t] = report(heads[t], Z, y)
    pix = False
    if Zc is not None:   # couleur : CLIP seul contre CLIP + pixels ; on garde la meilleure version (F1 macro de validation)
        X2, y = np.hstack([Z, Zc]), df["colour"].values; clf2 = fit(X2, y, True); v1 = met["colour"]["val_macro_f1"]
        v2 = round(f1_score(y[m["val"]], clf2.predict(X2[m["val"]]), average="macro"), 4)
        if v2 > v1: heads["colour"] = clf2; met["colour"] = report(clf2, X2, y) | {"variant": "clip+pixels", "val_macro_f1_clip_only": v1}; pix = True
        else: met["colour"]["variant"] = "clip"; met["colour"]["val_macro_f1_with_pixels"] = v2
    return heads, met, pix

def finetune(df, emb, img_dir, out, epochs, unfreeze, lr, bs):
    import torch, torch.nn as nn
    model, pre, dev = emb.model, emb.pre, emb.dev; v = model.visual
    for p in model.parameters(): p.requires_grad = False
    params = [p for b in list(v.transformer.resblocks)[-unfreeze:] for p in b.parameters()] + list(v.ln_post.parameters()) + [v.proj]
    for p in params: p.requires_grad = True
    tr = df[df.split == "train"].reset_index(drop=True); enc = {t: {c: i for i, c in enumerate(sorted(df[t].unique()))} for t in TASKS}
    heads = nn.ModuleDict({t: nn.Linear(v.proj.shape[1], len(enc[t])) for t in TASKS}).to(dev)
    w = {t: torch.tensor(compute_class_weight("balanced", classes=np.arange(len(enc[t])), y=tr[t].map(enc[t]).values), dtype=torch.float32).to(dev) for t in TASKS}
    class DS(torch.utils.data.Dataset):
        def __len__(s): return len(tr)
        def __getitem__(s, i):
            r = tr.iloc[i]; return pre(Image.open(Path(img_dir) / f"{r.id}.jpg").convert("RGB")), torch.tensor([enc[t][r[t]] for t in TASKS])
    dl = torch.utils.data.DataLoader(DS(), batch_size=bs, shuffle=True, num_workers=2)
    opt = torch.optim.AdamW([{"params": params, "lr": lr}, {"params": heads.parameters(), "lr": 1e-3}]); model.train()
    for ep in range(epochs):
        tot = 0
        for x, y in tqdm(dl, desc=f"epoch {ep + 1}/{epochs}"):
            x, y = x.to(dev), y.to(dev); z = model.encode_image(x); z = z / z.norm(dim=-1, keepdim=True)
            loss = sum(nn.functional.cross_entropy(heads[t](z), y[:, k], weight=w[t]) for k, t in enumerate(TASKS))
            opt.zero_grad(); loss.backward(); opt.step(); tot += loss.item()
        print(f"epoch {ep + 1}/{epochs} loss {tot / len(dl):.4f}")
    model.eval(); torch.save(v.state_dict(), out)

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean", default="data/clean.csv"); ap.add_argument("--images", default="data/images")
    ap.add_argument("--backend", default="clip"); ap.add_argument("--models-dir", default="models"); ap.add_argument("--cache", default="data")
    ap.add_argument("--finetune", action="store_true"); ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--unfreeze", type=int, default=2); ap.add_argument("--lr", type=float, default=1e-5)
    ap.add_argument("--no-colour-pixels", action="store_true"); ap.add_argument("--bs", type=int, default=32); ap.add_argument("--C", type=float, default=2.0)
    a = ap.parse_args(argv); md = Path(a.models_dir); md.mkdir(exist_ok=True); df = pd.read_csv(a.clean)
    Zof = lambda emb, tag: cached(Path(a.cache) / f"emb_{a.backend}{tag}.npz", df, lambda d: embed_df(d, emb, a.images))
    Zc = None if a.no_colour_pixels else cached(Path(a.cache) / "colour_feats.npz", df, lambda d: colour_df(d, a.images))
    emb = get_embedder(a.backend); heads, met, pix = probe(df, Zof(emb, ""), a.C, Zc); blob = {"backend": a.backend, "heads": heads, "ft": False, "colour_pixels": pix}
    report = {"frozen_probe": met}
    if a.finetune:
        ft = md / "clip_visual_ft.pt"; finetune(df, emb, a.images, ft, a.epochs, a.unfreeze, a.lr, a.bs)
        emb2 = get_embedder(a.backend, ft); heads2, met2, pix2 = probe(df, Zof(emb2, "_ft"), a.C, Zc); report["finetuned"] = met2
        f1 = lambda m: np.mean([m[t]["test_macro_f1"] for t in TASKS])
        if f1(met2) > f1(met): blob = {"backend": a.backend, "heads": heads2, "ft": True, "colour_pixels": pix2}; report["kept"] = "finetuned"
        else: ft.unlink(missing_ok=True); report["kept"] = "frozen_probe (le fine-tuning n'a pas amélioré le F1 macro)"
    joblib.dump(blob, md / "vision_heads.joblib"); (md / "vision_metrics.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({k: {t: {x: y for x, y in v[t].items() if x != "per_class_f1"} for t in TASKS} for k, v in report.items() if isinstance(v, dict)}, indent=2))

if __name__ == "__main__": main()
