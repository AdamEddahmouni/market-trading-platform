"""Lane E findings registry structural checks (IMP-RESEARCH-VALIDATION-04)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_IMP_ROOT = Path(__file__).resolve().parents[2]
_LANE_E_DIR = (
    _IMP_ROOT
    / "evidence"
    / "historical-research"
    / "imp-research-validation-04-lane-e-findings"
)

_FINDING_FIELDS = (
    "FINDING_ID",
    "SOURCE_RUN",
    "OBSERVATION",
    "CONFIDENCE / LIMITATION",
    "POSSIBLE_CAUSE",
    "FOLLOW-UP_HYPOTHESIS",
    "DATA NEEDED",
    "PROPOSED TEST",
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


class ImpResearchValidation04LaneEFindingsTests(unittest.TestCase):
    def test_findings_registry_shape(self) -> None:
        path = _LANE_E_DIR / "findings_registry_v1.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["lane"], "E")
        findings = payload["findings"]
        self.assertGreaterEqual(len(findings), 10)
        ids = [row["FINDING_ID"] for row in findings]
        self.assertEqual(len(ids), len(set(ids)))
        for row in findings:
            for field in _FINDING_FIELDS:
                self.assertIn(field, row)

    def test_hypothesis_queue_ranked_and_linked(self) -> None:
        findings_path = _LANE_E_DIR / "findings_registry_v1.json"
        queue_path = _LANE_E_DIR / "hypothesis_queue_v1.json"
        finding_ids = {row["FINDING_ID"] for row in json.loads(findings_path.read_text(encoding="utf-8"))["findings"]}
        queue = json.loads(queue_path.read_text(encoding="utf-8"))
        hypotheses = queue["hypotheses"]
        ranks = [h["queue_rank"] for h in hypotheses]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual(hypotheses[0]["hypothesis_queue_id"], "LANE-E-HYP-OPEND-MULTI-SESSION-V2")
        for hyp in hypotheses:
            for field in _HYPOTHESIS_REQUIRED:
                self.assertIn(field, hyp)
            for fid in hyp["source_finding_ids"]:
                self.assertIn(fid, finding_ids)


if __name__ == "__main__":
    unittest.main()
