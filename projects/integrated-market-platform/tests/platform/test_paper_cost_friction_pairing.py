"""Fail-closed Paper cost/friction and Alpaca paper-host pairing honesty.

Does not invent fills. Does not declare CALIBRATED. Live Alpaca is forbidden.
Does not edit the #87 calibration runner/harness files.
"""

from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.paper_forward_bridge.paper_handoff import (  # noqa: E402
    forward_test_correlation_id,
)
from market_platform_foundation.paper.calibration.comparator_contract import (  # noqa: E402
    ComparatorContractError,
    validate_comparator_binding,
)
from market_platform_foundation.paper.calibration.metrics import (  # noqa: E402
    FillObservation,
    SampleHonesty,
    compute_calibration_metric_report,
)
from market_platform_foundation.paper.calibration.pairing import (  # noqa: E402
    pair_imp_and_comparator,
)
from market_platform_foundation.paper.cost_friction import (  # noqa: E402
    COST_FRICTION_UNSET,
    PaperCostFrictionUnset,
    resolve_paper_cost_friction,
)
from market_platform_foundation.portfolio.canonical import (  # noqa: E402
    CanonicalPortfolio,
    CashBalance,
    PortfolioKey,
)
from market_platform_foundation.portfolio.paper_fill import (  # noqa: E402
    apply_paper_fill_to_portfolio,
)
from market_platform_foundation.providers.adapters.alpaca_paper_http import (  # noqa: E402
    ALPACA_PAPER_ORIGIN,
)


def _fill(*, order_id: str, **kwargs) -> FillObservation:
    return FillObservation(order_id=order_id, filled=True, **kwargs)


class PaperCostFrictionTests(unittest.TestCase):
    def test_missing_policy_and_fill_costs_fail_closed(self) -> None:
        with self.assertRaises(PaperCostFrictionUnset) as ctx:
            resolve_paper_cost_friction(
                fill={"fill_quantity": 2},
                policy={"price_scale": 100},
                quantity=2,
            )
        self.assertEqual(str(ctx.exception), COST_FRICTION_UNSET)

    def test_partial_fill_stamp_fails_closed(self) -> None:
        with self.assertRaises(PaperCostFrictionUnset):
            resolve_paper_cost_friction(
                fill={"commission_minor": 1},
                policy={
                    "commission_minor_per_share": 0,
                    "fee_minor_per_order": 0,
                },
                quantity=1,
            )

    def test_explicit_zero_policy_is_declared_not_invented(self) -> None:
        commission, fees = resolve_paper_cost_friction(
            fill={"fill_quantity": 3},
            policy={
                "commission_minor_per_share": 0,
                "fee_minor_per_order": 0,
            },
            quantity=3,
        )
        self.assertEqual(commission, 0)
        self.assertEqual(fees, 0)

    def test_paper_fill_does_not_silent_zero_missing_costs(self) -> None:
        portfolio = CanonicalPortfolio(PortfolioKey(account_id="a", mode="PAPER"))
        portfolio.set_cash(CashBalance(currency="USD", settled=Decimal("10000")))
        with self.assertRaises(PaperCostFrictionUnset):
            apply_paper_fill_to_portfolio(
                portfolio,
                fill={
                    "fill_id": "f-unset",
                    "instrument_id": "AAPL",
                    "direction": "long",
                    "fill_quantity": 1,
                    "fill_price_minor": 10000,
                },
                policy={"price_scale": 100, "currency": "USD"},
            )

    def test_missing_cost_fields_are_not_observable_zero(self) -> None:
        correlation = forward_test_correlation_id("ftd-cost-1")
        report = compute_calibration_metric_report(
            imp_fills=[_fill(order_id="imp-1", correlation_id=correlation, fill_price=100.0)],
            comparator_fills=[
                _fill(order_id="ap-1", correlation_id=correlation, fill_price=100.1)
            ],
        )
        self.assertEqual(report.cost_friction_honesty, SampleHonesty.NOT_OBSERVABLE)
        self.assertIsNone(report.cost_friction_delta_minor)
        self.assertFalse(report.calibrated)

    def test_declared_zero_costs_are_observable(self) -> None:
        correlation = forward_test_correlation_id("ftd-cost-1")
        report = compute_calibration_metric_report(
            imp_fills=[
                _fill(
                    order_id="imp-1",
                    correlation_id=correlation,
                    commission_minor=0,
                    fees_minor=0,
                )
            ],
            comparator_fills=[
                _fill(
                    order_id="ap-1",
                    correlation_id=correlation,
                    commission_minor=0,
                    fees_minor=0,
                )
            ],
            minimum_n=1,
        )
        self.assertEqual(report.cost_friction_honesty, SampleHonesty.SAMPLE_MET_NARROW)
        self.assertEqual(report.cost_friction_delta_minor, 0)


