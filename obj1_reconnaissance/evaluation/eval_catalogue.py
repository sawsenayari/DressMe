"""Section B du notebook : évaluation sur les 120 images de catalogue réservées + ablations.
Sert de jeu DEV pour régler les seuils (jamais les 30 photos réelles). Les appels LLM sont en cache : les ablations sont quasi gratuites.

    from evaluation.eval_catalogue import run_catalogue_eval
    run_catalogue_eval(svc, tag="v1")                                      # full
    run_catalogue_eval(svc, tag="llm_only", mode="llm_only")
    run_catalogue_eval(svc, tag="knn_only", mode="knn_only")
    svc.cfg.after_rag_policy = "llm"; run_catalogue_eval(svc, tag="after_rag_llm")"""
from __future__ import annotations
import json
import pandas as pd
from recognition.imaging import load_image
from recognition.taxonomy import coarse
from .metrics import wilson


def run_catalogue_eval(svc, tag: str = "v1", mode: str = "full") -> pd.DataFrame:
    out = svc.cfg.out / f"agent_eval_{tag}.jsonl"; done = {}
    if out.exists():
        for line in open(out, encoding="utf-8"):
            try: r = json.loads(line); done[r["id"]] = r
            except Exception: pass
    for _, row in svc.test_df.iterrows():
        if int(row.id) in done: continue
        r = svc.agent.run(load_image(svc.img_src / f"{int(row.id)}.jpg"), mode)
        rec = dict(id=int(row.id), truth=row.category, truth_color=row.color if isinstance(row.color, str) else None,
                   truth_gender=row.gender if isinstance(row.gender, str) else None, final=r["category"], source=r["source"], status=r["status"],
                   confidence=r["confidence"], H=r["H"], calls=r["llm_calls"], latency=r["latency_s"], color=r["color"], gender=r["gender"],
                   fp_valid=r["first"]["valid"], fp_cat=r["first"]["category"], fp_color=r["first"]["color"], fp_gender=r["first"]["gender"], trace="\n".join(r["trace"]))
        with open(out, "a", encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        done[rec["id"]] = rec
    ev = pd.DataFrame(done.values()); ev = ev[ev.id.isin(svc.test_df.id)].reset_index(drop=True)
    ok = ev.final == ev.truth; lo, hi = wilson(int(ok.sum()), len(ev)); ans = ev.status == "OK"
    print(f"[{tag}] précision finale {ok.mean():.3f} IC95 [{lo:.3f};{hi:.3f}] | groupée {sum(coarse(a) == coarse(b) for a, b in zip(ev.final, ev.truth)) / len(ev):.3f} "
          f"| REVIEW {1 - ans.mean():.3f} | appels LLM {ev.calls.mean():.2f}")
    print(ev.assign(correct=ok).groupby("source").agg(n=("id", "count"), précision=("correct", "mean")).round(3))
    tc = ev.truth_color.notna(); tg = ev.truth_gender.notna()
    print(f"couleur finale {(ev.color[tc] == ev.truth_color[tc]).mean():.3f} | genre final {(ev.gender[tg] == ev.truth_gender[tg]).mean():.3f}")
    ev.to_csv(svc.cfg.out / f"agent_eval_{tag}.csv", index=False); return ev
