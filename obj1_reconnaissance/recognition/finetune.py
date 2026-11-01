"""Fine-tuning OPTIONNEL de FashionCLIP (dernier bloc vision + projection + tête de classes), dataset mixte catalogue + photos tunisiennes.

Différences voulues par rapport au notebook v1 :
  * le modèle affiné est une COPIE (`embedder.clone()`) : l'encodeur gelé qui produit les embeddings des fiches n'est jamais modifié
    (sinon ses vecteurs ne seraient plus comparables à ceux des objectifs 2-6) ;
  * GradScaler pour l'entraînement fp16 (le notebook faisait un autocast fp16 sans mise à l'échelle du gradient) ;
  * rien n'est lancé sans `tunisian_dataset/labels.csv` (aucune donnée inventée).
Données tunisiennes : voir recognition/tunisian.py.  Le fine-tuning n'utilise QUE le split `train` (crops 512 px) ;
`dev` règle les seuils, `test` n'est jamais vu.  Les références kNN tunisiennes sont ajoutées à part (tunisian.add_tunisian_references)."""
from __future__ import annotations
import hashlib, random
from collections import Counter
from pathlib import Path
import numpy as np, pandas as pd
from PIL import Image
from .config import Config
from .imaging import load_image, open_rgb
from .taxonomy import CATEGORIES
from .tunisian import load_tunisian, prepare_crops

EPOCHS, BATCH, LR, HEAD_LR, PATIENCE, VAL_FRAC, TN_REPEAT, MAX_GENERIC = 5, 8, 1e-5, 2e-4, 2, 0.2, 2, 250


def _paths(cfg: Config):
    d = cfg.out / "fashionclip_finetuned"; d.mkdir(exist_ok=True); return d, d / "fashionclip_visual_finetuned.pt"


def build_mixed_dataset(cfg: Config, kb_df: pd.DataFrame, cropper=None):
    g = kb_df[kb_df.id >= 0].copy(); g["origin"] = "catalogue"; g["group_id"] = g.id.map(lambda x: f"catalogue_{int(x)}"); g["event"] = ""
    g = pd.concat([x.sample(min(len(x), MAX_GENERIC), random_state=cfg.seed) for _, x in g.groupby("category")], ignore_index=True)
    tn, issues = load_tunisian(cfg, "train")
    for lvl, msg in issues:
        if lvl == "ERREUR": print(f"[{lvl}] {msg}")
    if not len(tn): return g, pd.DataFrame(columns=g.columns)
    tn = prepare_crops(cfg, tn, cropper); tn = tn.assign(image_path=tn.crop_path, origin="tunisia")
    return g, tn[[c for c in tn.columns if c in set(g.columns) | {"subtype", "colour"}]].reset_index(drop=True)


def split_grouped(df: pd.DataFrame, seed: int):
    from sklearn.model_selection import GroupShuffleSplit
    a, b = next(GroupShuffleSplit(n_splits=1, test_size=VAL_FRAC, random_state=seed).split(df, groups=df.group_id.astype(str)))
    return df.iloc[a].copy(), df.iloc[b].copy()


