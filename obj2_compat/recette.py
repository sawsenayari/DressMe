"""Recette finale du service (objectif 2) : lance tout et affiche un rapport PASS / FAIL.

Usage :  python recette.py [real_embeddings.npz resultat_5B.csv]
Sans arguments, le rejeu du test réel est ignoré (SKIP). Code de sortie 0 = tout passe.
"""
import hashlib, json, os, subprocess, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, HERE)
RES = []
def check(name, ok, detail=""):
    ok = None if ok is None else bool(ok)
    RES.append((name, ok)); print(f"[{'PASS' if ok is True else ('SKIP' if ok is None else 'FAIL')}] {name}" + (f" : {detail}" if detail else ""))
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()[:16]

# 1. Fichiers présents et empreintes (versions figées)
need = ["core.py", "app.py", "reference.npz", "requirements.txt", "README.md", "golden.json",
        "models/final_image_s0.pt", "models/final_image_s1.pt", "models/final_image_s2.pt", "tests/test_core.py", "embed_cards.py"]
miss = [f for f in need if not os.path.exists(f)]
check("1. fichiers présents", not miss, f"manquants : {miss}" if miss else "11/11")
man = json.load(open("manifest.json")) if os.path.exists("manifest.json") else None
if man:
    bad = [f for f, h in man.items() if not os.path.exists(f) or sha(f) != h]
    check("1b. empreintes modèles et référence identiques à la version livrée", not bad, f"modifiés : {bad}" if bad else "")
else:
    check("1b. empreintes", None, "manifest.json absent")

# 2. Tests automatiques
r = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests"], capture_output=True, text=True)
check("2. tests automatiques", r.returncode == 0, r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:])

# 3. Non-régression : mêmes sorties que la version livrée sur 5 appels fixes
from core import CompatEngine
E = CompatEngine(); R = np.load("reference.npz")
it = lambda k: {"id": f"A{k}", "embedding": R["pool_img"][k].tolist(), "category": E.cats[int(R["pool_cat"][k])]}
gold = json.load(open("golden.json")); ok = True; det = ""
for g in gold:
    out = E.compat(it(g["candidate"]), [it(k) for k in g["wardrobe"]])
    if out["rank100"] != g["rank100"] or out["duplicate"]["pct"] != g["dup_pct"] or out["verdict"] != g["verdict"]:
        ok = False; det += f" cas {g['candidate']}: {out['rank100']} != {g['rank100']};"
check("3. non-régression (5 appels figés)", ok, det or "identique")

# 4. Test réel rejoué (facultatif)
if len(sys.argv) >= 3:
    from scipy.stats import spearmanr; import pandas as pd
    RAT = {'A': [1,3,4,4,5,5,1,1,4,4,4,5,1,1,1,4,4,5,5,5,4,5,5,4,4,1,1],
           'A2': [1,3,4,5,5,5,1,1,5,1,1,4,1,1,2,5,3,5,3,1,5,1,1,1,3,1,1]}
    d = np.load(sys.argv[1], allow_pickle=True)
    mk = lambda e, c, i: {"id": i, "embedding": e.tolist(), "category": str(c)}
    W = [mk(d['EW'][j], d['catW'][j], f"W{j+1}") for j in range(len(d['EW']))]
    pct = np.array([E.compat(mk(d['EC'][k], d['catC'][k], f"C{k+1}"), W)["rank100"] for k in range(len(d['EC']))], float)
    sp = spearmanr(pct, np.mean(list(RAT.values()), axis=0)).statistic
    p5 = pd.read_csv(sys.argv[2])["percentile_modele"].to_numpy(float)
    check("4. test réel : Spearman proche de +0,44", abs(sp - 0.44) <= 0.03, f"{sp:+.2f}")
    check("4b. test réel : percentiles à 3 points de l'étape 5B", bool((np.abs(p5 - pct) <= 3).all()), f"écart max {np.abs(p5 - pct).max():.0f}")
else:
    check("4. rejeu du test réel", None, "fournir real_embeddings.npz et resultat_5B.csv")

# 5. API réelle (serveur lancé en sous-processus) : contrat, erreurs, vitesse
import httpx
port = 8765
srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "app:app", "--port", str(port), "--log-level", "warning"])
try:
    base = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            if httpx.get(base + "/health", timeout=2).status_code == 200: break
        except Exception: time.sleep(0.5)
    h = httpx.get(base + "/health").json(); check("5a. /health", h.get("ok") is True and len(h["categories"]) == 11)
    W = [it(k) for k in (0, 1, 2, 3, 4)]
    t = time.time(); c = httpx.post(base + "/compat", json={"candidate": it(1500), "wardrobe": W}, timeout=60); dt = time.time() - t
    j = c.json(); keys = {"rank100", "score01", "verdict", "partners", "duplicate", "model"}
    check("5b. /compat : contrat", c.status_code == 200 and set(j) == keys and 0 <= j["rank100"] <= 100)
    check("5c. /compat : < 2 s", dt < 2, f"{dt*1000:.0f} ms")
    p = httpx.post(base + "/pairs", json={"a": [it(k) for k in range(3)], "b": [it(k) for k in range(1000, 1004)]}, timeout=60).json()
    check("5d. /pairs : contrat", set(p) == {"scores01", "verdicts", "thresholds"} and len(p["scores01"]) == 3 and len(p["scores01"][0]) == 4)
    check("5e. erreur claire (garde-robe trop petite)", httpx.post(base + "/compat", json={"candidate": it(5), "wardrobe": W[:1]}).status_code == 422)
    bad = it(7); bad["embedding"] = [1.0] * 10
    check("5f. erreur claire (embedding de mauvaise taille)", httpx.post(base + "/compat", json={"candidate": bad, "wardrobe": W}).status_code == 422)
    big = [it(k) for k in range(121)]; t = time.time()   # 2 122 paires environ : la taille du besoin de l'objectif 4
    httpx.post(base + "/pairs", json={"a": big[:46], "b": big[46:92]}, timeout=300); dtp = time.time() - t
    check("5g. /pairs : 2 116 paires < 30 s (besoin de l'objectif 4)", dtp < 30, f"{dtp:.0f} s")
finally:
    srv.terminate()

n_fail = sum(1 for _, o in RES if o is False)
print(f"\nRÉSULTAT : {sum(1 for _, o in RES if o is True)} PASS, {n_fail} FAIL, {sum(1 for _, o in RES if o is None)} SKIP")
sys.exit(1 if n_fail else 0)
