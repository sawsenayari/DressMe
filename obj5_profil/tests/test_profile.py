"""Tests de conformité au contrat et de comportement (pytest -q)."""
import json
import shutil
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from dressme_profile import config
from dressme_profile.contracts import ItemCard, ProfileRequest, RecommendRequest, StyleProfile
from dressme_profile.mock import mock_profile
from dressme_profile.profile import decide_persona
from dressme_profile.contracts import PersonaScores
from dressme_profile.service import ProfileService, load_items

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "wardrobe.json"


@pytest.fixture(scope="module")
def svc(tmp_path_factory):
    model = tmp_path_factory.mktemp("m") / "model.joblib"
    return ProfileService(CATALOG, model, ROOT / "data")


def test_catalog_respects_itemcard_v1():
    items = load_items(CATALOG)
    assert len(items) > 0 and all(i.slot in config.SLOTS for i in items)


def test_mock_is_valid_contract():
    StyleProfile.model_validate(mock_profile("u").model_dump())


def test_profile_contract_and_determinism(svc):
    ids = [i.id for i in svc.catalog if i.gender in ("Men", "Unisex")][:40]
    p1 = svc.profile(ProfileRequest(user_id="u1", item_ids=ids))
    p2 = svc.profile(ProfileRequest(user_id="u1", item_ids=ids))
    StyleProfile.model_validate(p1.model_dump())          # schéma respecté
    assert p1.model_dump() == p2.model_dump()             # déterministe
    assert p1.persona in ("efficacite", "economie", "image", "mixte")
    assert abs(sum(e.weight for e in p1.palette) - 1) < 0.02 or len(p1.palette) == 5
    assert 0 <= p1.diversity <= 1


def test_no_price_means_economie_null(svc):
    p = svc.profile(ProfileRequest(item_ids=[i.id for i in svc.catalog[:30]]))
    assert p.scores.economie is None and p.price_percentile is None
    assert any("economie" in w for w in p.warnings)


def test_low_confidence_and_duplicates_are_skipped(svc):
    # it_0978 : confidence.slot = 0 ; it_0751 / it_0796 : même fiche dupliquée
    p = svc.profile(ProfileRequest(item_ids=["it_0978", "it_0751", "it_0796", "it_0653"]))
    assert p.n_items == 4 and p.n_items_used == 2


def test_items_payload_accepted(svc):
    cards = json.loads(CATALOG.read_text())[:15]
    p = svc.profile(ProfileRequest(items=[ItemCard.model_validate(c) for c in cards]))
    assert p.n_items == 15


def test_mixed_margin():
    assert decide_persona(PersonaScores(efficacite=0.50, economie=None, image=0.45)) == "mixte"
    assert decide_persona(PersonaScores(efficacite=0.60, economie=0.30, image=0.45)) == "efficacite"


def test_recommend_excludes_wardrobe(svc):
    ids = [i.id for i in svc.catalog if i.gender == "Women"][:25]
    res = svc.recommend(RecommendRequest(wardrobe_ids=ids, k=10))
    assert len(res.items) == 10 and not set(r.id for r in res.items) & set(ids)
    assert res.items == sorted(res.items, key=lambda r: -r.score)


def test_fashionclip_space_used_when_npy_present(tmp_path):
    """Avec des .npy présents pour toutes les fiches, le service bascule en FashionCLIP."""
    cards = json.loads(CATALOG.read_text())[:120]
    rng = np.random.default_rng(0)
    for c in cards:
        out = tmp_path / c["embedding"]
        out.parent.mkdir(parents=True, exist_ok=True)
        v = rng.normal(size=512).astype(np.float32)
        np.save(out, v / np.linalg.norm(v))
    cat = tmp_path / "cat.json"
    cat.write_text(json.dumps(cards))
    s = ProfileService(cat, tmp_path / "m.joblib", tmp_path)
    assert s.model.space == "fashionclip"
    p = s.profile(ProfileRequest(item_ids=[c["id"] for c in cards[:30]]))
    assert p.embedding_space == "fashionclip"


def test_api(svc, monkeypatch):
    from dressme_profile import api
    monkeypatch.setattr(api, "get_service", lambda: svc)
    c = TestClient(api.app)
    assert c.get("/health").json()["status"] == "ok"
    r = c.post("/profile", json={"user_id": "u", "item_ids": ["it_0653", "it_0700", "it_0889"]})
    assert r.status_code == 200 and StyleProfile.model_validate(r.json())
    assert c.post("/profile", json={"item_ids": ["inconnu"]}).status_code == 404
    assert c.post("/profile", json={}).status_code == 422


def test_api_mock_mode(monkeypatch):
    from dressme_profile import api
    monkeypatch.setattr(config, "USE_MOCK", True)
    r = TestClient(api.app).post("/profile", json={"user_id": "x"})
    assert r.status_code == 200 and r.json()["model"] == "mock"
