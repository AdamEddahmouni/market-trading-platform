"""Lane H findings registry structural checks (IMP-INTEGRATE-AND-EXPERIMENT-05)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_IMP_ROOT = Path(__file__).resolve().parents[2]
_LANE_H_DIR = (
    _IMP_ROOT
    / "evidence"
    / "historical-research"
    / "imp-integrate-experiment-05-lane-h-findings"
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


class ImpIntegrateExperiment05LaneHFindingsTests(unittest.TestCase):
    def test_findings_registry_shape(self) -> None:
        path = _LANE_H_DIR / "findings_registry_v1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["lane"], "H")
        self.assertEqual(payload["increment_id"], "IMP-INTEGRATE-AND-EXPERIMENT-05")
        findings = payload["findings"]
        self.assertGreaterEqual(len(findings), 8)
        ids = [row["FINDING_ID"] for row in findings]
        self.assertEqual(len(ids), len(set(ids)))
        for row in findings:
            for field in _FINDING_FIELDS:
                self.assertIn(field, row)

    def test_smoke10_non_stub_not_executed_documented(self) -> None:
        registry = json.loads(
            (_LANE_H_DIR / "findings_registry_v1.json").read_text(encoding="utf-8")
        )
        i1 = registry["source_runs"]["lane_i1_nonstub_sut_pr267"]
        self.assertEqual(i1["execution_status"], "NOT_EXECUTED")
        receipt = json.loads(
            (_LANE_H_DIR / "lane_h_synthesis_receipt.json").read_text(encoding="utf-8")
        )
        self.assertEqual(receipt["smoke10_non_stub"]["execution_status"], "NOT_EXECUTED")

    def test_hypothesis_queue_ranked_and_linked(self) -> None:
        findings_path = _LANE_H_DIR / "findings_registry_v1.json"
        queue_path = _LANE_H_DIR / "hypothesis_queue_v1.json"
        finding_ids = {
            row["FINDING_ID"]
            for row in json.loads(findings_path.read_text(encoding="utf-8"))["findings"]
        }
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        hypotheses = queue["hypotheses"]
        ranks = [h["queue_rank"] for h in hypotheses]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual(
            hypotheses[0]["hypothesis_queue_id"],
            "LANE-H-HYP-SIMULATOR-FILL-ECONOMICS-V3",
        )
        closures = queue["lane_e_hypothesis_closure"]
        self.assertGreaterEqual(len(closures), 3)
        for hyp in hypotheses:
            for field in _HYPOTHESIS_REQUIRED:
                self.assertIn(field, hyp)
            for fid in hyp["source_finding_ids"]:
                self.assertIn(fid, finding_ids)
        for closure in closures:
            for fid in closure["closure_finding_ids"]:
                self.assertIn(fid, finding_ids)


if __name__ == "__main__":
    unittest.main()
