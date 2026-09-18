"""Research contamination auditor — contractual leakage checks (IMP-OFFHOURS-RESEARCH-03)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.calibration.dual_corpus.contamination_auditor import (  # noqa: E402
    CONTAMINATION_STATUS_FAIL,
    CONTAMINATION_STATUS_PASS,
    QUESTION_FEATURES_SAW_FUTURE,
    QUESTION_HISTORICAL_IN_ITEM9,
    QUESTION_HOLDOUT_IN_TRAINING,
    QUESTION_PROSPECTIVE_IN_HISTORICAL,
    QUESTION_TRAIN_SAW_TEST,
    audit_research_contamination_run,
)
from market_platform_foundation.paper.calibration.dual_corpus.evidence_authority import (  # noqa: E402
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
    CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
)
from market_platform_foundation.paper.calibration.dual_corpus.leak_audit import (  # noqa: E402
    VIOLATION_MISSING_LINEAGE,
)
from market_platform_foundation.paper.calibration.dual_corpus.run_manifest import (  # noqa: E402
    RESEARCH_CONTAMINATION_RUN_MANIFEST_KIND,
    RESEARCH_CONTAMINATION_RUN_SCHEMA_VERSION,
)


def _clean_manifest(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "artifact_kind": RESEARCH_CONTAMINATION_RUN_MANIFEST_KIND,
        "schema_version": RESEARCH_CONTAMINATION_RUN_SCHEMA_VERSION,
        "run_id": "research-audit-fixture-1",
        "lineage_complete": True,
        "authority_context": {
            "primary_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
            "item9_effect": "NONE",
        },
        "splits": {
            "train": {"start_ns": 1, "end_ns": 100},
            "test": {"start_ns": 100, "end_ns": 200},
        },
        "holdout": {"holdout_start_ns": 500, "holdout_end_ns": 600},
        "feature_lineage": [
            {"decision_cutoff_ns": 50, "feature_as_of_ns": 40, "ref": "feat-1"},
        ],
        "training_examples": [{"snapshot_id": "s1", "decision_time_ns": 10}],
        "corpus_inputs": [],
        "item9_prospective_inputs": [],
        "target_leakage": [],
    }
    body.update(overrides)
    return body


class ResearchContaminationAuditorTests(unittest.TestCase):
    def test_clean_manifest_passes_all_questions(self) -> None:
        report = audit_research_contamination_run(_clean_manifest())
        self.assertEqual(report["CONTAMINATION_STATUS"], CONTAMINATION_STATUS_PASS)
        self.assertEqual(report["questions"][QUESTION_TRAIN_SAW_TEST], CONTAMINATION_STATUS_PASS)
        self.assertEqual(report["questions"][QUESTION_FEATURES_SAW_FUTURE], CONTAMINATION_STATUS_PASS)
        self.assertEqual(report["questions"][QUESTION_HOLDOUT_IN_TRAINING], CONTAMINATION_STATUS_PASS)
        self.assertEqual(report["questions"][QUESTION_PROSPECTIVE_IN_HISTORICAL], CONTAMINATION_STATUS_PASS)
        self.assertEqual(report["questions"][QUESTION_HISTORICAL_IN_ITEM9], CONTAMINATION_STATUS_PASS)
        self.assertEqual(report["evidence_language"]["AUTHORITY"], CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT)
        self.assertEqual(report["evidence_language"]["ITEM9_EFFECT"], "NONE")

    def test_missing_lineage_fails_closed(self) -> None:
        report = audit_research_contamination_run({"run_id": "x", "lineage_complete": False})
        self.assertEqual(report["CONTAMINATION_STATUS"], CONTAMINATION_STATUS_FAIL)
        self.assertTrue(report["violations"])
        self.assertEqual(report["violations"][0]["reason_code"], VIOLATION_MISSING_LINEAGE)

    def test_train_test_overlap(self) -> None:
        manifest = _clean_manifest(
            splits={
                "train": {"start_ns": 1, "end_ns": 150},
                "test": {"start_ns": 100, "end_ns": 200},
            }
        )
        report = audit_research_contamination_run(manifest)
        self.assertEqual(report["CONTAMINATION_STATUS"], CONTAMINATION_STATUS_FAIL)
        self.assertEqual(report["questions"][QUESTION_TRAIN_SAW_TEST], CONTAMINATION_STATUS_FAIL)

    def test_feature_after_cutoff(self) -> None:
        manifest = _clean_manifest(
            feature_lineage=[{"decision_cutoff_ns": 50, "feature_as_of_ns": 55, "ref": "bad"}]
        )
        report = audit_research_contamination_run(manifest)
        self.assertEqual(report["questions"][QUESTION_FEATURES_SAW_FUTURE], CONTAMINATION_STATUS_FAIL)

    def test_holdout_in_training(self) -> None:
        manifest = _clean_manifest(
            training_examples=[{"snapshot_id": "holdout-row", "decision_time_ns": 550}]
        )
        report = audit_research_contamination_run(manifest)
        self.assertEqual(report["questions"][QUESTION_HOLDOUT_IN_TRAINING], CONTAMINATION_STATUS_FAIL)

    def test_prospective_in_historical_research(self) -> None:
        manifest = _clean_manifest(
            corpus_inputs=[
                {
                    "purpose": "historical_research",
                    "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
                }
            ]
        )
        report = audit_research_contamination_run(manifest)
        self.assertEqual(report["questions"][QUESTION_PROSPECTIVE_IN_HISTORICAL], CONTAMINATION_STATUS_FAIL)

    def test_historical_in_item9_prospective(self) -> None:
        manifest = _clean_manifest(
            item9_prospective_inputs=[
                {
                    "experiment_id": "bad-item9",
                    "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
                }
            ]
        )
        report = audit_research_contamination_run(manifest)
        self.assertEqual(report["questions"][QUESTION_HISTORICAL_IN_ITEM9], CONTAMINATION_STATUS_FAIL)

    def test_protected_holdout_corpus_in_training_fails_run(self) -> None:
        manifest = _clean_manifest(
            corpus_inputs=[
                {
                    "purpose": "selection_or_training",
                    "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
                }
            ]
        )
        report = audit_research_contamination_run(manifest)
        self.assertEqual(report["CONTAMINATION_STATUS"], CONTAMINATION_STATUS_FAIL)


if __name__ == "__main__":
    unittest.main()
