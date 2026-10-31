"""Local LLM agent for explaining DressMe wardrobe-gap reports."""

from .agent import DressMeGapAgent, AgentResult
from .compatibility_provider import MockCompatibilityProvider, Objective2CompatibilityProvider
from .config import AgentConfig
from .report import GapReportSource, load_gap_report
from .wardrobe_loader import WardrobeInventory, WardrobeValidationReport, load_wardrobe_from_json

__all__ = [
    "AgentConfig",
    "AgentResult",
    "DressMeGapAgent",
    "GapReportSource",
    "MockCompatibilityProvider",
    "Objective2CompatibilityProvider",
    "WardrobeInventory",
    "WardrobeValidationReport",
    "load_gap_report",
    "load_wardrobe_from_json",
]
