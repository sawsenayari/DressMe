"""Test de la passerelle avec un catalogue SYNTHÉTIQUE (embeddings tirés du pool Polyvore) : on teste les routes, pas la qualité."""
import json, os, shutil, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
if not (REPO / "obj5_profil" / "data" / "wardrobe.json").exists() or not (REPO / "obj2_compat" / "core.py").exists():
    import pytest; pytest.skip("obj2_compat / obj5_profil absents", allow_module_level=True)


def make_store(tmp):
    cat = json.load(open(REPO / "obj5_profil" / "data" / "wardrobe.json", encoding="utf-8"))
    cat = cat if isinstance(cat, list) else cat["items"]
    ref = np.load(REPO / "obj2_compat" / "reference.npz"); (tmp / "emb").mkdir()
    for k, c in enumerate(cat):
        v = ref["pool_img"][(k * 37) % len(ref["pool_img"])]; np.save(tmp / "emb" / f"{c['id']}.npy", v); c["embedding"] = f"emb/{c['id']}.npy"
    json.dump(cat, open(tmp / "wardrobe.json", "w", encoding="utf-8"))
    return tmp


def test_routes(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    monkeypatch.setenv("DRESSME_STORE", str(store)); monkeypatch.setenv("DRESSME_CATALOG", str(store / "wardrobe.json"))
    monkeypatch.setenv("DRESSME_PROFILE_MODEL", str(store / "style_model.joblib"))   # ne pas écraser le modèle versionné de l'Obj5
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    c = TestClient(g.app)
    h = c.get("/health").json(); assert h["ok"] and h["items_avec_embedding"] > 100
    items = c.get("/wardrobe/items").json(); assert items[0]["color"] is not None and items[0]["category"] == items[0]["slot"]
    ref = np.load(REPO / "obj2_compat" / "reference.npz")
    g.embed_photo = lambda data: (ref["pool_img"][5].astype(np.float32), "tops")     # remplace FashionCLIP
    r = c.post("/compatibility/score", files={"image": ("x.jpg", b"x", "image/jpeg")}); assert r.status_code == 200, r.text
    j = r.json(); assert 0 <= j["score"] <= 100 and j["verdict"] in ("compatible", "moyenne", "peu compatible") and "duplicate" in j
    p = c.get("/profile").json(); assert p["axis"] in ("efficiency", "economy", "brand", "mixte") and p["palette"]
    assert c.put("/profile", json={"axis": "economy", "budgetMode": True}).json()["budgetMode"] is True
    gp = c.get("/gaps"); assert gp.status_code in (200, 503)
    if gp.status_code == 200:
        assert all(g["slot"] == g["category"] and g["slot"] in ("top", "bottom", "onepiece", "outer", "footwear", "bag", "accessory") for g in gp.json())
    monkeypatch.setattr(g, "OBJ6_URL", "http://127.0.0.1:9")   # Obj6 absent (même si un vrai service tourne sur 8006)
    assert c.get("/outfits/today").status_code == 501
    monkeypatch.setattr(g, "OBJ1", tmp_path / "absent")                              # Obj1 non lançable -> 501
    r = c.post("/wardrobe/items", files={"image": ("x.jpg", b"x")}); assert r.status_code == 501 and "photos" in r.json()["detail"] and "Obj" not in r.json()["detail"]


def test_add_item_with_obj1_mock(tmp_path, monkeypatch):
    """photo -> Obj1 (mock : fiche valide, embedding factice) -> fiche + .npy + images ajoutées au catalogue, puis /compat et /profile."""
    import io
    from PIL import Image
    store = make_store(tmp_path)
    monkeypatch.setenv("DRESSME_OBJ1_MODE", "mock")
    monkeypatch.setenv("DRESSME_PROFILE_MODEL", str(store / "style_model.joblib"))
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "STORE", store); monkeypatch.setattr(g, "_cache", {})
    monkeypatch.setenv("DRESSME_CATALOG", str(store / "wardrobe.json")); monkeypatch.setenv("DRESSME_ASSETS_DIR", str(store))
    c = TestClient(g.app); n0 = len(c.get("/wardrobe/items").json())
    buf = io.BytesIO(); Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, "JPEG")
    r = c.post("/wardrobe/items", files={"image": ("veste.jpg", buf.getvalue(), "image/jpeg")}); assert r.status_code == 200, r.text
    it = r.json(); assert it["id"].startswith("it_") and it["status"] == "ok" and it["imageUrl"].startswith("/files/items/")
    card = next(x for x in json.load(open(store / "wardrobe.json", encoding="utf-8")) if x["id"] == it["id"])
    assert card["embedding"] == f"emb/{it['id']}.npy" and np.load(store / card["embedding"]).shape == (512,)
    assert (store / card["image"]).exists() and (store / card["image_crop"]).exists()
    assert len(c.get("/wardrobe/items").json()) == n0 + 1 and c.get("/profile").status_code == 200

