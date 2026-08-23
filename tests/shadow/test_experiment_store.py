import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.shadow.experiment import ShadowExperimentStore


class ExperimentStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ShadowExperimentStore(Path(self.tmp.name) / "exp.sqlite3")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_open_manifest_is_insert_once_and_never_rewrites(self):
        self.assertTrue(self.store.ensure_run("R1", '{"a":1}', "HASH1", 100))
        self.assertFalse(self.store.ensure_run("R1", '{"a":2}', "HASH2", 200))
        row = self.store.manifest("R1")
        self.assertEqual(row["manifest"], {"a": 1})
        self.assertEqual(row["manifest_hash"], "HASH1")
        self.assertEqual(row["created_at_ns"], 100)

    def test_lifecycle_events_append_only_and_state_derived(self):
        self.store.ensure_run("R1", "{}", "H", 1)
        self.assertEqual(self.store.run_state("R1"), "CREATED")
        self.store.append_event("R1", "OPEN", 10)
        self.store.append_event("R1", "CLOSED", 20)
        self.store.append_event("R1", "OPEN", 30)
        self.assertEqual(
            [e["event_type"] for e in self.store.events("R1")],
            ["OPEN", "CLOSED", "OPEN"],
        )
        self.assertEqual(self.store.run_state("R1"), "OPEN")

    def test_unknown_lifecycle_event_rejected(self):
        self.store.ensure_run("R1", "{}", "H", 1)
        with self.assertRaises(ValueError):
            self.store.append_event("R1", "MUTATED", 10)

    def test_record_decision_unique_per_bucket(self):
        self.store.ensure_run("R1", "{}", "H", 1)
        did, inserted = self.store.record_decision(
            "R1", "BIYA", 1234, "PREDICTED",
            prediction_id="P1", detail={"nss": 0.2}, created_at_ns=5,
        )
        self.assertTrue(inserted)
        did2, inserted2 = self.store.record_decision(
            "R1", "BIYA", 1234, "ABSTAINED_MODEL",
            detail={"reason": "FLAT_BAND"}, created_at_ns=6,
        )
        self.assertFalse(inserted2)
        self.assertEqual(did2, did)
        self.assertEqual(self.store.count_outcomes("R1"), {"PREDICTED": 1})

    def test_record_decision_once_collides_safely(self):
        self.store.ensure_run("R1", "{}", "H", 1)
        first, ok1 = self.store.record_decision_once(
            "R1", "BIYA", 99, "PREDICTED", prediction_id="P1", created_at_ns=1,
        )
        second, ok2 = self.store.record_decision_once(
            "R1", "BIYA", 99, "ABSTAINED_MODEL", detail={}, created_at_ns=2,
        )
        self.assertTrue(ok1)
        self.assertFalse(ok2)
        self.assertIsNone(second)

    def test_iter_decisions_filters_by_outcome(self):
        self.store.ensure_run("R1", "{}", "H", 1)
        self.store.record_decision("R1", "BIYA", 1, "PREDICTED", prediction_id="P1", created_at_ns=1)
        self.store.record_decision("R1", "BIYA", 2, "SKIPPED_QUALITY", created_at_ns=2)
        buckets = [d["decision_bucket"] for d in self.store.iter_decisions("R1", outcome="PREDICTED")]
        self.assertEqual(buckets, [1])

    def test_annotations_are_append_only(self):
        self.store.ensure_run("R1", "{}", "H", 1)
        did, _ = self.store.record_decision("R1", "BIYA", 7, "PREDICTED", prediction_id="P1", created_at_ns=1)
        self.assertTrue(self.store.add_annotation(did, "LABEL_LABELED_UP", {"r30_bps": 12.5}, 9))
        self.assertTrue(self.store.add_annotation(did, "LABEL_ZERO_RETURN", {}, 10))
        kinds = [a["kind"] for a in self.store.annotations(did)]
        self.assertEqual(kinds, ["LABEL_LABELED_UP", "LABEL_ZERO_RETURN"])

    def test_recorder_errors_log(self):
        self.store.ensure_run("R1", "{}", "H", 1)
        self.store.log_error("R1", 42, "STORE_BUSY", {"attempt": 1})
        errors = self.store.recorder_errors("R1")
        self.assertEqual(errors[0]["error_code"], "STORE_BUSY")


if __name__ == "__main__":
    unittest.main()
