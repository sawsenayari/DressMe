from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)
def rec(**kw):
    return c.post("/api/recommend", json={"when": "2026-10-22T08:00:00", **kw}).json()

def test_health(): assert c.get("/health").status_code == 200

def test_cold_warmer_than_hot():
    hot = rec(weather={"feels_like": 36}, occasion="casual")["outfits"][0]["features"]["warmth"]
    cold = rec(weather={"feels_like": 5}, occasion="casual")["outfits"][0]["features"]["warmth"]
    assert cold > hot + 2

def test_rain_closed_shoes():
    for o in rec(weather={"feels_like": 18, "rain_prob": 0.9}, occasion="work")["outfits"]:
        assert not any(i["open_toe"] for i in o["items"])

def test_formal_occasion():
    f = rec(weather={"feels_like": 20}, occasion="formal")["outfits"][0]["features"]
    assert f["mean_formality"] >= 2

def test_agenda_rules():
    assert rec(weather={"feels_like": 20}, agenda="Mariage de ma cousine samedi")["context"]["occasion"] == "wedding"
