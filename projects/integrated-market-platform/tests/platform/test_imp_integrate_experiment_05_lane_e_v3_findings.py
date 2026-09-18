"""Lane E v3 findings registry structural checks (IMP-INTEGRATE-AND-EXPERIMENT-05)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_IMP_ROOT = Path(__file__).resolve().parents[2]
_LANE_E_V3_DIR = (
    _IMP_ROOT
    / "evidence"
    / "historical-research"
    / "imp-integrate-experiment-05-lane-e-v3-findings"
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

_V3_EXPERIMENT_HASH = (
    "81EFC1B1E2650010962F81F5B58B7E614E1AC1C2232E7862890CBB37BF5F3F61"
)
_V2_EXPERIMENT_HASH = (
    "E8C9ADB9E295EBE913C254FCBBBDDC48A794D9FDE79492CB341138855A67C2A4"
)


class ImpIntegrateExperiment05LaneEV3FindingsTests(unittest.TestCase):
    def test_findings_registry_shape(self) -> None:
        path = _LANE_E_V3_DIR / "findings_registry_v1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["lane"], "E")
        self.assertEqual(payload["increment_id"], "IMP-INTEGRATE-AND-EXPERIMENT-05")
        findings = payload["findings"]
        self.assertGreaterEqual(len(findings), 10)
        ids = [row["FINDING_ID"] for row in findings]
        self.assertEqual(len(ids), len(set(ids)))
        for row in findings:
            for field in _FINDING_FIELDS:
                self.assertIn(field, row)

    def test_v3_source_pin_and_smoke10_not_executed(self) -> None:
        registry = json.loads(
            (_LANE_E_V3_DIR / "findings_registry_v1.json").read_text(encoding="utf-8")
        )
        v3 = registry["source_runs"]["integrate_r3_opend_fill_economics_v3_frozen"]
        self.assertEqual(v3["experiment_definition_hash"], _V3_EXPERIMENT_HASH)
        v2 = registry["source_runs"]["integrate_r2_opend_baseline_pack_v2_frozen"]
        self.assertEqual(v2["experiment_definition_hash"], _V2_EXPERIMENT_HASH)
        receipt = json.loads(
            (_LANE_E_V3_DIR / "lane_e_v3_synthesis_receipt.json").read_text(encoding="utf-8")
        )
        self.assertEqual(receipt["SMOKE10_EXECUTED"], "NO")
        self.assertFalse(
            registry["source_runs"]["lane_i1_nonstub_sut_wiring"]["smoke10_executed"]
        )

    def test_hypothesis_queue_ranked_linked_and_v3_hypothesis_closed(self) -> None:
        findings_path = _LANE_E_V3_DIR / "findings_registry_v1.json"
        queue_path = _LANE_E_V3_DIR / "hypothesis_queue_v1.json"
        finding_ids = {
            row["FINDING_ID"]
            for row in json.loads(findings_path.read_text(encoding="utf-8"))["findings"]
        }
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        hypotheses = queue["hypotheses"]
        ranks = [h["queue_rank"] for h in hypotheses]
        self.assertEqual(ranks, sorted(ranks))
        closures = queue["lane_h_hypothesis_closure"]
        self.assertEqual(
            closures[0]["hypothesis_queue_id"],
            "LANE-H-HYP-SIMULATOR-FILL-ECONOMICS-V3",
        )
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
