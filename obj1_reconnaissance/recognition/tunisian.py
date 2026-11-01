"""Jeu de données tunisien : à REMPLIR par toi, utilisé pour (A) références kNN/RAG sans entraînement, (C) fine-tuning, (D) évaluation.

Dossier :   <DRESSME_ROOT>/tunisian_dataset/
                images/…            tes photos (n'importe quel sous-dossier)
                labels.csv          une ligne par photo (créé / complété par `make_template`)
                crops/              crops 512 px générés automatiquement (ne pas toucher)

labels.csv — colonnes (seules `image_path` et `category` sont obligatoires ; une ligne sans `category` est ignorée = « à faire ») :
    image_path   chemin relatif à tunisian_dataset/ (ex. images/jebba_01.jpg)
    category     UNE des 17 classes (tshirt, shirt, … , traditional_garment)        ← la vérité terrain
    subtype      facultatif : jebba | farmla | blouza | kaftan | fouta | other      (surtout pour traditional_garment)
    colour       facultatif : beige black blue brown green grey metallic multicolor orange pink purple red white yellow
    gender, season, occasion   facultatifs (mêmes valeurs que le notebook)
    event, origin              facultatifs (libre : wedding, tunisia…)
    group_id     IMPORTANT : même valeur pour les photos d'une même séance / tenue / personne (évite qu'elles soient des deux côtés d'un split)
    split        facultatif : train | dev | test.  Vide -> attribution automatique PAR GROUPE (60 / 20 / 20, déterministe)
    cropped      facultatif : 1 si la photo est déjà un crop (sinon le crop automatique est appliqué)

Règles anti-biais : `train` = références + fine-tuning ; `dev` = réglage des seuils ; `test` = regardé UNE fois, à la fin.
Les 30 photos de l'évaluation finale ne doivent PAS être dans ce fichier avec un split `train`."""
from __future__ import annotations
import hashlib
from pathlib import Path
import numpy as np, pandas as pd
from contracts import slot_of, TRADITIONAL_SUBTYPE_TO_SLOT
from .config import Config
from PIL import Image
from .imaging import normalise_crop, open_rgb
from .taxonomy import CATEGORIES, COLORS, GENDERS, SEASONS, OCCASIONS, TN_SUBTYPES

COLS = ["image_path", "category", "subtype", "colour", "gender", "season", "occasion", "event", "origin", "group_id", "split", "cropped"]
IMG_EXT = {".png", ".jpg", ".jpeg", ".webp", ".heic", ".heif"}
_READ_CACHE: dict = {}


def readable(path) -> tuple[bool, str]:
    """True si l'image est RÉELLEMENT décodable (pas seulement identifiable : `verify()` laisse passer des fichiers tronqués).
    Cas typiques d'échec sur Drive : fichier de 0 octet, téléversement interrompu, HEIC renommé en .jpg (installe pillow-heif)."""
    p = Path(path)
    try: st = p.stat(); key = (str(p), st.st_mtime, st.st_size)
    except OSError as e: return False, f"inaccessible ({e.__class__.__name__})"
    if key in _READ_CACHE: return _READ_CACHE[key]
    if st.st_size == 0: res = (False, "fichier vide (0 octet)")
    else:
        try:
            with Image.open(p) as im: im.load()
            res = (True, "")
        except Exception as e: res = (False, f"{e.__class__.__name__}: {str(e)[:80]}")
    _READ_CACHE[key] = res; return res


def tn_dir(cfg: Config) -> Path:
    d = cfg.root / "tunisian_dataset"; (d / "images").mkdir(parents=True, exist_ok=True); return d


def make_template(cfg: Config) -> dict:
    """Crée labels.csv, ou AJOUTE une ligne vide pour chaque nouvelle image trouvée (n'écrase jamais ce que tu as rempli)."""
    d = tn_dir(cfg); csv = d / "labels.csv"
    old = pd.read_csv(csv, dtype=str).fillna("") if csv.exists() else pd.DataFrame(columns=COLS)
    for c in COLS:
        if c not in old: old[c] = ""
    have = set(old.image_path.map(lambda p: Path(p).as_posix()))
    new = sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.suffix.lower() in IMG_EXT and "crops" not in p.parts and p.relative_to(d).as_posix() not in have)
    add = pd.DataFrame([{**{c: "" for c in COLS}, "image_path": p, "origin": "tunisia"} for p in new])
    pd.concat([old[COLS], add], ignore_index=True).to_csv(csv, index=False)
    return dict(images_total=len(have) + len(new), nouvelles_lignes=len(new), fichier=str(csv))


