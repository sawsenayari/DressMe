"""Pont vers l'objectif 2 : score de compatibilité visuelle d'une tenue (FashionCLIP -> service Obj2).

Deux modes (au choix, automatique) :
  - local  : importe `core.CompatEngine` du dossier obj2_compat (variable DRESSME_OBJ2, défaut ../obj2_compat) ;
  - http   : si COMPAT_URL est défini (ex. http://localhost:8002), appelle POST /pairs.
Les embeddings des pièces sont lus dans <APP_DATA>/emb.npz (clés `ids`, `emb` ; voir make_piece_embeddings.py).
Si quelque chose manque (embeddings, objectif 2, pièce inconnue), `score()` renvoie None : le jury continue sans.
Le score est INFORMATIF : il n'entre pas dans le verdict de l'arbitre (non validé sur les tenues annotées).
"""
import os
import sys

import numpy as np

CAT = {"haut": "tops", "bas": "bottoms", "robe": "all-body", "veste": "outerwear",
       "chaussures": "shoes", "sac": "bags", "accessoire": "accessories"}
GOOD, BAD = 0.75, 0.35       # seuils /pairs calibrés (Obj2) : "va bien" / "peu probable"


def level(s):
    return "va bien" if s >= GOOD else ("moyen" if s >= BAD else "peu probable")


class CompatBridge:
    def __init__(self, emb_path, obj2_dir=None, url=None):
        z = np.load(emb_path, allow_pickle=False)
        self.emb = {str(i): v.astype(np.float32) for i, v in zip(z["ids"], z["emb"])}
        self.url = url or os.environ.get("COMPAT_URL")
        self.engine = None
        if not self.url:
            here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            d = obj2_dir or os.environ.get("DRESSME_OBJ2") or os.path.join(os.path.dirname(here), "obj2_compat")
            sys.path.insert(0, d)
            from core import CompatEngine          # ImportError -> géré par from_folder
            self.engine = CompatEngine(base=d)

    @classmethod
    def from_folder(cls, root):
        p = os.path.join(root, "emb.npz")
        if not os.path.exists(p):
            return None
        try:
            return cls(p)
        except Exception as e:
            print("Compatibilité Obj2 désactivée :", type(e).__name__, e)
            return None

    def score(self, pieces):
        """pieces : liste de fiches de pièces ({id, categorie,...}). Renvoie un dict ou None."""
        ps = [p for p in pieces if p["id"] in self.emb and p.get("categorie") in CAT]
        if len(ps) < 2:
            return None
        items = [{"id": p["id"], "category": CAT[p["categorie"]], "embedding": self.emb[p["id"]].tolist()} for p in ps]
        if self.url:
            import requests
            M = requests.post(self.url.rstrip("/") + "/pairs", json={"a": items, "b": items}, timeout=30).json()["scores01"]
        else:
            M = self.engine.pairs(items, items)
        n = len(ps)
        pairs = [{"a": ps[i]["id"], "b": ps[j]["id"], "score01": round(float(M[i][j]), 2)} for i in range(n) for j in range(i + 1, n)]
        mean = float(np.mean([M[i][j] for i in range(n) for j in range(n) if i != j]))
        worst = min(pairs, key=lambda x: x["score01"])
        return {"outfit_compat01": round(mean, 2), "niveau": level(mean), "pire_paire": worst, "paires": pairs,
                "source": "obj2 FashionCLIP + PairMLP (informatif, non intégré au verdict)"}
