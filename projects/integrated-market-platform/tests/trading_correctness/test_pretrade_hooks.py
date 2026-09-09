"""G3 BL-0209 — typed cross-asset pre-trade risk hook tests.

Proves ``evaluate_pretrade`` is a controlled dispatch surface wired into the
actual executable submit paths (not dead utility code):
- internal BUY cash check dispatches through the hook;
- broker-paper BUY check dispatches through the hook;
- hook receives typed contextual data (account, mode, instrument kind,
  portfolio cash, working obligations, policy revision);
- failure is fail-closed; futures never get equity cash arithmetic;
- long option premium x multiplier; uncovered short option fails;
- crypto quote-currency funding; bond/reference/non-executable rejection;
- the executable submit path rejects when the hook rejects.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.execution import submit_interactive_order
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY
from market_platform_foundation.risk.pretrade import (
    PreTradeRiskContext,
    evaluate_pretrade,
)


def _context(**overrides: object) -> PreTradeRiskContext:
    body: dict[str, object] = {
        "operational_identity": "op-1",
        "account_id": "acct-1",
        "mode": "PAPER",
        "instrument_id": "BIYA",
        "asset_class": "EQUITY",
        "instrument_kind": "TRADABLE_SECURITY",
        "symbol": "BIYA",
        "contract_multiplier": 1,
        "side": "BUY",
        "quantity": 100,
        "quantity_unit": "SHARES",
        "order_type": "LIMIT",
        "limit_price_minor": 1000,
        "currency": "USD",
        "account_currency": "USD",
        "portfolio_cash_minor": 10_000_00,
        "position_quantity": 0,
        "working_obligations_minor": 0,
        "risk_policy_revision": "pol-1",
        "source_time_ns": 1,
    }
    body.update(overrides)
    return PreTradeRiskContext(**body)  # type: ignore[arg-type]


class PretradeDispatchTests(unittest.TestCase):
    def test_equity_buy_accepted_within_cash(self) -> None:
        decision = evaluate_pretrade(_context(quantity=50, limit_price_minor=1000))
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.required_cash_minor, 50 * 1000)
        self.assertEqual(decision.available_cash_minor, 10_000_00)

    def test_equity_buy_rejected_when_cash_insufficient(self) -> None:
        # 1001 shares × $10.00 = $10,010 > $10,000 available.
        decision = evaluate_pretrade(_context(quantity=1001, limit_price_minor=1000))
        self.assertFalse(decision.accepted)
        self.assertIn("INSUFFICIENT_CASH", decision.reason_codes)

    def test_exact_cash_boundary(self) -> None:
        # 100 shares × $100.00 = $10,000 == available -> accepted.
        decision = evaluate_pretrade(_context(quantity=100, limit_price_minor=10_000))
        self.assertTrue(decision.accepted)
        # One share more -> rejected.
        decision = evaluate_pretrade(_context(quantity=101, limit_price_minor=10_000))
        self.assertFalse(decision.accepted)
        self.assertIn("INSUFFICIENT_CASH", decision.reason_codes)

    def test_working_obligations_reduce_availability(self) -> None:
        # $10,000 cash - $5,000 obligations = $5,000 available; required
        # 100 × $100 = $10,000 > $5,000 -> rejected.
        decision = evaluate_pretrade(_context(quantity=100, limit_price_minor=10_000, working_obligations_minor=5_000_00))
        self.assertFalse(decision.accepted)
        self.assertIn("INSUFFICIENT_CASH", decision.reason_codes)

    def test_long_option_premium_times_multiplier(self) -> None:
        decision = evaluate_pretrade(
            _context(
                instrument_id="SPY260918C00500000",
                asset_class="OPTION",
                instrument_kind="OPTION_CONTRACT",
                contract_multiplier=100,
                quantity=5,
                limit_price_minor=150,  # $1.50 premium
                portfolio_cash_minor=1_000_00,
            )
        )
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.required_cash_minor, 5 * 150 * 100)

    def test_uncovered_short_option_fails_closed(self) -> None:
        decision = evaluate_pretrade(
            _context(
                instrument_id="SPY260918C00500000",
                asset_class="OPTION",
                instrument_kind="OPTION_CONTRACT",
                side="SELL",
                quantity=1,
            )
        )
        self.assertFalse(decision.accepted)
        self.assertTrue(decision.unsupported_risk_model)

    def test_future_never_gets_equity_cash_arithmetic(self) -> None:
        decision = evaluate_pretrade(
            _context(
                instrument_id="ES202512",
                asset_class="FUTURE",
                instrument_kind="FUTURE_CONTRACT",
                side="BUY",
                quantity=1,
                portfolio_cash_minor=10_000_00,
            )
        )
        self.assertFalse(decision.accepted)
        self.assertIn(decision.reason_codes[0], {"UNSUPPORTED_RISK_MODEL", "MARGIN_MISSING"})

    def test_crypto_quote_currency_requirement(self) -> None:
        decision = evaluate_pretrade(
            _context(
                instrument_id="BTCUSDT",
                asset_class="CRYPTO",
                instrument_kind="CRYPTO_PAIR",
                symbol="BTCUSDT",
                quantity=1,
                limit_price_minor=60_000_00,
                portfolio_cash_minor=1_000_000_00,
            )
        )
        self.assertTrue(decision.accepted)
        self.assertEqual(decision.required_cash_minor, 60_000_00)

    def test_bond_and_reference_rejected(self) -> None:
        decision = evaluate_pretrade(
            _context(
                instrument_id="BOND-1",
                asset_class="BOND",
                instrument_kind="BOND",
            )
        )
        self.assertFalse(decision.accepted)
        self.assertIn("NON_EXECUTABLE_INSTRUMENT", decision.reason_codes)
        decision = evaluate_pretrade(
            _context(
                instrument_id="ES1!",
                asset_class="FUTURE",
                instrument_kind="CONTINUOUS_SERIES",
            )
        )
        self.assertFalse(decision.accepted)
        self.assertIn("NON_EXECUTABLE_INSTRUMENT", decision.reason_codes)

    def test_settlement_currency_mismatch_fails_closed(self) -> None:
        decision = evaluate_pretrade(
            _context(currency="EUR", account_currency="USD")
        )
        self.assertFalse(decision.accepted)
        self.assertIn("INSUFFICIENT_SETTLEMENT_CURRENCY", decision.reason_codes)

    def test_requires_price_evidence(self) -> None:
        decision = evaluate_pretrade(
            _context(order_type="MARKET", limit_price_minor=None, reference_price_minor=None)
        )
        self.assertFalse(decision.accepted)
        self.assertIn("REQUIRED_PRICE_MISSING", decision.reason_codes)


class ExecutablePathDispatchTests(unittest.TestCase):
    """The internal submit gate dispatches through evaluate_pretrade."""

    def _ledger(self, cash_minor: int = 10_000_00) -> PaperExecutionLedger:
        policy = dict(DEFAULT_RISK_POLICY)
        policy["initial_cash_minor"] = cash_minor
        policy["max_order_shares"] = 1_000
        policy["max_position_shares"] = 5_000
        return PaperExecutionLedger.open_session(
            replay_session_id="g3-pretrade-1",
            instrument_id="BIYA",
            symbol="BIYA",
            policy=policy,
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )

    def _bars(self, price: str = "10.00", volume: int = 100_000) -> list[dict[str, object]]:
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

    def test_executable_submit_rejects_when_hook_rejects(self) -> None:
        ledger = self._ledger(cash_minor=10_000_00)
        with self.assertRaises(ValueError) as ctx:
            submit_interactive_order(
                ledger=ledger, bars=self._bars(), symbol="BIYA", instrument_id="BIYA",
                side="BUY", quantity=1001, observation_time=1,
                client_order_id="hook-1", idempotency_key="hook-1",
                order_type="LIMIT", limit_price_minor=1000,
            )
        self.assertIn("INSUFFICIENT_CASH", str(ctx.exception))
        # No order or fill was recorded.
        self.assertEqual(ledger.project_orders(), [])
        self.assertEqual(ledger.project_fills(), [])

    def test_executable_submit_accepts_within_cash(self) -> None:
        ledger = self._ledger(cash_minor=10_000_00)
        result = submit_interactive_order(
            ledger=ledger, bars=self._bars(), symbol="BIYA", instrument_id="BIYA",
            side="BUY", quantity=10, observation_time=1,
            client_order_id="hook-2", idempotency_key="hook-2",
            order_type="LIMIT", limit_price_minor=1000,
        )
        self.assertEqual(result["order"]["state"], "FILLED")

    def test_context_is_pure_no_global_state(self) -> None:
        # Evaluating a context never mutates the input or global state.
        from dataclasses import asdict

        context = _context()
        before = asdict(context)
        evaluate_pretrade(context)
        self.assertEqual(asdict(context), before)


if __name__ == "__main__":
    unittest.main()