def test_outfit_today_obj6_obj3_obj2(tmp_path, monkeypatch):
    """Obj6 remplacé par une fausse réponse HTTP ; jury Obj3 (règles) et compatibilité Obj2 réels -> type Outfit du front."""
    store = make_store(tmp_path)
    monkeypatch.setenv("DRESSME_PROFILE_MODEL", str(store / "style_model.joblib"))
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "STORE", store); monkeypatch.setattr(g, "_cache", {})
    c = TestClient(g.app)
    monkeypatch.setattr(g, "OBJ6_URL", "http://127.0.0.1:9")                              # Obj6 absent -> 501
    assert c.get("/outfits/today").status_code == 501
    cat = json.load(open(store / "wardrobe.json", encoding="utf-8"))
    pick = lambda s: next(x for x in cat if x["slot"] == s)
    sent = {}
    def fake(payload):
        sent.update(payload)
        o = lambda ids, sc: {"score": sc, "items": [{"id": i} for i in ids], "accessories": [], "reasons": ["Épaisseur adaptée"], "warnings": []}
        return {"context": {"feels_like": 21, "rain_prob": .1, "occasion": "work", "weather_source": "request"},
                "outfits": [o([pick("top")["id"], pick("bottom")["id"], pick("footwear")["id"]], .9), o([pick("onepiece")["id"], pick("footwear")["id"]], .8)]}
    monkeypatch.setattr(g, "obj6_recommend", fake)
    r = c.get("/outfits/today", params={"occasion": "work"}); assert r.status_code == 200, r.text
    out = r.json()
    assert sent["occasion"] == "work" and all(i["slot"] != "bag" for i in sent["wardrobe"]) and len(sent["wardrobe"]) == len(cat)
    assert out["items"] and all({"id", "slot", "imageUrl"} <= set(i) for i in out["items"])
    assert 0 <= out["compat01"] <= 1 and "jury de style" in out["reason"] and "Obj" not in out["reason"] and out["weather"]["temperatureC"] == 21
    assert c.get("/outfits/today", params={"occasion": "plage"}).status_code == 422


