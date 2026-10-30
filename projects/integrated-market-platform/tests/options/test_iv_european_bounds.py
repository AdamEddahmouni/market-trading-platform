"""European implied-volatility regressions (audit 2026-10-29: AUD-036 admission bounds, AUD-038 convergence).

The reference price below uses ``statistics.NormalDist``, independent of the module's erf helper.
"""

from __future__ import annotations

import itertools
import math
import statistics
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.options.iv import (  # noqa: E402
    IV_SOLVER_VERSION,
    bsm_price,
    dual_track_iv,
    implied_volatility,
)

_N = statistics.NormalDist()


def reference_price(spot: float, strike: float, time_years: float, rate: float, sigma: float, call_put: str) -> float:
    d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * time_years) / (sigma * math.sqrt(time_years))
    d2 = d1 - sigma * math.sqrt(time_years)
    discount = math.exp(-rate * time_years)
    if call_put == "call":
        return spot * _N.cdf(d1) - strike * discount * _N.cdf(d2)
    return strike * discount * _N.cdf(-d2) - spot * _N.cdf(-d1)


def european_bounds(spot: float, strike: float, time_years: float, rate: float, call_put: str) -> tuple[float, float]:
    discounted = strike * math.exp(-rate * time_years)
    if call_put == "call":
        return max(spot - discounted, 0.0), spot
    return max(discounted - spot, 0.0), discounted


class EuropeanAdmissionBoundTests(unittest.TestCase):
    def test_aud036_in_the_money_put_below_spot_intrinsic_is_valid(self) -> None:
        # Lower bound 100e^-0.05 - 80 = 15.12 < price 15.29 < spot intrinsic 20 (v1 refused it).
        price = reference_price(80, 100, 1.0, 0.05, 0.2, "put")
        self.assertLess(price, 20.0)
        self.assertGreater(price, european_bounds(80, 100, 1.0, 0.05, "put")[0])
        self.assertAlmostEqual(implied_volatility(price, 80, 100, 1.0, 0.05, "put"), 0.2, places=6)
        track = dual_track_iv(market_price=price, spot=80, strike=100, time_years=1.0, rate=0.05,
                              call_put="put", provider_iv=0.2)
        self.assertFalse(track["iv_invalid"])
        self.assertEqual(track["solver_version"], IV_SOLVER_VERSION)

    def test_negative_rate_in_the_money_call_below_spot_intrinsic_is_valid(self) -> None:
        # r < 0 lifts the discounted strike above K: lower bound 130 - 100e^0.02 = 27.98 < price < 30.
        price = reference_price(130, 100, 2.0, -0.01, 0.1, "call")
        self.assertLess(price, 30.0)
        self.assertAlmostEqual(implied_volatility(price, 130, 100, 2.0, -0.01, "call"), 0.1, places=6)

    def test_negative_rate_put_upper_bound_is_the_discounted_strike_above_k(self) -> None:
        upper = european_bounds(50, 100, 1.0, -0.02, "put")[1]
        self.assertGreater(upper, 100.0)
        price = reference_price(50, 100, 1.0, -0.02, 0.6, "put")
        self.assertAlmostEqual(implied_volatility(price, 50, 100, 1.0, -0.02, "put"), 0.6, places=6)

    def test_prices_at_or_outside_the_bounds_are_refused(self) -> None:
        for spot, rate, call_put in itertools.product((80.0, 100.0, 120.0), (-0.01, 0.0, 0.05), ("call", "put")):
            lower, upper = european_bounds(spot, 100.0, 1.0, rate, call_put)
            for price in (lower, lower - 0.01, upper, upper + 0.01):
                with self.subTest(spot=spot, rate=rate, call_put=call_put, price=price):
                    self.assertIsNone(implied_volatility(price, spot, 100.0, 1.0, rate, call_put))

    def test_invalid_inputs_fail_closed(self) -> None:
        for args in ((0.0, 100, 100, 1, 0.05), (-1.0, 100, 100, 1, 0.05), (5.0, 0, 100, 1, 0.05),
                     (5.0, 100, 0, 1, 0.05), (5.0, 100, 100, 0, 0.05), (5.0, 100, 100, -1, 0.05),
                     (math.nan, 100, 100, 1, 0.05), (5.0, 100, 100, 1, math.inf)):
            with self.subTest(args=args):
                self.assertIsNone(implied_volatility(*args, "call"))


