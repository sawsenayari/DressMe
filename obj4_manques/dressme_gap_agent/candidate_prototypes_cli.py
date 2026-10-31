"""Create explicit Objective 2 candidate proxies from an existing embedding cache."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .candidate_prototypes import resolve_candidates_from_cache


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--embeddings", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    source = json.loads(Path(args.candidates).read_text(encoding="utf-8"))
    candidates = source.get("candidates") if isinstance(source, dict) else None
    if not isinstance(candidates, list):
        raise ValueError("candidate file must contain a candidates array")
    resolved = resolve_candidates_from_cache(candidates, args.inventory, args.embeddings)
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(
        json.dumps(
            {
                "representation": "wardrobe_image_proxy",
                "source_candidates": str(Path(args.candidates)),
                "candidates": resolved,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Resolved {len(resolved)} candidates with explicit wardrobe image proxies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
