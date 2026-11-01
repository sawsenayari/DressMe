"""ItemCard v1 : le contrat commun (produit par l'objectif 1 + crop, lu par tous)."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator

Slot = Literal["top", "bottom", "onepiece", "outer", "footwear", "bag", "accessory"]
Usage = Literal["Casual", "Smart Casual", "Formal", "Sports", "Ethnic", "Party"]
Source = Literal["obj1.llm", "obj1.knn", "user_corrected"]


class Confidence(BaseModel):
    slot: float = Field(ge=0, le=1)
    colour: float = Field(ge=0, le=1)
    type: float = Field(ge=0, le=1)


class ItemCard(BaseModel):
    id: str
    name: str
    slot: Slot
    type: str                                   # type fin (liste de l'objectif 6)
    colour: list[str] = Field(min_length=1, max_length=2)   # minuscules, anglais, 2 maximum
    usage: Usage
    warmth: int = Field(ge=0, le=4)
    formality: int = Field(ge=0, le=3)
    waterproof: bool = False
    open_toe: bool = False
    gender: str = "Unisex"
    image: str
    image_crop: str                             # vêtement seul, fond blanc, 512 px
    embedding: str                              # chemin du .npy : FashionCLIP 512-d, norme 1, calculé sur image_crop
    season: str = "all"
    pattern: Optional[str] = "plain"
    confidence: Confidence
    source: Source
    price_dt: Optional[float] = None
    traditional: bool = False

    @field_validator("colour")
    @classmethod
    def _lower(cls, v): return [c.strip().lower() for c in v]


class RecognitionResult(BaseModel):
    """Ce que renvoie le service de reconnaissance (la fiche + ce qu'il faut savoir pour décider quoi en faire)."""
    status: Literal["ok", "needs_review", "unsupported"]
    card: Optional[ItemCard] = None
    category: str = "unknown"                   # catégorie fine de l'objectif 1 (17 classes)
    reasons: list[str] = []
    trace: list[str] = []
    debug: dict = {}


def export_json_schema(path: str | Path) -> dict:
    schema = ItemCard.model_json_schema()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(schema, indent=2), encoding="utf-8")
    return schema
