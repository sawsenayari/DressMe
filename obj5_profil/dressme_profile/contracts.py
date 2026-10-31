"""Contrats d'interface (fiche d'orchestration, section « Contrats d'interface »).

- ItemCard v1 : la fiche article commune (lue ici, produite par crop + objectif 1).
- StyleProfile v1 : le profil de style produit par l'objectif 5, lu par les
  objectifs 6, 3 et 4.
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Slot = Literal["top", "bottom", "onepiece", "outer", "footwear", "bag", "accessory"]
Persona = Literal["efficacite", "economie", "image", "mixte"]


class Confidence(BaseModel):
    model_config = ConfigDict(extra="allow")
    slot: float = Field(1.0, ge=0, le=1)
    colour: float = Field(1.0, ge=0, le=1)
    type: float = Field(1.0, ge=0, le=1)


class ItemCard(BaseModel):
    """Fiche article v1. Les champs inconnus sont conservés (extra=allow)."""
    model_config = ConfigDict(extra="allow")

    id: str
    name: str = ""
    slot: Slot
    type: str = "Other"
    colour: List[str] = Field(default_factory=list, max_length=2)
    usage: str = "Casual"
    warmth: int = Field(1, ge=0, le=4)
    formality: int = Field(1, ge=0, le=3)
    waterproof: bool = False
    open_toe: bool = False
    gender: str = "Unisex"
    image: Optional[str] = None
    image_crop: Optional[str] = None
    embedding: Optional[str] = None
    season: Optional[str] = "all"
    pattern: Optional[str] = "plain"
    confidence: Confidence = Field(default_factory=Confidence)
    source: Optional[str] = None
    price_dt: Optional[float] = Field(None, ge=0)
    traditional: bool = False


class PaletteEntry(BaseModel):
    colour: str
    weight: float = Field(..., ge=0, le=1)


class PersonaScores(BaseModel):
    efficacite: float = Field(..., ge=0, le=1)
    # None quand les prix ne sont pas assez connus : l'économie n'est pas évaluable
    economie: Optional[float] = Field(None, ge=0, le=1)
    image: float = Field(..., ge=0, le=1)


class DominantCluster(BaseModel):
    id: int
    name: str
    share: float = Field(..., ge=0, le=1)


class StyleProfile(BaseModel):
    """Profil de style v1 (objectif 5)."""
    version: Literal["obj5-profile-v1"] = "obj5-profile-v1"
    user_id: Optional[str] = None
    persona: Persona
    scores: PersonaScores
    palette: List[PaletteEntry]
    formality_pref: float = Field(..., ge=0, le=3)
    price_percentile: Optional[float] = Field(None, ge=0, le=1)
    dominant_cluster: DominantCluster
    diversity: float = Field(..., ge=0, le=1)
    # Champs de traçabilité (en plus du contrat, sans effet pour les lecteurs)
    slot_counts: Dict[str, int] = Field(default_factory=dict)
    n_items: int
    n_items_used: int
    embedding_space: Literal["fashionclip", "attributes"]
    model: str
    warnings: List[str] = Field(default_factory=list)


class ProfileRequest(BaseModel):
    """Entrée de POST /profile : soit des fiches complètes, soit des identifiants."""
    user_id: Optional[str] = None
    items: Optional[List[ItemCard]] = None
    item_ids: Optional[List[str]] = None


class RecommendRequest(BaseModel):
    user_id: Optional[str] = None
    wardrobe_ids: List[str]
    candidate_ids: Optional[List[str]] = None   # défaut : tout le catalogue hors garde-robe
    k: int = Field(10, ge=1, le=100)
    slot: Optional[Slot] = None


class Recommendation(BaseModel):
    id: str
    score: float
    cosine: float
    bonus: float
    reasons: List[str]


class RecommendResponse(BaseModel):
    profile: StyleProfile
    items: List[Recommendation]
