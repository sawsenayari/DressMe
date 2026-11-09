"""Passerelle DressMe (provisoire, avant l'objectif 6) : UN backend sur le port 8000 pour le front.

Routes attendues par le front (frontend/src/services) :
  GET  /health
  GET  /wardrobe/items            -> fiches du catalogue (ItemCard -> ClothingItem)         [Obj1 : lecture seule]
  POST /wardrobe/crop              -> améliorer une photo avant l'ajout (découpage de l'objectif 6)
  POST /wardrobe/items            -> photo -> Obj1 (crop + ItemCard v1 + emb/<id>.npy) -> ajout au catalogue ; 501 si l'Obj1 n'est pas lançable
  POST /compatibility/score       -> photo (+ champ facultatif `category`) -> embedding FashionCLIP -> Obj2 /compat
  GET  /gaps                      -> pièces manquantes de l'objectif 4 (calculées sur la garde-robe)
  GET  /gaps/shopping             -> où acheter une pièce manquante (recherche web de l'Obj4)
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
import re
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
try:   # certificats du système (proxy qui intercepte le HTTPS : météo, Gemini, Groq) ; facultatif
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
from typing import Optional

import numpy as np
import contextvars

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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
LEGACY_STORE = Path(os.environ.get("DRESSME_STORE", REPO / "obj5_profil" / "data"))   # garde-robe d'avant les comptes
USERS_DIR = Path(os.environ.get("DRESSME_USERS_DIR", REPO / "gateway" / "users_data"))  # comptes et garde-robes (hors git)
_current_store = contextvars.ContextVar("dressme_store", default=None)
_current_user = contextvars.ContextVar("dressme_user", default=None)


class _UserStore(os.PathLike):
    """Dossier de garde-robe de l'utilisateur connecté (fixé à chaque requête par le middleware d'authentification) ;
    sans compte (authentification désactivée : DRESSME_AUTH=0), le dossier unique DRESSME_STORE."""
    def path(self):
        return _current_store.get() or LEGACY_STORE

    def __fspath__(self):
        return str(self.path())

    def __str__(self):
        return str(self.path())

    def __repr__(self):
        return f"<garde-robe {self.path()}>"

    def __truediv__(self, other):
        return self.path() / other

    def __getattr__(self, name):   # exists(), resolve(), stat()…
        return getattr(self.path(), name)


STORE = _UserStore()
OBJ2 = Path(os.environ.get("DRESSME_OBJ2", REPO / "obj2_compat"))
GAPS = Path(os.environ.get("DRESSME_GAPS", REPO / "obj4_manques" / "gap_report.json"))
OBJ1 = Path(os.environ.get("DRESSME_OBJ1", REPO / "obj1_reconnaissance"))
OBJ3 = Path(os.environ.get("DRESSME_OBJ3", REPO / "obj3_jury"))
OBJ6_URL = os.environ.get("OBJ6_URL", "http://127.0.0.1:8006")
os.environ.setdefault("DRESSME_ROOT", str(OBJ1 / "data"))          # base kNN de l'Obj1 (data/agent_final)
os.environ.setdefault("DRESSME_STORE", str(LEGACY_STORE))
os.environ.setdefault("DRESSME_CATALOG", str(LEGACY_STORE / "wardrobe.json"))
os.environ.setdefault("DRESSME_ASSETS_DIR", str(LEGACY_STORE))
sys.path.insert(0, str(OBJ2))
sys.path.insert(0, str(REPO / "obj5_profil"))

from core import CompatEngine, CardStore  # noqa: E402  (objectif 2)

from auth import AuthError, Users  # noqa: E402  (comptes : gateway/auth.py)

app = FastAPI(title="DressMe – passerelle front")
USERS = Users(USERS_DIR)
SESSION_COOKIE = "dressme_session"
PUBLIC_PATHS = ("/auth/", "/health", "/weather", "/docs", "/openapi.json")


def _auth_on():
    return os.environ.get("DRESSME_AUTH", "1") != "0"


@app.middleware("http")
async def _authenticate(request: Request, call_next):
    """Chaque requête est rattachée au compte de son cookie de session : sa garde-robe devient STORE."""
    if request.method == "OPTIONS":
        return await call_next(request)
    user = USERS.user_for_token(request.cookies.get(SESSION_COOKIE)) if _auth_on() else None
    if user is None and _auth_on() and not request.url.path.startswith(PUBLIC_PATHS):
        return JSONResponse({"detail": "Connectez-vous pour accéder à votre garde-robe."}, status_code=401)
    tokens = (_current_store.set(USERS.store_of(user)), _current_user.set(user)) if user else None
    try:
        return await call_next(request)
    finally:
        if tokens:
            _current_store.reset(tokens[0]); _current_user.reset(tokens[1])


# cookie de session envoyé par le front (localhost, autre port) : origines explicites + credentials
_origins = os.environ.get("CORS_ORIGINS")
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
                   **({"allow_origins": _origins.split(",")} if _origins else
                      {"allow_origin_regex": r"https?://(localhost|127\.0\.0\.1)(:\d+)?"}))

_cache = {}


def _ucache():
    """Cache propre à la garde-robe courante (catalogue, jurys, analyses) : jamais partagé entre utilisateurs."""
    return _cache.setdefault(("garde-robe", str(STORE)), {})


def _obj6_uid():
    """Utilisateur côté Obj6 (préférences, rotation des tenues portées) : le compte connecté."""
    u = _current_user.get()
    return u["id"] if u else "me"


@app.get("/files/{rel:path}")
def files(rel: str):
    """Images de la garde-robe : uniquement celles du compte connecté."""
    f = _store_file(rel)
    if f is None or not f.is_file():
        raise HTTPException(404, "Image introuvable.")
    return FileResponse(f)


# ---------------------------------------------------------------- comptes
class RegisterIn(BaseModel):
    name: str
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


def _open_session(user, response: Response):
    token = USERS.new_session(user)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=30 * 86400, path="/")
    return USERS.public(user)


@app.post("/auth/register")
def auth_register(body: RegisterIn, response: Response):
    """Création de compte ; le tout premier compte reprend la garde-robe existante (DRESSME_STORE)."""
    try:
        user = USERS.register(body.name, body.email, body.password, import_from=LEGACY_STORE)
    except AuthError as e:
        raise HTTPException(409 if "existe déjà" in str(e) else 422, str(e))
    return _open_session(user, response)


@app.post("/auth/login")
def auth_login(body: LoginIn, response: Response):
    try:
        user = USERS.authenticate(body.email, body.password)
    except AuthError as e:
        raise HTTPException(401, str(e))
    return _open_session(user, response)


@app.post("/auth/logout")
def auth_logout(request: Request, response: Response):
    USERS.drop_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@app.get("/auth/me")
def auth_me(request: Request):
    if not _auth_on():
        return {"id": "local", "name": "Moi", "email": "", "authDisabled": True}
    user = USERS.user_for_token(request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(401, "Non connecté.")
    return USERS.public(user)


def engine():
    if "e" not in _cache:
        _cache["e"] = CompatEngine(base=str(OBJ2), store=CardStore(None))   # partagé : chemins absolus fournis
    return _cache["e"]


COLOUR_FR = {"noir": "black", "blanc": "white", "gris": "grey", "crème": "beige", "creme": "beige", "marron": "brown",
             "bleu": "blue", "rouge": "red", "rose": "pink", "violet": "purple", "jaune": "yellow", "vert": "green",
             "doré": "metallic", "argenté": "metallic", "multicolore": "multicolor"}


def norm_colour(c):
    """Couleur saisie en français -> vocabulaire commun des fiches (anglais)."""
    c = str(c).strip().lower()
    return COLOUR_FR.get(c, c)


def catalog():
    if "c" not in _ucache():
        p = STORE / "wardrobe.json"
        if not p.exists():
            log(f"catalogue introuvable : {p} (variable DRESSME_STORE)")
            raise HTTPException(503, "La garde-robe est introuvable sur le serveur.")
        d = json.load(open(p, encoding="utf-8"))
        _ucache()["c"] = d if isinstance(d, list) else d.get("items", [])
        for c in _ucache()["c"]:
            if c.get("colour"):
                c["colour"] = [norm_colour(x) for x in c["colour"]]
    return _ucache()["c"]


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


# Noms générés en anglais par l'Obj1 (« Grey pants ») -> français (« Pantalon gris ») ; un nom saisi par l'utilisateur
# (au moins un mot inconnu) est gardé tel quel. Nom : (français, genre f/m, pluriel)
NAME_NOUN = {
    "traditional garment": ("tenue traditionnelle", "f", False), "track pants": ("pantalon de jogging", "m", False),
    "handbag": ("sac à main", "m", False), "shirt": ("chemise", "f", False), "blouse": ("chemisier", "m", False),
    "pants": ("pantalon", "m", False), "trousers": ("pantalon", "m", False), "jeans": ("jean", "m", False),
    "shorts": ("short", "m", False), "sweater": ("pull", "m", False), "sweatshirt": ("sweat", "m", False),
    "hoodie": ("sweat à capuche", "m", False), "tshirt": ("t-shirt", "m", False), "t-shirt": ("t-shirt", "m", False),
    "top": ("haut", "m", False), "dress": ("robe", "f", False), "skirt": ("jupe", "f", False),
    "jacket": ("veste", "f", False), "blazer": ("blazer", "m", False), "coat": ("manteau", "m", False),
    "shoes": ("chaussures", "f", True), "sneakers": ("baskets", "f", True), "boots": ("bottes", "f", True),
    "heels": ("talons", "m", True), "sandals": ("sandales", "f", True), "flats": ("ballerines", "f", True),
    "bag": ("sac", "m", False), "scarf": ("écharpe", "f", False), "belt": ("ceinture", "f", False),
    "hat": ("chapeau", "m", False), "cap": ("casquette", "f", False), "accessory": ("accessoire", "m", False),
    "socks": ("chaussettes", "f", True), "tie": ("cravate", "f", False), "watch": ("montre", "f", False),
}
NAME_COLOUR = {   # (masculin, féminin, masc. pluriel, fém. pluriel)
    "black": ("noir", "noire", "noirs", "noires"), "white": ("blanc", "blanche", "blancs", "blanches"),
    "grey": ("gris", "grise", "gris", "grises"), "gray": ("gris", "grise", "gris", "grises"),
    "beige": ("beige", "beige", "beiges", "beiges"), "brown": ("marron",) * 4, "blue": ("bleu", "bleue", "bleus", "bleues"),
    "navy": ("bleu marine",) * 4, "red": ("rouge", "rouge", "rouges", "rouges"), "pink": ("rose", "rose", "roses", "roses"),
    "green": ("vert", "verte", "verts", "vertes"), "yellow": ("jaune", "jaune", "jaunes", "jaunes"),
    "purple": ("violet", "violette", "violets", "violettes"), "orange": ("orange",) * 4, "cream": ("crème",) * 4,
    "khaki": ("kaki",) * 4, "multicolor": ("multicolore", "multicolore", "multicolores", "multicolores"),
    "multicolour": ("multicolore", "multicolore", "multicolores", "multicolores"),
}


def name_fr(name):
    """« Grey pants » -> « Pantalon gris » ; None si le nom n'est pas un nom anglais généré (couleur + type connus)."""
    words = str(name or "").strip().lower().split()
    if not words:
        return None
    for k in (2, 1):   # type en 1 ou 2 mots à la fin, couleurs devant
        noun, cols = " ".join(words[-k:]), words[:-k]
        if noun in NAME_NOUN and all(c in NAME_COLOUR for c in cols):
            fr, g, pl = NAME_NOUN[noun]
            adj = " ".join(NAME_COLOUR[c][(g == "f") + 2 * pl] for c in cols)
            out = f"{fr} {adj}".strip()
            return out[0].upper() + out[1:]
    return None


