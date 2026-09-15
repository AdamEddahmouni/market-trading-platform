"""Lane F congressional PTR disclosure opportunity vertical (read-only)."""

from __future__ import annotations

EXPERT_ID = "congressional.ptr.disclosure.v1"
DETECTOR_ID = "congressional-ptr-disclosure"
DETECTOR_VERSION = "1"
DETECTOR_POLICY_ID = "congressional-ptr-disclosure-policy-v1"
STRATEGY_FAMILY = "PARTICIPANT_CONGRESSIONAL_DISCLOSURE"
STRATEGY_VERSION = "1"

RUNTIME_EVENT_TYPE = "CONGRESSIONAL_PTR_ROW"
RUNTIME_PROVIDER_ID = "market_trackers.congressional_disclosure"
RUNTIME_CLOCK_KEYS = (
    "economic_event_time_ns",
    "filing_publication_time_ns",
    "ptr_primary_publication_time_ns",
    "aggregator_retrieved_time_ns",
    "platform_received_time_ns",
)

FORBIDDEN_CANDIDATE_DIRECTIONS = frozenset(
    {
        "LONG",
        "SHORT",
        "BULLISH",
        "BEARISH",
        "BUY",
        "SELL",
    }
)
