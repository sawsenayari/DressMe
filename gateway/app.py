"""Passerelle DressMe (provisoire, avant l'objectif 6) : UN backend sur le port 8000 pour le front.

Routes attendues par le front (frontend/src/services) :
  GET  /health
  GET  /wardrobe/items            -> fiches du catalogue (ItemCard -> ClothingItem)         [Obj1 : lecture seule]
  POST /wardrobe/items            -> photo -> Obj1 (crop + ItemCard v1 + emb/<id>.npy) -> ajout au catalogue ; 501 si l'Obj1 n'est pas lançable
  POST /compatibility/score       -> photo (+ champ facultatif `category`) -> embedding FashionCLIP -> Obj2 /compat
  GET  /gaps                      -> rapport de l'objectif 4 (gap_report.json)
  GET/PUT /profile                -> profil de style de l'objectif 5
  GET  /outfits/today             -> Obj6 (service HTTP, candidats + contexte météo) -> jury Obj3 (règles) + compatibilité Obj2 -> Outfit ; 501 si l'Obj6 ne répond pas
  POST /outfits/judge             -> tenue composée -> jury Obj3 (règles + réparations) + compatibilité Obj2 -> OutfitJuryResult
  /files/...                      -> images du catalogue

Dossiers (variables d'environnement, défauts relatifs à la racine du dépôt) :
  DRESSME_STORE  fiches + images + emb/*.npy      (défaut : obj5_profil/data)
  DRESSME_OBJ2   dossier du service de compatibilité (défaut : obj2_compat)
  DRESSME_GAPS   rapport de manques               (défaut : obj4_manques/gap_report.json)
  DRESSME_OBJ1   dossier de la reconnaissance     (défaut : obj1_reconnaissance)
  DRESSME_OBJ3   dossier du jury de tenues        (défaut : obj3_jury)
  OBJ6_URL       service de l'objectif 6          (défaut : http://127.0.0.1:8006 ; lancé depuis obj6_app, voir run_all.bat)
  DRESSME_OBJ1_MODE  auto (défaut : service complet, sinon kNN sur la base locale) | full (Kaggle ; Qwen si DRESSME_OBJ1_LLM=1)
                     | knn (base locale data/agent_final, sans Kaggle ni LLM) | mock (fiches factices, embedding ALÉATOIRE : tests seulement)
"""
import io
import json
import os
import sys
import tempfile
import threading
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

REPO = Path(__file__).resolve().parent.parent
STORE = Path(os.environ.get("DRESSME_STORE", REPO / "obj5_profil" / "data"))
OBJ2 = Path(os.environ.get("DRESSME_OBJ2", REPO / "obj2_compat"))
GAPS = Path(os.environ.get("DRESSME_GAPS", REPO / "obj4_manques" / "gap_report.json"))
OBJ1 = Path(os.environ.get("DRESSME_OBJ1", REPO / "obj1_reconnaissance"))
OBJ3 = Path(os.environ.get("DRESSME_OBJ3", REPO / "obj3_jury"))
OBJ6_URL = os.environ.get("OBJ6_URL", "http://127.0.0.1:8006")
os.environ.setdefault("DRESSME_ROOT", str(OBJ1 / "data"))          # base kNN de l'Obj1 (data/agent_final)
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


CLIP_NAME = "patrickjohncyh/fashion-clip"


def clip():
    """(modèle, transformation, vecteurs texte des catégories) de FashionCLIP, chargés une fois (partagés avec l'Obj1)."""
    if "clip" not in _cache:
        import torch
        import torchvision.transforms as T
        from transformers import CLIPModel, CLIPProcessor, CLIPImageProcessor
        name = CLIP_NAME
        m = CLIPModel.from_pretrained(name).eval()
        pr, ip = CLIPProcessor.from_pretrained(name), CLIPImageProcessor.from_pretrained(name)
        tf = T.Compose([T.Resize(224, interpolation=T.InterpolationMode.BICUBIC), T.CenterCrop(224), T.ToTensor(),
                        T.Normalize(ip.image_mean, ip.image_std)])
        with torch.no_grad():
            t = m.get_text_features(**pr(text=list(SLOT_PROMPTS.values()), return_tensors="pt", padding=True))
            t = t if isinstance(t, torch.Tensor) else t.pooler_output   # transformers >= 5 : sortie structurée
            t = t / t.norm(dim=-1, keepdim=True)
        _cache["clip"] = (m, tf, t)
    return _cache["clip"]


