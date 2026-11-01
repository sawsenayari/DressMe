import json, numpy as np, pytest
from pydantic import ValidationError
from contracts import ItemCard, CATEGORY_TO_SLOT, SLOTS, export_json_schema, warmth_formality, load_type_dictionary
from recognition.taxonomy import CATEGORIES
from recognition.mock import MockRecognizer
from recognition.itemcard_builder import apply_correction


def test_mapping_covers_all_17_categories():
    assert set(CATEGORIES) == set(CATEGORY_TO_SLOT)
    assert all(s in SLOTS for s in CATEGORY_TO_SLOT.values() if s)


def test_mock_is_valid_and_deterministic(tmp_path):
    m = MockRecognizer(); a = m.recognize("a.png", out_dir=tmp_path); b = m.recognize("a.png")
    assert a.card.slot == b.card.slot and a.status == "ok"
    v = np.load(tmp_path / a.card.embedding); assert v.shape == (512,) and abs(np.linalg.norm(v) - 1) < 1e-5
    ItemCard(**json.loads(a.card.model_dump_json()))


def test_contract_rejects_bad_values(tmp_path):
    c = MockRecognizer().recognize("a.png").card.model_dump()
    for bad in (dict(slot="hat"), dict(colour=["a", "b", "c"]), dict(warmth=9)):
        with pytest.raises(ValidationError): ItemCard(**{**c, **bad})


def test_schema_export(tmp_path):
    s = export_json_schema(tmp_path / "s.json"); assert "slot" in s["properties"] and (tmp_path / "s.json").exists()


def test_correction_sets_source_and_confidence():
    c = MockRecognizer().recognize("a.png").card; d = apply_correction(c, slot="outer", colour="Blue")
    assert d.source == "user_corrected" and d.confidence.slot == 1.0 and d.colour == ["blue"]


def test_placeholder_vs_official_dictionary(tmp_path):
    assert warmth_formality("jacket", "Jackets")[2] is False
    p = tmp_path / "d.json"; p.write_text(json.dumps({"Jackets": {"warmth": 3, "formality": 2}})); assert load_type_dictionary(str(p))
    assert warmth_formality("jacket", "Jackets") == (3, 2, True)