def _group_split(group: str) -> str:
    h = int(hashlib.md5(group.encode()).hexdigest(), 16) % 100
    return "train" if h < 60 else "dev" if h < 80 else "test"


def load_tunisian(cfg: Config, split: str | None = None):
    """Renvoie (df, issues). df ne contient que des lignes VALIDES (fichier présent, catégorie connue) avec `split` renseigné.
    issues = liste de (niveau, message) ; niveau 'ERREUR' = ligne ignorée, 'ATTENTION' = à corriger."""
    d = tn_dir(cfg); csv = d / "labels.csv"; issues = []
    if not csv.exists(): return pd.DataFrame(columns=COLS + ["abs_path"]), [("ATTENTION", f"{csv} absent : lance make_template(cfg)")]
    df = pd.read_csv(csv, dtype=str).fillna("")
    for c in COLS:
        if c not in df: df[c] = ""
    n_pending = int((df.category.str.strip() == "").sum()); df = df[df.category.str.strip() != ""].copy()
    if n_pending: issues.append(("INFO", f"{n_pending} lignes sans category : ignorées (à remplir)"))
    if df.empty: return pd.DataFrame(columns=COLS + ["abs_path"]), issues                     # rien d'étiqueté pour l'instant
    for c in ("category", "subtype", "colour", "gender", "season", "occasion", "split"): df[c] = df[c].str.strip().str.lower()
    df["abs_path"] = df.image_path.map(lambda p: str(Path(p) if Path(p).is_absolute() else d / p))
    bad = ~df.abs_path.map(lambda p: Path(p).is_file())
    for p in df.image_path[bad]: issues.append(("ERREUR", f"fichier introuvable : {p}"))
    df = df[~bad]
    if df.empty: return pd.DataFrame(columns=COLS + ["abs_path"]), issues
    ok = [readable(p) for p in df.abs_path]                                                    # décodage réel de chaque image
    for p, (good, why) in zip(df.image_path, ok):
        if not good: issues.append(("ERREUR", f"image illisible : {p} — {why}"))
    df = df[[g for g, _ in ok]]
    if df.empty: return pd.DataFrame(columns=COLS + ["abs_path"]), issues
    bad = ~df.category.isin(CATEGORIES)
    for p, c in zip(df.image_path[bad], df.category[bad]): issues.append(("ERREUR", f"category invalide '{c}' ({p}) : doit être l'une des 17 classes"))
    df = df[~bad]
    for col, allowed in (("subtype", TN_SUBTYPES), ("colour", COLORS), ("gender", GENDERS), ("season", SEASONS), ("occasion", ["casual", "formal", "sport", "party", "traditional", "home"])):
        b = (df[col] != "") & ~df[col].isin(allowed)
        for p, v in zip(df.image_path[b], df[col][b]): issues.append(("ATTENTION", f"{col} invalide '{v}' ({p}) : ignoré"))
        df.loc[b, col] = ""
    dup = df.image_path.duplicated(keep="first")
    for p in df.image_path[dup]: issues.append(("ERREUR", f"image listée deux fois : {p}"))
    df = df[~dup].copy()
    df["group_id"] = [g if g.strip() else Path(p).stem for g, p in zip(df.group_id, df.image_path)]
    if (df.group_id == df.image_path.map(lambda p: Path(p).stem)).all() and len(df) > 3:
        issues.append(("ATTENTION", "aucun group_id renseigné : des photos d'une même séance peuvent se retrouver des deux côtés d'un split"))
    auto = ~df.split.isin(["train", "dev", "test"]); df.loc[auto, "split"] = df.group_id[auto].map(_group_split)
    df["md5"] = df.abs_path.map(lambda p: hashlib.md5(Path(p).read_bytes()).hexdigest())            # fichiers identiques -> même split (anti-fuite)
    first = df.groupby("md5").split.transform("first")
    if (first != df.split).any(): issues.append(("ATTENTION", f"{int((first != df.split).sum())} doublons exacts répartis sur plusieurs splits : remis dans le même split"))
    df["split"] = first
    n = df.groupby(["category", "split"]).size().unstack(fill_value=0)
    for c in n.index:
        if n.loc[c].sum() < 3: issues.append(("ATTENTION", f"classe '{c}' : seulement {int(n.loc[c].sum())} photo(s) — trop peu pour une conclusion"))
    out = df.drop(columns="md5").reset_index(drop=True)
    return (out[out.split == split].reset_index(drop=True) if split else out), issues


