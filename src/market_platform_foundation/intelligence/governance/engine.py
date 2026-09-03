"""Governance orchestration engine (BUILD 23)."""

from __future__ import annotations

from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION, ContractKind, ContractReference
from ..promotion.identity import champion_scope_identity_payload
from .activation import ActivationEngine
from .activation_queries import get_current_runtime_activation
from .drift import create_alert_from_drift
from .failsafe import FailSafeEngine
from .gate import resolve_governance_state
from .identity import derive_governance_event_id
from .rollback import RollbackEngine
from .types import (
    DriftAssessmentV1,
    FailSafeDecisionV1,
    GovernanceEventType,
    GovernanceEventV1,
    GovernanceReasonCode,
    RuntimeActivationV1,
    RuntimeGovernanceState,
    RuntimeHealthSnapshotV1,
    RuntimeReportedIdentityV1,
)


class GovernanceEngine:
    """Top-level BUILD 23 orchestrator."""

    def __init__(self) -> None:
        self.activation_engine = ActivationEngine()
        self.fail_safe_engine = FailSafeEngine()
        self.rollback_engine = RollbackEngine()

    def get_active_activation(
        self,
        activations: tuple[RuntimeActivationV1, ...],
        *,
        component: str,
        target_kind: str,
        horizon_ns: int,
        mode: str,
        as_of_ns: int,
        scenario_id: str | None = None,
    ) -> RuntimeActivationV1 | None:
        return get_current_runtime_activation(
            activations,
            component=component,
            target_kind=target_kind,
            horizon_ns=horizon_ns,
            mode=mode,
            as_of_ns=as_of_ns,
            scenario_id=scenario_id,
        )

    def resolve_state(
        self,
        *,
        activation: RuntimeActivationV1 | None,
        fail_safe: FailSafeDecisionV1 | None,
        latest_champion_assignment_id: str | None = None,
    ) -> RuntimeGovernanceState:
        return resolve_governance_state(
            activation=activation,
            fail_safe_decision=fail_safe,
            latest_champion_assignment_id=latest_champion_assignment_id,
        )

    def check_runtime_consistency(
        self,
        *,
        activation: RuntimeActivationV1,
        reported: RuntimeReportedIdentityV1 | None,
    ) -> tuple[bool, tuple[GovernanceReasonCode, ...]]:
        return self.activation_engine.check_runtime_consistency(
            activation=activation,
            reported=reported,
        )

    def build_runtime_health_snapshot(
        self,
        *,
        activation: RuntimeActivationV1,
        observed_at_ns: int,
        window,
        overall_state,
        subsystem_snapshot_ids: dict[str, str],
        reason_codes: tuple[GovernanceReasonCode, ...] = (),
    ) -> RuntimeHealthSnapshotV1:
        from .identity import derive_health_snapshot_id

        return RuntimeHealthSnapshotV1(
            snapshot_id=derive_health_snapshot_id(
                kind="runtime_aggregate",
                window=window,
                context_key=activation.activation_id,
            ),
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            activation_id=activation.activation_id,
            champion_scope=activation.champion_scope,
            observed_at_ns=observed_at_ns,
            window=window,
            overall_state=overall_state,
            reason_codes=reason_codes,
            subsystem_snapshot_ids=subsystem_snapshot_ids,
        )

    def create_governance_event(
        self,
        *,
        event_type: GovernanceEventType,
        champion_scope,
        effective_at_ns: int,
        source_refs: tuple[ContractReference, ...] = (),
        reason_codes: tuple[GovernanceReasonCode, ...] = (),
        metadata: dict[str, Any] | None = None,
    ) -> GovernanceEventV1:
        source_key = source_refs[0].id if source_refs else event_type.value
        return GovernanceEventV1(
            event_id=derive_governance_event_id(
                event_type=event_type.value,
                champion_scope=champion_scope_identity_payload(champion_scope),
                effective_at_ns=effective_at_ns,
                source_key=source_key,
            ),
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            event_type=event_type,
            champion_scope=champion_scope,
            effective_at_ns=effective_at_ns,
            source_refs=source_refs,
            reason_codes=reason_codes,
            metadata=dict(metadata or {}),
        )

    def alerts_from_drift_assessments(
        self,
        *,
        assessments: tuple[DriftAssessmentV1, ...],
        policy,
        observed_at_ns: int,
    ):
        alerts = []
        for assessment in assessments:
            alert = create_alert_from_drift(
                assessment=assessment,
                policy=policy,
                observed_at_ns=observed_at_ns,
            )
            if alert is not None:
                alerts.append(alert)
        return tuple(alerts)
