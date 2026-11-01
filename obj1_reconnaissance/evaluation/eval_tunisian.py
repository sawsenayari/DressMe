"""Évaluation sur le jeu tunisien (split dev pour régler, split test UNE seule fois à la fin).

Compare, sur les MÊMES photos :
  clip_zeroshot            FashionCLIP seul, sans aucun exemple (sondes texte)  -> « FashionCLIP reconnaît-il ces pièces ? »
  knn_catalogue            kNN avec la base catalogue seule
  knn_+tn_refs             kNN avec les références tunisiennes (train) ajoutées
  llm_only                 Qwen seul
  full_catalogue           agent complet, base catalogue seule
  full_+tn_refs            agent complet, avec références tunisiennes
  full_+tn_refs_+prompt    idem + description des pièces tunisiennes dans le prompt
Mesures : précision (Wilson 95 %), F1 macro, rappel de `traditional_garment`, précision du sous-type (jebba, farmla…)."""
from __future__ import annotations
from pathlib import Path
import numpy as np, pandas as pd
from recognition.imaging import load_image, open_rgb
from recognition.itemcard_builder import traditional_subtype
from recognition.taxonomy import CATEGORIES
from recognition.tunisian import load_tunisian, prepare_crops
from .metrics import wilson, macro_f1

ZS_PROMPTS = {"tshirt": "a t-shirt", "shirt": "a button-up shirt", "top": "a blouse or tank top", "sweater": "a sweater or hoodie", "jacket": "a jacket",
              "blazer": "a blazer", "coat": "a long coat", "dress": "a dress", "skirt": "a skirt", "jeans": "a pair of jeans", "pants": "a pair of trousers",
              "shorts": "a pair of shorts", "underwear": "underwear", "shoes": "a pair of shoes", "bag": "a bag", "accessory": "a fashion accessory",
              "traditional_garment": "a traditional Tunisian garment such as a jebba, farmla, blouza or kaftan"}


def _zeroshot(svc, imgs):
    T = svc.shared.texts([f"a photo of {ZS_PROMPTS[c]}" for c in CATEGORIES]); I = svc.shared.images(imgs)
    return [CATEGORIES[i] for i in (I @ T.T).argmax(1)]


def run_tunisian_eval(svc, split: str = "dev", out_dir: str | Path | None = None, systems: tuple | None = None, tag: str = "") -> dict:
    cfg, agent = svc.cfg, svc.agent
    df, issues = load_tunisian(cfg, split)
    if not len(df): print(f"Aucune photo tunisienne valide dans le split '{split}'."); return {}
    df = prepare_crops(cfg, df, svc.cropper); imgs = [load_image(p) for p in df.crop_path]; out_dir = Path(out_dir or cfg.out / f"tunisian_eval_{split}{'_' + tag if tag else ''}"); out_dir.mkdir(parents=True, exist_ok=True)
    has_refs = getattr(svc, "retr_ref", None) is not getattr(svc, "retr_base", None)
    plan = {"clip_zeroshot": None, "knn_catalogue": ("knn_only", "base", False), "knn_+tn_refs": ("knn_only", "ref", False), "llm_only": ("llm_only", "base", False),
            "full_catalogue": ("full", "base", False), "full_+tn_refs": ("full", "ref", False), "full_+tn_refs_+prompt": ("full", "ref", True)}
    if not has_refs: plan = {k: v for k, v in plan.items() if "tn_refs" not in k}
    if systems: plan = {k: v for k, v in plan.items() if k in systems}
    keep = (agent.retriever, cfg.tunisian_prompt); preds, subs = {}, {}
    try:
        for name, spec in plan.items():
            if spec is None: preds[name] = _zeroshot(svc, imgs); continue
            mode, which, prompt = spec; agent.retriever = svc.retr_ref if which == "ref" else svc.retr_base; cfg.tunisian_prompt = prompt; P, S = [], []
            for im in imgs:
                r = agent.run(im, mode); P.append(r["category"] if r["category"] != "unknown" else r["knn"]["category"]); S.append(traditional_subtype(r["neighbors"], cfg.subtype_min_share)[0])
            preds[name] = P; subs[name] = S
    finally: agent.retriever, cfg.tunisian_prompt = keep
    truth = df.category.tolist(); rows = []
    for name, P in preds.items():
        ok = np.array([a == b for a, b in zip(truth, P)]); lo, hi = wilson(int(ok.sum()), len(ok)); trad = np.array([t == "traditional_garment" for t in truth])
        row = dict(systeme=name, n=len(ok), precision=ok.mean(), ic95=(round(lo, 3), round(hi, 3)), f1_macro=macro_f1(truth, P),
                   rappel_traditional=(ok[trad].mean() if trad.any() else np.nan), n_traditional=int(trad.sum()))
        if name in subs:
            m = np.array([t == "traditional_garment" and s != "" for t, s in zip(truth, df.subtype)])
            row["precision_sous_type"] = float(np.mean([a == b for a, b, k in zip(df.subtype, subs[name], m) if k])) if m.any() else np.nan
        rows.append(row)
    S = pd.DataFrame(rows).set_index("systeme"); S.to_csv(out_dir / "summary.csv")
    pd.DataFrame({"image": df.image_path, "truth": truth, **{k: v for k, v in preds.items()}}).to_csv(out_dir / "predictions.csv", index=False)
    print(S.round(3).to_string()); print(f"\nrésultats : {out_dir}  (split={split}, n={len(df)})")
    if split == "test": print("⚠️ split test : à ne regarder qu'UNE fois, après avoir figé les réglages sur dev.")
    return dict(summary=S, predictions=preds, data=df)
