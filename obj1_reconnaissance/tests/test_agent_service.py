import json, numpy as np
from conftest import FakeEmbedder, FakeLLM, ans, make_retriever
from recognition.agent import RecognitionAgent
from recognition.service import RecognitionService
from recognition.llm import JsonlCache
from PIL import Image


def agent(cfg, answers, cat="jacket"):
    return RecognitionAgent(FakeLLM(answers), FakeEmbedder(), make_retriever(cat), cfg)


def img(): return Image.new("RGB", (400, 400), (30, 60, 200))


def test_route_llm_direct(cfg):
    r = agent(cfg, [ans("jacket", 0.9)]).run(img()); assert r["source"] == "llm" and r["category"] == "jacket" and r["llm_calls"] == 1


def test_route_knn_fallback_when_llm_unsure(cfg):
    r = agent(cfg, [ans("jacket", 0.4)]).run(img()); assert r["source"] == "knn_fallback"


def test_route_rag_then_validated(cfg):
    r = agent(cfg, [ans("coat", 0.9), ans("jacket", 0.9)]).run(img()); assert r["source"] == "llm+rag" and r["category"] == "jacket" and r["llm_calls"] == 2


def test_after_rag_policy_knn_vs_llm(cfg):
    a = agent(cfg, [ans("blazer", 0.9), ans("blazer", 0.8)]); assert a.run(img())["source"] == "knn_after_rag"      # v1 : kNN l'emporte
    cfg.after_rag_policy = "llm"; b = agent(cfg, [ans("blazer", 0.9), ans("blazer", 0.8)]); r = b.run(img())
    assert r["source"] == "llm+rag_flagged" and r["category"] == "blazer"


def test_modes(cfg):
    assert agent(cfg, [ans("coat", 0.9)]).run(img(), "llm_only")["category"] == "coat"
    k = agent(cfg, []).run(img(), "knn_only"); assert k["category"] == "jacket" and k["llm_calls"] == 0


def test_cache_avoids_second_call(cfg, tmp_path):
    llm = FakeLLM([ans()]); a = RecognitionAgent(llm, FakeEmbedder(), make_retriever(), cfg, JsonlCache(tmp_path / "c.jsonl"))
    a.run(img()); a.run(img()); assert llm.calls == 1


def test_service_end_to_end_writes_contract_files(cfg, crop_png, tmp_path):
    svc = RecognitionService(agent(cfg, [ans("jacket", 0.9)]), FakeEmbedder(), cfg)
    out = tmp_path / "store"; r = svc.recognize(crop_png, item_id="it_0001", out_dir=out)
    c = r.card; assert r.status == "ok" and c.slot == "outer" and c.type == "Jackets" and c.colour == ["blue"] and c.source == "obj1.llm"
    assert (out / "items/it_0001_crop.png").exists() and (out / "items/it_0001.json").exists()
    v = np.load(out / c.embedding); assert v.shape == (512,) and abs(np.linalg.norm(v) - 1) < 1e-5
    assert "warmth_formality_placeholder" in r.reasons and r.debug["confidence_calibrated"] is False
    assert 0 <= c.confidence.slot <= 1 and 0 <= c.confidence.colour <= 1


def test_traditional_and_underwear_handling(cfg, crop_png):
    r = RecognitionService(RecognitionAgent(FakeLLM([ans("traditional_garment", 0.9)]), FakeEmbedder(), make_retriever("traditional_garment"), cfg), FakeEmbedder(), cfg).recognize(crop_png)
    assert r.status == "needs_review" and r.card.slot == "onepiece" and r.card.traditional
    u = RecognitionService(RecognitionAgent(FakeLLM([ans("underwear", 0.9)]), FakeEmbedder(), make_retriever("underwear"), cfg), FakeEmbedder(), cfg).recognize(crop_png)
    assert u.status == "unsupported" and u.card is None


def test_bad_crop_forces_review(cfg, tmp_path):
    p = tmp_path / "empty.png"; Image.new("RGB", (512, 512), (255, 255, 255)).save(p)
    r = RecognitionService(agent(cfg, [ans("jacket", 0.9)]), FakeEmbedder(), cfg).recognize(p); assert r.status == "needs_review"