def embed_photo(data: bytes):
    """Renvoie (vecteur 512 normalisé, catégorie devinée). Premier appel : télécharge FashionCLIP (~600 Mo)."""
    m, tf, txt = clip()
    import torch
    sys.path.insert(0, str(OBJ2))
    from embed_cards import load_img
    tmp = io.BytesIO(data)
    with torch.no_grad():
        o = m.get_image_features(pixel_values=tf(load_img(tmp)).unsqueeze(0))
        o = o if isinstance(o, torch.Tensor) else o.pooler_output
        o = o / o.norm(dim=-1, keepdim=True)
    cat = list(SLOT_PROMPTS)[int((o @ txt.T).argmax())]
    return o[0].numpy().astype(np.float32), cat


# ---------------------------------------------------------------- mappings vers les types du front
SEASON_FRONT = {"spring": "spring", "summer": "summer", "fall": "autumn", "autumn": "autumn", "winter": "winter", "all": "all"}
SEASON_STORE = {"autumn": "fall"}   # le contrat ItemCard (Obj1) écrit "fall" ; le front affiche "autumn"


def to_front_item(c):
    img = lambda p: f"/files/{p}" if p else None
    col = c.get("colour") or []
    return {"id": c["id"], "name": c.get("name") or c.get("type"), "slot": c["slot"], "category": c["slot"],
            "type": c.get("type"), "colour": col, "color": col[0] if col else "", "usage": c.get("usage"),
            "warmth": c.get("warmth"), "formality": c.get("formality"), "waterproof": c.get("waterproof"),
            "open_toe": c.get("open_toe"), "gender": c.get("gender"), "imageUrl": img(c.get("image")) or "",
            "imageCrop": img(c.get("image_crop")), "season": SEASON_FRONT.get(c.get("season") or "all", "all"), "pattern": c.get("pattern"),
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


# ---------------------------------------------------------------- objectif 1 : photo -> fiche
_write_lock = threading.Lock()


def recognizer():
    """Service de reconnaissance de l'Obj1, chargé une fois. Toute erreur de chargement -> 501 (Obj1 non lançable)."""
    mode = os.environ.get("DRESSME_OBJ1_MODE", "auto")
    if ("obj1", mode) not in _cache:
        try:
            if not (OBJ1 / "recognition").is_dir():
                raise FileNotFoundError(f"dossier introuvable : {OBJ1 / 'recognition'}")
            if str(OBJ1) not in sys.path:
                sys.path.append(str(OBJ1))
            if mode == "mock":
                from recognition.mock import MockRecognizer
                svc = MockRecognizer()
            elif mode == "knn":
                svc = _obj1_local_knn()
            else:  # full, ou auto : service complet (base Kaggle, Qwen si DRESSME_OBJ1_LLM=1), sinon kNN sur la base locale
                try:
                    from recognition.config import CFG
                    from recognition.service import RecognitionService
                    svc = RecognitionService.from_config(CFG, load_llm=os.environ.get("DRESSME_OBJ1_LLM") == "1")
                except Exception as e:
                    if mode != "auto":
                        raise
                    print(f"[obj1] service complet indisponible ({type(e).__name__}) : kNN sur la base locale.", file=sys.stderr)
                    svc = _obj1_local_knn()
            _cache[("obj1", mode)] = (svc, None)
        except Exception as e:  # dépendances (torch, transformers, kagglehub…), modèles ou base kNN absents
            _cache[("obj1", mode)] = (None, f"{type(e).__name__}: {e}")
    svc, err = _cache[("obj1", mode)]
    if svc is None:
        raise HTTPException(501, f"Objectif 1 non lançable ({err}).")
    return svc


def _obj1_local_knn():
    """Obj1 en mode « knn_only » sans Kaggle ni LLM : crop (SegFormer / rembg) -> FashionCLIP gelé -> vote des voisins
    sur la base locale data/agent_final (kb_meta.csv + kb_emb.npy) -> ItemCard v1. Même encodeur que la passerelle."""
    import pandas as pd
    from transformers import CLIPProcessor
    from recognition.agent import RecognitionAgent
    from recognition.config import CFG
    from recognition.crop import Cropper
    from recognition.embedder import FashionClipEmbedder
    from recognition.retrieval import Retriever
    from recognition.service import RecognitionService
    meta, emb = CFG.out / "kb_meta.csv", CFG.out / "kb_emb.npy"
    if not (meta.exists() and emb.exists()):
        raise FileNotFoundError(f"base kNN de l'Obj1 absente : {meta} / {emb}")
    shared = FashionClipEmbedder(model=clip()[0], proc=CLIPProcessor.from_pretrained(CLIP_NAME), device="cpu")
    agent = RecognitionAgent(None, shared, Retriever(np.load(emb), pd.read_csv(meta)), CFG)
    return RecognitionService(agent, shared, CFG, None, "knn_only", cropper=Cropper.from_config(CFG))


def _next_id():
    used = {c["id"] for c in catalog()}
    n = 1 + max([int(i[3:]) for i in used if i.startswith("it_") and i[3:].isdigit()] or [0])
    while f"it_{n:04d}" in used:
        n += 1
    return f"it_{n:04d}"


def _load_catalog_file():
    d = json.load(open(STORE / "wardrobe.json", encoding="utf-8"))
    return d, (d if isinstance(d, list) else d.setdefault("items", []))


def _save_catalog_file(d):
    p = STORE / "wardrobe.json"
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, p)
    for k in ("c", "p", "j"):  # catalogue relu ; profil Obj5 et jury Obj3 reconstruits (ils refusent les identifiants inconnus)
        _cache.pop(k, None)


