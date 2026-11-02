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
    assert {"ia", "shopping", "tenueDuJour"} <= set(h)                                  # état des services affiché dans le menu
    # noms anglais générés par l'Obj1 -> français (accords) ; nom saisi par l'utilisateur inchangé
    assert (g.name_fr("Grey pants"), g.name_fr("Blue shirt"), g.name_fr("White shoes")) == ("Pantalon gris", "Chemise bleue", "Chaussures blanches")
    assert g.name_fr("White traditional garment") == "Tenue traditionnelle blanche" and g.name_fr("panta djean") is None
    items = c.get("/wardrobe/items").json(); assert items[0]["color"] is not None and items[0]["category"] == items[0]["slot"]
    ref = np.load(REPO / "obj2_compat" / "reference.npz")
    g.embed_photo = lambda data: (ref["pool_img"][5].astype(np.float32), "tops")     # remplace FashionCLIP
    r = c.post("/compatibility/score", files={"image": ("x.jpg", b"x", "image/jpeg")}); assert r.status_code == 200, r.text
    j = r.json(); assert 0 <= j["score"] <= 100 and j["verdict"] in ("compatible", "moyenne", "peu compatible") and "duplicate" in j
    # /pairs de l'Obj2 : accord avec chaque pièce d'une autre catégorie, verdicts calibrés, triés ; pièces à éviter
    assert j["category"] == j["guessedCategory"] == "tops" and "bottoms" in j["categories"] and j["compared"] >= 2
    sc = [x["pair_score01"] for x in j["pairs"]]; assert sc == sorted(sc, reverse=True) and j["pairs"]
    assert all(x["verdict"] in ("va bien", "moyen", "à éviter") for x in j["pairs"])
    assert all(x["verdict"] == "à éviter" for x in j["clashing"]) and j["newOutfits"] == sum(x["verdict"] == "va bien" for x in j["pairs"])
    r = c.post("/compatibility/score", files={"image": ("x.jpg", b"x", "image/jpeg")}, data={"category": "shoes"})
    assert r.status_code == 200 and r.json()["category"] == "shoes" and r.json()["guessedCategory"] == "tops"   # catégorie corrigée
    assert c.post("/compatibility/score", files={"image": ("x.jpg", b"x", "image/jpeg")}, data={"category": "zz"}).status_code == 422
    p = c.get("/profile").json(); assert p["axis"] in ("efficiency", "economy", "brand", "mixte") and p["palette"]
    assert p["axis"] == p["persona"]                                                    # orientation calculée par l'Obj5
    # palette = part des pièces par couleur (pas la confiance de l'Obj1) : triée, cohérente avec le nombre de pièces
    pal = p["palette"]; assert [x["weight"] for x in pal] == sorted((x["weight"] for x in pal), reverse=True)
    cat = c.get("/wardrobe/items").json()
    assert pal[0]["pieces"] == sum(pal[0]["color"] in (i.get("colour") or []) for i in cat)
    assert p["dominantPieces"] and {d["id"] for d in p["dominantPieces"]} <= {i["id"] for i in cat}   # style dominant = vos pièces
    assert {"slotCounts", "nItems", "nItemsUsed", "notes", "dominantShare", "space"} <= set(p)
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
    # suggestions de l'Obj5 : pièces du catalogue de référence hors garde-robe, une par apparence, classées selon l'orientation
    owned = {x["id"] for x in cat}
    r = c.get("/profile/recommendations", params={"k": 5}); assert r.status_code == 200, r.text
    items = r.json()["items"]; assert 0 < len(items) <= 5 and not owned & {x["id"] for x in items}
    assert len({(x["name"], x["type"], tuple(x["colour"])) for x in items}) == len(items)
    shoes = c.get("/profile/recommendations", params={"slot": "footwear", "k": 3, "gender": "Women"}).json()
    assert shoes["gender"] == "Women" and all(x["slot"] == "footwear" for x in shoes["items"])
    assert c.get("/profile/recommendations").json()["axis"] in ("efficiency", "economy", "brand", "mixte")
    assert c.get("/profile/recommendations", params={"slot": "chapeau"}).status_code == 422
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
    for occ, o6 in (("sport", "sport"), ("ceremony", "wedding")):   # contextes du filtre unique de Today
        assert c.get("/outfits/today", params={"occasion": occ}).status_code == 200 and calls[-1][1]["occasion"] == o6

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


