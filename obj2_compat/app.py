"""API FastAPI : lancer avec  uvicorn app:app --port 8002"""
from typing import Any, Dict, List, Optional, Union
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from core import CompatEngine, pair_verdict, PAIR_GOOD, PAIR_BAD

app = FastAPI(title="DressMe - compatibilité (objectif 2)", version="1.0")
engine = CompatEngine()


# Un article est soit un identifiant (str, résolu dans le dossier de fiches DRESSME_STORE), soit une fiche ItemCard (dict).
# Les champs inconnus d'une fiche sont ignorés ; `embedding` = liste de 512 nombres OU chemin .npy relatif à DRESSME_STORE.
Item = Union[str, Dict[str, Any]]


class CompatIn(BaseModel):
    candidate: Item
    wardrobe: List[Item]


class PairsIn(BaseModel):
    a: List[Item]
    b: List[Item]


@app.get("/health")
def health():
    return {"ok": True, "model": "pairmlp-image-fitb-3seeds", "categories": engine.cats}


@app.post("/compat")
def compat(x: CompatIn):
    try:
        r = engine.compat(x.candidate, x.wardrobe)
    except ValueError as e:
        raise HTTPException(422, str(e))
    if "error" in r: raise HTTPException(422, r["error"])
    return r


@app.post("/pairs")
def pairs(x: PairsIn):
    try:
        sc = engine.pairs(x.a, x.b)
        return {"scores01": sc, "verdicts": [[pair_verdict(v) for v in row] for row in sc],
                "thresholds": {"va bien": PAIR_GOOD, "peu probable": PAIR_BAD}}
    except ValueError as e:
        raise HTTPException(422, str(e))
