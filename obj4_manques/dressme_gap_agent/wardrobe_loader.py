"""Validated loader for the Objective 1 wardrobe JSON contract."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

from .slot_mapping import COMMON_SLOTS, normalize_slot

REQUIRED_FIELDS = ("id", "name", "slot", "type")
NUMERIC_FIELDS = ("warmth", "formality")


@dataclass(frozen=True)
class WardrobeValidationReport:
    total: int
    valid: int
    invalid: int
    excluded: int
    needs_human_review: int
    missing_resources: int
    issues: tuple[str, ...]


@dataclass(frozen=True)
class WardrobeInventory:
    items: tuple[dict[str, Any], ...]
    report: WardrobeValidationReport
    source_path: Path


class WardrobeLoadError(ValueError):
    """Raised when the wardrobe root cannot be read or is not a supported shape."""


def _resource_status(item: dict[str, Any], source_path: Path) -> bool:
    missing = False
    for field in ("image", "image_crop", "embedding"):
        value = item.get(field)
        if not isinstance(value, str) or not value:
            continue
        if not (source_path.parent / value).exists():
            missing = True
    return missing


def load_wardrobe_from_json(path: str | Path) -> WardrobeInventory:
    """Load, normalize, and report on an Objective 1 wardrobe without silent drops."""
    source_path = Path(path).expanduser().resolve()
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WardrobeLoadError(f"Could not read wardrobe JSON: {source_path}") from exc

    raw_items = payload if isinstance(payload, list) else payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(raw_items, list):
        raise WardrobeLoadError("Wardrobe JSON root must be an array or an object containing an items array.")

    valid: list[dict[str, Any]] = []
    issues: list[str] = []
    seen: set[str] = set()
    invalid = excluded = review = missing_resources = 0
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            invalid += 1
            issues.append(f"item[{index}]: expected an object")
            continue
        item = dict(raw)
        item_id = item.get("id", item.get("item_id"))
        missing = []
        if not isinstance(item_id, str):
            missing.append("id")
        missing.extend(field for field in REQUIRED_FIELDS if field != "id" and not isinstance(item.get(field), str))
        if missing or not item_id or item_id in seen:
            invalid += 1
            issues.append(f"item[{index}]: missing required fields or duplicate id")
            continue
        seen.add(item_id)
        try:
            canonical_slot = normalize_slot(item["slot"])
        except ValueError:
            invalid += 1
            issues.append(f"{item_id}: invalid slot")
            continue
        if canonical_slot not in COMMON_SLOTS:
            invalid += 1
            issues.append(f"{item_id}: unsupported slot {item['slot']!r}")
            continue
        for field in NUMERIC_FIELDS:
            value = item.get(field)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)):
                invalid += 1
                issues.append(f"{item_id}: invalid numeric field {field}")
                break
        else:
            item["item_id"] = item_id
            item["slot"] = canonical_slot
            item["original_slot"] = raw["slot"]
            if _resource_status(item, source_path):
                missing_resources += 1
                review += 1
            if item.get("traditional") or str(item.get("type", "")).casefold() in {"jebba", "kaftan", "farmla", "traditional", "other"}:
                item["needs_human_review"] = bool(item.get("traditional") and canonical_slot == "accessory")
                review += int(item["needs_human_review"])
            valid.append(item)

    report = WardrobeValidationReport(
        total=len(raw_items),
        valid=len(valid),
        invalid=invalid,
        excluded=excluded,
        needs_human_review=review,
        missing_resources=missing_resources,
        issues=tuple(issues),
    )
    return WardrobeInventory(tuple(valid), report, source_path)