def test_outfit_recommend_full_screen(tmp_path, monkeypatch):
    """Écran Today complet : genre, ville, agenda (agent), envies, explications, contexte, avertissements, étapes, 3 tenues."""
    store = make_store(tmp_path)
    monkeypatch.setenv("DRESSME_PROFILE_MODEL", str(store / "style_model.joblib"))
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "STORE", store); monkeypatch.setattr(g, "_cache", {})
    cat = json.load(open(store / "wardrobe.json", encoding="utf-8"))
    women = [x for x in cat if (x.get("gender") or "Unisex") in ("Women", "Unisex")]
    by = lambda s, n: [x["id"] for x in women if x["slot"] == s][n]
    looks = [[by("top", n), by("bottom", n), by("footwear", n)] for n in range(4)]
    calls, parsed = [], []
    def fake(route, payload):
        calls.append((route, payload))
        outs = [{"score": .9 - .1 * n, "items": [{"id": i} for i in ids], "accessories": [], "reasons": ["Épaisseur adaptée à 18°C"],
                 "warnings": ["Pas assez habillée"] if n == 1 else [], "features": {"warmth": 2.0}, "explanation": "Joli." if payload["explain"] else None}
                for n, ids in enumerate(looks) if ids not in payload["exclude_outfits"]]
        return {"context": {"feels_like": 18.4, "rain_prob": .2, "occasion": "wedding", "formality": 3, "agenda_source": "llm+rag",
                            "retrieved": ["mariage tunisien"], "agenda_error": None, "prefs_relaxed": bool(payload["colours"]),
                            "weather_source": "open-meteo"}, "outfits": outs}
    monkeypatch.setattr(g, "_obj6_post", fake)
    monkeypatch.setattr(g, "obj6_parse", lambda text: parsed.append(text) or "llm+rag")
    c = TestClient(g.app)
    opt = c.get("/outfits/options", params={"gender": "Women"}).json()
    assert opt["cities"] == g.OBJ6_CITIES and opt["colours"] and opt["types"]
    r = c.post("/outfits/recommend", json={"gender": "Women", "city": "Sousse", "agenda": "mariage ce soir", "explain": True,
                                            "types": ["Tops"]})
    assert r.status_code == 200, r.text
    j = r.json(); route, sent = calls[-1]
    assert route == "/api/recommend" and sent["city"] == "Sousse" and sent["types"] == ["Tops"] and sent["explain"] and parsed == ["mariage ce soir"]
    assert all(it["gender"] in ("Women", "Unisex") for it in sent["wardrobe"])
    x = j["context"]
    assert (x["temperatureC"], x["rainPct"], x["occasion"], x["formality"], x["agent"], x["rag"]) == (18, 20, "mariage", 3, "IA + fiches locales", ["mariage tunisien"])
    assert len(j["outfits"]) == 3 and j["outfits"][0]["explanation"] == "Joli." and not j["warnings"]
    assert [s["label"].split(" (")[0] for s in j["steps"]][0] == "Lecture de l'agenda" and len(j["steps"]) == 4
    assert any("Pas assez habillée" in o["alerts"] for o in j["outfits"])
    # « Une autre » : tenues déjà vues exclues ; envies impossibles et garde-robe juste signalées
    r = c.post("/outfits/recommend", json={"gender": "Women", "colours": ["red"], "k": 3, "exclude_outfits": looks[:2]}).json()
    assert len(r["outfits"]) == 2 and r["context"]["agent"] is None and len(r["steps"]) == 3
    assert any("envies" in w for w in r["warnings"]) and any("Garde-robe insuffisante" in w for w in r["warnings"])
    assert c.post("/outfits/recommend", json={"exclude_outfits": looks}).json()["message"]
    assert c.post("/outfits/recommend", json={"city": "Paris"}).status_code == 422
    assert c.post("/outfits/recommend", json={"gender": "X"}).status_code == 422


def test_weather(monkeypatch):
    """Météo du jour : réponse Open-Meteo simulée ; service injoignable -> available False (pas d'erreur)."""
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g, httpx
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "_weather_cache", {})
    class R:
        def raise_for_status(self): pass
        def json(self): return {"current": {"temperature_2m": 21.4, "apparent_temperature": 20.6, "wind_speed_10m": 9.8},
                                "daily": {"precipitation_probability_max": [35]}}
    monkeypatch.setattr(httpx, "get", lambda *a, **k: R())
    c = TestClient(g.app)
    assert c.get("/weather", params={"city": "Sfax"}).json() == {"city": "Sfax", "available": True, "temperatureC": 21,
                                                                 "feelsLikeC": 21, "windKmh": 10, "rainPct": 35}
    def down(*a, **k): raise httpx.ConnectError("hors ligne")
    monkeypatch.setattr(httpx, "get", down)
    assert c.get("/weather", params={"city": "Djerba"}).json() == {"city": "Djerba", "available": False}
    assert c.get("/weather", params={"city": "Paris"}).status_code == 422


