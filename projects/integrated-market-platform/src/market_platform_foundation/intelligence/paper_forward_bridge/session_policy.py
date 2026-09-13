"""FTEP-V1 launch-policy enforcement at lock, submit, and evaluation boundaries."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ...shadow.session import ET, _CLOSE_MINUTES, _NS, _OPEN_MINUTES
from .activation import ActivationManifest
from .types import (
    ForwardTestDecision,
    ForwardTestEvidenceClass,
    ForwardTestMode,
    ForwardTestSession,
    ForwardTestState,
)

CALENDAR_US_EQUITY_RTH = "US_EQUITY_RTH"
CALENDAR_GLOBEX_ETH = "GLOBEX_ETH"

_OPEN_STATES = frozenset(
    {
        ForwardTestState.DRAFT,
        ForwardTestState.LOCKED,
        ForwardTestState.PAPER_SUBMITTED,
        ForwardTestState.PAPER_ACTIVE,
        ForwardTestState.OBSERVING,
        ForwardTestState.EVALUABLE,
    }
)

_INTEGRITY_CLEAN_LOCK_STATES = frozenset(
    {
        ForwardTestState.LOCKED,
        ForwardTestState.PAPER_SUBMITTED,
        ForwardTestState.PAPER_ACTIVE,
        ForwardTestState.OBSERVING,
        ForwardTestState.EVALUABLE,
        ForwardTestState.EVALUATED,
    }
)

_EMPIRICAL_EVIDENCE_CLASSES = frozenset(
    {
        ForwardTestEvidenceClass.PAPER_OBSERVED,
        ForwardTestEvidenceClass.ACTUAL_FORWARD,
    }
)


class SessionPolicyError(ValueError):
    """Launch-policy boundary failure."""


@dataclass(frozen=True, slots=True)
class PhaseGateConfig:
    phase_1_mode: str
    phase_2_mode: str
    min_integrity_clean_locks: int


@dataclass(frozen=True, slots=True)
class SampleFloorSnapshot:
    locked_decisions: int
    evaluated_decisions: int
    distinct_trading_days: int
    qualifying_sessions: int
    execution_mode_decisions: int
    per_arm_minimum: int


@dataclass(frozen=True, slots=True)
class SampleFloorDisposition:
    activation_ready: bool
    statistical_disposition_ready: bool
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "activation_ready": self.activation_ready,
            "statistical_disposition_ready": self.statistical_disposition_ready,
            "blockers": list(self.blockers),
        }


def sample_floor_disposition_to_dict(disposition: SampleFloorDisposition) -> dict[str, Any]:
    return disposition.to_dict()


def calendar_scope_from_manifest(manifest: ActivationManifest) -> str | None:
    raw = manifest.raw.get("calendar_scope")
    if raw is not None:
        return str(raw)
    return None


def phase_gate_from_manifest(manifest: ActivationManifest) -> PhaseGateConfig:
    raw = manifest.raw
    resolved = raw.get("resolved_fields")
    min_locks = 5
    if isinstance(resolved, dict):
        act02 = resolved.get("FTEP-ACT-02")
        if isinstance(act02, dict) and act02.get("resolution") is not None:
            min_locks = int(act02["resolution"])
    if raw.get("phase_transition_min_locks") is not None:
        min_locks = int(raw["phase_transition_min_locks"])
    return PhaseGateConfig(
        phase_1_mode=str(raw.get("test_mode_phase_1") or "SIGNAL_ONLY"),
        phase_2_mode=str(raw.get("test_mode_phase_2") or "EXECUTION"),
        min_integrity_clean_locks=min_locks,
    )


def sample_floors_from_manifest(manifest: ActivationManifest) -> SampleFloorSnapshot:
    floors = manifest.raw.get("sample_floors")
    if not isinstance(floors, dict):
        return SampleFloorSnapshot(30, 15, 5, 5, 10, 10)
    return SampleFloorSnapshot(
        locked_decisions=int(floors.get("locked_decisions", 30)),
        evaluated_decisions=int(floors.get("evaluated_decisions", 15)),
        distinct_trading_days=int(floors.get("distinct_trading_days", 5)),
        qualifying_sessions=int(floors.get("qualifying_sessions", 5)),
        execution_mode_decisions=int(floors.get("execution_mode_decisions", 10)),
        per_arm_minimum=int(floors.get("per_arm_minimum", 10)),
    )


def duration_floors_from_manifest(manifest: ActivationManifest) -> dict[str, int]:
    floors = manifest.raw.get("duration_floors")
    if not isinstance(floors, dict):
        return {
            "min_qualifying_sessions": 5,
            "min_session_duration_ns": 300_000_000_000,
            "min_distinct_trading_days": 5,
        }
    return {
        "min_qualifying_sessions": int(floors.get("min_qualifying_sessions", 5)),
        "min_session_duration_ns": int(floors.get("min_session_duration_ns", 300_000_000_000)),
        "min_distinct_trading_days": int(floors.get("min_distinct_trading_days", 5)),
    }


def _minutes_after_midnight_et(epoch_ns: int) -> float:
    dt = datetime.fromtimestamp(epoch_ns / _NS, tz=ET)
    return dt.hour * 60 + dt.minute + dt.second / 60.0


def is_within_us_equity_rth(epoch_ns: int) -> bool:
    dt = datetime.fromtimestamp(epoch_ns / _NS, tz=ET)
    if dt.weekday() >= 5:
        return False
    minutes = _minutes_after_midnight_et(epoch_ns)
    return _OPEN_MINUTES <= minutes < _CLOSE_MINUTES


def assert_decision_within_calendar(
    *,
    decision_time_ns: int,
    calendar_scope: str | None,
) -> None:
    if calendar_scope is None:
        return
    if calendar_scope == CALENDAR_US_EQUITY_RTH:
        if not is_within_us_equity_rth(decision_time_ns):
            raise SessionPolicyError("FORWARD_TEST_DECISION_OUTSIDE_RTH")
        return
    if calendar_scope == CALENDAR_GLOBEX_ETH:
        return
    raise SessionPolicyError("FORWARD_TEST_CALENDAR_SCOPE_UNKNOWN")


def count_integrity_clean_locks(
    *,
    session_id: str,
    decisions: tuple[ForwardTestDecision, ...] | list[ForwardTestDecision],
) -> int:
    count = 0
    for item in decisions:
        if item.session_id != session_id:
            continue
        if item.state in _INTEGRITY_CLEAN_LOCK_STATES:
            count += 1
    return count


def assert_execution_phase_gate(
    *,
    test_mode: ForwardTestMode,
    manifest: ActivationManifest,
    session: ForwardTestSession,
    decisions: tuple[ForwardTestDecision, ...] | list[ForwardTestDecision],
) -> None:
    if test_mode != ForwardTestMode.EXECUTION:
        return
    if manifest.raw.get("test_mode_phase_1") is None:
        return
    phase = phase_gate_from_manifest(manifest)
    if phase.phase_1_mode != "SIGNAL_ONLY":
        return
    clean_locks = count_integrity_clean_locks(session_id=session.session_id, decisions=decisions)
    if clean_locks < phase.min_integrity_clean_locks:
        raise SessionPolicyError("FORWARD_TEST_EXECUTION_PHASE_GATE")


def overlap_policy_from_manifest(manifest: ActivationManifest) -> str | None:
    raw = manifest.raw.get("overlap_policy")
    if raw is not None:
        return str(raw)
    return None


def assert_no_concurrent_overlap(
    *,
    manifest: ActivationManifest,
    session_id: str,
    symbol: str,
    decisions: tuple[ForwardTestDecision, ...] | list[ForwardTestDecision],
    exclude_forward_test_id: str | None = None,
) -> None:
    policy = overlap_policy_from_manifest(manifest)
    if policy != "FORBID_CONCURRENT":
        return
    normalized = str(symbol).upper()
    for item in decisions:
        if item.session_id != session_id:
            continue
        if exclude_forward_test_id and item.forward_test_id == exclude_forward_test_id:
            continue
        if str(item.symbol).upper() != normalized:
            continue
        if item.state in _OPEN_STATES:
            raise SessionPolicyError("FORWARD_TEST_OVERLAP_FORBIDDEN")


def assert_cohort_arm_consistency(
    *,
    session: ForwardTestSession,
    decision_cohort_arm: str | None,
) -> None:
    if session.cohort_arm is None or decision_cohort_arm is None:
        return
    session_value = session.cohort_arm.value
    normalized = str(decision_cohort_arm).upper().replace("-", "_")
    if session_value != normalized:
        raise SessionPolicyError("FORWARD_TEST_COHORT_ARM_MISMATCH")


def assert_evidence_class_fail_closed(
    evidence_class: ForwardTestEvidenceClass,
    *,
    boundary: str,
) -> None:
    if evidence_class in _EMPIRICAL_EVIDENCE_CLASSES:
        raise SessionPolicyError(f"FORWARD_TEST_EVIDENCE_CLASS_{boundary}_FORBIDDEN")
    if evidence_class in {
        ForwardTestEvidenceClass.REPLAY,
        ForwardTestEvidenceClass.FIXTURE,
        ForwardTestEvidenceClass.SYNTHETIC,
    }:
        raise SessionPolicyError(f"FORWARD_TEST_EVIDENCE_CLASS_{boundary}_FORBIDDEN")


def assert_evaluation_force_allowed(
    *,
    force: bool,
    session: ForwardTestSession | None,
) -> None:
    if not force:
        return
    if session is None or not session.campaign_id:
        return
    if os.environ.get("IMP_FORWARD_TEST_EVAL_FORCE", "").strip().lower() in {"1", "true", "yes"}:
        return
    raise SessionPolicyError("FORWARD_TEST_EVAL_FORCE_FORBIDDEN")


def evaluation_force_audit_metadata(
    *,
    force: bool,
    session: ForwardTestSession | None,
) -> dict[str, Any]:
    if not force:
        return {}
    return {
        "evaluation_force_bypass": True,
        "campaign_id": session.campaign_id if session else None,
        "override_env": "IMP_FORWARD_TEST_EVAL_FORCE",
    }


def assess_sample_floor_disposition(
    *,
    manifest: ActivationManifest,
    decisions: tuple[ForwardTestDecision, ...] | list[ForwardTestDecision],
    session_ids: tuple[str, ...] | list[str],
) -> SampleFloorDisposition:
    floors = sample_floors_from_manifest(manifest)
    duration = duration_floors_from_manifest(manifest)
    scoped = [item for item in decisions if item.session_id in set(session_ids)]
    locked = [item for item in scoped if item.state in _INTEGRITY_CLEAN_LOCK_STATES]
    evaluated = [item for item in scoped if item.state == ForwardTestState.EVALUATED]
    execution_mode = [
        item for item in scoped if item.test_mode == ForwardTestMode.EXECUTION
    ]
    trading_days = {
        datetime.fromtimestamp(item.decision_time_ns / _NS, tz=ET).date().isoformat()
        for item in locked
    }
    blockers: list[str] = []
    if len(locked) < floors.locked_decisions:
        blockers.append("SAMPLE_FLOOR_LOCKED_DECISIONS")
    if len(evaluated) < floors.evaluated_decisions:
        blockers.append("SAMPLE_FLOOR_EVALUATED_DECISIONS")
    if len(trading_days) < floors.distinct_trading_days:
        blockers.append("SAMPLE_FLOOR_DISTINCT_TRADING_DAYS")
    if len(execution_mode) < floors.execution_mode_decisions:
        blockers.append("SAMPLE_FLOOR_EXECUTION_MODE_DECISIONS")
    activation_blockers: list[str] = []
    if len(trading_days) < duration["min_distinct_trading_days"]:
        activation_blockers.append("DURATION_FLOOR_DISTINCT_TRADING_DAYS")
    return SampleFloorDisposition(
        activation_ready=not activation_blockers,
        statistical_disposition_ready=not blockers,
        blockers=tuple(blockers + activation_blockers),
    )


def resolve_paper_account_from_manifest(manifest: ActivationManifest) -> str | None:
    explicit = manifest.paper_account_id
    if explicit:
        return str(explicit)
    account_scope = manifest.raw.get("account_scope")
    if isinstance(account_scope, dict) and account_scope.get("account_id"):
        return str(account_scope["account_id"])
    recommended = manifest.raw.get("recommended_not_binding")
    if isinstance(recommended, dict) and recommended.get("paper_account_id"):
        return str(recommended["paper_account_id"])
    return None


def authority_strategy_binding(manifest: ActivationManifest) -> dict[str, Any] | None:
    """OD-1 Option A fields deterministic from NEWS_STRATEGY_EVALUATION authority."""
    resolved = manifest.raw.get("resolved_fields")
    if not isinstance(resolved, dict):
        return None
    baseline = resolved.get("FTEP-D004")
    ai_policy = resolved.get("FTEP-D005")
    universe = resolved.get("FTEP-D009")
    if not all(isinstance(item, dict) for item in (baseline, ai_policy, universe)):
        return None
    if baseline.get("conditional_on") != "OD-1=A":
        return None
    return {
        "strategy_binding": "A",
        "lane_id": "FUTURES_EQUITY_INDEX",
        "universe": ["ES"],
        "baseline_policy_id": str(baseline.get("resolution")),
        "ai_policy_id": str(ai_policy.get("resolution")),
        "intelligence_provider": "RECORDED_ARTIFACTS_ONLY",
        "authority_source": "docs/architecture/NEWS_STRATEGY_EVALUATION.md L35-39",
        "calendar_note": (
            "ES instrument with US_EQUITY_RTH decision window per OD-3 recommended; "
            "Globex catalyst windows excluded until owner selects OD-3=B."
        ),
    }