def test_outfit_judge_obj3_obj2(tmp_path, monkeypatch):
    """Tenue composée -> jury Obj3 (règles) et compatibilité Obj2 réels -> type OutfitJuryResult du front ; rien d'inventé."""
    monkeypatch.setenv("DRESSME_JURY_LLM", "0")   # règles seules, même si gateway/.env active le LLM
    store = make_store(tmp_path)
    monkeypatch.setenv("DRESSME_PROFILE_MODEL", str(store / "style_model.joblib"))
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "STORE", store); monkeypatch.setattr(g, "_cache", {})
    c = TestClient(g.app)
    cat = json.load(open(store / "wardrobe.json", encoding="utf-8"))
    card = lambda s: next(x for x in cat if x["slot"] == s)
    pick = lambda s: card(s)["id"]
    judge = lambda **kw: c.post("/outfits/judge", json={"occasion": "casual", **kw})

    r = judge(item_ids=[pick("top"), pick("bottom"), pick("footwear"), pick("accessory")], occasion="work", temperatureC=21, rain=False)
    assert r.status_code == 200, r.text
    o = r.json(); n = {"convient": 2, "a_ameliorer": 1, "deconseille": 0}[o["verdict"]]
    lo, hi = {2: (70, 100), 1: (40, 69), 0: (0, 39)}[n]                         # tranche du verdict, nuancée par les critères
    assert lo <= o["score"] <= hi and o["verdictLabel"] and ("À revoir" in o["rationale"] or "Rien à revoir" in o["rationale"]) and "/4" not in o["rationale"]
    assert o["judges"]["context"]["weatherLevel"] in (0, 1, 2) and o["judges"]["context"]["occasionLevel"] in (0, 1, 2)
    js = o["judges"]
    assert js["rules"]["status"] in ("pass", "warn", "fail") and js["rules"]["message"]
    assert js["visual"]["score01"] is None and js["visual"]["status"] == "unavailable" and "non activée" in js["visual"]["message"]
    assert js["llm"]["verdict"] == "non disponible" and "non activé" in js["llm"]["critique"]
    assert isinstance(js["context"]["matchWeather"], bool) and isinstance(js["context"]["matchOccasion"], bool)
    assert 0 <= js["compatibility"]["score01"] <= 1

    # une seule pièce, sans chaussures : réparations de l'Obj3, compatibilité absente, météo non évaluée sans température
    o = judge(item_ids=[pick("top")]).json()
    assert o["verdict"] != "convient" and o["score"] < 100 and o["repairs"]
    assert "score01" not in o["judges"]["compatibility"] and "Pas encore calculable" in o["judges"]["compatibility"]["message"]
    assert o["judges"]["context"]["matchWeather"] is None and o["judges"]["rules"]["status"] in ("warn", "fail")
    for rep in o["repairs"]:
        assert rep["reason"] and (rep["problemItemId"] or rep["suggestedReplacements"])
        assert all({"id", "slot", "imageUrl"} <= set(s) for s in rep["suggestedReplacements"])

    # un embedding manquant : compatibilité absente, pas de 500
    os.remove(store / card("top")["embedding"])
    o = judge(item_ids=[pick("top"), pick("bottom"), pick("footwear")], temperatureC=21).json()
    assert "score01" not in o["judges"]["compatibility"]

    assert judge(item_ids=[]).status_code == 422
    assert judge(item_ids=["inconnu"]).status_code == 422
    assert judge(item_ids=[pick("top")], occasion="plage").status_code == 422

def test_profile_small_wardrobe_uses_reference_model(tmp_path, monkeypatch):
    """Garde-robe sous le minimum de l'Obj5 (18 pièces) : profil calculé avec le modèle de référence ; sans lui, 503 (jamais 500)."""
    store = make_store(tmp_path)
    cat = json.load(open(store / "wardrobe.json", encoding="utf-8"))[:10]
    json.dump(cat, open(store / "wardrobe.json", "w", encoding="utf-8"))
    monkeypatch.setenv("DRESSME_PROFILE_MODEL", str(tmp_path / "absent.joblib"))
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "STORE", store); monkeypatch.setattr(g, "_cache", {})
    from dressme_profile import service as obj5
    class NoModel:                                                   # le service doit réentraîner (sinon un modèle d'un test précédent sert)
        @staticmethod
        def load(*a, **k): raise OSError("pas de modèle")
    monkeypatch.setattr(obj5, "StyleModel", NoModel)                 # le modèle de référence (clustering.StyleModel) reste chargeable
    ref = g.OBJ5_REF_MODEL.read_bytes()
    c = TestClient(g.app); r = c.get("/profile")
    assert r.status_code == 200 and r.json()["model"] == "référence" and r.json()["palette"], r.text
    assert g.OBJ5_REF_MODEL.read_bytes() == ref                                    # modèle versionné jamais réécrit
    monkeypatch.setattr(g, "OBJ5_REF_MODEL", tmp_path / "absent.joblib"); monkeypatch.setattr(g, "_cache", {})
    r = c.get("/profile"); assert r.status_code == 503 and "profil" in r.json()["detail"]

def _hf_cached(name):
    from pathlib import Path as P
    return (P.home() / ".cache" / "huggingface" / "hub" / ("models--" + name.replace("/", "--"))).exists()


