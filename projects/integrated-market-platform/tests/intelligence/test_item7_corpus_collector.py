"""Item 7 Lane G corpus collection pipeline tests."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.contracts import (
    ContractKind,
    ContractReference,
    Direction,
    ForecastEstimate,
    ForecastV1,
    OutcomeResolutionStatus,
    OutcomeV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.fusion.types import (
    ForecastContributorRole,
    PRODUCTION_FORECAST_STAGE,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.production.corpus_collector import (
    LABEL_SOURCE_FIXTURE,
    LABEL_SOURCE_OUTCOME_V1,
    MANIFEST_CANDIDATE_KIND,
    STATUS_PIPELINE_READY,
    STATUS_REAL_CORPUS_SOFTWARE_READY,
    assert_not_governed_production_manifest,
    collect_candidates_from_repository,
    export_manifest_candidate,
    floor_counters,
    pit_validate_candidate,
    run_corpus_collection_pipeline,
)
from market_platform_foundation.intelligence.production.corpus_collection_status import (
    BLOCKER_RTH_OR_FUTURE_OUTCOMES_REQUIRED,
    run_governed_corpus_collection_status,
)
from market_platform_foundation.intelligence.production.corpus_join_diagnostics import (
    diagnose_corpus_join_edges,
)
from market_platform_foundation.intelligence.production.corpus_persistence import (
    load_governed_intelligence_repository,
)
from market_platform_foundation.intelligence.production.identity import path_a_horizon
from market_platform_foundation.intelligence.production.training_build import load_governed_training_manifest
from tests.intelligence.outcome_fixtures import baseline_control_forecast
from tests.intelligence.test_path_a_production_emit import (
    PATH_A_HORIZON,
    PATH_A_TARGET,
    T,
    _emit_signals,
    _emit_snapshot,
)

HORIZON = PATH_A_HORIZON.duration_ns
CUTOFF = T - (HORIZON * 40)


class Item7CorpusCollectorTests(unittest.TestCase):
    def test_fixture_proof_pipeline_ready_without_governed_rows(self) -> None:
        repo_root = ROOT
        report, rows = run_corpus_collection_pipeline(
            repository=InMemoryIntelligenceRepository(),
            repo_root=repo_root,
            training_cutoff_ns=CUTOFF,
            include_fixture_proof=True,
        )
        self.assertEqual(report.status, STATUS_PIPELINE_READY)
        self.assertEqual(report.governed_candidate_rows, 0)
        self.assertEqual(report.pit_valid_governed_rows, 0)
        self.assertEqual(report.fixture_only_rows, 8)
        self.assertTrue(any(row.label_source == LABEL_SOURCE_FIXTURE for row in rows))
        self.assertEqual(
            report.production_artifact_status,
            "PRODUCTION_FORECAST_BLOCKED_NO_GOVERNED_PATH_A_TRAINING_CORPUS",
        )

    def test_manual_label_source_rejected(self) -> None:
        snapshot = _emit_snapshot()
        signals = _emit_signals()
        ok, reasons = pit_validate_candidate(
            snapshot=snapshot,
            signals=signals,
            label=1,
            label_source="manual",
            label_available_time_ns=snapshot.decision_time_ns + HORIZON,
        )
        self.assertFalse(ok)
        self.assertIn("MANUAL_LABEL_SOURCE_REJECTED", reasons)

    def test_manifest_candidate_not_loadable_as_governed(self) -> None:
        report, rows = run_corpus_collection_pipeline(
            repository=InMemoryIntelligenceRepository(),
            training_cutoff_ns=CUTOFF,
            include_fixture_proof=True,
        )
        self.assertEqual(report.status, STATUS_PIPELINE_READY)
        manifest = export_manifest_candidate(rows, training_cutoff_ns=CUTOFF)
        self.assertEqual(manifest["artifact_kind"], MANIFEST_CANDIDATE_KIND)
        self.assertFalse(manifest["production_claim"])
        reasons = assert_not_governed_production_manifest(manifest)
        self.assertIn("MANIFEST_CANDIDATE_NOT_GOVERNED", reasons)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.json"
            path.write_text(__import__("json").dumps(manifest), encoding="utf-8")
            self.assertIsNone(load_governed_training_manifest(path))

    def test_fixture_rows_excluded_from_governed_floor_counters(self) -> None:
        _report, rows = run_corpus_collection_pipeline(
            repository=InMemoryIntelligenceRepository(),
            training_cutoff_ns=CUTOFF,
            include_fixture_proof=True,
        )
        governed_floors = floor_counters(rows, governed_only=True)
        self.assertEqual(governed_floors.total_rows, 0)
        all_floors = floor_counters(rows, governed_only=False)
        self.assertGreaterEqual(all_floors.total_rows, 8)

    def test_collect_governed_row_from_repository_join(self) -> None:
        repo = InMemoryIntelligenceRepository()
        snapshot = _emit_snapshot()
        signals = _emit_signals()
        repo.put_snapshot(snapshot)
        for signal in signals:
            repo.put_signal(signal)
        forecast = ForecastV1(
            forecast_id="fc-corpus-governed-1",
            schema_version="1",
            scope=snapshot.scope,
            decision_time_ns=snapshot.decision_time_ns,
            snapshot_id=snapshot.snapshot_id,
            target=PATH_A_TARGET,
            horizon=path_a_horizon(),
            estimate=ForecastEstimate(estimate_kind="probability", probability=0.55),
            quality=QualitySummary(state=QualityState.GOOD),
            metadata={
                "contributor_role": "PRODUCTION",
                "forecast_stage": PRODUCTION_FORECAST_STAGE,
                "calibration_status": "UNCALIBRATED",
            },
        )
        repo.put_forecast(forecast)
        outcome = OutcomeV1(
            outcome_id="out-corpus-1",
            schema_version="1",
            forecast_id=forecast.forecast_id,
            adjudicated_at_ns=snapshot.decision_time_ns + HORIZON,
            resolution_status=OutcomeResolutionStatus.SETTLED,
            quality=QualitySummary(state=QualityState.GOOD),
            realized_direction=Direction.LONG,
            realized_return=0.01,
            lineage_refs=(ContractReference(kind=ContractKind.FORECAST.value, id=forecast.forecast_id),),
            metadata={"dataset_id": "replay-session-1", "provider_id": "paper-replay"},
        )
        repo.put_outcome(outcome)
        rows = collect_candidates_from_repository(repo, training_cutoff_ns=T + HORIZON * 2)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.label_source, LABEL_SOURCE_OUTCOME_V1)
        self.assertTrue(row.pit_passed)
        self.assertEqual(row.outcome_id, "out-corpus-1")
        report, _ = run_corpus_collection_pipeline(
            repository=repo,
            training_cutoff_ns=T + HORIZON * 2,
            include_fixture_proof=False,
        )
        self.assertEqual(report.governed_candidate_rows, 1)
        self.assertEqual(report.pit_valid_governed_rows, 1)
        self.assertEqual(report.governed_training_manifest_status, "GOVERNED_ROWS_INSUFFICIENT_FOR_FLOORS")

    def test_control_and_research_forecasts_excluded_from_collection(self) -> None:
        repo = InMemoryIntelligenceRepository()
        control = baseline_control_forecast(repo)
        self.assertEqual(
            collect_candidates_from_repository(repo, training_cutoff_ns=T + HORIZON * 2),
            (),
        )
        research = ForecastV1(
            forecast_id="fc-corpus-research-1",
            schema_version="1",
            scope=control.scope,
            decision_time_ns=control.decision_time_ns,
            snapshot_id=control.snapshot_id,
            target=PATH_A_TARGET,
            horizon=path_a_horizon(),
            estimate=ForecastEstimate(estimate_kind="probability", probability=0.5),
            quality=QualitySummary(state=QualityState.GOOD),
            metadata={
                "contributor_role": ForecastContributorRole.RESEARCH.value,
                "forecast_stage": PRODUCTION_FORECAST_STAGE,
                "calibration_status": "UNCALIBRATED",
            },
        )
        repo.put_forecast(research)
        repo.put_outcome(
            OutcomeV1(
                outcome_id="out-research-1",
                schema_version="1",
                forecast_id=research.forecast_id,
                adjudicated_at_ns=control.decision_time_ns + HORIZON,
                resolution_status=OutcomeResolutionStatus.SETTLED,
                quality=QualitySummary(state=QualityState.GOOD),
                realized_direction=Direction.LONG,
            )
        )
        self.assertEqual(
            collect_candidates_from_repository(repo, training_cutoff_ns=T + HORIZON * 2),
            (),
        )

    def test_load_governed_intelligence_jsonl_and_join(self) -> None:
        repo = InMemoryIntelligenceRepository()
        snapshot = _emit_snapshot()
        signals = _emit_signals()
        forecast = ForecastV1(
            forecast_id="fc-jsonl-1",
            schema_version="1",
            scope=snapshot.scope,
            decision_time_ns=snapshot.decision_time_ns,
            snapshot_id=snapshot.snapshot_id,
            target=PATH_A_TARGET,
            horizon=path_a_horizon(),
            estimate=ForecastEstimate(estimate_kind="probability", probability=0.55),
            quality=QualitySummary(state=QualityState.GOOD),
            metadata={
                "contributor_role": "PRODUCTION",
                "forecast_stage": PRODUCTION_FORECAST_STAGE,
                "calibration_status": "UNCALIBRATED",
            },
        )
        outcome = OutcomeV1(
            outcome_id="out-jsonl-1",
            schema_version="1",
            forecast_id=forecast.forecast_id,
            adjudicated_at_ns=snapshot.decision_time_ns + HORIZON,
            resolution_status=OutcomeResolutionStatus.SETTLED,
            quality=QualitySummary(state=QualityState.GOOD),
            realized_direction=Direction.LONG,
        )
        from market_platform_foundation.intelligence.contracts.forecast import forecast_v1_to_dict
        from market_platform_foundation.intelligence.contracts.outcome import outcome_v1_to_dict
        from market_platform_foundation.intelligence.contracts.signal import signal_v1_to_dict
        from market_platform_foundation.intelligence.contracts.snapshot import snapshot_v1_to_dict

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jsonl = root / "intelligence_records.jsonl"
            lines = [
                {"record_type": "snapshot", "payload": snapshot_v1_to_dict(snapshot)},
                {"record_type": "signal", "payload": signal_v1_to_dict(signals[0])},
                {"record_type": "signal", "payload": signal_v1_to_dict(signals[1])},
                {"record_type": "forecast", "payload": forecast_v1_to_dict(forecast)},
                {"record_type": "outcome", "payload": outcome_v1_to_dict(outcome)},
            ]
            jsonl.write_text("\n".join(json.dumps(row, sort_keys=True) for row in lines) + "\n", encoding="utf-8")
            loaded, report = load_governed_intelligence_repository(persistence_root=root)
            self.assertEqual(report.forecasts, 1)
            self.assertEqual(report.outcomes, 1)
            diag = diagnose_corpus_join_edges(loaded, training_cutoff_ns=T + HORIZON * 2)
            self.assertEqual(diag.pit_valid_governed_rows, 1)
            self.assertEqual(diag.missing_edges.get("SIGNALS_MISSING_FOR_SNAPSHOT", 0), 0)

    def test_governed_status_software_ready_without_rows(self) -> None:
        report, _rows, _repo, _load = run_governed_corpus_collection_status(
            training_cutoff_ns=CUTOFF,
            repo_root=ROOT,
            persistence_root=None,
            include_fixture_proof=False,
            now_ns=T,
        )
        self.assertEqual(report.acceptance_label, STATUS_REAL_CORPUS_SOFTWARE_READY)
        self.assertIn(BLOCKER_RTH_OR_FUTURE_OUTCOMES_REQUIRED, report.blockers)
        self.assertEqual(report.governed_candidate_rows, 0)


if __name__ == "__main__":
    unittest.main()
