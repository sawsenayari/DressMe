"""Arbitre : combine les juges en un verdict final.
Règle : médiane ordinale des niveaux (équivaut au vote majoritaire à 3 juges, et au
niveau médian si les trois sont en désaccord). Si un juge a échoué, on prend le plus
prudent des juges restants."""
from statistics import median_low

from .schema import CRITERIA, verdict_name


def arbitrate(judgments):
    """judgments : dict nom -> jugement (ou None si le juge a échoué)."""
    valid = {k: j for k, j in judgments.items() if j}
    if not valid:
        raise ValueError("Aucun jugement disponible")
    levels = {k: j["niveau"] for k, j in valid.items()}
    final = min(levels.values()) if len(valid) < 3 else int(median_low(levels.values()))
    crit = {}
    for c in CRITERIA:
        cl = [j["criteres"][c]["niveau"] for j in valid.values()]
        lvl = min(cl) if len(cl) < 3 else int(median_low(cl))
        # raison : celle d'un juge d'accord avec le niveau retenu
        raison = next((j["criteres"][c]["raison"] for j in valid.values()
                       if j["criteres"][c]["niveau"] == lvl), "")
        crit[c] = {"niveau": lvl, "raison": raison}
    raisons = []
    for j in valid.values():
        if j["niveau"] == final:
            for r in j["raisons"]:
                if r not in raisons:
                    raisons.append(r)
    return {
        "source": "arbitre", "verdict": verdict_name(final), "niveau": final,
        "criteres": crit, "raisons": raisons,
        "votes": {k: verdict_name(v) for k, v in levels.items()},
        "desaccord": len(set(levels.values())) > 1,
        "juges_dissidents": [k for k, v in levels.items() if v != final],
    }
