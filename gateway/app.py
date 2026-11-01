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


def _load_env_file(path):
    """gateway/.env (ignoré par git) : KEY=VALUE, sans écraser les variables déjà définies (ex. clés LLM du jury Obj3)."""
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            k, sep, v = line.strip().partition("=")
            if sep and k and not k.startswith("#"):
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env_file(Path(__file__).resolve().parent / ".env")
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
            log(f"catalogue introuvable : {p} (variable DRESSME_STORE)")
            raise HTTPException(503, "La garde-robe est introuvable sur le serveur.")
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
CAT_USER = {"tops": "un haut", "bottoms": "un bas", "all-body": "une robe", "outerwear": "une veste", "shoes": "des chaussures",
            "bags": "un sac", "accessories": "un accessoire", "hats": "un chapeau", "jewellery": "un bijou", "scarves": "une écharpe",
            "sunglasses": "des lunettes de soleil"}
CRIT_USER = {"couleurs": "Couleurs", "formalite": "Style", "meteo": "Météo", "coherence": "Ensemble"}
OCC_USER = {"casual": "décontractée", "work": "travail", "party": "soirée", "formal": "formelle", "sport": "sport",
            "wedding": "mariage", "religious": "religieuse"}


def log(msg):
    """Détail technique pour les développeurs (console du serveur), jamais affiché à l'utilisateur."""
    print(f"[passerelle] {msg}", file=sys.stderr)


def crit_text(entries):
    """« formalite : raison » (Obj3) -> « Style : raison »."""
    out = []
    for e in entries:
        k, sep, txt = e.partition(" : ")
        out.append(f"{CRIT_USER.get(k, k)} : {txt}" if sep and k in CRIT_USER else e)
    return out


def compat_for(vec, category, wardrobe, name="candidate"):
    cand = {"id": name, "category": category, "embedding": vec.tolist()}
    W = [{"id": c["id"], "slot": c["slot"], "embedding": c["embedding"]} for c in wardrobe]
    r = engine().compat(cand, W)
    if "error" in r:
        raise HTTPException(422, r["error"])
    return {"score": r["rank100"], "score01": r["score01"], "verdict": VERDICT.get(r["verdict"], r["verdict"]),
            "newOutfits": 0, "partners": [{"id": p["id"], "pair_score01": p["pair_score01"]} for p in r["partners"]],
            "duplicate": r["duplicate"], "clashingItems": [],
            "notes": [f"Pièce reconnue comme {CAT_USER.get(category, 'un vêtement')}."]}


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
        log(f"Objectif 1 non lançable ({err})")
        raise HTTPException(501, "L'analyse automatique des photos n'est pas disponible pour le moment.")
    return svc


class GeminiVisionLLM:
    """Remplace Qwen2.5-VL (GPU) dans l'agent de l'Obj1 : même interface generate(image, prompt, system) -> texte JSON.
    Modèles Gemini essayés dans l'ordre (quota gratuit par modèle)."""

    def __init__(self, key, models):
        from openai import OpenAI
        self.client = OpenAI(api_key=key, base_url="https://generativelanguage.googleapis.com/v1beta/openai/", max_retries=3)
        self.models = models

    def generate(self, image, prompt, system=None):
        import base64
        if system is None:
            from recognition.prompts import SYSTEM as system
        buf = io.BytesIO(); image.convert("RGB").save(buf, "JPEG", quality=90)
        url = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": url}}]}]
        last = None
        for m in self.models:
            try:
                r = self.client.chat.completions.create(model=m, messages=msgs, response_format={"type": "json_object"})
                return r.choices[0].message.content or ""
            except Exception as e:   # quota du modèle, modèle indisponible : modèle suivant
                last = e
        raise last


