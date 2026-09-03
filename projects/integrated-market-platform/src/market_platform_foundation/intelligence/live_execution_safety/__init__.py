"""Live execution safety gate package (BUILD 28)."""

from .authorization import (
    build_design_only_authorization,
    build_test_enabled_authorization_fixture,
    production_authorization_absent,
)
from .broker_inventory import BROKER_INVENTORY, LIVE_SUBMIT_OPERATIONS, inventory_by_broker
from .build27_integrity import BUILD27_BRANCH, Build27IntegrityResult, verify_build27_integrity
from .certification import certify_all_brokers, certify_broker
from .dry_run import (
    DryRunExecutionAdapter,
    GLOBAL_ZERO_SUBMIT_GUARD,
    LiveSubmitForbiddenError,
    ZeroSubmitGuard,
)
from .gate import BUILD28_PRODUCTION_FORBID_LIVE_SUBMIT, evaluate_live_execution_gate
from .health import build_broker_execution_health
from .identity import derive_client_order_id, derive_payload_hash, redact_secrets
from .kill_switch import BUILD28_KILL_SWITCH_SCOPE, build_production_kill_switch, build_test_inactive_kill_switch
from .order_intent import (
    approved_quantity_from_risk,
    build_broker_order_intent,
    validate_intent_not_expired,
    validate_opportunity_not_expired,
)
from .reconciliation import blocks_new_submission, build_reconciliation_snapshot
from .report import build_broker_dry_run_report, build_live_execution_safety_report
from .runner import BUILD28_KNOWN_LIMITATIONS, LiveExecutionSafetyRunResult, run_live_execution_safety_certification
from .scenarios import REQUIRED_SCENARIOS, ScenarioResultV1, ScenarioStatus, run_all_scenarios, run_scenario
from .serialization import live_execution_safety_spec_v1_to_dict
from .spec import BUILD25_RC_BRANCH, BUILD26_BRANCH, BUILD27_BRANCH as SPEC_BUILD27_BRANCH, build_live_execution_safety_spec
from .translation import translate_broker_payload, validate_tick_lot
from .types import (
    LIVE_EXECUTION_SAFETY_IMPLEMENTATION_VERSION,
    LIVE_EXECUTION_SAFETY_SCHEMA_VERSION,
    CERTIFIED_ASSET_CLASSES,
    CERTIFIED_ORDER_TYPES,
    AccountEnvironment,
    BrokerCapabilityCertificationV1,
    BrokerCapabilityStatus,
    BrokerCertificationDisposition,
    BrokerDryRunCertificationReportV1,
    BrokerExecutionHealthV1,
    BrokerOrderIntentV1,
    BrokerOrderStateKind,
    BrokerReconciliationSnapshotV1,
    CertificationMode,
    DryRunTransportResultV1,
    KillSwitchState,
    LiveAuthorizationState,
    LiveAuditEventKind,
    LiveExecutionAuthorizationV1,
    LiveExecutionGateDecisionV1,
    LiveExecutionKillSwitchV1,
    LiveExecutionSafetyReportV1,
    LiveExecutionSafetySpecV1,
    LiveGateDecisionKind,
    LiveGateReasonCode,
    LiveSafetyDisposition,
    ReconciliationHealthState,
)

__all__ = [
    "BUILD25_RC_BRANCH",
    "BUILD26_BRANCH",
    "BUILD27_BRANCH",
    "BUILD28_KNOWN_LIMITATIONS",
    "BUILD28_KILL_SWITCH_SCOPE",
    "BUILD28_PRODUCTION_FORBID_LIVE_SUBMIT",
    "BROKER_INVENTORY",
    "Build27IntegrityResult",
    "BrokerCapabilityCertificationV1",
    "BrokerCapabilityStatus",
    "BrokerCertificationDisposition",
    "BrokerDryRunCertificationReportV1",
    "BrokerExecutionHealthV1",
    "BrokerOrderIntentV1",
    "BrokerOrderStateKind",
    "BrokerReconciliationSnapshotV1",
    "CERTIFIED_ASSET_CLASSES",
    "CERTIFIED_ORDER_TYPES",
    "AccountEnvironment",
    "CertificationMode",
    "DryRunExecutionAdapter",
    "DryRunTransportResultV1",
    "GLOBAL_ZERO_SUBMIT_GUARD",
    "KillSwitchState",
    "LIVE_EXECUTION_SAFETY_IMPLEMENTATION_VERSION",
    "LIVE_EXECUTION_SAFETY_SCHEMA_VERSION",
    "LIVE_SUBMIT_OPERATIONS",
    "LiveAuthorizationState",
    "LiveAuditEventKind",
    "LiveExecutionAuthorizationV1",
    "LiveExecutionGateDecisionV1",
    "LiveExecutionKillSwitchV1",
    "LiveExecutionSafetyReportV1",
    "LiveExecutionSafetyRunResult",
    "LiveExecutionSafetySpecV1",
    "LiveGateDecisionKind",
    "LiveGateReasonCode",
    "LiveSafetyDisposition",
    "LiveSubmitForbiddenError",
    "REQUIRED_SCENARIOS",
    "ReconciliationHealthState",
    "ScenarioResultV1",
    "ScenarioStatus",
    "SPEC_BUILD27_BRANCH",
    "ZeroSubmitGuard",
    "approved_quantity_from_risk",
    "blocks_new_submission",
    "build_broker_dry_run_report",
    "build_broker_execution_health",
    "build_broker_order_intent",
    "build_design_only_authorization",
    "build_live_execution_safety_report",
    "build_live_execution_safety_spec",
    "build_production_kill_switch",
    "build_reconciliation_snapshot",
    "build_test_enabled_authorization_fixture",
    "build_test_inactive_kill_switch",
    "certify_all_brokers",
    "certify_broker",
    "derive_client_order_id",
    "derive_payload_hash",
    "evaluate_live_execution_gate",
    "inventory_by_broker",
    "live_execution_safety_spec_v1_to_dict",
    "production_authorization_absent",
    "redact_secrets",
    "run_all_scenarios",
    "run_live_execution_safety_certification",
    "run_scenario",
    "translate_broker_payload",
    "validate_intent_not_expired",
    "validate_opportunity_not_expired",
    "validate_tick_lot",
    "verify_build27_integrity",
]