def test_add_item_obj1_local_knn(tmp_path, monkeypatch):
    """Obj1 réel en mode kNN local (sans Kaggle ni LLM) : photo produit -> fiche ItemCard + vrai embedding FashionCLIP."""
    import pytest
    if not (_hf_cached("patrickjohncyh/fashion-clip") and _hf_cached("mattmdjaga/segformer_b2_clothes")
            and (REPO / "obj1_reconnaissance" / "data" / "agent_final" / "kb_emb.npy").exists()):
        pytest.skip("FashionCLIP / SegFormer non téléchargés ou base kNN de l'Obj1 absente")
    store = make_store(tmp_path)
    monkeypatch.setenv("DRESSME_OBJ1_MODE", "knn"); monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)   # vote des voisins seul : jamais d'appel réel à Gemini en test
    monkeypatch.setattr(g, "STORE", store); monkeypatch.setattr(g, "_cache", {})
    photo = (REPO / "frontend" / "public" / "images" / "cream-trousers.jpg").read_bytes()
    r = TestClient(g.app).post("/wardrobe/items", files={"image": ("p.jpg", photo, "image/jpeg")})
    assert r.status_code == 200, r.text
    it = r.json(); assert it["slot"] == "bottom" and it["source"] == "obj1.knn"
    v = np.load(store / f"emb/{it['id']}.npy"); assert v.shape == (512,) and abs(float(np.linalg.norm(v)) - 1) < 1e-3

def test_edit_and_delete_item(tmp_path, monkeypatch):
    """PUT corrige une fiche (validée, source user_corrected, saison autumn <-> fall) ; DELETE retire la fiche et ses fichiers."""
    store = make_store(tmp_path)
    monkeypatch.setenv("DRESSME_PROFILE_MODEL", str(store / "style_model.joblib"))
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "STORE", store); monkeypatch.setattr(g, "_cache", {})
    c = TestClient(g.app)
    first = c.get("/wardrobe/items").json()[0]; iid = first["id"]
    r = c.put(f"/wardrobe/items/{iid}", json={"name": "Veste noire", "slot": "outer", "colour": ["Black", "white"], "season": "autumn", "formality": 2})
    assert r.status_code == 200, r.text
    it = r.json(); assert it["name"] == "Veste noire" and it["slot"] == "outer" and it["colour"] == ["black", "white"] and it["season"] == "autumn"
    assert it["source"] == "user_corrected"
    card = next(x for x in json.load(open(store / "wardrobe.json", encoding="utf-8")) if x["id"] == iid)
    assert card["season"] == "fall" and card["formality"] == 2                       # contrat ItemCard conservé dans le store
    assert c.put(f"/wardrobe/items/{iid}", json={"slot": "chapeau"}).status_code == 422
    assert c.put(f"/wardrobe/items/{iid}", json={"formality": 9}).status_code == 422
    assert c.put("/wardrobe/items/inconnu", json={"name": "x"}).status_code == 404
    emb = store / card["embedding"]; assert emb.exists()
    n0 = len(c.get("/wardrobe/items").json())
    r = c.delete(f"/wardrobe/items/{iid}"); assert r.status_code == 200 and r.json()["items"] == n0 - 1
    assert not emb.exists() and iid not in {x["id"] for x in c.get("/wardrobe/items").json()}
    assert c.delete(f"/wardrobe/items/{iid}").status_code == 404

