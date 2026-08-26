"""Canonical intelligence contracts (BUILD 01).

Public import surface for typed V1 intelligence records exchanged across planes.
"""

from .adapters import (
    forecast_v1_to_shadow_prediction_fields,
    shadow_label_to_outcome_v1,
    shadow_manifest_to_run_manifest_v1,
    shadow_prediction_to_forecast_v1,
)
from .common import (
    ComponentLineage,
    INTELLIGENCE_CONTRACTS_VERSION,
    INTELLIGENCE_SCHEMA_VERSION,
    ContractKind,
    ContractReference,
    Direction,
    EvidenceApplicability,
    ForecastEstimate,
    ForecastTarget,
    IntelligenceScope,
    OpportunitySide,
    OutcomeResolutionStatus,
    QualityState,
    QualitySummary,
    SourceReference,
    TimeHorizonNs,
    round_trip_contract_dict,
)
from .detection import (
    DetectionSeverity,
    DetectionV1,
    SemanticEventType,
    detection_v1_from_dict,
    detection_v1_to_dict,
)
from .event import EventV1, event_v1_from_dict, event_v1_to_dict
from .evidence import EvidenceV1, evidence_v1_from_dict, evidence_v1_to_dict
from .forecast import ForecastV1, forecast_v1_from_dict, forecast_v1_to_dict
from .hypothesis import HypothesisV1, hypothesis_v1_from_dict, hypothesis_v1_to_dict
from .opportunity import OpportunityV1, opportunity_v1_from_dict, opportunity_v1_to_dict
from .trade_proposal import TradeProposalV1, trade_proposal_v1_from_dict, trade_proposal_v1_to_dict
from .outcome import OutcomeV1, outcome_v1_from_dict, outcome_v1_to_dict
from .prediction_ledger import (
    PredictionLedgerEntryV1,
    prediction_ledger_entry_v1_from_dict,
    prediction_ledger_entry_v1_to_dict,
)
from .run_manifest import RunManifestV1, run_manifest_v1_from_dict, run_manifest_v1_to_dict
from .routing_decision import (
    ExpertDomain,
    RouteAction,
    RoutingDecisionV1,
    RoutingPriority,
    routing_decision_v1_from_dict,
    routing_decision_v1_to_dict,
)
from .inference_job import InferenceJobV1, inference_job_v1_from_dict, inference_job_v1_to_dict
from .signal import SignalV1, signal_v1_from_dict, signal_v1_to_dict
from .snapshot import SnapshotV1, snapshot_v1_from_dict, snapshot_v1_to_dict

__all__ = [
    "INTELLIGENCE_CONTRACTS_VERSION",
    "INTELLIGENCE_SCHEMA_VERSION",
    "ContractKind",
    "ContractReference",
    "ComponentLineage",
    "DetectionSeverity",
    "DetectionV1",
    "Direction",
    "EvidenceApplicability",
    "EventV1",
    "EvidenceV1",
    "ForecastV1",
    "ForecastEstimate",
    "ForecastTarget",
    "ExpertDomain",
    "HypothesisV1",
    "InferenceJobV1",
    "IntelligenceScope",
    "OpportunitySide",
    "OpportunityV1",
    "OutcomeResolutionStatus",
    "OutcomeV1",
    "PredictionLedgerEntryV1",
    "QualityState",
    "QualitySummary",
    "RunManifestV1",
    "RouteAction",
    "RoutingDecisionV1",
    "RoutingPriority",
    "SemanticEventType",
    "SignalV1",
    "SnapshotV1",
    "SourceReference",
    "TradeProposalV1",
    "TimeHorizonNs",
    "event_v1_from_dict",
    "event_v1_to_dict",
    "detection_v1_from_dict",
    "detection_v1_to_dict",
    "evidence_v1_from_dict",
    "evidence_v1_to_dict",
    "forecast_v1_from_dict",
    "forecast_v1_to_shadow_prediction_fields",
    "forecast_v1_to_dict",
    "hypothesis_v1_from_dict",
    "hypothesis_v1_to_dict",
    "inference_job_v1_from_dict",
    "inference_job_v1_to_dict",
    "opportunity_v1_from_dict",
    "opportunity_v1_to_dict",
    "outcome_v1_from_dict",
    "outcome_v1_to_dict",
    "prediction_ledger_entry_v1_from_dict",
    "prediction_ledger_entry_v1_to_dict",
    "round_trip_contract_dict",
    "run_manifest_v1_from_dict",
    "run_manifest_v1_to_dict",
    "routing_decision_v1_from_dict",
    "routing_decision_v1_to_dict",
    "shadow_label_to_outcome_v1",
    "shadow_manifest_to_run_manifest_v1",
    "shadow_prediction_to_forecast_v1",
    "trade_proposal_v1_from_dict",
    "trade_proposal_v1_to_dict",
    "signal_v1_from_dict",
    "signal_v1_to_dict",
    "snapshot_v1_from_dict",
    "snapshot_v1_to_dict",
]
