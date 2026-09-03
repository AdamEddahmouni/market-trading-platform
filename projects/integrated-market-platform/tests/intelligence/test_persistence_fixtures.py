"""Shared persistence test fixtures (BUILD 04.5)."""

from __future__ import annotations

from market_platform_foundation.intelligence.contracts import (
    ContractReference,
    Direction,
    EvidenceApplicability,
    EventV1,
    EvidenceV1,
    ForecastEstimate,
    ForecastTarget,
    ForecastV1,
    HypothesisV1,
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    OutcomeResolutionStatus,
    OutcomeV1,
    QualityState,
    QualitySummary,
    RunManifestV1,
    SignalV1,
    SnapshotV1,
    SourceReference,
    TimeHorizonNs,
)
from market_platform_foundation.intelligence.persistence import IntelligenceRepository

DECISION_NS = 1_700_000_000_000_000_000
HORIZON_NS = 30 * 60 * 1_000_000_000
INSTRUMENT = "NVDA"
SOURCE = SourceReference(provider_id="TEST", source_type="unit", source_record_id="r1")
QUALITY = QualitySummary(state=QualityState.GOOD)
SCOPE = IntelligenceScope(instrument_ids=(INSTRUMENT,))


def sample_event(
    event_id: str = "evt-1",
    *,
    event_time_ns: int = DECISION_NS,
    available_time_ns: int = DECISION_NS,
    event_type: str = "TRADE",
    payload: dict | None = None,
) -> EventV1:
    return EventV1(
        event_id=event_id,
        schema_version="1",
        event_type=event_type,
        event_time_ns=event_time_ns,
        available_time_ns=available_time_ns,
        payload=payload or {"px": 100},
        quality=QUALITY,
        source=SOURCE,
        instrument_id=INSTRUMENT,
        received_time_ns=available_time_ns,
    )


def sample_snapshot(snapshot_id: str = "snap-1") -> SnapshotV1:
    return SnapshotV1(
        snapshot_id=snapshot_id,
        schema_version="1",
        decision_time_ns=DECISION_NS,
        scope=SCOPE,
        quality=QUALITY,
        source_event_refs=(ContractReference(kind="event", id="evt-1"),),
    )


def sample_signal(signal_id: str = "sig-1", *, as_of_time_ns: int = DECISION_NS) -> SignalV1:
    return SignalV1(
        signal_id=signal_id,
        schema_version="1",
        signal_type="CVD_5M",
        scope=SCOPE,
        as_of_time_ns=as_of_time_ns,
        value=100.0,
        quality=QUALITY,
    )


def sample_evidence(evidence_id: str = "ev-1", snapshot_id: str = "snap-1") -> EvidenceV1:
    return EvidenceV1(
        evidence_id=evidence_id,
        schema_version="1",
        snapshot_id=snapshot_id,
        expert_id="microstructure",
        scope=SCOPE,
        applicability=EvidenceApplicability.APPLICABLE,
        quality=QUALITY,
        assessment={"pressure": "buy"},
    )


def sample_hypothesis(hypothesis_id: str = "hyp-1") -> HypothesisV1:
    return HypothesisV1(
        hypothesis_id=hypothesis_id,
        schema_version="1",
        hypothesis_type="SHORT_SQUEEZE_FORMATION",
        scope=SCOPE,
        generated_at_ns=DECISION_NS,
        snapshot_id="snap-1",
        quality=QUALITY,
    )


def sample_forecast(
    forecast_id: str = "fc-1",
    *,
    decision_time_ns: int = DECISION_NS,
    probability: float = 0.68,
) -> ForecastV1:
    return ForecastV1(
        forecast_id=forecast_id,
        schema_version="1",
        scope=SCOPE,
        decision_time_ns=decision_time_ns,
        snapshot_id="snap-1",
        target=ForecastTarget(
            target_kind="midpoint_return_threshold",
            instrument_id=INSTRUMENT,
            parameters={"threshold": 0.0},
        ),
        horizon=TimeHorizonNs(duration_ns=HORIZON_NS),
        estimate=ForecastEstimate(
            estimate_kind="classification_probability",
            probability=probability,
        ),
        quality=QUALITY,
    )


def sample_opportunity(opportunity_id: str = "opp-1") -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version="1",
        scope=SCOPE,
        created_at_ns=DECISION_NS,
        quality=QUALITY,
        side=OpportunitySide.LONG,
        valid_until_ns=DECISION_NS + HORIZON_NS,
    )


def sample_outcome(outcome_id: str = "out-1", forecast_id: str = "fc-1") -> OutcomeV1:
    return OutcomeV1(
        outcome_id=outcome_id,
        schema_version="1",
        forecast_id=forecast_id,
        adjudicated_at_ns=DECISION_NS + HORIZON_NS,
        resolution_status=OutcomeResolutionStatus.SETTLED,
        quality=QUALITY,
        realized_return=0.01,
        realized_direction=Direction.LONG,
    )


def sample_run_manifest(run_id: str = "run-1") -> RunManifestV1:
    return RunManifestV1(
        run_id=run_id,
        schema_version="1",
        created_at_ns=DECISION_NS,
        quality=QUALITY,
        data_mode="FIXTURE_REPLAY",
        execution_mode="NONE",
        execution_authority="BLOCKED",
    )


def populate_all_record_types(repo: IntelligenceRepository) -> None:
    repo.put_event(sample_event())
    repo.put_snapshot(sample_snapshot())
    repo.put_signal(sample_signal())
    repo.put_evidence(sample_evidence())
    repo.put_hypothesis(sample_hypothesis())
    repo.put_forecast(sample_forecast())
    repo.put_opportunity(sample_opportunity())
    repo.put_outcome(sample_outcome())
    repo.put_run_manifest(sample_run_manifest())
