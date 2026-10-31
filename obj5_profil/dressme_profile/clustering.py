"""Taxonomie de styles : PCA + K-Means, k choisi par silhouette (fiche obj. 5).

Le modèle est entraîné une fois sur le catalogue commun puis sauvegardé
(models/style_model.joblib). Le profil d'un utilisateur ne fait qu'assigner ses
pièces aux clusters existants : c'est rapide (pas de GPU) et déterministe.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import sys

import joblib
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score

from . import config
from .contracts import ItemCard
from .features import AttributeVocab, stack, vectorize


@dataclass
class StyleModel:
    space: str                                  # "fashionclip" ou "attributes"
    vocab: Optional[AttributeVocab]
    pca: PCA
    kmeans: KMeans
    cluster_names: Dict[int, str]
    k_table: List[dict]                         # silhouette, DB, CH pour chaque k testé
    catalog_prices: List[float] = field(default_factory=list)
    n_train: int = 0
    version: str = "obj5-style-model-v1"

    @property
    def name(self) -> str:
        return f"{self.version}:{self.space}:k{self.kmeans.n_clusters}"

    # --- inférence -----------------------------------------------------------
    def vectorize(self, items: Sequence[ItemCard], assets_dir: Optional[Path] = None):
        return vectorize(items, self.space, self.vocab, assets_dir)

    def assign(self, X: np.ndarray) -> np.ndarray:
        return self.kmeans.predict(self.pca.transform(X))

    def centroid_vectors(self) -> np.ndarray:
        """Centres des clusters ramenés dans l'espace d'origine, normalisés."""
        C = self.pca.inverse_transform(self.kmeans.cluster_centers_)
        return C / np.clip(np.linalg.norm(C, axis=1, keepdims=True), 1e-12, None)

    # --- persistance ---------------------------------------------------------
    def save(self, path: Path = config.MODEL_PATH) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        return path

    @staticmethod
    def load(path: Path = config.MODEL_PATH) -> "StyleModel":
        return joblib.load(path)


def _name_cluster(members: Sequence[ItemCard]) -> str:
    """Nom lisible tiré des attributs majoritaires (ex. « onepiece · Ethnic · beige »)."""
    slot = Counter(m.slot for m in members).most_common(1)[0][0]
    usage = Counter(m.usage for m in members).most_common(1)[0][0]
    colours = Counter(c for m in members for c in m.colour).most_common(2)
    trad = sum(m.traditional for m in members) / len(members)
    parts = [slot, usage, "/".join(c for c, _ in colours)]
    if trad >= 0.6:
        parts.append("traditionnel")
    return " · ".join(p for p in parts if p)


def card_fingerprint(it: ItemCard) -> tuple:
    """Empreinte d'une fiche : mêmes attributs ET mêmes confiances au 1e-9 près.
    Deux pièces différentes peuvent avoir les mêmes attributs, mais pas les mêmes
    confiances flottantes : une empreinte identique signale la même photo traitée deux fois."""
    c = it.confidence
    return (it.slot, it.type, tuple(it.colour), it.usage, it.gender, it.traditional,
            round(c.slot, 9), round(c.colour, 9), round(c.type, 9))


def dedupe(items: Sequence[ItemCard], X: np.ndarray, space: str,
           threshold: float = config.DUPLICATE_COSINE):
    """Retire les doublons. Renvoie (ids gardés, ids doublons).

    - fashionclip : cosinus ≥ seuil entre images (vraie quasi-identité visuelle) ;
    - attributes : empreinte identique de la fiche (sinon, des pièces distinctes
      mais de mêmes attributs seraient fusionnées à tort).
    """
    keep, dups = [], []
    if space == "attributes":
        seen = set()
        for it in items:
            fp = card_fingerprint(it)
            (dups if fp in seen else keep).append(it.id)
            seen.add(fp)
        return keep, dups
    kept_vecs: List[np.ndarray] = []
    for it, v in zip(items, X):
        if kept_vecs and float(np.max(np.vstack(kept_vecs) @ v)) >= threshold:
            dups.append(it.id)
        else:
            keep.append(it.id)
            kept_vecs.append(v)
    return keep, dups


def train(catalog: Sequence[ItemCard], space: str = "attributes",
          assets_dir: Optional[Path] = None, seed: int = config.SEED,
          verbose: bool = True) -> StyleModel:
    vocab = AttributeVocab.from_items(catalog) if space == "attributes" else None
    vecs = vectorize(catalog, space, vocab, assets_dir)
    ids = [i.id for i in catalog if i.id in vecs]
    if len(ids) < config.K_MIN * 3:
        raise ValueError(f"Trop peu de fiches vectorisées ({len(ids)}) pour l'espace '{space}'.")
    by_id = {i.id: i for i in catalog}
    ids, dups = dedupe([by_id[i] for i in ids], stack(vecs, ids), space)
    X = stack(vecs, ids)

    n_comp = min(config.PCA_DIM, X.shape[1], X.shape[0] - 1)
    pca = PCA(n_components=n_comp, random_state=seed).fit(X)
    Z = pca.transform(X)

    table, best = [], None
    for k in range(config.K_MIN, min(config.K_MAX, len(ids) - 1) + 1):
        km = KMeans(n_clusters=k, n_init=config.N_INIT, random_state=seed).fit(Z)
        row = {"k": k,
               "silhouette": float(silhouette_score(Z, km.labels_, random_state=seed)),
               "davies_bouldin": float(davies_bouldin_score(Z, km.labels_)),
               "calinski_harabasz": float(calinski_harabasz_score(Z, km.labels_))}
        table.append(row)
        if best is None or row["silhouette"] > best[0]["silhouette"]:
            best = (row, km)
    row, km = best

    names = {}
    for c in range(km.n_clusters):
        members = [by_id[i] for i, lab in zip(ids, km.labels_) if lab == c]
        names[c] = _name_cluster(members)

    prices = [float(i.price_dt) for i in catalog if i.price_dt is not None]
    model = StyleModel(space=space, vocab=vocab, pca=pca, kmeans=km, cluster_names=names,
                       k_table=table, catalog_prices=prices, n_train=len(ids))
    if verbose:
        print(f"[obj5] espace={space} fiches={len(ids)} (doublons retirés : {len(dups)}) "
              f"k={row['k']} silhouette={row['silhouette']:.3f}", file=sys.stderr)
        for c, n in names.items():
            print(f"   cluster {c:2d} ({int(np.sum(km.labels_ == c)):3d}) : {n}", file=sys.stderr)
    return model
