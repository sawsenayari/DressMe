"""ÉVALUATION 2 — LLM-as-a-judge sur les explications de la styliste IA, avec contrôle de la fiabilité du juge.
python -m training.eval_judge [--n 8] [--compare reports/judge_cases.csv]
Le juge note 4 critères (1-5). Contrôle : une explication prise dans un AUTRE contexte doit recevoir une note plus basse."""
import argparse, asyncio, csv, json, os, random
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from app.agent import explain
from app.features import FORMALITY
from app.rag import retrieve
from .evalkit import judge_json, save

SCENARIOS = [("casual", 22, .05, "Women"), ("work", 12, .7, "Men"), ("formal", 30, 0, "Women"), ("sport", 22, .1, "Women"), ("wedding", 26, 0, "Women"),
             ("religious", 15, .2, "Men"), ("party", 18, .1, "Men"), ("casual", 38, 0, "Men"), ("casual", 4, .3, "Women"), ("work", 24, .2, "Women")]
CRITERIA = ("pertinence", "fidelite", "honnetete", "clarte")
JUDGE = """Tu es un évaluateur strict et impartial. On te donne un contexte, la liste EXACTE des articles d'une tenue, d'éventuelles alertes et
l'explication écrite par un styliste IA. Note l'explication de 1 à 5 sur chaque critère :
- pertinence : s'appuie sur des éléments réels du contexte (météo, occasion) et justifie correctement (1 = hors sujet ou faux, 5 = précis)
- fidelite : ne mentionne AUCUN vêtement absent de la liste (1 = invente des vêtements, 5 = aucun ajout)
- honnetete : signale les alertes au lieu de les masquer ; n'invente pas d'alerte s'il n'y en a pas (1 = masque ou invente, 5 = exact)
- clarte : une phrase courte (25 mots max), en français correct
Ne favorise pas les textes longs. Réponds uniquement par un JSON :
{"pertinence": int, "fidelite": int, "honnetete": int, "clarte": int, "commentaire": "20 mots max"}"""

async def build_cases(n):
    from app.main import RecommendRequest, recommend
    cases, failures = [], 0
    for sc, (occ, t, rain, g) in enumerate(SCENARIOS[:n]):
        r = await recommend(RecommendRequest(occasion=occ, gender=g, weather={"feels_like": t, "rain_prob": rain}, k=3, uid="eval", when=datetime(2026, 10, 22, 8)))
        outs = r["outfits"]; ctx = {"occasion": occ, "formality": FORMALITY[occ], "feels_like": t, "rain_prob": rain, "ramadan": 0, "eid": 0}
        ex = await explain(ctx, [{"articles": [i["name"] for i in o["items"]], "alertes": o["warnings"]} for o in outs], retrieve(occ))
        if not ex: failures += 1; continue
        cases += [dict(sc=sc, contexte={"occasion": occ, "temperature_ressentie": t, "proba_pluie": rain}, articles=[i["name"] for i in o["items"]],
                       alertes=o["warnings"], explication=e) for o, e in zip(outs, ex)]
    return cases, failures

async def score(case, explication, model=None):
    d = await judge_json(JUDGE, {"contexte": case["contexte"], "articles": case["articles"], "alertes": case["alertes"], "explication": explication}, model)
    return {k: int(d[k]) for k in CRITERIA} | {"commentaire": d.get("commentaire", "")}

overall = lambda s: (s["pertinence"] + s["fidelite"] + s["honnetete"]) / 3
INJECT = " Complétez avec un manteau en fourrure et des bottes de ski."      # défaut injecté : vêtements inventés
MASK = "Cette tenue convient parfaitement à la situation, sans aucun point faible."   # défaut injecté : alertes masquées
DETECT = {"autre_contexte": lambda x: min(x["pertinence"], x["fidelite"]) <= 2, "invente": lambda x: x["fidelite"] <= 2, "alerte_masquee": lambda x: x["honnetete"] <= 2}

