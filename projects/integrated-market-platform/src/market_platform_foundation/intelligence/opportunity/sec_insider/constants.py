"""Lane C SEC insider disclosure vertical — stable identifiers."""

from __future__ import annotations

EXPERT_ID = "sec.insider.disclosure.v1"
DETECTOR_ID = "sec-insider-disclosure"
DETECTOR_VERSION = "1"
DETECTOR_POLICY_ID = "sec-insider-disclosure-policy-v1"
STRATEGY_FAMILY = "PARTICIPANT_INSIDER_DISCLOSURE"
STRATEGY_VERSION = "1"

# Lane B production EventV1 (PR #152): normalize_sec_insider_row / market_trackers.sec_insider.
LANE_B_EVENT_TYPE = "INSIDER_OWNERSHIP_ROW"
LANE_B_PROVIDER_ID = "market_trackers.sec_insider"
LANE_B_CLOCK_KEYS = (
    "economic_event_time_ns",
    "filing_publication_time_ns",
    "sec_acceptance_time_ns",
    "aggregator_retrieved_time_ns",
    "platform_received_time_ns",
)

# Legacy Lane C compat only — not Lane B production shape.
LANE_PAYLOAD_KIND = "sec_insider_transaction"
PAYLOAD_SECTION = "sec_insider"

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