def _obj1_local_knn():
    """Obj1 sans Kaggle ni GPU : crop (SegFormer / rembg) -> FashionCLIP gelé -> base de voisins locale data/agent_final
    (kb_meta.csv + kb_emb.npy) -> ItemCard v1. Avec GEMINI_API_KEY, l'agent tourne en mode complet (Gemini voit la photo,
    contrôle par les voisins, RAG) au lieu du seul vote des voisins. Même encodeur que la passerelle."""
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
    key = os.environ.get("GEMINI_API_KEY", "")
    vlm, cache = None, None
    if key and os.environ.get("DRESSME_OBJ1_VLM", "gemini") == "gemini":
        from recognition.llm import JsonlCache
        models = [m.strip() for m in os.environ.get("GEMINI_VISION_MODELS", GEMINI_VISION_MODELS).split(",") if m.strip()]
        vlm = GeminiVisionLLM(key, models)
        cache = JsonlCache(Path(os.environ.get("DRESSME_OBJ1_CACHE", CFG.out / "llm_calls_gemini.jsonl")))   # réponses déjà obtenues (fichier ignoré par git)
    log(f"Obj1 : {'mode complet avec Gemini (' + vlm.models[0] + ')' if vlm else 'vote des voisins seul (pas de GEMINI_API_KEY)'}")
    agent = RecognitionAgent(vlm, shared, Retriever(np.load(emb), pd.read_csv(meta)), CFG, cache)
    return RecognitionService(agent, shared, CFG, None, "full" if vlm else "knn_only", cropper=Cropper.from_config(CFG))


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
    for k in ("c", "p", "j", "jl"):  # catalogue relu ; profil Obj5 et jury Obj3 reconstruits (ils refusent les identifiants inconnus)
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
            raise HTTPException(404, "Cette pièce n'existe plus dans votre garde-robe.")
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
            raise HTTPException(404, "Cette pièce n'existe plus dans votre garde-robe.")
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
            log(f"Reconnaissance (Obj1) en échec : {type(e).__name__}: {e}")
            raise HTTPException(500, "L'analyse de la photo a échoué. Réessayez avec une autre photo.")
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
        log("moins de 2 articles avec embedding : lancer embed_cards.py (voir README)")
        raise HTTPException(503, "Pas encore assez de pièces analysées dans votre garde-robe pour comparer (2 au minimum).")
    W = W[:int(os.environ.get("MAX_WARDROBE", "40"))]   # le calcul croît avec le carré de la taille de la garde-robe
    data = await image.read()
    try:
        vec, guessed = embed_photo(data)
    except ImportError as e:
        log(f"torch/transformers manquants : {e}")
        raise HTTPException(503, "La comparaison n'est pas disponible pour le moment.")
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
        log(f"rapport de manques introuvable : {GAPS}")
        raise HTTPException(503, "L'analyse des pièces manquantes n'est pas encore disponible.")
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
        log(f"Profil de style (Obj5) indisponible : {type(e).__name__}: {e}")
        raise HTTPException(503, "Votre profil de style n'est pas encore disponible.")


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
OCC_OBJ6 = {"work": "work", "casual": "casual", "evening": "party", "sport": "sport", "ceremony": "wedding"}   # front -> Obj6
OCC_OBJ3 = {"work": "travail", "casual": "décontracté", "evening": "soirée", "sport": "sport", "ceremony": "cérémonie"}   # front -> Obj3
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


OBJ6_UID = "me"   # utilisateur unique de la démo : préférences et rotation mémorisées par l'Obj6 (feedback.db)


def _obj6_post(route, payload):
    """Appel HTTP à l'objectif 6. Service absent -> 501 ; requête refusée par l'Obj6 -> même code et son détail."""
    import httpx
    try:
        r = httpx.post(f"{OBJ6_URL}{route}", json=payload, timeout=60)
    except Exception as e:
        log(f"Objectif 6 non joignable sur {OBJ6_URL} ({type(e).__name__}) : lancer obj6_app (voir run_all.bat)")
        raise HTTPException(501, "Le service de tenue du jour ne répond pas. Réessayez dans un instant.")
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail")
        except Exception:
            detail = r.text[:200]
        log(f"Objectif 6 {route} : {r.status_code} {detail}")
        raise HTTPException(r.status_code if r.status_code < 500 else 502,
                            detail if r.status_code < 500 and isinstance(detail, str) else "Le service de tenue du jour a rencontré un problème.")
    return r.json()


def obj6_recommend(payload):
    return _obj6_post("/api/recommend", payload)


def obj6_parse(text):
    """Lecture de l'agenda par l'agent de l'Obj6 ; renvoie l'agent utilisé (« rules », « llm », « llm+rag ») ou None."""
    import httpx
    try:
        r = httpx.get(f"{OBJ6_URL}/api/parse", params={"text": text}, timeout=60)
    except Exception as e:
        log(f"Objectif 6 non joignable sur {OBJ6_URL} ({type(e).__name__})")
        raise HTTPException(501, "Le service de tenue du jour ne répond pas. Réessayez dans un instant.")
    return r.json().get("source") if r.status_code == 200 else None


def jury():
    if "j" not in _cache:
        if str(OBJ3) not in sys.path:
            sys.path.append(str(OBJ3))
        from dressme.service import DressMeService
        _cache["j"] = DressMeService({c["id"]: to_obj3_piece(c) for c in catalog()}, llm=None)   # règles seules
    return _cache["j"]


