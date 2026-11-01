import io, os
from datetime import datetime
from pathlib import Path
try:   # certificats du système (proxy qui intercepte le HTTPS : météo, Gemini, Groq) ; facultatif
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
from typing import Literal, Optional
from zoneinfo import ZoneInfo
import numpy as np
from PIL import Image
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import ranker, segment, store, vision
from .agent import explain, parse_agenda
from .catalog import CROP, IMAGES, demo_wardrobe, item_from_prediction
from .context import build_context, get_weather
from .assistant import run_assistant
from .features import featurize, target_warmth, warnings
from .outfits import diversify, generate, pick_accessories
from .agent import ROLES, model_for
from .rag import KB, retrieve

Occasion = Literal["casual", "work", "formal", "sport", "wedding", "religious", "party"]
Gender = Literal["Men", "Women"]

class Item(BaseModel):
    id: str; name: str; slot: Literal["top", "bottom", "footwear", "outer", "onepiece", "accessory"]; colour: str
    usage: str = "Casual"; warmth: float = 1.0; formality: int = Field(1, ge=0, le=3)
    waterproof: bool = False; open_toe: bool = False; image: Optional[str] = None; type: Optional[str] = None; gender: str = "Unisex"

class Weather(BaseModel):
    feels_like: float; rain_prob: float = Field(0, ge=0, le=1); wind: float = 0

class RecommendRequest(BaseModel):
    wardrobe: Optional[list[Item]] = None
    city: str = "Tunis"; agenda: Optional[str] = None; occasion: Optional[Occasion] = None
    gender: Optional[Gender] = None
    weather: Optional[Weather] = None; when: Optional[datetime] = None; k: int = Field(3, ge=1, le=10); seed: int = 0
    colours: list[str] = []; types: list[str] = []   # envies facultatives ; vide = aucun filtre
    uid: str = "anon"; explain: bool = False
    exclude_ids: list[str] = []; exclude_outfits: list[list[str]] = []   # articles / tenues refusés (changement de tenue)

class FeedbackRequest(BaseModel):
    features: dict[str, float]; accepted: bool; uid: str = "anon"
    reason: Optional[Literal["too_hot", "too_cold", "too_formal", "too_casual", "style"]] = None; item_ids: list[str] = []

app = FastAPI(title="DressMe — Contextual Outfit API", version="2.0")

@app.get("/health")
def health(): return {"status": "ok", "model_loaded": ranker.model_loaded(), "vision_loaded": vision.available()}

@app.get("/api/sample-wardrobe")
def sample(seed: int = 0, gender: Gender = "Women"): return demo_wardrobe(seed, gender)

@app.get("/api/options")
def options(seed: int = 0, gender: Gender = "Women"):
    w = demo_wardrobe(seed, gender)
    return {"colours": sorted({i["colour"] for i in w if i["slot"] != "accessory"}),
            "types": sorted({i["type"] for i in w if i.get("type") and i["slot"] != "accessory"})}

@app.get("/api/parse")
async def parse(text: str, rag: bool = True, llm: bool = True): return await parse_agenda(text, rag, llm)

@app.get("/api/agents")   # quel agent utilise quel modèle (utile pour la démonstration)
def agents():
    return {"llm_agents": {a: {"model": model_for(a), "role": ROLES[a]} for a in ROLES}, "llm_base_url": os.getenv("LLM_BASE_URL"),
            "rag": {"fiches": len(KB), "recherche": "TF-IDF sur n-grammes de caractères"}, "vision": {"charge": vision.available()}, "classement": ranker.kind()}

@app.get("/api/rag")
def rag(q: str): return retrieve(q)

@app.get("/api/stats")
def stats(uid: str = "anon"): return store.stats(uid)

class AskRequest(BaseModel):
    question: str; gender: Gender = "Women"; uid: str = "anon"; mcp: bool = False; wardrobe: Optional[list[Item]] = None

@app.post("/api/assistant")
async def assistant(req: AskRequest):
    try: return await run_assistant(req.question, req.gender, req.uid, [i.model_dump() for i in req.wardrobe] if req.wardrobe else None, req.mcp)
    except Exception as e: raise HTTPException(503, f"Assistant indisponible : {e!r}")

@app.post("/api/analyze-photo")
async def analyze_photo(file: UploadFile):
    if not vision.available(): raise HTTPException(503, "Modèle vision absent : lance training.prepare_data puis training.vision")
    try:
        img = Image.open(io.BytesIO(await file.read())).convert("RGB"); seg_ok = segment.available()
        worn, parts = segment.extract_parts(img) if seg_ok else (False, {"photo": img})  # photo portée : une pièce par vêtement détecté
        res = []
        for name, im in (parts or {"photo": img}).items():
            pred = vision.analyze_image(im); it = item_from_prediction(pred); it["image"] = segment.thumb(im)
            res.append({"part": name, "prediction": pred, "item": it})
    except Exception as e: raise HTTPException(422, f"Analyse impossible : {e!r}")
    return {"worn": worn, "segmentation": seg_ok, "results": res}

