from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from dressme_gap_agent.compatibility_provider import (
    CompatibilityProviderError,
    MockCompatibilityProvider,
)
from dressme_gap_agent.compatibility_scores import score_to_verdict
from dressme_gap_agent.embedding_inventory import load_items_with_embeddings
from dressme_gap_agent.candidate_prototypes import resolve_candidate_prototypes
from dressme_gap_agent.objective2_gap_pipeline import _score_required_pairs
from dressme_gap_agent.contracts import GapContractError, validate_gap_result
from dressme_gap_agent.outfit_engine import count_outfits, required_pair_keys
from dressme_gap_agent.wardrobe_loader import load_wardrobe_from_json


class Objective4IntegrationTests(unittest.TestCase):
    def test_objective1_wardrobe_is_loaded_and_canonicalized(self):
        path = Path(r"C:\Users\mariem\Downloads\wardrobe.json")
        if not path.exists():
            self.skipTest("local Objective 1 fixture is unavailable")
        inventory = load_wardrobe_from_json(path)
        self.assertEqual(inventory.report.total, 423)
        self.assertEqual(inventory.report.valid, 423)
        self.assertEqual(len({item["item_id"] for item in inventory.items}), 423)
        self.assertTrue(all(item["slot"] in {"top", "bottom", "onepiece", "outer", "footwear", "bag", "accessory"} for item in inventory.items))

    def test_loader_rejects_duplicate_ids_without_silent_drop(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wardrobe.json"
            path.write_text(json.dumps([
                {"id": "same", "name": "A", "slot": "shoes", "type": "Shoes"},
                {"id": "same", "name": "B", "slot": "top", "type": "Shirts"},
            ]), encoding="utf-8")
            inventory = load_wardrobe_from_json(path)
        self.assertEqual(inventory.report.total, 2)
        self.assertEqual(inventory.report.valid, 1)
        self.assertEqual(inventory.report.invalid, 1)

    def test_mock_provider_is_deterministic_and_validates_scores(self):
        provider = MockCompatibilityProvider({("a", "b"): 0.8})
        self.assertEqual(provider.score_pairs(["a"], ["b"]), [[0.8]])
        self.assertEqual(provider.score_pairs(["b"], ["a"]), [[0.8]])
        with self.assertRaises(CompatibilityProviderError):
            provider.score_pairs([], ["b"])

    def test_footwear_alias_is_counted_by_the_deterministic_engine(self):
        wardrobe = [
            {"item_id": "t", "slot": "top"},
            {"item_id": "b", "slot": "bottom"},
            {"item_id": "f", "slot": "footwear"},
        ]
        judgments = {pair: "compatible" for pair in required_pair_keys(wardrobe)}
        self.assertEqual(count_outfits(wardrobe, judgments, unknown_as_compatible=False)["base_outfits"], 1)

    def test_incomplete_result_cannot_be_marked_ready(self):
        payload = {
            "contract_version": "1.0",
            "status": "in_progress",
            "ranking_ready": True,
            "compatibility_progress": {"total_pairs": 2, "completed_pairs": 1, "remaining_pairs": 1},
            "gaps": [],
        }
        with self.assertRaises(GapContractError):
            validate_gap_result(payload)

    def test_objective2_scores_are_explicitly_mapped_to_engine_verdicts(self):
        self.assertEqual(score_to_verdict(0.8), "compatible")
        self.assertEqual(score_to_verdict(0.2), "incompatible")
        self.assertEqual(score_to_verdict(0.5), "uncertain")

    def test_fashionclip_cache_is_joined_by_stable_item_id(self):
        inventory = Path(r"wardrobe/.dressme-cache/full/wardrobe_inventory.json")
        embeddings = Path(r"wardrobe/.dressme-cache/full/fashionclip_embeddings.npz")
        if not inventory.exists() or not embeddings.exists():
            self.skipTest("local FashionCLIP cache is unavailable")
        items = load_items_with_embeddings(inventory, embeddings)
        self.assertEqual(len(items), 200)
        self.assertEqual(len(items[0]["embedding"]), 512)

    def test_text_candidates_get_explicit_same_slot_proxies(self):
        wardrobe = [
            {"id": "outer-1", "slot": "outer", "type": "Jackets", "name": "charcoal jacket", "embedding": [0.1] * 512},
            {"id": "top-1", "slot": "top", "type": "Shirts", "name": "white shirt", "embedding": [0.2] * 512},
        ]
        resolved = resolve_candidate_prototypes(
            [{"item_id": "candidate-1", "slot": "outer", "description": "neutral charcoal blazer"}],
            wardrobe,
        )
        self.assertEqual(resolved[0]["proxy_item_id"], "outer-1")
        self.assertEqual(resolved[0]["representation"], "wardrobe_image_proxy")

    def test_objective2_matrix_is_reduced_to_required_pairs(self):
        class Provider:
            def score_items(self, left, right):
                return [[0.8 for _ in right] for _ in left]

        items = [
            {"id": "t", "item_id": "t", "slot": "top", "embedding": [0.1] * 512},
            {"id": "b", "item_id": "b", "slot": "bottom", "embedding": [0.1] * 512},
            {"id": "f", "item_id": "f", "slot": "footwear", "embedding": [0.1] * 512},
        ]
        scores, requests = _score_required_pairs(items, Provider(), chunk_size=2)
        self.assertEqual(len(scores), 3)
        self.assertEqual(requests, 3)
