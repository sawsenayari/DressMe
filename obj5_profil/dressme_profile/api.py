"""Service HTTP de l'objectif 5 (FastAPI).

Lancer :  uvicorn dressme_profile.api:app --port 8005
Endpoints : GET /health, POST /profile, POST /recommend, GET /schema/profile
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import FastAPI, HTTPException

from . import config
from .contracts import ProfileRequest, RecommendRequest, RecommendResponse, StyleProfile
from .mock import mock_profile, mock_recommend

app = FastAPI(title="DressMe — Objectif 5 : profil de style", version="1.0.0")


@lru_cache(maxsize=1)
def get_service():
    from .service import ProfileService
    return ProfileService()


@app.get("/health")
def health():
    if config.USE_MOCK:
        return {"status": "ok", "mode": "mock"}
    svc = get_service()
    return {"status": "ok", "mode": "real", "model": svc.model.name,
            "catalog_items": len(svc.catalog)}


@app.get("/schema/profile")
def profile_schema():
    return StyleProfile.model_json_schema()


@app.post("/profile", response_model=StyleProfile)
def profile(req: ProfileRequest):
    if config.USE_MOCK:
        return mock_profile(req.user_id)
    try:
        return get_service().profile(req)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest):
    if config.USE_MOCK:
        return mock_recommend(req.user_id)
    try:
        return get_service().recommend(req)
    except KeyError as e:
        raise HTTPException(404, str(e.args[0]))
    except ValueError as e:
        raise HTTPException(422, str(e))
