"""Convert Objective 2 numeric scores into the legacy outfit-engine verdicts."""

from __future__ import annotations

from typing import Any, Mapping

from .outfit_engine import COMPATIBLE, INCOMPATIBLE, UNCERTAIN


def score_to_verdict(
    score: float,
    *,
    compatible_threshold: float = 0.70,
    incompatible_threshold: float = 0.40,
) -> str:
    """Apply explicitly configured thresholds; defaults are calibration placeholders."""
    if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 1:
        raise ValueError("compatibility score must be a number in [0, 1]")
    if not 0 <= incompatible_threshold < compatible_threshold <= 1:
        raise ValueError("compatibility thresholds must be ordered in [0, 1]")
    if score >= compatible_threshold:
        return COMPATIBLE
    if score < incompatible_threshold:
        return INCOMPATIBLE
    return UNCERTAIN


def scores_to_verdicts(
    left_items: list[Mapping[str, Any]],
    right_items: list[Mapping[str, Any]],
    scores: list[list[float]],
    *,
    compatible_threshold: float = 0.70,
    incompatible_threshold: float = 0.40,
) -> dict[tuple[str, str], str]:
    if len(scores) != len(left_items) or any(len(row) != len(right_items) for row in scores):
        raise ValueError("score matrix dimensions do not match item lists")
    result: dict[tuple[str, str], str] = {}
    for left, row in zip(left_items, scores):
        left_id = left.get("id", left.get("item_id"))
        for right, score in zip(right_items, row):
            right_id = right.get("id", right.get("item_id"))
            if not isinstance(left_id, str) or not isinstance(right_id, str):
                raise ValueError("all scored items require string IDs")
            result[tuple(sorted((left_id, right_id)))] = score_to_verdict(
                score,
                compatible_threshold=compatible_threshold,
                incompatible_threshold=incompatible_threshold,
            )
    return result
