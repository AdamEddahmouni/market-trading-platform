"""Recorded news_strategy_evaluation → forward-test bridge tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.paper_forward_bridge.recorded_eval_bridge import (  # noqa: E402
    RecordedEvalBridgeError,
    recorded_eval_forward_handoff_params,
    strategy_evaluation_decision_from_recorded,
)
from market_platform_foundation.intelligence.paper_forward_bridge.types import (  # noqa: E402
    ForwardTestEvidenceClass,
)


class RecordedEvalBridgeTests(unittest.TestCase):
    def test_handoff_marks_recorded_artifacts_only(self) -> None:
        payload = {
            "decision_id": "d1",
            "evaluation_run_id": "run-1",
            "sample_id": "s1",
            "policy_id": "news_deterministic_baseline",
            "policy_version": "1.0.0",
            "policy_classification": "BASELINE_DETERMINISTIC",
            "config_hash": "cfg",
            "as_of": "2024-01-15T14:30:00Z",
            "instrument_id": "ES",
            "asset_class": "FUTURES",
            "decision": "POSITIVE_DIRECTIONAL_BIAS",
            "normalized_directional_units": 1,
            "simulation_only": True,
            "execution_authority": False,
            "news_event_ids": ["n1"],
            "inference_record_ids": [],
            "feature_snapshot_id": "feat-1",
            "market_snapshot_ref": "mkt-1",
        }
        decision = strategy_evaluation_decision_from_recorded(payload)
        params = recorded_eval_forward_handoff_params(
            decision,
            decision_time_ns=1,
            source_time_ns=1,
        )
        self.assertEqual(
            params["evidence_class"],
            ForwardTestEvidenceClass.SOFTWARE_FIXTURE_ONLY.value,
        )
        self.assertEqual(params["intelligence_provider"], "RECORDED_ARTIFACTS_ONLY")

    def test_execution_authority_rejected(self) -> None:
        payload = {
            "policy_classification": "BASELINE_DETERMINISTIC",
            "decision": "NEUTRAL",
            "execution_authority": True,
        }
        with self.assertRaises(RecordedEvalBridgeError):
            strategy_evaluation_decision_from_recorded(payload)


if __name__ == "__main__":
    unittest.main()
