from __future__ import annotations
import numpy as np
import pandas as pd


def _s(v): return v if isinstance(v, str) else None


class Retriever:
    """kNN / RAG sur l'index FashionCLIP. Les vecteurs de l'index et de la requête doivent venir du MÊME encodeur."""
    def __init__(self, E: np.ndarray, meta: pd.DataFrame, T: float = 0.05):
        self.E, self.meta, self.T = E.astype("float32"), meta.reset_index(drop=True), T
        assert len(self.E) == len(self.meta), "index et métadonnées incohérents"

    def add(self, meta: pd.DataFrame, E: np.ndarray) -> "Retriever":
        """Nouveau Retriever = index actuel + références supplémentaires (ex. photos tunisiennes). L'encodeur doit être le même."""
        assert E.shape[1] == self.E.shape[1], "dimension d'embedding différente"
        cols = list(self.meta.columns); m = meta.copy()
        for c in cols:
            if c not in m: m[c] = None
        return Retriever(np.vstack([self.E, E.astype("float32")]), pd.concat([self.meta, m[cols]], ignore_index=True), self.T)

    def search(self, q: np.ndarray, k: int) -> list[dict]:
        s = self.E @ q; k = min(k, len(s) - 1); idx = np.argpartition(-s, k)[:k]; idx = idx[np.argsort(-s[idx])]
        w = np.exp((s[idx] - s[idx].max()) / self.T); w /= w.sum(); m = self.meta
        has = lambda c: c in m.columns
        return [dict(id=int(m.id[j]), category=m.category[j], color=_s(m.color[j]), gender=_s(m.gender[j]), season=_s(m.season[j]),
                     occasion=_s(m.occasion[j]), name=str(m.name[j]), article_type=_s(m.article_type[j]) if has("article_type") else None,
                     subtype=_s(m.subtype[j]) if has("subtype") else None,
                     image_path=str(m.image_path[j]) if has("image_path") else "", sim=float(s[j]), w=float(wi)) for j, wi in zip(idx, w)]


def knn_vote(nb):
    d = {}
    for n in nb: d[n["category"]] = d.get(n["category"], 0.0) + n["w"]
    cat = max(d, key=d.get); return dict(category=cat, conf=float(d[cat]), dist=dict(sorted(d.items(), key=lambda x: -x[1])))


def consensus(nb, attr):
    d = {}
    for n in nb:
        if n[attr]: d[n[attr]] = d.get(n[attr], 0.0) + n["w"]
    if not d: return None, 0.0
    v = max(d, key=d.get); return v, d[v] / sum(d.values())


def attr_share(nb, attr, value) -> float:
    """Part (pondérée) des voisins dont l'attribut vaut `value`."""
    tot = sum(n["w"] for n in nb if n[attr]);
    return sum(n["w"] for n in nb if n[attr] == value) / tot if tot else 0.0
