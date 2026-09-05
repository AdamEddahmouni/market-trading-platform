"""Fixture-driven promotion dry-run harness (hardening P0-2).

The dry run replays recorded paper / shadow outcomes through the BUILD 20
champion-challenger promotion ladder and emits an immutable decision record
(``PromotionDryRunRecord``). Its purpose is to prove the ladder works end to
end — registration, eligibility, metric/statistical gates, shadow evidence,
and a deterministic ``PROMOTE`` / ``RETAIN_CHAMPION`` / ``INCONCLUSIVE`` /
``INVALID`` decision — without claiming an edge.

The record grants **no execution authority**: a promotion decision is not a
deploy, not a hot-swap, and not an order. Nothing in this module can reach an
execution path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ..research_experiments.types import ExperimentManifestV1
from ..training.types import CandidateArtifactV1
from ..validation import ValidationReportV1
from .engine import PromotionEngine
from .serialization import promotion_decision_v1_to_dict
from .types import (
    ChallengerRegistrationV1,
    ChampionAssignmentV1,
    PromotionDecisionV1,
    PromotionPolicyV1,
    ShadowEvidenceManifestV1,
)

DRY_RUN_SCHEMA_VERSION = "promotion_dry_run.v1"

#: The dry run never names an execution surface. Kept as a literal so a future
#: change to this module that reaches toward execution is caught by tests.
DRY_RUN_DISALLOWED_TOKENS = ("TradeProposal", "broker", "OrderReady")


@dataclass(frozen=True, slots=True)
class PromotionDryRunRecord:
    """Immutable record of one promotion dry run."""

    dry_run_id: str
    decision: PromotionDecisionV1 = field(compare=True)
    schema_version: str = DRY_RUN_SCHEMA_VERSION
    preregistration_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    grants_execution_authority: bool = False


def _record_body(
    decision: PromotionDecisionV1,
    preregistration_refs: tuple[str, ...],
    evidence_refs: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "schema_version": DRY_RUN_SCHEMA_VERSION,
        "decision": promotion_decision_v1_to_dict(decision),
        "preregistration_refs": sorted(preregistration_refs),
        "evidence_refs": sorted(evidence_refs),
        "grants_execution_authority": False,
    }


def run_promotion_dry_run(
    *,
    policy: PromotionPolicyV1,
    candidate: CandidateArtifactV1,
    validation_report: ValidationReportV1,
    challenger_registration: ChallengerRegistrationV1,
    current_champion: ChampionAssignmentV1,
    shadow_evidence: ShadowEvidenceManifestV1 | None = None,
    experiment: ExperimentManifestV1 | None = None,
    preregistration_refs: tuple[str, ...] = (),
    evidence_refs: tuple[str, ...] = (),
    engine: PromotionEngine | None = None,
) -> PromotionDryRunRecord:
    """Run one promotion decision over recorded evidence and freeze the record.

    ``preregistration_refs`` / ``evidence_refs`` are identifiers the caller
    chooses to pin on the record (for example the preregistration identity
    hash from ``strategy/evaluation.py`` and the validation / shadow manifest
    ids). They are hashed into ``dry_run_id`` so the record is auditable to
    exactly the preregistration + evidence that produced it.
    """
    decision = (engine or PromotionEngine()).evaluate_promotion(
        policy=policy,
        candidate=candidate,
        validation_report=validation_report,
        challenger_registration=challenger_registration,
        current_champion=current_champion,
        shadow_evidence=shadow_evidence,
        experiment=experiment,
    )
    body = _record_body(decision, preregistration_refs, evidence_refs)
    dry_run_id = sha256_bytes(canonical_bytes(body))
    return PromotionDryRunRecord(
        dry_run_id=dry_run_id,
        decision=decision,
        preregistration_refs=tuple(sorted(preregistration_refs)),
        evidence_refs=tuple(sorted(evidence_refs)),
        grants_execution_authority=False,
    )


__all__ = [
    "DRY_RUN_DISALLOWED_TOKENS",
    "DRY_RUN_SCHEMA_VERSION",
    "PromotionDryRunRecord",
    "run_promotion_dry_run",
]
