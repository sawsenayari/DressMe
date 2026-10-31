"""Validated, data-minimized sources for the agent's primary tools."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any


class WardrobeSourceError(ValueError):
    """Raised when a wardrobe inventory or LLM gap analysis is unavailable."""


class WardrobeInventorySource:
    def __init__(self, path: str | Path) -> None:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WardrobeSourceError("Could not read the FashionCLIP wardrobe inventory.") from exc
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise WardrobeSourceError("Wardrobe inventory must contain an items list.")
        clean = []
        for item in items:
            if not isinstance(item, dict):
                raise WardrobeSourceError("Wardrobe inventory contains a malformed item.")
            if item.get("duplicate_of") is not None:
                continue
            if not all(isinstance(item.get(key), str) and item[key] for key in ("item_id", "category", "slot")):
                raise WardrobeSourceError("Wardrobe inventory item is missing its ID, category, or slot.")
            clean.append(item)
        self._items = clean
        self._encoder = payload.get("encoder", {})

    def get_wardrobe_summary(self) -> dict[str, Any]:
        slot_counts = Counter(item["slot"] for item in self._items)
        color_counts = Counter(
            item["color_candidates"][0]["label"]
            for item in self._items
            if item.get("color_candidates")
            and isinstance(item["color_candidates"][0], dict)
            and isinstance(item["color_candidates"][0].get("label"), str)
        )
        return {
            "metadata": {
                "source": "fashionclip_wardrobe_inventory",
                "encoder": self._encoder.get("model_id") if isinstance(self._encoder, dict) else None,
                "recalculated": False,
                "duplicate_images_excluded": True,
            },
            "summary": {
                "unique_item_count": len(self._items),
                "counts_by_slot": dict(sorted(slot_counts.items())),
                "top_tentative_color_labels": color_counts.most_common(8),
            },
        }


class LLMGapAnalysisSource:
    """Expose only a completed LLM-judged/pure-Python-counted gap analysis."""

    def __init__(self, path: str | Path) -> None:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WardrobeSourceError("Could not read the LLM gap analysis.") from exc
        if not isinstance(payload, dict) or payload.get("status") != "complete" or not payload.get("ranking_ready"):
            raise WardrobeSourceError("A complete LLM-judged ranking is not available yet.")
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            raise WardrobeSourceError("LLM gap analysis has no candidate list.")
        for candidate in candidates:
            if (
                not isinstance(candidate, dict)
                or not isinstance(candidate.get("description"), str)
                or not isinstance(candidate.get("gain_lower"), int)
                or not isinstance(candidate.get("gain_upper"), int)
                or candidate["gain_lower"] > candidate["gain_upper"]
            ):
                raise WardrobeSourceError("LLM gap analysis contains an invalid candidate result.")
        self._payload = payload

    def rank_wardrobe_gaps(self, limit: int = 5) -> dict[str, Any]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 8:
            raise ValueError("limit must be an integer between 1 and 8.")
        return {
            "metadata": {
                "source": "llm_compatibility_plus_deterministic_outfit_counter",
                "recalculated": True,
                "notebook_gap_report_used": False,
                "compatibility_prompt_version": self._payload.get("compatibility_prompt_version"),
                "candidate_prompt_version": self._payload.get("candidate_prompt_version"),
                "applied_constraints": {},
                "uncertainty_method": self._payload.get("uncertainty_method"),
                "prices_available": False,
            },
            "recommendations": self._payload["candidates"][:limit],
        }
