"""Contexte + tenue -> features. Partagé par l'entraînement ET le serving (zéro training/serving skew)."""
from dataclasses import dataclass
import numpy as np

OCCASIONS = ["casual", "work", "formal", "sport", "wedding", "religious", "party"]
FORMALITY = {"casual": 1, "work": 2, "formal": 3, "sport": 0, "wedding": 3, "religious": 2, "party": 2}
USAGE_FOR = {"casual": {"Casual", "Smart Casual"}, "work": {"Smart Casual", "Formal"}, "formal": {"Formal", "Smart Casual"},
 "sport": {"Sports"}, "wedding": {"Formal", "Ethnic", "Party"}, "religious": {"Ethnic", "Formal", "Smart Casual"},
 "party": {"Party", "Smart Casual"}}
NEUTRALS = {"black", "white", "grey", "navy", "beige", "brown", "cream", "off white", "khaki", "tan", "silver", "charcoal"}

@dataclass
class Context:
    feels_like: float; rain_prob: float; wind: float; occasion: str; formality: int
    hour: int = 8; ramadan: int = 0; eid: int = 0

def target_warmth(feels_like, wind=0.0):
    t = feels_like - 0.1 * wind
    return float(np.clip((24 - t) * 0.3 + 3, 1.5, 9))

FEATURES = ["feels_like", "rain_prob", "wind", "occasion_idx", "formality_req", "hour", "ramadan", "eid", "warmth",
 "warmth_gap", "abs_warmth_gap", "has_outer", "n_items", "mean_formality", "formality_gap", "usage_match",
 "underdress", "foot_match", "open_sport", "open_footwear", "open_x_rain", "waterproof", "traditional", "colour_score"]

def featurize(ctx: Context, items) -> dict:
    w = sum(i["warmth"] for i in items); tw = target_warmth(ctx.feels_like, ctx.wind)
    foot = [i for i in items if i["slot"] == "footwear"]; foot_open = float(any(i["open_toe"] for i in foot))
    foot_match = float(all(i["usage"] in USAGE_FOR[ctx.occasion] for i in foot)) if foot else 1.0
    mf = float(np.mean([i["formality"] for i in items]))
    um = float(np.mean([i["usage"] in USAGE_FOR[ctx.occasion] for i in items]))
    nn = {i["colour"] for i in items if i["colour"] not in NEUTRALS}
    return dict(feels_like=ctx.feels_like, rain_prob=ctx.rain_prob, wind=ctx.wind,
        occasion_idx=OCCASIONS.index(ctx.occasion), formality_req=ctx.formality, hour=ctx.hour, ramadan=ctx.ramadan,
        eid=ctx.eid, warmth=w, warmth_gap=w - tw, abs_warmth_gap=abs(w - tw),
        has_outer=float(any(i["slot"] == "outer" for i in items)), n_items=len(items), mean_formality=mf,
        formality_gap=abs(mf - ctx.formality),
        underdress=float(max(0, ctx.formality - min(i["formality"] for i in items))), usage_match=um, open_footwear=foot_open, foot_match=foot_match, open_sport=foot_open * float(ctx.occasion == "sport"),
        open_x_rain=foot_open * ctx.rain_prob, waterproof=float(any(i["waterproof"] for i in items)),
        traditional=float(any(i["usage"] == "Ethnic" for i in items)),
        colour_score={0: 1.0, 1: 1.0, 2: 0.6}.get(len(nn), 0.2))

def vector(d): return [d[k] for k in FEATURES]

def utility(d) -> float:
    """Oracle de règles métier : sert d'étiquetage synthétique ET de fallback si aucun modèle n'est chargé."""
    u = 3 - .5 * min(d["abs_warmth_gap"], 5) - .9 * d["formality_gap"] - .8 * d["underdress"] - 2 * d["open_x_rain"] + d["usage_match"] + .6 * d["colour_score"]
    occ = OCCASIONS[int(d["occasion_idx"])]
    u -= {"sport": 1.5, "formal": 1.0, "wedding": 1.0, "work": .5}.get(occ, .2) * (1 - d["foot_match"]) + 2 * d["open_sport"]  # chaussures adaptées
    festive = d["eid"] or occ in ("wedding", "religious")
    if d["traditional"]:
        u += .8 if festive else (-1 if occ in ("sport", "work") else -.6)
    if d["rain_prob"] > .5 and d["waterproof"]: u += .4
    return float(u)

def warnings(f, ctx):
    """Alertes honnêtes sur les points faibles d'une tenue (affichées et transmises au LLM styliste)."""
    w = []
    if f["abs_warmth_gap"] > 2: w.append("Plutôt trop chaude pour la météo" if f["warmth_gap"] > 0 else "Plutôt légère pour la météo")
    if f["open_footwear"] and (ctx.rain_prob > .5 or ctx.occasion == "sport"): w.append("Chaussures ouvertes peu adaptées")
    if f["foot_match"] == 0 and ctx.occasion in ("sport", "formal", "wedding", "work"): w.append("Chaussures peu adaptées à l'occasion")
    if f["underdress"] >= 2: w.append("Trop décontractée pour l'occasion")
    return w
