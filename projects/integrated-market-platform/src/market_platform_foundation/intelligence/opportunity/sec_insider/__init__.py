"""Lane C SEC insider disclosure opportunity vertical (isolated)."""

from __future__ import annotations

from .adapters import (
    accepts_sec_insider_event,
    extract_sec_insider_facts,
    filing_payload_with_sec_insider_section,
)
from .candidate import assert_candidate_not_form4_directional, project_opportunity_candidate
from .constants import EXPERT_ID, LANE_PAYLOAD_KIND, PAYLOAD_SECTION
from .detector import build_detection
from .evidence import build_evidence
from .facts import SecInsiderDisclosureFacts, facts_from_market_trackers_row
from .pipeline import SecInsiderVerticalResult, run_sec_insider_vertical
from .validation import SecInsiderFailureCode, validate_sec_insider_inputs

__all__ = [
    "EXPERT_ID",
    "LANE_PAYLOAD_KIND",
    "PAYLOAD_SECTION",
    "SecInsiderDisclosureFacts",
    "SecInsiderFailureCode",
    "SecInsiderVerticalResult",
    "accepts_sec_insider_event",
    "assert_candidate_not_form4_directional",
    "build_detection",
    "build_evidence",
    "extract_sec_insider_facts",
    "facts_from_market_trackers_row",
    "filing_payload_with_sec_insider_section",
    "project_opportunity_candidate",
    "run_sec_insider_vertical",
    "validate_sec_insider_inputs",
]
