import json, numpy as np, pandas as pd
from PIL import Image
from conftest import FakeEmbedder, FakeEmbedder2, FakeLLM, ans, make_retriever, fake_segmenter
from recognition.crop import Cropper, piece_from_mask
from recognition.agent import RecognitionAgent
from recognition.service import RecognitionService
from recognition.batch import recognize_folder
from recognition import tunisian as T
from recognition.itemcard_builder import build_card, traditional_subtype
from evaluation.eval_tunisian import run_tunisian_eval


def photo(path, size=(200, 200)):
    Image.new("RGB", size, (120, 140, 160)).save(path); return path


def test_worn_photo_gives_one_crop_per_garment():
    c = Cropper(segmenter=fake_segmenter(True)); ps = c.crop(Image.new("RGB", (200, 200), (120, 140, 160)))
    assert {p.name for p in ps} == {"top", "bottom"} and all(p.image.size == (512, 512) for p in ps)
    assert {p.slot_hint for p in ps} == {"top", "bottom"} and all(p.quality["ok"] for p in ps)


def test_flat_photo_uses_remover_and_none_mode():
    def remover(im): o = im.convert("RGBA"); a = np.zeros(im.size[::-1], "uint8"); a[40:160, 50:150] = 255; o.putalpha(Image.fromarray(a)); return o
    c = Cropper(segmenter=fake_segmenter(False), remover=remover); ps = c.crop(Image.new("RGB", (200, 200), (30, 60, 200)))
    assert len(ps) == 1 and ps[0].name == "item" and ps[0].quality["ok"]
    assert Cropper().crop(Image.new("RGB", (80, 90)), "none")[0].name == "whole"


def test_quality_flags_cut_and_small_and_empty():
    im = Image.new("RGB", (200, 200), (10, 10, 10)); m = np.zeros((200, 200), bool); m[:, :60] = True       # touche le bord
    assert "garment_cut_by_frame" in piece_from_mask(im, m).quality["reasons"]
    m = np.zeros((200, 200), bool); m[90:95, 90:95] = True; assert "mask_too_small" in piece_from_mask(im, m, min_area=0.01).quality["reasons"]
    c = Cropper(segmenter=lambda im: np.zeros((im.size[1], im.size[0]), int)); p = c.crop(Image.new("RGB", (100, 100), (9, 9, 9)), "worn")
    assert p[0].name == "whole" and "no_garment_segmented" in p[0].quality["reasons"]


def test_photo_to_json_with_crop_and_slot_disagreement(cfg, tmp_path):
    inbox = tmp_path / "inbox"; inbox.mkdir(); photo(inbox / "p1.jpg")
    svc = RecognitionService(RecognitionAgent(FakeLLM([ans("jacket", 0.9)]), FakeEmbedder(), make_retriever(), cfg), FakeEmbedder(), cfg, cropper=Cropper(segmenter=fake_segmenter(True)))
    store = tmp_path / "store"; out = recognize_folder(svc, inbox, store, crop=True, verbose=False)
    assert out["cards"] == 2 and (store / "wardrobe.json").exists()
    rep = {e["source_key"]: e for e in json.loads((store / "recognition_report.json").read_text())["items"]}
    assert set(rep) == {"p1.jpg#top", "p1.jpg#bottom"}
    assert any(r.startswith("slot_disagrees_with_segmentation") for r in rep["p1.jpg#top"]["reasons"]) and rep["p1.jpg#top"]["status"] == "needs_review"
    ids = {e["id"] for e in rep.values()}; recognize_folder(svc, inbox, store, crop=True, verbose=False)
    assert {e["id"] for e in json.loads((store / "recognition_report.json").read_text())["items"]} == ids      # ids stables


def make_tn(cfg, n=9):
    d = T.tn_dir(cfg)
    for i in range(n): Image.new("RGB", (120, 140), (180 - i * 5, 100, 60 + i)).save(d / "images" / f"p{i}.jpg")
    T.make_template(cfg); df = pd.read_csv(d / "labels.csv", dtype=str).fillna("")
    df["category"] = ["traditional_garment"] * 6 + ["jacket"] * 3; df["subtype"] = ["jebba"] * 4 + ["farmla"] * 2 + [""] * 3
    df["group_id"] = [f"g{i}" for i in range(n)]; df["split"] = ["train"] * 5 + ["dev"] * 2 + ["test"] * 2; df["cropped"] = "1"; df.to_csv(d / "labels.csv", index=False); return df


def test_references_only_use_train_split(cfg):
    make_tn(cfg); kb = make_retriever().meta; E = make_retriever().E
    kb2, E2, n = T.add_tunisian_references(cfg, FakeEmbedder(), kb, E)
    assert n == 5 and len(kb2) == len(kb) + 5 and E2.shape == (len(kb) + 5, 512) and (kb2.id[-5:] < 0).all()
    assert (kb2.category[-5:] == "traditional_garment").sum() >= 4                                   # train = p0..p4


def test_traditional_subtype_changes_slot_and_type(cfg):
    nb = [dict(id=-i, category="traditional_garment", subtype="farmla", color="red", gender=None, season=None, occasion=None, name="n", article_type=None, sim=.9, w=.2) for i in range(5)]
    res = dict(category="traditional_garment", confidence=.9, status="OK", source="llm", neighbors=nb, knn=dict(category="traditional_garment", conf=1.0, dist={"traditional_garment": 1.0}),
               color="red", gender="unknown", season="unknown", occasion="traditional", candidate="traditional_garment", llm_conf=.9)
    card, status, reasons = build_card("it_1", res, image="a", image_crop="b", embedding="c")
    assert card.type == "Farmla" and card.slot == "outer" and card.usage == "Ethnic" and status == "needs_review"
    assert "traditional_subtype_from_neighbours:farmla" in reasons
    assert traditional_subtype([], 0.5) == (None, 0.0)


def test_tunisian_eval_runs_all_systems(cfg):
    make_tn(cfg); base = make_retriever("jacket"); kb, E = base.meta, base.E
    kb2, E2, _ = T.add_tunisian_references(cfg, FakeEmbedder(), kb, E)
    from recognition.retrieval import Retriever
    ref = Retriever(E2, kb2); agent = RecognitionAgent(FakeLLM([ans("traditional_garment", 0.9)]), FakeEmbedder(), ref, cfg)
    svc = RecognitionService(agent, FakeEmbedder2(), cfg); svc.retr_base, svc.retr_ref, svc.cropper = base, ref, None
    out = run_tunisian_eval(svc, "dev"); s = out["summary"]
    assert {"clip_zeroshot", "knn_catalogue", "knn_+tn_refs", "llm_only", "full_+tn_refs_+prompt"} <= set(s.index) and (s.n == 2).all()
    assert agent.retriever is ref and cfg.tunisian_prompt is False                                  # état restauré
