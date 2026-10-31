"""Run the local DressMe gap assistant from an exported report."""

from __future__ import annotations

import argparse
import os
import sys

from .agent import AgentConversation, AgentError, DressMeGapAgent
from .config import AgentConfig, ConfigurationError
from .images import collect_wardrobe_images
from .report import GapReportError, GapReportSource
from .sources import LLMGapAnalysisSource, WardrobeInventorySource, WardrobeSourceError


def _print_result(result) -> None:
    print("\n" + result.answer + "\n")
    if result.recommendations:
        source = (result.tool_metadata or {}).get("source", "unknown")
        if source == "precomputed_notebook_export":
            print("Notebook report result (fallback/precomputed):")
        else:
            print("Wardrobe gap results (LLM compatibility judgments; Python-counted):")
        for index, item in enumerate(result.recommendations, start=1):
            if "unlockedOutfits" in item:
                summary = f"{item['unlockedOutfits']} new outfit(s)"
            else:
                summary = f"estimated gain {item.get('gain_lower')}–{item.get('gain_upper')}"
            print(f"{index}. {item.get('description')} — {summary} [{item.get('category')}/{item.get('slot')}]")
    elif result.used_tool == "get_wardrobe_summary" and result.tool_metadata:
        print("Wardrobe summary: " + str(result.tool_metadata))
    print(f"Prompt version: {result.prompt_version}")
    print(f"\nConfigured 9Router route: {result.model}")
    if result.image_count:
        print(f"Images attached to model request: {result.image_count}")
    if result.reported_model_ids:
        print("Model ID(s) reported by gateway: " + ", ".join(result.reported_model_ids))
    if result.usage:
        print("Provider-reported token usage: " + ", ".join(f"{k}={v}" for k, v in result.usage.items()))


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask questions about a DressMe gap report.")
    parser.add_argument("--report", default=None)
    parser.add_argument("--inventory", default="wardrobe/.dressme-cache/full/wardrobe_inventory.json")
    parser.add_argument("--analysis", default="wardrobe/.dressme-cache/llm_gap_analysis.json")
    parser.add_argument(
        "--image",
        action="append",
        default=[],
        help="Local wardrobe photo to analyze (repeat up to three times).",
    )
    parser.add_argument("--wardrobe-dir", default=None, help="Folder containing up to three wardrobe photos.")
    parser.add_argument("question", nargs="?", help="Question to ask about the wardrobe gaps")
    args = parser.parse_args()
    if args.image and args.wardrobe_dir:
        parser.error("Use either --image or --wardrobe-dir, not both.")
    image_paths = args.image
    if args.wardrobe_dir:
        try:
            image_paths = collect_wardrobe_images(args.wardrobe_dir)
        except ValueError as exc:
            parser.error(str(exc))

    try:
        from dotenv import load_dotenv

        load_dotenv()
        config = AgentConfig.from_env()
        report_path = args.report or os.getenv("DRESSME_GAP_REPORT")
        report_source = GapReportSource(report_path) if report_path else None
        inventory_source = (
            WardrobeInventorySource(args.inventory) if os.path.isfile(args.inventory) else None
        )
        try:
            gap_analysis_source = (
                LLMGapAnalysisSource(args.analysis) if os.path.isfile(args.analysis) else None
            )
        except WardrobeSourceError as exc:
            gap_analysis_source = None
            print(f"Primary LLM gap analysis unavailable: {exc}", file=sys.stderr)
        if gap_analysis_source is None and report_source is not None:
            print("Using the precomputed gap report as a fallback.", file=sys.stderr)
        from openai import OpenAI

        client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout_seconds,
            max_retries=0,
        )
        agent = DressMeGapAgent(
            client,
            config,
            report_source,
            wardrobe_source=inventory_source,
            gap_analysis_source=gap_analysis_source,
        )
        if args.question:
            result = agent.run(args.question, images=image_paths)
            _print_result(result)
            return 0
    except (ConfigurationError, GapReportError, AgentError, ImportError, ValueError) as exc:
        print(f"DressMe agent: {exc}", file=sys.stderr)
        return 2

    session = AgentConversation(agent)
    print("DressMe is ready. Ask about your wardrobe; enter /clear to reset or /quit to exit.")
    first_turn = True
    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nDressMe session closed.")
            break
        if not question:
            continue
        if question.casefold() in {"/quit", "/exit", "quit", "exit"}:
            print("DressMe session closed.")
            break
        if question.casefold() == "/clear":
            session.clear()
            print("Conversation history cleared.")
            continue
        try:
            result = session.run(question, images=image_paths if first_turn else None)
            _print_result(result)
        except (AgentError, ValueError) as exc:
            print(f"DressMe agent: {exc}", file=sys.stderr)
        finally:
            first_turn = False
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