def _append_to_catalog(card):
    d, items = _load_catalog_file()
    items.append(card)
    _save_catalog_file(d)


def _store_file(rel):
    """Chemin d'un fichier du store, refusé s'il sort du dossier (chemins lus dans les fiches)."""
    if not rel:
        return None
    f = (STORE / rel).resolve()
    return f if STORE.resolve() in f.parents else None


SLOTS = {"top", "bottom", "onepiece", "outer", "footwear", "bag", "accessory"}
USAGES = {"Casual", "Smart Casual", "Formal", "Sports", "Ethnic", "Party"}
SEASONS = {"spring", "summer", "fall", "winter", "all"}


def _check_patch(body):
    """Champs modifiables d'une fiche ItemCard v1, validés ; accepte aussi les noms du front (color, category, autumn)."""
    b = dict(body)
    if "color" in b and "colour" not in b:
        b["colour"] = [b.pop("color")]
    if "category" in b and "slot" not in b:
        b["slot"] = b.pop("category")
    out, err = {}, []
    if "name" in b:
        out["name"] = str(b["name"]).strip() or err.append("name vide")
    if "type" in b:
        out["type"] = str(b["type"]).strip() or err.append("type vide")
    if "slot" in b:
        out["slot"] = b["slot"] if b["slot"] in SLOTS else err.append(f"slot : {sorted(SLOTS)}")
    if "colour" in b:
        col = [str(x).strip().lower() for x in (b["colour"] if isinstance(b["colour"], list) else [b["colour"]]) if str(x).strip()]
        out["colour"] = col if 1 <= len(col) <= 2 else err.append("colour : 1 ou 2 couleurs")
    if "usage" in b:
        out["usage"] = b["usage"] if b["usage"] in USAGES else err.append(f"usage : {sorted(USAGES)}")
    if "season" in b:
        sea = SEASON_STORE.get(b["season"], b["season"])
        out["season"] = sea if sea in SEASONS else err.append("season : spring, summer, autumn, winter, all")
    for k, hi in (("formality", 3), ("warmth", 4)):
        if k in b:
            try:
                v = int(b[k]); out[k] = v if 0 <= v <= hi else err.append(f"{k} : 0 à {hi}")
            except (TypeError, ValueError):
                err.append(f"{k} : entier 0 à {hi}")
    for k in ("traditional", "waterproof", "open_toe"):
        if k in b:
            out[k] = bool(b[k])
    if "price_dt" in b:
        try:
            out["price_dt"] = None if b["price_dt"] in (None, "") else float(b["price_dt"])
        except (TypeError, ValueError):
            err.append("price_dt : nombre")
    if err:
        raise HTTPException(422, "Champs invalides : " + " ; ".join(err))
    return out


