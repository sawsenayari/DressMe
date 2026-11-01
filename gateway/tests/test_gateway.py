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
    assert c.get("/outfits/today").status_code == 501
    monkeypatch.setattr(g, "OBJ1", tmp_path / "absent")                              # Obj1 non lançable -> 501
    r = c.post("/wardrobe/items", files={"image": ("x.jpg", b"x")}); assert r.status_code == 501 and "Objectif 1" in r.json()["detail"]


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
    assert 0 <= out["compat01"] <= 1 and "Jury (Obj3)" in out["reason"] and out["weather"]["temperatureC"] == 21
    assert c.get("/outfits/today", params={"occasion": "plage"}).status_code == 422