def test_outfit_agenda_exclusions_and_feedback(tmp_path, monkeypatch):
    """Today : agenda et tenues écartées transmis à l'Obj6 ; « Valider & Porter » relayé vers /api/feedback de l'Obj6."""
    store = make_store(tmp_path)
    monkeypatch.setenv("DRESSME_PROFILE_MODEL", str(store / "style_model.joblib"))
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "STORE", store); monkeypatch.setattr(g, "_cache", {})
    cat = json.load(open(store / "wardrobe.json", encoding="utf-8"))
    pick = lambda s: next(x for x in cat if x["slot"] == s)["id"]
    calls = []
    def fake(route, payload):
        calls.append((route, payload))
        if route == "/api/feedback":
            return {"stored": True, "feedback": 1, "accepted": int(payload["accepted"])}
        ids = [pick("top"), pick("bottom"), pick("footwear")]
        return {"context": {"feels_like": 18, "rain_prob": 0, "occasion": "work"},
                "outfits": [{"score": .9, "items": [{"id": i} for i in ids], "accessories": [], "reasons": [], "warnings": [], "features": {"warmth": 2.5}}]}
    monkeypatch.setattr(g, "_obj6_post", fake)
    c = TestClient(g.app)
    r = c.get("/outfits/today", params={"occasion": "work", "agenda": "réunion client", "exclude": "a,b;c,d"}); assert r.status_code == 200, r.text
    route, sent = calls[-1]
    assert route == "/api/recommend" and sent["agenda"] == "réunion client" and sent["exclude_outfits"] == [["a", "b"], ["c", "d"]] and sent["uid"] == "me"
    o = r.json(); assert o["excludeKey"] == [i["id"] for i in o["items"]] and o["features"] == {"warmth": 2.5} and o["excludedCount"] == 2
    r = c.post("/outfits/feedback", json={"item_ids": o["excludeKey"], "accepted": True, "features": o["features"]})
    assert r.status_code == 200 and calls[-1][0] == "/api/feedback" and calls[-1][1]["item_ids"] == o["excludeKey"] and calls[-1][1]["uid"] == "me"
    assert c.post("/outfits/feedback", json={"item_ids": ["x"], "accepted": False, "reason": "bof"}).status_code == 422
    assert c.post("/outfits/feedback", json={"item_ids": [], "accepted": True}).status_code == 422

def test_outfit_judge_with_llm(tmp_path, monkeypatch):
    """Outfit Studio avec le juge LLM de l'Obj3 (DRESSME_JURY_LLM=1) : faux LLM, arbitrage règles + LLM + hybride."""
    store = make_store(tmp_path)
    monkeypatch.setenv("DRESSME_PROFILE_MODEL", str(store / "style_model.joblib")); monkeypatch.setenv("DRESSME_JURY_LLM", "1")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)   # pas de vrai Gemini (juge visuel) pendant les tests
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "STORE", store); monkeypatch.setattr(g, "_cache", {})
    g.jury()
    from dressme import service as obj3
    class FakeLLM:
        def json_call(self, prompt, images=None):
            crit = {k: {"niveau": 2, "raison": "ok"} for k in ("couleurs", "formalite", "meteo", "coherence")}
            crit["couleurs"] = {"niveau": 1, "raison": "Bleu et gris un peu ternes ensemble."}
            return {"verdict": "à améliorer", "criteres": crit, "raisons": ["couleurs : Bleu et gris un peu ternes ensemble."]}
    monkeypatch.setattr(obj3, "build_llm", lambda *a, **k: FakeLLM())
    cat = json.load(open(store / "wardrobe.json", encoding="utf-8"))
    ids = [next(x for x in cat if x["slot"] == s)["id"] for s in ("top", "bottom", "footwear")]
    r = TestClient(g.app).post("/outfits/judge", json={"item_ids": ids, "occasion": "casual", "temperatureC": 20})
    assert r.status_code == 200, r.text
    j = r.json(); assert j["mode"] == "complet" and j["judges"]["llm"]["verdict"] != "non disponible", j
    assert "ternes" in j["judges"]["llm"]["critique"] and "Couleurs" in j["judges"]["llm"]["critique"] and "IA" in j["rationale"]
    monkeypatch.setattr(obj3, "build_llm", lambda *a, **k: None); monkeypatch.setattr(g, "_cache", {})   # pas de clé -> règles seules
    j = TestClient(g.app).post("/outfits/judge", json={"item_ids": ids, "occasion": "casual"}).json()
    assert j["mode"] == "regles" and j["judges"]["llm"]["verdict"] == "non disponible" and "IA" in j["judges"]["llm"]["critique"]


