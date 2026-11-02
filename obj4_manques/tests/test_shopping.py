from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dressme_gap_agent.shopping import (
    ShoppingSearchConfig,
    ShoppingSearchError,
    _extract_price,
    recommend_products,
    search_gap,
)


class ShoppingTests(unittest.TestCase):
    def test_search_extracts_links_and_applies_price_filter(self):
        response = {
            "results": [
                    {
                        "title": "White shirt - $35",
                        "url": "https://shop.example/shirt",
                        "content": "Cotton shirt for $35",
                    },
                    {
                        "title": "Premium shirt - $120",
                        "url": "https://shop.example/premium",
                        "content": "Premium cotton",
                    },
            ]
        }

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(response).encode("utf-8")

        with patch("dressme_gap_agent.shopping.urlopen", return_value=FakeResponse()):
            options = search_gap(
                {"description": "white button-down shirt"},
                ShoppingSearchConfig(api_key="test"),
                max_price=50,
            )
        self.assertEqual(len(options), 1)
        self.assertEqual(options[0]["price"], 35)

    def test_missing_search_key_is_explicit(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ShoppingSearchError):
                ShoppingSearchConfig.from_env()

    def test_price_parser_handles_thousands_and_chooses_lowest_offer(self):
        self.assertEqual(_extract_price("From $1,400 down to $14"), (14, "$"))
        self.assertEqual(_extract_price("$50 shipping, product $19.99"), (19.99, "$"))

    def test_price_parser_handles_european_formats_without_failing(self):
        # milliers et décimales dans les deux conventions, symbole avant ou après ; « $1,299.99 » faisait planter la recherche
        self.assertEqual(_extract_price("$1,299.99"), (1299.99, "$"))
        self.assertEqual(_extract_price("Prix 23.400,00 €"), (23400.0, "€"))
        self.assertEqual(_extract_price("23.400,00 EUR"), (23400.0, "EUR"))
        self.assertEqual(_extract_price("€ 1.299,99"), (1299.99, "€"))
        self.assertEqual(_extract_price("19,99 €"), (19.99, "€"))
        self.assertEqual(_extract_price("aucun prix ici"), (None, None))

    def test_search_preserves_provider_image_url(self):
        response = {
            "results": [{
                "title": "White shirt",
                "url": "https://shop.example/shirt",
                "content": "$35",
                "image_url": "https://cdn.example/shirt.jpg",
            }]
        }

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(response).encode("utf-8")

        with patch("dressme_gap_agent.shopping.urlopen", return_value=FakeResponse()):
            options = search_gap(
                {"description": "white shirt"},
                ShoppingSearchConfig(api_key="test"),
            )
        self.assertEqual(options[0]["image_url"], "https://cdn.example/shirt.jpg")

    def test_search_uses_tavily_result_images(self):
        response = {
            "results": [{
                "title": "White shirt",
                "url": "https://shop.example/shirt",
                "content": "$35",
                "images": [{"url": "https://cdn.example/shirt.webp"}],
            }],
            "images": [],
        }

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(response).encode("utf-8")

        with patch("dressme_gap_agent.shopping.urlopen", return_value=FakeResponse()):
            options = search_gap(
                {"description": "white shirt"},
                ShoppingSearchConfig(api_key="test"),
            )
        self.assertEqual(options[0]["image_url"], "https://cdn.example/shirt.webp")

    def test_recommendations_use_ranked_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            analysis = Path(directory) / "analysis.json"
            output = Path(directory) / "shopping.json"
            analysis.write_text(json.dumps({
                "gaps": [
                    {"description": "white shirt", "slot": "top", "rank": 1},
                    {"description": "loafers", "slot": "footwear", "rank": 2},
                ]
            }), encoding="utf-8")
            with patch(
                "dressme_gap_agent.shopping.search_gap",
                return_value=[{"title": "Result", "url": "https://example.com"}],
            ) as mocked:
                result = recommend_products(
                    analysis,
                    output,
                    config=ShoppingSearchConfig(api_key="test"),
                    gap_limit=1,
                )
        self.assertEqual(result["gap_count"], 1)
        mocked.assert_called_once()
