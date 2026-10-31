"""LLM-driven compatibility pipeline with bounded, resumable pair judgments."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Any

from .compatibility import (
    COMPATIBILITY_PROMPT_VERSION,
    CompatibilityError,
    LLMCompatibilityJudge,
    generate_gap_archetypes,
    inventory_fingerprint,
    judge_with_checkpoint,
    load_compatibility_cache,
    load_inventory_items,
    prepare_pair_records,
)
from .config import AgentConfig, ConfigurationError
from .gateway import OpenAICompatibleGateway
from .outfit_engine import gain_bounds


PIPELINE_VERSION = "llm-gap-pipeline-v1"
ARCHETYPE_PROMPT_VERSION = "gap-archetype-v2"


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with path.with_suffix(path.suffix + ".tmp").open("w", encoding="utf-8") as stream:
            temporary = path.with_suffix(path.suffix + ".tmp")
            json.dump(payload, stream, indent=2, ensure_ascii=False)
        temporary.replace(path)
    except OSError:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def _load_or_generate_candidates(
    path: Path,
    gateway: OpenAICompatibleGateway,
    config: AgentConfig,
    items: list[dict[str, Any]],
    max_candidates: int,
) -> list[dict[str, Any]]:
    inventory_hash = inventory_fingerprint(items)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("prompt_version") != ARCHETYPE_PROMPT_VERSION
            or payload.get("inventory_sha256") != inventory_hash
            or payload.get("configured_model") != config.model
        ):
            raise CompatibilityError(
                "Cached candidate archetypes do not match this inventory/model/prompt; choose a new candidate file."
            )
        candidates = payload.get("candidates")
        if not isinstance(candidates, list):
            raise CompatibilityError("Candidate cache has no candidates array.")
        return candidates

    candidates = generate_gap_archetypes(gateway, config, items, max_candidates=max_candidates)
    if not candidates:
        raise CompatibilityError("The LLM returned no gap archetypes for compatibility testing.")
    _write_json_atomic(
        path,
        {
            "prompt_version": ARCHETYPE_PROMPT_VERSION,
            "inventory_sha256": inventory_hash,
            "configured_model": config.model,
            "candidate_source": "llm_generated_archetypes_not_products",
            "candidates": candidates,
        },
    )
    return candidates


def run_pipeline(
    inventory_path: str | Path,
    cache_dir: str | Path,
    output_path: str | Path,
    config: AgentConfig,
    *,
    max_new_pairs: int = 40,
    batch_size: int = 10,
    max_candidates: int = 6,
    candidate_file: str | Path | None = None,
    batch_delay_seconds: float | None = None,
) -> dict[str, Any]:
    from openai import OpenAI

    wardrobe = load_inventory_items(inventory_path, exclude_exact_duplicates=True)
    judge_config = replace(config, model=config.compatibility_model or config.model)
    client = OpenAI(
        api_key=judge_config.api_key,
        base_url=judge_config.base_url,
        timeout=judge_config.timeout_seconds,
        max_retries=0,
    )
    gateway = OpenAICompatibleGateway(client, judge_config)
    cache_root = Path(cache_dir)
    candidate_path = Path(candidate_file) if candidate_file else cache_root / "gap_archetypes.json"
    candidates = _load_or_generate_candidates(candidate_path, gateway, judge_config, wardrobe, max_candidates)
    combined = [*wardrobe, *candidates]
    # Gap candidates are ranked independently; candidate-candidate styling is
    # not part of marginal gain unless the user explicitly asks for a basket.
    pair_records = [
        pair for pair in prepare_pair_records(combined)
        if not all(item_id.startswith("candidate-") for item_id in pair["pair_id"].split("::"))
    ]
    pair_cache_path = cache_root / "compatibility_judgments.json"
    judge = LLMCompatibilityJudge(gateway, judge_config)
    progress = judge_with_checkpoint(
        judge,
        combined,
        pair_records,
        pair_cache_path,
        batch_size=batch_size,
        max_new_pairs=max_new_pairs,
        batch_delay_seconds=(
            judge_config.compatibility_batch_delay_seconds
            if batch_delay_seconds is None
            else batch_delay_seconds
        ),
    )
    judgments = load_compatibility_cache(
        pair_cache_path,
        inventory_hash=inventory_fingerprint(combined),
        model=judge_config.model,
    )
    verdicts: dict[tuple[str, str], str] = {}
    for key, value in judgments.items():
        left, right = key.split("::", 1)
        verdicts[(left, right)] = value["verdict"]

    complete = progress["remaining_pairs"] == 0
    candidate_results = []
    if complete:
        for candidate in candidates:
            bounds = gain_bounds(wardrobe, candidate, verdicts)
            candidate_results.append(
                {
                    "item_id": candidate["item_id"],
                    "description": candidate["description"],
                    "category": candidate["category"],
                    "slot": candidate["slot"],
                    "llm_rationale": candidate["rationale"],
                    **bounds,
                }
            )
        candidate_results.sort(key=lambda item: (item["gain_lower"], item["gain_upper"]), reverse=True)
        for rank, candidate in enumerate(candidate_results, start=1):
            candidate["rank_by_conservative_gain"] = rank

    payload = {
        "pipeline_version": PIPELINE_VERSION,
        "status": "complete" if complete else "compatibility_judgments_incomplete",
        "source": "fashionclip_inventory_plus_llm_compatibility_judgments",
        "notebook_gap_report_used": False,
        "configured_model_route": config.model,
        "compatibility_judge_model": judge_config.model,
        "compatibility_prompt_version": COMPATIBILITY_PROMPT_VERSION,
        "candidate_prompt_version": ARCHETYPE_PROMPT_VERSION,
        "inventory": {
            "source": str(inventory_path),
            "unique_items": len(wardrobe),
            "duplicate_images_excluded": True,
        },
        "candidate_count": len(candidates),
        "compatibility_progress": progress,
        "count_method": "notebook outfit templates with capped optional outer/bag layers; Python counts only LLM-labelled compatible pairs",
        "uncertainty_method": "unknown pair judgments produce conservative and optimistic gain bounds",
        "ranking_ready": complete,
        "candidates": candidate_results if complete else [],
        "next_action": None if complete else "Resume this pipeline; cached pair judgments are retained and no completed pair is resent.",
    }
    output = Path(output_path)
    _write_json_atomic(output, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build LLM-judged wardrobe-gap estimates from a FashionCLIP inventory.")
    parser.add_argument("--inventory", default="wardrobe/.dressme-cache/full/wardrobe_inventory.json")
    parser.add_argument("--cache-dir", default="wardrobe/.dressme-cache/llm-gap-v1")
    parser.add_argument("--output", default="wardrobe/.dressme-cache/llm_gap_analysis.json")
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--batch-delay", type=float, default=None)
    parser.add_argument("--max-candidates", type=int, default=6)
    parser.add_argument("--candidate-file", default=None, help="Reuse a validated candidate-archetype cache.")
    parser.add_argument(
        "--max-new-pairs",
        type=int,
        default=40,
        help="Bounded LLM work for one run; rerun to resume the checkpoint.",
    )
    args = parser.parse_args()
    try:
        from dotenv import load_dotenv

        load_dotenv()
        config = AgentConfig.from_env()
        result = run_pipeline(
            args.inventory,
            args.cache_dir,
            args.output,
            config,
            max_new_pairs=args.max_new_pairs,
            batch_size=args.batch_size,
            max_candidates=args.max_candidates,
            candidate_file=args.candidate_file,
            batch_delay_seconds=args.batch_delay,
        )
    except (ConfigurationError, CompatibilityError, ImportError, OSError, ValueError) as exc:
        print(f"LLM gap pipeline failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        # Provider payloads may contain request details; log only the safe category.
        category = getattr(exc, "category", type(exc).__name__)
        status = getattr(exc, "status_code", None)
        status_note = f" HTTP {status}" if isinstance(status, int) else ""
        safe_message = str(exc) if exc.__class__.__module__.startswith("dressme_gap_agent") else "Gateway request failed."
        print(f"LLM gap pipeline failed ({category}{status_note}): {safe_message}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
