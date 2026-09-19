"""Lane C frozen simulator experiment specs — schema and canonical constant guards (no OpenD)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Canonical strings from fill_economics.py / execution/simulator.py (JSON-only guard; no package import).
ACCOUNTING_VERSION = "simulator-research-fill-economics/3.0.1"
COST_MODEL_VERSION = "simulator-research/notional-linear-bps/1.0.0"
SIMULATOR_VERSION = "phase7.bar-conservative/1.1.0"
DEFAULT_RISK_POLICY_COMMISSION = 0
DEFAULT_RISK_POLICY_FEE = 0

EVIDENCE = ROOT / "evidence" / "historical-research"
V3_FROZEN = (
    EVIDENCE
    / "imp-integrate-experiment-05-r3-opend-fill-economics-v3"
    / "frozen_experiment_definition.json"
)
COST_SPEC = EVIDENCE / "imp-simulator-cost-sensitivity-v4" / "pre_registered_methodology_v1.json"
COST_EXEC = EVIDENCE / "imp-simulator-cost-sensitivity-v4" / "execution_status_v1.json"
COST_RECEIPT = EVIDENCE / "imp-simulator-cost-sensitivity-v4" / "cost_sensitivity_v4_evidence_receipt.json"
FILL_SPEC = EVIDENCE / "imp-simulator-fill-price-realism-v1" / "methodology_v1.json"
READINESS = EVIDENCE / "imp-simulator-experiment-specs-sep18" / "lane_c_readiness_v1.json"

COST_V4_EXPERIMENT_HASH = "30FB6972170147A49B9C23423596451F5EC865433B888B1DD5F48AA1E9020B53"
COST_V4_PACK_RUN_ID = "1DEF586AD729B270E20814B03606A718"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class SimulatorExperimentSpecsLaneCTests(unittest.TestCase):
    def test_cost_spec_matches_code_and_v3_frozen_baseline(self) -> None:
        spec = _load(COST_SPEC)
        v3 = _load(V3_FROZEN)
        self.assertTrue(spec["spec_ready"])
        self.assertFalse(spec["executed"])
        self.assertEqual(spec["accounting_version"], ACCOUNTING_VERSION)
        self.assertEqual(spec["cost_model_version"], COST_MODEL_VERSION)
        self.assertEqual(spec["simulator_version"], SIMULATOR_VERSION)
        self.assertEqual(
            spec["v3_baseline_cost_slippage_bps"],
            float(v3["run_parameters"]["cost_slippage_bps"]),
        )
        self.assertEqual(spec["dataset"]["dataset_fingerprint"], v3["dataset"]["dataset_fingerprint"])
        self.assertIn(5.0, spec["cost_slippage_bps_grid"])
        self.assertEqual(len(spec["cost_slippage_bps_grid"]), spec["cost_slippage_bps_grid_size_max"])
        self.assertEqual(
            spec["risk_policy_defaults"]["commission_minor_per_share"],
            DEFAULT_RISK_POLICY_COMMISSION,
        )
        self.assertEqual(
            spec["risk_policy_defaults"]["fee_minor_per_order"],
            DEFAULT_RISK_POLICY_FEE,
        )
        self.assertEqual(
            str(v3["run_parameters"]["simulator_version"]),
            SIMULATOR_VERSION,
        )

    def test_fill_price_spec_current_binding(self) -> None:
        spec = _load(FILL_SPEC)
        self.assertTrue(spec["spec_ready"])
        self.assertFalse(spec["executed"])
        self.assertEqual(spec["current_fill_binding"]["simulator_version"], SIMULATOR_VERSION)
        self.assertEqual(spec["current_fill_binding"]["fill_price_long"], "bar_high")
        self.assertEqual(spec["current_fill_binding"]["fill_price_short"], "bar_low")

    def test_cost_v4_pre_registration_unchanged(self) -> None:
        """Pre-exec methodology JSON stays frozen; post-exec status is separate."""
        spec = _load(COST_SPEC)
        self.assertTrue(spec["spec_ready"])
        self.assertFalse(spec["executed"])
        self.assertFalse(spec["implementation_ready"])

    def test_cost_v4_execution_status_matches_receipt(self) -> None:
        status = _load(COST_EXEC)
        receipt = _load(COST_RECEIPT)
        self.assertTrue(status["EXECUTED"])
        self.assertTrue(status["IMPLEMENTATION_READY"])
        self.assertEqual(status["execution_status"], "EXECUTED_BOUNDED_HISTORICAL_OBSERVATION")
        self.assertEqual(status["experiment_definition_hash"], COST_V4_EXPERIMENT_HASH)
        self.assertEqual(status["pack_run_id"], COST_V4_PACK_RUN_ID)
        self.assertEqual(receipt["execution_status"], status["execution_status"])
        self.assertEqual(receipt["experiment_definition_hash"], COST_V4_EXPERIMENT_HASH)
        self.assertEqual(receipt["pack_run_id"], COST_V4_PACK_RUN_ID)
        self.assertEqual(receipt["contamination_status"], "PASS")

    def test_lane_c_readiness_gates(self) -> None:
        readiness = _load(READINESS)
        cost = readiness["hypotheses"]["LANE-E-HYP-SIMULATOR-COST-SENSITIVITY-V4"]
        fill = readiness["hypotheses"]["LANE-E-HYP-SIMULATOR-FILL-PRICE-REALISM-V1"]
        dd = readiness["hypotheses"]["LANE-E-HYP-SIMULATOR-DRAWDOWN-WIRING-V1"]
        self.assertTrue(cost["SPEC_READY"])
        self.assertTrue(cost["IMPLEMENTATION_READY"])
        self.assertTrue(cost["EXECUTED"])
        self.assertEqual(cost["execution_status"], "EXECUTED_BOUNDED_HISTORICAL_OBSERVATION")
        self.assertEqual(cost["experiment_definition_hash"], COST_V4_EXPERIMENT_HASH)
        self.assertEqual(cost["pack_run_id"], COST_V4_PACK_RUN_ID)
        self.assertEqual(
            cost["evidence_receipt_path"],
            "evidence/historical-research/imp-simulator-cost-sensitivity-v4/cost_sensitivity_v4_evidence_receipt.json",
        )
        self.assertTrue(fill["SPEC_READY"])
        self.assertFalse(fill["IMPLEMENTATION_READY"])
        self.assertFalse(fill["EXECUTED"])
        self.assertTrue(dd["SPEC_READY"])
        self.assertTrue(dd["IMPLEMENTATION_READY"])
        self.assertFalse(dd["EXECUTED"])


if __name__ == "__main__":
    unittest.main()
