"""Lane C SEC insider disclosure vertical — stable identifiers."""

from __future__ import annotations

EXPERT_ID = "sec.insider.disclosure.v1"
DETECTOR_ID = "sec-insider-disclosure"
DETECTOR_VERSION = "1"
DETECTOR_POLICY_ID = "sec-insider-disclosure-policy-v1"
STRATEGY_FAMILY = "PARTICIPANT_INSIDER_DISCLOSURE"
STRATEGY_VERSION = "1"

# Narrow EventV1.payload discriminators (Lane B may bind without changing EventV1).
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
