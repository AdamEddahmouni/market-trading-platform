"""Item 7 corpus evidence validator tests (fixture/replay only)."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.production.corpus_collector import (
    export_pit_validated_corpus,
    pit_validate_candidate,
    run_corpus_collection_pipeline,
)
from market_platform_foundation.intelligence.production.corpus_evidence_validator import (
    CAPTURE_CONTEXT_ARTIFACT_KIND,
    CorpusEvidenceVerdict,
    validate_item7_corpus_evidence_bundle,
    validate_item7_corpus_evidence_paths,
)
from tests.intelligence.test_item7_corpus_collector import CUTOFF


class Item7CorpusEvidenceValidatorTests(unittest.TestCase):
    def test_fixture_pipeline_valid_with_limitations_no_coerced_missing(self) -> None:
        report, rows = run_corpus_collection_pipeline(
            repository=InMemoryIntelligenceRepository(),
            training_cutoff_ns=CUTOFF,
            include_fixture_proof=True,
        )
        status = report.to_dict()
        validation = validate_item7_corpus_evidence_bundle(status=status)
        self.assertEqual(validation.verdict, CorpusEvidenceVerdict.VALID)
        self.assertNotIn("ITEM7_COMPLETE", validation.gate_signals)
        self.assertEqual(validation.governed_candidate_rows, 0)
        self.assertEqual(validation.fixture_only_rows, 8)
        self.assertEqual(validation.pit_valid_governed_rows, 0)

    def test_missing_status_field_not_coerced_to_zero_in_output(self) -> None:
        sparse_status = {
            "artifact_kind": "item7_path_a_corpus_collection_report_v1",
            "status": "ITEM7_REAL_CORPUS_COLLECTION_SOFTWARE_READY",
            "fixture_only_rows": 0,
        }
        validation = validate_item7_corpus_evidence_bundle(status=sparse_status)
        payload = validation.to_dict()
        self.assertNotIn("governed_candidate_rows", payload)
        self.assertNotIn("pit_valid_governed_rows", payload)
        self.assertIsNone(validation.governed_candidate_rows)

    def test_fixture_row_in_pit_export_invalid(self) -> None:
        report, rows = run_corpus_collection_pipeline(
            repository=InMemoryIntelligenceRepository(),
            training_cutoff_ns=CUTOFF,
            include_fixture_proof=True,
        )
        pit_export = export_pit_validated_corpus(rows, training_cutoff_ns=CUTOFF)
        self.assertGreater(len(pit_export["rows"]), 0)
        validation = validate_item7_corpus_evidence_bundle(
            status=report.to_dict(),
            pit_validated_export=pit_export,
        )
        self.assertEqual(validation.verdict, CorpusEvidenceVerdict.INVALID)
        self.assertIn("FIXTURE_ROW_IN_PIT_EXPORT", validation.reasons)

    def test_governed_row_export_revalidates_with_pit_validate_candidate(self) -> None:
        from market_platform_foundation.intelligence.contracts import (
            Direction,
            OutcomeResolutionStatus,
            QualityState,
            QualitySummary,
        )
        from market_platform_foundation.intelligence.contracts.forecast import ForecastEstimate, ForecastV1
        from market_platform_foundation.intelligence.contracts.outcome import OutcomeV1
        from market_platform_foundation.intelligence.fusion.types import PRODUCTION_FORECAST_STAGE
        from market_platform_foundation.intelligence.production.identity import path_a_horizon
        from tests.intelligence.test_item7_corpus_collector import HORIZON as TEST_HORIZON
        from tests.intelligence.test_path_a_production_emit import PATH_A_TARGET, T, _emit_signals, _emit_snapshot

        repo = InMemoryIntelligenceRepository()
        snapshot = _emit_snapshot()
        signals = _emit_signals()
        repo.put_snapshot(snapshot)
        for signal in signals:
            repo.put_signal(signal)
        forecast = ForecastV1(
            forecast_id="fc-evidence-1",
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
        repo.put_outcome(
            OutcomeV1(
                outcome_id="out-evidence-1",
                schema_version="1",
                forecast_id=forecast.forecast_id,
                adjudicated_at_ns=snapshot.decision_time_ns + TEST_HORIZON,
                resolution_status=OutcomeResolutionStatus.SETTLED,
                quality=QualitySummary(state=QualityState.GOOD),
                realized_direction=Direction.LONG,
                metadata={"provider_id": "replay", "dataset_id": "session-1"},
            )
        )
        report, rows = run_corpus_collection_pipeline(
            repository=repo,
            training_cutoff_ns=T + TEST_HORIZON * 2,
            include_fixture_proof=False,
        )
        pit_export = export_pit_validated_corpus(rows, training_cutoff_ns=T + TEST_HORIZON * 2)
        validation = validate_item7_corpus_evidence_bundle(
            status=report.to_dict(),
            pit_validated_export=pit_export,
        )
        self.assertEqual(validation.verdict, CorpusEvidenceVerdict.VALID)
        self.assertIn("AT_LEAST_ONE_GOVERNED_PIT_VALID_ROW_PRESENT", validation.gate_signals)
        ok, _ = pit_validate_candidate(
            snapshot=snapshot,
            signals=signals,
            label=1,
            label_source="OUTCOME_V1_SETTLED",
            label_available_time_ns=snapshot.decision_time_ns + TEST_HORIZON,
            training_cutoff_ns=T + TEST_HORIZON * 2,
        )
        self.assertTrue(ok)

    def test_capture_context_hash_mismatch_invalid(self) -> None:
        report, rows = run_corpus_collection_pipeline(
            repository=InMemoryIntelligenceRepository(),
            training_cutoff_ns=CUTOFF,
            include_fixture_proof=False,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pit_path = root / "pit_validated_corpus.json"
            pit_path.write_text(
                json.dumps(export_pit_validated_corpus(rows, training_cutoff_ns=CUTOFF)),
                encoding="utf-8",
            )
            context = {
                "artifact_kind": CAPTURE_CONTEXT_ARTIFACT_KIND,
                "schema_version": "1.0.0",
                "artifact_path": str(pit_path),
                "artifact_sha256": "0" * 64,
                "evidence_class": "SOFTWARE",
            }
            validation = validate_item7_corpus_evidence_paths(
                collection_report_path=None,
                pit_validated_export_path=pit_path,
                capture_context_path=None,
                export_dir=None,
            )
            validation = validate_item7_corpus_evidence_bundle(
                status=report.to_dict(),
                pit_validated_export=json.loads(pit_path.read_text(encoding="utf-8")),
                capture_context=context,
                artifact_paths={"pit_validated_corpus.json": pit_path},
            )
            self.assertEqual(validation.verdict, CorpusEvidenceVerdict.INVALID)
            self.assertIn("CAPTURE_CONTEXT_ARTIFACT_HASH_MISMATCH", validation.reasons)

    def test_sidecar_cannot_upgrade_fixture_to_prospective(self) -> None:
        status = {
            "artifact_kind": "item7_path_a_corpus_collection_report_v1",
            "fixture_only_rows": 8,
            "pit_valid_governed_rows": 0,
        }
        context = {"evidence_class": "PROSPECTIVE", "artifact_kind": CAPTURE_CONTEXT_ARTIFACT_KIND}
        validation = validate_item7_corpus_evidence_bundle(status=status, capture_context=context)
        self.assertEqual(validation.verdict, CorpusEvidenceVerdict.INVALID)
        self.assertIn("CAPTURE_CONTEXT_EVIDENCE_CLASS_UPGRADE_FORBIDDEN", validation.reasons)

    def test_forbidden_item7_complete_label(self) -> None:
        status = {
            "artifact_kind": "item7_path_a_corpus_collection_report_v1",
            "acceptance_label": "ITEM7_COMPLETE",
        }
        validation = validate_item7_corpus_evidence_bundle(status=status)
        self.assertEqual(validation.verdict, CorpusEvidenceVerdict.INVALID)
        self.assertIn("FORBIDDEN_ACCEPTANCE_LABEL", validation.reasons)


if __name__ == "__main__":
    unittest.main()
