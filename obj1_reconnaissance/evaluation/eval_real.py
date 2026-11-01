"""Évaluation sur les PHOTOS RÉELLES (livrable : 30 photos de téléphone, déjà découpées par le crop partagé).

labels.csv (étiqueté par 2 personnes puis arbitré) — colonnes :
    image_path, true_category (17 classes), true_colour (14 couleurs)   [facultatif : true_type, true_usage, wardrobe]
    python -m evaluation.eval_real labels.csv      (ou run_real_eval(svc, 'labels.csv') depuis le notebook)

Compare 3 systèmes sur les MÊMES images : agent complet, LLM seul, kNN seul (références exigées par l'évaluation commune)."""
from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
from contracts import slot_of
from .metrics import wilson, macro_f1, bootstrap_ci, mcnemar_exact, confidence_table

MODES = ("full", "llm_only", "knn_only")


def run_real_eval(svc, labels_csv: str | Path, out_dir: str | Path | None = None, modes=MODES) -> dict:
    lab = pd.read_csv(labels_csv).fillna(""); base = Path(labels_csv).parent; out_dir = Path(out_dir or svc.cfg.out / "real_eval"); out_dir.mkdir(parents=True, exist_ok=True)
    allrows, summ = {}, []
    for m in modes:
        rows = []
        for _, r in lab.iterrows():
            p = Path(r.image_path); p = p if p.is_absolute() else base / p
            res = svc.recognize(p, item_id=None, out_dir=out_dir / f"cards_{m}", mode=m); c = res.card
            rows.append(dict(image=str(p), true_category=r.true_category, pred_category=res.category, true_slot=slot_of(r.true_category) or "none",
                             pred_slot=c.slot if c else "none", true_colour=r.true_colour, pred_colour=(c.colour[0] if c else None),
                             true_type=r.get("true_type", ""), pred_type=(c.type if c else None), status=res.status, conf_slot=c.confidence.slot if c else 0.0,
                             conf_type=c.confidence.type if c else 0.0, conf_colour=c.confidence.colour if c else 0.0, source=res.debug.get("source", ""),
                             latency=res.debug.get("latency_s", 0.0), reasons=";".join(res.reasons)))
        df = pd.DataFrame(rows); df.to_csv(out_dir / f"predictions_{m}.csv", index=False); allrows[m] = df; n = len(df)
        ok_slot, ok_cat, ok_col = df.true_slot == df.pred_slot, df.true_category == df.pred_category, df.true_colour == df.pred_colour
        row = dict(systeme=m, n=n, slot=ok_slot.mean(), slot_ic=wilson(int(ok_slot.sum()), n), categorie=ok_cat.mean(), categorie_ic=wilson(int(ok_cat.sum()), n),
                   couleur=ok_col.mean(), couleur_ic=wilson(int(ok_col.sum()), n), f1_macro_cat=macro_f1(df.true_category.tolist(), df.pred_category.tolist()),
                   f1_macro_ic=bootstrap_ci(df.true_category.tolist(), df.pred_category.tolist(), macro_f1),
                   taux_revue=(df.status != "ok").mean())
        if (df.true_type != "").all(): ok_t = df.true_type == df.pred_type; row.update(type=ok_t.mean(), type_ic=wilson(int(ok_t.sum()), n))
        summ.append(row)
    S = pd.DataFrame(summ).set_index("systeme"); S.to_csv(out_dir / "summary.csv"); print(S.round(3).to_string())
    if "full" in allrows and "llm_only" in allrows:
        a, b = allrows["full"], allrows["llm_only"]
        print("McNemar exact (catégorie, full vs llm_only) p =", round(mcnemar_exact((a.true_category == a.pred_category).tolist(), (b.true_category == b.pred_category).tolist()), 4))
    if "full" in allrows:
        f = allrows["full"]; print("\nPrécision du slot par tranche de confiance (calibration) :")
        print(pd.DataFrame(confidence_table(f.conf_slot, f.true_slot == f.pred_slot)).round(3).to_string(index=False))
        err = f[f.true_category != f.pred_category]; print("\nConfusions :"); print(err.groupby(["true_category", "pred_category"]).size().sort_values(ascending=False).head(10).to_string())
    return dict(summary=S, predictions=allrows)


if __name__ == "__main__":
    from recognition.service import RecognitionService
    run_real_eval(RecognitionService.from_config(), sys.argv[1])
