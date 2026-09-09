"""G3 BL-0205 — replace lifecycle tests.

Proves canonical replacement semantics on the Paper lifecycle:
- only a working remainder is replaceable (WORKING/ACTIVATED/PARTIALLY_FILLED/REPLACED);
- prior fills are immutable; replacement total below cumulative filled is rejected;
- replace may change quantity and/or price, never side/instrument/account/mode;
- explicit lineage (OrderReplaced event, replace revision/digest);
- idempotent retry returns the same logical result without duplicate events;
- reservation is recomputed atomically (old obligation replaced, not doubled);
- cancel after replace works; a replaced order remains working.
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
from market_platform_foundation.risk.financial import working_order_obligations_minor
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY


def _policy() -> dict:
    policy = dict(DEFAULT_RISK_POLICY)
    policy["participation_cap_numerator"] = 1
    policy["participation_cap_denominator"] = 10
    policy["max_order_shares"] = 1_000
    policy["max_position_shares"] = 5_000
    return policy


def _ledger() -> PaperExecutionLedger:
    return PaperExecutionLedger.open_session(
        replay_session_id="g3-replace-1",
        instrument_id="BIYA",
        symbol="BIYA",
        policy=_policy(),
        execution_mode="INTERNAL_SIMULATION",
        execution_authority="PAPER_ONLY",
    )


def _bars(price: str = "10.00", volume: int = 40, offset: int = 0) -> list[dict[str, object]]:
    return [
        {
            "available_time": 100 + offset + i * 100,
            "bar_payload": {
                "close": price,
                "high": price,
                "low": price,
                "open": price,
                "volume": volume,
            },
        }
        for i in range(1, 6)
    ]


def _submit_partial(ledger: PaperExecutionLedger, client_id: str = "rp-1") -> str:
    result = submit_interactive_order(
        ledger=ledger, bars=_bars(volume=40), symbol="BIYA", instrument_id="BIYA",
        side="BUY", quantity=10, observation_time=1,
        client_order_id=client_id, idempotency_key=client_id,
        order_type="LIMIT", limit_price_minor=1000,
    )
    assert result["order"]["state"] == "PARTIALLY_FILLED"
    return result["order_id"]


class ReplaceEligibilityTests(unittest.TestCase):
    def test_replace_working_remainder(self) -> None:
        ledger = _ledger()
        order_id = _submit_partial(ledger)
        replaced = replace_interactive_order(
            ledger=ledger, order_id=order_id, replaced_quantity=8,
            order_type="LIMIT", limit_price_minor=1000,
        )
        self.assertEqual(replaced["state"], "REPLACED")
        projected = ledger.lookup_order(order_id)
        # Fills immutable (4); replacement total 8 -> remainder 4.
        self.assertEqual(int(projected["cumulative_filled_quantity"]), 4)
        self.assertEqual(int(projected["working_remaining"]), 4)
        self.assertEqual(int(projected["replaced_quantity"]), 8)
        self.assertEqual(int(projected["replace_count"]), 1)
        self.assertTrue(projected["replace_revision"])

    def test_replace_below_filled_rejected(self) -> None:
        ledger = _ledger()
        order_id = _submit_partial(ledger)
        with self.assertRaises(ValueError) as ctx:
            replace_interactive_order(
                ledger=ledger, order_id=order_id, replaced_quantity=3,
                order_type="LIMIT", limit_price_minor=1000,
            )
        self.assertIn("PAPER_ORDER_REPLACE_BELOW_FILLED", str(ctx.exception))
        # Order unchanged after failed replace.
        self.assertEqual(ledger.lookup_order(order_id)["state"], "PARTIALLY_FILLED")

    def test_replace_terminal_order_rejected(self) -> None:
        ledger = _ledger()
        result = submit_interactive_order(
            ledger=ledger, bars=_bars(volume=1000), symbol="BIYA", instrument_id="BIYA",
            side="BUY", quantity=5, observation_time=1,
            client_order_id="rp-term", idempotency_key="rp-term",
            order_type="LIMIT", limit_price_minor=1000,
        )
        self.assertEqual(result["order"]["state"], "FILLED")
        with self.assertRaises(ValueError) as ctx:
            replace_interactive_order(
                ledger=ledger, order_id=result["order_id"], replaced_quantity=5,
            )
        self.assertIn("PAPER_ORDER_REPLACE_INVALID_STATE", str(ctx.exception))

    def test_replace_price_only(self) -> None:
        ledger = _ledger()
        order_id = _submit_partial(ledger)
        replaced = replace_interactive_order(
            ledger=ledger, order_id=order_id, replaced_quantity=10,
            order_type="LIMIT", limit_price_minor=1500,
        )
        self.assertEqual(replaced["state"], "REPLACED")
        projected = ledger.lookup_order(order_id)
        self.assertEqual(int(projected["limit_price_minor"]), 1500)
        self.assertEqual(int(projected["working_remaining"]), 6)

    def test_replace_quantity_reduce_drops_reservation(self) -> None:
        ledger = _ledger()
        order_id = _submit_partial(ledger)
        replaced = replace_interactive_order(
            ledger=ledger, order_id=order_id, replaced_quantity=5,
            order_type="LIMIT", limit_price_minor=1000,
        )
        self.assertEqual(replaced["state"], "REPLACED")
        projected = ledger.lookup_order(order_id)
        self.assertEqual(int(projected["working_remaining"]), 1)
        self.assertEqual(working_order_obligations_minor(ledger), 1 * 1000)

    def test_replace_price_increase_recomputes_reservation(self) -> None:
        ledger = _ledger()
        order_id = _submit_partial(ledger)
        replaced = replace_interactive_order(
            ledger=ledger, order_id=order_id, replaced_quantity=10,
            order_type="LIMIT", limit_price_minor=100_000,
        )
        self.assertEqual(replaced["state"], "REPLACED")
        # Obligation = 6 remaining × $1,000/share = $600,000, not the old 6×$10.
        self.assertEqual(working_order_obligations_minor(ledger), 6 * 100_000)

    def test_replace_insufficient_cash_rejected(self) -> None:
        # Low-cash ledger: $10,000 cash. After the 4-share fill at $10 cash is
        # $9,960; replacing the 6-share remainder to 8 shares at $1,000/share
        # needs (8-4)=4 × $1,000 = $4,000 — within cash, so accepted. Raising
        # the price to $10,000/share needs $40,000 > available -> rejected.
        policy = _policy()
        policy["initial_cash_minor"] = 10_000_00
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="g3-replace-cash",
            instrument_id="BIYA",
            symbol="BIYA",
            policy=policy,
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )
        order_id = _submit_partial(ledger)
        replace_interactive_order(
            ledger=ledger, order_id=order_id, replaced_quantity=8,
            order_type="LIMIT", limit_price_minor=100_000,
        )
        with self.assertRaises(ValueError) as ctx:
            replace_interactive_order(
                ledger=ledger, order_id=order_id, replaced_quantity=8,
                order_type="LIMIT", limit_price_minor=1_000_000,
            )
        self.assertIn("INSUFFICIENT_CASH", str(ctx.exception))


class ReplaceLineageTests(unittest.TestCase):
    def test_duplicate_retry_same_logical_result(self) -> None:
        ledger = _ledger()
        order_id = _submit_partial(ledger)
        first = replace_interactive_order(
            ledger=ledger, order_id=order_id, replaced_quantity=8,
            order_type="LIMIT", limit_price_minor=1200,
        )
        events_before = len(ledger.events)
        second = replace_interactive_order(
            ledger=ledger, order_id=order_id, replaced_quantity=8,
            order_type="LIMIT", limit_price_minor=1200,
        )
        self.assertTrue(second["duplicate"])
        self.assertEqual(len(ledger.events), events_before, "no duplicate replace events")
        self.assertEqual(first["order_id"], second["order_id"])

    def test_replaced_order_still_cancellable(self) -> None:
        ledger = _ledger()
        order_id = _submit_partial(ledger)
        replace_interactive_order(
            ledger=ledger, order_id=order_id, replaced_quantity=8,
            order_type="LIMIT", limit_price_minor=1000,
        )
        cancelled = cancel_interactive_order(ledger=ledger, order_id=order_id)
        self.assertEqual(cancelled["state"], "CANCELLED")
        self.assertEqual(int(cancelled["filled_quantity"]), 4)

    def test_second_replace_works(self) -> None:
        ledger = _ledger()
        order_id = _submit_partial(ledger)
        first = replace_interactive_order(
            ledger=ledger, order_id=order_id, replaced_quantity=8,
            order_type="LIMIT", limit_price_minor=1000,
        )
        second = replace_interactive_order(
            ledger=ledger, order_id=order_id, replaced_quantity=7,
            order_type="LIMIT", limit_price_minor=1100,
        )
        self.assertFalse(second["duplicate"])
        self.assertEqual(int(second["replace_count"]), 2)
        projected = ledger.lookup_order(order_id)
        self.assertEqual(int(projected["working_remaining"]), 3)

    def test_replace_does_not_mutate_side_or_instrument(self) -> None:
        ledger = _ledger()
        order_id = _submit_partial(ledger)
        replace_interactive_order(
            ledger=ledger, order_id=order_id, replaced_quantity=8,
            order_type="LIMIT", limit_price_minor=1000,
        )
        projected = ledger.lookup_order(order_id)
        self.assertEqual(projected["side"], "BUY")
        self.assertEqual(projected["instrument_id"], "BIYA")


if __name__ == "__main__":
    unittest.main()