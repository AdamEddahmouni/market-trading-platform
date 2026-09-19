"""Lane M5 IBP factual gold findings registry structural checks."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_IMP_ROOT = Path(__file__).resolve().parents[2]
_LANE_M5_DIR = (
    _IMP_ROOT
    / "evidence"
    / "intelligence-benchmark"
    / "imp-ibp-factual-gold-v1-lane-m5-findings"
)

_FINDING_FIELDS = (
    "FINDING_ID",
    "SOURCE_RUN",
    "OBSERVATION",
    "LIMITATION",
    "POSSIBLE_CAUSE",
    "FOLLOW_UP_HYPOTHESIS",
    "REQUIRED_DATA",
    "PROPOSED_TEST",
    "AUTHORITY",
)

_HYPOTHESIS_REQUIRED = (
    "queue_rank",
    "hypothesis_queue_id",
    "source_finding_ids",
    "claim",
    "failure_conditions",
    "leakage_risks",
    "evidence_needed_for_promotion",
)

_BASELINE_RUN_ID = "ibp-factual-smoke-28EA7748057E312D"
_REGISTERED_HYPOTHESES = (
    "LANE-M5-HYP-GROUNDED-FACT-EXTRACTION-V1",
    "LANE-M5-HYP-ANSWERABLE-EVIDENCE-UNKNOWN-V1",
    "LANE-M5-HYP-STRUCTURED-FACT-NORMALIZATION-V1",
)


class ImpIbpFactualGoldV1LaneM5FindingsTests(unittest.TestCase):
    def test_findings_registry_shape_and_baseline_pin(self) -> None:
        path = _LANE_M5_DIR / "findings_registry_v1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["lane"], "M5")
        self.assertEqual(payload["increment_id"], "IMP-IBP-FACTUAL-GOLD-V1")
        baseline = payload["source_runs"]["ibp_factual_smoke_v1_baseline"]
        self.assertEqual(baseline["run_id"], _BASELINE_RUN_ID)
        findings = payload["findings"]
        self.assertGreaterEqual(len(findings), 6)
        ids = [row["FINDING_ID"] for row in findings]
        self.assertEqual(len(ids), len(set(ids)))
        for row in findings:
            for field in _FINDING_FIELDS:
                self.assertIn(field, row)

    def test_synthesis_receipt_invariants_and_smoke10_justified(self) -> None:
        receipt = json.loads(
            (_LANE_M5_DIR / "lane_m5_synthesis_receipt.json").read_text(encoding="utf-8")
        )
        self.assertEqual(receipt["baseline_run_id"], _BASELINE_RUN_ID)
        self.assertEqual(receipt["MERGE_PERFORMED"], "NO")
        self.assertEqual(receipt["APPROVE_M5_EVIDENCE"], "YES")
        self.assertEqual(receipt["SMOKE10_JUSTIFIED_IBP_FACTUAL_PROTOCOL"], "YES")
        self.assertEqual(receipt["SMOKE10_JUSTIFIED_LEGACY_STUB_CATALOG"], "NO")
        self.assertEqual(receipt["FULL30_EXECUTED"], "NO")
        self.assertEqual(receipt["frozen_collector_pin"]["sha"], "fed2d9f7")

    def test_hypothesis_queue_ranked_linked_and_methodology_closed(self) -> None:
        findings_path = _LANE_M5_DIR / "findings_registry_v1.json"
        queue_path = _LANE_M5_DIR / "hypothesis_queue_v1.json"
        finding_ids = {
            row["FINDING_ID"] for row in json.loads(findings_path.read_text(encoding="utf-8"))["findings"]
        }
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        hyps = queue["hypotheses"]
        self.assertEqual(len(hyps), 3)
        ranks = [row["queue_rank"] for row in hyps]
        self.assertEqual(sorted(ranks), [1, 2, 3])
        registered = [row["hypothesis_queue_id"] for row in hyps]
        self.assertEqual(registered, list(_REGISTERED_HYPOTHESES))
        for row in hyps:
            for field in _HYPOTHESIS_REQUIRED:
                self.assertIn(field, row)
            for fid in row["source_finding_ids"]:
                self.assertIn(fid, finding_ids)
        closure = queue["methodology_hypothesis_closure"][0]
        self.assertEqual(
            closure["hypothesis_queue_id"], "LANE-E-HYP-IBP-ADMITTED-FACTUAL-GOLD-V1"
        )
        for fid in closure["closure_finding_ids"]:
            self.assertIn(fid, finding_ids)


if __name__ == "__main__":
    unittest.main()
