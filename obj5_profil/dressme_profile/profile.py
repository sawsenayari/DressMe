"""Construction du profil de style (contrat StyleProfile v1).

Tout est calculé par du code déterministe : chaque chiffre du profil est
vérifiable et identique d'une exécution à l'autre.
"""
from __future__ import annotations

import math
from collections import Counter
from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np

from . import config
from .clustering import StyleModel, dedupe
from .contracts import (DominantCluster, ItemCard, PaletteEntry, PersonaScores,
                        StyleProfile)
from .features import stack


def _percentile_of(value: float, reference: Sequence[float]) -> float:
    ref = np.sort(np.asarray(reference, dtype=float))
    return float(np.searchsorted(ref, value, side="right") / len(ref))


def is_neutral(it: ItemCard) -> bool:
    return bool(it.colour) and all(c.lower() in config.NEUTRAL_COLOURS for c in it.colour)


def is_basic(it: ItemCard) -> bool:
    return it.type in config.BASIC_TYPES and (it.pattern or "plain") == "plain" and not it.traditional


def is_statement(it: ItemCard) -> bool:
    return any(c.lower() in config.STATEMENT_COLOURS for c in it.colour)


def decide_persona(scores: PersonaScores, margin: float = config.MIXED_MARGIN) -> str:
    avail = sorted(((v, k) for k, v in scores.model_dump().items() if v is not None), reverse=True)
    if len(avail) >= 2 and avail[0][0] - avail[1][0] < margin:
        return "mixte"
    return avail[0][1]


def build_profile(items: Sequence[ItemCard], model: StyleModel, user_id: Optional[str] = None,
                  assets_dir: Optional[Path] = None) -> StyleProfile:
    warnings: List[str] = []
    n_items = len(items)
    if n_items == 0:
        raise ValueError("Garde-robe vide : impossible de calculer un profil.")

    # 1. Qualité : fiches trop douteuses
    low = [i.id for i in items if i.confidence.slot < config.MIN_SLOT_CONFIDENCE]
    if low:
        warnings.append(f"{len(low)} fiche(s) ignorée(s), confidence.slot < "
                        f"{config.MIN_SLOT_CONFIDENCE} : {', '.join(low[:10])}")
    usable = [i for i in items if i.confidence.slot >= config.MIN_SLOT_CONFIDENCE]

    # 2. Vecteurs dans l'espace du modèle
    vecs = model.vectorize(usable, assets_dir)
    missing = [i.id for i in usable if i.id not in vecs]
    if missing:
        warnings.append(f"{len(missing)} fiche(s) sans vecteur {model.space} ignorée(s) "
                        f"(fichier .npy absent ?) : {', '.join(missing[:10])}")
    ids = [i.id for i in usable if i.id in vecs]
    if not ids:
        raise ValueError("Aucune fiche exploitable après filtrage.")

    # 3. Doublons quasi exacts (ils gonfleraient palette et diversité)
    by_id = {i.id: i for i in usable}
    ids, dups = dedupe([by_id[i] for i in ids], stack(vecs, ids), model.space)
    if dups:
        warnings.append(f"{len(dups)} doublon(s) quasi exact(s) ignoré(s) : {', '.join(dups[:10])}")
    kept = [by_id[i] for i in ids]
    X = stack(vecs, ids)
    n = len(kept)

    # 4. Clusters, dominant et diversité (entropie normalisée)
    labels = model.assign(X)
    counts = Counter(int(l) for l in labels)
    dom_id, dom_n = counts.most_common(1)[0]
    k = model.kmeans.n_clusters
    probs = np.array([c / n for c in counts.values()])
    entropy = float(-(probs * np.log(probs)).sum())
    diversity = entropy / math.log(min(k, n)) if min(k, n) > 1 else 0.0

    # 5. Palette pondérée par la confiance couleur
    col_w: Counter = Counter()
    for it in kept:
        w = max(it.confidence.colour, 0.1) / max(len(it.colour), 1)
        for c in it.colour:
            col_w[c.lower()] += w
    total = sum(col_w.values()) or 1.0
    palette = [PaletteEntry(colour=c, weight=round(w / total, 3)) for c, w in col_w.most_common(5)]

    # 6. Formalité et prix
    formality_pref = float(np.mean([it.formality for it in kept]))
    prices = [it.price_dt for it in kept if it.price_dt is not None]
    price_percentile = None
    if len(prices) / n < config.MIN_PRICE_COVERAGE:
        warnings.append(f"Prix connus pour {len(prices)}/{n} pièces : score « economie » et "
                        "price_percentile non évaluables (null).")
    elif len(model.catalog_prices) < 20:
        warnings.append("Catalogue de référence sans prix suffisants : price_percentile null.")
    else:
        price_percentile = round(_percentile_of(float(np.median(prices)), model.catalog_prices), 3)

    # 7. Scores de persona (trois formules simples, la plus forte gagne)
    neutral = sum(map(is_neutral, kept)) / n
    basic = sum(map(is_basic, kept)) / n
    statement = sum(map(is_statement, kept)) / n
    scores = PersonaScores(
        efficacite=round(0.5 * neutral + 0.3 * basic + 0.2 * (1 - diversity), 3),
        economie=None if price_percentile is None else round(1 - price_percentile, 3),
        image=round(0.4 * dom_n / n + 0.35 * formality_pref / 3 + 0.25 * statement, 3),
    )
    persona = decide_persona(scores)

    # 8. Avertissements de domaine (cf. section « Risques » de l'orchestration)
    trad = sum(it.traditional for it in kept) / n
    if trad > 0.3:
        warnings.append(f"{trad:.0%} de pièces traditionnelles : hors domaine Polyvore, "
                        "à interpréter avec prudence.")
    genders = {it.gender for it in kept} - {"Unisex"}
    if len(genders) > 1:
        warnings.append("Garde-robe mêlant articles homme et femme : vérifier qu'il s'agit "
                        "bien d'un seul utilisateur.")
    if n < 10:
        warnings.append(f"Seulement {n} pièces exploitables : profil peu stable.")
    if model.space != "fashionclip":
        warnings.append("Espace 'attributes' (repli) : recalculer avec FashionCLIP dès que "
                        "les embeddings communs sont disponibles.")

    return StyleProfile(
        user_id=user_id, persona=persona, scores=scores, palette=palette,
        formality_pref=round(formality_pref, 3), price_percentile=price_percentile,
        dominant_cluster=DominantCluster(id=dom_id, name=model.cluster_names[dom_id],
                                         share=round(dom_n / n, 3)),
        diversity=round(min(max(diversity, 0.0), 1.0), 3),
        slot_counts=dict(Counter(it.slot for it in kept)),
        n_items=n_items, n_items_used=n, embedding_space=model.space,
        model=model.name, warnings=warnings,
    )
