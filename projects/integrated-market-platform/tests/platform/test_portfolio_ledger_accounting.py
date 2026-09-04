"""Focused regression tests for authoritative fill accounting."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from market_platform_foundation.intelligence.outcomes.scheduler import OutcomeSettlementScheduler
from market_platform_foundation.intelligence.outcomes.types import SettlementStatus
from market_platform_foundation.portfolio.attribution import (
    AttributionFillV1,
    compute_slice_realized_pnl,
)
from market_platform_foundation.portfolio.ledger import apply_fill, build_ledger_state


POLICY = {
    "commission_minor_per_share": 0,
    "fee_minor_per_order": 0,
}


def _fill(fill_id: str, *, direction: str, quantity: int, price_minor: int) -> dict[str, object]:
    return {
        "direction": direction,
        "fill_id": fill_id,
        "fill_price_minor": price_minor,
        "fill_quantity": quantity,
    }


def _apply(*fills: dict[str, object]) -> dict[str, object]:
    state: dict[str, object] = build_ledger_state(initial_cash_minor=1_000_000)
    for fill in fills:
        state = apply_fill(state, fill=fill, policy=POLICY)
    return state


class _EmptyOutcomeRepository:
    def get_outcomes_by_forecast(self, forecast_id: str) -> tuple[object, ...]:
        return ()


class PortfolioLedgerAccountingTests(unittest.TestCase):
    def test_long_close_uses_opening_cost_basis(self) -> None:
        state = _apply(
            _fill("buy", direction="long", quantity=10, price_minor=100),
            _fill("sell", direction="short", quantity=10, price_minor=125),
        )

        self.assertEqual(state["position_shares"], 0)
        self.assertEqual(state["position_cost_basis_minor"], 0)
        self.assertEqual(state["realized_pnl_minor"], 250)

    def test_short_close_uses_opening_cost_basis(self) -> None:
        state = _apply(
            _fill("sell", direction="short", quantity=10, price_minor=125),
            _fill("buy", direction="long", quantity=10, price_minor=100),
        )

        self.assertEqual(state["position_shares"], 0)
        self.assertEqual(state["position_cost_basis_minor"], 0)
        self.assertEqual(state["realized_pnl_minor"], 250)

    def test_scale_in_and_scale_out_preserve_weighted_cost_basis(self) -> None:
        state = _apply(
            _fill("buy-1", direction="long", quantity=10, price_minor=100),
            _fill("buy-2", direction="long", quantity=10, price_minor=120),
            _fill("sell-1", direction="short", quantity=5, price_minor=130),
            _fill("sell-2", direction="short", quantity=15, price_minor=100),
        )

        self.assertEqual(state["position_shares"], 0)
        self.assertEqual(state["position_cost_basis_minor"], 0)
        self.assertEqual(state["realized_pnl_minor"], -50)

    def test_long_to_short_reversal_closes_then_opens_new_basis(self) -> None:
        state = _apply(
            _fill("buy", direction="long", quantity=10, price_minor=100),
            _fill("reverse", direction="short", quantity=15, price_minor=120),
        )

        self.assertEqual(state["position_shares"], -5)
        self.assertEqual(state["position_cost_basis_minor"], -600)
        self.assertEqual(state["realized_pnl_minor"], 200)

    def test_short_to_long_reversal_closes_then_opens_new_basis(self) -> None:
        state = _apply(
            _fill("sell", direction="short", quantity=10, price_minor=100),
            _fill("reverse", direction="long", quantity=15, price_minor=80),
        )

        self.assertEqual(state["position_shares"], 5)
        self.assertEqual(state["position_cost_basis_minor"], 400)
        self.assertEqual(state["realized_pnl_minor"], 200)

    def test_scheduler_reports_due_unsettled_entry(self) -> None:
        entry = SimpleNamespace(
            availability_cutoff_ns=100,
            forecast_id="forecast-1",
            ledger_entry_id="entry-1",
            mode="ACTUAL_LIVE",
            scenario_id=None,
        )

        status = OutcomeSettlementScheduler(_EmptyOutcomeRepository()).inspect(entry, now_ns=100)

        self.assertEqual(status, SettlementStatus.DUE)

    def test_authoritative_and_slice_accounting_share_explicit_fill_costs(self) -> None:
        fill = {
            "direction": "long",
            "fill_id": "costed-fill",
            "fill_price_minor": 100,
            "fill_quantity": 10,
            "commission_minor": 5,
            "fees_minor": 7,
        }
        authoritative = apply_fill(
            build_ledger_state(initial_cash_minor=1_000_000),
            fill=fill,
            policy=POLICY,
        )
        slice_outcome = compute_slice_realized_pnl(
            (
                AttributionFillV1(
                    fill_id="costed-fill",
                    fill_time_ns=100,
                    direction="LONG",
                    quantity=10,
                    price_minor=100,
                    commission_minor=5,
                    fees_minor=7,
                ),
            )
        )

        self.assertEqual(
            authoritative["realized_pnl_minor"],
            slice_outcome.realized_pnl_minor,
        )
        self.assertEqual(authoritative["total_commission_minor"], 5)
        self.assertEqual(authoritative["total_fees_minor"], 7)


if __name__ == "__main__":
    unittest.main()