def _file_version(rel):
    """« ?v=… » d'après la date du fichier : une image remplacée (ou un identifiant déjà vu) n'est jamais resservie
    depuis le cache du navigateur."""
    try:
        return f"?v={int((STORE / rel).stat().st_mtime)}"
    except OSError:
        return ""


def to_front_item(c):
    img = lambda p: f"/files/{p}{_file_version(p)}" if p else None
    col = c.get("colour") or []
    return {"id": c["id"], "name": name_fr(c.get("name")) or c.get("name") or c.get("type"), "slot": c["slot"], "category": c["slot"],
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


PAIR_USER = {"va bien": "va bien", "moyen": "moyen", "peu probable": "à éviter"}   # verdicts /pairs de l'Obj2
CAT_SLOT = {"tops": "top", "bottoms": "bottom", "all-body": "onepiece", "outerwear": "outer", "shoes": "footwear", "bags": "bag"}


def _wearable_together(cat, slot):
    """Deux pièces portées dans une même tenue : jamais deux de la même catégorie, ni une robe avec un haut ou un bas."""
    a = CAT_SLOT.get(cat, "accessory")
    if a == slot and a != "accessory":
        return False
    return {a, slot} not in ({"onepiece", "top"}, {"onepiece", "bottom"})


def compat_for(vec, category, wardrobe, name="candidate"):
    """/compat de l'Obj2 (score de la pièce avec toute la garde-robe, doublon) + /pairs (accord avec chaque pièce
    d'une autre catégorie, verdicts calibrés de l'Obj2 : >= 0,75 va bien, < 0,35 peu probable)."""
    from core import pair_verdict
    eng = engine()
    cand = {"id": name, "category": category, "embedding": vec.tolist()}
    W = [{"id": c["id"], "slot": c["slot"], "embedding": str(STORE / c["embedding"])} for c in wardrobe]
    r = eng.compat(cand, W)
    if "error" in r:
        raise HTTPException(422, r["error"])
    others = [w for w in W if eng.category_of(w) != category and _wearable_together(category, w["slot"])]
    pairs = []
    if others:
        row = eng.pairs([cand], others)[0]
        pairs = sorted(({"id": w["id"], "pair_score01": round(float(sc), 2), "verdict": PAIR_USER[pair_verdict(float(sc))]}
                        for w, sc in zip(others, row)), key=lambda x: -x["pair_score01"])
    good = [x for x in pairs if x["verdict"] == "va bien"]
    notes = [f"Plus assortie à votre garde-robe que {r['rank100']} % des pièces du même type prises au hasard (50 % = moyenne)."]
    if pairs:
        notes.append(f"Elle va bien avec {len(good)} des {len(pairs)} pièces de votre garde-robe qui peuvent se porter avec elle.")
    return {"score": r["rank100"], "score01": r["score01"], "verdict": VERDICT.get(r["verdict"], r["verdict"]),
            "category": category, "categories": [c for c in eng.cats if c in CAT_USER],
            "newOutfits": len(good),
            "partners": (good or pairs)[:4], "pairs": pairs,
            "clashing": [x for x in pairs if x["verdict"] == "à éviter"][-3:][::-1],
            "duplicate": r["duplicate"], "clashingItems": [], "notes": notes, "compared": len(W)}


# ---------------------------------------------------------------- routes
@app.get("/health")
def health():
    cat = catalog() if (STORE / "wardrobe.json").exists() else []
    return {"ok": True, "items": len(cat), "items_avec_embedding": len(wardrobe_with_embeddings()) if cat else 0,
            "gaps": GAPS.exists(),
            # état des services pour l'interface (clés présentes, pas leur valeur)
            "ia": bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("LLM_API_KEY")),
            "shopping": bool(os.environ.get("DRESSME_TAVILY_API_KEY", "").strip()), "tenueDuJour": _obj6_up()}


def _obj6_up():
    """Le service de tenue du jour (Obj6) répond-il ? (contrôle rapide, gardé 30 s)."""
    import httpx
    import time
    hit = _cache.get("obj6_up")
    if hit and time.time() - hit[0] < 30:
        return hit[1]
    try:
        ok = httpx.get(f"{OBJ6_URL}/health", timeout=1.5).status_code == 200
    except Exception:
        ok = False
    _cache["obj6_up"] = (time.time(), ok)
    return ok


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
    """Nouvel identifiant, jamais réutilisé : le dernier numéro attribué est gardé dans le store (une pièce
    supprimée ou annulée ne rend pas son numéro, sinon la suivante reprendrait les mêmes adresses d'images)."""
    used = {c["id"] for c in catalog()}
    counter = STORE / "_last_id.txt"
    try:
        last = int(counter.read_text().strip())
    except (OSError, ValueError):
        last = 0
    n = 1 + max([int(i[3:]) for i in used if i.startswith("it_") and i[3:].isdigit()] + [last])
    while f"it_{n:04d}" in used or (STORE / "items" / f"it_{n:04d}_raw.jpg").exists():
        n += 1
    try:
        counter.write_text(str(n))
    except OSError:
        pass
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
        _ucache().pop(k, None)


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
        col = [norm_colour(x) for x in (b["colour"] if isinstance(b["colour"], list) else [b["colour"]]) if str(x).strip()]
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


# ---------------------------------------------------------------- découpage des photos (module de l'objectif 6)
CROP_PART_SLOT = {"haut": "top", "bas": "bottom", "robe": "onepiece", "chaussures": "footwear", "sac": "bag",
                  "ceinture": "accessory", "chapeau": "accessory", "écharpe": "accessory", "lunettes": "accessory"}
CROP_PART_FR = {"haut": "Haut", "bas": "Bas", "robe": "Robe / pièce unique", "chaussures": "Chaussures", "sac": "Sac",
                "ceinture": "Ceinture", "chapeau": "Chapeau", "écharpe": "Écharpe", "lunettes": "Lunettes"}


