"""API du jury (backend seul, sans Gradio) : python -m uvicorn api:app --port 8003
GET /health · GET /pieces?categorie=&gender= · POST /judge   (documentation : /docs)
Variables : APP_DATA (dossier de données), GEMINI_API_KEY / LLM_API_KEY (facultatives), COMPAT_URL (facultative), CORS_ORIGINS.
"""
import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dressme.service import DressMeService

root = os.environ.get("APP_DATA")
try:
    SVC = DressMeService.from_folder(root)
except FileNotFoundError:
    SVC = DressMeService.from_demo(); print("APP_DATA introuvable : données de démonstration.")

app = FastAPI(title="DressMe – jury (Obj3) + compatibilité (Obj2)")
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])


class JudgeIn(BaseModel):
    pieces: List[str]
    temperature: float = 18
    pluie: bool = False
    occasion: str = "décontracté"
    mode: str = "complet"
    repair: bool = True


@app.get("/health")
def health():
    return {"ok": True, "pieces": len(SVC.pieces), "llm": SVC.llm is not None, "compatibilite": SVC.compat is not None}


@app.get("/pieces")
def pieces(categorie: Optional[str] = None, gender: Optional[str] = None):
    return SVC.list_pieces(categorie, gender)


@app.post("/judge")
def judge(x: JudgeIn):
    try:
        return SVC.judge(x.pieces, x.temperature, x.pluie, x.occasion, x.mode, x.repair)
    except ValueError as e:
        raise HTTPException(422, str(e))
