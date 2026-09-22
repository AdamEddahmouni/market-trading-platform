"""Runtime producer wiring for execution decision traces (observability only)."""

from __future__ import annotations

from typing import Any, Mapping

from ...canonical import canonical_bytes, sha256_bytes
from ...clock import monotonic_wall_ns
from ...intelligence.contracts.common import ContractReference
from ...intelligence.execution.types import RiskDecisionKind
from ...intelligence.opportunity.lifecycle import OperatorLifecycleState
from ...intelligence.opportunity.types import AssessmentAction
from ...local_state.paths import persistence_enabled
from ...local_state.startup import open_local_state, reset_local_state_for_tests
from ...paper.preview import PreviewError
from .recorder import ExecutionDecisionTraceDraft, materialize_execution_decision_trace
from .repository import ExecutionDecisionTraceRepository, InMemoryExecutionDecisionTraceRepository
from .sqlite_repository import (
    SqliteExecutionDecisionTraceRepository,
    reset_execution_decision_trace_schema_tracking_for_tests,
)
from .types import (
    EligibilityDecisionSnapshot,
    ExecutionDecisionKind,
    ExecutionDecisionTraceV1,
    PreviewDecisionSnapshot,
    RuleEvaluationOutcome,
    RuleEvaluationV1,
)

EXECUTION_DECISION_TRACE_RUNTIME_READY = "EXECUTION_DECISION_TRACE_RUNTIME_READY"

_PROCESS_REPOSITORY: InMemoryExecutionDecisionTraceRepository | None = None

_REVALIDATION_PREVIEW_CODES = frozenset(
    {
        "PREVIEW_EXPIRED",
        "PREVIEW_INTENT_MISMATCH",
        "PREVIEW_PORTFOLIO_STALE",
        "PREVIEW_POLICY_STALE",
        "PREVIEW_MARGIN_STALE",
        "PREVIEW_ACCOUNT_MISMATCH",
        "PREVIEW_MODE_MISMATCH",
        "PREVIEW_NOT_FOUND",
    }
)


def reset_execution_decision_trace_runtime_for_tests() -> None:
    global _PROCESS_REPOSITORY
    _PROCESS_REPOSITORY = None
    reset_execution_decision_trace_schema_tracking_for_tests()
    reset_local_state_for_tests()


def execution_decision_trace_repository() -> ExecutionDecisionTraceRepository:
    global _PROCESS_REPOSITORY
    if persistence_enabled():
        repo = open_local_state()
        if repo is not None:
            return SqliteExecutionDecisionTraceRepository(repo.connection)
    if _PROCESS_REPOSITORY is None:
        _PROCESS_REPOSITORY = InMemoryExecutionDecisionTraceRepository()
    return _PROCESS_REPOSITORY


def _digest_mapping(payload: Mapping[str, Any] | None) -> str | None:
    if not payload:
        return None
    return sha256_bytes(canonical_bytes(dict(payload)))


def _eligibility_from_row(row: Any) -> EligibilityDecisionSnapshot:
    lifecycle_raw = getattr(row, "lifecycle_state", None) or getattr(row, "eligibility_state", None)
    lifecycle = OperatorLifecycleState(str(lifecycle_raw)) if lifecycle_raw else None
    metadata = dict(getattr(row, "metadata", None) or {})
    reason_codes: list[str] = []
    for key in ("family_admission_reason", "supersession_reason", "duplicate_reason"):
        value = metadata.get(key)
        if value:
            reason_codes.append(str(value))
    assessment = AssessmentAction.EMIT if lifecycle == OperatorLifecycleState.ELIGIBLE else None
    if lifecycle == OperatorLifecycleState.INELIGIBLE:
        assessment = AssessmentAction.ABSTAIN
    return EligibilityDecisionSnapshot(
        assessment_action=assessment,
        lifecycle_state=lifecycle,
        reason_codes=tuple(reason_codes),
    )


