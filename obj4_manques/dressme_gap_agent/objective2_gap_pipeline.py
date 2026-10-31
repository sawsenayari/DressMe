"""Build a proxy-based Objective 4 gap ranking from the Objective 2 /pairs API."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any

from .candidate_prototypes import resolve_candidates_from_cache
from .compatibility_provider import Objective2CompatibilityProvider
from .compatibility_scores import scores_to_verdicts
from .contracts import validate_gap_result
from .embedding_inventory import load_items_with_embeddings
from .outfit_engine import gain_bounds, required_pair_keys
from .slot_mapping import normalize_slot

PIPELINE_VERSION = "objective2-gap-pipeline-v1"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _service_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "embedding": item["embedding"],
        "slot": normalize_slot(item["slot"]),
    }


def _score_required_pairs(
    items: list[dict[str, Any]],
    provider: Objective2CompatibilityProvider,
    *,
    chunk_size: int = 32,
) -> tuple[dict[tuple[str, str], float], int]:
    required = set(required_pair_keys(items))
    by_slot: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_slot[normalize_slot(item["slot"])].append(item)
    scores: dict[tuple[str, str], float] = {}
    slot_names = sorted(by_slot)
    requests = 0
    for index, left_slot in enumerate(slot_names):
        for right_slot in slot_names[index + 1 :]:
            left = by_slot[left_slot]
            right = by_slot[right_slot]
            for left_offset in range(0, len(left), chunk_size):
                left_chunk = left[left_offset : left_offset + chunk_size]
                for right_offset in range(0, len(right), chunk_size):
                    right_chunk = right[right_offset : right_offset + chunk_size]
                    matrix = provider.score_items(
                        [_service_item(item) for item in left_chunk],
                        [_service_item(item) for item in right_chunk],
                    )
                    requests += 1
                    for left_item, row in zip(left_chunk, matrix):
                        for right_item, score in zip(right_chunk, row):
                            key = tuple(sorted((left_item["id"], right_item["id"])))
                            if key in required:
                                scores[key] = score
    missing = required - set(scores)
    if missing:
        raise RuntimeError(f"Objective 2 did not return {len(missing)} required pair scores.")
    return scores, requests


def run_pipeline(
    inventory_path: str | Path,
    embeddings_path: str | Path,
    candidate_path: str | Path,
    output_path: str | Path,
    *,
    base_url: str = "http://127.0.0.1:8002",
    score_cache_path: str | Path | None = None,
    compatible_threshold: float = 0.70,
    incompatible_threshold: float = 0.40,
    timeout_seconds: float = 120.0,
) -> dict[str, Any]:
    wardrobe = [
        item for item in load_items_with_embeddings(inventory_path, embeddings_path)
        if item.get("duplicate_of") is None
    ]
    candidate_payload = json.loads(Path(candidate_path).read_text(encoding="utf-8"))
    candidates = candidate_payload.get("candidates") if isinstance(candidate_payload, dict) else None
    if not isinstance(candidates, list):
        raise ValueError("candidate file must contain a candidates array")
    candidates = resolve_candidates_from_cache(candidates, str(inventory_path), str(embeddings_path))
    combined = [*wardrobe, *candidates]
    provider = Objective2CompatibilityProvider(
        base_url, timeout_seconds=timeout_seconds, cache_path=score_cache_path
    )
    raw_scores, request_count = _score_required_pairs(combined, provider)
    score_rows = []
    for pair, score in raw_scores.items():
        score_rows.append((pair, score))
    left_items = [{"id": pair[0]} for pair, _ in score_rows]
    right_items = [{"id": pair[1]} for pair, _ in score_rows]
    # Convert the already validated scalar scores without making a second service call.
    verdicts = {
        pair: scores_to_verdicts(
            [{"id": pair[0]}],
            [{"id": pair[1]}],
            [[score]],
            compatible_threshold=compatible_threshold,
            incompatible_threshold=incompatible_threshold,
        )[pair]
        for pair, score in score_rows
    }
    results = []
    for candidate in candidates:
        bounds = gain_bounds(wardrobe, candidate, verdicts)
        results.append({
            "item_id": candidate["id"],
            "description": candidate["description"],
            "slot": candidate["slot"],
            "llm_rationale": candidate.get("rationale", ""),
            "representation": candidate["representation"],
            "proxy_item_id": candidate["proxy_item_id"],
            **bounds,
        })
    results.sort(key=lambda item: (-item["gain_lower"], -item["gain_upper"], item["item_id"]))
    for rank, result in enumerate(results, start=1):
        result["rank"] = rank
    payload = {
        "contract_version": "1.0",
        "pipeline_version": PIPELINE_VERSION,
        "status": "complete",
        "ranking_ready": True,
        "compatibility_progress": {
            "total_pairs": len(required_pair_keys(combined)),
            "completed_pairs": len(raw_scores),
            "remaining_pairs": 0,
        },
        "source": "objective2_pairs_plus_deterministic_outfit_counter",
        "representation": "wardrobe_image_proxy",
        "inventory_items": len(wardrobe),
        "candidate_count": len(candidates),
        "objective2": {
            "base_url": base_url,
            "score_requests": request_count,
            "compatible_threshold": compatible_threshold,
            "incompatible_threshold": incompatible_threshold,
            "calibration_status": "thresholds_not_yet_team_calibrated",
        },
        "gaps": results,
    }
    validate_gap_result(payload)
    _write_json(Path(output_path), payload)
    return payload


def main() -> int:
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", default="wardrobe/.dressme-cache/full/wardrobe_inventory.json")
    parser.add_argument("--embeddings", default="wardrobe/.dressme-cache/full/fashionclip_embeddings.npz")
    parser.add_argument("--candidates", default="wardrobe/.dressme-cache/llm-gap-v1/gap_archetypes.json")
    parser.add_argument("--output", default="wardrobe/.dressme-cache/objective2_gap_analysis.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:8002")
    parser.add_argument("--score-cache", default="wardrobe/.dressme-cache/objective2-pairs.json")
    parser.add_argument("--compatible-threshold", type=float, default=0.70)
    parser.add_argument("--incompatible-threshold", type=float, default=0.40)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    result = run_pipeline(
        args.inventory,
        args.embeddings,
        args.candidates,
        args.output,
        base_url=args.base_url,
        score_cache_path=args.score_cache,
        compatible_threshold=args.compatible_threshold,
        incompatible_threshold=args.incompatible_threshold,
        timeout_seconds=args.timeout,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
