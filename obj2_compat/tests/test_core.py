import os, sys, numpy as np, torch, torch.nn as nn
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import CompatEngine

E = CompatEngine()
REF = np.load(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reference.npz"))
def item(k, i):  # article du pool de référence (embeddings réels FashionCLIP de Polyvore)
    return {"id": i, "embedding": REF["pool_img"][k].tolist(), "category": E.cats[int(REF["pool_cat"][k])]}
def of_cat(cat, n, off=0):
    idx = np.where(REF["pool_cat"] == E.cid[cat])[0]; return [item(int(idx[off + j]), f"{cat}{off+j}") for j in range(n)]

# --- code d'origine (regen_3) recopié tel quel : forward par broadcasting
class OrigEnc(nn.Module):
    def __init__(s, d, h=256):
        super().__init__(); s.proj = nn.Sequential(nn.Linear(d, h), nn.GELU(), nn.Dropout(0.1), nn.Linear(h, h)); s.cat = nn.Embedding(12, h)
    def forward(s, f, c): return s.proj(f) + s.cat(c)
class OrigPairMLP(nn.Module):
    def __init__(s, d, h=256):
        super().__init__(); s.enc = OrigEnc(d, h)
        s.pair = nn.Sequential(nn.Linear(2 * h, h), nn.GELU(), nn.Dropout(0.1), nn.Linear(h, 1))
    def forward(s, f, c, m):
        z = s.enc(f, c); L = z.size(1); zi, zj = z.unsqueeze(2), z.unsqueeze(1)
        p = s.pair(torch.cat([zi * zj, (zi - zj).abs()], -1)).squeeze(-1)
        pm = (m.unsqueeze(2) & m.unsqueeze(1)) & ~torch.eye(L, dtype=torch.bool, device=m.device)
        return (p * pm).sum((1, 2)) / pm.sum((1, 2)).clamp(min=1)

def test_equivalence_avec_le_code_d_origine():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ck = torch.load(os.path.join(base, "models", "final_image_s0.pt"), map_location="cpu")
    o = OrigPairMLP(ck["d"]); o.load_state_dict(ck["state"]); o.eval()
    f = torch.tensor(REF["pool_img"][:40].reshape(8, 5, 512)); c = torch.tensor(REF["pool_cat"][:40].reshape(8, 5))
    m = torch.ones(8, 5, dtype=torch.bool)
    with torch.no_grad(): a = o(f, c, m); b = E.models[0](f, c, m)
    assert torch.allclose(a, b, atol=1e-5), (a - b).abs().max()

def test_schema_et_bornes():
    W = of_cat("tops", 2) + of_cat("bottoms", 2) + of_cat("shoes", 1)
    r = E.compat(of_cat("bags", 1, 50)[0], W)
    assert set(r) == {"rank100", "score01", "verdict", "partners", "duplicate", "model"}
    assert 0 <= r["rank100"] <= 100 and r["score01"] == r["rank100"] / 100
    assert r["verdict"] in {"compatible", "moyenne", "peu compatible"}
    assert len(r["partners"]) == 2 and set(r["duplicate"]) == {"id", "similarity", "pct", "is_duplicate"}

def test_verdict_coherent_avec_rang():
    for k in range(5):
        W = of_cat("tops", 2, k) + of_cat("bottoms", 2, k) + of_cat("shoes", 1, k)
        r = E.compat(of_cat("outerwear", 1, 20 + k)[0], W)
        want = "compatible" if r["rank100"] >= 70 else ("moyenne" if r["rank100"] >= 40 else "peu compatible")
        assert r["verdict"] == want

def test_doublon_detecte():
    W = of_cat("tops", 2) + of_cat("bottoms", 2)
    cand = dict(W[0]); cand["id"] = "copie"
    r = E.compat(cand, W)
    assert r["duplicate"]["id"] == W[0]["id"] and r["duplicate"]["is_duplicate"] and r["duplicate"]["similarity"] > 0.99

def test_non_doublon_pour_article_different():
    W = of_cat("tops", 2) + of_cat("bottoms", 2)
    r = E.compat(of_cat("shoes", 1, 99)[0], W)
    assert not r["duplicate"]["is_duplicate"]

def test_deterministe():
    W = of_cat("tops", 3) + of_cat("shoes", 2)
    c = of_cat("bags", 1, 7)[0]
    assert E.compat(c, W) == E.compat(c, W)

def test_pairs_forme_et_symetrie():
    A = of_cat("tops", 2); B = of_cat("bottoms", 3)
    s = E.pairs(A, B); s2 = E.pairs(B, A)
    assert len(s) == 2 and len(s[0]) == 3 and all(0 <= v <= 1 for r in s for v in r)
    assert np.allclose(np.array(s), np.array(s2).T, atol=0.01)

def test_erreurs_claires():
    import pytest
    W = of_cat("tops", 2)
    with pytest.raises(ValueError): E.compat({"id": "x", "embedding": [0.0] * 512, "category": "tops"}, W)
    with pytest.raises(ValueError): E.compat({"id": "x", "embedding": [1.0] * 10, "category": "tops"}, W)
    with pytest.raises(ValueError): E.compat({"id": "x", "embedding": [1.0] * 512, "category": "robe"}, W)
    assert "error" in E.compat(of_cat("bags", 1)[0], W[:1])

def test_slot_donne_categorie():
    it = {"id": "a", "embedding": REF["pool_img"][0].tolist(), "slot": "footwear"}
    assert E.category_of(it) == "shoes"

def test_api():
    from fastapi.testclient import TestClient
    from app import app
    c = TestClient(app); assert c.get("/health").json()["ok"]
    W = of_cat("tops", 2) + of_cat("bottoms", 2)
    r = c.post("/compat", json={"candidate": of_cat("shoes", 1)[0], "wardrobe": W}); assert r.status_code == 200 and "rank100" in r.json()
    r = c.post("/pairs", json={"a": of_cat("tops", 2), "b": of_cat("bottoms", 2)}); assert r.status_code == 200 and len(r.json()["scores01"]) == 2 and len(r.json()["verdicts"][0]) == 2
    assert c.post("/compat", json={"candidate": of_cat("shoes", 1)[0], "wardrobe": W[:1]}).status_code == 422

def test_verdict_paires():
    from core import pair_verdict
    assert pair_verdict(0.9) == "va bien" and pair_verdict(0.75) == "va bien"
    assert pair_verdict(0.5) == "moyen" and pair_verdict(0.35) == "moyen"
    assert pair_verdict(0.1) == "peu probable"

def test_store_ids_et_chemin_d_embedding(tmp_path):
    import json
    from core import CardStore
    (tmp_path / "emb").mkdir()
    cards = []
    for n, (k, slot) in enumerate([(0, "top"), (1, "bottom"), (2, "footwear"), (3, "top")]):
        cid = f"c{n}"; np.save(tmp_path / "emb" / f"{cid}.npy", REF["pool_img"][k * 700])
        c = {"id": cid, "slot": slot, "embedding": f"emb/{cid}.npy"}; cards.append(c)
        json.dump(c, open(tmp_path / f"{cid}.json", "w"))
    e = CompatEngine(store=CardStore(str(tmp_path)))
    r = e.compat("c0", ["c1", "c2", "c3"])           # identifiants
    assert 0 <= r["rank100"] <= 100 and all("pair_score01" in p and 0 <= p["pair_score01"] <= 1 for p in r["partners"])
    assert e.compat(cards[0], cards[1:])["rank100"] == r["rank100"]   # fiches avec chemin d'embedding = même résultat
    assert len(e.pairs(["c0", "c1"], ["c2"])) == 2

def test_fiche_sans_embedding_erreur_claire():
    import pytest
    with pytest.raises(ValueError, match="sans embedding"):
        E.compat({"id": "x", "slot": "top", "embedding": None}, of_cat("tops", 2))
    with pytest.raises(ValueError, match="inconnu"):
        E.compat("n_existe_pas", of_cat("tops", 2))
