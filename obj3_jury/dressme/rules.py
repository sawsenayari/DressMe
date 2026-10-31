"""Juge n°1 : règles explicites, écrites d'après la politique de l'annotateur.
Chaque critère renvoie {"niveau": 0|1|2, "raison": str}. 0=déconseillé, 1=à améliorer, 2=convient."""
from .schema import (CHROMATIC_FAMILIES, CLASHES, colour_family, verdict_name)

# ---- Combinaison des critères (les deux choix laissés ouverts dans le brouillon : à ajuster) ----
DECONSEILLE_SI_ZEROS = 1   # nombre de critères « déconseillé » qui suffisent pour un verdict « déconseillé »
CONVIENT_MAX_UNS = 1       # nombre de critères « à améliorer » tolérés pour un verdict « convient »
# ---- Autres hypothèses modifiables ----
FRAIS = 15                 # en dessous (°C) sans veste : « à améliorer »
ECART_CHALEUR = 1.0        # écart de chaleur toléré (au-delà : « un peu trop chaude/légère »)

CLOTHES = ("haut", "bas", "robe", "veste")
FORMALITY_CATS = ("haut", "bas", "robe", "veste", "chaussures")
OPEN_SHOES = ("sandale", "claquette", "tong", "sandal", "flip")


def _crit(niveau, raison):
    return {"niveau": niveau, "raison": raison}


def _typ(p):
    return str(p.get("type", "")).lower()


def _combine(niveaux_raisons):
    """Niveau le plus bas parmi les règles déclenchées ; (2, ok) si aucune."""
    if not niveaux_raisons:
        return None
    lvl = min(n for n, _ in niveaux_raisons)
    return lvl, " ".join(r for n, r in niveaux_raisons if n == lvl)


# ============================ COULEURS ============================
def judge_couleurs(pieces):
    fams = [colour_family(p.get("couleur")) for p in pieces]
    chrom = sorted({f for f in fams if f in CHROMATIC_FAMILIES})
    printed = [p for p in pieces if p.get("categorie") in CLOTHES
               and (p.get("motif") in ("rayé", "imprimé") or colour_family(p.get("couleur")) == "multi")]
    vivid_printed = [p for p in printed
                     if colour_family(p.get("couleur")) in CHROMATIC_FAMILIES | {"multi"}]
    clashes = [tuple(sorted(c)) for c in CLASHES if c <= set(chrom)]
    if len(chrom) >= 4:
        return _crit(0, f"Trop de couleurs vives différentes ({', '.join(chrom)}).")
    if len(vivid_printed) >= 2:
        return _crit(0, "Deux imprimés aux couleurs vives.")
    if clashes:
        return _crit(1, f"Association de couleurs risquée : {' + '.join(clashes[0])}.")
    if len(chrom) == 3:
        return _crit(1, f"Trois couleurs vives ({', '.join(chrom)}) : à simplifier.")
    if len(printed) >= 2:
        return _crit(1, "Plusieurs pièces à motifs : en garder une seule.")
    if not chrom:
        return _crit(2, "Palette neutre, facile à porter.")
    return _crit(2, f"Palette harmonieuse ({', '.join(chrom)} avec des neutres).")


# ============================ FORMALITÉ ============================
def judge_formalite(pieces, context):
    occ = (context or {}).get("occasion")
    cl = [p for p in pieces if p.get("categorie") in FORMALITY_CATS]
    shoes = [p for p in pieces if p.get("categorie") == "chaussures"]
    vals = [p["formalite"] for p in cl if "formalite" in p]
    hit = []   # (niveau, raison)

    if occ == "sport":
        if any(p.get("categorie") == "robe" for p in pieces):
            hit.append((0, "Robe pour une activité sportive."))
        if shoes and not any("basket" in _typ(s) or "sport" in _typ(s) for s in shoes):
            if all("sandale" in _typ(s) for s in shoes):
                hit.append((1, "Sandales peu adaptées au sport."))
            else:
                hit.append((0, "Chaussures non sportives pour une activité sportive."))
    elif occ == "cérémonie":
        bas_niveau = [p for p in cl if p.get("formalite", 5) <= 1]
        if bas_niveau:
            hit.append((0, f"Pièce trop décontractée pour une cérémonie ({_typ(bas_niveau[0])})."))
    elif occ == "travail":
        if any(("short" in _typ(p) or "débardeur" in _typ(p)) for p in cl):
            hit.append((0, "Short ou débardeur au travail."))
        elif any(("pantalon décontracté" in _typ(p) or "basket" in _typ(p)) for p in cl):
            hit.append((1, "Pantalon décontracté ou baskets au travail."))
    elif occ == "soirée":
        if vals and max(vals) < 4:
            hit.append((1, "Aucune pièce habillée pour une soirée."))
    # « décontracté » : aucune sanction (robe + chaussures habillées acceptées)

    if vals and max(vals) - min(vals) >= 3:
        hit.append((1, f"Une pièce beaucoup plus habillée que le reste (formalité {min(vals)} à {max(vals)})."))
    res = _combine(hit)
    return _crit(*res) if res else _crit(2, "Formalité adaptée.")


