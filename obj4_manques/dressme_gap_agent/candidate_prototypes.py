"""Represent text-only gap archetypes with explicit wardrobe image proxies."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .embedding_inventory import EmbeddingInventoryError, load_items_with_embeddings
from .slot_mapping import normalize_slot


class CandidatePrototypeError(ValueError):
    """Raised when an archetype cannot be represented for Objective 2."""


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.casefold()) if len(token) > 2}


def resolve_candidate_prototypes(
    candidates: Sequence[Mapping[str, Any]],
    wardrobe_items: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Choose deterministic same-slot image proxies; never hide proxy provenance."""
    if not wardrobe_items:
        raise CandidatePrototypeError("Cannot resolve prototypes from an empty wardrobe.")
    resolved: list[dict[str, Any]] = []
    used: set[str] = set()
    for candidate in candidates:
        candidate_id = candidate.get("item_id")
        description = candidate.get("description")
        if not isinstance(candidate_id, str) or not candidate_id or not isinstance(description, str) or not description:
            raise CandidatePrototypeError("Candidates require item_id and description.")
        try:
            slot = normalize_slot(candidate.get("slot"))
        except ValueError as exc:
            raise CandidatePrototypeError(f"Candidate {candidate_id} has an invalid slot.") from exc
        eligible = [
            item for item in wardrobe_items
            if normalize_slot(item.get("slot")) == slot
            and isinstance(item.get("id", item.get("item_id")), str)
            and item.get("id", item.get("item_id")) not in used
            and isinstance(item.get("embedding"), list)
        ]
        if not eligible:
            raise CandidatePrototypeError(f"No embedded wardrobe prototype exists for slot {slot!r}.")
        candidate_tokens = _tokens(description)

        def rank(item: Mapping[str, Any]) -> tuple[int, str]:
            values = [item.get("name"), item.get("type"), item.get("category"), item.get("colour"), item.get("pattern")]
            item_tokens = _tokens(" ".join(
                value if isinstance(value, str) else " ".join(value) if isinstance(value, list) else ""
                for value in values
            ))
            return (len(candidate_tokens & item_tokens), str(item.get("id", item.get("item_id"))))

        prototype = max(eligible, key=rank)
        prototype_id = prototype.get("id", prototype.get("item_id"))
        used.add(prototype_id)
        resolved.append({
            **candidate,
            "slot": slot,
            "id": candidate_id,
            "embedding": prototype["embedding"],
            "category": candidate.get("category") or prototype.get("category") or slot,
            "representation": "wardrobe_image_proxy",
            "proxy_item_id": prototype_id,
            "proxy_source": prototype.get("image_crop") or prototype.get("source_path"),
        })
    return resolved


def resolve_candidates_from_cache(
    candidates: Sequence[Mapping[str, Any]],
    inventory_path: str,
    embeddings_path: str,
) -> list[dict[str, Any]]:
    try:
        wardrobe = load_items_with_embeddings(inventory_path, embeddings_path)
    except EmbeddingInventoryError:
        raise
    return resolve_candidate_prototypes(candidates, wardrobe)
