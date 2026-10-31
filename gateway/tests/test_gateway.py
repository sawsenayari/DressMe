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
    assert c.get("/gaps").status_code in (200, 503)
    assert c.get("/outfits/today").status_code == 501 and c.post("/wardrobe/items", files={"image": ("x.jpg", b"x")}).status_code == 501