def _provider_and_freshness_refs(store: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    provider_state: dict[str, Any] = {
        "data_mode": str(getattr(store, "data_mode", "") or ""),
        "execution_mode": str(getattr(store, "execution_mode", "") or ""),
        "session_state": str(getattr(store, "session_state", "") or "UNAVAILABLE"),
    }
    as_of_ns = getattr(store, "as_of_time_ns", None)
    last_source_ns = getattr(store, "last_source_time_ns", None)
    freshness: dict[str, Any] = {
        "as_of_time_ns": as_of_ns,
        "last_source_time_ns": last_source_ns,
    }
    quality = getattr(store, "runtime_capability", None)
    if quality is not None:
        provider_state["runtime_capability_ref"] = _digest_mapping(
            quality if isinstance(quality, dict) else {"value": str(quality)}
        )
    freshness["freshness_digest"] = _digest_mapping(freshness)
    return provider_state, freshness


def _config_version_refs(store: Any) -> tuple[str, ...]:
    ledger = getattr(store, "paper_ledger", None)
    if ledger is None:
        return ()
    policy = getattr(ledger, "policy", None) or {}
    revision = str(policy.get("risk_policy_identity_hash") or "").strip()
    if not revision:
        return ()
    return (f"risk-policy/{revision}",)


def _persist_draft(
    draft: ExecutionDecisionTraceDraft,
    *,
    fail_closed: bool = False,
) -> ExecutionDecisionTraceV1 | None:
    try:
        record = materialize_execution_decision_trace(draft)
        execution_decision_trace_repository().put_execution_decision_trace(record)
        return record
    except Exception:
        if fail_closed:
            raise
        return None


def record_opportunity_surface_trace(
    store: Any,
    row: Any,
    *,
    decision_time_ns: int | None = None,
) -> ExecutionDecisionTraceV1 | None:
    when = int(decision_time_ns or getattr(store, "as_of_time_ns", None) or monotonic_wall_ns())
    opportunity_id = getattr(row, "opportunity_id", None)
    provider_state, freshness = _provider_and_freshness_refs(store)
    immutable_inputs = {
        "decision_kind": ExecutionDecisionKind.SURFACE.value,
        "mode": "PAPER",
        "opportunity_id": opportunity_id,
        "summary_id": getattr(row, "summary_id", None),
    }
    draft = ExecutionDecisionTraceDraft(
        opportunity_id=opportunity_id,
        decision_time_ns=when,
        mode="PAPER",
        decision_kind=ExecutionDecisionKind.SURFACE,
        eligibility=_eligibility_from_row(row),
        provider_state=provider_state,
        market_data_freshness=freshness,
        config_version_refs=_config_version_refs(store),
        immutable_inputs=immutable_inputs,
    )
    return _persist_draft(draft)


def _trace_mode_for_store(store: Any) -> str:
    data_mode = str(getattr(store, "data_mode", "") or "")
    if data_mode == "LIVE_OBSERVATIONAL" or str(getattr(store, "mode", "")).upper() == "LIVE":
        return "LIVE_OBSERVATIONAL"
    return "PAPER"


def record_operator_lifecycle_trace(
    store: Any,
    row: Any,
    *,
    action: str,
    decision_time_ns: int,
) -> ExecutionDecisionTraceV1 | None:
    ack = OperatorLifecycleState(str(action))
    kind_by_action = {
        OperatorLifecycleState.WATCHED: ExecutionDecisionKind.WATCH,
        OperatorLifecycleState.DISMISSED: ExecutionDecisionKind.DISMISS,
    }
    kind = kind_by_action.get(ack)
    if kind is None:
        return None
    trace_mode = _trace_mode_for_store(store)
    provider_state, freshness = _provider_and_freshness_refs(store)
    opportunity_id = getattr(row, "opportunity_id", None)
    immutable_inputs = {
        "action": ack.value,
        "decision_kind": kind.value,
        "mode": trace_mode,
        "opportunity_id": opportunity_id,
        "summary_id": getattr(row, "summary_id", None),
    }
    draft = ExecutionDecisionTraceDraft(
        opportunity_id=opportunity_id,
        decision_time_ns=int(decision_time_ns),
        mode=trace_mode,
        decision_kind=kind,
        eligibility=_eligibility_from_row(row),
        provider_state=provider_state,
        market_data_freshness=freshness,
        operator_action=ack,
        config_version_refs=_config_version_refs(store),
        immutable_inputs=immutable_inputs,
    )
    return _persist_draft(draft, fail_closed=True)


def _opportunity_id_from_body(body: Mapping[str, Any]) -> str | None:
    explicit = body.get("opportunity_id")
    if explicit:
        return str(explicit)
    snapshot = body.get("decision_source_snapshot")
    if isinstance(snapshot, dict):
        candidate = snapshot.get("opportunity_id")
        if candidate:
            return str(candidate)
    return None


def record_preview_allowed_trace(
    store: Any,
    body: Mapping[str, Any],
    *,
    preview_id: str,
    decision_time_ns: int | None = None,
) -> ExecutionDecisionTraceV1 | None:
    when = int(decision_time_ns or monotonic_wall_ns())
    provider_state, freshness = _provider_and_freshness_refs(store)
    ledger = store.paper_ledger
    opportunity_id = _opportunity_id_from_body(body)
    immutable_inputs = {
        "decision_kind": ExecutionDecisionKind.PREVIEW_ALLOWED.value,
        "mode": "PAPER",
        "opportunity_id": opportunity_id,
        "preview_id": preview_id,
        "account_id": ledger.paper_account_id,
    }
    draft = ExecutionDecisionTraceDraft(
        opportunity_id=opportunity_id,
        decision_time_ns=when,
        mode="PAPER",
        decision_kind=ExecutionDecisionKind.PREVIEW_ALLOWED,
        eligibility=EligibilityDecisionSnapshot(
            lifecycle_state=OperatorLifecycleState.PAPER_PREVIEWED,
        ),
        provider_state=provider_state,
        market_data_freshness=freshness,
        preview=PreviewDecisionSnapshot(status="PREVIEW_ALLOWED", preview_id=preview_id),
        rule_evaluations=(
            RuleEvaluationV1(
                rule_id="paper.preview.binding",
                outcome=RuleEvaluationOutcome.PASS,
                reason_codes=("PREVIEW_ISSUED",),
            ),
        ),
        config_version_refs=_config_version_refs(store),
        correlation_id=str(body.get("correlation_id") or "") or None,
        immutable_inputs=immutable_inputs,
    )
    return _persist_draft(draft)


def record_preview_gate_block_trace(
    store: Any,
    body: Mapping[str, Any],
    *,
    reason: str,
    decision_time_ns: int | None = None,
) -> ExecutionDecisionTraceV1 | None:
    when = int(decision_time_ns or monotonic_wall_ns())
    code = str(reason).split(":", 1)[0].strip()
    if code in _REVALIDATION_PREVIEW_CODES:
        kind = ExecutionDecisionKind.REVALIDATION_REQUIRED
        preview = PreviewDecisionSnapshot(status="REVALIDATION_REQUIRED", reason_codes=(code,))
    elif code == "PREVIEW_REQUIRED":
        kind = ExecutionDecisionKind.PAPER_BLOCKED
        preview = None
    else:
        kind = ExecutionDecisionKind.PAPER_BLOCKED
        preview = None
    provider_state, freshness = _provider_and_freshness_refs(store)
    opportunity_id = _opportunity_id_from_body(body)
    blocker_codes = (code,)
    immutable_inputs = {
        "blocker_code": code,
        "decision_kind": kind.value,
        "mode": "PAPER",
        "opportunity_id": opportunity_id,
    }
    draft = ExecutionDecisionTraceDraft(
        opportunity_id=opportunity_id,
        decision_time_ns=when,
        mode="PAPER",
        decision_kind=kind,
        eligibility=EligibilityDecisionSnapshot(lifecycle_state=OperatorLifecycleState.ELIGIBLE),
        risk_decision_kind=RiskDecisionKind.REJECT if kind == ExecutionDecisionKind.PAPER_BLOCKED else None,
        risk_decision_ref=(
            ContractReference(kind="preview_gate", id=code) if kind == ExecutionDecisionKind.PAPER_BLOCKED else None
        ),
        provider_state=provider_state,
        market_data_freshness=freshness,
        preview=preview,
        rule_evaluations=(
            RuleEvaluationV1(
                rule_id="paper.preview.required",
                outcome=RuleEvaluationOutcome.FAIL,
                reason_codes=blocker_codes,
            ),
        ),
        blocker_codes=blocker_codes,
        config_version_refs=_config_version_refs(store),
        correlation_id=str(body.get("correlation_id") or "") or None,
        immutable_inputs=immutable_inputs,
    )
    return _persist_draft(draft)


def record_preview_gate_block_from_error(
    store: Any,
    body: Mapping[str, Any],
    exc: BaseException,
) -> ExecutionDecisionTraceV1 | None:
    if isinstance(exc, PreviewError):
        return record_preview_gate_block_trace(store, body, reason=str(exc.code))
    if isinstance(exc, ValueError):
        return record_preview_gate_block_trace(store, body, reason=str(exc))
    return None


__all__ = [
    "EXECUTION_DECISION_TRACE_RUNTIME_READY",
    "execution_decision_trace_repository",
    "record_opportunity_surface_trace",
    "record_operator_lifecycle_trace",
    "record_preview_allowed_trace",
    "record_preview_gate_block_from_error",
    "record_preview_gate_block_trace",
    "reset_execution_decision_trace_runtime_for_tests",
]
