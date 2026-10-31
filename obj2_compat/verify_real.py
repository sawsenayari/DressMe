"""Rejoue le test réel pilote avec le service (core.py) et compare à l'étape 5B.
Usage :  python verify_real.py real_embeddings.npz [resultat_5B.csv]"""
import sys, json, numpy as np
from scipy.stats import spearmanr
from core import CompatEngine

RATINGS = {'A':  [1,3,4,4,5,5,1,1,4,4,4,5,1,1,1,4,4,5,5,5,4,5,5,4,4,1,1],
           'A2': [1,3,4,5,5,5,1,1,5,1,1,4,1,1,2,5,3,5,3,1,5,1,1,1,3,1,1]}
d = np.load(sys.argv[1], allow_pickle=True)
EW, EC, catW, catC = d['EW'], d['EC'], [str(c) for c in d['catW']], [str(c) for c in d['catC']]
E = CompatEngine()
mk = lambda e, c, i: {"id": i, "embedding": e.tolist(), "category": c}
W = [mk(EW[j], catW[j], f"W{j+1}") for j in range(len(EW))]
res = [E.compat(mk(EC[k], catC[k], f"C{k+1}"), W) for k in range(len(EC))]
pct = np.array([r["rank100"] for r in res], dtype=float)
human = np.mean([RATINGS['A'], RATINGS['A2']], axis=0)
assert len(pct) == len(human), f"{len(pct)} candidats mais {len(human)} notes"
print(f"Spearman service vs humains : {spearmanr(pct, human).statistic:+.2f}   (5B : +0.44)")
print("Percentiles C1..C8 :", pct[:8].astype(int).tolist())
if len(sys.argv) > 2:
    import pandas as pd
    ref = pd.read_csv(sys.argv[2]); p5 = ref["percentile_modele"].to_numpy(dtype=float)
    diff = np.abs(p5 - pct)
    print(f"Écart avec 5B : moyen {diff.mean():.1f} points, max {diff.max():.0f} ; identiques à 3 points près : {(diff <= 3).sum()}/{len(diff)}")
    print("Candidats en désaccord (>3 points) :", [f"C{k+1}: 5B={int(p5[k])} service={int(pct[k])}" for k in np.where(diff > 3)[0]])
