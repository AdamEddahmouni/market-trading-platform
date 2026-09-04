"""Broker redundancy assessment — advisory only, no auto-failover (BUILD 33)."""

from __future__ import annotations

from .identity import derive_broker_redundancy_assessment_id
from .types import (
    BrokerFailoverAuthorization,
    BrokerRedundancyAssessmentV1,
    BUILD33_KNOWN_LIMITATIONS,
    SUPERVISED_PILOT_IMPLEMENTATION_VERSION,
    SUPERVISED_PILOT_SCHEMA_VERSION,
)


def build_broker_redundancy_assessment(
    *,
    brokers_assessed: tuple[str, ...] = ("tradier.paper", "ibkr.paper"),
) -> BrokerRedundancyAssessmentV1:
    """Assess broker capability overlap; AUTO_FAILOVER remains NOT_AUTHORIZED."""
    overlap: dict[str, tuple[str, ...]] = {}
    for broker in sorted(brokers_assessed):
        if "tradier" in broker:
            overlap[broker] = ("equity_market_order", "equity_limit_order", "account_snapshot")
        elif "ibkr" in broker:
            overlap[broker] = ("equity_market_order", "equity_limit_order", "account_snapshot")
        else:
            overlap[broker] = ("unknown",)

    assessment = BrokerRedundancyAssessmentV1(
        assessment_id="",
        schema_version=SUPERVISED_PILOT_SCHEMA_VERSION,
        brokers_assessed=brokers_assessed,
        capability_overlap=overlap,
        account_isolation=True,
        auto_failover_authorization=BrokerFailoverAuthorization.NOT_AUTHORIZED.value,
        limitations=BUILD33_KNOWN_LIMITATIONS[:4],
        implementation_version=SUPERVISED_PILOT_IMPLEMENTATION_VERSION,
    )
    object.__setattr__(assessment, "assessment_id", derive_broker_redundancy_assessment_id(assessment))
    return assessment


def broker_auto_failover_prohibited(
    *,
    primary_broker: str,
    alternate_broker: str,
    ambiguous_submission: bool,
) -> tuple[bool, tuple[str, ...]]:
    """Return whether alternate broker submission must be blocked."""
    reasons: list[str] = []
    if ambiguous_submission:
        reasons.append("AMBIGUOUS_PRIMARY_SUBMISSION")
    reasons.append("AUTO_BROKER_FAILOVER_NOT_AUTHORIZED")
    return True, tuple(reasons)
