"""Interchangeable compatibility providers for Objective 2 pair scores."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Protocol
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

OBJECTIVE2_CATEGORY_BY_SLOT = {
    "top": "tops",
    "bottom": "bottoms",
    "onepiece": "all-body",
    "outer": "outerwear",
    "footwear": "shoes",
    "shoes": "shoes",
    "bag": "bags",
    "accessory": "accessories",
}

class CompatibilityProviderError(ValueError):
    """Raised when a provider request or response violates the pair contract."""


class CompatibilityProvider(Protocol):
    def score_pairs(self, left_ids: Sequence[str], right_ids: Sequence[str]) -> list[list[float]]:
        ...

    def score_items(
        self, left_items: Sequence[Mapping[str, Any]], right_items: Sequence[Mapping[str, Any]]
    ) -> list[list[float]]:
        ...


def _validate_matrix(matrix: Any, rows: int, columns: int) -> list[list[float]]:
    if not isinstance(matrix, list) or len(matrix) != rows:
        raise CompatibilityProviderError("scores01 has an invalid row count")
    result: list[list[float]] = []
    for row in matrix:
        if not isinstance(row, list) or len(row) != columns:
            raise CompatibilityProviderError("scores01 has invalid dimensions")
        clean: list[float] = []
        for score in row:
            if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1:
                raise CompatibilityProviderError("compatibility scores must be finite numbers in [0, 1]")
            clean.append(float(score))
        result.append(clean)
    return result


class MockCompatibilityProvider:
    """Deterministic local provider; scores are explicitly mock data."""

    def __init__(self, scores: Mapping[tuple[str, str], float] | None = None) -> None:
        self._scores = dict(scores or {})

    def score_pairs(self, left_ids: Sequence[str], right_ids: Sequence[str]) -> list[list[float]]:
        if not left_ids or not right_ids or any(not isinstance(value, str) or not value for value in [*left_ids, *right_ids]):
            raise CompatibilityProviderError("pair ID lists must contain non-empty strings")
        result = []
        for left in left_ids:
            row = []
            for right in right_ids:
                explicit = self._scores.get((left, right), self._scores.get((right, left)))
                if explicit is None:
                    digest = hashlib.sha256(f"{left}\0{right}".encode()).digest()
                    explicit = 0.35 + (digest[0] / 255) * 0.4
                row.append(explicit)
            result.append(row)
        return _validate_matrix(result, len(left_ids), len(right_ids))


class Objective2CompatibilityProvider:
    """HTTP client for Objective 2 POST /pairs using full FashionCLIP items."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 120.0, retries: int = 1, cache_path: str | Path | None = None) -> None:
        if retries < 0 or retries > 2:
            raise ValueError("retries must be between 0 and 2")
        self._url = base_url.rstrip("/") + "/pairs"
        self._timeout = timeout_seconds
        self._retries = retries
        self._cache_path = Path(cache_path) if cache_path else None

    def _cache_key(self, left_items: Sequence[Mapping[str, Any]], right_items: Sequence[Mapping[str, Any]]) -> str:
        return json.dumps({"a": list(left_items), "b": list(right_items)}, separators=(",", ":"), sort_keys=True)

    @staticmethod
    def _validate_items(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        result = []
        for item in items:
            if not isinstance(item, Mapping):
                raise CompatibilityProviderError("Objective 2 items must be objects")
            item_id = item.get("id", item.get("item_id"))
            embedding = item.get("embedding")
            if not isinstance(item_id, str) or not item_id or not isinstance(embedding, Sequence) or isinstance(embedding, (str, bytes)) or len(embedding) != 512:
                raise CompatibilityProviderError("Objective 2 items require an id and a 512-value embedding")
            category = item.get("category")
            slot = item.get("slot")
            if not isinstance(category, str) and not isinstance(slot, str):
                raise CompatibilityProviderError("Objective 2 items require category or slot")
            service_category = category if category in {
                "accessories", "all-body", "bags", "bottoms", "hats", "jewellery",
                "outerwear", "scarves", "shoes", "sunglasses", "tops",
            } else OBJECTIVE2_CATEGORY_BY_SLOT.get(slot)
            if service_category is None:
                raise CompatibilityProviderError("item category cannot be mapped to Objective 2")
            result.append({
                "id": item_id,
                "embedding": [float(value) for value in embedding],
                "category": service_category,
                **({"slot": slot} if isinstance(slot, str) else {}),
            })
        if not result:
            raise CompatibilityProviderError("Objective 2 item lists cannot be empty")
        return result

    def score_items(
        self, left_items: Sequence[Mapping[str, Any]], right_items: Sequence[Mapping[str, Any]]
    ) -> list[list[float]]:
        left = self._validate_items(left_items)
        right = self._validate_items(right_items)
        return self._request(left, right)

    def score_pairs(self, left_ids: Sequence[str], right_ids: Sequence[str]) -> list[list[float]]:
        raise CompatibilityProviderError(
            "Objective 2 /pairs requires full items with 512-value FashionCLIP embeddings; use score_items()."
        )

    def _request(self, left: Sequence[Mapping[str, Any]], right: Sequence[Mapping[str, Any]]) -> list[list[float]]:
        cache: dict[str, Any] = {}
        if self._cache_path and self._cache_path.exists():
            try:
                cache = json.loads(self._cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise CompatibilityProviderError("compatibility cache is invalid") from exc
        key = self._cache_key(left, right)
        if key in cache:
            return _validate_matrix(cache[key], len(left), len(right))
        body = json.dumps({"a": list(left), "b": list(right)}).encode()
        last_error: Exception | None = None
        for _ in range(self._retries + 1):
            try:
                request = Request(self._url, data=body, headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(request, timeout=self._timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                matrix = _validate_matrix(payload.get("scores01") if isinstance(payload, dict) else None, len(left), len(right))
                if self._cache_path:
                    cache[key] = matrix
                    self._cache_path.parent.mkdir(parents=True, exist_ok=True)
                    self._cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
                return matrix
            except (OSError, URLError, HTTPError, json.JSONDecodeError, CompatibilityProviderError) as exc:
                last_error = exc
        raise CompatibilityProviderError("Objective 2 /pairs request failed") from last_error