def test_gaps_analysis_and_shopping(tmp_path, monkeypatch):
    """Obj4 sur la garde-robe : candidats (IA simulée, puis liste de base sans clé), proxy de même catégorie, scores Obj2,
    gains prudent/optimiste triés et contrat de l'Obj4 respecté ; « Où l'acheter ? » sans clé -> 503, avec recherche simulée."""
    store = make_store(tmp_path)
    cat = json.load(open(store / "wardrobe.json", encoding="utf-8"))
    keep = [x for n, sl in ((8, "top"), (8, "bottom"), (6, "footwear"), (2, "outer")) for x in [y for y in cat if y["slot"] == sl][:n]]
    json.dump(keep, open(store / "wardrobe.json", "w", encoding="utf-8"))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False); monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("DRESSME_TAVILY_API_KEY", raising=False)
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "STORE", store); monkeypatch.setattr(g, "_cache", {})
    for k in ("GEMINI_API_KEY", "LLM_API_KEY", "DRESSME_TAVILY_API_KEY"):   # gateway/.env rechargé à l'import : aucune vraie clé
        monkeypatch.delenv(k, raising=False)
    c = TestClient(g.app)
    d = c.get("/gaps").json()
    assert d["mode"] == "analyse" and d["source"] == "base" and d["outfitsNow"]["lower"] <= d["outfitsNow"]["upper"]
    gaps = d["gaps"]; assert gaps and [x["rank"] for x in gaps] == list(range(1, len(gaps) + 1))
    assert all(0 <= x["gain_lower"] <= x["gain_likely"] <= x["gain_upper"] for x in gaps)          # estimé entre les bornes
    key = lambda x: (-x["gain_likely"], -x["gain_upper"], -x["gain_lower"])
    assert [key(x) for x in gaps] == sorted(key(x) for x in gaps)                                   # classé sur l'estimé
    o = d["outfitsNow"]; assert o["lower"] <= o["likely"] <= o["upper"] and d["shoppingEnabled"] is False
    assert all(isinstance(x["proxyColourDiffers"], bool) for x in gaps)
    ids = {x["id"] for x in keep}
    assert all(x["proxy"]["id"] in ids and x["proxy"]["slot"] == x["slot"] for x in gaps)          # proxy de même catégorie
    assert len({x["proxy"]["id"] for x in gaps}) == len(gaps)                                       # jamais deux fois le même
    assert any(u["slot"] in ("bag", "onepiece") for u in d["unscorable"])                          # catégorie absente : non chiffrée
    # IA (simulée) : ses candidats remplacent la liste de base ; refresh redemande
    monkeypatch.setattr(g, "_gap_llm_candidates", lambda items, n=6: ([
        {"item_id": "candidate-001", "slot": "shoes", "description": "baskets blanches", "rationale": "Neutres."},
        {"item_id": "candidate-002", "slot": "bag", "description": "Ceinture en cuir marron", "rationale": "x"}], "faux-modele"))
    d = c.get("/gaps", params={"refresh": True}).json()
    assert d["source"] == "ia" and d["model"] == "faux-modele" and [x["slot"] for x in d["gaps"]] == ["footwear"]
    assert d["unscorable"] == [{"description": "Ceinture en cuir marron", "slot": "accessory", "rationale": "x"}]   # accessoire
    # « Où l'acheter ? »
    r = c.get("/gaps/shopping", params={"description": "baskets blanches"}); assert r.status_code == 503
    monkeypatch.setenv("DRESSME_TAVILY_API_KEY", "faux")
    monkeypatch.setattr(g, "_cache", {})
    assert c.get("/gaps").json()["shoppingEnabled"] is True
    import dressme_gap_agent.shopping as shop
    sent = []
    def fake_search(gap, cfg, max_results=5, max_price=None):
        sent.append(shop._search_query(gap))   # requête Tavily construite par l'Obj4
        return [{"title": "Baskets", "url": "https://exemple.tn/b", "snippet": "…", "price": 89.0, "currency": "TND", "source": "x"}]
    monkeypatch.setattr(shop, "search_gap", fake_search)
    r = c.get("/gaps/shopping", params={"description": "baskets blanches", "max_price": 100}).json()
    assert sent == ["baskets blanches buy online"]
    assert r["options"][0]["price"] == 89.0 and r["options"][0]["url"].startswith("https://")
    assert c.get("/gaps/shopping", params={"description": " "}).status_code == 422
    # comptage : chaque veste compatible donne une tenue (l'Obj4 plafonnait à « avec ou sans veste »)
    items = [{"item_id": i, "slot": sl} for i, sl in (("t", "top"), ("b", "bottom"), ("s", "footwear"), ("o", "outer"), ("o2", "outer"))]
    J = {tuple(sorted(p)): "compatible" for p in [("t", "b"), ("t", "s"), ("b", "s")] + [(o, x) for o in ("o", "o2") for x in "tbs"]}
    assert g._count_outfits(items, J, False) == 3 and g._count_outfits(items[:4], J, False) == 2


