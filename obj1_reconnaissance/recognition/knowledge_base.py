"""Base kNN/RAG construite automatiquement depuis Fashion Product Images (aucune étiquette manuelle).
Nouveauté v2 : on garde `article_type` (ex. 'Jackets') -> type fin de l'ItemCard lu chez les voisins, cohérent avec l'objectif 6."""
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd
try:
    from tqdm.auto import tqdm
except ImportError:            # tqdm facultatif
    def tqdm(x, **k): return x
from .config import Config
from .imaging import load_image
from .taxonomy import ART, COLOR_MAP, GENDER_MAP, USAGE_MAP

COLS = ["id", "category", "article_type", "color", "gender", "season", "occasion", "name"]


def build_catalogue():
    import kagglehub
    root = Path(kagglehub.dataset_download("paramaggarwal/fashion-product-images-small"))
    styles = next(p for p in root.rglob("styles.csv") if p.is_file()); imgdir = next(p for p in root.rglob("images") if p.is_dir())
    raw = pd.read_csv(styles, on_bad_lines="skip")
    raw["article_type"] = raw.articleType.astype(str).str.strip()
    raw["category"] = raw.article_type.str.lower().map(ART)
    raw = raw.dropna(subset=["category"]).copy(); raw["id"] = raw.id.astype(int)
    raw = raw[raw.id.map(lambda i: (imgdir / f"{i}.jpg").exists())]
    low = lambda col: raw[col].astype(str).str.strip().str.lower()
    raw["color"] = low("baseColour").map(COLOR_MAP); raw["gender"] = low("gender").map(GENDER_MAP)
    raw["season"] = low("season").map({"summer": "summer", "winter": "winter", "spring": "spring", "fall": "fall"})
    raw["occasion"] = low("usage").map(USAGE_MAP); raw["name"] = raw.productDisplayName.astype(str)
    return raw[COLS].reset_index(drop=True), imgdir


def build_or_load(cfg: Config, embedder, force: bool = False):
    """Renvoie (kb_df, E_kb, test_df, img_src). Même échantillonnage que le notebook (random_state 0 / 1) : résultats comparables."""
    out = cfg.out; KB_META, KB_EMB, TEST_META = out / "kb_meta.csv", out / "kb_emb.npy", out / "test_meta.csv"
    cat_df, img_src = build_catalogue()
    if not force and KB_META.exists() and KB_EMB.exists() and TEST_META.exists():
        kb_df = pd.read_csv(KB_META)
        if "article_type" in kb_df.columns:
            kb_df["image_path"] = kb_df.id.map(lambda i: str(img_src / f"{int(i)}.jpg"))
            return kb_df, np.load(KB_EMB), pd.read_csv(TEST_META), img_src
        print("kb_meta.csv ancien (sans article_type) -> reconstruction de la base.")
    test_df = pd.concat([d.sample(min(cfg.n_test_per_cat, len(d)), random_state=0) for _, d in cat_df.groupby("category")]).reset_index(drop=True)
    rest = cat_df[~cat_df.id.isin(test_df.id)]
    kb_df = pd.concat([d.sample(min(cfg.kb_per_cat, len(d)), random_state=1) for _, d in rest.groupby("category")]).reset_index(drop=True)

    def embed_ids(ids, desc):
        parts = []
        for i in tqdm(range(0, len(ids), 64), desc=desc): parts.append(embedder.images([load_image(img_src / f"{j}.jpg") for j in ids[i:i + 64]]))
        return np.vstack(parts)
    E_kb, E_test = embed_ids(list(kb_df.id), "Base kNN"), embed_ids(list(test_df.id), "Test")
    keep = (E_kb @ E_test.T).max(1) < cfg.dup_sim                              # anti-fuite : quasi-doublons base/test
    print(f"anti-fuite : {int((~keep).sum())} images de base retirées")
    kb_df, E_kb = kb_df[keep].reset_index(drop=True), E_kb[keep]
    kb_df.to_csv(KB_META, index=False); np.save(KB_EMB, E_kb); test_df.to_csv(TEST_META, index=False)
    kb_df["image_path"] = kb_df.id.map(lambda i: str(img_src / f"{int(i)}.jpg"))
    return kb_df, E_kb, test_df, img_src
