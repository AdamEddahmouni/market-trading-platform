"""Forward-test repository protocol and factory."""

from __future__ import annotations

import json
from typing import Any, Protocol, runtime_checkable

from ...local_state.connection import LocalStateConnection
from ...local_state.paths import persistence_enabled
from .campaign_binding import CampaignBinding
from .types import (
    EvaluationState,
    ExecutionOutcomeMetrics,
    ForwardTestCohortArm,
    ForwardTestDecision,
    ForwardTestEvidenceClass,
    ForwardTestMode,
    ForwardTestObservation,
    ForwardTestRunKind,
    ForwardTestSession,
    ForwardTestSessionStatus,
    ForwardTestState,
    SignalOutcomeMetrics,
)


class ForwardTestRepositoryError(ValueError):
    """Forward-test persistence boundary failure."""


@runtime_checkable
class ForwardTestRepository(Protocol):
    def put_session(self, session: ForwardTestSession) -> None: ...

    def get_session(self, session_id: str) -> ForwardTestSession | None: ...

    def list_sessions(self, *, account_id: str) -> list[ForwardTestSession]: ...

    def put_decision(self, decision: ForwardTestDecision) -> None: ...

    def get_decision(self, forward_test_id: str) -> ForwardTestDecision | None: ...

    def list_decisions(
        self,
        *,
        account_id: str,
        session_id: str | None = None,
    ) -> list[ForwardTestDecision]: ...

    def claim_paper_submission(self, forward_test_id: str) -> bool: ...

    def claim_evaluation(self, forward_test_id: str) -> bool: ...

    def release_evaluation_claim(self, forward_test_id: str) -> None: ...

    def claim_active_binding(self, binding: CampaignBinding) -> None: ...

    def get_active_binding(self, *, account_id: str) -> CampaignBinding | None: ...

    def release_binding(
        self,
        *,
        account_id: str,
        campaign_id: str | None = None,
        released_at_ns: int | None = None,
    ) -> CampaignBinding | None: ...

    def record_first_lock_at_ns(
        self,
        *,
        account_id: str,
        campaign_id: str,
        first_lock_at_ns: int,
    ) -> None: ...


def create_forward_test_repository(
    *,
    connection: LocalStateConnection | None = None,
) -> ForwardTestRepository:
    if persistence_enabled() and connection is not None:
        from .sqlite_repository import SqliteForwardTestRepository

        return SqliteForwardTestRepository(connection)
    from .store import ForwardTestStore

    return ForwardTestStore()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    loaded = json.loads(raw)
    return loaded if loaded is not None else default


def session_to_row(session: ForwardTestSession) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "account_id": session.account_id,
        "mode": session.mode,
        "strategy_id": session.strategy_id,
        "strategy_version": session.strategy_version,
        "universe_json": _json_dumps(list(session.universe)),
        "evaluation_horizon_ns": session.evaluation_horizon_ns,
        "created_at_ns": session.created_at_ns,
        "status": session.status.value,
        "config_json": _json_dumps(session.config),
        "campaign_id": session.campaign_id,
        "protocol_id": session.protocol_id,
        "activation_version": session.activation_version,
        "manifest_fingerprint": session.manifest_fingerprint,
        "cohort_arm": session.cohort_arm.value if session.cohort_arm else None,
        "config_frozen": 1 if session.config_frozen else 0,
    }


def session_from_row(row: dict[str, Any]) -> ForwardTestSession:
    universe = _json_loads(row.get("universe_json"), [])
    config = _json_loads(row.get("config_json"), {})
    cohort_raw = row.get("cohort_arm")
    cohort_arm = ForwardTestCohortArm(str(cohort_raw)) if cohort_raw else None
    config_frozen = bool(int(row.get("config_frozen") or 0))
    return ForwardTestSession(
        session_id=str(row["session_id"]),
        account_id=str(row["account_id"]),
        mode=str(row["mode"]),
        strategy_id=str(row["strategy_id"]),
        strategy_version=str(row["strategy_version"]),
        universe=tuple(str(item) for item in universe),
        evaluation_horizon_ns=int(row["evaluation_horizon_ns"]),
        created_at_ns=int(row["created_at_ns"]),
        status=ForwardTestSessionStatus(str(row["status"])),
        campaign_id=row.get("campaign_id"),
        protocol_id=row.get("protocol_id"),
        activation_version=row.get("activation_version"),
        manifest_fingerprint=row.get("manifest_fingerprint"),
        cohort_arm=cohort_arm,
        config_frozen=config_frozen,
        config=dict(config) if isinstance(config, dict) else {},
    )


