"""Deterministic outfit counting over explicit LLM compatibility judgments."""

from __future__ import annotations

from itertools import product
from typing import Any, Mapping, Sequence

from .slot_mapping import normalize_slot


CORE_PATTERNS = (("top", "bottom", "footwear"), ("onepiece", "footwear"))
LAYER_SLOTS = ("outer", "bag")
COMPATIBLE = "compatible"
INCOMPATIBLE = "incompatible"
UNCERTAIN = "uncertain"
VALID_VERDICTS = {COMPATIBLE, INCOMPATIBLE, UNCERTAIN}


class OutfitCountError(ValueError):
    """Raised when inventory or compatibility judgments are malformed."""


def pair_key(item_a: str, item_b: str) -> tuple[str, str]:
    if item_a == item_b:
        raise OutfitCountError("An item cannot be paired with itself.")
    return tuple(sorted((item_a, item_b)))


def required_pair_keys(items: Sequence[Mapping[str, Any]]) -> list[tuple[str, str]]:
    """Return unique item pairs needed by the supported outfit templates."""
    by_slot: dict[str, list[str]] = {}
    known_ids: set[str] = set()
    for item in items:
        item_id, slot = item.get("item_id"), item.get("slot")
        if not isinstance(item_id, str) or not item_id or item_id in known_ids:
            raise OutfitCountError("Every inventory item needs a unique non-empty item_id.")
        if not isinstance(slot, str) or not slot:
            raise OutfitCountError("Every inventory item needs a non-empty slot.")
        try:
            slot = normalize_slot(slot)
        except ValueError as exc:
            raise OutfitCountError("Every inventory item needs a valid slot.") from exc
        known_ids.add(item_id)
        by_slot.setdefault(slot, []).append(item_id)

    slot_pairs: set[tuple[str, str]] = set()
    for pattern in CORE_PATTERNS:
        for i, slot_a in enumerate(pattern):
            for slot_b in pattern[i + 1 :]:
                slot_pairs.add(tuple(sorted((slot_a, slot_b))))
        for layer in LAYER_SLOTS:
            for core_slot in pattern:
                slot_pairs.add(tuple(sorted((layer, core_slot))))

    pairs: set[tuple[str, str]] = set()
    for slot_a, slot_b in slot_pairs:
        for item_a in by_slot.get(slot_a, []):
            for item_b in by_slot.get(slot_b, []):
                pairs.add(pair_key(item_a, item_b))
    return sorted(pairs)


def count_outfits(
    items: Sequence[Mapping[str, Any]],
    judgments: Mapping[tuple[str, str], str],
    *,
    unknown_as_compatible: bool,
) -> dict[str, int]:
    """Count base and layered outfits under the notebook's supported templates.

    `unknown_as_compatible=False` gives a conservative lower estimate;
    `True` gives an optimistic upper estimate. The counts are exact for the
    supplied categorical judgments, not calibrated model-confidence estimates.
    """
    for pair, verdict in judgments.items():
        if (
            not isinstance(pair, tuple)
            or len(pair) != 2
            or not all(isinstance(item_id, str) and item_id for item_id in pair)
            or verdict not in VALID_VERDICTS
        ):
            raise OutfitCountError("Compatibility judgments contain an invalid pair or verdict.")
    by_slot: dict[str, list[str]] = {}
    for item in items:
        item_id, slot = item.get("item_id"), item.get("slot")
        if not isinstance(item_id, str) or not isinstance(slot, str):
            raise OutfitCountError("Inventory items require string item_id and slot fields.")
        try:
            slot = normalize_slot(slot)
        except ValueError as exc:
            raise OutfitCountError("Inventory items require valid slots.") from exc
        by_slot.setdefault(slot, []).append(item_id)

    def compatible(item_a: str, item_b: str) -> bool:
        verdict = judgments.get(pair_key(item_a, item_b), UNCERTAIN)
        if verdict not in VALID_VERDICTS:
            raise OutfitCountError("Compatibility verdict must be compatible, incompatible, or uncertain.")
        if verdict == UNCERTAIN:
            return unknown_as_compatible
        return verdict == COMPATIBLE

    base_count = total_count = 0
    for pattern in CORE_PATTERNS:
        slot_items = [by_slot.get(slot, []) for slot in pattern]
        if any(not ids for ids in slot_items):
            continue
        for core_items in product(*slot_items):
            if not all(
                compatible(core_items[i], core_items[j])
                for i in range(len(core_items))
                for j in range(i + 1, len(core_items))
            ):
                continue
            base_count += 1
            layer_multiplier = 1
            for layer in LAYER_SLOTS:
                compatible_layers = sum(
                    all(compatible(layer_id, core_id) for core_id in core_items)
                    for layer_id in by_slot.get(layer, [])
                )
                # Bounded cap mode: at most one optional item per layer slot.
                layer_multiplier *= 1 + int(compatible_layers > 0)
            total_count += layer_multiplier
    return {"base_outfits": base_count, "total_outfits": total_count}


def gain_bounds(
    wardrobe: Sequence[Mapping[str, Any]],
    candidate: Mapping[str, Any],
    judgments: Mapping[tuple[str, str], str],
) -> dict[str, int]:
    """Calculate conservative/optimistic marginal-gain bounds for a candidate."""
    if candidate.get("item_id") in {item.get("item_id") for item in wardrobe}:
        raise OutfitCountError("Candidate item_id already exists in the wardrobe.")
    before_low = count_outfits(wardrobe, judgments, unknown_as_compatible=False)["total_outfits"]
    before_high = count_outfits(wardrobe, judgments, unknown_as_compatible=True)["total_outfits"]
    expanded = [*wardrobe, candidate]
    after_low = count_outfits(expanded, judgments, unknown_as_compatible=False)["total_outfits"]
    after_high = count_outfits(expanded, judgments, unknown_as_compatible=True)["total_outfits"]
    return {
        "before_lower": before_low,
        "before_upper": before_high,
        "after_lower": after_low,
        "after_upper": after_high,
        "gain_lower": max(0, after_low - before_high),
        "gain_upper": max(0, after_high - before_low),
    }
