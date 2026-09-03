"""Supervised production pilot package (BUILD 33)."""

from .accounting import PilotAccounting
from .broker_redundancy import (
    broker_auto_failover_prohibited,
    build_broker_redundancy_assessment,
)
from .checkpoints import (
    build_operational_pilot_checkpoint,
    checkpoint_due,
    missed_checkpoint_detected,
    pilot_expired_blocks_session,
)
from .gate import evaluate_pilot_active, evaluate_pilot_session_gate, pilot_policy_authorizes_order
from .identity import (
    derive_pilot_checkpoint_id,
    derive_pilot_policy_id,
    derive_pilot_qualification_report_id,
    derive_pilot_run_id,
    derive_provider_redundancy_policy_id,
    derive_provider_selection_decision_id,
)
from .maintenance import execute_planned_maintenance, maintenance_auto_resume_prohibited
from .pilot_state import (
    can_transition_pilot_state,
    pilot_ready_implies_trading_authority,
    pilot_state_allows_observation,
    transition_pilot_state,
)
from .policy import (
    build_default_pilot_policy,
    build_default_provider_redundancy_policy,
    validate_pilot_policy_constraints,
)
from .provider_divergence import assess_provider_divergence, critical_divergence_blocks_opportunity
from .provider_selection import ProviderSelectionTracker, pit_safe_candidate
from .qualification import (
    build_default_pilot_qualification_spec,
    build_sustained_pilot_qualification_report,
)
from .reviews import build_pilot_operational_review, review_disposition_authorizes_trading
from .runbooks import build_runbook_exercise_spec, run_all_runbook_exercises, run_runbook_exercise
from .runner import (
    build_pilot_run,
    run_ambiguous_broker_safety_fixture,
    run_maintenance_fixture,
    run_multi_provider_pilot_fixture,
    run_operational_incident_fixture,
)
from .telemetry import build_pilot_snapshot
from .types import (
    BUILD33_KNOWN_LIMITATIONS,
    PilotDisposition,
    PilotGovernanceState,
    ProviderDivergenceStatus,
    ProviderHealthState,
    ProviderSelectionReason,
    SUPERVISED_PILOT_IMPLEMENTATION_VERSION,
    SUPERVISED_PILOT_SCHEMA_VERSION,
)

__all__ = [
    "BUILD33_KNOWN_LIMITATIONS",
    "PilotAccounting",
    "PilotDisposition",
    "PilotGovernanceState",
    "ProviderDivergenceStatus",
    "ProviderHealthState",
    "ProviderSelectionReason",
    "ProviderSelectionTracker",
    "SUPERVISED_PILOT_IMPLEMENTATION_VERSION",
    "SUPERVISED_PILOT_SCHEMA_VERSION",
    "assess_provider_divergence",
    "broker_auto_failover_prohibited",
    "build_broker_redundancy_assessment",
    "build_default_pilot_policy",
    "build_default_pilot_qualification_spec",
    "build_default_provider_redundancy_policy",
    "build_operational_pilot_checkpoint",
    "build_pilot_operational_review",
    "build_pilot_run",
    "build_pilot_snapshot",
    "build_runbook_exercise_spec",
    "build_sustained_pilot_qualification_report",
    "can_transition_pilot_state",
    "checkpoint_due",
    "critical_divergence_blocks_opportunity",
    "derive_pilot_checkpoint_id",
    "derive_pilot_policy_id",
    "derive_pilot_qualification_report_id",
    "derive_pilot_run_id",
    "derive_provider_redundancy_policy_id",
    "derive_provider_selection_decision_id",
    "evaluate_pilot_active",
    "evaluate_pilot_session_gate",
    "execute_planned_maintenance",
    "maintenance_auto_resume_prohibited",
    "missed_checkpoint_detected",
    "pilot_expired_blocks_session",
    "pilot_policy_authorizes_order",
    "pilot_ready_implies_trading_authority",
    "pilot_state_allows_observation",
    "pit_safe_candidate",
    "review_disposition_authorizes_trading",
    "run_all_runbook_exercises",
    "run_ambiguous_broker_safety_fixture",
    "run_maintenance_fixture",
    "run_multi_provider_pilot_fixture",
    "run_operational_incident_fixture",
    "run_runbook_exercise",
    "transition_pilot_state",
    "validate_pilot_policy_constraints",
]