def observation_from_row(row: dict[str, Any]) -> ForwardTestObservation:
    payload = _json_loads(row.get("payload_json"), {})
    return ForwardTestObservation(
        observation_id=str(row["observation_id"]),
        observed_at_ns=int(row["observed_at_ns"]),
        source_time_ns=int(row["source_time_ns"]),
        payload=dict(payload) if isinstance(payload, dict) else {},
    )


def _signal_outcome_from_json(raw: str | None) -> SignalOutcomeMetrics | None:
    if not raw:
        return None
    data = json.loads(raw)
    if not isinstance(data, dict):
        return None
    warnings = data.get("warnings") or ()
    return SignalOutcomeMetrics(
        entry_reference_price=data.get("entry_reference_price"),
        exit_reference_price=data.get("exit_reference_price"),
        absolute_return=data.get("absolute_return"),
        percentage_return=data.get("percentage_return"),
        directional_correct=data.get("directional_correct"),
        quality=str(data.get("quality") or "UNKNOWN"),
        warnings=tuple(str(item) for item in warnings),
    )


def _execution_outcome_from_json(raw: str | None) -> ExecutionOutcomeMetrics | None:
    if not raw:
        return None
    data = json.loads(raw)
    if not isinstance(data, dict):
        return None
    warnings = data.get("warnings") or ()
    return ExecutionOutcomeMetrics(
        paper_order_id=data.get("paper_order_id"),
        paper_intent_id=data.get("paper_intent_id"),
        realized_pnl_minor=data.get("realized_pnl_minor"),
        unrealized_pnl_minor=data.get("unrealized_pnl_minor"),
        fill_count=int(data.get("fill_count") or 0),
        quality=str(data.get("quality") or "UNKNOWN"),
        warnings=tuple(str(item) for item in warnings),
    )


def decision_from_row(
    row: dict[str, Any],
    observations: tuple[ForwardTestObservation, ...] = (),
) -> ForwardTestDecision:
    decision_payload = _json_loads(row.get("decision_payload_json"), {})
    provenance = _json_loads(row.get("provenance_snapshot_json"), {})
    quantity = row.get("quantity")
    confidence = row.get("confidence")
    locked_at = row.get("locked_at_ns")
    submitted_at = row.get("submitted_at_ns")
    cohort_raw = row.get("cohort_arm")
    cohort_arm = ForwardTestCohortArm(str(cohort_raw)) if cohort_raw else None
    evidence_raw = row.get("evidence_class") or ForwardTestEvidenceClass.UNCLASSIFIED.value
    return ForwardTestDecision(
        forward_test_id=str(row["forward_test_id"]),
        session_id=row.get("session_id"),
        account_id=str(row["account_id"]),
        mode=str(row["mode"]),
        run_kind=ForwardTestRunKind(str(row["run_kind"])),
        test_mode=ForwardTestMode(str(row["test_mode"])),
        symbol=str(row["symbol"]),
        decision_time_ns=int(row["decision_time_ns"]),
        source_time_ns=int(row["source_time_ns"]),
        state=ForwardTestState(str(row["state"])),
        direction=str(row["direction"]),
        quantity=int(quantity) if quantity is not None else None,
        confidence=float(confidence) if confidence is not None else None,
        strategy_id=str(row["strategy_id"]),
        strategy_version=str(row["strategy_version"]),
        research_artifact_ref=row.get("research_artifact_ref"),
        evaluation_horizon_ns=int(row["evaluation_horizon_ns"]),
        decision_payload=dict(decision_payload) if isinstance(decision_payload, dict) else {},
        provenance_snapshot=dict(provenance) if isinstance(provenance, dict) else {},
        paper_order_id=row.get("paper_order_id"),
        paper_intent_id=row.get("paper_intent_id"),
        locked_at_ns=int(locked_at) if locked_at is not None else None,
        submitted_at_ns=int(submitted_at) if submitted_at is not None else None,
        observations=observations,
        signal_outcome=_signal_outcome_from_json(row.get("signal_outcome_json")),
        execution_outcome=_execution_outcome_from_json(row.get("execution_outcome_json")),
        evaluation_state=EvaluationState(str(row["evaluation_state"])),
        failure_reason=row.get("failure_reason"),
        evidence_class=ForwardTestEvidenceClass(str(evidence_raw)),
        cohort_arm=cohort_arm,
    )


