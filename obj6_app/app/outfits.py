import random
from collections import defaultdict

def generate(items, max_n=3000, rng=None):
    """Candidats de tenues (stand-in de l'objectif 3 : branche ici ton outfit-matching quand il est prêt)."""
    by = defaultdict(list)
    for i in items: by[i["slot"]].append(i)
    foot = by["footwear"] or [None]; outers = [None] + by["outer"]
    base = [(t, b) for t in by["top"] for b in by["bottom"]] + [(o,) for o in by["onepiece"]]
    out = [tuple(x for x in (*b, f, o) if x) for b in base for f in foot for o in outers]
    return (rng or random).sample(out, max_n) if len(out) > max_n else out

def diversify(ranked, k):
    """Évite de proposer k fois la même tenue avec un seul article changé."""
    chosen = []
    for score, outfit, feats in ranked:
        ids = {i["id"] for i in outfit}
        if all(len(ids & {i["id"] for i in c[1]}) < max(1, len(ids) - 1) for c in chosen):
            chosen.append((score, outfit, feats))
        if len(chosen) == k: break
    return chosen

def pick_accessories(outfit, accs, ctx, k=2):
    """Touche finale : meilleur accessoire par type (sac, montre, ceinture…), choisi selon formalité, météo et couleurs."""
    from .features import NEUTRALS
    cols = {i["colour"] for i in outfit}; best = {}
    for a in accs:
        t = a.get("type") or a["name"]
        s = -.7 * abs(a["formality"] - ctx.formality) + (.8 if a["colour"] in NEUTRALS or a["colour"] in cols else -.4)
        if t == "Scarves": s += 1 if ctx.feels_like < 14 else -3
        if t == "Sunglasses": s += .8 if ctx.rain_prob < .3 and ctx.feels_like > 18 else -3
        if t == "Caps": s -= 2 if ctx.formality >= 2 else 0
        if t == "Ties": s += 1 if ctx.formality >= 3 else -3
        if t in ("Handbags", "Clutches"): s += .5
        if s > best.get(t, (-9, None))[0]: best[t] = (s, a)
    return [a for s, a in sorted(best.values(), key=lambda x: -x[0]) if s > 0][:k]