def train(cfg: Config, base_embedder, kb_df: pd.DataFrame, cropper=None):
    import torch
    from torch.utils.data import Dataset, DataLoader
    from sklearn.metrics import f1_score, accuracy_score
    random.seed(cfg.seed); np.random.seed(cfg.seed); torch.manual_seed(cfg.seed)
    generic, tn = build_mixed_dataset(cfg, kb_df, cropper)
    if len(tn) == 0: print("Aucune photo tunisienne `train` valide : aucun fine-tuning (rien n'est inventé)."); return None
    combined = pd.concat([generic, tn], ignore_index=True).drop_duplicates("image_path").reset_index(drop=True)
    tr, va = split_grouped(combined, cfg.seed)
    tr = pd.concat([tr] + [tr[tr.origin == "tunisia"]] * (TN_REPEAT - 1), ignore_index=True)      # sur-échantillonnage TRAIN uniquement
    print("train", len(tr), "val", len(va), "| tunisien train", int((tr.origin == "tunisia").sum()), "val", int((va.origin == "tunisia").sum()))
    emb = base_embedder.clone(); model = emb.model; dev = emb.dev; d, weights = _paths(cfg)

    class DS(Dataset):
        def __init__(s, df): s.df = df.reset_index(drop=True)
        def __len__(s): return len(s.df)
        def __getitem__(s, i): r = s.df.iloc[i]; return open_rgb(r.image_path), CATEGORIES.index(r.category)
    def collate(b):
        im, y = zip(*b); return emb.proc(images=list(im), return_tensors="pt")["pixel_values"], torch.tensor(y)
    def feats(px):
        f = model.get_image_features(pixel_values=px); f = f.pooler_output if hasattr(f, "pooler_output") else f
        return torch.nn.functional.normalize(f.float(), dim=-1)

    dl_tr = DataLoader(DS(tr), batch_size=BATCH, shuffle=True, collate_fn=collate); dl_va = DataLoader(DS(va), batch_size=BATCH, collate_fn=collate)
    for p in model.parameters(): p.requires_grad = False
    trainables = list(model.vision_model.encoder.layers[-1].parameters()) + list(model.vision_model.post_layernorm.parameters()) + list(model.visual_projection.parameters())
    for p in trainables: p.requires_grad = True
    head = torch.nn.Linear(model.config.projection_dim, len(CATEGORIES)).to(dev); cnt = Counter(tr.category)
    w = torch.tensor([min(5.0, max(0.35, len(tr) / (len(CATEGORIES) * max(1, cnt.get(c, 0))))) for c in CATEGORIES], device=dev)
    loss_fn = torch.nn.CrossEntropyLoss(weight=w, label_smoothing=0.05)
    opt = torch.optim.AdamW([{"params": trainables, "lr": LR}, {"params": head.parameters(), "lr": HEAD_LR}], weight_decay=0.01)
    scaler = torch.amp.GradScaler("cuda", enabled=dev == "cuda"); best, wait, rows = -1.0, 0, []
    for ep in range(1, EPOCHS + 1):
        model.train(); head.train(); tot = seen = 0
        for x, y in dl_tr:
            x, y = x.to(dev), y.to(dev); opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=dev == "cuda"): loss = loss_fn(head(feats(x)), y)
            scaler.scale(loss).backward(); scaler.unscale_(opt); torch.nn.utils.clip_grad_norm_(trainables + list(head.parameters()), 1.0)
            scaler.step(opt); scaler.update(); tot += loss.item() * len(y); seen += len(y)
        model.eval(); head.eval(); T, P = [], []
        with torch.no_grad():
            for x, y in dl_va: P += head(feats(x.to(dev))).argmax(-1).cpu().tolist(); T += y.tolist()
        mf = f1_score(T, P, average="macro", zero_division=0); rows.append(dict(epoch=ep, train_loss=tot / max(1, seen), val_acc=accuracy_score(T, P), val_macro_f1=mf)); print(rows[-1])
        if mf > best + 1e-5:
            best, wait = mf, 0
            torch.save({"vision_last": model.vision_model.encoder.layers[-1].state_dict(), "post_norm": model.vision_model.post_layernorm.state_dict(),
                        "projection": model.visual_projection.state_dict(), "head": head.state_dict(), "categories": CATEGORIES}, weights)
        else:
            wait += 1
            if wait >= PATIENCE: print("early stopping"); break
    pd.DataFrame(rows).to_csv(d / "training_history.csv", index=False); return weights


def load_finetuned_retrieval(cfg: Config, shared_embedder, kb_df: pd.DataFrame, img_src, cropper=None):
    """Charge l'encodeur affiné (COPIE) et ré-indexe la base catalogue.  Renvoie (encodeur_affiné, kb_df, E_kb_affiné, tag).
    Les fiches continuent d'utiliser `shared_embedder` (gelé).  Si aucun entraînement n'est possible : (encodeur gelé, kb_df, E gelé, 'frozen')."""
    import torch
    d, weights = _paths(cfg)
    if not weights.exists():
        w = train(cfg, shared_embedder, kb_df, cropper)
        if w is None: return shared_embedder, kb_df, np.load(cfg.out / "kb_emb.npy"), "frozen"
    ck = torch.load(weights, map_location="cpu", weights_only=False)
    if ck["categories"] != CATEGORIES: raise ValueError("taxonomie du checkpoint différente")
    emb = shared_embedder.clone(); m = emb.model
    m.vision_model.encoder.layers[-1].load_state_dict(ck["vision_last"]); m.vision_model.post_layernorm.load_state_dict(ck["post_norm"])
    m.visual_projection.load_state_dict(ck["projection"]); m.eval()
    tag = hashlib.sha256(weights.read_bytes()).hexdigest()[:12]; path = d / f"kb_finetuned_{tag}.npy"
    base = kb_df[kb_df.id >= 0]
    if path.exists(): E = np.load(path)
    else: E = np.vstack([emb.images([load_image(p) for p in base.image_path.iloc[j:j + 32]], bs=16) for j in range(0, len(base), 32)]); np.save(path, E)
    return emb, base.reset_index(drop=True), E, "ft_" + tag
