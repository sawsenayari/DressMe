import json
import pandas as pd
from PIL import Image
from conftest import FakeEmbedder, FakeLLM, ans, make_retriever
from recognition.agent import RecognitionAgent
from recognition.service import RecognitionService
from recognition.batch import recognize_folder
from recognition.mock import MockRecognizer
from evaluation.eval_real import run_real_eval


def svc_fake(cfg): return RecognitionService(RecognitionAgent(FakeLLM([ans("jacket", 0.9)]), FakeEmbedder(), make_retriever(), cfg), FakeEmbedder(), cfg)


def put(folder, name):
    im = Image.new("RGB", (512, 512), (255, 255, 255)); im.paste(Image.new("RGB", (300, 380), (30, 60, 200)), (100, 60)); im.save(folder / name)


def test_batch_writes_json_files_and_unique_ids(cfg, tmp_path):
    inbox, store = tmp_path / "inbox", tmp_path / "store"; inbox.mkdir(); put(inbox, "a.png"); put(inbox, "b.jpg")
    s = svc_fake(cfg); out = recognize_folder(s, inbox, store, verbose=False)
    assert out["cards"] == 2 and (store / "items/it_0001.json").exists() and (store / "items/it_0002.json").exists()
    assert len(json.loads((store / "wardrobe.json").read_text())) == 2 and (store / "emb/it_0002.npy").exists()
    put(inbox, "c.png"); recognize_folder(s, inbox, store, verbose=False)                      # relance : a et b gardent leur id, c = it_0003
    rep = {e["source_key"]: e["id"] for e in json.loads((store / "recognition_report.json").read_text())["items"]}
    assert rep == {"a.png": "it_0001", "b.jpg": "it_0002", "c.png": "it_0003"}
    assert len(json.loads((store / "wardrobe.json").read_text())) == 3


def test_real_eval_runs_with_mock_and_underwear(tmp_path):
    for n in ("p1.png", "p2.png", "p3.png"): put(tmp_path, n)
    pd.DataFrame(dict(image_path=["p1.png", "p2.png", "p3.png"], true_category=["jacket", "shoes", "underwear"], true_colour=["blue", "black", "white"])).to_csv(tmp_path / "l.csv", index=False)
    out = run_real_eval(MockRecognizer(), tmp_path / "l.csv", out_dir=tmp_path / "o", modes=("full",))
    assert (tmp_path / "o/summary.csv").exists() and "slot" in out["summary"].columns