def test_outfit_judge_visual_with_fake_gemini(tmp_path, monkeypatch):
    """Juge visuel : planche des photos de la tenue -> judge_vision_v3 de l'Obj3 (faux client vision) ; avis informatif hors vote."""
    from PIL import Image
    store = make_store(tmp_path)
    monkeypatch.setenv("DRESSME_PROFILE_MODEL", str(store / "style_model.joblib")); monkeypatch.setenv("DRESSME_JURY_LLM", "0")
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "STORE", store); monkeypatch.setattr(g, "_cache", {})
    cat = json.load(open(store / "wardrobe.json", encoding="utf-8"))
    cards = [next(x for x in cat if x["slot"] == s) for s in ("top", "bottom", "footwear")]
    for k, c in enumerate(cards):                                            # vraies petites photos dans le store
        f = store / c["image_crop"]; f.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (120, 160), (40 * k, 90, 200)).save(f)
    seen = {}
    class FakeVision:
        vision = True
        def json_call(self, prompt, images=None):
            seen["prompt"], seen["images"] = prompt, images
            crit = {k: {"niveau": 2, "raison": "ok"} for k in ("couleurs", "formalite", "meteo", "coherence")}
            crit["couleurs"] = {"niveau": 1, "raison": "Le bleu vif écrase le reste."}
            return {"verdict": "convient", "criteres": crit, "_modele": "faux-gemini"}
    monkeypatch.setattr(g, "vision_llm", lambda: FakeVision())
    c = TestClient(g.app)
    j = c.post("/outfits/judge", json={"item_ids": [x["id"] for x in cards], "occasion": "casual", "temperatureC": 20}).json()
    v = j["judges"]["visual"]
    assert v["score01"] == 0.88 and v["status"] == "warn" and "bleu vif" in v["message"] and v["message"].startswith("Sur les photos : Couleurs")
    assert isinstance(seen["images"][0], Image.Image) and seen["images"][0].width > 300 and "image montre" in seen["prompt"]
    monkeypatch.setattr(g, "vision_llm", lambda: None)                      # sans Gemini : raison affichée
    v = c.post("/outfits/judge", json={"item_ids": [x["id"] for x in cards], "occasion": "casual"}).json()["judges"]["visual"]
    assert v["score01"] is None and v["status"] == "unavailable" and "non activée" in v["message"]

def test_add_item_obj1_full_with_fake_gemini(tmp_path, monkeypatch):
    """Obj1 en mode complet (Gemini voit la photo à la place de Qwen) : faux Gemini -> fiche reconnue par le LLM (source obj1.llm)."""
    import pytest
    if not (_hf_cached("patrickjohncyh/fashion-clip") and _hf_cached("mattmdjaga/segformer_b2_clothes")
            and (REPO / "obj1_reconnaissance" / "data" / "agent_final" / "kb_emb.npy").exists()):
        pytest.skip("FashionCLIP / SegFormer non téléchargés ou base kNN de l'Obj1 absente")
    store = make_store(tmp_path)
    monkeypatch.setenv("DRESSME_OBJ1_MODE", "knn"); monkeypatch.setenv("HF_HUB_OFFLINE", "1"); monkeypatch.setenv("GEMINI_API_KEY", "faux")
    monkeypatch.setenv("DRESSME_OBJ1_CACHE", str(tmp_path / "cache.jsonl"))   # jamais le vrai cache de l'Obj1
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    seen = []
    class FakeGemini:
        def __init__(self, key, models): self.models = models
        def generate(self, image, prompt, system=None):
            seen.append(image.size)
            return json.dumps({"evidence": "pantalon large crème", "category": "pants", "alternative": "jeans", "color": "beige",
                               "gender": "female", "season": "all_season", "occasion": "casual", "confidence": 0.93})
    monkeypatch.setattr(g, "GeminiVisionLLM", FakeGemini)
    monkeypatch.setattr(g, "STORE", store); monkeypatch.setattr(g, "_cache", {})
    photo = (REPO / "frontend" / "public" / "images" / "cream-trousers.jpg").read_bytes()
    r = TestClient(g.app).post("/wardrobe/items", files={"image": ("p.jpg", photo, "image/jpeg")})
    assert r.status_code == 200, r.text
    it = r.json(); assert it["slot"] == "bottom" and it["colour"] == ["beige"] and it["source"] == "obj1.llm" and seen