class ConvergenceTests(unittest.TestCase):
    def test_aud038_high_volatility_short_dated_call(self) -> None:
        price = reference_price(50, 100, 0.25, 0.05, 1.2, "call")  # about 2.51, vega about 6.9
        self.assertAlmostEqual(implied_volatility(price, 50, 100, 0.25, 0.05, "call"), 1.2, places=6)

    def test_very_high_volatility_needs_bracket_expansion(self) -> None:
        price = reference_price(100, 100, 0.5, 0.03, 3.5, "call")
        self.assertAlmostEqual(implied_volatility(price, 100, 100, 0.5, 0.03, "call"), 3.5, places=5)

    def test_identifiable_grid_round_trips(self) -> None:
        # The audit's 1,400-case grid. Identifiable: enough time value and vega to recover sigma to 1e-4.
        spots, times = (50, 80, 95, 100, 105, 120, 150), (0.02, 0.25, 1.0, 3.0)
        rates, sigmas = (-0.01, 0.0, 0.02, 0.05, 0.10), (0.05, 0.10, 0.20, 0.60, 1.20)
        identifiable = recovered = 0
        for spot, time_years, rate, sigma, call_put in itertools.product(spots, times, rates, sigmas, ("call", "put")):
            price = reference_price(spot, 100.0, time_years, rate, sigma, call_put)
            lower, _ = european_bounds(spot, 100.0, time_years, rate, call_put)
            d1 = (math.log(spot / 100.0) + (rate + 0.5 * sigma * sigma) * time_years) / (sigma * math.sqrt(time_years))
            vega = spot * _N.pdf(d1) * math.sqrt(time_years)
            solved = implied_volatility(price, spot, 100.0, time_years, rate, call_put)
            if solved is not None:
                # Whatever is returned must reprice the input within the solver's price tolerance.
                self.assertLess(abs(reference_price(spot, 100.0, time_years, rate, solved, call_put) - price), 1e-5)
            if price - lower >= 0.01 and vega >= 0.05:
                identifiable += 1
                with self.subTest(spot=spot, time_years=time_years, rate=rate, sigma=sigma, call_put=call_put):
                    self.assertIsNotNone(solved)
                    self.assertAlmostEqual(solved, sigma, delta=1e-4)
                    recovered += 1
        self.assertEqual(identifiable, 986)
        self.assertEqual(recovered, identifiable)

    def test_module_price_matches_the_independent_reference(self) -> None:
        for args in ((100, 100, 1.0, 0.05, 0.2, "call"), (80, 100, 1.0, 0.05, 0.2, "put"),
                     (130, 100, 2.0, -0.01, 0.1, "call"), (50, 100, 0.25, 0.05, 1.2, "call")):
            with self.subTest(args=args):
                self.assertAlmostEqual(bsm_price(*args), reference_price(*args), places=9)


class LimitingContractTests(unittest.TestCase):
    """bsm_price's documented fail-closed contract (formula ledger): non-positive spot/strike/T/vol price 0.0.

    This is not the mathematical T->0 / sigma->0 limit (intrinsic / discounted-forward intrinsic); the IV solver
    never evaluates there because its bracket starts strictly above zero volatility.
    """

    def test_non_positive_time_or_volatility_prices_zero(self) -> None:
        self.assertEqual(bsm_price(110, 100, 0.0, 0.05, 0.2, "call"), 0.0)
        self.assertEqual(bsm_price(110, 100, 1.0, 0.05, 0.0, "call"), 0.0)

    def test_small_positive_time_and_volatility_approach_the_limits(self) -> None:
        self.assertAlmostEqual(bsm_price(110, 100, 1e-8, 0.05, 0.2, "call"), 10.0, places=4)
        self.assertAlmostEqual(bsm_price(90, 100, 1.0, 0.05, 1e-8, "put"), 100 * math.exp(-0.05) - 90, places=6)


if __name__ == "__main__":
    unittest.main()