def variants(cases):
    """Pour chaque cas : la vraie explication + des versions volontairement défectueuses. Le juge doit les distinguer."""
    out = []
    for i, c in enumerate(cases):
        other = cases[(i + len(cases) // 2) % len(cases)]
        out += [(i, "bonne", c["explication"]), (i, "autre_contexte", other["explication"]), (i, "invente", c["explication"] + INJECT)]
        if c["alertes"]: out.append((i, "alerte_masquee", MASK))
    return out

def summarize(V, rs):
    by = defaultdict(list)
    for (_, t, _), r in zip(V, rs):
        if r: by[t].append(r)
    mean = lambda l, f: round(sum(f(x) for x in l) / len(l), 2) if l else None
    good = by.get("bonne", [])
    return {"by_variant": {t: {"n": len(l), "overall": mean(l, overall), **{k: mean(l, lambda x, k=k: x[k]) for k in CRITERIA}} for t, l in by.items()},
            "detection_rate": {t: round(sum(DETECT[t](x) for x in by[t]) / len(by[t]), 2) for t in DETECT if by.get(t)},   # défauts détectés (note ≤ 2)
            "false_alarm_on_good": round(sum(min(x["pertinence"], x["fidelite"], x["honnetete"]) <= 2 for x in good) / len(good), 2) if good else None,
            "judge_failures": sum(r is None for r in rs)}

def _rho(a, b):
    from scipy.stats import spearmanr
    import warnings
    if len(a) < 3: return None
    with warnings.catch_warnings(): warnings.simplefilter("ignore"); v = spearmanr(a, b)[0]
    return None if v != v else round(float(v), 3)

async def amain(n=8):
    cases, gen_fail = await build_cases(n); V = variants(cases); judges = [m for m in (os.getenv("LLM_MODEL_JUDGE"), os.getenv("LLM_MODEL_JUDGE2")) if m] or [None]; res = {}
    for jm in judges:
        res[jm] = []
        for i, t, text in V:
            try: res[jm].append(await score(cases[i], text, jm))
            except Exception as e: print("juge indisponible :", jm, repr(e)[:120]); res[jm].append(None)
    out = {"cases": len(cases), "variants_judged": len(V), "generation_failures": gen_fail, "judges": {str(jm): summarize(V, r) for jm, r in res.items()},
           "within_25_words": f"{sum(len(c['explication'].split()) <= 25 for c in cases)}/{len(cases)}"}
    if len(judges) == 2:
        pr = [(overall(a), overall(b)) for a, b in zip(*res.values()) if a and b]; out["agreement_between_judges_spearman"] = _rho(*zip(*pr)) if pr else None
    p = save("judge", out); print(json.dumps(out, indent=2, ensure_ascii=False)); rows = []
    for k, (i, t, text) in enumerate(V):
        o = [round(overall(r[k]), 2) if r[k] else "" for r in res.values()] + [""] * (2 - len(res))
        c = cases[i]; rows.append([t, json.dumps(c["contexte"], ensure_ascii=False), "; ".join(c["articles"]), "; ".join(c["alertes"]), text, *o, ""])
    random.Random(0).shuffle(rows)   # ordre mélangé : l'annotateur ne voit pas la structure
    with open(Path(p) / "judge_cases.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["type", "contexte", "articles", "alertes", "explication", "juge1_overall", "juge2_overall", "humain_score_1a5"]); w.writerows(rows)
    return out

def compare(path):
    rows = [r for r in csv.DictReader(open(path, encoding="utf-8")) if r["humain_score_1a5"].strip()]; h = [float(r["humain_score_1a5"]) for r in rows]; res = {"n": len(rows)}
    for col in ("juge1_overall", "juge2_overall"):
        pr = [(float(r[col]), x) for r, x in zip(rows, h) if r[col].strip()]
        if len(pr) > 2: res[f"spearman_{col}_vs_humain"] = _rho(*zip(*pr))
    by = defaultdict(list)
    for r, x in zip(rows, h): by[r["type"]].append((x, r))
    res["par_type"] = {t: {"n": len(v), "note_humaine_moyenne": round(sum(x for x, _ in v) / len(v), 2),
                           **{c: round(sum(float(r[c]) for _, r in v if r[c].strip()) / max(1, sum(bool(r[c].strip()) for _, r in v)), 2) for c in ("juge1_overall", "juge2_overall")}} for t, v in by.items()}
    print(json.dumps(res, indent=2, ensure_ascii=False)); return res

def main(argv=None):
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=8); ap.add_argument("--compare"); a = ap.parse_args(argv)
    return compare(a.compare) if a.compare else asyncio.run(amain(a.n))

if __name__ == "__main__": main()