def report(cfg: Config) -> pd.DataFrame:
    df, issues = load_tunisian(cfg)
    for lvl, msg in issues: print(f"[{lvl}] {msg}")
    if len(df): tab = df.groupby(["category", "split"]).size().unstack(fill_value=0); print(tab.to_string()); print("total :", len(df)); return tab
    print("aucune ligne valide pour l'instant."); return pd.DataFrame()


def _target_slot(r) -> str | None:
    return TRADITIONAL_SUBTYPE_TO_SLOT.get(r.subtype) if r.category == "traditional_garment" and r.subtype else slot_of(r.category)


def prepare_crops(cfg: Config, df: pd.DataFrame, cropper=None, force: bool = False) -> pd.DataFrame:
    """Un crop 512 px par photo (mis en cache). Les références et la requête passent ainsi par le MÊME prétraitement.
    Une photo qui échoue (illisible, crop impossible) est IGNORÉE avec un avertissement : elle ne fait plus planter le chargement."""
    out = tn_dir(cfg) / "crops"; out.mkdir(exist_ok=True); paths, failed = [], []
    for r in df.itertuples():
        tgt = out / (hashlib.md5(r.abs_path.encode()).hexdigest()[:12] + "_crop.png")
        try:
            if force or not tgt.exists():
                im = open_rgb(r.abs_path)
                if str(r.cropped).strip().lower() in ("1", "true", "yes", "oui") or cropper is None: crop = normalise_crop(im, cfg.crop_size)
                else:
                    pieces = cropper.crop(im, cfg.crop_mode); want = _target_slot(r)
                    match = [p for p in pieces if p.slot_hint == want] or pieces
                    crop = max(match, key=lambda p: p.area_frac).image
                crop.save(tgt)
            paths.append(str(tgt))
        except Exception as e:
            paths.append(None); failed.append((r.image_path, f"{e.__class__.__name__}: {str(e)[:80]}"))
    for p, why in failed: print(f"⚠️ photo ignorée (crop impossible) : {p} — {why}")
    df = df.copy(); df["crop_path"] = paths; df = df[df.crop_path.notna()].reset_index(drop=True); df.attrs["failed"] = failed; return df


def add_tunisian_references(cfg: Config, embedder, kb_df: pd.DataFrame, E_kb: np.ndarray, cropper=None, tag: str = "frozen"):
    """Ajoute les photos tunisiennes `train` comme voisins du kNN/RAG (SANS entraînement).  Renvoie (kb_df, E, n_ajoutées).
    `embedder` = l'encodeur qui a servi à construire E_kb (gelé, ou affiné s'il y a fine-tuning) ; `tag` identifie le cache."""
    df, _ = load_tunisian(cfg, "train")
    if not len(df): return kb_df, E_kb, 0
    df = prepare_crops(cfg, df, cropper)
    key = hashlib.md5((tag + "|".join(f"{p}:{Path(p).stat().st_mtime}:{c}" for p, c in zip(df.crop_path, df.category))).encode()).hexdigest()[:10]
    cache = cfg.out / f"tn_refs_{key}.npy"
    if cache.exists(): Et = np.load(cache)
    else:
        Et = np.vstack([embedder.images([open_rgb(p) for p in df.crop_path.iloc[i:i + 32]], bs=16) for i in range(0, len(df), 32)]); np.save(cache, Et)
    t = pd.DataFrame(dict(id=-1 - np.arange(len(df)), category=df.category, article_type=None, subtype=df.subtype.replace("", None), color=df.colour.replace("", None),
                          gender=df.gender.replace("", None), season=df.season.replace("", None), occasion=df.occasion.replace("", None),
                          name=[f"Tunisian {s or c}" for s, c in zip(df.subtype, df.category)], image_path=df.crop_path))
    return pd.concat([kb_df, t], ignore_index=True), np.vstack([E_kb, Et]), len(df)