@app.put("/wardrobe/items/{item_id}")
def edit_item(item_id: str, body: dict):
    """Correction d'une fiche par l'utilisateur (source = user_corrected, comme apply_correction de l'Obj1)."""
    patch = _check_patch(body)
    with _write_lock:
        d, items = _load_catalog_file()
        card = next((c for c in items if c.get("id") == item_id), None)
        if card is None:
            raise HTTPException(404, f"article inconnu : {item_id}")
        card.update(patch)
        card["source"] = "user_corrected"
        conf = card.get("confidence") or {}   # comme apply_correction (Obj1) : confiance 1.0 sur les champs corrigés ;
        for k in conf:                         # patch vide (« Confirmer ») = tous les attributs confirmés
            if not patch or k in patch:
                conf[k] = 1.0
        _save_catalog_file(d)
        own = _store_file(f"items/{item_id}.json")
        if own is not None and own.exists():
            own.write_text(json.dumps(card, indent=2, ensure_ascii=False), encoding="utf-8")
    return to_front_item(card)


@app.delete("/wardrobe/items/{item_id}")
def delete_item(item_id: str):
    """Retire la pièce du catalogue et supprime ses fichiers (photo, crop, embedding, fiche)."""
    with _write_lock:
        d, items = _load_catalog_file()
        card = next((c for c in items if c.get("id") == item_id), None)
        if card is None:
            raise HTTPException(404, f"article inconnu : {item_id}")
        items.remove(card)
        _save_catalog_file(d)
        for rel in {card.get("image"), card.get("image_crop"), card.get("embedding"), f"items/{item_id}.json"}:
            f = _store_file(rel)
            if f is not None and f.is_file():
                f.unlink()
    return {"deleted": item_id, "items": len(items)}


@app.post("/wardrobe/items")
def add_item(image: UploadFile = File(...)):
    svc = recognizer()
    data = image.file.read()
    suffix = Path(image.filename or "photo.jpg").suffix.lower() or ".jpg"
    with _write_lock, tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / f"photo{suffix}"
        raw.write_bytes(data)
        item_id = _next_id()
        src, kw = raw, {}
        cropper = getattr(svc, "cropper", None)
        if cropper is not None:  # vrai service : une seule pièce par photo (la plus grande)
            try:
                piece = cropper.crop(raw, strategy="main")[0]
            except Exception as e:  # modèle de segmentation indisponible : photo entière, signalée
                print(f"[obj1] découpe impossible ({type(e).__name__}) : photo entière.", file=sys.stderr)
                piece = cropper.crop(raw, mode="none")[0]
                piece.quality = {"ok": False, "reasons": ["crop_unavailable"]}
            src = Path(tmp) / "piece.png"
            piece.image.save(src)
            kw = dict(crop_reasons=(piece.quality or {}).get("reasons"), slot_hint=piece.slot_hint)
        try:
            r = svc.recognize(src, item_id=item_id, raw_path=str(raw), out_dir=STORE, **kw)
        except Exception as e:
            raise HTTPException(500, f"Reconnaissance (Obj1) en échec : {type(e).__name__}: {e}")
        if r.card is None:
            raise HTTPException(422, f"Aucune fiche produite ({r.status}) : {', '.join(r.reasons) or r.category}")
        card = r.card.model_dump()
        for rel in (card["image"], card["image_crop"]):  # le mock n'écrit pas les images
            if not (STORE / rel).exists():
                (STORE / rel).parent.mkdir(parents=True, exist_ok=True)
                from PIL import Image
                Image.open(io.BytesIO(data)).convert("RGB").save(STORE / rel)
        _append_to_catalog(card)
    return {**to_front_item(card), "status": r.status, "reasons": r.reasons}


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


FRONT_SLOT = {  # slots / catégories Polyvore de l'Obj4 -> Slot du front
    "top": "top", "tops": "top", "bottom": "bottom", "bottoms": "bottom", "onepiece": "onepiece", "all-body": "onepiece",
    "outer": "outer", "outerwear": "outer", "footwear": "footwear", "shoes": "footwear", "bag": "bag", "bags": "bag",
    "accessory": "accessory", "accessories": "accessory", "hats": "accessory", "jewellery": "accessory",
    "scarves": "accessory", "sunglasses": "accessory",
}