GEMINI_VISION_MODELS = "gemini-3.5-flash-lite,gemini-3.5-flash"   # modèles Gemini existants (la liste par défaut de l'Obj3 cite un modèle retiré)


def vision_llm():
    """Client vision de l'Obj3 (Gemini, voit les images) si DRESSME_JURY_LLM=1 et GEMINI_API_KEY ; None sinon."""
    key = os.environ.get("GEMINI_API_KEY", "")
    if os.environ.get("DRESSME_JURY_LLM") != "1" or not key:
        return None
    if "vl" not in _cache:
        jury()   # chemin de l'Obj3
        from dressme.llm2 import GEMINI_URL, FallbackLLM, OpenAICompatClient2
        models = [m.strip() for m in os.environ.get("GEMINI_VISION_MODELS", GEMINI_VISION_MODELS).split(",") if m.strip()]
        _cache["vl"] = FallbackLLM([OpenAICompatClient2(key, m, GEMINI_URL, vision=True, cache_dir=str(OBJ3 / "app_data" / "llm_cache"),
                                                        name=m) for m in models])
    return _cache["vl"]


def outfit_board(cards, legend):
    """Planche attendue par le juge vision de l'Obj3 : légende en haut, puis les pièces de gauche à droite (découpes)."""
    from PIL import Image, ImageDraw, ImageFont
    tiles = []
    for c in cards:
        f = next((x for x in (_store_file(c.get("image_crop")), _store_file(c.get("image"))) if x is not None and x.is_file()), None)
        if f is None:
            continue
        im = Image.open(f).convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
        im = bg.convert("RGB"); im.thumbnail((320, 320)); tiles.append(im)
    if not tiles:
        return None
    pad, top = 20, 60
    board = Image.new("RGB", (pad + sum(t.width + pad for t in tiles), top + 320 + pad), "white")
    d = ImageDraw.Draw(board)
    font = None
    for name in ("arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):   # polices avec accents (Windows, Linux)
        try:
            font = ImageFont.truetype(name, 22); break
        except OSError:
            pass
    if font is None:   # police intégrée sans accents : légende translittérée
        import unicodedata
        legend = unicodedata.normalize("NFKD", legend).encode("ascii", "ignore").decode()
        try:
            font = ImageFont.load_default(size=22)
        except TypeError:   # Pillow < 10.1
            font = ImageFont.load_default()
    d.text((pad, 18), legend, fill="black", font=font)
    x = pad
    for t in tiles:
        board.paste(t, (x, top + (320 - t.height) // 2)); x += t.width + pad
    return board


def judge_visual(cards, temperature, rain, occasion):
    """Juge visuel de l'Obj3 (judge_vision_v3) sur la planche de la tenue. Informatif : n'entre pas dans le vote de l'arbitre."""
    llm = vision_llm()
    if llm is None:
        log("juge visuel : DRESSME_JURY_LLM=1 et GEMINI_API_KEY requis (gateway/.env)")
        return {"score01": None, "status": "unavailable", "message": "Analyse des photos non activée."}
    from dressme.context import make_context
    from dressme.judges2 import judge_vision_v3
    t = "météo non précisée" if temperature is None else f"{temperature:g} °C{', pluie' if rain else ''}"
    board = outfit_board(cards, f"Tenue 1 - {t} - occasion : {occasion}")
    if board is None:
        return {"score01": None, "status": "unavailable", "message": "Pas de photo pour ces pièces."}
    try:
        v = judge_vision_v3(llm, board, make_context(temperature, rain, occasion))
    except Exception as e:   # quota Gemini, réseau, réponse illisible
        log(f"juge visuel : {type(e).__name__} : {str(e)[:200]}")
        return {"score01": None, "status": "unavailable", "message": "Analyse des photos momentanément indisponible."}
    lv = {k: c["niveau"] for k, c in v["criteres"].items()}
    notes = [f"{k} : {c['raison']}" for k, c in v["criteres"].items() if c["niveau"] < 2]
    return {"score01": round(sum(lv.values()) / (2 * len(lv)), 2), "status": JURY_STATUS[min(lv.values())],   # une réserve visible = « Réserves »
            "message": ("Sur les photos : " + " · ".join(crit_text(notes))) if notes else "Rien à signaler sur les photos."}


def jury_llm():
    """Jury Obj3 complet (règles + LLM + hybride) si DRESSME_JURY_LLM=1 et une clé GEMINI_API_KEY ou LLM_API_KEY (Groq) ;
    None sinon (règles seules). Réservé à Outfit Studio : Today juge plusieurs tenues par appel (latence, quota 40/h)."""
    if os.environ.get("DRESSME_JURY_LLM") != "1":
        return None
    if "jl" not in _cache:
        jury()   # chemin de l'Obj3
        from dressme.service import DressMeService, build_llm
        os.environ.setdefault("GEMINI_MODELS", GEMINI_VISION_MODELS)   # la liste par défaut de l'Obj3 cite un modèle Gemini retiré
        llm = build_llm(str(OBJ3 / "app_data" / "llm_cache"))   # cache des réponses (app_data/ ignoré par git)
        _cache["jl"] = DressMeService({c["id"]: to_obj3_piece(c) for c in catalog()}, llm=llm) if llm else None
        if llm is None:
            print("[obj3] DRESSME_JURY_LLM=1 mais aucune clé GEMINI_API_KEY / LLM_API_KEY : règles seules.", file=sys.stderr)
    return _cache["jl"]


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
def outfit_today(occasion: str = "casual", budget: bool = False, city: str = "Tunis", k: int = 5,
                 agenda: Optional[str] = None, exclude: Optional[str] = None):
    """agenda : texte libre transmis à l'Obj6 ; exclude : tenues déjà refusées, "id1,id2;id3,id4" (« Autre proposition »)."""
    if occasion not in OCC_OBJ6:
        raise HTTPException(422, f"occasion inconnue : {occasion} (attendu : {list(OCC_OBJ6)})")
    by_id = {c["id"]: c for c in catalog()}
    excl = [[i for i in grp.split(",") if i] for grp in (exclude or "").split(";") if grp.strip()]
    # deux pièces identiques (même nom, type, couleurs) donnent la même tenue à l'écran : « Autre proposition »
    # écarte donc aussi les tenues de même aspect, et demande plus de candidats à l'Obj6 pour en garder assez
    look = lambda i: (str(by_id[i].get("name")).lower(), by_id[i].get("type"), tuple(by_id[i].get("colour") or []))
    excl_looks = {frozenset(look(i) for i in grp if i in by_id) for grp in excl}
    payload = {"wardrobe": [to_obj6_item(c) for c in by_id.values()], "occasion": OCC_OBJ6[occasion],
               "city": city, "k": 10, "uid": OBJ6_UID, "exclude_outfits": excl}   # k = 10 : assez de candidats une fois les doublons écartés
    if agenda and agenda.strip():
        payload["agenda"] = agenda.strip()[:300]
    res = obj6_recommend(payload)
    ctx = res.get("context", {})
    if excl_looks:
        res["outfits"] = [o for o in res.get("outfits") or []
                          if frozenset(look(i["id"]) for i in o["items"] if i["id"] in by_id) not in excl_looks]
        if not res["outfits"]:
            raise HTTPException(404, "Plus d'autre tenue différente avec votre garde-robe : réinitialisez les tenues écartées.")
    if not res.get("outfits"):
        raise HTTPException(404, res.get("message") or "Aucune tenue trouvée pour aujourd'hui avec votre garde-robe.")
    temp, rain = float(ctx.get("feels_like", 20)), float(ctx.get("rain_prob", 0))
    # Chaque candidat de l'Obj6 (classé selon la météo et l'occasion) passe par le jury (Obj3) et la compatibilité (Obj2).
    # Ordre de choix : verdict du jury, puis nombre de réserves, puis le score de contexte de l'Obj6 ; la compatibilité
    # ne départage que des scores quasi égaux (sinon la même paire « qui va bien » gagnerait quel que soit le contexte).
    best, seen_looks = None, set()
    for o in res["outfits"]:
        ids = [i["id"] for i in o["items"]] + [a["id"] for a in o.get("accessories", [])]
        cards = [by_id[i] for i in ids if i in by_id]
        sig = frozenset(look(i["id"]) for i in o["items"] if i["id"] in by_id)
        if not cards or sig in seen_looks:   # tenue identique à l'écran (pièces jumelles) : déjà évaluée
            continue
        seen_looks.add(sig)
        j = jury().judge([c["id"] for c in cards], temp, rain > .5, OCC_OBJ3[occasion], mode="regles", repair=False)
        c01 = outfit_compat01([by_id[i["id"]] for i in o["items"] if i["id"] in by_id])
        reserves = sum(v["niveau"] < 2 for v in j["criteres"].values())
        key = (j["niveau"], -reserves, round(float(o["score"]), 2), c01 or 0)   # compatibilité : départage seulement
        if best is None or key > best[0]:
            best = (key, o, cards, j, c01)
    _, o, cards, j, c01 = best
    def occ_fr(txt):   # « casual » (Obj6) -> « décontractée »
        for k, v in OCC_USER.items():
            txt = txt.replace(f"« {k} »", f"« {v} »")
        return txt
    reasons = [occ_fr(r) for r in (o.get("reasons") or [])]
    reasons.append("Validée par le jury de style." if j["niveau"] == 2 else "Le jury de style émet des réserves.")
    warns = list(o.get("warnings") or []) + crit_text(f"{k} : {v['raison']}" for k, v in j["criteres"].items() if v["niveau"] < 2)
    if budget:
        warns.append("Le mode budget n'est pas encore pris en compte.")
    src = str(ctx.get("weather_source", ""))
    wlabel = f"{city} · pluie {rain:.0%}" if not src.startswith("default") else f"{city} · météo indisponible (température estimée)"
    return {"id": "-".join(c["id"] for c in cards), "items": [to_front_item(c) for c in cards], "compat01": c01,
            "reason": " · ".join(reasons), "weather": {"temperatureC": round(temp), "label": wlabel},
            "agenda": agenda or ctx.get("occasion"), "warnings": warns,
            "features": o.get("features") or {}, "excludeKey": [i["id"] for i in o["items"]],   # pour le feedback / « Autre proposition »
            "excludedCount": len(excl)}


FEEDBACK_REASONS = {"too_hot", "too_cold", "too_formal", "too_casual", "style"}

# ---------------------------------------------------------------- objectif 6 : écran complet « tenue du jour »
OBJ6_CITIES = ["Tunis", "Sfax", "Sousse", "Bizerte", "Nabeul", "Djerba"]
OCC6_OBJ3 = {"casual": "décontracté", "work": "travail", "formal": "travail", "sport": "sport", "wedding": "cérémonie",
             "religious": "travail", "party": "soirée"}   # occasion déduite par l'Obj6 -> occasion du jury (Obj3)
AGENT_USER = {"rules": "mots-clés", "llm": "IA", "llm+rag": "IA + fiches locales"}


def _for_gender(cards, gender):
    """Pièces portables pour le genre choisi : celles de ce genre et les pièces mixtes (ou sans genre)."""
    if gender not in ("Women", "Men"):
        return list(cards)
    return [c for c in cards if (c.get("gender") or "Unisex") in (gender, "Unisex")]


@app.get("/outfits/options")
def outfit_options(gender: Optional[str] = None):
    """Valeurs proposées pour les « envies » (couleurs principales et types présents dans la garde-robe) et villes."""
    cards = [c for c in _for_gender(catalog(), gender) if c["slot"] not in ("bag", "accessory")]
    return {"colours": sorted({(c.get("colour") or [""])[0] for c in cards} - {""}),
            "types": sorted({c.get("type") for c in cards if c.get("type")}), "cities": OBJ6_CITIES}


class RecommendIn(BaseModel):
    gender: Optional[str] = None
    city: str = "Tunis"
    agenda: Optional[str] = None
    colours: list[str] = []
    types: list[str] = []
    explain: bool = False
    k: int = 3
    exclude_outfits: list[list[str]] = []
    exclude_ids: list[str] = []


@app.post("/outfits/recommend")
def outfit_recommend(body: RecommendIn):
    """Écran « tenue du jour » complet : l'agent de l'Obj6 lit l'agenda (occasion, formalité), l'Obj6 propose des tenues
    selon la météo de la ville, le jury (Obj3) et l'accord des pièces (Obj2) les vérifient ; durée de chaque étape."""
    import time
    if body.city not in OBJ6_CITIES:
        raise HTTPException(422, f"Ville inconnue : choisissez parmi {', '.join(OBJ6_CITIES)}.")
    if body.gender not in (None, "Women", "Men"):
        raise HTTPException(422, "Genre : Femme ou Homme.")
    k = max(1, min(body.k, 5))
    agenda = (body.agenda or "").strip()[:300] or None
    steps = []

    def step(label, t0):
        steps.append({"label": label, "ms": round((time.perf_counter() - t0) * 1000)})

    by_id = {c["id"]: c for c in _for_gender(catalog(), body.gender)}
    if agenda:   # étape séparée et chronométrée ; l'Obj6 garde le résultat en cache pour la recommandation
        t0 = time.perf_counter()
        src = obj6_parse(agenda)
        step(f"Lecture de l'agenda ({AGENT_USER.get(src, 'mots-clés')})", t0)
    t0 = time.perf_counter()
    res = obj6_recommend({"wardrobe": [to_obj6_item(c) for c in by_id.values()], "city": body.city, "gender": body.gender,
                          "agenda": agenda, "colours": body.colours, "types": body.types, "explain": body.explain, "k": 10,
                          "uid": OBJ6_UID, "exclude_outfits": body.exclude_outfits, "exclude_ids": body.exclude_ids})
    step("Météo, création et classement des tenues" + (" + explications de la styliste IA" if body.explain else ""), t0)
    ctx = res.get("context", {})
    occ6 = ctx.get("occasion", "casual")
    temp, rain = float(ctx.get("feels_like", 20)), float(ctx.get("rain_prob", 0))

    warnings = []
    if ctx.get("agenda_error"):
        log(f"agent de l'agenda : {ctx['agenda_error']}")
        warnings.append("L'IA n'a pas pu lire votre agenda : il a été lu par mots-clés.")
    if ctx.get("prefs_relaxed"):
        warnings.append("Aucune tenue ne respecte toutes vos envies : elles ont été ignorées.")
    if str(ctx.get("weather_source", "")).startswith("default"):
        warnings.append("Météo indisponible : température estimée.")

    # doublons visuels (pièces jumelles) et tenues déjà écartées par l'utilisateur
    look = lambda i: (str(by_id[i].get("name")).lower(), by_id[i].get("type"), tuple(by_id[i].get("colour") or []))
    excl_looks = {frozenset(look(i) for i in grp if i in by_id) for grp in body.exclude_outfits}
    cands, seen = [], set()
    for o in res.get("outfits") or []:
        sig = frozenset(look(i["id"]) for i in o["items"] if i["id"] in by_id)
        if sig and sig not in seen and sig not in excl_looks:
            seen.add(sig); cands.append(o)

    t_jury = t_compat = 0.0
    scored = []
    for o in cands:
        ids = [i["id"] for i in o["items"]] + [a["id"] for a in o.get("accessories", [])]
        cards = [by_id[i] for i in ids if i in by_id]
        t0 = time.perf_counter()
        j = jury().judge([c["id"] for c in cards], temp, rain > .5, OCC6_OBJ3.get(occ6, "décontracté"), mode="regles", repair=False)
        t_jury += time.perf_counter() - t0
        t0 = time.perf_counter()
        c01 = outfit_compat01([by_id[i["id"]] for i in o["items"] if i["id"] in by_id])
        t_compat += time.perf_counter() - t0
        reserves = sum(v["niveau"] < 2 for v in j["criteres"].values())
        scored.append(((j["niveau"], -reserves, round(float(o["score"]), 2), c01 or 0), o, j, c01))
    steps.append({"label": f"Vérification par le jury de style ({len(scored)} tenue{'s' if len(scored) > 1 else ''})", "ms": round(t_jury * 1000)})
    steps.append({"label": "Accord entre les pièces", "ms": round(t_compat * 1000)})
    scored.sort(key=lambda x: x[0], reverse=True)

    def occ_fr(txt):
        for key, val in OCC_USER.items():
            txt = txt.replace(f"« {key} »", f"« {val} »")
        return txt

    outfits = []
    for _, o, j, c01 in scored[:k]:
        alerts = list(o.get("warnings") or []) + crit_text(f"{key} : {v['raison']}" for key, v in j["criteres"].items() if v["niveau"] < 2)
        outfits.append({
            "id": "-".join(i["id"] for i in o["items"]),
            "items": [to_front_item(by_id[i["id"]]) for i in o["items"] if i["id"] in by_id],
            "accessories": [to_front_item(by_id[a["id"]]) for a in o.get("accessories", []) if a["id"] in by_id],
            "score": round(float(o["score"]), 2), "compat01": c01,
            "jury": "Validée par le jury de style" if j["niveau"] == 2 and not alerts else
                    ("Convient, avec réserves" if j["niveau"] == 2 else "Le jury de style émet des réserves"),
            "reasons": [occ_fr(r) for r in o.get("reasons") or []], "explanation": o.get("explanation"),
            "alerts": list(dict.fromkeys(alerts)), "excludeKey": [i["id"] for i in o["items"]], "features": o.get("features") or {}})
    if body.explain and outfits and not any(x["explanation"] for x in outfits):
        warnings.append("Explications de la styliste IA indisponibles : les raisons calculées sont affichées.")
    if 0 < len(outfits) < k:
        warnings.append(f"Garde-robe insuffisante : {len(outfits)} tenue{'s' if len(outfits) > 1 else ''} différente"
                        f"{'s' if len(outfits) > 1 else ''} seulement (sur {k}). Ajoutez des pièces pour plus de choix.")
    message = None
    if not outfits:
        message = (res.get("message") if not res.get("outfits") else None) or \
                  "Plus d'autre tenue différente avec votre garde-robe : réinitialisez les tenues écartées."
    return {"context": {"city": body.city, "temperatureC": round(temp), "rainPct": round(rain * 100), "occasion": OCC_USER.get(occ6, occ6),
                        "formality": ctx.get("formality"), "agent": AGENT_USER.get(ctx.get("agenda_source")) if agenda else None,
                        "rag": ctx.get("retrieved") or [], "ramadan": bool(ctx.get("ramadan")), "eid": bool(ctx.get("eid")),
                        "notes": ctx.get("agenda_notes"), "pieces": len(by_id)},
            "warnings": warnings, "message": message, "steps": steps, "outfits": outfits}


class FeedbackIn(BaseModel):
    item_ids: list[str]
    accepted: bool
    features: dict = {}
    reason: Optional[str] = None


@app.post("/outfits/feedback")
def outfit_feedback(body: FeedbackIn):
    """« Valider & Porter » (accepted) ou refus motivé : mémorisé par l'Obj6 (préférences des pièces, rotation des tenues portées)."""
    if not body.item_ids:
        raise HTTPException(422, "item_ids vide")
    if body.reason is not None and body.reason not in FEEDBACK_REASONS:
        raise HTTPException(422, f"reason : {sorted(FEEDBACK_REASONS)}")
    feats = {k: float(v) for k, v in body.features.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    return _obj6_post("/api/feedback", {"features": feats, "accepted": body.accepted, "uid": OBJ6_UID,
                                        "reason": body.reason, "item_ids": body.item_ids})


# ---------------------------------------------------------------- objectif 3 : jury d'une tenue composée (Outfit Studio)
JURY_VERDICT = {0: "deconseille", 1: "a_ameliorer", 2: "convient"}   # niveau Obj3 -> JuryVerdict du front
JURY_STATUS = {0: "fail", 1: "warn", 2: "pass"}
JURY_BANDS = {0: (0, 39), 1: (40, 69), 2: (70, 100)}   # mêmes seuils que /compat : déconseillé < 40 <= à améliorer < 70 <= convient


def jury_score(niveau, crit):
    """Note 0-100 : la tranche vient du verdict de l'Obj3, la position dans la tranche de la part des 4 critères satisfaits."""
    lo, hi = JURY_BANDS[niveau]
    ok = sum(c["niveau"] == 2 for c in crit.values())
    return round(lo + (hi - lo) * ok / len(crit))
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
        log(f"compatibilité de la tenue : {type(e).__name__}")
        return {"message": "Pas encore calculable pour ces pièces."}
    if c01 is None:
        return {"message": "Pas encore calculable pour ces pièces."}
    return {"score01": c01, "message": "Accord visuel entre les pièces de la tenue."}


SLOT_FR = {"top": "un haut", "bottom": "un bas", "onepiece": "une robe", "outer": "une veste", "footwear": "des chaussures",
           "bag": "un sac", "accessory": "un accessoire"}


def jury_repairs(reps, by_id):
    """Réparations de l'Obj3 regroupées : une entrée par pièce à remplacer / retirer et par emplacement à compléter,
    remplaçants dédoublonnés (deux pièces identiques de la garde-robe ne sont proposées qu'une fois), textes en français."""
    name = lambda i: by_id[i].get("name") or by_id[i].get("type") or i
    look = lambda i: (str(by_id[i].get("name")).lower(), tuple(by_id[i].get("colour") or []), by_id[i].get("type"))
    groups = {}
    for r in reps:
        rid, add = r.get("retirer"), r.get("ajouter")
        if rid is not None and rid not in by_id or add is not None and add not in by_id:
            continue
        target = r.get("explication", "").rsplit("→", 1)[-1].strip(" .") or "convient"
        key = (rid, by_id[add]["slot"] if rid is None else None)
        g = groups.setdefault(key, {"rid": rid, "slot": key[1], "adds": [], "looks": set(), "target": target})
        if add is not None and look(add) not in g["looks"]:
            g["looks"].add(look(add)); g["adds"].append(add)
    out = []
    for g in groups.values():
        if g["rid"] is None:
            reason = f"Ajouter {SLOT_FR.get(g['slot'], 'une pièce')}"
        elif g["adds"]:
            reason = f"Remplacer « {name(g['rid'])} »"
        else:
            reason = f"Retirer « {name(g['rid'])} »"
        out.append({"problemItemId": g["rid"], "reason": f"{reason} → la tenue {g['target']}.",
                    "suggestedReplacements": [to_front_item(by_id[a]) for a in g["adds"]]})
    return out


@app.post("/outfits/judge")
def outfit_judge(body: JudgeRequest):
    if body.occasion not in OCC_OBJ3:
        raise HTTPException(422, f"occasion inconnue : {body.occasion} (attendu : {list(OCC_OBJ3)})")
    ids = list(dict.fromkeys(body.item_ids))
    svc = jury_llm()
    by_id = {c["id"]: c for c in catalog()}
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as pool:   # le juge visuel (Gemini) tourne pendant les autres juges
        vis = pool.submit(judge_visual, [by_id[i] for i in ids if i in by_id], body.temperatureC, body.rain, OCC_OBJ3[body.occasion])
        try:
            j = (svc or jury()).judge(ids, body.temperatureC, body.rain, OCC_OBJ3[body.occasion], mode="complet" if svc else "regles")
        except ValueError as e:   # tenue vide ou identifiant inconnu
            raise HTTPException(422, str(e))
        visual = vis.result()
    crit, niveau = j["criteres"], j["niveau"]
    votes, par_juge, notes = j.get("votes", {}), j.get("raisons_par_juge", {}), j.get("notes", [])
    complet = j.get("mode_utilise") == "complet"
    rules_lvl = min(v["par_juge"].get("regles", v["niveau"]) for v in crit.values())
    rules_msg = [r for r in par_juge.get("regles", []) if r != "Tous les critères sont satisfaisants."]
    if "llm" in votes or "hybride" in votes:   # avis du LLM (et du juge hybride règles + LLM)
        ia = {v for k, v in votes.items() if k in ("llm", "hybride")}
        llm = {"verdict": ia.pop() if len(ia) == 1 else "avis partagé",
               "critique": " · ".join(crit_text(par_juge.get("llm") or par_juge.get("hybride") or []))}
    else:
        log("avis IA : " + (" ".join(notes) or ("DRESSME_JURY_LLM=1 non activé" if os.environ.get("DRESSME_JURY_LLM") != "1"
                                                  else "aucune clé GEMINI_API_KEY / LLM_API_KEY")))
        llm = {"verdict": NON_DISPONIBLE, "critique": "Avis de l'IA non activé." if not notes else "Avis de l'IA momentanément indisponible."}
    reserves = [k for k, v in crit.items() if v["niveau"] < 2]
    label = j["verdict"].capitalize() + (", avec réserves" if niveau == 2 and reserves else "")
    # Description minimaliste : seules les raisons du juge règles (calculées sur les fiches) sont citées ;
    # un point relevé uniquement par le LLM est signalé sans recopier son texte, qui peut être inexact.
    rules_why = {}
    for r in par_juge.get("regles", []):
        k, sep, txt = r.partition(" : ")
        if sep and k in crit:
            rules_why[k] = txt.strip().rstrip(".")
    if not reserves:
        why = "Rien à revoir : couleurs, style, météo et ensemble conviennent."
    else:
        why = "À revoir : " + " · ".join(
            f"{CRIT_USER[k]} ({rules_why[k]})" if k in rules_why else f"{CRIT_USER[k]} (signalé par l'IA)" for k in reserves) + "."
    return {"score": jury_score(niveau, crit), "verdict": JURY_VERDICT[niveau], "verdictLabel": label,
            "rationale": why,
            "mode": "complet" if complet else "regles", "notes": notes,
            "judges": {
                "rules": {"status": JURY_STATUS[rules_lvl],
                          "message": " · ".join(crit_text(rules_msg)) or "Tout est en ordre."},
                "visual": visual,
                "llm": llm,
                "context": {"matchWeather": None if body.temperatureC is None else crit["meteo"]["niveau"] == 2,
                            "matchOccasion": crit["formalite"]["niveau"] == 2,
                            "weatherLevel": None if body.temperatureC is None else crit["meteo"]["niveau"],   # 0 / 1 / 2
                            "occasionLevel": crit["formalite"]["niveau"],
                            "message": f"Météo : {crit['meteo']['raison']} · Style : {crit['formalite']['raison']}"},
                "compatibility": jury_compat([by_id[i] for i in ids])},
            "repairs": jury_repairs(j["reparations"], by_id)}