def _obj6_segment():
    """Module de découpage de l'Obj6 (obj6_app/app/segment.py : SegFormer « clothes » + rembg u2netp), chargé par chemin."""
    if "seg6" not in _cache:
        import importlib.util
        spec = importlib.util.spec_from_file_location("obj6_segment", REPO / "obj6_app" / "app" / "segment.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _cache["seg6"] = mod
    return _cache["seg6"]


def _clean_mask(mask):
    """Masque d'une pièce : zones principales seulement (au moins 20 % de la plus grande), trous comblés -> pas de
    morceaux isolés quand la segmentation hésite (tenues traditionnelles, motifs)."""
    from scipy import ndimage as ndi
    m = ndi.binary_closing(mask, iterations=2)
    lab, n = ndi.label(m)
    if n == 0:
        return mask
    sizes = ndi.sum(m, lab, range(1, n + 1))
    keep = np.isin(lab, [i + 1 for i, s_ in enumerate(sizes) if s_ >= 0.2 * sizes.max()])
    return ndi.binary_fill_holes(keep)


def _plain_background(img):
    """Photo déjà sur fond clair et uni (photo produit) : au moins 85 % de la bordure à ±12 d'une teinte claire
    (le vêtement peut toucher un bord)."""
    a = np.asarray(img.convert("L"), dtype=np.float32)
    b = max(2, min(a.shape) // 40)
    border = np.concatenate([a[:b].ravel(), a[-b:].ravel(), a[:, :b].ravel(), a[:, -b:].ravel()])
    med = float(np.median(border))
    return med >= 228 and float((np.abs(border - med) <= 12).mean()) >= 0.85


def _data_url(im, side=900):
    from PIL import Image
    im = im.convert("RGB")
    im.thumbnail((side, side), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=90)
    return "data:image/jpeg;base64," + __import__("base64").b64encode(buf.getvalue()).decode()


@app.post("/wardrobe/crop")
def crop_photo(image: UploadFile = File(...)):
    """Améliore une photo avant l'ajout (découpage de l'Obj6) : photo portée -> une image par vêtement détecté (fond
    blanc) ; photo à plat sur fond chargé -> vêtement détouré. needed = False quand la photo est déjà propre."""
    from PIL import Image
    try:
        img = Image.open(io.BytesIO(image.file.read())).convert("RGB")
    except Exception:
        raise HTTPException(422, "Ce fichier n'est pas une image lisible.")
    img.thumbnail((1600, 1600))
    seg = _obj6_segment()
    try:
        labels, id2l = seg._segment(img)
    except Exception as e:
        log(f"découpage (Obj6) indisponible : {type(e).__name__}: {e}")
        raise HTTPException(503, "L'amélioration automatique de la photo n'est pas disponible pour le moment.")
    n2i = {v: k for k, v in id2l.items()}
    total = labels.size
    person = sum(int((labels == n2i[n]).sum()) for n in seg.PERSON if n in n2i) / total
    parts = []
    if person >= 0.02:   # photo portée (même seuil que l'Obj6) : une image par vêtement
        for part, names in seg.PARTS.items():
            m = np.isin(labels, [n2i[x] for x in names if x in n2i])
            if m.mean() >= 0.015:
                m = _clean_mask(m)
                parts.append((int(m.sum()), part, seg._cut(img, m)))
        parts.sort(key=lambda x: -x[0])
    if parts:
        kind = "portée"
    elif _plain_background(img):
        return {"needed": False, "kind": "propre", "parts": []}
    else:
        try:
            cut = seg.cutout(img)
        except Exception as e:
            log(f"détourage (rembg) indisponible : {type(e).__name__}: {e}")
            return {"needed": False, "kind": "à plat", "parts": []}
        if cut is img:
            return {"needed": False, "kind": "à plat", "parts": []}
        kind, parts = "à plat", [(0, "photo", cut)]
    return {"needed": True, "kind": kind, "parts": [
        {"part": p, "label": CROP_PART_FR.get(p, "Vêtement détouré"), "slot": CROP_PART_SLOT.get(p), "image": _data_url(im)}
        for _, p, im in parts]}


@app.post("/wardrobe/items")
def add_item(image: UploadFile = File(...), crop: Optional[UploadFile] = File(None), slot_hint: Optional[str] = Form(None)):
    """image : photo d'origine ; crop (facultatif) : pièce choisie après /wardrobe/crop, analysée telle quelle."""
    svc = recognizer()
    data = image.file.read()
    crop_data = crop.file.read() if crop is not None else None
    suffix = Path(image.filename or "photo.jpg").suffix.lower() or ".jpg"
    with _write_lock, tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / f"photo{suffix}"
        raw.write_bytes(data)
        item_id = _next_id()
        src, kw = raw, {}
        cropper = getattr(svc, "cropper", None)
        if crop_data:   # pièce déjà découpée et choisie par l'utilisateur : pas de second découpage
            src = Path(tmp) / "piece.jpg"
            src.write_bytes(crop_data)
            import inspect
            if slot_hint in SLOTS and "slot_hint" in inspect.signature(svc.recognize).parameters:
                kw = dict(slot_hint=slot_hint)   # catégorie trouvée par le découpage (si le service de l'Obj1 la prend)
        elif cropper is not None:
            # pas d'amélioration demandée : photo entière, seulement mise au format de l'Obj1 (mode « none » : ni
            # segmentation ni détourage). Le découpage ne se fait que sur demande (« Améliorer la photo », /wardrobe/crop).
            piece = cropper.crop(raw, mode="none")[0]
            src = Path(tmp) / "piece.png"
            piece.image.save(src)
            kw = dict(crop_reasons=(piece.quality or {}).get("reasons"), slot_hint=piece.slot_hint)
        try:
            # photo de la pièce : la version améliorée choisie (pièce découpée / détourée), sinon la photo d'origine
            r = svc.recognize(src, item_id=item_id, raw_path=str(src if crop_data else raw), out_dir=STORE, **kw)
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
                Image.open(io.BytesIO(crop_data or data)).convert("RGB").save(STORE / rel)
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
    if category and category not in CAT_USER:
        raise HTTPException(422, "Type de pièce inconnu.")
    try:
        vec, guessed = embed_photo(data)
    except ImportError as e:
        log(f"torch/transformers manquants : {e}")
        raise HTTPException(503, "La comparaison n'est pas disponible pour le moment.")
    except Exception as e:
        log(f"photo illisible pour la comparaison : {type(e).__name__}: {e}")
        raise HTTPException(422, "Ce fichier n'est pas une image lisible.")
    res = compat_for(vec, category or guessed, W)
    res["guessedCategory"] = guessed   # type deviné par FashionCLIP ; « category » = celui utilisé (corrigé par l'utilisateur)
    return res


# ---- conseil de la styliste IA (couche LLM de l'Obj2) : le score reste celui du modèle PairMLP ; le LLM l'explique.
# Prompts versionnés, schéma de sortie, garde-fous, traces et évaluation : obj2_compat/stylist/ (voir son README).
STYLIST_TRACE = USERS_DIR / "traces" / "stylist.jsonl"   # observabilité des appels LLM (hors git)


def _stylist(key):
    from stylist import StylistAdvisor, StylistConfig
    os.environ.setdefault("GEMINI_VISION_MODELS", GEMINI_VISION_MODELS)
    os.environ.setdefault("STYLIST_TRACE", str(STYLIST_TRACE))
    return StylistAdvisor(StylistConfig(), api_key=key)


@app.post("/compatibility/advice")
async def compat_advice(image: UploadFile = File(...), category: Optional[str] = Form(None)):
    """Conseil de la styliste IA sur demande : score du modèle (Obj2) recalculé, puis Gemini voit la photo et explique."""
    import hashlib
    from PIL import Image
    from stylist.advisor import build_facts
    data = await image.read()
    res = await compat_score(_Upload(data), category)
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return {**res, "advice": None, "adviceNote": "Conseil de l'IA non activé (clé GEMINI_API_KEY absente)."}
    facts, suspects = build_facts(res, {c["id"]: c for c in catalog()}, _tryon_name)
    advisor = _stylist(key)
    ck = ("compat-advice", advisor.prompt.version, hashlib.sha1(data).hexdigest(), json.dumps(facts, sort_keys=True))
    if ck not in _ucache():
        try:
            img = Image.open(io.BytesIO(data)).convert("RGB")
        except Exception:
            raise HTTPException(422, "Ce fichier n'est pas une image lisible.")
        out = advisor.advise(img, facts, suspects)
        if out.advice is None:
            log(f"conseil compatibilité : {out.trace.get('error') or out.trace.get('schema_error') or 'refusé par les garde-fous'}")
            return {**res, "advice": None, "adviceNote": out.note}
        _ucache()[ck] = out.advice.model_dump()
    return {**res, "advice": _ucache()[ck], "adviceNote": None}


class _Upload:
    """Photo déjà lue, repassée à compat_score (même calcul que « Ça va avec ? »)."""
    def __init__(self, data):
        self.data = data

    async def read(self):
        return self.data


FRONT_SLOT = {  # slots / catégories Polyvore de l'Obj4 -> Slot du front
    "top": "top", "tops": "top", "bottom": "bottom", "bottoms": "bottom", "onepiece": "onepiece", "all-body": "onepiece",
    "outer": "outer", "outerwear": "outer", "footwear": "footwear", "shoes": "footwear", "bag": "bag", "bags": "bag",
    "accessory": "accessory", "accessories": "accessory", "hats": "accessory", "jewellery": "accessory",
    "scarves": "accessory", "sunglasses": "accessory",
}


OBJ4 = REPO / "obj4_manques"
# Liste de pièces de base (repli quand aucune IA n'est disponible) : mêmes champs que les candidats de l'IA de l'Obj4
GAP_BASICS = [
    ("top", "chemise blanche unie", "Basique neutre qui s'accorde avec presque tous les bas."),
    ("top", "t-shirt noir uni", "Haut simple pour multiplier les tenues décontractées."),
    ("bottom", "pantalon noir droit", "Bas neutre qui va avec la plupart des hauts, du quotidien au bureau."),
    ("bottom", "jean bleu foncé", "Bas polyvalent pour les tenues de tous les jours."),
    ("onepiece", "robe noire simple", "Pièce unique qui forme une tenue complète avec des chaussures."),
    ("outer", "trench beige", "Couche légère et neutre qui complète beaucoup de tenues."),
    ("shoes", "baskets blanches", "Chaussures neutres qui s'accordent avec la majorité des tenues."),
    ("shoes", "bottines noires", "Chaussures fermées pour la mi-saison et les tenues plus habillées."),
    ("bag", "sac cabas beige", "Sac neutre qui accompagne la plupart des tenues."),
]
# mots français ajoutés aux pièces pour que le choix du proxy de l'Obj4 (mots communs avec la description) marche en français
GAP_TYPE_FR = {"sneakers": "baskets tennis", "casual shoes": "baskets chaussures", "track pants": "pantalon jogging",
               "sweatshirts": "sweat pull", "boots": "bottes bottines", "shoes": "chaussures", "heels": "escarpins talons",
               "sandals": "sandales", "flats": "ballerines", "shirts": "chemise chemisier", "tshirts": "t-shirt tshirt",
               "tops": "haut top", "sweaters": "pull", "trousers": "pantalon", "pants": "pantalon", "jeans": "jean",
               "shorts": "short", "skirts": "jupe", "dresses": "robe", "coats": "manteau trench", "jackets": "veste blazer",
               "handbags": "sac main", "bags": "sac cabas"}
GAP_COLOUR_FR = {"black": "noir noire noirs noires", "white": "blanc blanche blancs blanches", "grey": "gris grise grises",
                 "beige": "beige beiges", "brown": "marron", "blue": "bleu bleue bleus bleues", "red": "rouge rouges",
                 "pink": "rose roses", "green": "vert verte verts vertes", "yellow": "jaune jaunes", "purple": "violet violette"}
# accessoires (non comptés dans les tenues de l'Obj4) que l'IA range parfois en « sac » ou « haut »
GAP_ACCESSORY_WORDS = re.compile(r"\b(ceinture|belt|montre|watch|bijou|collier|necklace|bracelet|chapeau|hat|casquette|cap|"
                                 r"écharpe|echarpe|foulard|scarf|lunettes|sunglasses|cravate|tie)s?\b", re.IGNORECASE)
GAP_COMPATIBLE, GAP_INCOMPATIBLE = 0.70, 0.40
GAP_LIKELY = 0.50   # estimation de la passerelle : association retenue si l'Obj2 la juge plus probable qu'improbable
GAP_COLOUR_WORDS = {w: en for en, ws in GAP_COLOUR_FR.items() for w in ws.split()}   # « noire » -> black   # seuils de l'Obj4 (non encore calibrés par l'équipe)


def _obj4_path():
    if str(OBJ4) not in sys.path:
        sys.path.append(str(OBJ4))


class _FrenchGateway:
    """Enveloppe de la passerelle LLM de l'Obj4 : demande les descriptions et justifications en français."""
    def __init__(self, inner):
        self.inner = inner

    def complete(self, messages, **kw):
        extra = {"role": "system", "content": "Rédige les champs 'description' et 'rationale' en français, phrases courtes."}
        return self.inner.complete([messages[0], extra, *messages[1:]], **kw)


def _gap_llm_candidates(items, n=6):
    """Candidats de pièces manquantes proposés par l'IA de l'Obj4 (Gemini, sinon Groq) ; (None, None) sans IA."""
    from openai import OpenAI
    from dressme_gap_agent.compatibility import generate_gap_archetypes
    from dressme_gap_agent.config import AgentConfig
    from dressme_gap_agent.gateway import OpenAICompatibleGateway
    routes = []
    if os.environ.get("GEMINI_API_KEY"):
        model = os.environ.get("GEMINI_MODELS", "gemini-3.5-flash-lite,gemini-3.1-flash").split(",")[0].strip()
        routes.append(("https://generativelanguage.googleapis.com/v1beta/openai", os.environ["GEMINI_API_KEY"], model))
    if os.environ.get("LLM_API_KEY"):
        routes.append(("https://api.groq.com/openai/v1", os.environ["LLM_API_KEY"], "openai/gpt-oss-120b"))
    summary = [{"item_id": c["id"], "category": c["slot"], "slot": "shoes" if c["slot"] == "footwear" else c["slot"],
                "color_candidates": [{"label": x} for x in c.get("colour") or []],
                "style_candidates": [{"label": c["usage"]}] if c.get("usage") else []} for c in items]
    for base, key, model in routes:
        try:
            cfg = AgentConfig(base_url=base, api_key=key, model=model, allow_remote_router=True, timeout_seconds=45,
                              max_judge_tokens=2000)
            gw = OpenAICompatibleGateway(OpenAI(api_key=key, base_url=base, timeout=45, max_retries=0), cfg)
            return generate_gap_archetypes(_FrenchGateway(gw), cfg, summary, max_candidates=n), model
        except Exception as e:
            log(f"Obj4 : candidats IA indisponibles avec {model} ({type(e).__name__}: {str(e)[:160]})")
    return None, None


def _gap_static():
    """Rapport statique de l'Obj4 (repli documenté) : exemple sans lien avec la garde-robe."""
    if not GAPS.exists():
        log(f"rapport de manques introuvable : {GAPS}")
        raise HTTPException(503, "L'analyse des pièces manquantes n'est pas encore disponible.")
    d = json.load(open(GAPS, encoding="utf-8"))
    d = d if isinstance(d, list) else d.get("gaps", [])
    out = []
    for i, g in enumerate(d):
        sl = FRONT_SLOT.get(str(g.get("slot") or g.get("category") or "").lower(), "accessory")
        n = int(g.get("unlockedOutfits") or 0)
        out.append({"id": g.get("id", f"gap-{i + 1}"), "rank": i + 1, "description": g.get("description", ""), "slot": sl,
                    "category": sl, "rationale": "", "gain_lower": int(g.get("gain_lower", n)),
                    "gain_upper": int(g.get("gain_upper", n)), "unlockedOutfits": n, "proxy": None})
    return out


def _count_outfits(items, judgments, unknown_as_compatible):
    """Comptage des tenues du moteur de l'Obj4 (mêmes modèles : haut + bas + chaussures, ou robe + chaussures ; veste et
    sac en couches facultatives), SANS le plafond « une seule veste / un seul sac » de l'Obj4 : chaque veste ou sac
    compatible donne une tenue différente. Avec le plafond, une veste ou un sac de plus ne pouvait jamais rien ajouter
    (le candidat étant simulé par une pièce déjà possédée)."""
    from itertools import product
    from dressme_gap_agent.outfit_engine import CORE_PATTERNS, LAYER_SLOTS
    from dressme_gap_agent.slot_mapping import normalize_slot
    by_slot = {}
    for it in items:
        by_slot.setdefault(normalize_slot(it["slot"]), []).append(it["item_id"])

    def ok(a, b):
        v = judgments.get(tuple(sorted((a, b))), "uncertain")
        return unknown_as_compatible if v == "uncertain" else v == "compatible"

    total = 0
    for pattern in CORE_PATTERNS:
        lists = [by_slot.get(sl, []) for sl in pattern]
        if any(not x for x in lists):
            continue
        for core in product(*lists):
            if not all(ok(core[i], core[j]) for i in range(len(core)) for j in range(i + 1, len(core))):
                continue
            mult = 1
            for layer in LAYER_SLOTS:   # sans veste, ou avec chacune des vestes compatibles (idem pour les sacs)
                mult *= 1 + sum(all(ok(x, c) for c in core) for x in by_slot.get(layer, []))
            total += mult
    return total


def _gain_bounds(wardrobe, cand, judgments):
    """Bornes prudente / optimiste, même formule que gain_bounds de l'Obj4, avec le comptage ci-dessus."""
    b_lo, b_hi = _count_outfits(wardrobe, judgments, False), _count_outfits(wardrobe, judgments, True)
    a_lo, a_hi = _count_outfits([*wardrobe, cand], judgments, False), _count_outfits([*wardrobe, cand], judgments, True)
    return {"before_lower": b_lo, "before_upper": b_hi, "after_lower": a_lo, "after_upper": a_hi,
            "gain_lower": max(0, a_lo - b_hi), "gain_upper": max(0, a_hi - b_lo)}


@app.get("/gaps")
def gaps(refresh: bool = False):
    """Pièces manquantes (objectif 4) calculées sur la garde-robe : candidats (IA de l'Obj4, sinon pièces de base),
    chacun représenté par une pièce de même catégorie (proxy de l'Obj4), scores de paires de l'Obj2, comptage
    déterministe des tenues (moteur de l'Obj4) avec un gain prudent et un gain optimiste. Repli : rapport statique."""
    import hashlib
    _obj4_path()
    from dressme_gap_agent.candidate_prototypes import CandidatePrototypeError, resolve_candidate_prototypes
    from dressme_gap_agent.compatibility_scores import score_to_verdict
    from dressme_gap_agent.contracts import validate_gap_result
    from dressme_gap_agent.outfit_engine import required_pair_keys

    # garde-robe comptée par l'Obj4 : pièces avec embedding, hors accessoires, une seule pièce par apparence
    cards, seen = [], set()
    for c in wardrobe_with_embeddings():
        sig = (str(c.get("name")).lower(), c.get("type"), tuple(c.get("colour") or []), c["slot"])
        if c["slot"] != "accessory" and sig not in seen:
            seen.add(sig)
            cards.append(c)
    if len(cards) < 2:
        return {"mode": "exemple", "notice": "Ajoutez des pièces avec photo à votre garde-robe pour une analyse personnalisée.",
                "gaps": _gap_static(), "unscorable": [], "outfitsNow": None, "source": None}

    fp = hashlib.sha1(json.dumps([(c["id"], c["slot"], c.get("colour")) for c in cards]).encode()).hexdigest()
    key = ("gaps", fp)
    if not refresh and key in _ucache():
        return _ucache()[key]
    if refresh or ("gapcand", fp) not in _ucache():
        cands, model = _gap_llm_candidates(cards)
        if cands:
            _ucache()[("gapcand", fp)] = (cands, "ia", model)
        else:
            g = [c.get("gender") for c in cards if c.get("gender") in ("Women", "Men")]
            men = bool(g) and g.count("Men") > g.count("Women")
            basics = [b for b in GAP_BASICS if not (men and b[0] == "onepiece")]
            _ucache()[("gapcand", fp)] = ([{"item_id": f"candidate-{i + 1:03d}", "slot": sl, "description": d, "rationale": r}
                                        for i, (sl, d, r) in enumerate(basics)], "base", None)
    cands, source, model = _ucache()[("gapcand", fp)]

    wardrobe = [{"item_id": c["id"], "id": c["id"], "slot": c["slot"], "name": c.get("name"), "type": c.get("type"),
                 "colour": c.get("colour") or [], "embedding": np.load(STORE / c["embedding"]).astype(float).tolist(),
                 "pattern": " ".join([GAP_TYPE_FR.get(str(c.get("type") or "").lower(), ""),
                                      *[GAP_COLOUR_FR.get(x, "") for x in c.get("colour") or []]])}
                for c in cards]
    resolved, unscorable, used = [], [], set()
    for cand in cands:
        base = {k: cand[k] for k in ("item_id", "slot", "description", "rationale")}
        if GAP_ACCESSORY_WORDS.search(base["description"]):   # accessoire : pas compté dans les tenues -> non chiffré
            unscorable.append({**base, "slot": "accessory"})
            continue
        try:   # proxy de l'Obj4 : pièce de même catégorie la plus proche du texte, jamais deux fois la même
            r = resolve_candidate_prototypes([base], [w for w in wardrobe if w["id"] not in used])[0]
            used.add(r["proxy_item_id"])
            resolved.append(r)
        except CandidatePrototypeError:   # aucune pièce de cette catégorie pour la représenter
            unscorable.append(base)

    combined = [*wardrobe, *resolved]
    pairs = [pk for pk in required_pair_keys(combined) if not all(x.startswith("candidate-") for x in pk)]
    # scores de l'Obj2 par blocs de catégories (seulement les paires utiles au comptage, comme le pipeline de l'Obj4)
    by_id = {x["item_id"]: x for x in combined}
    blocks = {}
    for x, y in pairs:
        sx, sy = by_id[x]["slot"], by_id[y]["slot"]
        if (sy, sx) in blocks:
            x, y, sx, sy = y, x, sy, sx
        bx, by_ = blocks.setdefault((sx, sy), ({}, {}))
        bx[x] = by_id[x]; by_[y] = by_id[y]
    scores = {}
    for (sx, sy), (bx, by_) in blocks.items():
        A, B = list(bx.values()), list(by_.values())
        M = engine().pairs([{"id": v["item_id"], "slot": v["slot"], "embedding": v["embedding"]} for v in A],
                           [{"id": v["item_id"], "slot": v["slot"], "embedding": v["embedding"]} for v in B])
        for i, va in enumerate(A):
            for j, vb in enumerate(B):
                if va["item_id"] != vb["item_id"]:
                    scores[tuple(sorted((va["item_id"], vb["item_id"])))] = float(M[i][j])
    verdicts = {pk: score_to_verdict(scores[pk], compatible_threshold=GAP_COMPATIBLE,
                                     incompatible_threshold=GAP_INCOMPATIBLE) for pk in pairs}
    # chiffre principal : comptage du moteur de l'Obj4 où chaque association est tranchée au score 0,5 de l'Obj2
    # (ni prudent ni optimiste) ; les bornes de l'Obj4 restent fournies telles quelles
    likely = {pk: ("compatible" if scores[pk] >= GAP_LIKELY else "incompatible") for pk in pairs}
    now_likely = _count_outfits(wardrobe, likely, False)
    results = []
    for r in resolved:
        b = _gain_bounds(wardrobe, r, verdicts)
        after = _count_outfits([*wardrobe, r], likely, False)
        results.append({"item_id": r["item_id"], "description": r["description"], "slot": r["slot"],
                        "rationale": r.get("rationale", ""), "proxy_item_id": r["proxy_item_id"],
                        "gain_likely": max(0, after - now_likely), **b})
    results.sort(key=lambda x: (-x["gain_likely"], -x["gain_upper"], -x["gain_lower"], x["item_id"]))
    for rank, x in enumerate(results, 1):
        x["rank"] = rank
    validate_gap_result({"contract_version": "1.0", "status": "complete", "ranking_ready": True, "gaps": results,
                         "compatibility_progress": {"total_pairs": len(pairs), "completed_pairs": len(pairs), "remaining_pairs": 0}})
    now_low = _count_outfits(wardrobe, verdicts, False)
    now_high = _count_outfits(wardrobe, verdicts, True)
    cat = {c["id"]: c for c in catalog()}
    def colour_differs(desc, proxy_id):
        """La description cite une couleur que la pièce de simulation n'a pas (proxy de l'Obj4 = même catégorie)."""
        wanted = {GAP_COLOUR_WORDS[w] for w in re.findall(r"[a-zà-ÿ]+", desc.lower()) if w in GAP_COLOUR_WORDS}
        have = set((cat.get(proxy_id) or {}).get("colour") or [])
        return bool(wanted) and not wanted & have

    res = {"mode": "analyse", "source": source, "model": model, "pieces": len(cards), "pairsScored": len(pairs),
           "thresholds": {"compatible": GAP_COMPATIBLE, "incompatible": GAP_INCOMPATIBLE, "likely": GAP_LIKELY},
           "calibrated": False, "shoppingEnabled": bool(os.environ.get("DRESSME_TAVILY_API_KEY", "").strip()),
           "outfitsNow": {"lower": now_low, "upper": now_high, "likely": now_likely},
           "gaps": [{"id": x["item_id"], "rank": x["rank"], "description": x["description"], "slot": x["slot"],
                     "category": x["slot"], "rationale": x["rationale"], "gain_lower": x["gain_lower"],
                     "gain_upper": x["gain_upper"], "gain_likely": x["gain_likely"], "unlockedOutfits": x["gain_likely"],
                     "ranking_ready": True, "proxyColourDiffers": colour_differs(x["description"], x["proxy_item_id"]),
                     "proxy": to_front_item(cat[x["proxy_item_id"]]) if x["proxy_item_id"] in cat else None}
                    for x in results],
           "unscorable": [{"description": u["description"], "slot": "footwear" if u["slot"] == "shoes" else u["slot"],
                           "rationale": u.get("rationale", "")} for u in unscorable]}
    _ucache()[key] = res
    return res


_TND_PRICE = re.compile(r"(\d{1,3}(?:[ .,\u00a0]\d{3})*(?:[.,]\d{1,3})?)\s?(?:DT|TND|dinars?)\b", re.IGNORECASE)


# taux approximatifs (dinars pour 1 unité), seulement pour trier et indiquer un ordre de grandeur
SOCIAL_SITES = ("facebook.", "instagram.", "pinterest.", "tiktok.", "twitter.", "x.com", "reddit.", "youtube.", "youtu.be")
TND_RATE = {"TND": 1.0, "EUR": 3.4, "USD": 3.1, "GBP": 4.0, "$": 3.1, "€": 3.4, "£": 4.0}


def _price_tnd(text):
    """Prix en dinars (« 89,000 DT », « 129 TND ») que l'extraction de l'Obj4 ($ € £) ne reconnaît pas."""
    m = _TND_PRICE.search(text or "")
    if not m:
        return None
    raw = m.group(1).replace(" ", "").replace("\u00a0", "")
    if "." in raw and "," in raw:                     # 1.299,500 DT : milliers puis décimales (ou l'inverse)
        sep = "." if raw.index(".") < raw.index(",") else ","
        raw = raw.replace(sep, "").replace("," if sep == "." else ".", ".")
    elif re.fullmatch(r"\d+[.,]\d{3}", raw):        # 89,000 DT / 89.000 DT = 89 dinars (millimes)
        raw = raw.replace(",", ".")
    else:
        raw = raw.replace(".", "").replace(",", ".") if raw.count(".") > 1 else raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _page_meta(url):
    """Balises de la page produit (comme le site les affiche) : description, photo, prix (og / product / JSON-LD)."""
    from html.parser import HTMLParser
    from urllib.request import Request, urlopen

    class P(HTMLParser):
        def __init__(self):
            super().__init__(); self.meta = {}; self.ld = []; self._ld = False

        def handle_starttag(self, tag, attrs):
            a = {k.lower(): v for k, v in attrs}
            if tag == "meta":
                k = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
                if k and a.get("content") and k not in self.meta:
                    self.meta[k] = a["content"].strip()
            elif tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
                self._ld = True; self.ld.append("")

        def handle_endtag(self, tag):
            if tag == "script":
                self._ld = False

        def handle_data(self, data):
            if self._ld:
                self.ld[-1] += data

    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (DressMe)", "Accept-Language": "fr,en;q=0.8"})
        with urlopen(req, timeout=6) as r:
            if "text/html" not in r.headers.get("Content-Type", "").lower():
                return {}
            html = r.read(400_000).decode("utf-8", errors="ignore")
    except Exception:
        return {}
    p = P(); p.feed(html)
    m = p.meta
    out = {"description": m.get("og:description") or m.get("description") or m.get("twitter:description"),
           "image": m.get("og:image") or m.get("twitter:image"),
           "title": m.get("og:title"), "product": (m.get("og:type") or "").lower().startswith("product")}
    price = m.get("product:price:amount") or m.get("og:price:amount") or m.get("price")
    cur = m.get("product:price:currency") or m.get("og:price:currency") or m.get("pricecurrency")
    if not price:   # JSON-LD schema.org Product / Offer
        for block in p.ld:
            mm = re.search(r'"price"\s*:\s*"?([\d.,]+)"?', block)
            if mm:
                price = mm.group(1); out["product"] = True
                cc = re.search(r'"priceCurrency"\s*:\s*"([A-Z]{3})"', block)
                cur = cur or (cc.group(1) if cc else None)
                break
    try:
        out["price"] = float(str(price).replace(",", ".")) if price else None
    except ValueError:
        out["price"] = None
    out["currency"] = (cur or "").upper() or None
    return out


def _clean_snippet(text, n=220):
    """Texte de Tavily sans markdown ni liens, coupé à la fin d'un mot."""
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text or "")
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"[#*_`>|]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


@app.get("/gaps/shopping")
def gaps_shopping(description: str, slot: str = "", max_price: Optional[float] = None, k: int = 10):
    """Recherche en ligne d'une pièce manquante : Tavily (requête de l'Obj4 « [pièce] buy online »), puis lecture des
    pages trouvées (description, photo, prix du produit). Résultats triés par prix croissant, prix inconnus à la fin ;
    les fiches produit passent devant les articles. Ne modifie pas le classement des manques."""
    from concurrent.futures import ThreadPoolExecutor
    from urllib.parse import urlparse
    _obj4_path()
    from dressme_gap_agent.shopping import ShoppingSearchConfig, ShoppingSearchError, search_gap
    if not description.strip() or len(description) > 120:
        raise HTTPException(422, "Description de la pièce invalide.")
    try:
        cfg = ShoppingSearchConfig.from_env()
    except ShoppingSearchError:
        raise HTTPException(503, "La recherche en ligne n'est pas configurée : ajoutez la clé DRESSME_TAVILY_API_KEY dans gateway/.env puis relancez run_all.bat.")
    try:   # sans filtre de prix ici : l'Obj4 écarterait les prix en dinars qu'il ne sait pas lire
        opts = search_gap({"description": description.strip(), "slot": slot}, cfg, max_results=max(3, min(k, 12)))
    except Exception as e:
        log(f"Obj4 : recherche de boutiques en échec ({type(e).__name__}: {str(e)[:160]})")
        raise HTTPException(502, "La recherche en ligne n'a pas abouti. Réessayez dans un instant.")
    opts = [o for o in opts if not any(sn in urlparse(o["url"]).netloc.lower() for sn in SOCIAL_SITES)]   # pas des boutiques
    with ThreadPoolExecutor(max_workers=6) as pool:
        metas = list(pool.map(lambda o: _page_meta(o["url"]), opts))
    out = []
    for o, m in zip(opts, metas):
        price, cur = m.get("price"), m.get("currency")
        if price is None and o.get("price") is not None:
            price, cur = o["price"], o.get("currency")
        if price is None:
            price = _price_tnd(f"{o.get('title', '')} {o.get('snippet', '')}")
            cur = "TND" if price is not None else None
        if price is not None and price <= 0:   # prix vide sur la page (« 0 »)
            price, cur = None, None
        tnd = round(price * TND_RATE[cur], 1) if price is not None and cur in TND_RATE else None
        if max_price is not None and (tnd is None or tnd > max_price):   # budget en dinars
            continue
        out.append({"title": (m.get("title") or o["title"]).strip()[:140], "url": o["url"],
                    "site": urlparse(o["url"]).netloc.removeprefix("www."),
                    "description": _clean_snippet(m.get("description") or o.get("snippet") or ""),
                    "price": price, "currency": cur, "imageUrl": m.get("image") or o.get("image_url"),
                    "priceTnd": tnd,
                    # fiche produit : la page se déclare produit (og:type, product:price, schema.org) et n'est pas une
                    # page d'accueil de marque ; un prix trouvé dans le texte ne suffit pas
                    "product": bool(m.get("product")) and urlparse(o["url"]).path.strip("/") != ""})
    out.sort(key=lambda x: (not x["product"], x["priceTnd"] is None, x["priceTnd"] or 0))   # devises comparées en dinars
    return {"description": description, "query": f"{description.strip()} buy online", "options": out}


AXIS = {"efficacite": "efficiency", "economie": "economy", "image": "brand", "mixte": "mixte"}


OBJ5_REF_MODEL = REPO / "obj5_profil" / "models" / "style_model.joblib"   # modèle de référence versionné (423 fiches, attributs)


def _obj5_core(ids):
    """Profil Obj5 avec son modèle de référence (taxonomie de 16 styles apprise sur 423 fiches, espace d'attributs) :
    les pièces de la garde-robe sont rangées dans ces styles. Le même profil sert à l'affichage et aux suggestions."""
    from dressme_profile.clustering import StyleModel
    from dressme_profile.profile import build_profile
    from dressme_profile.service import load_items
    try:
        if "pref" not in _cache:
            _cache["pref"] = StyleModel.load(OBJ5_REF_MODEL)
        items = [i.model_copy(update={"colour": [norm_colour(c) for c in i.colour]})
                 for i in load_items(STORE / "wardrobe.json") if i.id in set(ids)]
        return _cache["pref"], items, build_profile(items, _cache["pref"], "me", None)
    except Exception as e:
        log(f"Profil de style (Obj5) indisponible : {type(e).__name__}: {e}")
        raise HTTPException(503, "Votre profil de style n'est pas encore disponible.")


def _obj5_profile(ids):
    from collections import Counter
    from dressme_profile.clustering import _name_cluster
    from dressme_profile.features import stack
    model, items, prof = _obj5_core(ids)
    p = prof.model_dump()
    # Style dominant : le nom de l'Obj5 décrit le groupe du catalogue de référence (sa couleur n'est pas forcément la
    # vôtre) -> renommé avec la même règle à partir de VOS pièces rangées dans ce style, et ces pièces sont renvoyées.
    vecs = model.vectorize(items, None)
    vid = [i.id for i in items if i.id in vecs]
    by = {i.id: i for i in items}
    members = [by[i] for i, lab in zip(vid, model.assign(stack(vecs, vid))) if int(lab) == prof.dominant_cluster.id] if vid else []
    if members:
        p["dominant_cluster"]["name"] = _name_cluster(members)
    p["dominant_pieces"] = [{"id": m.id, "name": name_fr(m.name) or m.name} for m in members]
    # Palette : chaque pièce compte pour 1, partagée entre ses couleurs (l'Obj5 pondère par la confiance de l'Obj1 sur
    # la couleur, ce qui faisait passer une couleur fréquente mais incertaine derrière une couleur rare).
    share, pieces = Counter(), Counter()
    for it in items:
        for c in it.colour:
            share[c] += 1 / len(it.colour); pieces[c] += 1
    p["palette"] = [{"colour": c, "weight": round(w / max(len(items), 1), 3), "pieces": pieces[c]} for c, w in share.most_common(5)]
    return p, "référence"


def _profile_notes(p):
    """Avertissements de l'Obj5 reformulés pour l'utilisateur (les détails techniques vont dans le journal)."""
    notes, ignored = [], p["n_items"] - p["n_items_used"]
    if ignored:
        notes.append(f"{ignored} pièce(s) non prise(s) en compte (doublon ou catégorie incertaine).")
    if p["n_items_used"] < 10:
        notes.append(f"Seulement {p['n_items_used']} pièces analysées : profil encore peu stable.")
    for w in p.get("warnings") or []:
        if "homme et femme" in w:
            notes.append("Votre garde-robe mélange des pièces homme et femme.")
        elif "traditionnelles" in w:
            notes.append("Beaucoup de pièces traditionnelles : profil à interpréter avec prudence.")
        elif w not in _cache.setdefault("obj5_logged", set()):   # une seule fois par message
            _cache["obj5_logged"].add(w); log(f"Obj5 : {w}")
    return notes


@app.get("/profile")
def get_profile():
    ids = [c["id"] for c in catalog()]
    if not ids:
        raise HTTPException(422, "Ajoutez des pièces à votre garde-robe pour calculer votre profil de style.")
    p, model = _obj5_profile(ids)
    s = p["scores"]
    pct = lambda v: None if v is None else round(100 * v)
    dom = p.get("dominant_cluster") or {}
    return {"axis": AXIS.get(p["persona"], "mixte"), "persona": AXIS.get(p["persona"], "mixte"),   # orientation calculée par l'Obj5
            "budgetMode": False,
            "scores": {"efficacite": pct(s["efficacite"]), "economie": pct(s["economie"]), "image": pct(s["image"])},
            "diversityScore": pct(p["diversity"]), "formalityPref": round(p["formality_pref"], 2),
            "pricePercentile": pct(p.get("price_percentile")),
            "dominantCluster": dom.get("name"), "dominantShare": pct(dom.get("share")),
            "dominantPieces": p.get("dominant_pieces") or [],
            "palette": [{"color": e["colour"], "weight": e["weight"], "pieces": e["pieces"]} for e in p["palette"]],
            "slotCounts": p.get("slot_counts") or {}, "nItems": p["n_items"], "nItemsUsed": p["n_items_used"],
            "space": "photos" if p.get("embedding_space") == "fashionclip" else "attributs",
            "notes": _profile_notes(p),
            "nStyles": _cache["pref"].kmeans.n_clusters, "model": model}


OBJ5_REF_CATALOG = REPO / "obj5_profil" / "data" / "wardrobe.json"   # 423 fiches de référence (pièces à découvrir)


@app.get("/profile/recommendations")
def profile_recommendations(slot: Optional[str] = None, k: int = 8, gender: Optional[str] = None):
    """Pièces du catalogue de référence qui prolongent votre style (Obj5 : proximité au centre de la garde-robe,
    puis bonus selon l'orientation calculée : neutre/basique pour Efficacité, prix pour Économie, style dominant pour Image)."""
    from dressme_profile.recommend import recommend
    from dressme_profile.service import load_items
    if slot not in (None, "", *SLOTS):
        raise HTTPException(422, "Catégorie inconnue.")
    ids = {c["id"] for c in catalog()}
    if not ids:
        raise HTTPException(422, "Ajoutez des pièces à votre garde-robe pour obtenir des suggestions.")
    model, wardrobe, prof = _obj5_core(ids)   # même profil que /profile (orientation et style dominant identiques)
    try:
        if "pref_cat" not in _cache:
            _cache["pref_cat"] = load_items(OBJ5_REF_CATALOG)
        ref = _cache["pref_cat"]
    except Exception as e:
        log(f"Suggestions Obj5 indisponibles : {type(e).__name__}: {e}")
        raise HTTPException(503, "Les suggestions de style ne sont pas disponibles pour le moment.")
    auto = gender not in ("Women", "Men")
    if auto:   # par défaut : le genre le plus présent dans la garde-robe
        g = [i.gender for i in wardrobe if i.gender in ("Women", "Men")]
        gender = max(set(g), key=g.count) if g else None
    owned = {(str(i.name).lower(), i.type, tuple(i.colour)) for i in wardrobe}
    cands = [c for c in ref if c.id not in ids and (gender is None or c.gender in (gender, "Unisex"))
             and (str(c.name).lower(), c.type, tuple(c.colour)) not in owned]
    k = max(1, min(k, 20))
    by_id = {c.id: c for c in cands}
    # « Toutes » : au plus 2 pièces par catégorie (le catalogue de référence homme compte 164 tenues traditionnelles
    # sur 223 : elles occuperaient toutes les places) ; une seule pièce par apparence
    per_slot = 2 if not slot else k
    recs, seen, taken = [], set(), {}
    for r in recommend(prof, wardrobe, cands, model, 400, slot or None, None):
        c = by_id[r.id]; sig = (str(c.name).lower(), c.type, tuple(c.colour))
        if sig in seen or taken.get(c.slot, 0) >= per_slot or len(recs) >= k:
            continue
        seen.add(sig); taken[c.slot] = taken.get(c.slot, 0) + 1; recs.append(r)
    from collections import Counter
    available = Counter(c.slot for c in cands)
    return {"axis": AXIS.get(prof.persona, "mixte"), "gender": gender, "genderAuto": auto,
            "available": dict(available), "items": [
        {"id": r.id, "name": name_fr(by_id[r.id].name) or by_id[r.id].name, "slot": by_id[r.id].slot, "type": by_id[r.id].type,
         "colour": list(by_id[r.id].colour), "usage": by_id[r.id].usage, "formality": by_id[r.id].formality,
         "traditional": bool(by_id[r.id].traditional),
         "match": round(100 * max(0.0, min(1.0, r.score))),
         "reasons": [x for x in r.reasons if "prix" not in x]}   # pas de prix dans l'interface
        for r in recs]}


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


OBJ6_UID = "me"   # sans compte (DRESSME_AUTH=0) ; sinon _obj6_uid() = identifiant du compte connecté


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
    if "j" not in _ucache():
        if str(OBJ3) not in sys.path:
            sys.path.append(str(OBJ3))
        from dressme.service import DressMeService
        _ucache()["j"] = DressMeService({c["id"]: to_obj3_piece(c) for c in catalog()}, llm=None)   # règles seules
    return _ucache()["j"]


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
    """Juge visuel de l'Obj3 (judge_vision_v3) sur la planche de la tenue. Informatif : n'entre pas dans le vote de l'arbitre.
    Retiré de l'interface : n'appelle Gemini que si DRESSME_JURY_VISUAL=1 (sinon ni latence ni quota consommé)."""
    if os.environ.get("DRESSME_JURY_VISUAL") != "1":
        return {"score01": None, "status": "unavailable", "message": "Analyse des photos non activée."}
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
    if "jl" not in _ucache():
        jury()   # chemin de l'Obj3
        from dressme.service import DressMeService, build_llm
        os.environ.setdefault("GEMINI_MODELS", GEMINI_VISION_MODELS)   # la liste par défaut de l'Obj3 cite un modèle Gemini retiré
        llm = build_llm(str(OBJ3 / "app_data" / "llm_cache"))   # cache des réponses (app_data/ ignoré par git)
        _ucache()["jl"] = DressMeService({c["id"]: to_obj3_piece(c) for c in catalog()}, llm=llm) if llm else None
        if llm is None:
            print("[obj3] DRESSME_JURY_LLM=1 mais aucune clé GEMINI_API_KEY / LLM_API_KEY : règles seules.", file=sys.stderr)
    return _ucache()["jl"]


def outfit_compat01(cards):
    """Moyenne des scores /pairs de l'Obj2 sur les paires de la tenue (None si des embeddings manquent)."""
    W = [c for c in cards if c.get("embedding") and (STORE / c["embedding"]).exists()]
    if len(W) < 2 or len(W) < len(cards):
        return None
    E = [{"id": c["id"], "slot": c["slot"], "embedding": str(STORE / c["embedding"])} for c in W]
    M = np.array(engine().pairs(E, E))
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
               "city": city, "k": 10, "uid": _obj6_uid(), "exclude_outfits": excl}   # k = 10 : assez de candidats une fois les doublons écartés
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