@app.get("/gaps")
def gaps():
    if not GAPS.exists():
        raise HTTPException(503, f"rapport de manques introuvable : {GAPS}")
    d = json.load(open(GAPS, encoding="utf-8"))
    d = d if isinstance(d, list) else d.get("gaps", [])
    for i, g in enumerate(d):
        g.setdefault("rank", i + 1)
        s = FRONT_SLOT.get(str(g.get("slot") or g.get("category") or "").lower(), "accessory")
        g["slot"] = g["category"] = s
    return d


AXIS = {"efficacite": "efficiency", "economie": "economy", "image": "brand", "mixte": "mixte"}
_prefs = {"axis": None, "budgetMode": False}


OBJ5_REF_MODEL = REPO / "obj5_profil" / "models" / "style_model.joblib"   # modèle de référence versionné (423 fiches, attributs)


def _profile_service():
    """Service Obj5 entraîné sur la garde-robe ; None si elle est trop petite (moins de 18 pièces vectorisées)."""
    if "p" not in _cache:
        from dressme_profile import ProfileService
        try:
            _cache["p"] = ProfileService(catalog_path=STORE / "wardrobe.json", assets_dir=STORE)
        except ValueError as e:
            print(f"[obj5] {e} -> modèle de référence.", file=sys.stderr)
            _cache["p"] = None
    return _cache["p"]


def _obj5_profile(ids):
    """Profil Obj5 : modèle entraîné sur la garde-robe, sinon modèle de référence en lecture seule (petite garde-robe)."""
    from dressme_profile import ProfileRequest
    svc = _profile_service()
    if svc is not None:
        return svc.profile(ProfileRequest(user_id="me", item_ids=ids)).model_dump(), "garde-robe"
    from dressme_profile.clustering import StyleModel
    from dressme_profile.profile import build_profile
    from dressme_profile.service import load_items
    try:
        if "pref" not in _cache:
            _cache["pref"] = StyleModel.load(OBJ5_REF_MODEL)
        items = [i for i in load_items(STORE / "wardrobe.json") if i.id in set(ids)]
        return build_profile(items, _cache["pref"], "me", None).model_dump(), "référence"
    except Exception as e:
        raise HTTPException(503, f"Profil de style (Obj5) indisponible : {type(e).__name__}: {e}")


@app.get("/profile")
def get_profile():
    ids = [c["id"] for c in catalog()]
    p, model = _obj5_profile(ids)
    s = p["scores"]
    pct = lambda v: None if v is None else round(100 * v)
    return {"axis": _prefs["axis"] or AXIS.get(p["persona"], "mixte"), "budgetMode": _prefs["budgetMode"],
            "scores": {"efficacite": pct(s["efficacite"]), "economie": pct(s["economie"]), "image": pct(s["image"])},
            "diversityScore": pct(p["diversity"]), "formalityPref": p["formality_pref"],
            "dominantCluster": (p.get("dominant_cluster") or {}).get("name"),
            "palette": [{"color": e["colour"], "weight": e["weight"]} for e in p["palette"]],
            "model": model}   # "garde-robe" (entraîné sur vos pièces) ou "référence" (moins de 18 pièces)


@app.put("/profile")
def put_profile(body: dict):
    _prefs["axis"] = body.get("axis") or _prefs["axis"]
    _prefs["budgetMode"] = bool(body.get("budgetMode", _prefs["budgetMode"]))
    return get_profile()


# ---------------------------------------------------------------- objectif 6 : tenue du jour
OCC_OBJ6 = {"work": "work", "casual": "casual", "evening": "party"}            # Occasion du front -> Obj6
OCC_OBJ3 = {"work": "travail", "casual": "décontracté", "evening": "soirée"}    # Occasion du front -> Obj3
CAT_OBJ3 = {"top": "haut", "bottom": "bas", "onepiece": "robe", "outer": "veste", "footwear": "chaussures",
            "bag": "sac", "accessory": "accessoire"}
FORM_OBJ3 = {0: 1, 1: 2, 2: 3, 3: 5}   # formalité ItemCard 0-3 -> Obj3 1-5 (1 sport, 3 smart casual, 5 cérémonie)


