"""P1-1: single explicit eligibility gate before OrderReadyV1 execution intent.

One checkable predicate answers "may this strategy drive an order with execution
intent?" by combining three legs that are each recorded elsewhere in the
governance ladder:

1. preregistration  — the strategy identity was preregistered before any
   interpretation and the identity on the order path matches that record;
2. promotion state  — the driving champion is an ACTIVE champion reached
   through the promotion engine (assignment reason PROMOTION carrying a
   promotion decision), never an unknown or unpromoted strategy;
3. forward-evidence class — the champion's evidence includes a forward
   (post-registration) evidence tier rather than replay/synthetic history
   only.

The predicate is pure: callers supply the recorded facts (mirroring the
"caller supplies evidence flags only" convention in shadow acceptance) and
receive an immutable, deterministically-addressed record. Order-ready intent
is auditable to that record through its record id.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..intelligence.promotion.types import (
    ChampionAssignmentReason,
    ChampionAssignmentStatus,
    EligibilityDisposition,
)
from ..intelligence.research_experiments.types import EvidenceTier

EXECUTION_ELIGIBILITY_SCHEMA_VERSION = "1"
EXECUTION_ELIGIBILITY_RECORD_PREFIX = "STRATEGY-ELIGIBILITY"

PREREGISTRATION_STATUS_PASS = "PASS"
PREREGISTRATION_STATUS_FAIL = "FAIL"
PREREGISTRATION_STATUS_ABSENT = "ABSENT"

# Evidence tiers that represent forward (post-registration) observation and may
# therefore qualify a promoted champion for execution intent. Counterfactual
# replay and synthetic tests are backward-looking evidence for the promotion
# decision itself; they cannot by themselves carry execution intent.
FORWARD_EVIDENCE_CLASSES_FOR_EXECUTION_INTENT: frozenset[str] = frozenset(
    {
        EvidenceTier.ACTUAL_LIVE.value,
        EvidenceTier.OBSERVED_REPLAY.value,
    }
)

# Reason tokens attached to an ineligible record (and surfaced through the
# order-ready gate code / diagnostics).
REASON_STRATEGY_NOT_PREREGISTERED = "STRATEGY_NOT_PREREGISTERED"
REASON_PREREGISTRATION_VERIFICATION_FAILED = "PREREGISTRATION_VERIFICATION_FAILED"
REASON_NO_CHAMPION_ASSIGNMENT = "NO_CHAMPION_ASSIGNMENT"
REASON_CHAMPION_NOT_ACTIVE = "CHAMPION_NOT_ACTIVE"
REASON_CHAMPION_NOT_PROMOTED = "CHAMPION_NOT_PROMOTED"
REASON_PROMOTION_DECISION_REF_MISSING = "PROMOTION_DECISION_REF_MISSING"
REASON_FORWARD_EVIDENCE_CLASS_NOT_ESTABLISHED = "FORWARD_EVIDENCE_CLASS_NOT_ESTABLISHED"
REASON_FORWARD_EVIDENCE_CLASS_INELIGIBLE = "FORWARD_EVIDENCE_CLASS_INELIGIBLE"

# Code stamped on a BLOCKED OrderReadyV1 when the gate (not risk) is the
# blocker, so downstream audit can distinguish governance denial from risk
# denial on the persisted readiness record.
GATE_REASON_CODE = "STRATEGY_EXECUTION_ELIGIBILITY_BLOCKED"

# ContractReference kind used to make per-order intent auditable to the
# eligibility record it was assessed against.
ELIGIBILITY_REF_KIND = "strategy_eligibility"


class ExecutionEligibilityState(StrEnum):
    """Disposition of the execution-intent predicate (mirrors governance
    EligibilityDisposition values so callers can compare by value)."""

    ELIGIBLE = EligibilityDisposition.ELIGIBLE.value
    INELIGIBLE = EligibilityDisposition.INELIGIBLE.value
    INCONCLUSIVE = EligibilityDisposition.INCONCLUSIVE.value


@dataclass(frozen=True, slots=True)
class StrategyEligibilityRecordV1:
    """Immutable, deterministically-addressed record of one gate assessment.

    Per-order execution intent references this record by id; the record is
    reproducible from the same recorded facts, so an auditor can recompute it
    byte-for-byte.
    """

    record_id: str
    schema_version: str
    strategy_id: str
    preregistration_status: str
    champion_assignment_id: str | None
    champion_assignment_reason: str | None
    champion_status: str | None
    promotion_decision_id: str | None
    forward_evidence_class: str | None
    disposition: str
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.record_id or not self.schema_version or not self.strategy_id:
            raise ValueError("STRATEGY_ELIGIBILITY_RECORD_IDENTITY_REQUIRED")
        if self.disposition not in {
            ExecutionEligibilityState.ELIGIBLE.value,
            ExecutionEligibilityState.INELIGIBLE.value,
            ExecutionEligibilityState.INCONCLUSIVE.value,
        }:
            raise ValueError("STRATEGY_ELIGIBILITY_DISPOSITION_INVALID")
        object.__setattr__(self, "reasons", tuple(self.reasons))

    @property
    def eligible(self) -> bool:
        return self.disposition == ExecutionEligibilityState.ELIGIBLE.value


def _record_identity_payload(
    *,
    strategy_id: str,
    preregistration_status: str,
    champion_assignment_id: str | None,
    champion_assignment_reason: str | None,
    champion_status: str | None,
    promotion_decision_id: str | None,
    forward_evidence_class: str | None,
    disposition: str,
    reasons: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "schema_version": EXECUTION_ELIGIBILITY_SCHEMA_VERSION,
        "strategy_id": strategy_id,
        "preregistration_status": preregistration_status,
        "champion_assignment_id": champion_assignment_id,
        "champion_assignment_reason": champion_assignment_reason,
        "champion_status": champion_status,
        "promotion_decision_id": promotion_decision_id,
        "forward_evidence_class": forward_evidence_class,
        "disposition": disposition,
        "reasons": sorted(set(reasons)),
    }


def _derive_record_id(payload: Mapping[str, Any]) -> str:
    digest = sha256_bytes(canonical_bytes(dict(payload)))
    return f"{EXECUTION_ELIGIBILITY_RECORD_PREFIX}-{digest}"


def assess_strategy_execution_eligibility(
    *,
    strategy_id: str,
    preregistration_status: str = PREREGISTRATION_STATUS_ABSENT,
    champion_assignment_id: str | None = None,
    champion_assignment_reason: str | None = None,
    champion_status: str | None = None,
    promotion_decision_id: str | None = None,
    forward_evidence_class: str | None = None,
) -> StrategyEligibilityRecordV1:
    """Evaluate the single execution-intent predicate from recorded facts.

    Unknown or unpromoted strategies are INELIGIBLE (fail closed): a missing
    preregistration, a missing/non-active champion, a champion that did not
    reach ACTIVE champion through promotion, or a missing promotion-decision
    reference each deny execution intent. A champion that is otherwise sound
    but has not established a forward-evidence class is INCONCLUSIVE (cannot
    be granted execution intent, but the gap is reversible). INELIGIBLE
    outranks INCONCLUSIVE.
    """
    reasons: list[str] = []
    inconclusive: list[str] = []

    if preregistration_status == PREREGISTRATION_STATUS_ABSENT:
        reasons.append(REASON_STRATEGY_NOT_PREREGISTERED)
    elif preregistration_status == PREREGISTRATION_STATUS_FAIL:
        reasons.append(REASON_PREREGISTRATION_VERIFICATION_FAILED)

    if not champion_assignment_id:
        reasons.append(REASON_NO_CHAMPION_ASSIGNMENT)
    elif champion_status != ChampionAssignmentStatus.ACTIVE.value:
        reasons.append(REASON_CHAMPION_NOT_ACTIVE)
    elif champion_assignment_reason != ChampionAssignmentReason.PROMOTION.value:
        reasons.append(REASON_CHAMPION_NOT_PROMOTED)
    elif not promotion_decision_id:
        reasons.append(REASON_PROMOTION_DECISION_REF_MISSING)

    if forward_evidence_class is None:
        inconclusive.append(REASON_FORWARD_EVIDENCE_CLASS_NOT_ESTABLISHED)
    elif forward_evidence_class not in FORWARD_EVIDENCE_CLASSES_FOR_EXECUTION_INTENT:
        reasons.append(REASON_FORWARD_EVIDENCE_CLASS_INELIGIBLE)

    if reasons:
        disposition = ExecutionEligibilityState.INELIGIBLE.value
    elif inconclusive:
        disposition = ExecutionEligibilityState.INCONCLUSIVE.value
    else:
        disposition = ExecutionEligibilityState.ELIGIBLE.value

    record_reasons = tuple(dict.fromkeys([*reasons, *inconclusive]))
    payload = _record_identity_payload(
        strategy_id=strategy_id,
        preregistration_status=preregistration_status,
        champion_assignment_id=champion_assignment_id,
        champion_assignment_reason=champion_assignment_reason,
        champion_status=champion_status,
        promotion_decision_id=promotion_decision_id,
        forward_evidence_class=forward_evidence_class,
        disposition=disposition,
        reasons=record_reasons,
    )
    return StrategyEligibilityRecordV1(
        record_id=_derive_record_id(payload),
        schema_version=EXECUTION_ELIGIBILITY_SCHEMA_VERSION,
        strategy_id=strategy_id,
        preregistration_status=preregistration_status,
        champion_assignment_id=champion_assignment_id,
        champion_assignment_reason=champion_assignment_reason,
        champion_status=champion_status,
        promotion_decision_id=promotion_decision_id,
        forward_evidence_class=forward_evidence_class,
        disposition=disposition,
        reasons=record_reasons,
    )
