"""Loading and sanitizing the existing Objective 4 JSON export."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class GapReportError(ValueError):
    """Raised for missing, malformed, or unsupported gap-report files."""


_REQUIRED_STRING_FIELDS = ("id", "category", "slot", "description")


def load_gap_report(path: str | Path) -> list[dict[str, Any]]:
    """Read the notebook's array-shaped ``gap_report.json`` export."""
    report_path = Path(path)
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise GapReportError(f"Could not read gap report: {report_path}") from exc
    except json.JSONDecodeError as exc:
        raise GapReportError("Gap report is not valid JSON.") from exc

    if not isinstance(payload, list) or len(payload) > 1000:
        raise GapReportError("Gap report must be a JSON array with at most 1000 entries.")

    cleaned: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise GapReportError(f"Gap report entry {index} must be an object.")
        if any(not isinstance(item.get(key), str) or not item[key].strip() for key in _REQUIRED_STRING_FIELDS):
            raise GapReportError(f"Gap report entry {index} is missing a required text field.")
        gap_id = item["id"]
        if gap_id in seen_ids:
            raise GapReportError(f"Gap report contains duplicate id: {gap_id}")
        seen_ids.add(gap_id)
        gain = item.get("unlockedOutfits")
        if isinstance(gain, bool) or not isinstance(gain, int) or gain < 0:
            raise GapReportError(f"Gap report entry {index} has an invalid unlockedOutfits value.")

        # exampleItemId may be a local dataset path; it is intentionally not
        # sent to the model. Keep only fields needed to explain the ranking.
        cleaned.append(
            {
                "id": gap_id[:80],
                "category": item["category"][:80],
                "slot": item["slot"][:80],
                "description": item["description"][:200],
                "unlockedOutfits": gain,
            }
        )
    return cleaned


class GapReportSource:
    """Read-only adapter exposing a bounded slice of the exported report."""

    def __init__(self, path: str | Path) -> None:
        self._items = load_gap_report(path)

    def get_gap_report(self, top_k: int = 5) -> dict[str, Any]:
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 10:
            raise ValueError("top_k must be an integer between 1 and 10.")
        recommendations = self._items[:top_k]
        return {
            "metadata": {
                "source": "precomputed_notebook_export",
                "recalculated": False,
                "applied_constraints": {},
                "total_available": len(self._items),
                "returned_count": len(recommendations),
                "truncated": len(recommendations) < len(self._items),
            },
            "ranking_basis": "unlockedOutfits from the exported Objective 4 report",
            "recommendations": recommendations,
            "personalization": (
                "This is a precomputed report. It does not recalculate rankings by persona, "
                "season, or budget."
            ),
        }
