"""Recommandations personnalisées : cosinus au profil + re-ranking selon le persona.

Bonus/malus (fiche obj. 5, section 4) :
- efficacité : couleur neutre +0,10, basique +0,05
- économie   : −0,15 × percentile de prix de l'article (si prix connu)
- image      : article dans le cluster dominant +0,10
Persona « mixte » : on applique les deux meilleurs personas, chacun à moitié.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence

import numpy as np

from . import config
from .clustering import StyleModel, dedupe
from .contracts import ItemCard, Recommendation, StyleProfile
from .features import stack
from .profile import _percentile_of, is_basic, is_neutral


def _persona_weights(profile: StyleProfile) -> dict:
    if profile.persona != "mixte":
        return {profile.persona: 1.0}
    ranked = sorted(((v, k) for k, v in profile.scores.model_dump().items() if v is not None),
                    reverse=True)[:2]
    return {k: 0.5 for _, k in ranked}


def recommend(profile: StyleProfile, wardrobe: Sequence[ItemCard], candidates: Sequence[ItemCard],
              model: StyleModel, k: int = 10, slot: Optional[str] = None,
              assets_dir: Optional[Path] = None) -> List[Recommendation]:
    w_vecs = model.vectorize(wardrobe, assets_dir)
    if not w_vecs:
        return []
    centre = stack(w_vecs, list(w_vecs)).mean(axis=0)
    centre /= max(np.linalg.norm(centre), 1e-12)

    owned = {i.id for i in wardrobe}
    pool = [c for c in candidates if c.id not in owned and (slot is None or c.slot == slot)
            and c.confidence.slot >= config.MIN_SLOT_CONFIDENCE]
    c_vecs = model.vectorize(pool, assets_dir)
    pool = [c for c in pool if c.id in c_vecs]
    if not pool:
        return []
    keep, _ = dedupe(pool, stack(c_vecs, [c.id for c in pool]), model.space)  # pas deux fois la même pièce
    keep = set(keep)
    pool = [c for c in pool if c.id in keep]
    C = stack(c_vecs, [c.id for c in pool])
    cos = C @ centre
    labels = model.assign(C)
    weights = _persona_weights(profile)

    out = []
    for c, s, lab in zip(pool, cos, labels):
        bonus, reasons = 0.0, []
        w = weights.get("efficacite", 0)
        if w and is_neutral(c):
            bonus += w * config.RERANK["efficacite"]["neutral"]; reasons.append("couleur neutre")
        if w and is_basic(c):
            bonus += w * config.RERANK["efficacite"]["basic"]; reasons.append("pièce basique")
        w = weights.get("economie", 0)
        if w and c.price_dt is not None and len(model.catalog_prices) >= 20:
            p = _percentile_of(c.price_dt, model.catalog_prices)
            bonus += w * config.RERANK["economie"]["price_percentile"] * p
            reasons.append(f"prix au percentile {p:.0%}")
        w = weights.get("image", 0)
        if w and int(lab) == profile.dominant_cluster.id:
            bonus += w * config.RERANK["image"]["dominant_cluster"]
            reasons.append("dans votre style dominant")
        out.append(Recommendation(id=c.id, score=round(float(s) + bonus, 4),
                                  cosine=round(float(s), 4), bonus=round(bonus, 4),
                                  reasons=reasons))
    out.sort(key=lambda r: (-r.score, r.id))
    return out[:k]
