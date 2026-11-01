import json, random
from pathlib import Path
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from app import store
from app.main import app
from app.rag import retrieve
c = TestClient(app)

def test_rag_retrieves_relevant():
    assert retrieve("فرح صاحبي")[0]["title"] == "Mariage"
    assert retrieve("je présente mon pfe devant le jury")[0]["title"] == "Soutenance et entretien"

def test_accessory_and_feedback_loop():
    body = {"uid": "t1", "gender": "Women", "occasion": "formal", "weather": {"feels_like": 20}, "when": "2026-10-22T08:00:00"}
    r = c.post("/api/recommend", json=body).json(); o = r["outfits"][0]
    assert o["accessories"], "un accessoire doit accompagner la tenue"
    out = c.post("/api/feedback", json={"uid": "t1", "features": o["features"], "accepted": True, "item_ids": o["item_ids"]}).json()
    assert out["feedback"] == 1 and out["acceptance_rate"] == 1.0
    assert set(o["item_ids"]) <= store.recent_worn("t1")        # rotation : pièces portées
    c.post("/api/feedback", json={"uid": "t2", "features": o["features"], "accepted": False, "reason": "style", "item_ids": o["item_ids"]})
    assert all(v < 0 for v in store.prefs("t2").values())       # 👎 style : pièces pénalisées
    c.post("/api/feedback", json={"uid": "t3", "features": o["features"], "accepted": False, "reason": "too_hot", "item_ids": o["item_ids"]})
    assert all(v == 0 for v in store.prefs("t3").values())      # 👎 trop chaud : erreur de contexte, pas de goût

def test_vision_pipeline_dummy(tmp_path):
    from training import prepare_data, vision
    img = tmp_path / "images"; img.mkdir(); rng = random.Random(0); rows = []
    rgb = {"Black": (20, 20, 20), "White": (240, 240, 240), "Red": (200, 30, 30), "Blue": (30, 40, 200)}
    for i in range(480):
        col = rng.choice(list(rgb)); t = rng.choice(["Tshirts", "Jeans"])
        Image.new("RGB", (60, 80), tuple(min(255, max(0, v + rng.randint(-15, 15))) for v in rgb[col])).save(img / f"{i}.jpg")
        rows.append([i, "Men", "Apparel", "Topwear", t, col, rng.choice(["Summer", "Winter"]), 2012, "Casual", f"Prod {i}"])
    import csv; f = tmp_path / "styles.csv"; w = csv.writer(open(f, "w"))
    w.writerow("id,gender,masterCategory,subCategory,articleType,baseColour,season,year,usage,productDisplayName".split(",")); w.writerows(rows)
    prepare_data.main(["--csv", str(f), "--images", str(img), "--out", str(tmp_path / "clean.csv"), "--report", str(tmp_path / "r.json"), "--min-class", "20", "--cap", "300"])
    vision.main(["--clean", str(tmp_path / "clean.csv"), "--images", str(img), "--backend", "dummy", "--models-dir", str(tmp_path / "m"), "--cache", str(tmp_path)])
    m = json.loads((tmp_path / "m" / "vision_metrics.json").read_text())["frozen_probe"]
    assert m["colour"]["test_macro_f1"] > 0.9 and m["colour"]["baseline_majority_acc"] < 0.5 and m["colour"]["variant"] in ("clip", "clip+pixels")

def test_llm_retries_on_429(monkeypatch):
    import asyncio, threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    calls = []
    class H(BaseHTTPRequestHandler):
        def do_POST(s):
            s.rfile.read(int(s.headers["Content-Length"])); calls.append(1)
            body = b'{"error":{"message":"Rate limit. Please try again in 50ms."}}' if len(calls) == 1 else \
                json.dumps({"choices": [{"message": {"content": json.dumps({"occasion": "work", "formality": 3, "gender": None, "notes": "x"})}}]}).encode()
            s.send_response(429 if len(calls) == 1 else 200); s.send_header("Content-Type", "application/json"); s.end_headers(); s.wfile.write(body)
        def log_message(*a): pass
    srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("LLM_BASE_URL", f"http://127.0.0.1:{srv.server_port}/v1"); monkeypatch.setenv("LLM_MODEL", "m")
    from app.agent import parse_agenda
    r = asyncio.run(parse_agenda("réunion client")); srv.shutdown()
    assert r["source"].startswith("llm") and len(calls) == 2

def test_segment_split_logic():
    from app import segment
    img = Image.fromarray(np.random.randint(0, 255, (100, 80, 3), dtype=np.uint8)); id2l = {0: "Background", 4: "Upper-clothes", 6: "Pants", 11: "Face"}
    seg = np.zeros((100, 80), int); seg[10:20, 30:50] = 11; seg[20:50, 20:60] = 4; seg[50:90, 25:55] = 6
    worn, parts = segment.split(img, seg, id2l)
    assert worn and list(parts) == ["haut", "bas"] or set(parts) == {"haut", "bas"}
    assert parts["haut"].size[0] < 80 and parts["haut"].getpixel((0, 0)) == (255, 255, 255)   # fond blanc autour du vêtement
    seg2 = np.zeros((100, 80), int); seg2[10:90, 10:70] = 4                                    # photo à plat : aucune personne
    assert segment.split(img, seg2, id2l)[0] is False

