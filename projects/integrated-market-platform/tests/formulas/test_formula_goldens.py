"""Closed-form golden tests for pre-trade formula hardening (no QuantLib)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cross_lane.fusion import fuse_opportunity_v1  # noqa: E402
from market_platform_foundation.cross_lane.opportunity import (  # noqa: E402
    CostInput,
    FuturesInput,
    LiquidityInput,
    PayoffInput,
    ProbabilityInput,
)
from market_platform_foundation.donor_patterns.cvd_formulas import ofi_events  # noqa: E402
from market_platform_foundation.options.edge import (  # noqa: E402
    DIRECTIONAL_EDGE_BASELINE,
    compare_physical_vs_risk_neutral,
    estimate_execution_friction,
)
from market_platform_foundation.options.flow import (  # noqa: E402
    FLOW_VERSION,
    aggregate_signed_flow,
)
from market_platform_foundation.options import flow as options_flow  # noqa: E402
from market_platform_foundation.options.greeks import bsm_greeks  # noqa: E402
from market_platform_foundation.options.iv import bsm_price, implied_volatility  # noqa: E402
from market_platform_foundation.options.risk_neutral import MODEL_VERSION  # noqa: E402
from market_platform_foundation.order_flow.ofi import compute_bbo_ofi, usable_ofi_value  # noqa: E402
from market_platform_foundation.research.baseline_naive import NaiveLastValueModel  # noqa: E402
from market_platform_foundation.research.distribution.ewma import ewma_variance  # noqa: E402
from market_platform_foundation.research.forecast import (  # noqa: E402
    build_forecast,
    verify_forecast_interface,
)
from market_platform_foundation.strategy.evaluation import (  # noqa: E402
    default_forecast_momentum_spec,
    default_whale_contrarian_spec,
)
from market_platform_foundation.strategy.interpretation import interpret_strategy  # noqa: E402
from market_platform_foundation.strategy.preregistration import build_preregistration  # noqa: E402
from market_platform_foundation.strategy.strategy_spec import CAPABILITY_CLASS_BASELINE_ONLY  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "formulas"


class RiskNeutralNamingTests(unittest.TestCase):
    def test_q_version_is_log_normal_moment_approx(self) -> None:
        self.assertEqual(MODEL_VERSION, "risk_neutral_log_normal_moment_approx_v1")
        self.assertNotIn("breeden", MODEL_VERSION.lower())


class DirectionalEdgeBaselineTests(unittest.TestCase):
    def test_p_minus_q_stamped_vs_zero_drift(self) -> None:
        physical = {
            "confidence": "LOW",
            "vol_forecast_annualized": 0.3,
            "horizons": [
                {
                    "mean_return": 0.0,
                    "variance": 0.04,
                    "upside_tail_probability": 0.1,
                    "downside_tail_probability": 0.06,
                    "skew": 0.0,
                }
            ],
        }
        q = {
            "available": True,
            "confidence": "LOW",
            "vol_implied_annualized": 0.35,
            "horizons": [
                {
                    "mean_return": 0.01,
                    "variance": 0.05,
                    "upside_tail_probability": 0.07,
                    "downside_tail_probability": 0.08,
                    "skew": 0.0,
                }
            ],
        }
        result = compare_physical_vs_risk_neutral(physical, q)
        self.assertTrue(result["available"])
        self.assertEqual(
            result["components"]["directional_edge_baseline"],
            DIRECTIONAL_EDGE_BASELINE,
        )
        self.assertEqual(DIRECTIONAL_EDGE_BASELINE, "vs_zero_drift_baseline")


class OptionsFrictionFailClosedTests(unittest.TestCase):
    def test_missing_underlying_assumption_fails_closed(self) -> None:
        friction = estimate_execution_friction([{"bid": 1.80, "ask": 1.85}])
        self.assertFalse(friction.get("executable_available"))
        self.assertEqual(friction.get("reason"), "UNDERLYING_PRICE_ASSUMPTION_MISSING")

    def test_inferred_underlying_from_activity(self) -> None:
        friction = estimate_execution_friction(
            [{"bid": 1.80, "ask": 1.85, "underlying_price": 50.0}]
        )
        self.assertTrue(friction.get("executable_available"))
        self.assertAlmostEqual(friction["commission_return_equiv"], 0.65 / 50.0, places=8)


class OptionsO5SpotFailClosedTests(unittest.TestCase):
    def test_quote_only_activities_fail_greeks_closed(self) -> None:
        self.assertEqual(FLOW_VERSION, "options_signed_flow_v3")
        self.assertFalse(hasattr(options_flow, "DEFAULT_SPOT"))
        self.assertFalse(hasattr(options_flow, "DEFAULT_VOL"))
        self.assertFalse(hasattr(options_flow, "DEFAULT_RATE"))
        aggregate = aggregate_signed_flow(
            [
                {
                    "bid": 1.80,
                    "ask": 1.85,
                    "flow_side": "buy",
                    "open_close": "open",
                    "option_type": "call",
                    "strike": 130.0,
                    "size": 100,
                }
            ]
        )
        self.assertFalse(aggregate["greeks_flow_available"])
        self.assertEqual(aggregate["reason"], "UNDERLYING_PRICE_ASSUMPTION_MISSING")
        self.assertIsNone(aggregate["net_delta_flow"])

    def test_spot_without_vol_or_rate_fails_greeks_closed(self) -> None:
        aggregate = aggregate_signed_flow(
            [
                {
                    "flow_side": "buy",
                    "open_close": "open",
                    "option_type": "call",
                    "strike": 130.0,
                    "size": 100,
                    "underlying_price": 128.0,
                }
            ]
        )
        self.assertFalse(aggregate["greeks_flow_available"])
        self.assertEqual(aggregate["reason"], "BSM_VOL_OR_RATE_ASSUMPTION_MISSING")
        self.assertIsNone(aggregate["net_delta_flow"])

    def test_inferred_spot_greeks_differ_from_legacy_default_100(self) -> None:
        row = {
            "flow_side": "buy",
            "open_close": "open",
            "option_type": "call",
            "strike": 130.0,
            "size": 100,
            "underlying_price": 128.0,
            "provider_iv": 0.42,
            "rate": 0.04,
        }
        inferred = aggregate_signed_flow([row])
        at_100 = aggregate_signed_flow(
            [{k: v for k, v in row.items() if k != "underlying_price"}],
            spot=100.0,
        )
        self.assertTrue(inferred["greeks_flow_available"])
        self.assertTrue(at_100["greeks_flow_available"])
        self.assertNotAlmostEqual(inferred["net_delta_flow"], at_100["net_delta_flow"], places=4)

    def test_fixture_iv_greeks_differ_from_silent_default_vol(self) -> None:
        self.assertFalse(hasattr(options_flow, "DEFAULT_VOL"))
        row = {
            "flow_side": "buy",
            "open_close": "open",
            "option_type": "call",
            "strike": 130.0,
            "size": 100,
            "underlying_price": 128.0,
            "provider_iv": 0.42,
            "rate": 0.04,
        }
        at_tape_iv = aggregate_signed_flow([row])
        at_silent_vol = aggregate_signed_flow([row], vol=0.35)
        self.assertTrue(at_tape_iv["greeks_flow_available"])
        self.assertNotAlmostEqual(0.42, 0.35, places=4)
        self.assertNotAlmostEqual(at_tape_iv["net_delta_flow"], at_silent_vol["net_delta_flow"], places=4)


class OptionsRateFailClosedTests(unittest.TestCase):
    def test_dealer_surface_q_have_no_silent_rate(self) -> None:
        from market_platform_foundation.options import dealer as options_dealer
        from market_platform_foundation.options import risk_neutral as options_q
        from market_platform_foundation.options import surface as options_surface
        from market_platform_foundation.options.dealer import (
            BSM_VOL_OR_RATE_ASSUMPTION_MISSING,
            DEALER_VERSION,
            estimate_contract_dealer_greeks,
        )
        from market_platform_foundation.options.risk_neutral import (
            RATE_ASSUMPTION_MISSING,
            infer_risk_neutral_distribution,
        )
        from market_platform_foundation.options.surface import (
            SURFACE_VERSION,
            build_volatility_surface,
        )

        self.assertFalse(hasattr(options_dealer, "DEFAULT_RATE"))
        self.assertFalse(hasattr(options_surface, "DEFAULT_RATE"))
        self.assertFalse(hasattr(options_q, "DEFAULT_RATE"))
        self.assertEqual(DEALER_VERSION, "options_dealer_proxy_v2")
        self.assertEqual(SURFACE_VERSION, "sigma_kt_v3")
        self.assertEqual(BSM_VOL_OR_RATE_ASSUMPTION_MISSING, "BSM_VOL_OR_RATE_ASSUMPTION_MISSING")
        self.assertEqual(RATE_ASSUMPTION_MISSING, "RATE_ASSUMPTION_MISSING")

        quote_spot = {
            "bid": 1.80,
            "ask": 1.85,
            "event_time": "2026-07-21T19:45:00.000000000Z",
            "expiry": "2026-08-15",
            "option_type": "call",
            "strike": 130.0,
            "open_interest": 100,
            "underlying_price": 132.0,
        }
        dealer = estimate_contract_dealer_greeks(quote_spot)
        self.assertFalse(dealer["available"])
        self.assertEqual(dealer["reason"], BSM_VOL_OR_RATE_ASSUMPTION_MISSING)
        surface = build_volatility_surface([quote_spot])
        self.assertEqual(surface["point_count"], 0)
        q = infer_risk_neutral_distribution(
            {
                "point_count": 2,
                "surface_version": SURFACE_VERSION,
                "points": [
                    {
                        "strike": 130.0,
                        "expiration": "2026-08-15",
                        "dte": 25,
                        "call_put": "call",
                        "sigma": 0.30,
                        "underlying_price": 132.0,
                    },
                    {
                        "strike": 135.0,
                        "expiration": "2026-08-15",
                        "dte": 25,
                        "call_put": "call",
                        "sigma": 0.32,
                        "underlying_price": 132.0,
                    },
                ],
            }
        )
        self.assertFalse(q.get("available"))
        self.assertEqual(q.get("reason"), RATE_ASSUMPTION_MISSING)


class EwmaGoldenTests(unittest.TestCase):
    def test_lambda_094_closed_form(self) -> None:
        payload = json.loads((FIXTURES / "ewma_lambda_094.json").read_text(encoding="utf-8"))
        returns = payload["returns"]
        expected_path = payload["variance_path"]
        running: list[float] = []
        for index in range(len(returns)):
            variance = ewma_variance(returns[: index + 1], lambda_=payload["lambda"])
            self.assertIsNotNone(variance)
            running.append(variance)  # type: ignore[arg-type]
            self.assertAlmostEqual(variance, expected_path[index], places=10)


class CsOfiGoldenTests(unittest.TestCase):
    def test_synthetic_tape_matches_hand_e_t(self) -> None:
        payload = json.loads((FIXTURES / "cs_ofi_synthetic_tape.json").read_text(encoding="utf-8"))
        snapshots = payload["snapshots"]
        for row in payload["transitions"]:
            prev_s = snapshots[row["from"]]
            curr_s = snapshots[row["to"]]
            events = ofi_events(
                [prev_s["bids"][0]["price"], curr_s["bids"][0]["price"]],
                [prev_s["asks"][0]["price"], curr_s["asks"][0]["price"]],
                [prev_s["bids"][0]["size"], curr_s["bids"][0]["size"]],
                [prev_s["asks"][0]["size"], curr_s["asks"][0]["size"]],
            )
            self.assertAlmostEqual(events[-1], row["hand_e_t"], places=6)
            ofi = compute_bbo_ofi(prev_s, curr_s)
            self.assertTrue(ofi.book_state_valid)
            self.assertAlmostEqual(ofi.value, row["hand_e_t"], places=4)
            self.assertEqual(usable_ofi_value(ofi), ofi.value)


class BsmGoldenTests(unittest.TestCase):
    def test_iv_round_trip_and_day_count(self) -> None:
        payload = json.loads((FIXTURES / "bsm_iv_greeks.json").read_text(encoding="utf-8"))
        call = bsm_price(
            payload["spot"],
            payload["strike"],
            payload["time_years"],
            payload["rate"],
            payload["sigma"],
            "call",
        )
        put = bsm_price(
            payload["spot"],
            payload["strike"],
            payload["time_years"],
            payload["rate"],
            payload["sigma"],
            "put",
        )
        self.assertAlmostEqual(call, payload["call_price"], places=6)
        self.assertAlmostEqual(put, payload["put_price"], places=6)
        call_iv = implied_volatility(
            call,
            payload["spot"],
            payload["strike"],
            payload["time_years"],
            payload["rate"],
            "call",
        )
        put_iv = implied_volatility(
            put,
            payload["spot"],
            payload["strike"],
            payload["time_years"],
            payload["rate"],
            "put",
        )
        self.assertIsNotNone(call_iv)
        self.assertIsNotNone(put_iv)
        assert call_iv is not None and put_iv is not None
        self.assertAlmostEqual(call_iv, payload["sigma"], delta=payload["iv_tolerance"])
        self.assertAlmostEqual(put_iv, payload["sigma"], delta=payload["iv_tolerance"])
        greeks = bsm_greeks(
            payload["spot"],
            payload["strike"],
            payload["time_years"],
            payload["rate"],
            payload["sigma"],
            "call",
        )
        self.assertAlmostEqual(greeks["delta"], payload["call_delta"], delta=payload["greeks_tolerance"])
        self.assertAlmostEqual(greeks["gamma"], payload["gamma"], delta=payload["greeks_tolerance"])
        self.assertAlmostEqual(
            greeks["vega"], payload["vega_per_vol_point"], delta=payload["greeks_tolerance"]
        )
        self.assertAlmostEqual(
            greeks["theta"], payload["call_theta_calendar_365"], delta=payload["greeks_tolerance"]
        )
        theta_252 = payload["call_theta_calendar_365"] * (365.0 / 252.0)
        self.assertAlmostEqual(theta_252, payload["call_theta_trading_252"], places=6)
        self.assertNotAlmostEqual(
            payload["call_theta_calendar_365"],
            payload["call_theta_trading_252"],
            places=4,
        )


class FusionProductGoldenTests(unittest.TestCase):
    def test_gross_friction_product_and_outcomes(self) -> None:
        payload = json.loads((FIXTURES / "fusion_product_v1.json").read_text(encoding="utf-8"))
        ranked = payload["ranked"]
        fused = fuse_opportunity_v1(
            ProbabilityInput(available=True),
            PayoffInput(
                available=True,
                expected_pnl=ranked["expected_pnl"],
                net_expected_pnl=ranked["net_expected_pnl"],
                template="long_straddle",
            ),
            CostInput(available=True, friction_cost=ranked["friction_cost"]),
            LiquidityInput(available=True, gates_passed=True, cvd_confidence=ranked["cvd_confidence"]),
        )
        self.assertEqual(fused["outcome"], ranked["outcome"])
        self.assertAlmostEqual(fused["fused_net_ev"], ranked["fused_net_ev"], places=6)
        self.assertAlmostEqual(
            fused["fusion"]["gross_ev_before_weights"],
            ranked["expected_pnl"] - ranked["friction_cost"],
            places=6,
        )

        unavailable = fuse_opportunity_v1(
            ProbabilityInput(available=False),
            PayoffInput(available=False, reason="PAYOFF_UNAVAILABLE"),
            CostInput(available=False),
            LiquidityInput(available=True, gates_passed=True),
        )
        self.assertEqual(unavailable["outcome"], "UNAVAILABLE")

        blocked = fuse_opportunity_v1(
            ProbabilityInput(available=True),
            PayoffInput(available=True, expected_pnl=100.0, template="long_straddle"),
            CostInput(available=True, friction_cost=1.0),
            LiquidityInput(available=True, gates_passed=False),
        )
        self.assertEqual(blocked["reason"], "LIQUIDITY_BLOCKED")

        non_pos = payload["non_positive"]
        negative = fuse_opportunity_v1(
            ProbabilityInput(available=True),
            PayoffInput(available=True, expected_pnl=non_pos["expected_pnl"], template="long_straddle"),
            CostInput(available=True, friction_cost=non_pos["friction_cost"]),
            LiquidityInput(available=True, gates_passed=True),
        )
        self.assertEqual(negative["outcome"], non_pos["outcome"])
        self.assertEqual(negative["reason"], non_pos["reason"])

        scaled = payload["futures_scaled"]
        with_futures = fuse_opportunity_v1(
            ProbabilityInput(available=True),
            PayoffInput(available=True, expected_pnl=scaled["expected_pnl"], template="long_straddle"),
            CostInput(available=True, friction_cost=scaled["friction_cost"]),
            LiquidityInput(available=True, gates_passed=True, cvd_confidence=1.0),
            FuturesInput(
                available=True,
                leverage_stress_regime=scaled["leverage_stress_regime"],
                trend_regime=scaled["trend_regime"],
            ),
        )
        self.assertAlmostEqual(with_futures["futures_regime_factor"], scaled["futures_regime_factor"], places=6)
        self.assertAlmostEqual(with_futures["fused_net_ev"], scaled["fused_net_ev"], places=6)


class NaiveLastValueGoldenTests(unittest.TestCase):
    def test_score_equals_last_close_and_empty_training_fallback(self) -> None:
        model = NaiveLastValueModel()
        empty = model.predict(
            {"instrument_id": "EQ-1", "prediction_cutoff": 100},
            horizon_ns=60_000_000_000,
        )
        self.assertEqual(empty["status"], "fallback")
        self.assertEqual(empty["fallback_reason_code"], "FCAST_NO_TRAINING_OBSERVATION")
        model.fit([{"instrument_id": "EQ-1", "value": "137.25", "bar_close": "137.25"}])
        forecast = model.predict(
            {"instrument_id": "EQ-1", "prediction_cutoff": 200},
            horizon_ns=60_000_000_000,
        )
        self.assertEqual(forecast["score"], "137.25")
        status, _ = verify_forecast_interface(forecast)
        self.assertEqual(status, "PASS")

    def test_strategy_metadata_is_baseline_only(self) -> None:
        spec = default_forecast_momentum_spec()
        self.assertEqual(spec["capability_class"], CAPABILITY_CLASS_BASELINE_ONLY)
        whale = default_whale_contrarian_spec()
        self.assertEqual(whale["capability_class"], CAPABILITY_CLASS_BASELINE_ONLY)


class WhaleContrarianGoldenTests(unittest.TestCase):
    def test_flips_long_to_short_when_institutional_present(self) -> None:
        spec = default_whale_contrarian_spec()
        prereg = build_preregistration(spec, registered_at="2026-08-16T00:00:00.000000000Z")
        forecast = build_forecast(score="1.0", prediction_cutoff=100, horizon_ns=60_000_000_000)
        fcast_status, _ = verify_forecast_interface(forecast)
        with patch(
            "market_platform_foundation.strategy.interpretation.query_all_institutional",
            return_value=[{"status": "available", "family": "order_flow"}],
        ):
            result = interpret_strategy(
                strategy_spec=spec,
                preregistration=prereg,
                forecast=forecast,
                forecast_status=fcast_status,
                prediction_cutoff=100,
                observation_time=100,
            )
        self.assertEqual(result["outcome"], "signal")
        self.assertEqual(result["direction"], "short")

    def test_abstains_when_institutional_ledger_empty(self) -> None:
        spec = default_whale_contrarian_spec()
        prereg = build_preregistration(spec, registered_at="2026-08-16T00:00:00.000000000Z")
        forecast = build_forecast(score="1.0", prediction_cutoff=100, horizon_ns=60_000_000_000)
        fcast_status, _ = verify_forecast_interface(forecast)
        result = interpret_strategy(
            strategy_spec=spec,
            preregistration=prereg,
            forecast=forecast,
            forecast_status=fcast_status,
            prediction_cutoff=100,
            observation_time=100,
        )
        self.assertEqual(result["outcome"], "abstention")
        self.assertIn("ABSTAIN_INSTITUTIONAL_UNAVAILABLE", result["abstention_reason_codes"])


if __name__ == "__main__":
    unittest.main()