def to_obj6_item(c):
    col = (c.get("colour") or ["black"])[0]
    return {"id": c["id"], "name": c.get("name") or c.get("type") or c["id"], "slot": "accessory" if c["slot"] == "bag" else c["slot"],
            "colour": col, "usage": c.get("usage") or "Casual", "warmth": float(c.get("warmth") or 1),
            "formality": int(c.get("formality") if c.get("formality") is not None else 1), "waterproof": bool(c.get("waterproof")),
            "open_toe": bool(c.get("open_toe")), "type": c.get("type"), "gender": c.get("gender") or "Unisex"}


def to_obj3_piece(c):
    col = (c.get("colour") or ["multi"])[0]
    return {"categorie": CAT_OBJ3[c["slot"]], "type": (c.get("type") or c["slot"]).lower(),
            "couleur": "Multi" if col.startswith("multi") else col.title(),
            "formalite": FORM_OBJ3.get(c.get("formality"), 2), "chaleur": min(5, int(c.get("warmth") or 0) + 1),
            "motif": "uni" if (c.get("pattern") or "plain") == "plain" else "imprimé"}


def obj6_recommend(payload):
    """Appel HTTP à l'objectif 6. Service absent ou en erreur -> 501 (Obj6 non lançable)."""
    import httpx
    try:
        r = httpx.post(f"{OBJ6_URL}/api/recommend", json=payload, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        raise HTTPException(501, f"Objectif 6 non joignable sur {OBJ6_URL} ({type(e).__name__}) : lancer obj6_app (voir run_all.bat).")


def jury():
    if "j" not in _cache:
        if str(OBJ3) not in sys.path:
            sys.path.append(str(OBJ3))
        from dressme.service import DressMeService
        _cache["j"] = DressMeService({c["id"]: to_obj3_piece(c) for c in catalog()}, llm=None)   # règles seules
    return _cache["j"]


def outfit_compat01(cards):
    """Moyenne des scores /pairs de l'Obj2 sur les paires de la tenue (None si des embeddings manquent)."""
    W = [c for c in cards if c.get("embedding") and (STORE / c["embedding"]).exists()]
    if len(W) < 2 or len(W) < len(cards):
        return None
    M = np.array(engine().pairs([{"id": c["id"], "slot": c["slot"], "embedding": c["embedding"]} for c in W],
                                [{"id": c["id"], "slot": c["slot"], "embedding": c["embedding"]} for c in W]))
    iu = np.triu_indices(len(W), 1)
    return round(float(M[iu].mean()), 2)


@app.get("/outfits/today")
def outfit_today(occasion: str = "casual", budget: bool = False, city: str = "Tunis", k: int = 5):
    if occasion not in OCC_OBJ6:
        raise HTTPException(422, f"occasion inconnue : {occasion} (attendu : {list(OCC_OBJ6)})")
    by_id = {c["id"]: c for c in catalog()}
    res = obj6_recommend({"wardrobe": [to_obj6_item(c) for c in by_id.values()], "occasion": OCC_OBJ6[occasion],
                          "city": city, "k": max(1, min(k, 10))})
    ctx = res.get("context", {})
    if not res.get("outfits"):
        raise HTTPException(404, res.get("message") or "Aucune tenue proposée par l'objectif 6.")
    temp, rain = float(ctx.get("feels_like", 20)), float(ctx.get("rain_prob", 0))
    best = None
    for o in res["outfits"]:   # chaque candidat de l'Obj6 passe par le jury (Obj3) et la compatibilité (Obj2)
        ids = [i["id"] for i in o["items"]] + [a["id"] for a in o.get("accessories", [])]
        cards = [by_id[i] for i in ids if i in by_id]
        j = jury().judge([c["id"] for c in cards], temp, rain > .5, OCC_OBJ3[occasion], mode="regles", repair=False)
        c01 = outfit_compat01([by_id[i["id"]] for i in o["items"] if i["id"] in by_id])
        key = (j["niveau"], c01 if c01 is not None else -1, o["score"])
        if best is None or key > best[0]:
            best = (key, o, cards, j, c01)
    _, o, cards, j, c01 = best
    reasons = list(o.get("reasons") or []) + [f"Jury (Obj3) : {j['verdict']}."]
    warns = list(o.get("warnings") or []) + [f"{k} : {v['raison']}" for k, v in j["criteres"].items() if v["niveau"] < 2]
    if c01 is None:
        warns.append("Compatibilité (Obj2) non calculée : embeddings manquants dans le catalogue.")
    if budget:
        warns.append("Mode budget : pas encore pris en compte par l'objectif 6.")
    return {"id": "-".join(c["id"] for c in cards), "items": [to_front_item(c) for c in cards], "compat01": c01,
            "reason": " · ".join(reasons), "weather": {"temperatureC": round(temp), "label": f"{city}, pluie {rain:.0%} ({ctx.get('weather_source', '?')})"},
            "agenda": ctx.get("occasion"), "warnings": warns}


# ---------------------------------------------------------------- objectif 3 : jury d'une tenue composée (Outfit Studio)
JURY_VERDICT = {0: "deconseille", 1: "a_ameliorer", 2: "convient"}   # niveau Obj3 -> JuryVerdict du front
JURY_STATUS = {0: "fail", 1: "warn", 2: "pass"}
JURY_SCORE = 50                                                       # score = niveau x 50 : l'Obj3 ne note pas plus finement
NON_DISPONIBLE = "non disponible"


class JudgeRequest(BaseModel):
    item_ids: list[str]
    occasion: str
    temperatureC: Optional[float] = None
    rain: bool = False


def jury_compat(cards):
    """Compatibilité Obj2 de la tenue : {score01, message}, sans score01 si elle n'est pas calculable."""
    try:
        c01 = outfit_compat01(cards)
    except Exception as e:
        return {"message": f"Compatibilité (Obj2) {NON_DISPONIBLE} ({type(e).__name__})."}
    if c01 is None:
        return {"message": f"Compatibilité (Obj2) {NON_DISPONIBLE} : moins de 2 pièces ou embeddings manquants."}
    return {"score01": c01, "message": "Moyenne des paires de la tenue (Obj2 /pairs, centile parmi 300 références)."}


def jury_repair(r, by_id):
    return {"problemItemId": r["retirer"], "reason": r["explication"],
            "suggestedReplacements": [to_front_item(by_id[r["ajouter"]])] if r["ajouter"] else []}


@app.post("/outfits/judge")
def outfit_judge(body: JudgeRequest):
    if body.occasion not in OCC_OBJ3:
        raise HTTPException(422, f"occasion inconnue : {body.occasion} (attendu : {list(OCC_OBJ3)})")
    ids = list(dict.fromkeys(body.item_ids))
    try:
        j = jury().judge(ids, body.temperatureC, body.rain, OCC_OBJ3[body.occasion], mode="regles")
    except ValueError as e:   # tenue vide ou identifiant inconnu
        raise HTTPException(422, str(e))
    by_id = {c["id"]: c for c in catalog()}
    crit, niveau = j["criteres"], j["niveau"]
    bad = [f"{k} : {v['raison']}" for k, v in crit.items() if v["niveau"] < 2]
    return {"score": niveau * JURY_SCORE, "verdict": JURY_VERDICT[niveau], "verdictLabel": j["verdict"].capitalize(),
            "rationale": f"{' · '.join(j['raisons'])} (Score = niveau {niveau}/2 du jury Obj3, règles seules.)",
            "judges": {
                "rules": {"status": JURY_STATUS[min(v["niveau"] for v in crit.values())],
                          "message": " · ".join(bad) or "Tous les critères sont satisfaisants."},
                "visual": {"score01": None, "status": "unavailable",
                           "message": f"Juge visuel {NON_DISPONIBLE} : la passerelle lance l'Obj3 en règles seules."},
                "llm": {"verdict": NON_DISPONIBLE, "critique": f"Juge LLM {NON_DISPONIBLE} : la passerelle lance l'Obj3 sans LLM."},
                "context": {"matchWeather": None if body.temperatureC is None else crit["meteo"]["niveau"] == 2,
                            "matchOccasion": crit["formalite"]["niveau"] == 2,
                            "message": f"{crit['meteo']['raison']} · {crit['formalite']['raison']}"},
                "compatibility": jury_compat([by_id[i] for i in ids])},
            "repairs": [jury_repair(r, by_id) for r in j["reparations"]]}
