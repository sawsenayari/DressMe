"""Réparateur : propose la correction minimale (remplacer / ajouter / retirer UNE pièce)
en cherchant dans la garde-robe. La recherche utilise le juge à règles (rapide, gratuit) ;
la meilleure proposition est ensuite re-vérifiée par le jury complet (voir jury.py)."""
from collections import defaultdict

from .rules import judge_rules
from .schema import piece_label


def _score(pieces, context):
    j = judge_rules(pieces, context)
    return j["niveau"], sum(c["niveau"] for c in j["criteres"].values()), j


def _distance(old, new):
    """Écart entre deux pièces : plus c'est petit, plus la correction est discrète."""
    return (abs(old.get("formalite", 3) - new.get("formalite", 3))
            + abs(old.get("chaleur", 3) - new.get("chaleur", 3))
            + (0 if old.get("couleur") == new.get("couleur") else 0.5))


def _missing_categories(pieces):
    cats = [p["categorie"] for p in pieces]
    miss = []
    if "haut" not in cats and "robe" not in cats:
        miss.append("haut")
    if "bas" not in cats and "robe" not in cats:
        miss.append("bas")
    if "chaussures" not in cats:
        miss.append("chaussures")
    return miss


def propose_repairs(pieces, context, wardrobe, top=3):
    """wardrobe : liste de pièces décrites. Renvoie jusqu'à `top` corrections, la meilleure d'abord."""
    base_level, base_sum, _ = _score(pieces, context)
    if base_level == 2:
        return []
    by_cat = defaultdict(list)
    for w in wardrobe:
        by_cat[w["categorie"]].append(w)
    ids = {p["id"] for p in pieces}
    cands = []   # (clé de tri, correction)

    def consider(new_outfit, action, removed, added, dist):
        lvl, s, j = _score(new_outfit, context)
        if (lvl, s) > (base_level, base_sum):
            cands.append(((-lvl, -s, dist), {
                "action": action, "piece_retiree": removed, "piece_ajoutee": added,
                "nouvelle_tenue": new_outfit, "verdict_regles": j["verdict"],
                "criteres_regles": {k: c["niveau"] for k, c in j["criteres"].items()}}))

    for i, p in enumerate(pieces):
        rest = pieces[:i] + pieces[i + 1:]
        consider(rest, "retirer", p, None, 1.0)
        for c in by_cat.get(p["categorie"], []):
            if c["id"] not in ids:
                consider(rest + [c], "remplacer", p, c, _distance(p, c))
    for cat in _missing_categories(pieces):
        for c in by_cat.get(cat, []):
            if c["id"] not in ids:
                consider(pieces + [c], "ajouter", None, c, 1.0)

    cands.sort(key=lambda x: x[0])
    out, seen = [], set()
    for _, rep in cands:
        key = (rep["action"], (rep["piece_retiree"] or {}).get("id"), (rep["piece_ajoutee"] or {}).get("id"))
        if key not in seen:
            seen.add(key)
            rep["explication"] = explain(rep)
            out.append(rep)
        if len(out) == top:
            break
    return out


def explain(rep):
    a, r, n = rep["action"], rep["piece_retiree"], rep["piece_ajoutee"]
    v = rep["verdict_regles"]
    tail = f"→ {v}" + ("" if v == "convient" else " (amélioration partielle : une seule correction ne suffit pas)")
    if a == "remplacer":
        return f"Remplace {piece_label(r)} par {piece_label(n)} {tail}."
    if a == "ajouter":
        return f"Ajoute {piece_label(n)} {tail}."
    return f"Retire {piece_label(r)} {tail}."
