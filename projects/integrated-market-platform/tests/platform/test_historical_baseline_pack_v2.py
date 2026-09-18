"""Frozen OpenD Historical Baseline Pack v2 (Lane R2 definition / integrity only)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.historical_research_harness.baseline_pack_v2 import (  # noqa: E402
    HISTORICAL_BASELINE_PACK_V2,
    HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID,
    HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID,
    OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT,
    canonical_baseline_pack_v2_evidence_dir,
    load_pinned_opend_build,
    verify_frozen_experiment_definition,
    verify_pinned_opend_corpus_fingerprint,
)
from market_platform_foundation.intelligence.historical_research_harness.consumption import (  # noqa: E402
    HistoricalResearchHoldoutConsumptionError,
    assert_split_consumable_for_training_or_selection,
)
from market_platform_foundation.intelligence.historical_research_harness.features import (  # noqa: E402
    reconstruct_historical_research_features,
)
from market_platform_foundation.intelligence.historical_research_harness.split import (  # noqa: E402
    assign_chronological_splits,
    assert_chronological_order,
    decision_times_for_split,
    splits_overlap,
)
from market_platform_foundation.intelligence.historical_research_harness.types import (  # noqa: E402
    ChronologicalSplitPolicy,
    HistoricalResearchSplitName,
)
from market_platform_foundation.paper.calibration.dual_corpus import (  # noqa: E402
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    evaluate_item9_prospective_corpus_admission,
)


class HistoricalBaselinePackV2FreezeTests(unittest.TestCase):
    def test_frozen_definition_hash_recomputes(self) -> None:
        evidence_dir = canonical_baseline_pack_v2_evidence_dir(ROOT)
        frozen_path = evidence_dir / "frozen_experiment_definition.json"
        self.assertTrue(frozen_path.is_file(), msg="frozen definition must be committed for Lane R2")
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
        verify = verify_frozen_experiment_definition(frozen)
        self.assertTrue(verify["ok"], msg=verify.get("reason_code"))
        self.assertEqual(verify["computed_hash"], verify["embedded_hash"])

    def test_tampered_frozen_definition_refused(self) -> None:
        evidence_dir = canonical_baseline_pack_v2_evidence_dir(ROOT)
        frozen = json.loads((evidence_dir / "frozen_experiment_definition.json").read_text(encoding="utf-8"))
        frozen["baseline_strategies"][0]["description"] = "tampered after freeze"
        result = verify_frozen_experiment_definition(frozen)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason_code"], "EXPERIMENT_DEFINITION_HASH_MISMATCH")

    def test_dataset_fingerprint_verified_against_pin(self) -> None:
        corpus_pin = canonical_baseline_pack_v2_evidence_dir(ROOT) / "corpus_pin"
        result = verify_pinned_opend_corpus_fingerprint(repository_root=ROOT, corpus_dir=corpus_pin)
        self.assertTrue(result["ok"], msg=result.get("reason_code"))
        self.assertEqual(result["computed_normalized_fingerprint"], OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT)
        self.assertEqual(result["row_count"], 1950)

    def test_freeze_receipt_declares_not_executed(self) -> None:
        receipt_path = canonical_baseline_pack_v2_evidence_dir(ROOT) / "baseline_pack_v2_freeze_receipt.json"
        self.assertTrue(receipt_path.is_file())
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["EXPERIMENT_DEFINITION_FROZEN"], "YES")
        self.assertEqual(receipt["performance_run"], "NO")
        self.assertEqual(receipt["execution_status"], "NOT_EXECUTED")

    def test_frozen_metadata_matches_hypothesis(self) -> None:
        frozen = json.loads(
            (canonical_baseline_pack_v2_evidence_dir(ROOT) / "frozen_experiment_definition.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(frozen["hypothesis_id"], HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID)
        self.assertEqual(frozen["experiment_id"], HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID)
        self.assertEqual(frozen["evidence_label"], HISTORICAL_BASELINE_PACK_V2)
        self.assertEqual(
            frozen["dataset"]["dataset_fingerprint"],
            OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT,
        )

    def test_chronological_split_valid_on_pinned_corpus(self) -> None:
        build = load_pinned_opend_build(ROOT)
        self.assertTrue(build.ok)
        bars = json.loads(sorted(build.paths.normalized_dir.glob("*_normalized.json"))[0].read_text(encoding="utf-8"))
        clocks = sorted({int(bar["available_time"]) for bar in bars})
        policy = ChronologicalSplitPolicy()
        assignments = assign_chronological_splits(clocks, policy)
        self.assertFalse(splits_overlap(assignments))
        assert_chronological_order(assignments)
        train = decision_times_for_split(assignments, HistoricalResearchSplitName.HISTORICAL_TRAIN)
        test = decision_times_for_split(assignments, HistoricalResearchSplitName.HISTORICAL_RESEARCH_TEST)
        self.assertTrue(train.isdisjoint(test))

    def test_future_feature_leakage_refused_on_real_bars(self) -> None:
        build = load_pinned_opend_build(ROOT)
        bars = json.loads(sorted(build.paths.normalized_dir.glob("*_normalized.json"))[0].read_text(encoding="utf-8"))
        cutoff = int(bars[100]["available_time"])
        features = reconstruct_historical_research_features(bars, prediction_cutoff_ns=cutoff)
        self.assertEqual(features["prediction_cutoff_ns"], cutoff)
        self.assertNotIn("PIT_FEATURE_FUTURE_INPUT", features.get("pit_rejection_reasons", []))

    def test_prospective_item9_contamination_refused(self) -> None:
        admission = evaluate_item9_prospective_corpus_admission(
            corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT
        )
        self.assertEqual(admission.get("disposition"), "REFUSED")

    def test_holdout_split_refused_for_training(self) -> None:
        with self.assertRaises(HistoricalResearchHoldoutConsumptionError):
            assert_split_consumable_for_training_or_selection(
                HistoricalResearchSplitName.HISTORICAL_RESEARCH_TEST,
                purpose="parameter_selection",
            )


if __name__ == "__main__":
    unittest.main()
