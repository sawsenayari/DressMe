"""Canonical slot mapping shared by inventory and outfit components."""

from __future__ import annotations

COMMON_SLOTS = (
    "top",
    "bottom",
    "onepiece",
    "outer",
    "footwear",
    "bag",
    "accessory",
)

SLOT_MAPPING = {
    "shoes": "footwear",
    "shoe": "footwear",
    "footwear": "footwear",
    "outwear": "outer",
    "outerwear": "outer",
}


def normalize_slot(slot: str) -> str:
    """Return a canonical orchestration slot, preserving unknown values for validation."""
    if not isinstance(slot, str) or not slot.strip():
        raise ValueError("slot must be a non-empty string")
    normalized = slot.strip().casefold()
    return SLOT_MAPPING.get(normalized, normalized)