CITY_COORDS = {"Tunis": (36.81, 10.18), "Sfax": (34.74, 10.76), "Sousse": (35.83, 10.64), "Bizerte": (37.27, 9.87),
               "Nabeul": (36.45, 10.73), "Djerba": (33.81, 10.85)}   # mêmes coordonnées que l'Obj6 (app/context.py)
_weather_cache = {}


@app.get("/weather")
def weather(city: str = "Tunis"):
    """Météo du jour (Open-Meteo, comme l'Obj6) : température ressentie, pluie, vent ; gardée 10 min en mémoire."""
    import httpx
    import time
    if city not in CITY_COORDS:
        raise HTTPException(422, f"Ville inconnue : choisissez parmi {', '.join(OBJ6_CITIES)}.")
    hit = _weather_cache.get(city)
    if hit and time.time() - hit[0] < 600:
        return hit[1]
    lat, lon = CITY_COORDS[city]
    try:
        r = httpx.get("https://api.open-meteo.com/v1/forecast", timeout=8, params={
            "latitude": lat, "longitude": lon, "current": "apparent_temperature,temperature_2m,wind_speed_10m",
            "daily": "precipitation_probability_max", "timezone": "auto", "forecast_days": 1})
        r.raise_for_status(); j = r.json()
    except Exception as e:
        log(f"météo indisponible pour {city} ({type(e).__name__}: {e})")
        return {"city": city, "available": False}
    res = {"city": city, "available": True, "temperatureC": round(j["current"]["temperature_2m"]),
           "feelsLikeC": round(j["current"]["apparent_temperature"]), "windKmh": round(j["current"]["wind_speed_10m"]),
           "rainPct": round(j["daily"]["precipitation_probability_max"][0] or 0)}
    _weather_cache[city] = (time.time(), res)
    return res


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
                          "uid": _obj6_uid(), "exclude_outfits": body.exclude_outfits, "exclude_ids": body.exclude_ids})
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
        message = ("Votre garde-robe est vide : ajoutez des pièces (haut, bas, chaussures) pour recevoir des tenues."
                   if not by_id else (res.get("message") if not res.get("outfits") else None) or
                   ("Plus d'autre tenue différente avec votre garde-robe : réinitialisez les tenues écartées."
                    if body.exclude_outfits else
                    "Garde-robe insuffisante : il faut un haut et un bas (ou une robe), et des chaussures."))
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
    return _obj6_post("/api/feedback", {"features": feats, "accepted": body.accepted, "uid": _obj6_uid(),
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


# ---------------------------------------------------------------- essayage réaliste (photos des pièces portées)
# Essayage virtuel par diffusion (modèles libres hébergés gratuitement sur Hugging Face Spaces) : la photo de la pièce
# est « portée » par un mannequin photographique ; motifs, couleurs et coupe viennent de la photo, pas d'une description.
#   haut / veste : IDM-VTON (yisol/IDM-VTON), le plus fidèle aux détails (logos, boutons, imprimés) ;
#   bas / robe   : OOTDiffusion (levihsu/OOTDiffusion), catégories « Lower-body » et « Dress ».
# Les étapes s'enchaînent (le bas est posé sur l'image où le haut est déjà porté). Chaussures et accessoires ne sont pas
# gérés par ces modèles : le front les montre à côté. Résultat mis en cache dans la garde-robe (tryon/<empreinte>.png).
TRYON_ASSETS = Path(__file__).resolve().parent / "assets" / "tryon"
TRYON_TOP_SPACE = os.environ.get("DRESSME_TRYON_TOP", "yisol/IDM-VTON")
TRYON_OOTD_SPACE = os.environ.get("DRESSME_TRYON_OOTD", "levihsu/OOTDiffusion")
TRYON_LOW_SPACE = os.environ.get("DRESSME_TRYON_LOW", "franciszzj/Leffa")   # bas / robe (DressCode) ; OOTDiffusion en secours
TRYON_OOTD_SEED = int(os.environ.get("DRESSME_TRYON_OOTD_SEED", "7"))   # graine retenue : rendu propre sur nos essais (42 : taches)
_tryon_lock = threading.Lock()


class TryOnIn(BaseModel):
    item_ids: list[str]
    gender: Optional[str] = None   # « Women » / « Men » ; sinon déduit des pièces


class TryOnUnavailable(Exception):
    pass


def _tryon_client(space):
    if ("tryon", space) not in _cache:
        from gradio_client import Client
        # adresse directe du Space (« yisol/IDM-VTON » -> https://yisol-idm-vton.hf.space) : marche aussi avec
        # HF_HUB_OFFLINE=1, posé pour charger FashionCLIP depuis le cache, qui bloque la résolution par l'API du Hub
        url = space if space.startswith("http") else "https://" + re.sub(r"[/_.]", "-", space.lower()) + ".hf.space"
        _cache[("tryon", space)] = Client(url, token=os.environ.get("HF_TOKEN") or None, verbose=False)
    return _cache[("tryon", space)]


def _tryon_call(space, *args, api_name):
    try:
        return _tryon_client(space).predict(*args, api_name=api_name)
    except ImportError:
        raise TryOnUnavailable("Le module gradio_client n'est pas installé sur le serveur (pip install gradio_client).")
    except Exception as e:   # quota GPU gratuit, Space en veille ou en maintenance
        _cache.pop(("tryon", space), None)
        msg = str(e)
        log(f"essayage ({space}) : {type(e).__name__}: {msg[:300]}")
        if "quota" in msg.lower():
            m = re.search(r"Try again in (\d+):(\d+):\d+", msg)
            # « Try again in 0:00:00 » : le quota se recharge peu à peu, mais pas assez pour l'étape demandée
            wait = "plus tard (le quota gratuit se recharge au fil de la journée)" if not m or m.groups() == ("0", "00")                 else "dans " + (f"{int(m[1])} h {int(m[2]):02d}" if int(m[1]) else f"{int(m[2])} min")
            raise TryOnUnavailable(f"Le quota gratuit de calcul (Hugging Face) est épuisé : réessayez {wait}"
                                   + ("." if os.environ.get("HF_TOKEN") else
                                      ", ou ajoutez un jeton gratuit HF_TOKEN dans gateway/.env (quota bien plus large)."))
        raise TryOnUnavailable("Le service d'essayage est momentanément indisponible : réessayez plus tard.")


def _garment_photo(c):
    """Photo de la pièce envoyée au modèle : la découpe sur fond propre si elle existe, sinon la photo."""
    return next((x for x in (_store_file(c.get("image_crop")), _store_file(c.get("image"))) if x is not None and x.is_file()), None)


def _garment_input(c):
    """Photo préparée pour les modèles : sur fond blanc (la transparence d'une découpe PNG est lue comme du noir) et
    centrée sans déformation dans le format 3:4 (768 x 1024) des modèles ; une photo carrée étirée donne des taches."""
    from PIL import Image
    im = Image.open(_garment_photo(c)).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im)
    im = bg.convert("RGB")
    W, H = 768, 1024
    im.thumbnail((W - 80, H - 80))
    canvas = Image.new("RGB", (W, H), "white"); canvas.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    f = Path(tempfile.gettempdir()) / f"dressme_tryon_{c['id']}.jpg"
    canvas.save(f, quality=95)
    return str(f)


def _garment_text(c):
    return " ".join(str(x) for x in [*(c.get("colour") or [])[:2], c.get("type") or c.get("name") or "garment"]).lower()


@app.post("/outfits/tryon")
def outfit_tryon(body: TryOnIn):
    import hashlib
    import shutil
    try:
        from gradio_client import handle_file
    except ImportError:
        raise HTTPException(503, "Le module gradio_client n'est pas installé sur le serveur (pip install gradio_client).")
    by_id = {c["id"]: c for c in catalog()}
    cards = [by_id[i] for i in body.item_ids if i in by_id]
    first = lambda *slots: next((c for s in slots for c in cards if c["slot"] == s and _garment_photo(c)), None)
    dress, top, bottom = first("onepiece"), first("top", "outer"), first("bottom")
    if dress:
        top = bottom = None   # une robe se porte seule
    if not (dress or top or bottom):
        raise HTTPException(422, "Choisissez au moins un haut, un bas ou une robe avec photo pour l'essayage.")
    gender = body.gender if body.gender in ("Women", "Men") else None
    if gender is None:
        g = [c.get("gender") for c in cards if c.get("gender") in ("Women", "Men")]
        gender = "Men" if g and g.count("Men") > g.count("Women") else "Women"
    worn = [c for c in (dress, top, bottom) if c]
    fp = hashlib.sha1(json.dumps(["v5", TRYON_LOW_SPACE, TRYON_OOTD_SEED, gender, TRYON_TOP_SPACE, TRYON_OOTD_SPACE,
                                  *[(c["id"], str(_garment_photo(c).stat().st_mtime)) for c in worn]]).encode()).hexdigest()[:20]
    rel = f"tryon/{fp}.png"
    out = STORE / rel
    result = {"worn": [c["id"] for c in worn], "notWorn": [c["id"] for c in cards if c not in worn], "gender": gender}
    if out.is_file():
        return {**result, "note": None, "imageUrl": f"/files/{rel}{_file_version(rel)}", "cached": True}
    person = str(TRYON_ASSETS / ("mannequin_men.jpg" if gender == "Men" else "mannequin_women.jpg"))
    t0, done, note = time.time(), [], None
    with _tryon_lock:   # un essayage à la fois : le quota GPU gratuit est partagé
        # bas / robe d'abord : OOTDiffusion travaille bien sur la photo du mannequin, mal sur une image déjà retouchée
        # (taches) ; IDM-VTON, plus robuste, pose ensuite le haut. Une étape refusée (quota) n'empêche pas les suivantes.
        err = None
        for c, kind in ((bottom, "lower_body"), (dress, "dresses")):
            if c:
                try:
                    person = _tryon_lower(person, c, kind, handle_file)
                    done.append(c)
                except TryOnUnavailable as e:
                    err = e
        if top:
            try:
                person = _tryon_call(TRYON_TOP_SPACE, dict(background=handle_file(person), layers=[], composite=None),
                                     handle_file(_garment_input(top)), _garment_text(top), True, False, 30, 42,
                                     api_name="/tryon")[0]
                done.append(top)
            except TryOnUnavailable as e:
                err = e
        if err and not done:
            raise HTTPException(503, str(err))
        if err:
            note = f"Essayage partiel : {', '.join(_tryon_name(c) for c in worn if c not in done)} non porté(s). {err}"
    if note:   # résultat partiel : montré mais pas mis en cache, pour retenter l'essayage complet plus tard
        rel = f"tryon/{fp}_partiel.png"
        out = STORE / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(person, out)
    log(f"essayage {fp} : {len(done)}/{len(worn)} pièce(s) en {time.time() - t0:.0f} s")
    return {**result, "worn": [c["id"] for c in done], "notWorn": [c["id"] for c in cards if c not in done], "note": note,
            "imageUrl": f"/files/{rel}{_file_version(rel)}", "cached": False}


def _image_path(r):
    """Premier résultat d'un Space (liste, galerie ou fichier) -> chemin local de l'image."""
    while isinstance(r, (list, tuple)):
        r = r[0]
    return r.get("image") or r.get("path") if isinstance(r, dict) else r


def _tryon_lower(person, c, kind, handle_file):
    """Bas ou robe : Leffa (2025, modèle DressCode : jupes, shorts, pantalons, robes avec leur longueur), puis
    OOTDiffusion si Leffa ne répond pas (le refus pour quota épuisé est remonté tel quel, OOTDiffusion en demanderait plus)."""
    garment = handle_file(_garment_input(c))
    try:
        return _image_path(_tryon_call(TRYON_LOW_SPACE, handle_file(person), garment, False, 30, 2.5, 42, "dress_code", kind, False,
                                       api_name="/leffa_predict_vt"))
    except TryOnUnavailable as e:
        if "quota" in str(e):
            raise
    cat = "Lower-body" if kind == "lower_body" else "Dress"
    return _image_path(_tryon_call(TRYON_OOTD_SPACE, handle_file(person), garment, cat, 1, 20, 2.0, TRYON_OOTD_SEED,
                                   api_name="/process_dc"))


def _tryon_name(c):
    return (name_fr(c.get("name") or _garment_text(c).capitalize()) or c.get("name") or c.get("type") or c["id"]).lower()


# ---------------------------------------------------------------- tenue « inspirée » (sans quota GPU)
# Variante illimitée de l'essayage : Gemini décrit chaque photo (couleurs, matière, motif, coupe, longueur), puis FLUX
# (Cloudflare Workers AI, allocation gratuite quotidienne) génère une photo de mode de la tenue à partir de ces
# descriptions. Image inspirée des photos, pas copiée : moins fidèle que l'essayage, mais toujours disponible.
CF_FLUX_MODEL = os.environ.get("DRESSME_FLUX_MODEL", "@cf/black-forest-labs/flux-1-schnell")
INSPIRE_PERSON = {"Women": "a young woman with long straight black hair", "Men": "a young man with short dark hair"}
INSPIRE_DESC_PROMPT = ('Describe this garment so an image model can reproduce it faithfully when worn. Return JSON {"desc": "..."}: '
                       "one English phrase of 15-30 words: exact colours (shade), fabric look, pattern/print/graphics (position, "
                       "colours), cut, neckline, sleeves, length, fit, notable details. No brand guesses, no background.")


class InspireIn(BaseModel):
    item_ids: list[str]
    gender: Optional[str] = None


def _inspire_desc(c):
    """Description anglaise de la pièce vue par Gemini (mise en cache à côté des photos) ; à défaut, ses champs."""
    f = _garment_photo(c)
    rel = f"tryon/desc_{c['id']}_{int(f.stat().st_mtime)}.txt"
    if (STORE / rel).is_file():
        return (STORE / rel).read_text(encoding="utf-8")
    fallback = " ".join(str(x) for x in [*(c.get("colour") or [])[:2], c.get("pattern") if c.get("pattern") not in (None, "solid", "plain") else "",
                                           c.get("type") or c.get("name") or "garment"] if x).lower()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return fallback
    try:
        from PIL import Image
        models = [m.strip() for m in os.environ.get("GEMINI_VISION_MODELS", GEMINI_VISION_MODELS).split(",") if m.strip()]
        d = json.loads(GeminiVisionLLM(key, models).generate(Image.open(_garment_input(c)), INSPIRE_DESC_PROMPT,
                                                             "You describe garments precisely for an image generator."))["desc"]
        d = re.sub(r"\s+", " ", str(d)).strip()[:300]
    except Exception as e:   # quota Gemini, réponse illisible : description tirée de la fiche
        log(f"tenue inspirée : description Gemini indisponible ({type(e).__name__}: {str(e)[:150]})")
        return fallback
    (STORE / rel).parent.mkdir(parents=True, exist_ok=True)
    (STORE / rel).write_text(d, encoding="utf-8")
    return d


def _cf_keys():
    acc, tok = os.environ.get("CLOUDFLARE_ACCOUNT_ID"), os.environ.get("CLOUDFLARE_API_TOKEN")
    if not (acc and tok):
        raise HTTPException(501, "Tenue inspirée non activée : ajoutez CLOUDFLARE_ACCOUNT_ID et CLOUDFLARE_API_TOKEN dans gateway/.env.")
    return acc, tok


def _flux_image(prompt):
    """Image JPEG générée par FLUX sur Cloudflare Workers AI (CLOUDFLARE_ACCOUNT_ID + CLOUDFLARE_API_TOKEN)."""
    import base64
    import requests
    acc, tok = _cf_keys()
    try:
        r = requests.post(f"https://api.cloudflare.com/client/v4/accounts/{acc}/ai/run/{CF_FLUX_MODEL}",
                          headers={"Authorization": f"Bearer {tok}"}, json={"prompt": prompt, "steps": 8}, timeout=120)
    except requests.RequestException as e:
        log(f"tenue inspirée : Cloudflare injoignable ({type(e).__name__})")
        raise HTTPException(503, "Le service d'images est injoignable : réessayez plus tard.")
    if r.status_code != 200:
        log(f"tenue inspirée : Cloudflare {r.status_code} {r.text[:300]}")
        if r.status_code == 429 or "limit" in r.text.lower():
            raise HTTPException(503, "L'allocation gratuite du jour (Cloudflare) est épuisée : réessayez demain.")
        raise HTTPException(503 if r.status_code >= 500 else 502, "Le service d'images a refusé la demande (clés Cloudflare à vérifier).")
    return base64.b64decode(r.json()["result"]["image"])


@app.post("/outfits/inspire")
def outfit_inspire(body: InspireIn):
    import hashlib
    by_id = {c["id"]: c for c in catalog()}
    order = {"onepiece": 0, "outer": 1, "top": 2, "bottom": 3, "footwear": 4, "bag": 5, "accessory": 6}
    cards = sorted((by_id[i] for i in body.item_ids if i in by_id and _garment_photo(by_id[i])), key=lambda c: order.get(c["slot"], 9))
    if not cards:
        raise HTTPException(422, "Choisissez au moins une pièce avec photo.")
    _cf_keys()   # avant d'appeler Gemini : rien n'est consommé si la génération n'est pas activée
    gender = body.gender if body.gender in ("Women", "Men") else None
    if gender is None:
        g = [c.get("gender") for c in cards if c.get("gender") in ("Women", "Men")]
        gender = "Men" if g and g.count("Men") > g.count("Women") else "Women"
    descs = [_inspire_desc(c) for c in cards]
    prompt = (f"A single full-length photograph of one person only, front view, centered: {INSPIRE_PERSON[gender]}, "
              "head to toe with the shoes visible, standing straight facing the camera, arms relaxed, plain light grey studio "
              "background, soft natural light, photorealistic fashion catalog, sharp focus. Not a collage, no split screen, no "
              "back view. The outfit, exactly as described: " + "; ".join(descs) + ".")
    fp = hashlib.sha1(json.dumps([CF_FLUX_MODEL, prompt]).encode()).hexdigest()[:20]
    rel = f"tryon/inspire_{fp}.jpg"
    result = {"worn": [c["id"] for c in cards], "notWorn": [i for i in body.item_ids if i not in {c["id"] for c in cards}],
              "gender": gender, "note": None, "descriptions": descs}
    if not (STORE / rel).is_file():
        data = _flux_image(prompt)   # flux-1-schnell n'accepte pas de graine : allure du mannequin fixée par le texte
        (STORE / rel).parent.mkdir(parents=True, exist_ok=True)
        (STORE / rel).write_bytes(data)
        return {**result, "imageUrl": f"/files/{rel}{_file_version(rel)}", "cached": False}
    return {**result, "imageUrl": f"/files/{rel}{_file_version(rel)}", "cached": True}
