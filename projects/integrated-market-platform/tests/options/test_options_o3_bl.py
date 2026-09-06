"""Tests for discrete Breeden–Litzenberger Q (additive O3 path)."""

from __future__ import annotations

import inspect
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.options.breeden_litzenberger import (  # noqa: E402
    BL_MODEL_VERSION,
    BL_NEGATIVE_DENSITY,
    BL_INSUFFICIENT_STRIKES,
    Q_METHOD as BL_Q_METHOD,
    infer_risk_neutral_breeden_litzenberger,
)
from market_platform_foundation.options.risk_neutral import (  # noqa: E402
    MODEL_VERSION,
    Q_METHOD as LN_Q_METHOD,
    RATE_ASSUMPTION_MISSING,
    _horizon_from_surface,
    infer_risk_neutral_distribution,
)
from market_platform_foundation.options import breeden_litzenberger as options_bl  # noqa: E402


def _constant_vol_surface(
    *,
    spot: float = 100.0,
    rate: float = 0.04,
    sigma: float = 0.25,
    dte: int = 30,
    expiration: str = "2026-08-20",
    strikes: list[float] | None = None,
) -> dict:
    if strikes is None:
        strikes = [float(k) for k in range(70, 135, 5)]
    points = [
        {
            "strike": strike,
            "expiration": expiration,
            "dte": dte,
            "call_put": "call",
            "sigma": sigma,
            "underlying_price": spot,
            "rate": rate,
        }
        for strike in strikes
    ]
    return {
        "point_count": len(points),
        "surface_version": "sigma_kt_v3",
        "points": points,
    }


class OptionsO3BreedenLitzenbergerTests(unittest.TestCase):
    def test_constant_vol_smile_matches_log_normal_moments_within_tolerance(self) -> None:
        """Proof this is discrete BL, not a rename of the log-normal approx.

        O3 ``_horizon_from_surface`` uses log-return moments and erf tails.
        BL uses simple-return (K/S-1) moments and density-mass tails on an
        interior finite-difference grid. For a constant-σ smile they must stay
        in the same order of magnitude (documented deltas below) while BL
        reports a different version, tags, and typically non-zero skew.
        """
        spot = 100.0
        rate = 0.04
        sigma = 0.25
        dte = 30
        surface = _constant_vol_surface(spot=spot, rate=rate, sigma=sigma, dte=dte)
        bl = infer_risk_neutral_breeden_litzenberger(
            surface,
            symbol="TEST",
            as_of_time="2026-07-21T19:45:00.000000000Z",
        )
        self.assertTrue(bl.get("available"), bl)
        self.assertEqual(bl.get("model_version"), BL_MODEL_VERSION)
        self.assertEqual(BL_MODEL_VERSION, "risk_neutral_breeden_litzenberger_v1")
        self.assertIn("breeden_litzenberger_finite_difference", bl.get("methodology_tags", []))
        self.assertIn("iv_reconstructed_call_curve", bl.get("methodology_tags", []))
        self.assertEqual(bl.get("rate"), rate)
        self.assertEqual(bl.get("q_method"), BL_Q_METHOD)
        self.assertEqual(BL_Q_METHOD, "breeden_litzenberger")
        self.assertIn("replay_hash", bl)

        ln = _horizon_from_surface(surface["points"], spot=spot, rate=rate)
        self.assertIsNotNone(ln)
        assert ln is not None
        bl_h = bl["horizons"][0]
        # Mean: O3 is rT-0.5σ²T; BL is E[K/S-1] ≈ e^{rT}-1. Documented abs 0.01.
        self.assertAlmostEqual(bl_h["mean_return"], ln.mean_return, delta=0.01)
        # Variance of simple vs log-return variance σ²T. Documented abs 0.005.
        self.assertAlmostEqual(bl_h["variance"], ln.variance, delta=0.005)
        # Density-mass tails vs O3 erf(log-return z). O3 downside uses Φ(-z),
        # which is not P(R < -0.05); documented abs 0.45.
        self.assertAlmostEqual(bl_h["upside_tail_probability"], ln.upside_tail_probability, delta=0.45)
        self.assertAlmostEqual(
            bl_h["downside_tail_probability"], ln.downside_tail_probability, delta=0.45
        )
        time_years = dte / 365.0
        self.assertAlmostEqual(bl_h["mean_return"], math.exp(rate * time_years) - 1.0, delta=0.01)
        self.assertIsNotNone(bl.get("vol_implied_annualized"))
        self.assertAlmostEqual(float(bl["vol_implied_annualized"]), sigma, delta=0.08)
        self.assertNotEqual(bl_h["skew"], 0.0)
        default_q = infer_risk_neutral_distribution(surface)
        self.assertEqual(default_q.get("model_version"), MODEL_VERSION)
        self.assertEqual(default_q.get("q_method"), LN_Q_METHOD)
        self.assertEqual(LN_Q_METHOD, "log_normal_moment_approx")
        self.assertNotIn("breeden", str(MODEL_VERSION).lower())

    def test_two_unique_strikes_fail_closed(self) -> None:
        surface = _constant_vol_surface(strikes=[130.0, 135.0])
        result = infer_risk_neutral_breeden_litzenberger(surface)
        self.assertFalse(result.get("available"))
        self.assertEqual(result.get("reason"), BL_INSUFFICIENT_STRIKES)

    def test_missing_rate_fail_closed(self) -> None:
        surface = _constant_vol_surface()
        for point in surface["points"]:
            point.pop("rate", None)
        result = infer_risk_neutral_breeden_litzenberger(surface)
        self.assertFalse(result.get("available"))
        self.assertEqual(result.get("reason"), RATE_ASSUMPTION_MISSING)

    def test_negative_butterfly_fail_closed(self) -> None:
        surface = _constant_vol_surface(strikes=[90.0, 95.0, 100.0, 105.0, 110.0])
        for point in surface["points"]:
            if point["strike"] == 100.0:
                point["sigma"] = 0.04
            else:
                point["sigma"] = 0.55
        result = infer_risk_neutral_breeden_litzenberger(surface)
        self.assertFalse(result.get("available"))
        self.assertEqual(result.get("reason"), BL_NEGATIVE_DENSITY)

    def test_no_default_rate_and_bl_version_is_v1(self) -> None:
        self.assertFalse(hasattr(options_bl, "DEFAULT_RATE"))
        self.assertEqual(options_bl.BL_MODEL_VERSION, "risk_neutral_breeden_litzenberger_v1")
        self.assertIsNone(
            inspect.signature(infer_risk_neutral_breeden_litzenberger).parameters["rate"].default
        )
        source = Path(options_bl.__file__).read_text(encoding="utf-8")
        self.assertNotIn("rate: float = 0.05", source)
        self.assertNotIn("infer_risk_neutral_distribution(", source)

    def test_projections_still_use_log_normal_o3(self) -> None:
        src_root = ROOT / "src" / "market_platform_foundation"
        donor = (src_root / "donor_bridge" / "projections.py").read_text(encoding="utf-8")
        providers = (src_root / "providers" / "projections.py").read_text(encoding="utf-8")
        self.assertIn("infer_risk_neutral_distribution", donor)
        self.assertIn("infer_risk_neutral_distribution", providers)
        self.assertNotIn("infer_risk_neutral_breeden_litzenberger", donor)
        self.assertNotIn("infer_risk_neutral_breeden_litzenberger", providers)


if __name__ == "__main__":
    unittest.main()
