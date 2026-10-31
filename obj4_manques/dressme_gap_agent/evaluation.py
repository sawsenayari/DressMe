"""Run the versioned live LLM evaluation set and write machine-readable results."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
import tempfile
import time
from typing import Any

from PIL import Image, ImageDraw

from .agent import AgentError, DressMeGapAgent
from .config import AgentConfig, ConfigurationError
from .report import GapReportError, GapReportSource


def _recommendations_match(actual: list[dict[str, Any]], expected: list[dict[str, Any]]) -> bool:
    if len(actual) < len(expected):
        return False
    return all(
        actual_item.get("id") == expected_item.get("id")
        and actual_item.get("unlockedOutfits") == expected_item.get("unlockedOutfits")
        for actual_item, expected_item in zip(actual, expected)
    )


def _normalize_answer_text(text: str) -> str:
    return (
        text.casefold()
        .replace("\u2011", "-")
        .replace("\u202f", " ")
        .replace("*", "")
        .replace("`", "")
    )


def evaluate_case(
    agent: DressMeGapAgent,
    case: dict[str, Any],
    image_paths: list[str | Path] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        run_options: dict[str, Any] = {"context": case.get("context")}
        if image_paths is not None:
            run_options["images"] = image_paths
        result = agent.run(case["question"], **run_options)
    except (AgentError, ValueError) as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return {
            "id": case["id"],
            "success": False,
            "error_category": exc.category if isinstance(exc, AgentError) else type(exc).__name__,
            "safe_error": str(exc),
            "latency_ms": round(elapsed_ms, 1),
            "prompt_version": None,
            "tool_correct": False,
            "tool_arguments_correct": False,
            "recommendations_match": False,
            "required_terms_present": False,
            "forbidden_terms_absent": False,
            "security_pass": None,
            "answer": None,
        }

    elapsed_ms = (time.perf_counter() - started) * 1000
    answer_folded = _normalize_answer_text(result.answer)
    required_terms = [_normalize_answer_text(term) for term in case.get("required_answer_terms", [])]
    required_any_groups = [
        [_normalize_answer_text(term) for term in group]
        for group in case.get("required_answer_any_terms", [])
    ]
    forbidden_terms = [_normalize_answer_text(term) for term in case.get("forbidden_answer_terms", [])]
    expected_tool = case.get("expected_tool")
    expected_args = case.get("expected_tool_arguments")
    expected_args_min = case.get("expected_tool_arguments_min", {})
    expected_args_max = case.get("expected_tool_arguments_max", {})
    tool_correct = result.used_tool == expected_tool
    arguments_correct = (
        (expected_args is None or result.tool_arguments == expected_args)
        and all(
            isinstance(result.tool_arguments, dict)
            and isinstance(result.tool_arguments.get(key), (int, float))
            and not isinstance(result.tool_arguments.get(key), bool)
            and result.tool_arguments[key] >= minimum
            for key, minimum in expected_args_min.items()
        )
        and all(
            isinstance(result.tool_arguments, dict)
            and isinstance(result.tool_arguments.get(key), (int, float))
            and not isinstance(result.tool_arguments.get(key), bool)
            and result.tool_arguments[key] <= maximum
            for key, maximum in expected_args_max.items()
        )
    )
    recommendations_match = _recommendations_match(
        result.recommendations, case.get("expected_recommendations", [])
    )
    required_present = all(term in answer_folded for term in required_terms) and all(
        any(term in answer_folded for term in group) for group in required_any_groups
    )
    forbidden_absent = not any(term in answer_folded for term in forbidden_terms)
    checks = [tool_correct, arguments_correct, recommendations_match, required_present, forbidden_absent]

    return {
        "id": case["id"],
        "success": all(checks),
        "latency_ms": round(elapsed_ms, 1),
        "prompt_version": result.prompt_version,
        "configured_route": result.model,
        "reported_model_ids": result.reported_model_ids,
        "usage": result.usage,
        "used_tool": result.used_tool,
        "tool_arguments": result.tool_arguments,
        "tool_correct": tool_correct,
        "tool_arguments_correct": arguments_correct,
        "recommendations_match": recommendations_match,
        "recommendation_ids": [item["id"] for item in result.recommendations],
        "recommendation_gains": [item["unlockedOutfits"] for item in result.recommendations],
        "required_terms_present": required_present,
        "forbidden_terms_absent": forbidden_absent,
        "security_pass": forbidden_absent if case.get("security_test") else None,
        "manual_review": case.get("manual_review"),
        "answer": result.answer,
    }


def run_evaluation(
    cases_path: str | Path,
    report_path: str | Path,
    output_path: str | Path,
    config: AgentConfig,
) -> dict[str, Any]:
    from openai import OpenAI

    dataset = json.loads(Path(cases_path).read_text(encoding="utf-8"))
    if not isinstance(dataset, dict) or not isinstance(dataset.get("cases"), list):
        raise ValueError("Evaluation file must contain a cases array.")
    client = OpenAI(
        api_key=config.api_key,
        base_url=config.base_url,
        timeout=config.timeout_seconds,
        max_retries=0,
    )
    agent = DressMeGapAgent(client, config, GapReportSource(report_path))
    case_results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="dressme-image-eval-") as temp_dir:
        for case in dataset["cases"]:
            fixture = case.get("synthetic_image")
            if fixture:
                if fixture != "red_shirt":
                    raise ValueError(f"Unsupported synthetic image fixture: {fixture}")
                image_path = Path(temp_dir) / "synthetic_red_shirt.png"
                _write_synthetic_red_shirt(image_path)
                case_results.append(evaluate_case(agent, case, [image_path]))
            else:
                case_results.append(evaluate_case(agent, case))

    evaluated_results = [result for result in case_results if result.get("status") != "skipped"]
    count = len(evaluated_results)
    successful = sum(result["success"] for result in evaluated_results)
    latencies = [result["latency_ms"] for result in evaluated_results]
    security_results = [r["security_pass"] for r in evaluated_results if r.get("security_pass") is not None]
    summary = {
        "dataset_version": dataset.get("dataset_version"),
        "prompt_version": next((r.get("prompt_version") for r in evaluated_results if r.get("prompt_version")), None),
        "configured_route": config.model,
        "cases_total": len(case_results),
        "cases_evaluated": count,
        "cases_skipped": len(case_results) - count,
        "successful_cases": successful,
        "success_rate": successful / count if count else None,
        "tool_correct_rate": sum(r["tool_correct"] for r in evaluated_results) / count if count else None,
        "tool_argument_correct_rate": sum(r["tool_arguments_correct"] for r in evaluated_results) / count if count else None,
        "recommendation_match_rate": sum(r["recommendations_match"] for r in evaluated_results) / count if count else None,
        "answer_criteria_rate": sum(r["required_terms_present"] and r["forbidden_terms_absent"] for r in evaluated_results) / count if count else None,
        "security_cases": len(security_results),
        "security_pass_rate": sum(security_results) / len(security_results) if security_results else None,
        "mean_latency_ms": round(statistics.mean(latencies), 1) if latencies else None,
        "usage_available_cases": sum(r.get("usage") is not None for r in evaluated_results),
        "cost": None,
        "cost_note": "Not estimated: provider pricing and model actually serving the combo were not verified by this runner.",
        "manual_review_required": [r["id"] for r in evaluated_results if r.get("manual_review")],
    }
    payload = {"summary": summary, "results": case_results}
    Path(output_path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def _write_synthetic_red_shirt(path: Path) -> None:
    """Create a deterministic synthetic visual smoke fixture, not a real garment photo."""
    image = Image.new("RGB", (240, 240), "white")
    draw = ImageDraw.Draw(image)
    draw.polygon(
        [(80, 45), (45, 75), (65, 115), (85, 105), (85, 195), (155, 195),
         (155, 105), (175, 115), (195, 75), (160, 45), (140, 65), (100, 65)],
        fill=(180, 35, 45),
    )
    image.save(path, format="PNG")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DressMe's fixed live LLM evaluation set.")
    parser.add_argument("--cases", default="llm_evaluation_cases.json")
    parser.add_argument("--report", default="gap_report.json")
    parser.add_argument("--output", default="llm_eval_results.json")
    args = parser.parse_args()
    try:
        from dotenv import load_dotenv

        load_dotenv()
        config = AgentConfig.from_env()
        result = run_evaluation(args.cases, args.report, args.output, config)
    except (ConfigurationError, GapReportError, ImportError, ValueError, OSError) as exc:
        print(f"DressMe evaluation failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
    print(f"Detailed results saved to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
