"""V3 OpenD fill-economics experiment prep (Lane B; definition only — no performance run)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.historical_research_harness.baseline_pack import (  # noqa: E402
    verify_frozen_experiment_definition,
)
from market_platform_foundation.intelligence.historical_research_harness.baseline_pack_v2 import (  # noqa: E402
    HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID,
    OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT,
    canonical_baseline_pack_v2_evidence_dir,
    verify_pinned_opend_corpus_fingerprint,
)

V3_EXPERIMENT_ID = "imp-integrate-experiment-05-r3-opend-fill-economics-v3"
V3_HYPOTHESIS_ID = "LANE-H-HYP-SIMULATOR-FILL-ECONOMICS-V3"
V2_IMMUTABLE_HASH = "E8C9ADB9E295EBE913C254FCBBBDDC48A794D9FDE79492CB341138855A67C2A4"
PENDING_HASH_TOKEN = "PENDING_LANE_A_REVIEW"

V3_EVIDENCE_DIR = (
    ROOT
    / "evidence"
    / "historical-research"
    / "imp-integrate-experiment-05-r3-opend-fill-economics-v3"
)

_REQUIRED_METRICS = (
    "signals",
    "intents",
    "fills",
    "traded_notional",
    "turnover",
    "gross_realized_pnl",
    "gross_unrealized_pnl",
    "gross_pnl",
    "transaction_costs",
    "net_pnl",
    "drawdown",
    "exposure",
    "win_loss_closed_trades",
    "directional_accuracy",
    "abstention",
    "coverage",
)

_CONTAMINATION_CHECKS = (
    "DID_TRAIN_SEE_TEST",
    "DID_FEATURES_SEE_FUTURE_DATA",
    "DID_HOLDOUT_ENTER_TRAINING",
    "DID_PROSPECTIVE_RECEIPTS_ENTER_HISTORICAL_RESEARCH",
    "DID_HISTORICAL_DATA_ENTER_PROSPECTIVE_ITEM9",
)


class HistoricalBaselinePackV3PrepTests(unittest.TestCase):
    def test_v3_dataset_fingerprint_passes_on_pinned_corpus(self) -> None:
        corpus_pin = V3_EVIDENCE_DIR / "corpus_pin"
        result = verify_pinned_opend_corpus_fingerprint(repository_root=ROOT, corpus_dir=corpus_pin)
        self.assertTrue(result["ok"], msg=result.get("reason_code"))
        self.assertEqual(result["computed_normalized_fingerprint"], OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT)
        self.assertEqual(result["row_count"], 1950)
        verification = json.loads((V3_EVIDENCE_DIR / "dataset_fingerprint_verification.json").read_text(encoding="utf-8"))
        self.assertTrue(verification["ok"])
        self.assertEqual(verification["experiment_id"], V3_EXPERIMENT_ID)

    def test_pre_execution_definition_not_final_hash(self) -> None:
        frozen_path = V3_EVIDENCE_DIR / "pre_execution_frozen_experiment_definition.json"
        frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
        self.assertEqual(frozen["experiment_definition_hash"], PENDING_HASH_TOKEN)
        self.assertEqual(frozen["hypothesis_id"], V3_HYPOTHESIS_ID)
        self.assertEqual(frozen["experiment_id"], V3_EXPERIMENT_ID)
        self.assertEqual(frozen["research_code_sha"], "PENDING_LANE_A")
        verify = verify_frozen_experiment_definition(frozen)
        self.assertFalse(verify["ok"])
        self.assertEqual(verify["reason_code"], "EXPERIMENT_DEFINITION_HASH_MISMATCH")

    def test_protocol_lists_contamination_checks_and_metrics(self) -> None:
        protocol = json.loads((V3_EVIDENCE_DIR / "experiment_protocol_v3.json").read_text(encoding="utf-8"))
        check_ids = {row["check_id"] for row in protocol["contamination_auditor_checks_required_before_execution"]}
        self.assertEqual(check_ids, set(_CONTAMINATION_CHECKS))
        self.assertEqual(protocol["contamination_auditor_execution_status"], "NOT_RUN_PRE_EXECUTION")
        self.assertEqual(set(protocol["metrics_contract"]["required"]), set(_REQUIRED_METRICS))

    def test_v2_frozen_artifacts_remain_immutable(self) -> None:
        v2_dir = canonical_baseline_pack_v2_evidence_dir(ROOT)
        v2_frozen = json.loads((v2_dir / "frozen_experiment_definition.json").read_text(encoding="utf-8"))
        self.assertEqual(v2_frozen["experiment_id"], HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID)
        self.assertEqual(v2_frozen["experiment_definition_hash"], V2_IMMUTABLE_HASH)
        verify = verify_frozen_experiment_definition(v2_frozen)
        self.assertTrue(verify["ok"], msg=verify.get("reason_code"))

    def test_hypothesis_queue_links_proposed_v3_experiment(self) -> None:
        queue_path = (
            ROOT
            / "evidence"
            / "historical-research"
            / "imp-integrate-experiment-05-lane-h-findings"
            / "hypothesis_queue_v1.json"
        )
        hypotheses = json.loads(queue_path.read_text(encoding="utf-8"))["hypotheses"]
        top = hypotheses[0]
        self.assertEqual(top["hypothesis_queue_id"], V3_HYPOTHESIS_ID)
        self.assertEqual(top.get("proposed_experiment_id"), V3_EXPERIMENT_ID)


if __name__ == "__main__":
    unittest.main()
