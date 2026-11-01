"""Notation humaine (sans voir les notes du juge) pour vérifier le juge. python -m training.label_cases [--csv reports/judge_cases.csv] [--n 15]
Ensuite : python -m training.eval_judge --compare reports/judge_cases.csv"""
import argparse, csv
from pathlib import Path

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--csv", default="reports/judge_cases.csv"); ap.add_argument("--n", type=int, default=30); a = ap.parse_args(argv)
    rows = list(csv.DictReader(open(a.csv, encoding="utf-8"))); todo = [r for r in rows if not r["humain_score_1a5"].strip()][:a.n]
    print("Note chaque explication de 1 (mauvaise) à 5 (excellente) : pertinente pour la météo et l'occasion, sans vêtement inventé, honnête sur les alertes, courte.\nEntrée = passer, q = quitter.\n")
    for k, r in enumerate(todo, 1):
        print(f"--- {k}/{len(todo)}\nContexte : {r['contexte']}\nArticles : {r['articles']}\nAlertes  : {r['alertes'] or '(aucune)'}\nExplication : {r['explication']}")
        v = input("Note 1-5 > ").strip()
        if v.lower() == "q": break
        if v in {"1", "2", "3", "4", "5"}: r["humain_score_1a5"] = v
    with open(a.csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"{sum(bool(r['humain_score_1a5'].strip()) for r in rows)} notes enregistrées dans {a.csv}")

if __name__ == "__main__": main()