def decision_to_row(decision: ForwardTestDecision) -> dict[str, Any]:
    return {
        "forward_test_id": decision.forward_test_id,
        "session_id": decision.session_id,
        "account_id": decision.account_id,
        "mode": decision.mode,
        "run_kind": decision.run_kind.value,
        "test_mode": decision.test_mode.value,
        "symbol": decision.symbol,
        "decision_time_ns": decision.decision_time_ns,
        "source_time_ns": decision.source_time_ns,
        "state": decision.state.value,
        "direction": decision.direction,
        "quantity": decision.quantity,
        "confidence": decision.confidence,
        "strategy_id": decision.strategy_id,
        "strategy_version": decision.strategy_version,
        "research_artifact_ref": decision.research_artifact_ref,
        "evaluation_horizon_ns": decision.evaluation_horizon_ns,
        "decision_payload_json": _json_dumps(decision.decision_payload),
        "provenance_snapshot_json": _json_dumps(decision.provenance_snapshot),
        "paper_order_id": decision.paper_order_id,
        "paper_intent_id": decision.paper_intent_id,
        "locked_at_ns": decision.locked_at_ns,
        "submitted_at_ns": decision.submitted_at_ns,
        "signal_outcome_json": _json_dumps(decision.signal_outcome.to_dict())
        if decision.signal_outcome
        else None,
        "execution_outcome_json": _json_dumps(decision.execution_outcome.to_dict())
        if decision.execution_outcome
        else None,
        "evaluation_state": decision.evaluation_state.value,
        "failure_reason": decision.failure_reason,
        "evidence_class": decision.evidence_class.value,
        "cohort_arm": decision.cohort_arm.value if decision.cohort_arm else None,
    }


def _session_config_without_disposition(config: dict) -> dict:
    filtered = dict(config)
    filtered.pop("sample_floor_disposition", None)
    return filtered


def assert_session_config_immutable(
    existing: ForwardTestSession,
    proposed: ForwardTestSession,
) -> None:
    if not existing.config_frozen:
        return
    if _session_config_without_disposition(existing.config) != _session_config_without_disposition(
        proposed.config
    ):
        raise ForwardTestRepositoryError("FORWARD_TEST_SESSION_CONFIG_FROZEN")


def assert_observations_append_only(
    existing: ForwardTestDecision,
    proposed: ForwardTestDecision,
) -> None:
    if len(proposed.observations) < len(existing.observations):
        raise ForwardTestRepositoryError("FORWARD_TEST_OBSERVATIONS_APPEND_ONLY")
    existing_ids = [item.observation_id for item in existing.observations]
    proposed_ids = [item.observation_id for item in proposed.observations]
    if proposed_ids[: len(existing_ids)] != existing_ids:
        raise ForwardTestRepositoryError("FORWARD_TEST_OBSERVATIONS_APPEND_ONLY")


def assert_locked_decision_immutable(
    existing: ForwardTestDecision,
    proposed: ForwardTestDecision,
) -> None:
    if existing.locked_at_ns is None:
        return
    immutable_checks = (
        ("session_id", existing.session_id, proposed.session_id),
        ("account_id", existing.account_id, proposed.account_id),
        ("mode", existing.mode, proposed.mode),
        ("run_kind", existing.run_kind, proposed.run_kind),
        ("test_mode", existing.test_mode, proposed.test_mode),
        ("symbol", existing.symbol, proposed.symbol),
        ("decision_time_ns", existing.decision_time_ns, proposed.decision_time_ns),
        ("source_time_ns", existing.source_time_ns, proposed.source_time_ns),
        ("direction", existing.direction, proposed.direction),
        ("quantity", existing.quantity, proposed.quantity),
        ("confidence", existing.confidence, proposed.confidence),
        ("strategy_id", existing.strategy_id, proposed.strategy_id),
        ("strategy_version", existing.strategy_version, proposed.strategy_version),
        ("research_artifact_ref", existing.research_artifact_ref, proposed.research_artifact_ref),
        ("evaluation_horizon_ns", existing.evaluation_horizon_ns, proposed.evaluation_horizon_ns),
        ("decision_payload", existing.decision_payload, proposed.decision_payload),
        ("provenance_snapshot", existing.provenance_snapshot, proposed.provenance_snapshot),
        ("locked_at_ns", existing.locked_at_ns, proposed.locked_at_ns),
        ("evidence_class", existing.evidence_class, proposed.evidence_class),
        ("cohort_arm", existing.cohort_arm, proposed.cohort_arm),
    )
    for field_name, before, after in immutable_checks:
        if before != after:
            raise ForwardTestRepositoryError(f"FORWARD_TEST_LOCKED_IMMUTABLE:{field_name}")
