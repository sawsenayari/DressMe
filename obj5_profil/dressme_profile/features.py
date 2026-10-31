"""Représentation vectorielle des fiches article.

Deux espaces possibles :
- "fashionclip" : le vecteur FashionCLIP 512-d de la fiche (champ `embedding`,
  fichier .npy). C'est l'espace commun décidé dans la fiche d'orchestration.
- "attributes" : repli déterministe construit à partir des attributs de la fiche
  (emplacement, type, couleur, usage, formalité…), utilisé tant que les .npy
  FashionCLIP ne sont pas disponibles. Il gère aussi les pièces traditionnelles,
  que Polyvore/FashionCLIP ne couvrent pas bien.

Le modèle de clustering est entraîné dans un seul espace ; on ne mélange jamais
les deux (comparer des vecteurs de deux espaces n'a pas de sens).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

from . import config
from .contracts import ItemCard

SEASONS = ["all", "summer", "fall", "winter", "spring"]
GENDERS = ["Men", "Women", "Unisex"]

# Poids des blocs d'attributs (somme des carrés ≈ importance relative)
BLOCK_WEIGHTS = {
    "slot": 1.0, "type": 1.0, "colour": 1.0, "usage": 0.8,
    "num": 0.8, "traditional": 0.8, "gender": 0.4, "season": 0.3,
}


class AttributeVocab:
    """Vocabulaire figé au moment de l'entraînement (sérialisé avec le modèle)."""

    def __init__(self, types: Sequence[str], colours: Sequence[str]):
        self.types = sorted(set(types) | {"Other"})
        self.colours = sorted(set(colours))

    @classmethod
    def from_items(cls, items: Sequence[ItemCard]) -> "AttributeVocab":
        return cls([i.type for i in items], [c.lower() for i in items for c in i.colour])

    @property
    def dim(self) -> int:
        return (len(config.SLOTS) + len(self.types) + len(self.colours) + len(config.USAGES)
                + 2 + 1 + len(GENDERS) + len(SEASONS))

    def encode(self, it: ItemCard) -> np.ndarray:
        def one_hot(value, vocab):
            v = np.zeros(len(vocab))
            if value in vocab:
                v[vocab.index(value)] = 1.0
            return v

        t = it.type if it.type in self.types else "Other"
        colours = np.zeros(len(self.colours))
        for c in it.colour:
            c = c.lower()
            if c in self.colours:
                colours[self.colours.index(c)] = 1.0
        if colours.sum() > 0:
            colours /= np.linalg.norm(colours)
        blocks = {
            "slot": one_hot(it.slot, config.SLOTS),
            "type": one_hot(t, self.types),
            "colour": colours,
            "usage": one_hot(it.usage, config.USAGES),
            "num": np.array([it.formality / 3.0, it.warmth / 4.0]),
            "traditional": np.array([1.0 if it.traditional else 0.0]),
            "gender": one_hot(it.gender, GENDERS),
            "season": one_hot(it.season or "all", SEASONS),
        }
        vec = np.concatenate([blocks[k] * BLOCK_WEIGHTS[k] for k in blocks])
        n = np.linalg.norm(vec)
        return vec / n if n > 0 else vec


def resolve_embedding_path(it: ItemCard, assets_dir: Optional[Path] = None) -> Optional[Path]:
    if not it.embedding:
        return None
    p = Path(it.embedding)
    if not p.is_absolute():
        p = (assets_dir or config.ASSETS_DIR) / p
    return p if p.exists() else None


def load_fashionclip(it: ItemCard, assets_dir: Optional[Path] = None) -> Optional[np.ndarray]:
    p = resolve_embedding_path(it, assets_dir)
    if p is None:
        return None
    v = np.load(p).astype(np.float64).ravel()
    n = np.linalg.norm(v)
    return v / n if n > 0 else None


def fashionclip_coverage(items: Sequence[ItemCard], assets_dir: Optional[Path] = None) -> float:
    if not items:
        return 0.0
    return sum(resolve_embedding_path(i, assets_dir) is not None for i in items) / len(items)


def vectorize(items: Sequence[ItemCard], space: str, vocab: Optional[AttributeVocab] = None,
              assets_dir: Optional[Path] = None) -> Dict[str, np.ndarray]:
    """Renvoie {id: vecteur normalisé}. Les fiches sans vecteur sont absentes."""
    out: Dict[str, np.ndarray] = {}
    for it in items:
        if space == "fashionclip":
            v = load_fashionclip(it, assets_dir)
        else:
            assert vocab is not None, "vocabulaire requis pour l'espace 'attributes'"
            v = vocab.encode(it)
        if v is not None:
            out[it.id] = v
    return out


def stack(vectors: Dict[str, np.ndarray], ids: List[str]) -> np.ndarray:
    return np.vstack([vectors[i] for i in ids]) if ids else np.zeros((0, 1))
