"""Small dependency-free validator for the stable Objective 4 result contract."""

from __future__ import annotations

from typing import Any

from .slot_mapping import COMMON_SLOTS

CONTRACT_VERSION = "1.0"


class GapContractError(ValueError):
    """Raised when an Objective 4 result is not consumable by orchestration."""


def validate_gap_result(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise GapContractError("gap result must be an object")
    required = {"contract_version", "status", "ranking_ready", "compatibility_progress", "gaps"}
    if not required.issubset(payload) or payload["contract_version"] != CONTRACT_VERSION:
        raise GapContractError("gap result has an unsupported contract version or missing fields")
    progress = payload["compatibility_progress"]
    if not isinstance(progress, dict) or any(
        isinstance(progress.get(key), bool) or not isinstance(progress.get(key), int) or progress[key] < 0
        for key in ("total_pairs", "completed_pairs", "remaining_pairs")
    ):
        raise GapContractError("compatibility_progress is invalid")
    if progress["completed_pairs"] + progress["remaining_pairs"] != progress["total_pairs"]:
        raise GapContractError("compatibility progress is inconsistent")
    gaps = payload["gaps"]
    if not isinstance(gaps, list):
        raise GapContractError("gaps must be an array")
    for expected_rank, gap in enumerate(gaps, start=1):
        if not isinstance(gap, dict) or not isinstance(gap.get("description"), str) or gap.get("slot") not in COMMON_SLOTS:
            raise GapContractError("gap has invalid description or slot")
        if gap.get("rank") != expected_rank:
            raise GapContractError("gap ranks must be consecutive")
        if any(isinstance(gap.get(key), bool) or not isinstance(gap.get(key), int) or gap[key] < 0 for key in ("gain_lower", "gain_upper")):
            raise GapContractError("gap gains must be non-negative integers")
        if gap["gain_lower"] > gap["gain_upper"]:
            raise GapContractError("gap lower gain cannot exceed upper gain")
    if payload["ranking_ready"] and progress["remaining_pairs"] != 0:
        raise GapContractError("ranking_ready cannot be true while pairs remain")
    return payload
