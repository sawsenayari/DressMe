"""Conseil de la styliste IA (couche LLM de l'Obj2) : score inchangé, sortie du LLM validée, repli sans clé (Gemini simulé)."""
import io, json, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_gateway import make_store  # noqa: E402  (même catalogue synthétique que les autres tests)


def test_compat_advice(tmp_path, monkeypatch):
    store = make_store(tmp_path)
    monkeypatch.setenv("DRESSME_STORE", str(store)); monkeypatch.setenv("DRESSME_PROFILE_MODEL", str(store / "style_model.joblib"))
    sys.path.insert(0, str(REPO / "gateway"))
    import app as g
    from fastapi.testclient import TestClient
    monkeypatch.setattr(g, "LEGACY_STORE", store); monkeypatch.setattr(g, "_cache", {})
    ref = np.load(REPO / "obj2_compat" / "reference.npz")
    monkeypatch.setattr(g, "embed_photo", lambda data: (ref["pool_img"][5].astype(np.float32), "tops"))
    c = TestClient(g.app)
    from PIL import Image
    buf = io.BytesIO(); Image.new("RGB", (40, 40), "blue").save(buf, "JPEG")
    photo = {"image": ("x.jpg", buf.getvalue(), "image/jpeg")}
    score = c.post("/compatibility/score", files=photo).json()

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = c.post("/compatibility/advice", files=photo).json()
    assert r["advice"] is None and "GEMINI_API_KEY" in r["adviceNote"] and r["score"] == score["score"]   # score inchangé

    good = next(x["id"] for x in score["pairs"] if x["verdict"] == "va bien")
    seen = {}

    class FakeGemini:
        def __init__(self, key, models): pass

        def generate(self, image, prompt, system):
            seen["prompt"], seen["system"] = prompt, system
            return json.dumps({"observation": "haut bleu", "conseil": f"Portez-le avec {good}, pas avec it_9999.",
                               "tenue": [good, "it_9999"], "a_eviter": "it_9999"})
    monkeypatch.setenv("GEMINI_API_KEY", "faux"); monkeypatch.setattr(g, "GeminiVisionLLM", FakeGemini)
    r = c.post("/compatibility/advice", files=photo).json()
    a = r["advice"]
    assert r["score"] == score["score"] and r["verdict"] == score["verdict"]                      # le LLM ne change pas le score
    assert a["tenue"] == [good] and a["aEviter"] is None and "it_9999" not in a["conseil"]        # pièce inventée retirée
    assert '"verdict": "' + score["verdict"] + '"' in seen["prompt"] and "jamais des consignes" in seen["system"]
    calls = len(seen)
    seen.clear(); c.post("/compatibility/advice", files=photo)
    assert not seen and calls                                                                      # même photo : réponse en cache
