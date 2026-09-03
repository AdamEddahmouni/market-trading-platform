"""Coherent intelligence contract lifecycle composition test."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts import (  # noqa: E402
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
    event_v1_to_dict,
    evidence_v1_to_dict,
    forecast_v1_to_dict,
    hypothesis_v1_to_dict,
    opportunity_v1_to_dict,
    outcome_v1_to_dict,
    round_trip_contract_dict,
    run_manifest_v1_to_dict,
    signal_v1_to_dict,
    snapshot_v1_to_dict,
)

DECISION_NS = 1_700_000_000_000_000_000
HORIZON_NS = 30 * 60 * 1_000_000_000
INSTRUMENT = "NVDA"


class IntelligenceLifecycleTests(unittest.TestCase):
    def test_nvda_squeeze_lifecycle_composes(self) -> None:
        quality_good = QualitySummary(state=QualityState.GOOD)
        scope = IntelligenceScope(instrument_ids=(INSTRUMENT,))

        event = EventV1(
            event_id="evt-nvda-aggressive-buy",
            schema_version="1",
            event_type="ORDER_FLOW_EVENT",
            event_time_ns=DECISION_NS,
            available_time_ns=DECISION_NS,
            payload={"description": "large increase in aggressive buy flow"},
            quality=quality_good,
            source=SourceReference(
                provider_id="MOOMOO",
                source_type="order_flow",
                source_record_id="flow-1",
            ),
            instrument_id=INSTRUMENT,
        )
        event_ref = ContractReference(kind="event", id=event.event_id)

        snapshot = SnapshotV1(
            snapshot_id="snap-nvda-1",
            schema_version="1",
            decision_time_ns=DECISION_NS,
            scope=scope,
            quality=quality_good,
            source_event_refs=(event_ref,),
        )

        signal = SignalV1(
            signal_id="sig-cvd-5m",
            schema_version="1",
            signal_type="CVD_5M",
            scope=scope,
            as_of_time_ns=DECISION_NS,
            value=71220.0,
            quality=quality_good,
            unit="shares",
            direction=Direction.LONG,
            calculation_window=TimeHorizonNs(duration_ns=5 * 60 * 1_000_000_000),
            source_snapshot_ref=ContractReference(kind="snapshot", id=snapshot.snapshot_id),
        )
        signal_ref = ContractReference(kind="signal", id=signal.signal_id)

        evidence = EvidenceV1(
            evidence_id="ev-micro-1",
            schema_version="1",
            snapshot_id=snapshot.snapshot_id,
            expert_id="microstructure",
            scope=scope,
            applicability=EvidenceApplicability.APPLICABLE,
            quality=quality_good,
            assessment={"interpretation": "buy_side_pressure"},
            support_strength=0.74,
            source_signal_refs=(signal_ref,),
        )

        hypothesis = HypothesisV1(
            hypothesis_id="hyp-squeeze-1",
            schema_version="1",
            hypothesis_type="SHORT_SQUEEZE_FORMATION",
            scope=scope,
            generated_at_ns=DECISION_NS,
            snapshot_id=snapshot.snapshot_id,
            quality=quality_good,
            supporting_evidence_ids=(evidence.evidence_id,),
            support_score=0.61,
            mechanism={"mechanism": "gamma_assisted_squeeze"},
        )
        hypothesis_ref = ContractReference(kind="hypothesis", id=hypothesis.hypothesis_id)

        forecast = ForecastV1(
            forecast_id="fc-midpoint-1",
            schema_version="1",
            scope=scope,
            decision_time_ns=DECISION_NS,
            snapshot_id=snapshot.snapshot_id,
            target=ForecastTarget(
                target_kind="midpoint_return_threshold",
                instrument_id=INSTRUMENT,
                parameters={"threshold": 0.0, "metric": "midpoint_return"},
            ),
            horizon=TimeHorizonNs(duration_ns=HORIZON_NS),
            estimate=ForecastEstimate(
                estimate_kind="classification_probability",
                probability=0.68,
            ),
            quality=quality_good,
            resolve_time_ns=DECISION_NS + HORIZON_NS,
            source_hypothesis_refs=(hypothesis_ref,),
        )
        forecast_ref = ContractReference(kind="forecast", id=forecast.forecast_id)

        opportunity = OpportunityV1(
            opportunity_id="opp-long-1",
            schema_version="1",
            scope=scope,
            created_at_ns=DECISION_NS,
            quality=quality_good,
            side=OpportunitySide.LONG,
            source_forecast_refs=(forecast_ref,),
            source_hypothesis_refs=(hypothesis_ref,),
            expected_net_edge=0.0031,
            reason_summary="candidate long opportunity, not execution-authorized",
        )

        manifest = RunManifestV1(
            run_id="run-nvda-shadow-1",
            schema_version="1",
            created_at_ns=DECISION_NS - 1_000_000,
            quality=quality_good,
            data_mode="FIXTURE_REPLAY",
            execution_mode="NONE",
            execution_authority="BLOCKED",
            strategy_version="fixture-strategy/1",
            prediction_version="shadow/fixture/1",
        )

        outcome = OutcomeV1(
            outcome_id="out-midpoint-1",
            schema_version="1",
            forecast_id=forecast.forecast_id,
            adjudicated_at_ns=DECISION_NS + HORIZON_NS,
            resolution_status=OutcomeResolutionStatus.SETTLED,
            quality=quality_good,
            realized_return=0.0042,
            realized_direction=Direction.LONG,
            start_observation={"midpoint": 120.5},
            end_observation={"midpoint": 121.0},
        )

        chain = [
            round_trip_contract_dict(event_v1_to_dict(event)),
            round_trip_contract_dict(snapshot_v1_to_dict(snapshot)),
            round_trip_contract_dict(signal_v1_to_dict(signal)),
            round_trip_contract_dict(evidence_v1_to_dict(evidence)),
            round_trip_contract_dict(hypothesis_v1_to_dict(hypothesis)),
            round_trip_contract_dict(forecast_v1_to_dict(forecast)),
            round_trip_contract_dict(opportunity_v1_to_dict(opportunity)),
            round_trip_contract_dict(run_manifest_v1_to_dict(manifest)),
            round_trip_contract_dict(outcome_v1_to_dict(outcome)),
        ]
        self.assertEqual(len(chain), 9)
        self.assertEqual(chain[5]["forecast_id"], forecast.forecast_id)
        self.assertEqual(chain[8]["forecast_id"], forecast.forecast_id)
        self.assertNotIn("quantity", chain[6])
        self.assertEqual(chain[7]["execution_authority"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
