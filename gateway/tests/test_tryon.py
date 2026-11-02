"""Essayage réaliste : enchaînement haut puis bas, cache, résultat partiel quand le quota GPU gratuit est épuisé (modèles simulés)."""
import json, sys
from pathlib import Path
from PIL import Image
REPO = Path(__file__).resolve().parents[2]


def make_store(tmp):
    (tmp / "items").mkdir()
    cards = [{"id": "t1", "slot": "top", "type": "shirt", "colour": ["blue"], "gender": "Men"},
             {"id": "b1", "slot": "bottom", "type": "pants", "colour": ["grey"], "gender": "Men"},
             {"id": "s1", "slot": "footwear", "type": "sneakers", "gender": "Men"}]
    for c in cards:
        Image.new("RGB", (40, 40), "white").save(tmp / "items" / f"{c['id']}_raw.jpg"); c["image"] = f"items/{c['id']}_raw.jpg"
    json.dump(cards, open(tmp / "wardrobe.json", "w", encoding="utf-8"))
    return tmp


def test_tryon_chain_cache_and_partial(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "LEGACY_STORE", store); monkeypatch.setattr(g, "_cache", {})
    calls = []

    def fake_call(space, *args, api_name):
        calls.append((space, api_name))
        out = tmp_path / f"step{len(calls)}.png"; Image.new("RGB", (30, 40), "pink").save(out)
        if api_name == "/tryon":
            assert args[2] == "blue shirt"
            return [str(out), "mask"]
        assert "mannequin_" in args[0]["path"]                     # le bas est posé sur la photo du mannequin
        if api_name == "/leffa_predict_vt":
            assert args[6:8] == ("dress_code", "lower_body")
            return (str(out), "masque", "densepose")
        return [{"image": str(out), "caption": None}]                 # OOTDiffusion (secours)
    monkeypatch.setattr(g, "_tryon_call", fake_call)
    c = TestClient(g.app)
    assert c.post("/outfits/tryon", json={"item_ids": ["s1"]}).status_code == 422          # rien à « porter »
    r = c.post("/outfits/tryon", json={"item_ids": ["t1", "b1", "s1"]}).json()
    assert [a for _, a in calls] == ["/leffa_predict_vt", "/tryon"] and r["worn"] == ["b1", "t1"] and r["notWorn"] == ["s1"]
    assert r["note"] is None and not r["cached"] and c.get(r["imageUrl"]).status_code == 200
    assert c.post("/outfits/tryon", json={"item_ids": ["t1", "b1", "s1"]}).json()["cached"] and len(calls) == 2   # cache

    def no_quota(space, *args, api_name):     # haut refusé faute de quota : le bas déjà porté est quand même montré
        if api_name == "/tryon":
            raise g.TryOnUnavailable("Le quota gratuit de calcul (Hugging Face) est épuisé.")
        return fake_call(space, *args, api_name=api_name)
    monkeypatch.setattr(g, "_tryon_call", no_quota)
    r = c.post("/outfits/tryon", json={"item_ids": ["t1", "b1"], "gender": "Women"}).json()   # autre mannequin : pas en cache
    assert r["worn"] == ["b1"] and "partiel" in r["note"] and "chemise bleue" in r["note"] and "_partiel" in r["imageUrl"]
    monkeypatch.setattr(g, "_tryon_call", lambda *a, **k: (_ for _ in ()).throw(g.TryOnUnavailable("quota épuisé")))
    r = c.post("/outfits/tryon", json={"item_ids": ["t1"]}); assert r.status_code == 503 and "quota" in r.json()["detail"]
    monkeypatch.setattr(g, "_tryon_call", lambda space, *a, api_name: (_ for _ in ()).throw(g.TryOnUnavailable("quota épuisé"))
                        if api_name == "/leffa_predict_vt" else fake_call(space, *a, api_name=api_name))
    r = c.post("/outfits/tryon", json={"item_ids": ["t1", "b1"], "gender": "Women"}).json()   # bas refusé : le haut est quand même porté
    assert r["worn"] == ["t1"] and "pantalon gris" in r["note"]


def test_tryon_falls_back_to_ootdiffusion(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "LEGACY_STORE", store); monkeypatch.setattr(g, "_cache", {})
    calls = []

    def fake_call(space, *args, api_name):     # Leffa en panne (hors quota) : OOTDiffusion pose le bas
        calls.append(api_name)
        if api_name == "/leffa_predict_vt":
            raise g.TryOnUnavailable("Le service d'essayage est momentanément indisponible.")
        out = tmp_path / f"o{len(calls)}.png"; Image.new("RGB", (30, 40)).save(out)
        return [{"image": str(out), "caption": None}]
    monkeypatch.setattr(g, "_tryon_call", fake_call)
    r = TestClient(g.app).post("/outfits/tryon", json={"item_ids": ["b1"]}).json()
    assert calls == ["/leffa_predict_vt", "/process_dc"] and r["worn"] == ["b1"] and r["note"] is None
