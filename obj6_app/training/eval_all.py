"""Lance les 3 évaluations et écrit reports/evaluation_summary.md. python -m training.eval_all [--n 8]"""
import argparse, os
from pathlib import Path
from . import eval_agent, eval_judge, eval_tools

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=8); a = ap.parse_args(argv)
    ag, ju, to = eval_agent.main([]), eval_judge.main(["--n", str(a.n)]), eval_tools.main([])
    md = ["# Évaluation des composants LLM", "", "## 1. Agent agenda (jeu étiqueté)", "| Mode | Exactitude occasion | MAE formalité | Traité par le LLM |", "|---|---|---|---|"]
    md += [f"| {m} | {ag[m]['occasion_accuracy']} | {ag[m]['formality_mae']} | {ag[m]['answered_by_llm']} |" for m in ("rules", "llm", "rag")]
    md += ["", "## 2. LLM-as-a-judge (explications)", *[f"Juge {j} : détection des défauts {v['detection_rate']} ; fausses alertes sur les bonnes explications {v['false_alarm_on_good']} ; notes par variante {({t: x['overall'] for t, x in v['by_variant'].items()})}" for j, v in ju['judges'].items()],
           f"Accord entre juges (Spearman) : {ju.get('agreement_between_judges_spearman')}", "", "## 3. Assistant à outils", *[f"- {k} : {v}" for k, v in to.items()]]
    p = Path(os.getenv("DRESSME_REPORTS", "reports")) / "evaluation_summary.md"; p.write_text("\n".join(md), encoding="utf-8"); print("écrit :", p)

if __name__ == "__main__": main()
