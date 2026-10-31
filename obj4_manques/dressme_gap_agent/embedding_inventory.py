"""Join a FashionCLIP inventory with its row-aligned embedding cache."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class EmbeddingInventoryError(ValueError):
    """Raised when inventory and FashionCLIP embeddings cannot be joined safely."""


def load_items_with_embeddings(
    inventory_path: str | Path,
    embeddings_path: str | Path,
) -> list[dict[str, Any]]:
    import numpy as np

    try:
        payload = json.loads(Path(inventory_path).read_text(encoding="utf-8"))
        archive = np.load(embeddings_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise EmbeddingInventoryError("Could not read the inventory or embedding cache.") from exc
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise EmbeddingInventoryError("Inventory must contain an items array.")
    if not all(key in archive for key in ("item_ids", "embeddings")):
        raise EmbeddingInventoryError("Embedding cache must contain item_ids and embeddings.")
    item_ids = archive["item_ids"]
    embeddings = archive["embeddings"]
    if embeddings.ndim != 2 or embeddings.shape[1] != 512 or len(item_ids) != len(embeddings) or len(items) != len(embeddings):
        raise EmbeddingInventoryError("Inventory and embedding cache dimensions do not match.")
    result = []
    for item, item_id, embedding in zip(items, item_ids.tolist(), embeddings):
        if item.get("item_id") != item_id:
            raise EmbeddingInventoryError("Inventory and embedding row order differs.")
        values = embedding.astype("float32").tolist()
        result.append({**item, "id": item_id, "embedding": values})
    return result
