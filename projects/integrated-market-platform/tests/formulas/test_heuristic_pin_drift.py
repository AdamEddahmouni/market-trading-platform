"""Assert Q-H1 named module constants still match formula_ledger.json (no calibration)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
# Canonical monorepo tree (projects/short-squeeze-project), not a root nested checkout.
# CI sparse-checks a sibling short-squeeze-project without apps/.
SQUEEZE_CORE = ROOT.parent / "short-squeeze-project" / "short-squeeze-core"
sys.path.insert(0, str(SQUEEZE_CORE))

from apps.research_screener.methodologies.adam_v1 import IGNITION, PRESSURE  # noqa: E402
from market_platform_foundation.cross_lane import fusion as fusion_mod  # noqa: E402
from market_platform_foundation.research.distribution import garch as garch_mod  # noqa: E402
from market_platform_foundation.research.distribution import har_rv as har_mod  # noqa: E402
from market_platform_foundation.options import breeden_litzenberger as options_bl  # noqa: E402
from market_platform_foundation.options import dealer as options_dealer  # noqa: E402
from market_platform_foundation.options import delta_hedged as options_dh  # noqa: E402
from market_platform_foundation.options import r_o6 as options_ro6  # noqa: E402
from market_platform_foundation.options import risk_neutral as options_q  # noqa: E402
from market_platform_foundation.options import surface as options_surface  # noqa: E402
from market_platform_foundation.research.squeeze_models import logistic_hazard as logistic_mod  # noqa: E402

LEDGER_PATH = ROOT / "docs" / "research" / "formula_ledger.json"

FUSION_LIQUIDITY_ATTRS = {
    "book_imbalance_supports": "LIQUIDITY_BOOK_IMBALANCE_SUPPORTS",
    "book_imbalance_opposes": "LIQUIDITY_BOOK_IMBALANCE_OPPOSES",
    "book_fragility_elevated": "LIQUIDITY_BOOK_FRAGILITY_ELEVATED",
    "depth_withdrawal_gt_0": "LIQUIDITY_DEPTH_WITHDRAWAL_GT_0",
    "depth_replenishment_gt_0": "LIQUIDITY_DEPTH_REPLENISHMENT_GT_0",
    "resiliency_boost_cap": "LIQUIDITY_RESILIENCY_BOOST_CAP",
    "fill_probability_lt_0.55": "LIQUIDITY_FILL_PROBABILITY_LT_0_55",
    "expected_slippage_spread_fraction_ge_0.0035": "LIQUIDITY_EXPECTED_SLIPPAGE_SPREAD_FRACTION_GE_0_0035",
    "adverse_selection_risk_ge_0.45": "LIQUIDITY_ADVERSE_SELECTION_RISK_GE_0_45",
}

FUSION_FUTURES_ATTRS = {
    "leverage_stress_elevated": "FUTURES_LEVERAGE_STRESS_ELEVATED",
    "macro_event_risk": "FUTURES_MACRO_EVENT_RISK",
    "rv_spread_abs_z_gt_2": "FUTURES_RV_SPREAD_ABS_Z_GT_2",
    "trend_up": "FUTURES_TREND_UP",
    "trend_down": "FUTURES_TREND_DOWN",
}

ADAM_PRESSURE_WEIGHTS = {
    "published_short_interest_pct_weight": "published_short_interest_pct",
    "days_to_cover_weight": "days_to_cover",
    "cost_to_borrow_weight": "cost_to_borrow",
    "borrow_availability_pct_float_weight": "borrow_availability_pct_float",
    "float_shares_weight": "float_shares",
}

ADAM_IGNITION_WEIGHTS = {
    "current_percentage_change_weight": "current_percentage_change",
    "relative_volume_weight": "relative_volume",
    "completed_bar_acceleration_weight": "completed_bar_acceleration",
    "catalyst_age_hours_weight": "catalyst_age_hours",
}


def _ledger_formulas() -> dict[str, dict]:
    payload = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    return {row["id"]: row for row in payload["formulas"]}


class HeuristicPinDriftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.formulas = _ledger_formulas()

    def test_fusion_liquidity_pins_match_ledger(self) -> None:
        pins = self.formulas["fusion.liquidity_factor"]["pinned_constants"]
        for key, attr in FUSION_LIQUIDITY_ATTRS.items():
            self.assertEqual(getattr(fusion_mod, attr), pins[key], msg=key)

    def test_fusion_futures_pins_match_ledger(self) -> None:
        pins = self.formulas["fusion.futures_regime_factor"]["pinned_constants"]
        for key, attr in FUSION_FUTURES_ATTRS.items():
            self.assertEqual(getattr(fusion_mod, attr), pins[key], msg=key)

    def test_garch_pins_match_ledger(self) -> None:
        pins = self.formulas["vol.garch11"]["pinned_constants"]
        self.assertEqual(garch_mod.DEFAULT_OMEGA, pins["omega"])
        self.assertEqual(garch_mod.DEFAULT_ALPHA, pins["alpha"])
        self.assertEqual(garch_mod.DEFAULT_BETA, pins["beta"])

    def test_har_pins_match_ledger(self) -> None:
        pins = self.formulas["vol.har_rv"]["pinned_constants"]
        self.assertEqual(har_mod.HAR_DAILY_WEIGHT, pins["daily_weight"])
        self.assertEqual(har_mod.HAR_WEEKLY_WEIGHT, pins["weekly_weight"])
        self.assertEqual(har_mod.HAR_MONTHLY_WEIGHT, pins["monthly_weight"])
        self.assertEqual(har_mod.HAR_DAILY_WINDOW, pins["daily_window"])
        self.assertEqual(har_mod.HAR_WEEKLY_WINDOW, pins["weekly_window"])
        self.assertEqual(har_mod.HAR_MONTHLY_WINDOW, pins["monthly_window"])

    def test_logistic_pins_match_ledger(self) -> None:
        pins = self.formulas["squeeze.logistic_hazard"]["pinned_constants"]
        self.assertEqual(list(logistic_mod.DEFAULT_WEIGHTS), pins["default_weights"])
        self.assertEqual(logistic_mod.DEFAULT_HORIZON_DAYS, pins["default_horizon_days"])

    def test_adam_pressure_ignition_weights_match_ledger(self) -> None:
        pressure_pins = self.formulas["adam.pressure_score"]["pinned_constants"]
        for pin_key, component in ADAM_PRESSURE_WEIGHTS.items():
            self.assertEqual(PRESSURE[component][0], pressure_pins[pin_key], msg=pin_key)
        ignition_pins = self.formulas["adam.ignition_score"]["pinned_constants"]
        for pin_key, component in ADAM_IGNITION_WEIGHTS.items():
            self.assertEqual(IGNITION[component][0], ignition_pins[pin_key], msg=pin_key)

    def test_dealer_surface_q_drop_silent_rate_pins(self) -> None:
        dealer = self.formulas["options.dealer_gamma_proxy"]
        q = self.formulas["options.risk_neutral_q"]
        surface = self.formulas["options.surface_underlying_fallback"]
        self.assertEqual(dealer["version"], "options_dealer_proxy_v2")
        self.assertNotIn("DEFAULT_RATE", dealer.get("pinned_constants", {}))
        self.assertNotIn("default_rate", q.get("pinned_constants", {}))
        self.assertEqual(q["pinned_constants"]["tail_threshold"], 0.05)
        self.assertIn("sigma_kt_v3", surface["notes"])
        self.assertFalse(hasattr(options_dealer, "DEFAULT_RATE"))
        self.assertFalse(hasattr(options_surface, "DEFAULT_RATE"))
        self.assertFalse(hasattr(options_q, "DEFAULT_RATE"))
        self.assertEqual(options_surface.SURFACE_VERSION, "sigma_kt_v3")
        self.assertEqual(options_dealer.DEALER_VERSION, "options_dealer_proxy_v2")
        delta_hedged = self.formulas["options.delta_hedged"]
        r_o6 = self.formulas["options.r_o6"]
        self.assertEqual(delta_hedged["version"], "delta_hedged_research_v2")
        self.assertEqual(r_o6["version"], "r_o6_research_v2")
        self.assertNotIn("DEFAULT_RATE", delta_hedged.get("pinned_constants", {}))
        self.assertNotIn("DEFAULT_RATE", r_o6.get("pinned_constants", {}))
        self.assertFalse(hasattr(options_dh, "DEFAULT_RATE"))
        self.assertFalse(hasattr(options_ro6, "DEFAULT_RATE"))
        self.assertEqual(options_dh.DELTA_HEDGED_VERSION, "delta_hedged_research_v2")
        self.assertEqual(options_ro6.R_O6_VERSION, "r_o6_research_v2")

    def test_bl_q_pins_match_ledger(self) -> None:
        bl = self.formulas["options.risk_neutral_q_bl"]
        q = self.formulas["options.risk_neutral_q"]
        self.assertEqual(bl["version"], "risk_neutral_breeden_litzenberger_v1")
        self.assertEqual(q["version"], "risk_neutral_log_normal_moment_approx_v1")
        pins = bl["pinned_constants"]
        self.assertEqual(options_bl.MIN_UNIQUE_STRIKES, pins["min_unique_strikes"])
        self.assertEqual(options_bl.DENSITY_MASS_MIN, pins["density_mass_min"])
        self.assertEqual(options_bl.DENSITY_MASS_MAX, pins["density_mass_max"])
        self.assertEqual(options_bl.TAIL_THRESHOLD, pins["tail_threshold"])
        self.assertEqual(options_bl.BL_MODEL_VERSION, bl["version"])
        self.assertEqual(bl["capability_class"], "research_baseline")
        self.assertFalse(hasattr(options_bl, "DEFAULT_RATE"))


if __name__ == "__main__":
    unittest.main()
