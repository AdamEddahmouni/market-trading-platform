"""Governed strategy research promotion registry (Phase 5 Lane J)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from .errors import PromotionError
from .research_types import (
    RESEARCH_PROMOTION_RECORD_PREFIX,
    ResearchPromotionReasonCode,
    ResearchResultSummaryV1,
    RuntimeParityComparisonRecordV1,
    RuntimeParityDisposition,
    StrategyResearchEvidenceBundleV1,
    StrategyResearchPromotionLifecycleState,
    StrategyResearchPromotionRecordV1,
    StrategyResearchPromotionTransitionV1,
)

_ALLOWED_TRANSITIONS: dict[
    StrategyResearchPromotionLifecycleState, frozenset[StrategyResearchPromotionLifecycleState]
] = {
    StrategyResearchPromotionLifecycleState.DISCOVERED: frozenset(
        {
            StrategyResearchPromotionLifecycleState.RUNNABLE,
            StrategyResearchPromotionLifecycleState.REJECTED,
        }
    ),
    StrategyResearchPromotionLifecycleState.RUNNABLE: frozenset(
        {
            StrategyResearchPromotionLifecycleState.PARITY_CHECKED,
            StrategyResearchPromotionLifecycleState.REJECTED,
        }
    ),
    StrategyResearchPromotionLifecycleState.PARITY_CHECKED: frozenset(
        {
            StrategyResearchPromotionLifecycleState.HISTORICAL_VALIDATED,
            StrategyResearchPromotionLifecycleState.REJECTED,
        }
    ),
    StrategyResearchPromotionLifecycleState.HISTORICAL_VALIDATED: frozenset(
        {
            StrategyResearchPromotionLifecycleState.OOS_VALIDATED,
            StrategyResearchPromotionLifecycleState.REJECTED,
        }
    ),
    StrategyResearchPromotionLifecycleState.OOS_VALIDATED: frozenset(
        {
            StrategyResearchPromotionLifecycleState.RESEARCH_APPROVED,
            StrategyResearchPromotionLifecycleState.REJECTED,
        }
    ),
    StrategyResearchPromotionLifecycleState.RESEARCH_APPROVED: frozenset(
        {
            StrategyResearchPromotionLifecycleState.FTEP_ELIGIBLE,
            StrategyResearchPromotionLifecycleState.REJECTED,
        }
    ),
    StrategyResearchPromotionLifecycleState.FTEP_ELIGIBLE: frozenset(
        {
            StrategyResearchPromotionLifecycleState.FTEP_TESTING,
            StrategyResearchPromotionLifecycleState.REJECTED,
        }
    ),
    StrategyResearchPromotionLifecycleState.FTEP_TESTING: frozenset(
        {
            StrategyResearchPromotionLifecycleState.PROMOTION_REVIEW,
            StrategyResearchPromotionLifecycleState.REJECTED,
        }
    ),
    StrategyResearchPromotionLifecycleState.PROMOTION_REVIEW: frozenset(
        {StrategyResearchPromotionLifecycleState.REJECTED}
    ),
    StrategyResearchPromotionLifecycleState.REJECTED: frozenset(),
}


def _missing_evidence_fields(
    evidence: StrategyResearchEvidenceBundleV1,
    *,
    require_parity: bool = False,
    parity_records: tuple[RuntimeParityComparisonRecordV1, ...] = (),
    require_historical: bool = False,
    require_oos: bool = False,
    require_full: bool = False,
) -> tuple[str, ...]:
    missing: list[str] = []
    if not evidence.strategy_id.strip():
        missing.append("strategy_id")
    if require_historical or require_oos or require_full:
        if not evidence.runtime_id.strip():
            missing.append("runtime_id")
        if not evidence.runtime_version.strip():
            missing.append("runtime_version")
        if not evidence.source_hash.strip():
            missing.append("source_hash")
        if not evidence.dataset_hashes:
            missing.append("dataset_hashes")
        if not evidence.pit_classification.strip():
            missing.append("pit_classification")
    if require_historical or require_oos or require_full:
        if evidence.in_sample_result is None:
            missing.append("in_sample_result")
    if require_oos or require_full:
        if evidence.out_of_sample_result is None:
            missing.append("out_of_sample_result")
    if require_full:
        if evidence.walk_forward_result is None:
            missing.append("walk_forward_result")
        if not evidence.transaction_cost_assumptions.strip():
            missing.append("transaction_cost_assumptions")
        if not evidence.regime_sensitivity.strip():
            missing.append("regime_sensitivity")
        if not evidence.capacity_liquidity_notes.strip():
            missing.append("capacity_liquidity_notes")
        if not evidence.multiple_testing_controls.strip():
            missing.append("multiple_testing_controls")
        if not evidence.challenger_results:
            missing.append("challenger_results")
        if not evidence.known_contradictions:
            missing.append("known_contradictions")
    if require_parity:
        if not parity_records:
            missing.append("parity_records")
        elif not any(
            record.disposition == RuntimeParityDisposition.PASS for record in parity_records
        ):
            missing.append("parity_pass")
    return tuple(missing)


def evidence_gate_for_transition(
    *,
    target_state: StrategyResearchPromotionLifecycleState,
    evidence: StrategyResearchEvidenceBundleV1,
    parity_records: tuple[RuntimeParityComparisonRecordV1, ...],
) -> tuple[str, ...]:
    if target_state == StrategyResearchPromotionLifecycleState.REJECTED:
        return ()
    if target_state == StrategyResearchPromotionLifecycleState.RUNNABLE:
        missing = _missing_evidence_fields(evidence)
        if not evidence.runtime_id.strip():
            missing = (*missing, "runtime_id")
        if not evidence.runtime_version.strip():
            missing = (*missing, "runtime_version")
        if not evidence.source_hash.strip():
            missing = (*missing, "source_hash")
        return missing
    if target_state == StrategyResearchPromotionLifecycleState.PARITY_CHECKED:
        return _missing_evidence_fields(
            evidence,
            require_parity=True,
            parity_records=parity_records,
        )
    if target_state == StrategyResearchPromotionLifecycleState.HISTORICAL_VALIDATED:
        return _missing_evidence_fields(evidence, require_historical=True)
    if target_state == StrategyResearchPromotionLifecycleState.OOS_VALIDATED:
        return _missing_evidence_fields(evidence, require_historical=True, require_oos=True)
    if target_state in {
        StrategyResearchPromotionLifecycleState.RESEARCH_APPROVED,
        StrategyResearchPromotionLifecycleState.FTEP_ELIGIBLE,
        StrategyResearchPromotionLifecycleState.FTEP_TESTING,
        StrategyResearchPromotionLifecycleState.PROMOTION_REVIEW,
    }:
        return _missing_evidence_fields(
            evidence,
            require_historical=True,
            require_oos=True,
            require_full=True,
            require_parity=True,
            parity_records=parity_records,
        )
    return ()


def derive_strategy_research_promotion_record_id(
    *,
    strategy_id: str,
    source_hash: str,
    lifecycle_state: StrategyResearchPromotionLifecycleState,
) -> str:
    payload = {
        "schema_version": INTELLIGENCE_SCHEMA_VERSION,
        "strategy_id": strategy_id,
        "source_hash": source_hash or "absent",
        "lifecycle_state": lifecycle_state.value,
    }
    digest = sha256_bytes(canonical_bytes(payload))
    return f"{RESEARCH_PROMOTION_RECORD_PREFIX}-{digest}"


def assess_auto_execution_authority(
    record: StrategyResearchPromotionRecordV1,
) -> tuple[bool, tuple[ResearchPromotionReasonCode, ...]]:
    """Numerical promotion state never activates Paper or Live by itself."""
    _ = record
    return False, (ResearchPromotionReasonCode.AUTO_PAPER_LIVE_ACTIVATION_FORBIDDEN,)


def assess_promotion_review_eligibility(
    record: StrategyResearchPromotionRecordV1,
) -> tuple[bool, tuple[ResearchPromotionReasonCode, ...]]:
    if record.lifecycle_state != StrategyResearchPromotionLifecycleState.PROMOTION_REVIEW:
        return False, (ResearchPromotionReasonCode.RESEARCH_SUBORDINATE_TO_EXECUTION_ELIGIBILITY,)
    missing = evidence_gate_for_transition(
        target_state=StrategyResearchPromotionLifecycleState.PROMOTION_REVIEW,
        evidence=record.evidence,
        parity_records=record.parity_records,
    )
    if missing:
        return False, (ResearchPromotionReasonCode.EVIDENCE_INCOMPLETE,)
    paper_ok, paper_reasons = assess_auto_execution_authority(record)
    if paper_ok:
        return False, paper_reasons
    return True, (ResearchPromotionReasonCode.PROMOTION_REVIEW_ELIGIBLE,)


class StrategyResearchPromotionRegistry:
    """In-memory registry of governed research promotion records."""

    def __init__(self) -> None:
        self._records: dict[str, StrategyResearchPromotionRecordV1] = {}
        self._transitions: list[StrategyResearchPromotionTransitionV1] = []

    def records(self) -> tuple[StrategyResearchPromotionRecordV1, ...]:
        return tuple(self._records.values())

    def get(self, promotion_record_id: str) -> StrategyResearchPromotionRecordV1 | None:
        return self._records.get(promotion_record_id)

    def register_discovered(
        self,
        *,
        strategy_id: str,
        effective_at_ns: int,
        metadata: dict[str, Any] | None = None,
    ) -> StrategyResearchPromotionRecordV1:
        evidence = StrategyResearchEvidenceBundleV1(
            strategy_id=strategy_id,
            runtime_id="",
            runtime_version="",
            source_hash="",
            dataset_hashes=(),
            pit_classification="",
            in_sample_result=None,
            out_of_sample_result=None,
            walk_forward_result=None,
            transaction_cost_assumptions="",
            regime_sensitivity="",
            capacity_liquidity_notes="",
            multiple_testing_controls="",
            challenger_results=(),
            known_contradictions=(),
        )
        state = StrategyResearchPromotionLifecycleState.DISCOVERED
        record_id = derive_strategy_research_promotion_record_id(
            strategy_id=strategy_id,
            source_hash="",
            lifecycle_state=state,
        )
        record = StrategyResearchPromotionRecordV1(
            promotion_record_id=record_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            strategy_id=strategy_id,
            lifecycle_state=state,
            evidence=evidence,
            updated_at_ns=effective_at_ns,
            metadata=dict(metadata or {}),
        )
        self._records[record_id] = record
        self._append_transition(
            record_id=record_id,
            from_state=None,
            to_state=state,
            effective_at_ns=effective_at_ns,
        )
        return record

    def upsert_evidence(
        self,
        promotion_record_id: str,
        evidence: StrategyResearchEvidenceBundleV1,
        *,
        parity_records: tuple[RuntimeParityComparisonRecordV1, ...] | None = None,
    ) -> StrategyResearchPromotionRecordV1:
        current = self._require_record(promotion_record_id)
        updated = replace(
            current,
            evidence=evidence,
            parity_records=parity_records if parity_records is not None else current.parity_records,
        )
        self._records[promotion_record_id] = updated
        return updated

    def attach_parity_record(
        self,
        promotion_record_id: str,
        parity_record: RuntimeParityComparisonRecordV1,
    ) -> StrategyResearchPromotionRecordV1:
        current = self._require_record(promotion_record_id)
        updated = replace(
            current,
            parity_records=(*current.parity_records, parity_record),
        )
        self._records[promotion_record_id] = updated
        return updated

    def transition(
        self,
        promotion_record_id: str,
        *,
        to_state: StrategyResearchPromotionLifecycleState,
        effective_at_ns: int,
        reject_reason: str | None = None,
    ) -> StrategyResearchPromotionRecordV1:
        current = self._require_record(promotion_record_id)
        allowed = _ALLOWED_TRANSITIONS.get(current.lifecycle_state, frozenset())
        if to_state not in allowed:
            raise PromotionError(
                ResearchPromotionReasonCode.INVALID_LIFECYCLE_TRANSITION.value,
                details={
                    "from": current.lifecycle_state.value,
                    "to": to_state.value,
                },
            )
        missing = evidence_gate_for_transition(
            target_state=to_state,
            evidence=current.evidence,
            parity_records=current.parity_records,
        )
        if missing:
            raise PromotionError(
                ResearchPromotionReasonCode.EVIDENCE_INCOMPLETE.value,
                details={"missing_fields": list(missing)},
            )
        review_eligible = False
        reason_codes: tuple[ResearchPromotionReasonCode, ...] = ()
        if to_state == StrategyResearchPromotionLifecycleState.PROMOTION_REVIEW:
            review_eligible, reason_codes = assess_promotion_review_eligibility(
                replace(current, lifecycle_state=to_state)
            )
            if not review_eligible:
                raise PromotionError(
                    ResearchPromotionReasonCode.EVIDENCE_INCOMPLETE.value,
                    details={"reason_codes": [code.value for code in reason_codes]},
                )
        elif to_state == StrategyResearchPromotionLifecycleState.REJECTED:
            reason_codes = (ResearchPromotionReasonCode.REJECTED,)
        metadata = dict(current.metadata)
        if reject_reason and to_state == StrategyResearchPromotionLifecycleState.REJECTED:
            metadata["reject_reason"] = reject_reason
        updated = StrategyResearchPromotionRecordV1(
            promotion_record_id=current.promotion_record_id,
            schema_version=current.schema_version,
            strategy_id=current.strategy_id,
            lifecycle_state=to_state,
            evidence=current.evidence,
            parity_records=current.parity_records,
            reason_codes=reason_codes,
            review_eligible=review_eligible,
            grants_execution_authority=False,
            updated_at_ns=effective_at_ns,
            metadata=metadata,
        )
        self._records[promotion_record_id] = updated
        self._append_transition(
            record_id=promotion_record_id,
            from_state=current.lifecycle_state,
            to_state=to_state,
            effective_at_ns=effective_at_ns,
            reason_codes=reason_codes,
        )
        return updated

    def transition_history(
        self, promotion_record_id: str
    ) -> tuple[StrategyResearchPromotionTransitionV1, ...]:
        return tuple(
            event
            for event in self._transitions
            if event.promotion_record_id == promotion_record_id
        )

    def _require_record(self, promotion_record_id: str) -> StrategyResearchPromotionRecordV1:
        record = self._records.get(promotion_record_id)
        if record is None:
            raise PromotionError(
                "PROMOTION_RECORD_NOT_FOUND",
                details={"promotion_record_id": promotion_record_id},
            )
        return record

    def _append_transition(
        self,
        *,
        record_id: str,
        from_state: StrategyResearchPromotionLifecycleState | None,
        to_state: StrategyResearchPromotionLifecycleState,
        effective_at_ns: int,
        reason_codes: tuple[ResearchPromotionReasonCode, ...] = (),
    ) -> None:
        payload = {
            "promotion_record_id": record_id,
            "from_state": from_state.value if from_state else None,
            "to_state": to_state.value,
            "effective_at_ns": effective_at_ns,
            "reason_codes": [code.value for code in reason_codes],
        }
        event_id = f"SRP-EVT-{sha256_bytes(canonical_bytes(payload))}"
        self._transitions.append(
            StrategyResearchPromotionTransitionV1(
                event_id=event_id,
                schema_version=INTELLIGENCE_SCHEMA_VERSION,
                promotion_record_id=record_id,
                from_state=from_state,
                to_state=to_state,
                effective_at_ns=effective_at_ns,
                reason_codes=reason_codes,
            )
        )


def minimal_research_result(
    *,
    summary_id: str,
    metric_name: str,
    metric_value: float,
    sample_count: int,
    window_label: str,
) -> ResearchResultSummaryV1:
    return ResearchResultSummaryV1(
        summary_id=summary_id,
        metric_name=metric_name,
        metric_value=metric_value,
        sample_count=sample_count,
        window_label=window_label,
    )


__all__ = [
    "StrategyResearchPromotionRegistry",
    "assess_auto_execution_authority",
    "assess_promotion_review_eligibility",
    "derive_strategy_research_promotion_record_id",
    "evidence_gate_for_transition",
    "minimal_research_result",
]