@app.post("/api/recommend")
async def recommend(req: RecommendRequest):
    now = req.when or datetime.now(ZoneInfo("Africa/Tunis"))
    ag = await parse_agenda(req.agenda) if req.agenda else {}
    gender = req.gender or ag.get("gender") or "Women"
    wx = (req.weather.model_dump() | {"source": "request"}) if req.weather else await get_weather(req.city)
    ctx = build_context(now, wx, req.occasion or ag.get("occasion"), None if req.occasion else ag.get("formality"))
    items = [i.model_dump() for i in req.wardrobe] if req.wardrobe else demo_wardrobe(req.seed, gender)
    info = {**ctx.__dict__, "gender": gender, "weather_source": wx["source"], "agenda_source": ag.get("source"),
            "agenda_error": ag.get("error"), "agenda_notes": ag.get("notes"), "retrieved": ag.get("retrieved"),
            "target_warmth": round(target_warmth(ctx.feels_like, ctx.wind), 2)}
    ex_i, ex_o = set(req.exclude_ids), {frozenset(x) for x in req.exclude_outfits}
    all_c = generate(items)
    cands = [o for o in all_c if not any(i["id"] in ex_i for i in o) and frozenset(i["id"] for i in o) not in ex_o]
    if not cands:
        return {"context": info, "outfits": [], "message": "Plus de tenue possible avec tes exclusions : réinitialise-les." if all_c else
                "Garde-robe insuffisante : il faut (haut + bas) ou une pièce unique, plus des chaussures."}
    cs, ts = {c.lower() for c in req.colours}, set(req.types)  # OU dans un groupe, ET entre groupes
    pick = [o for o in cands if (not cs or any(i["colour"] in cs for i in o)) and (not ts or any(i.get("type") in ts for i in o))]
    info["prefs_relaxed"] = bool((cs or ts) and not pick); cands = pick or cands
    feats = [featurize(ctx, o) for o in cands]
    pref, worn = store.prefs(req.uid), store.recent_worn(req.uid)
    def adj(s, o):  # personnalisation : goûts appris (👍/👎) et rotation (pièces portées ces 3 derniers jours)
        ids = [i["id"] for i in o]
        return s + .1 * np.mean([pref.get(i, 0) for i in ids]) - .2 * np.mean([i in worn for i in ids])
    sc = [adj(s, o) for s, o in zip(ranker.score(feats).tolist(), cands)]
    top = diversify(sorted(zip(sc, cands, feats), key=lambda x: -x[0]), req.k)
    accs = [i for i in items if i["slot"] == "accessory" and i["id"] not in ex_i]
    def why(f):
        r = []
        if f["abs_warmth_gap"] <= 1: r.append(f"Épaisseur adaptée à {ctx.feels_like:.0f}°C")
        if ctx.rain_prob > .5 and not f["open_footwear"]: r.append(f"Chaussures fermées (pluie {ctx.rain_prob:.0%})")
        if f["usage_match"] == 1: r.append(f"Cohérent avec l'occasion « {ctx.occasion} »")
        if f["traditional"] and (ctx.eid or ctx.occasion in ("wedding", "religious")): r.append("Tenue traditionnelle de circonstance")
        return r
    outs = [{"score": round(s, 4), "items": o, "accessories": pick_accessories(o, accs, ctx), "reasons": why(f), "features": f, "warnings": warnings(f, ctx),
             "item_ids": [i["id"] for i in o]} for s, o, f in top]
    if req.explain:
        ex = await explain({k: info[k] for k in ("occasion", "formality", "feels_like", "rain_prob", "ramadan", "eid")},
                           [{"articles": [i["name"] for i in o["items"]], "alertes": o["warnings"]} for o in outs], retrieve(req.agenda or ctx.occasion))
        for o, e in zip(outs, ex or []): o["explanation"] = e
    return {"context": info, "outfits": outs}

@app.post("/api/feedback")
def feedback(fb: FeedbackRequest):
    store.save_feedback(fb.uid, fb.features, fb.accepted, fb.reason, fb.item_ids)
    return {"stored": True, **store.stats(fb.uid)}

CROP.mkdir(parents=True, exist_ok=True); app.mount("/images_crop", StaticFiles(directory=CROP), name="images_crop")
if IMAGES.exists(): app.mount("/images", StaticFiles(directory=IMAGES), name="images")
app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "static", html=True), name="static")
