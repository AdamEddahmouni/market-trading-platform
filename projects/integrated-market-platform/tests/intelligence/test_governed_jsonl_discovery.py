"""Governed JSONL discovery and UTF-8 fail-closed policy (IMP-ACTUAL-01 Phase C)."""

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
    Direction,
    OutcomeResolutionStatus,
    OutcomeV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.contracts.outcome import outcome_v1_to_dict
from market_platform_foundation.intelligence.production.corpus_collector import (
    run_corpus_collection_pipeline,
    scan_jsonl_for_settled_outcomes,
)
from market_platform_foundation.intelligence.production.corpus_collection_status import (
    run_governed_corpus_collection_status,
)
from market_platform_foundation.intelligence.production.corpus_persistence import (
    load_governed_intelligence_repository,
)
from market_platform_foundation.intelligence.production.governed_jsonl_discovery import (
    GovernedJsonlEncodingError,
    GovernedJsonlParseError,
    discover_governed_outcome_jsonl_paths,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from tests.intelligence.test_path_a_production_emit import T

CUTOFF = T - 3_600_000_000_000


class GovernedJsonlDiscoveryTests(unittest.TestCase):
    def test_unrelated_non_utf8_jsonl_under_local_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local_dir = root / ".local" / "scratch"
            local_dir.mkdir(parents=True)
            (local_dir / "telemetry.jsonl").write_bytes("{\xff\xfe".encode("latin-1"))
            discovered = discover_governed_outcome_jsonl_paths(persistence_root=root)
            self.assertEqual(discovered, ())
            summary = scan_jsonl_for_settled_outcomes(discovered)
            self.assertEqual(summary.paths_scanned, 0)

    def test_valid_governed_utf8_jsonl_loads(self) -> None:
        outcome = OutcomeV1(
            outcome_id="out-gov-1",
            schema_version="1",
            forecast_id="fc-1",
            adjudicated_at_ns=T,
            resolution_status=OutcomeResolutionStatus.SETTLED,
            quality=QualitySummary(state=QualityState.GOOD),
            realized_direction=Direction.LONG,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jsonl = root / "intelligence_records.jsonl"
            jsonl.write_text(
                json.dumps({"record_type": "outcome", "payload": outcome_v1_to_dict(outcome)}) + "\n",
                encoding="utf-8",
            )
            paths = discover_governed_outcome_jsonl_paths(persistence_root=root)
            self.assertEqual(paths, (jsonl.resolve(),))
            loaded, report = load_governed_intelligence_repository(persistence_root=root)
            self.assertEqual(report.outcomes, 1)
            self.assertEqual(len(loaded._stores.get("outcomes") or {}), 1)

    def test_malformed_governed_jsonl_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jsonl = root / "intelligence_records.jsonl"
            jsonl.write_text("{not-json\n", encoding="utf-8")
            with self.assertRaises(GovernedJsonlParseError):
                load_governed_intelligence_repository(persistence_root=root)

    def test_governed_utf8_encoding_error_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jsonl = root / "intelligence_records.jsonl"
            jsonl.write_bytes(b"\xff\xfe{\n")
            with self.assertRaises(GovernedJsonlEncodingError):
                load_governed_intelligence_repository(persistence_root=root)

    def test_discovery_does_not_recursive_sweep_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts = root / "artifacts" / "shadow-run-1"
            artifacts.mkdir(parents=True)
            (artifacts / "random.jsonl").write_text('{"artifact_kind":"noise"}\n', encoding="utf-8")
            discovered = discover_governed_outcome_jsonl_paths(persistence_root=root)
            self.assertEqual(discovered, ())

    def test_empty_governed_store_reports_zero_without_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report, rows = run_corpus_collection_pipeline(
                repository=InMemoryIntelligenceRepository(),
                persistence_root=root,
                training_cutoff_ns=CUTOFF,
                include_fixture_proof=False,
            )
            self.assertEqual(report.governed_candidate_rows, 0)
            self.assertIsNotNone(report.jsonl_scan)
            self.assertEqual(report.jsonl_scan.paths_scanned, 0)
            self.assertEqual(rows, ())
            status, _r, _repo, load_report = run_governed_corpus_collection_status(
                training_cutoff_ns=CUTOFF,
                persistence_root=root,
                include_fixture_proof=False,
                now_ns=T,
            )
            self.assertEqual(status.governed_candidate_rows, 0)
            self.assertEqual(load_report.outcomes, 0)


if __name__ == "__main__":
    unittest.main()
