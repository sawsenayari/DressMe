"""python -m training.train [--styles data/styles.csv] [--feedback data/feedback.db]
Données synthétiques (contexte x tenue) étiquetées par l'oracle de règles + bruit, puis réajustées avec le feedback réel."""
import argparse, json, random, sqlite3
from pathlib import Path
import joblib, numpy as np
from tqdm import tqdm
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import roc_auc_score
from app.catalog import builtin_catalog, load_styles, sample_wardrobe
from app.features import FEATURES, FORMALITY, OCCASIONS, Context, featurize, utility, vector
from app.outfits import generate

def sample_context(rng):
    eid = int(rng.random() < .03)
    occ = "religious" if eid else rng.choices(OCCASIONS, [4, 4, 1, 1, 1, 1, 1.5])[0]
    form = int(np.clip(FORMALITY[occ] + rng.choice([0, 0, 0, 1, -1]), 0, 3))
    rain = rng.uniform(.3, 1) if rng.random() < .3 else rng.uniform(0, .2)
    return Context(rng.uniform(2, 42), rain, rng.uniform(0, 40), occ, form, rng.randint(6, 11), int(rng.random() < .1), eid)

def build(n_ctx, n_cand, seed, catalog, tunisian):
    rng, nrng = random.Random(seed), np.random.default_rng(seed)
    X, y, g, Z, U = [], [], [], [], []
    for c in tqdm(range(n_ctx), desc="Génération des données", unit="contexte"):
        ctx = sample_context(rng)
        cands = generate(sample_wardrobe(catalog, rng, tunisian, gender=rng.choice(['Men', 'Women'])), max_n=n_cand, rng=rng)
        rows = [featurize(ctx, o) for o in cands]
        u0 = np.array([utility(r) for r in rows]); u = u0 + nrng.normal(0, .4, len(rows))
        lab = u >= np.quantile(u, .75); Z += ((u - u.mean()) / (u.std() + 1e-6)).tolist(); U += u0.tolist()   # Z : score normalisé par contexte (régression)
        X += [vector(r) for r in rows]; y += lab.astype(int).tolist(); g += [c] * len(rows)
    return np.array(X), np.array(y), np.array(g), np.array(Z), np.array(U)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--styles"); ap.add_argument("--feedback"); ap.add_argument("--n-ctx", type=int, default=2500)
    ap.add_argument("--n-cand", type=int, default=100); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--objective", choices=["classify", "regress"], default="classify", help="classify (défaut) : top 25 % oui/non ; regress : score fin. Mesuré : équivalents (regret 0,025 contre 0,028)")
    a = ap.parse_args()
    base = builtin_catalog(); tun = [i for i in base if i["usage"] == "Ethnic"]
    catalog = (load_styles(a.styles) + base) if a.styles else base
    X, y, g, Z, U = build(a.n_ctx, a.n_cand, a.seed, catalog, tun)
    te = g >= int(a.n_ctx * .8)
    reg = a.objective == "regress"; mk = lambda: (HistGradientBoostingRegressor if reg else HistGradientBoostingClassifier)(max_iter=300, learning_rate=.08, max_depth=6, random_state=a.seed)
    model = mk().fit(X[~te], (Z if reg else y)[~te])
    Xt, yt, gt, Ut = X[te], y[te], g[te], U[te]; p = model.predict(Xt) if reg else model.predict_proba(Xt)[:, 1]
    fi = {k: i for i, k in enumerate(FEATURES)}
    bad = lambda r: r[fi["abs_warmth_gap"]] > 2 or r[fi["open_x_rain"]] > .5
    p1, rnd, viol, viol_rnd, viol_or, reg_m, reg_r = [], [], [], [], [], [], []
    for c in np.unique(gt):
        m = gt == c; Xc, yc = Xt[m], yt[m]; b = int(np.argmax(p[m]))
        reg_m.append(Ut[m].max() - Ut[m][b]); reg_r.append(Ut[m].max() - Ut[m].mean())   # regret = écart d'utilité avec le meilleur choix possible
        p1.append(yc[b]); rnd.append(yc.mean()); viol.append(bad(Xc[b])); viol_rnd.append(np.mean([bad(r) for r in Xc]))
        viol_or.append(bad(Xc[int(np.argmax([utility(dict(zip(FEATURES, r))) for r in Xc]))]))
    metrics = {"objective": a.objective, "mean_utility_regret": round(float(np.mean(reg_m)), 4), "mean_utility_regret_random": round(float(np.mean(reg_r)), 4), "auc": round(roc_auc_score(yt, p), 4), "precision_at_1": round(float(np.mean(p1)), 4),
               "precision_at_1_random": round(float(np.mean(rnd)), 4),
               "constraint_violation_top1": round(float(np.mean(viol)), 4),
               "constraint_violation_random": round(float(np.mean(viol_rnd)), 4),
               "constraint_violation_oracle_best_possible": round(float(np.mean(viol_or)), 4), "rows": int(len(y))}
    Xf, yf, w = X, (Z if reg else y), np.ones(len(y))  # modèle final : tout + feedback réel (poids x5)
    if a.feedback and Path(a.feedback).exists():
        rows = sqlite3.connect(a.feedback).execute("SELECT features, accepted FROM feedback").fetchall()
        if rows:
            Xf = np.vstack([X, [[json.loads(r[0]).get(k, 0) for k in FEATURES] for r in rows]])
            yf = np.concatenate([yf, [(1.5 if r[1] else -1.5) if reg else r[1] for r in rows]]); w = np.concatenate([w, np.full(len(rows), 5.0)])
            metrics["feedback_rows"] = len(rows)
    model = mk().fit(Xf, yf, sample_weight=w)
    Path("models").mkdir(exist_ok=True)
    joblib.dump({"model": model, "features": FEATURES, "kind": a.objective}, "models/ranker.joblib")
    Path("models/metrics.json").write_text(json.dumps(metrics, indent=2)); print(json.dumps(metrics, indent=2))

if __name__ == "__main__": main()
