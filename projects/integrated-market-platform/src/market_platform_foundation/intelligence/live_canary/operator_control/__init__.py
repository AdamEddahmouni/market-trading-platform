"""Operator control plane package (BUILD 31)."""

from .commands import (
    OperatorCommandError,
    acknowledge_incident,
    activate_kill_switch,
    approve_resume,
    authorize_reviewed_session,
    confirm_reviewed_order,
    inject_incident,
    prepare_session_authorization,
    register_pending_order_review,
    revoke_session_authorization,
    submit_resolution_evidence,
)
from .context import OperatorControlContext, PendingOrderReview
from .drills import DRILL_SPECS, run_all_drills, run_drill
from .qualification import build_operator_qualification_report
from .review_report import build_audit_review_report
from .snapshot import OperatorControlError, build_operator_control_snapshot, validate_snapshot_binding
from .timeline import build_operator_audit_timeline
from .trace import build_authorization_review_model, build_lineage_trace, build_order_review_model
from .types import (
    BUILD31_KNOWN_LIMITATIONS,
    OPERATOR_CONTROL_IMPLEMENTATION_VERSION,
    OPERATOR_CONTROL_SCHEMA_VERSION,
    AuditReviewDisposition,
    DrillResult,
    ExecutionModeLabel,
    IncidentDrillReportV1,
    IncidentDrillSpecV1,
    OperatorActionReceiptV1,
    OperatorActionType,
    OperatorAuditTimelineEventV1,
    OperatorAuditTimelineV1,
    OperatorControlPlaneQualificationReportV1,
    OperatorControlSnapshotV1,
    OperatorNextAction,
    OperatorQualificationDisposition,
)

__all__ = [
    "BUILD31_KNOWN_LIMITATIONS",
    "DRILL_SPECS",
    "OPERATOR_CONTROL_IMPLEMENTATION_VERSION",
    "OPERATOR_CONTROL_SCHEMA_VERSION",
    "AuditReviewDisposition",
    "DrillResult",
    "ExecutionModeLabel",
    "IncidentDrillReportV1",
    "IncidentDrillSpecV1",
    "OperatorActionReceiptV1",
    "OperatorActionType",
    "OperatorAuditTimelineEventV1",
    "OperatorAuditTimelineV1",
    "OperatorCommandError",
    "OperatorControlContext",
    "OperatorControlError",
    "OperatorControlPlaneQualificationReportV1",
    "OperatorControlSnapshotV1",
    "OperatorNextAction",
    "OperatorQualificationDisposition",
    "PendingOrderReview",
    "acknowledge_incident",
    "activate_kill_switch",
    "approve_resume",
    "authorize_reviewed_session",
    "build_audit_review_report",
    "build_authorization_review_model",
    "build_lineage_trace",
    "build_operator_audit_timeline",
    "build_operator_control_snapshot",
    "build_operator_qualification_report",
    "build_order_review_model",
    "confirm_reviewed_order",
    "inject_incident",
    "prepare_session_authorization",
    "register_pending_order_review",
    "revoke_session_authorization",
    "run_all_drills",
    "run_drill",
    "submit_resolution_evidence",
    "validate_snapshot_binding",
]
