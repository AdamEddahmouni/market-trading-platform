import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools" / "research"))

from market_platform_foundation.shadow.experiment import ShadowExperimentStore
from reconcile_shadow_provenance import reconcile_run
import run_shadow_run as cli


_BUCKET_SECONDS = 60
_NS = 1_000_000_000


class ProvenanceReconcileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store_root = self.root / "shadow"
        self.capture_id = "CAP-TEST"
        (self.store_root / "captures").mkdir(parents=True)
        self.exp = ShadowExperimentStore(self.store_root / "experiment.sqlite3")
        self.run_id = "SHRUN-TEST"
        self.exp.ensure_run(
            self.run_id,
            json.dumps({"config": {"capture_id": self.capture_id}}),
            "HASH",
            1,
        )

    def tearDown(self):
        self.exp.close()
        self.tmp.cleanup()

    def _write_capture(self, *, event_time_ns: int, received_time_ns: int) -> None:
        path = self.store_root / "captures" / f"{self.capture_id}.jsonl"
        payload = {
            "clocks": {
                "event_time_ns": event_time_ns,
                "received_time_ns": received_time_ns,
            }
        }
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    def test_reconcile_legacy_decision_from_sealed_capture_bucket(self):
        bucket = 42
        event_time_ns = bucket * _BUCKET_SECONDS * _NS + 5
        received_time_ns = event_time_ns + 1000
        self._write_capture(event_time_ns=event_time_ns, received_time_ns=received_time_ns)
        self.exp.record_decision(
            self.run_id,
            "BIYA",
            bucket,
            "ABSTAINED_MODEL",
            detail={"reason": "STALE_INPUT"},
            created_at_ns=1,
        )

        report = reconcile_run(run_id=self.run_id, store_root=self.store_root)

        self.assertEqual(report["summary"]["reconciled"], 1)
        self.assertEqual(report["summary"]["unreconciled"], 0)
        row = report["reconciled_decisions"][0]
        self.assertEqual(row["decision_time_ns"], event_time_ns)
        self.assertEqual(row["available_time_ns"], received_time_ns)
        self.assertEqual(row["method"], "sealed_capture_bucket_replay_v1")

    def test_reconcile_skips_decisions_with_inline_provenance(self):
        bucket = 7
        event_time_ns = bucket * _BUCKET_SECONDS * _NS
        self._write_capture(event_time_ns=event_time_ns, received_time_ns=event_time_ns + 1)
        self.exp.record_decision(
            self.run_id,
            "BIYA",
            bucket,
            "ABSTAINED_MODEL",
            detail={
                "capture_id": self.capture_id,
                "decision_time_ns": event_time_ns,
                "available_time_ns": event_time_ns + 1,
            },
            created_at_ns=1,
        )

        report = reconcile_run(run_id=self.run_id, store_root=self.store_root)

        self.assertEqual(report["summary"]["reconciled"], 0)
        self.assertEqual(report["summary"]["unreconciled"], 0)


class ReconciledDecisionLoaderTests(unittest.TestCase):
    def test_load_reconciled_decision_ids_filters_by_run_and_shape(self):
        artifact = cli.repo_root() / "artifacts" / "shadow-run-1" / "LEGACY_PROVENANCE_RECONCILIATION.json"
        if not artifact.is_file():
            self.skipTest("live reconciliation artifact not present")
        body = json.loads(artifact.read_text(encoding="utf-8"))
        run_id = body["run_id"]
        loaded = cli._load_reconciled_decision_ids(run_id)
        self.assertGreaterEqual(len(loaded), 1)
        self.assertEqual(cli._load_reconciled_decision_ids("SHRUN-NOT-FOUND"), set())


if __name__ == "__main__":
    unittest.main()
