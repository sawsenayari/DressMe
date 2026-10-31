"""Passerelle DressMe (provisoire, avant l'objectif 6) : UN backend sur le port 8000 pour le front.

Routes attendues par le front (frontend/src/services) :
  GET  /health
  GET  /wardrobe/items            -> fiches du catalogue (ItemCard -> ClothingItem)         [Obj1 : lecture seule]
  POST /wardrobe/items            -> 501 tant que l'objectif 1 (classification d'une photo) n'est pas branché
  POST /compatibility/score       -> photo (+ champ facultatif `category`) -> embedding FashionCLIP -> Obj2 /compat
  GET  /gaps                      -> rapport de l'objectif 4 (gap_report.json)
  GET/PUT /profile                -> profil de style de l'objectif 5
  GET  /outfits/today             -> 501 tant que l'objectif 6 (tenue du jour) n'est pas branché
  /files/...                      -> images du catalogue

Dossiers (variables d'environnement, défauts relatifs à la racine du dépôt) :
  DRESSME_STORE  fiches + images + emb/*.npy      (défaut : obj5_profil/data)
  DRESSME_OBJ2   dossier du service de compatibilité (défaut : obj2_compat)
  DRESSME_GAPS   rapport de manques               (défaut : obj4_manques/gap_report.json)
"""
import io
import json
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

REPO = Path(__file__).resolve().parent.parent
STORE = Path(os.environ.get("DRESSME_STORE", REPO / "obj5_profil" / "data"))
OBJ2 = Path(os.environ.get("DRESSME_OBJ2", REPO / "obj2_compat"))
GAPS = Path(os.environ.get("DRESSME_GAPS", REPO / "obj4_manques" / "gap_report.json"))
os.environ.setdefault("DRESSME_STORE", str(STORE))
os.environ.setdefault("DRESSME_CATALOG", str(STORE / "wardrobe.json"))
os.environ.setdefault("DRESSME_ASSETS_DIR", str(STORE))
sys.path.insert(0, str(OBJ2))
sys.path.insert(0, str(REPO / "obj5_profil"))

from core import CompatEngine, CardStore  # noqa: E402  (objectif 2)

app = FastAPI(title="DressMe – passerelle front")
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])
if STORE.exists():
    app.mount("/files", StaticFiles(directory=str(STORE)), name="files")

_cache = {}


def engine():
    if "e" not in _cache:
        _cache["e"] = CompatEngine(base=str(OBJ2), store=CardStore(str(STORE)))
    return _cache["e"]


def catalog():
    if "c" not in _cache:
        p = STORE / "wardrobe.json"
        if not p.exists():
            raise HTTPException(503, f"catalogue introuvable : {p} (variable DRESSME_STORE)")
        d = json.load(open(p, encoding="utf-8"))
        _cache["c"] = d if isinstance(d, list) else d.get("items", [])
    return _cache["c"]


def wardrobe_with_embeddings():
    return [c for c in catalog() if c.get("embedding") and (STORE / c["embedding"]).exists()]


# ---------------------------------------------------------------- embedding d'une photo (FashionCLIP)
SLOT_PROMPTS = {  # catégories Polyvore de l'objectif 2 -> texte (zéro-shot, comme dans le test réel)
    "tops": "a photo of a top, shirt, t-shirt or sweater", "bottoms": "a photo of trousers, jeans or a skirt",
    "all-body": "a photo of a dress or a jumpsuit", "outerwear": "a photo of a jacket or a coat",
    "shoes": "a photo of a pair of shoes", "bags": "a photo of a handbag", "accessories": "a photo of a fashion accessory",
    "hats": "a photo of a hat", "jewellery": "a photo of jewellery", "scarves": "a photo of a scarf",
    "sunglasses": "a photo of sunglasses",
}


def embed_photo(data: bytes):
    """Renvoie (vecteur 512 normalisé, catégorie devinée). Premier appel : télécharge FashionCLIP (~600 Mo)."""
    if "clip" not in _cache:
        import torch
        import torchvision.transforms as T
        from transformers import CLIPModel, CLIPProcessor, CLIPImageProcessor
        name = "patrickjohncyh/fashion-clip"
        m = CLIPModel.from_pretrained(name).eval()
        pr, ip = CLIPProcessor.from_pretrained(name), CLIPImageProcessor.from_pretrained(name)
        tf = T.Compose([T.Resize(224, interpolation=T.InterpolationMode.BICUBIC), T.CenterCrop(224), T.ToTensor(),
                        T.Normalize(ip.image_mean, ip.image_std)])
        with torch.no_grad():
            t = m.get_text_features(**pr(text=list(SLOT_PROMPTS.values()), return_tensors="pt", padding=True))
            t = t if isinstance(t, torch.Tensor) else t[0]
            t = t / t.norm(dim=-1, keepdim=True)
        _cache["clip"] = (m, tf, t)
    import torch
    sys.path.insert(0, str(OBJ2))
    from embed_cards import load_img
    m, tf, txt = _cache["clip"]
    tmp = io.BytesIO(data)
    with torch.no_grad():
        o = m.get_image_features(pixel_values=tf(load_img(tmp)).unsqueeze(0))
        o = o if isinstance(o, torch.Tensor) else o[0]
        o = o / o.norm(dim=-1, keepdim=True)
    cat = list(SLOT_PROMPTS)[int((o @ txt.T).argmax())]
    return o[0].numpy().astype(np.float32), cat