def test_exclusions_change_the_whole_outfit():
    base = {"uid": "t9", "gender": "Women", "occasion": "casual", "weather": {"feels_like": 22}, "when": "2026-10-22T08:00:00", "k": 3}
    first = c.post("/api/recommend", json=base).json()["outfits"][0]
    r = c.post("/api/recommend", json={**base, "exclude_ids": first["item_ids"]}).json()
    assert r["outfits"] and all(not set(o["item_ids"]) & set(first["item_ids"]) for o in r["outfits"])      # « changer toute la tenue »
    r = c.post("/api/recommend", json={**base, "exclude_outfits": [first["item_ids"]]}).json()
    assert all(set(o["item_ids"]) != set(first["item_ids"]) for o in r["outfits"])                          # « une autre » (même pièces permises)
    r = c.post("/api/recommend", json={**base, "exclude_ids": [i["id"] for i in c.get("/api/sample-wardrobe?gender=Women").json() if i["slot"] == "footwear"]}).json()
    assert r["outfits"] == [] and "exclusions" in r["message"]

def _mock_llm(monkeypatch):
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    step = []
    def tc(*calls): return {"choices": [{"message": {"content": "", "tool_calls": [{"id": f"c{i}", "type": "function", "function": {"name": n, "arguments": json.dumps(a)}} for i, (n, a) in enumerate(calls)]}}]}
    script = [tc(("get_weather", {"city": "Tunis"}), ("search_dress_code", {"query": "foot avec les amis"})),
              tc(("recommend_outfits", {"occasion": "sport", "feels_like": 22, "gender": "Women"})),
              {"choices": [{"message": {"content": "Voici une tenue sportive adaptée à 22 °C."}}]}]
    class H(BaseHTTPRequestHandler):
        def do_POST(s):
            s.rfile.read(int(s.headers["Content-Length"])); body = json.dumps(script[min(len(step), 2)]).encode(); step.append(1)
            s.send_response(200); s.send_header("Content-Type", "application/json"); s.end_headers(); s.wfile.write(body)
        def log_message(*a): pass
    srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("LLM_BASE_URL", f"http://127.0.0.1:{srv.server_port}/v1"); monkeypatch.setenv("LLM_MODEL", "m")
    return srv

def test_assistant_tool_calling_local_and_mcp(monkeypatch):
    import asyncio
    from app.assistant import run_assistant
    for use_mcp in (False, True):
        srv = _mock_llm(monkeypatch)
        r = asyncio.run(run_assistant("foot avec mes amis demain", "Women", use_mcp=use_mcp)); srv.shutdown()
        assert [t["tool"] for t in r["trace"]] == ["get_weather", "search_dress_code", "recommend_outfits"] and r["mcp"] is use_mcp
        assert '"tenues"' in r["trace"][-1]["result"] and "sportive" in r["answer"]

def test_sport_prefers_sport_shoes_and_warns_otherwise():
    r = c.post("/api/recommend", json={"gender": "Women", "occasion": "sport", "weather": {"feels_like": 22}, "when": "2026-10-22T08:00:00"}).json()
    foot = [i for i in r["outfits"][0]["items"] if i["slot"] == "footwear"][0]
    assert foot["usage"] == "Sports" and not foot["open_toe"]
    r = c.post("/api/recommend", json={"gender": "Women", "occasion": "sport", "weather": {"feels_like": 22}, "k": 10,
         "wardrobe": [i for i in c.get("/api/sample-wardrobe?gender=Women").json() if i["usage"] != "Sports"]}).json()
    assert any("Chaussures" in w for o in r["outfits"] for w in o["warnings"])      # pas de chaussures de sport -> alerte honnête

def test_agents_endpoint_and_item_rules(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "base"); monkeypatch.setenv("LLM_MODEL_ASSISTANT", "grand")
    a = c.get("/api/agents").json()
    assert a["llm_agents"]["agenda"]["model"] == "base" and a["llm_agents"]["assistant"]["model"] == "grand" and a["llm_agents"]["judge"]["role"] and a["rag"]["fiches"] == 15
    from app.catalog import item_from_prediction
    pred = lambda t, u, s="Summer", sc=.9: {"articleType": {"label": t, "conf": .9}, "colour": {"label": "blue", "conf": .5}, "usage": {"label": u, "conf": .8}, "season": {"label": s, "conf": sc}}
    assert item_from_prediction(pred("Shirts", "Casual"))["usage"] == "Smart Casual"      # type habillé : usage déduit
    assert item_from_prediction(pred("Formal Shoes", "Casual"))["usage"] == "Formal"
    assert item_from_prediction(pred("Tshirts", "Casual"))["usage"] == "Casual"
    assert item_from_prediction(pred("Tshirts", "Casual", "Winter", .5))["warmth"] < item_from_prediction(pred("Tshirts", "Casual", "Winter", .9))["warmth"]   # saison peu fiable ignorée
