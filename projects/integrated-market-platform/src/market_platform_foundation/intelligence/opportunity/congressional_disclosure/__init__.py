"""Lane F congressional PTR disclosure opportunity vertical (read-only runtime)."""

from __future__ import annotations

from .adapters import accepts_congressional_disclosure_event, extract_congressional_disclosure_facts
from .candidate import assert_candidate_not_directional, project_opportunity_candidate
from .constants import EXPERT_ID, FORBIDDEN_CANDIDATE_DIRECTIONS, RUNTIME_EVENT_TYPE, STRATEGY_FAMILY
from .detector import build_detection
from .evidence import build_evidence
from .facts import CongressionalDisclosureFacts
from .pipeline import CongressionalDisclosureVerticalResult, run_congressional_disclosure_vertical
from .validation import CongressionalDisclosureFailureCode, validate_congressional_disclosure_inputs

__all__ = [
    "FORBIDDEN_CANDIDATE_DIRECTIONS",
    "RUNTIME_EVENT_TYPE",
    "STRATEGY_FAMILY",
    "CongressionalDisclosureFacts",
    "CongressionalDisclosureFailureCode",
    "CongressionalDisclosureVerticalResult",
    "accepts_congressional_disclosure_event",
    "assert_candidate_not_directional",
    "build_detection",
    "build_evidence",
    "extract_congressional_disclosure_facts",
    "project_opportunity_candidate",
    "run_congressional_disclosure_vertical",
    "validate_congressional_disclosure_inputs",
]