# ---------------------------------------------------------------- mappings vers les types du front
def to_front_item(c):
    img = lambda p: f"/files/{p}" if p else None
    col = c.get("colour") or []
    return {"id": c["id"], "name": c.get("name") or c.get("type"), "slot": c["slot"], "category": c["slot"],
            "type": c.get("type"), "colour": col, "color": col[0] if col else "", "usage": c.get("usage"),
            "warmth": c.get("warmth"), "formality": c.get("formality"), "waterproof": c.get("waterproof"),
            "open_toe": c.get("open_toe"), "gender": c.get("gender"), "imageUrl": img(c.get("image")) or "",
            "imageCrop": img(c.get("image_crop")), "season": c.get("season") or "all", "pattern": c.get("pattern"),
            "confidence": c.get("confidence"), "source": c.get("source"), "price_dt": c.get("price_dt"),
            "traditional": c.get("traditional")}


VERDICT = {"compatible": "compatible", "moyenne": "moyenne", "peu compatible": "peu compatible"}


def compat_for(vec, category, wardrobe, name="candidate"):
    cand = {"id": name, "category": category, "embedding": vec.tolist()}
    W = [{"id": c["id"], "slot": c["slot"], "embedding": c["embedding"]} for c in wardrobe]
    r = engine().compat(cand, W)
    if "error" in r:
        raise HTTPException(422, r["error"])
    return {"score": r["rank100"], "score01": r["score01"], "verdict": VERDICT.get(r["verdict"], r["verdict"]),
            "newOutfits": 0, "partners": [{"id": p["id"], "pair_score01": p["pair_score01"]} for p in r["partners"]],
            "duplicate": r["duplicate"], "clashingItems": [],
            "notes": [f"Catégorie utilisée : {category}.",
                      "Score = rang parmi 300 articles Polyvore de même catégorie (50 = hasard).",
                      "newOutfits non calculé : à fournir par l'objectif 4."]}


# ---------------------------------------------------------------- routes
@app.get("/health")
def health():
    cat = catalog() if (STORE / "wardrobe.json").exists() else []
    return {"ok": True, "store": str(STORE), "items": len(cat), "items_avec_embedding": len(wardrobe_with_embeddings()) if cat else 0,
            "gaps": GAPS.exists()}


@app.get("/wardrobe/items")
def list_items():
    return [to_front_item(c) for c in catalog()]


@app.post("/wardrobe/items")
async def add_item(image: UploadFile = File(...)):
    raise HTTPException(501, "Classification d'une photo = objectif 1, pas encore branché.")


@app.post("/compatibility/score")
async def compat_score(image: UploadFile = File(...), category: Optional[str] = Form(None)):
    W = wardrobe_with_embeddings()
    if len(W) < 2:
        raise HTTPException(503, "Moins de 2 articles avec embedding dans le catalogue : lancer embed_cards.py (voir README).")
    W = W[:int(os.environ.get("MAX_WARDROBE", "40"))]   # le calcul croît avec le carré de la taille de la garde-robe
    data = await image.read()
    try:
        vec, guessed = embed_photo(data)
    except ImportError as e:
        raise HTTPException(503, f"torch/transformers manquants : {e}")
    return compat_for(vec, category or guessed, W)


@app.get("/gaps")
def gaps():
    if not GAPS.exists():
        raise HTTPException(503, f"rapport de manques introuvable : {GAPS}")
    d = json.load(open(GAPS, encoding="utf-8"))
    for i, g in enumerate(d if isinstance(d, list) else []):
        g.setdefault("rank", i + 1)
    return d


AXIS = {"efficacite": "efficiency", "economie": "economy", "image": "brand", "mixte": "mixte"}
_prefs = {"axis": None, "budgetMode": False}


def _profile_service():
    if "p" not in _cache:
        from dressme_profile import ProfileService
        _cache["p"] = ProfileService()
    return _cache["p"]


@app.get("/profile")
def get_profile():
    from dressme_profile import ProfileRequest
    ids = [c["id"] for c in catalog()]
    p = _profile_service().profile(ProfileRequest(user_id="me", item_ids=ids)).model_dump()
    s = p["scores"]
    pct = lambda v: None if v is None else round(100 * v)
    return {"axis": _prefs["axis"] or AXIS.get(p["persona"], "mixte"), "budgetMode": _prefs["budgetMode"],
            "scores": {"efficacite": pct(s["efficacite"]), "economie": pct(s["economie"]), "image": pct(s["image"])},
            "diversityScore": pct(p["diversity"]), "formalityPref": p["formality_pref"],
            "dominantCluster": (p.get("dominant_cluster") or {}).get("name"),
            "palette": [{"color": e["colour"], "weight": e["weight"]} for e in p["palette"]]}


@app.put("/profile")
def put_profile(body: dict):
    _prefs["axis"] = body.get("axis") or _prefs["axis"]
    _prefs["budgetMode"] = bool(body.get("budgetMode", _prefs["budgetMode"]))
    return get_profile()


@app.get("/outfits/today")
def outfit_today(occasion: str = "casual", budget: bool = False):
    raise HTTPException(501, "Tenue du jour = objectif 6 (contexte, météo, agenda), pas encore branché.")
