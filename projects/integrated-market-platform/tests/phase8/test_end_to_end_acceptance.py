"""Phase 8 end-to-end acceptance tests."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.canonical import load_json_strict
from market_platform_foundation.phase8_assertions import MANDATORY_IDS, aggregate_status, build_registry, evaluate_run
from tools.phase8.run_phase8_pipeline import build_evidence, end_to_end_root_hash
from market_platform_foundation.adapters.equity_intraday_jsonl import EquityIntradayJsonlAdapter, SOURCE_OBJECT_ID
from market_platform_foundation.canonical import canonical_bytes, sha256_bytes
from market_platform_foundation.contracts.identity import sort_events
from market_platform_foundation.risk_simulation.evaluation import run_risk_simulation_evaluation

COLLECTION_ROOT = ROOT.parent
REGISTRY_PATH = ROOT / "manifests/phase8/assertion-predicates.json"
BUNDLE_PATH = ROOT / "evidence/phase8/8C94A65C60955EAB3A13A453CFBBF6DAAA7035600776C419F1AC17D036548A5F"


class Phase8EndToEndTests(unittest.TestCase):
    def test_registry_mandatory_ids(self) -> None:
        registry = build_registry(REGISTRY_PATH)
        self.assertEqual(set(registry["mandatory_ids"]), set(MANDATORY_IDS))

    def test_pipeline_aggregate_pass(self) -> None:
        output_dir = ROOT / "evidence/phase8/.pytest-run"
        if output_dir.exists():
            for child in output_dir.iterdir():
                child.unlink()
        else:
            output_dir.mkdir(parents=True)
        try:
            report = build_evidence(output_dir)
            self.assertEqual(report["aggregate_status"], "PASS")
            results_doc = load_json_strict(output_dir / "assertion-results.json")
            self.assertIsInstance(results_doc, dict)
            statuses = {row["assertion_id"]: row["status"] for row in results_doc["results"]}
            self.assertEqual(statuses["AE-001"], "PASS")
            self.assertEqual(statuses["DET-001"], "PASS")
            self.assertEqual(statuses["ROLLUP-001"], "PASS")
            self.assertEqual(statuses["SAFE-003"], "PASS")
        finally:
            if output_dir.exists():
                for child in output_dir.iterdir():
                    child.unlink()
                output_dir.rmdir()

    def test_determinism_root_hash_stable(self) -> None:
        ingest_run_id = sha256_bytes(
            canonical_bytes({"collection_root_id": "ROOT-2E7C91F4", "source_object_id": SOURCE_OBJECT_ID})
        )
        adapter = EquityIntradayJsonlAdapter(ingest_run_id=ingest_run_id)
        events = sort_events(adapter.ingest_collection(COLLECTION_ROOT).canonical_events)
        result_a = run_risk_simulation_evaluation(events)
        result_b = run_risk_simulation_evaluation(events)
        self.assertEqual(
            end_to_end_root_hash(result_a, event_count=len(events)),
            end_to_end_root_hash(result_b, event_count=len(events)),
        )

    def test_published_bundle_exists(self) -> None:
        self.assertTrue(BUNDLE_PATH.is_dir())
        aggregate = load_json_strict(BUNDLE_PATH / "assertion-aggregate.json")
        self.assertEqual(aggregate["aggregate_status"], "PASS")

    def test_publication_verifier_passes(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "tools/phase8/verify_phase8_publication.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
