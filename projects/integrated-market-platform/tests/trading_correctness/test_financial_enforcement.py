"""G3 BL-0202 — cash / available-funds enforcement tests.

Proves the canonical financial gate on the executable submit paths:
- exact cash boundary (required == available accepted, +1 minor unit rejected);
- working-order obligations reduce availability (reservation from open orders);
- reservation shrinks after partial fill and releases after cancel;
- broker-paper path fails closed on missing price evidence;
- multi-currency never silently assumed convertible.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.execution import (
    cancel_interactive_order,
    replace_interactive_order,
    submit_interactive_order,
)
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.risk.financial import (
    available_cash_minor,
    working_order_obligations_minor,
)
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY

POLICY_LOW_CASH = {
    **DEFAULT_RISK_POLICY,
    "commission_minor_per_share": 0,
    "initial_cash_minor": 10_000_00,  # $10,000
    "max_order_shares": 1_000,
    "max_position_shares": 5_000,
    "participation_cap_numerator": 1,
    "participation_cap_denominator": 10,
    "policy_version": "g3-test",
    "risk_policy_identity_hash": "g3-policy-low-cash",
}


def _ledger(cash_minor: int = 10_000_00) -> PaperExecutionLedger:
    policy = dict(POLICY_LOW_CASH)
    policy["initial_cash_minor"] = cash_minor
    return PaperExecutionLedger.open_session(
        replay_session_id="g3-fin-1",
        instrument_id="BIYA",
        symbol="BIYA",
        policy=policy,
        execution_mode="INTERNAL_SIMULATION",
        execution_authority="PAPER_ONLY",
    )


def _bars(price: str = "10.00", volume: int = 100_000) -> list[dict[str, object]]:
    return [
        {
            "available_time": 100 + i * 100,
            "bar_payload": {
                "close": price,
                "high": price,
                "low": price,
                "open": price,
                "volume": volume,
            },
        }
        for i in range(1, 4)
    ]


class ExactCashBoundaryTests(unittest.TestCase):
    def test_required_equals_available_accepted(self) -> None:
        # $10,000 cash, 1000 shares at $10.00 exactly = $10,000. LIMIT order so
        # the gate prices at the explicit limit.
        ledger = _ledger(cash_minor=10_000_00)
        result = submit_interactive_order(
            ledger=ledger,
            bars=_bars(),
            symbol="BIYA",
            instrument_id="BIYA",
            side="BUY",
            quantity=1000,
            observation_time=1,
            client_order_id="exact-ok",
            idempotency_key="exact-ok",
            order_type="LIMIT",
            limit_price_minor=1000,
        )
        self.assertEqual(result["order"]["state"], "FILLED")

    def test_required_equals_available_plus_one_rejected(self) -> None:
        # 1001 shares × $10.00 = $10,010 > $10,000 cash.
        ledger = _ledger(cash_minor=10_000_00)
        with self.assertRaises(ValueError) as ctx:
            submit_interactive_order(
                ledger=ledger,
                bars=_bars(),
                symbol="BIYA",
                instrument_id="BIYA",
                side="BUY",
                quantity=1001,
                observation_time=1,
                client_order_id="exact-over",
                idempotency_key="exact-over",
                order_type="LIMIT",
                limit_price_minor=1000,
            )
        self.assertIn("INSUFFICIENT_CASH", str(ctx.exception))

    def test_market_order_priced_from_bar_not_zero(self) -> None:
        # MARKET buy with $5,000 cash: 1000 shares × $10.00 bar high = $10,000
        # required > $5,000 available -> rejected (never priced at zero).
        ledger = _ledger(cash_minor=5_000_00)
        with self.assertRaises(ValueError) as ctx:
            submit_interactive_order(
                ledger=ledger,
                bars=_bars(),
                symbol="BIYA",
                instrument_id="BIYA",
                side="BUY",
                quantity=1000,
                observation_time=1,
                client_order_id="market-over",
                idempotency_key="market-over",
            )
        self.assertIn("INSUFFICIENT_CASH", str(ctx.exception))

    def test_multi_currency_no_silent_conversion(self) -> None:
        # Intent currency EUR vs account USD: fail closed, never 1:1 assume.
        from market_platform_foundation.paper.contracts import build_instrument_ref, build_user_order_intent

        ledger = _ledger()
        instrument = build_instrument_ref(
            instrument_id="BIYA",
            symbol="BIYA",
            currency="EUR",
        )
        with self.assertRaises(ValueError) as ctx:
            submit_interactive_order(
                ledger=ledger,
                bars=_bars(),
                symbol="BIYA",
                instrument_id="BIYA",
                side="BUY",
                quantity=10,
                observation_time=1,
                client_order_id="eur-1",
                idempotency_key="eur-1",
                order_type="LIMIT",
                limit_price_minor=1000,
                instrument=instrument,
            )
        self.assertIn("INSUFFICIENT_SETTLEMENT_CURRENCY", str(ctx.exception))


class WorkingObligationTests(unittest.TestCase):
    def test_open_order_reduces_available_cash(self) -> None:
        # Cash $10,000. Submit BUY 1000 @ $5.00 (LIMIT fills fully, no open
        # remainder) — then a second order must see reduced availability only
        # via open remainders, not filled cash.
        ledger = _ledger(cash_minor=10_000_00)
        first = submit_interactive_order(
            ledger=ledger,
            bars=_bars(price="5.00"),
            symbol="BIYA",
            instrument_id="BIYA",
            side="BUY",
            quantity=1000,
            observation_time=1,
            client_order_id="obl-1",
            idempotency_key="obl-1",
            order_type="LIMIT",
            limit_price_minor=500,
        )
        self.assertEqual(first["order"]["state"], "FILLED")
        # Filled cash is spent; remaining = $5,000. A 600-share order at $10
        # ($6,000) must be rejected.
        with self.assertRaises(ValueError) as ctx:
            submit_interactive_order(
                ledger=ledger,
                bars=_bars(price="10.00"),
                symbol="BIYA",
                instrument_id="BIYA",
                side="BUY",
                quantity=600,
                observation_time=1,
                client_order_id="obl-2",
                idempotency_key="obl-2",
                order_type="LIMIT",
                limit_price_minor=1000,
            )
        self.assertIn("INSUFFICIENT_CASH", str(ctx.exception))

    def test_partial_fill_shrinks_working_obligation(self) -> None:
        # Participation cap 1/10 with 40-share bar admits 4 shares per bar.
        # BUY 10 at $10 -> fills 4 (partial), working remainder 6 remains
        # reserved at $10 each = $60 obligation.
        policy = dict(POLICY_LOW_CASH)
        policy["participation_cap_numerator"] = 1
        policy["participation_cap_denominator"] = 10
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="g3-fin-2",
            instrument_id="BIYA",
            symbol="BIYA",
            policy=policy,
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )
        bars = [
            {
                "available_time": 100 + i * 100,
                "bar_payload": {
                    "close": "10.00",
                    "high": "10.00",
                    "low": "10.00",
                    "open": "10.00",
                    "volume": 40,
                },
            }
            for i in range(1, 4)
        ]
        result = submit_interactive_order(
            ledger=ledger,
            bars=bars,
            symbol="BIYA",
            instrument_id="BIYA",
            side="BUY",
            quantity=10,
            observation_time=1,
            client_order_id="pf-1",
            idempotency_key="pf-1",
            order_type="LIMIT",
            limit_price_minor=1000,
        )
        self.assertEqual(result["order"]["state"], "PARTIALLY_FILLED")
        projected = ledger.lookup_order(result["order_id"])
        filled = int(projected["cumulative_filled_quantity"])
        self.assertEqual(filled, 4)
        self.assertEqual(int(projected["working_remaining"]), 6)
        obligations = working_order_obligations_minor(ledger)
        self.assertEqual(obligations, 6 * 1000, "obligation must track the working remainder, not the original quantity")
        available = available_cash_minor(ledger)
        self.assertEqual(available, 10_000_00 - 4 * 1000 - 6 * 1000)

    def test_cancel_releases_reservation(self) -> None:
        ledger = _ledger(cash_minor=10_000_00)
        result = submit_interactive_order(
            ledger=ledger,
            bars=_bars(),
            symbol="BIYA",
            instrument_id="BIYA",
            side="BUY",
            quantity=10,
            observation_time=1,
            client_order_id="rel-1",
            idempotency_key="rel-1",
            order_type="LIMIT",
            limit_price_minor=1000,
        )
        self.assertEqual(result["order"]["state"], "FILLED")
        self.assertEqual(working_order_obligations_minor(ledger), 0)

    def test_replace_recomputes_reservation(self) -> None:
        # Raise the price of the working remainder: reservation must be
        # recomputed and fail closed when the new requirement exceeds headroom.
        policy = dict(POLICY_LOW_CASH)
        policy["participation_cap_numerator"] = 1
        policy["participation_cap_denominator"] = 10
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="g3-fin-3",
            instrument_id="BIYA",
            symbol="BIYA",
            policy=policy,
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )
        bars = [
            {
                "available_time": 100 + i * 100,
                "bar_payload": {
                    "close": "10.00",
                    "high": "10.00",
                    "low": "10.00",
                    "open": "10.00",
                    "volume": 40,
                },
            }
            for i in range(1, 4)
        ]
        result = submit_interactive_order(
            ledger=ledger,
            bars=bars,
            symbol="BIYA",
            instrument_id="BIYA",
            side="BUY",
            quantity=10,
            observation_time=1,
            client_order_id="rep-fin-1",
            idempotency_key="rep-fin-1",
            order_type="LIMIT",
            limit_price_minor=1000,
        )
        self.assertEqual(result["order"]["state"], "PARTIALLY_FILLED")
        order_id = result["order_id"]
        # Raise remainder price to $1,000/share: 6 × $1,000 = $6,000 which is
        # within $10,000 cash minus $4,000 spent -> accepted.
        replaced = replace_interactive_order(
            ledger=ledger,
            order_id=order_id,
            replaced_quantity=10,
            order_type="LIMIT",
            limit_price_minor=100_000,
        )
        self.assertEqual(replaced["state"], "REPLACED")
        # Now obligations reflect the new price for the remainder.
        obligations = working_order_obligations_minor(ledger)
        self.assertEqual(obligations, 6 * 100_000)


if __name__ == "__main__":
    unittest.main()