def test_crop_photo_then_add(tmp_path, monkeypatch):
    """Découpage de l'Obj6 (simulé, sans modèle) : photo portée -> une image par vêtement (morceaux isolés retirés),
    photo propre -> needed False, photo à plat sur fond chargé -> détourée ; puis ajout avec la pièce choisie."""
    import io, types
    from PIL import Image
    store = make_store(tmp_path)
    monkeypatch.setenv("DRESSME_OBJ1_MODE", "mock")
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "STORE", store); monkeypatch.setattr(g, "_cache", {})
    real = g._obj6_segment()                                       # vrai module de l'Obj6 : PARTS, PERSON et _cut réels
    labels = {0: "Background", 1: "Upper-clothes", 2: "Pants", 3: "Face"}
    state = {"seg": None}
    fake = types.SimpleNamespace(PARTS=real.PARTS, PERSON=real.PERSON, _cut=real._cut,
                                 _segment=lambda img: (state["seg"], labels),
                                 cutout=lambda img: img.crop((10, 10, 60, 60)))
    g._cache["seg6"] = fake
    c = TestClient(g.app)
    def jpg(colour, bg=None):
        im = Image.new("RGB", (100, 100), bg or colour)
        if bg: im.paste(colour, (30, 30, 70, 70))
        b = io.BytesIO(); im.save(b, "JPEG"); return b.getvalue()
    seg = np.zeros((100, 100), int); seg[0:10, 40:60] = 3; seg[10:50, 20:80] = 1; seg[50:95, 30:70] = 2; seg[97:99, 0:2] = 1   # morceau isolé
    state["seg"] = seg
    j = c.post("/wardrobe/crop", files={"image": ("p.jpg", jpg((90, 90, 200)), "image/jpeg")}).json()
    assert j["needed"] and j["kind"] == "portée" and [p["slot"] for p in j["parts"]] == ["top", "bottom"]
    assert all(p["image"].startswith("data:image/jpeg;base64,") for p in j["parts"])
    state["seg"] = np.zeros((100, 100), int)                                                    # pas de personne
    assert c.post("/wardrobe/crop", files={"image": ("p.jpg", jpg((250, 250, 250)), "image/jpeg")}).json() == {"needed": False, "kind": "propre", "parts": []}
    j = c.post("/wardrobe/crop", files={"image": ("p.jpg", jpg((200, 30, 30), bg=(120, 90, 60)), "image/jpeg")}).json()
    assert j["needed"] and j["kind"] == "à plat" and j["parts"][0]["part"] == "photo"
    assert c.post("/wardrobe/crop", files={"image": ("x.jpg", b"pas une image", "image/jpeg")}).status_code == 422
    # ajout : photo d'origine + pièce choisie (analysée telle quelle)
    import base64
    piece = base64.b64decode(j["parts"][0]["image"].split(",", 1)[1])
    r = c.post("/wardrobe/items", files={"image": ("o.jpg", jpg((200, 30, 30), bg=(120, 90, 60)), "image/jpeg"),
                                         "crop": ("piece.jpg", piece, "image/jpeg")}, data={"slot_hint": "top"})
    assert r.status_code == 200, r.text
    card = next(x for x in json.load(open(store / "wardrobe.json", encoding="utf-8")) if x["id"] == r.json()["id"])
    assert (store / card["image"]).exists() and (store / card["image_crop"]).exists()