# ============================ MÉTÉO ============================
def required_warmth(t):
    for limit, w in [(5, 4.5), (10, 4.0), (15, 3.2), (20, 2.5), (25, 1.8)]:
        if t <= limit:
            return w
    return 1.2


def judge_meteo(pieces, context):
    ctx = context or {}
    t = ctx.get("temperature")
    if t is None:
        return _crit(2, "Météo non fournie : critère non évalué.")
    pluie = bool(ctx.get("pluie"))
    vestes = [p for p in pieces if p.get("categorie") == "veste"]
    chaude = any(p.get("chaleur", 1) >= 4 for p in vestes)
    sandales = any(any(k in _typ(p) for k in OPEN_SHOES) for p in pieces if p.get("categorie") == "chaussures")
    epais = [p for p in pieces if p.get("categorie") in ("haut", "veste") and p.get("chaleur", 1) >= 4]

    # --- déconseillé ---
    if t < 5 and not chaude:
        return _crit(0, f"Moins de 5 °C sans manteau ni veste chaude ({t:g} °C).")
    if t > 28 and epais:
        return _crit(0, f"Manteau, doudoune ou pull épais par {t:g} °C.")
    if pluie and sandales and not vestes:
        return _crit(0, "Pluie avec sandales et sans veste.")

    # --- à améliorer ---
    why = []
    if 5 <= t <= 10 and vestes and not chaude:
        why.append(f"Seulement une veste légère par {t:g} °C.")
    if pluie and sandales:
        why.append("Sandales sous la pluie.")
    if pluie and not vestes:
        why.append("Pluie sans veste.")
    if not vestes and t < FRAIS:
        why.append(f"Pas de veste par {t:g} °C.")
    base = [p["chaleur"] for p in pieces if p.get("categorie") in ("haut", "bas", "robe") and "chaleur" in p]
    if base:
        eff = sum(base) / len(base) + sum(0.4 * (p.get("chaleur", 1) - 1) for p in vestes)
        diff = eff - required_warmth(t)
        if abs(diff) > ECART_CHALEUR:
            why.append(f"Tenue un peu {'trop chaude' if diff > 0 else 'trop légère'} pour {t:g} °C.")
    if why:
        return _crit(1, " ".join(why))
    return _crit(2, f"Chaleur adaptée à {t:g} °C.")


# ============================ COHÉRENCE ============================
def judge_coherence(pieces):
    cats = [p.get("categorie") for p in pieces]
    n = lambda c: cats.count(c)
    haut_ok, bas_ok = n("haut") + n("robe") > 0, n("bas") + n("robe") > 0
    problems = []
    if n("chaussures") == 0:
        problems.append((0, "Pas de chaussures."))
    if not haut_ok and not bas_ok:
        problems.append((0, "Ni haut ni bas."))
    elif not haut_ok:
        problems.append((1, "Il manque un haut."))
    elif not bas_ok:
        problems.append((1, "Il manque un bas."))
    if n("robe") and n("bas"):
        problems.append((0, "Une robe et un bas en même temps."))
    if n("bas") > 1:
        problems.append((0, "Deux bas dans la même tenue."))
    if n("robe") > 1:
        problems.append((0, "Deux robes dans la même tenue."))
    if n("chaussures") > 1:
        problems.append((0, "Deux paires de chaussures."))
    if n("haut") > 1:
        problems.append((1, "Plusieurs hauts : vérifier qu'il s'agit bien d'une superposition."))
    if n("veste") > 1:
        problems.append((1, "Deux vestes superposées."))
    if not problems:
        return _crit(2, "Tenue complète et cohérente.")
    res = _combine(problems)
    return _crit(*res)


# ============================ VERDICT GLOBAL ============================
def combine_levels(niveaux):
    n0 = sum(n == 0 for n in niveaux)
    n1 = sum(n == 1 for n in niveaux)
    if n0 >= DECONSEILLE_SI_ZEROS:
        return 0
    if n0 >= 1 or n1 > CONVIENT_MAX_UNS:
        return 1
    return 2


def judge_rules(pieces, context=None):
    crit = {
        "couleurs": judge_couleurs(pieces),
        "formalite": judge_formalite(pieces, context),
        "meteo": judge_meteo(pieces, context),
        "coherence": judge_coherence(pieces),
    }
    level = combine_levels([c["niveau"] for c in crit.values()])
    bad = [f"{k} : {c['raison']}" for k, c in crit.items() if c["niveau"] < 2]
    return {"source": "regles", "verdict": verdict_name(level), "niveau": level,
            "criteres": crit,
            "raisons": bad or ["Tous les critères sont satisfaisants."]}
