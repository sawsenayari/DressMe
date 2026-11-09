"""Contrat de sortie de la styliste IA : forme brute attendue du LLM, puis forme renvoyée au front."""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class RawAdvice(BaseModel):
    """Ce que le LLM doit renvoyer (vérifié avant tout usage ; champs inconnus ignorés)."""
    observation: Optional[str] = None
    conseil: str = Field(min_length=1)
    tenue: List[str] = Field(default_factory=list)
    a_eviter: Optional[str] = None

    @field_validator("tenue", mode="before")
    @classmethod
    def _liste(cls, v):
        if v is None:
            return []
        return [x for x in (v if isinstance(v, list) else [v]) if isinstance(x, str)]

    @field_validator("a_eviter", mode="before")
    @classmethod
    def _id_ou_rien(cls, v):
        return v if isinstance(v, str) and v.strip() else None


class Advice(BaseModel):
    """Conseil validé, ancré sur les faits (forme publique de l'API)."""
    observation: Optional[str] = Field(default=None, max_length=120)
    conseil: str
    tenue: List[str] = Field(default_factory=list, max_length=3)
    aEviter: Optional[str] = None
