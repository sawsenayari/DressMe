"""Faux module (mock) : renvoie un profil valide et constant, sans modèle ni données.

Exigé par la fiche d'orchestration (« chaque module fournit un mock qui renvoie
des réponses valides, pour que personne n'attende personne »).
Activation côté API : variable d'environnement DRESSME_PROFILE_MOCK=1.
"""
from __future__ import annotations

from typing import Optional

from .contracts import (DominantCluster, PaletteEntry, PersonaScores, Recommendation,
                        RecommendResponse, StyleProfile)


def mock_profile(user_id: Optional[str] = None) -> StyleProfile:
    return StyleProfile(
        user_id=user_id, persona="efficacite",
        scores=PersonaScores(efficacite=0.62, economie=0.41, image=0.38),
        palette=[PaletteEntry(colour="black", weight=0.35), PaletteEntry(colour="white", weight=0.25),
                 PaletteEntry(colour="beige", weight=0.2), PaletteEntry(colour="blue", weight=0.2)],
        formality_pref=1.4, price_percentile=0.59,
        dominant_cluster=DominantCluster(id=0, name="top · Casual · white/black", share=0.4),
        diversity=0.55, slot_counts={"top": 8, "bottom": 5, "footwear": 3, "outer": 2},
        n_items=18, n_items_used=18, embedding_space="fashionclip", model="mock",
        warnings=["MOCK : profil fictif, ne pas utiliser pour une évaluation."],
    )


def mock_recommend(user_id: Optional[str] = None) -> RecommendResponse:
    return RecommendResponse(profile=mock_profile(user_id), items=[
        Recommendation(id="it_0042", score=0.91, cosine=0.81, bonus=0.10,
                       reasons=["couleur neutre"]),
    ])
