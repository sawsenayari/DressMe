import sys, json
from pathlib import Path
import numpy as np, pandas as pd, pytest
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recognition.config import Config
from recognition.retrieval import Retriever


class FakeEmbedder:
    """Encodeur factice : vecteur déterministe selon la couleur moyenne de l'image."""
    def images(self, imgs, bs=32):
        out = []
        for im in imgs:
            a = np.asarray(im.resize((8, 8))).reshape(-1, 3).mean(0); v = np.zeros(512, "float32"); v[:3] = a / 255.0; v[3:] = 0.01
            out.append(v / np.linalg.norm(v))
        return np.vstack(out)


class FakeLLM:
    def __init__(self, answers): self.answers, self.calls = list(answers), 0
    def generate(self, image, prompt, system=None):
        a = self.answers[min(self.calls, len(self.answers) - 1)]; self.calls += 1; return json.dumps(a)


def ans(cat="jacket", conf=0.9, color="blue", gender="male", season="unknown", occasion="casual"):
    return dict(evidence="x", category=cat, alternative="coat", color=color, gender=gender, season=season, occasion=occasion, confidence=conf)


def make_retriever(cat="jacket", n=12, color="blue"):
    emb = FakeEmbedder(); im = Image.new("RGB", (64, 64), (30, 60, 200)); E = np.vstack([emb.images([im])[0] + 0.001 * i for i in range(n)])
    E /= np.linalg.norm(E, axis=1, keepdims=True)
    meta = pd.DataFrame(dict(id=range(n), category=[cat] * n, article_type=["Jackets"] * n, color=[color] * n, gender=["male"] * n,
                             season=["winter"] * n, occasion=["casual"] * n, name=["n"] * n, image_path=[""] * n))
    return Retriever(E, meta)


@pytest.fixture
def cfg(tmp_path): return Config(root=tmp_path)


@pytest.fixture
def crop_png(tmp_path):
    im = Image.new("RGB", (512, 512), (255, 255, 255)); im.paste(Image.new("RGB", (300, 380), (30, 60, 200)), (100, 60))
    p = tmp_path / "veste_crop.png"; im.save(p); return p


class FakeEmbedder2(FakeEmbedder):
    def texts(self, prompts):
        rng = np.random.default_rng(0); v = rng.normal(size=(len(prompts), 512)).astype("float32"); return v / np.linalg.norm(v, axis=1, keepdims=True)


def fake_segmenter(person=True):
    """Carte de classes factice 200x200 : haut (4) en haut, pantalon (6) en bas, visage (11) si personne ; marges blanches autour."""
    def seg(image):
        L = np.zeros((image.size[1], image.size[0]), int); H, W = L.shape
        L[int(.25 * H):int(.55 * H), int(.3 * W):int(.7 * W)] = 4; L[int(.55 * H):int(.9 * H), int(.3 * W):int(.7 * W)] = 6
        if person: L[int(.05 * H):int(.2 * H), int(.4 * W):int(.6 * W)] = 11
        return L
    return seg