class AlpacaPaperHostPairingTests(unittest.TestCase):
    def test_alpaca_binding_requires_paper_host(self) -> None:
        with self.assertRaises(ComparatorContractError) as ctx:
            validate_comparator_binding(
                {
                    "comparator_id": "alpaca.paper",
                    "environment": "paper",
                    "account_mode": "paper",
                    "limitations": ["equity_only"],
                }
            )
        self.assertEqual(str(ctx.exception), "COMPARATOR_ALPACA_PAPER_HOST_REQUIRED")

    def test_alpaca_binding_rejects_non_paper_host(self) -> None:
        with self.assertRaises(ComparatorContractError) as ctx:
            validate_comparator_binding(
                {
                    "comparator_id": "alpaca.paper",
                    "environment": "https://sandbox.tradier.com/v1",
                    "account_mode": "paper",
                    "limitations": ["equity_only"],
                }
            )
        self.assertEqual(str(ctx.exception), "COMPARATOR_ALPACA_PAPER_HOST_REQUIRED")

    def test_alpaca_live_host_forbidden(self) -> None:
        with self.assertRaises(ComparatorContractError) as ctx:
            validate_comparator_binding(
                {
                    "comparator_id": "alpaca.paper",
                    "environment": "https://api.alpaca.markets",
                    "account_mode": "paper",
                    "limitations": ["equity_only"],
                }
            )
        self.assertEqual(str(ctx.exception), "COMPARATOR_LIVE_HOST_FORBIDDEN")

    def test_alpaca_paper_host_binding_accepted(self) -> None:
        binding = validate_comparator_binding(
            {
                "comparator_id": "alpaca.paper",
                "environment": ALPACA_PAPER_ORIGIN,
                "account_mode": "paper",
                "limitations": ["equity_only", "alpaca_paper_host"],
            }
        )
        self.assertEqual(binding.environment, ALPACA_PAPER_ORIGIN)
        self.assertFalse(binding.is_market_truth)

    def test_pairing_live_alpaca_host_does_not_invent_fills(self) -> None:
        correlation = forward_test_correlation_id("ftd-cost-1")
        with self.assertRaises(ComparatorContractError) as ctx:
            pair_imp_and_comparator(
                forward_test_id="ftd-cost-1",
                imp_fills=[_fill(order_id="imp-1", correlation_id=correlation)],
                comparator_fills=[_fill(order_id="live-1", correlation_id=correlation)],
                comparator_id="alpaca.paper",
                comparator_environment="https://api.alpaca.markets",
            )
        self.assertEqual(str(ctx.exception), "COMPARATOR_LIVE_HOST_FORBIDDEN")

    def test_pairing_paper_host_joins_existing_fills_only(self) -> None:
        correlation = forward_test_correlation_id("ftd-cost-1")
        result = pair_imp_and_comparator(
            forward_test_id="ftd-cost-1",
            imp_fills=[_fill(order_id="imp-1", correlation_id=correlation, fill_price=10.0)],
            comparator_fills=[
                _fill(order_id="ap-1", correlation_id=correlation, fill_price=10.1)
            ],
            comparator_id="alpaca.paper",
            comparator_environment=ALPACA_PAPER_ORIGIN,
        )
        self.assertEqual(result.pair_count, 1)
        self.assertEqual(len(result.unpaired_imp), 0)
        self.assertEqual(len(result.unpaired_comparator), 0)


if __name__ == "__main__":
    unittest.main()
