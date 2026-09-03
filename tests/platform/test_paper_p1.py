"""Platformization P1 adversarial and parity tests."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.execution.intent import build_order_intent
from market_platform_foundation.paper.contracts import build_instrument_ref, build_user_order_intent
from market_platform_foundation.paper.execution import (
    cancel_interactive_order,
    execute_normalized_intent_for_parity,
    preview_interactive_order,
    submit_interactive_order,
)
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.risk.kill_switch import KillSwitchState
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY
from market_platform_foundation.ui_api.paper_projections import open_paper_session, submit_paper_order
from market_platform_foundation.ui_api.store import ReplayStore

COLLECTION_ROOT = ROOT.parent


class InteractiveExecutionParityTests(unittest.TestCase):
    store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=COLLECTION_ROOT)
        cls.store.load()

    def _select_fillable_cursor(self) -> None:
        for index in range(len(self.store.bars) - 2, -1, -1):
            self.store.set_cursor_index(index)
            bars = self.store.bars_for_execution()
            if not bars:
                continue
            preview = preview_interactive_order(
                ledger=self.store.paper_ledger,
                bars=bars,
                symbol=self.store.symbol,
                instrument_id=self.store.instrument_id,
                side="BUY",
                quantity=1,
                observation_time=self.store.prediction_cutoff(),
                client_order_id="parity-probe",
                idempotency_key="parity-probe",
            )
            if preview.get("fill_preview") is not None and preview.get("risk_status") == "PASS":
                return
        self.fail("No fillable replay cursor found on BIYA fixture")

    def test_interactive_execution_parity(self) -> None:
        """INTERACTIVE_EXECUTION_PARITY: equivalent semantics produce equivalent fills."""
        self._select_fillable_cursor()
        cutoff = self.store.prediction_cutoff()
        bars = self.store.bars_for_execution()
        instrument_id = self.store.instrument_id
        quantity = 1

        strategy_intent = build_order_intent(
            interpretation={
                "outcome": "signal",
                "direction": "long",
                "prediction_cutoff": cutoff,
                "strategy_identity_hash": "parity-test",
            },
            instrument_id=instrument_id,
            observation_time=cutoff,
            desired_quantity=quantity,
        )
        assert strategy_intent is not None

        user_intent = build_user_order_intent(
            instrument=build_instrument_ref(instrument_id=instrument_id, symbol=self.store.symbol),
            side="BUY",
            quantity=quantity,
            observation_time=cutoff,
            client_order_id="parity-user",
            idempotency_key="parity-user-key",
        )

        _, strategy_order, strategy_fill = execute_normalized_intent_for_parity(
            intent=strategy_intent,
            policy=DEFAULT_RISK_POLICY,
            bars=bars,
        )
        _, user_order, user_fill = execute_normalized_intent_for_parity(
            intent=user_intent,
            policy=DEFAULT_RISK_POLICY,
            bars=bars,
        )

        self.assertIsNotNone(strategy_fill)
        self.assertIsNotNone(user_fill)
        assert strategy_fill is not None and user_fill is not None
        self.assertEqual(strategy_fill["fill_quantity"], user_fill["fill_quantity"])
        self.assertEqual(strategy_fill["fill_price_minor"], user_fill["fill_price_minor"])
        self.assertEqual(strategy_order["state"], user_order["state"])


class PaperP1AdversarialSubmissionTests(unittest.TestCase):
    store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=COLLECTION_ROOT)
        cls.store.load()

    def test_zero_quantity_rejected(self) -> None:
        with self.assertRaises(ValueError):
            preview_interactive_order(
                ledger=self.store.paper_ledger,
                bars=self.store.bars_for_execution(),
                symbol=self.store.symbol,
                instrument_id=self.store.instrument_id,
                side="BUY",
                quantity=0,
                observation_time=self.store.prediction_cutoff(),
                client_order_id="zero-qty",
                idempotency_key="zero-qty-key",
            )

    def test_invalid_side_rejected(self) -> None:
        with self.assertRaises(ValueError):
            preview_interactive_order(
                ledger=self.store.paper_ledger,
                bars=self.store.bars_for_execution(),
                symbol=self.store.symbol,
                instrument_id=self.store.instrument_id,
                side="HOLD",
                quantity=1,
                observation_time=self.store.prediction_cutoff(),
                client_order_id="bad-side",
                idempotency_key="bad-side-key",
            )

    def test_preview_does_not_append_submit_events(self) -> None:
        before = len(self.store.paper_ledger.events)
        preview_interactive_order(
            ledger=self.store.paper_ledger,
            bars=self.store.bars_for_execution(),
            symbol=self.store.symbol,
            instrument_id=self.store.instrument_id,
            side="BUY",
            quantity=1,
            observation_time=self.store.prediction_cutoff(),
            client_order_id="preview-only",
            idempotency_key="preview-only-key",
        )
        self.assertEqual(len(self.store.paper_ledger.events), before)


class PaperP1SimulationTests(unittest.TestCase):
    store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=COLLECTION_ROOT)
        cls.store.load()

    def setUp(self) -> None:
        self._prior = os.environ.get("IMP_PAPER_EXECUTION")
        os.environ["IMP_PAPER_EXECUTION"] = "1"
        open_paper_session(self.store, {"execution_mode": "INTERNAL_SIMULATION"})
        self._select_fillable_cursor()

    def tearDown(self) -> None:
        if self._prior is None:
            os.environ.pop("IMP_PAPER_EXECUTION", None)
        else:
            os.environ["IMP_PAPER_EXECUTION"] = self._prior

    def _select_fillable_cursor(self) -> None:
        for index in range(len(self.store.bars) - 2, -1, -1):
            self.store.set_cursor_index(index)
            preview = preview_interactive_order(
                ledger=self.store.paper_ledger,
                bars=self.store.bars_for_execution(),
                symbol=self.store.symbol,
                instrument_id=self.store.instrument_id,
                side="BUY",
                quantity=1,
                observation_time=self.store.prediction_cutoff(),
                client_order_id="cursor-probe",
                idempotency_key="cursor-probe",
            )
            if preview.get("fill_preview") is not None and preview.get("risk_status") == "PASS":
                return
        self.fail("No fillable replay cursor found on BIYA fixture")

    def test_risk_blocked_vertical_slice(self) -> None:
        self.store.paper_ledger.kill_switch = KillSwitchState(active=True)
        body = {
            "side": "BUY",
            "quantity": 1,
            "client_order_id": "risk-block-1",
            "idempotency_key": "risk-block-key-1",
        }
        result = submit_paper_order(self.store, body)
        self.assertEqual(result["submission"]["decision"], "REJECT")
        self.assertIsNone(result["submission"].get("fill"))
        self.assertEqual(len(self.store.paper_ledger.project_fills()), 0)

    def test_idempotent_retry_single_fill(self) -> None:
        body = {
            "side": "BUY",
            "quantity": 1,
            "client_order_id": "idempotent-1",
            "idempotency_key": "idempotent-key-1",
        }
        first = submit_paper_order(self.store, body)
        second = submit_paper_order(self.store, body)
        self.assertFalse(first["submission"]["duplicate"])
        self.assertTrue(second["submission"]["duplicate"])
        self.assertEqual(len(self.store.paper_ledger.project_fills()), 1)

    def test_different_idempotency_key_creates_second_order(self) -> None:
        first = submit_paper_order(
            self.store,
            {
                "side": "BUY",
                "quantity": 1,
                "client_order_id": "order-a",
                "idempotency_key": "key-a",
            },
        )
        second = submit_paper_order(
            self.store,
            {
                "side": "BUY",
                "quantity": 1,
                "client_order_id": "order-b",
                "idempotency_key": "key-b",
            },
        )
        self.assertFalse(first["submission"]["duplicate"])
        self.assertFalse(second["submission"]["duplicate"])
        self.assertGreaterEqual(len(self.store.paper_ledger.project_orders()), 2)

    def test_execution_trace_resolves_vertical_slice(self) -> None:
        result = submit_paper_order(
            self.store,
            {
                "side": "BUY",
                "quantity": 1,
                "client_order_id": "trace-1",
                "idempotency_key": "trace-key-1",
            },
        )
        intent_id = result["submission"]["intent_id"]
        trace = self.store.paper_ledger.project_execution_trace(intent_id=intent_id)
        stages = {step["stage"] for step in trace["steps"]}
        self.assertIn("ORDER_INTENT", stages)
        self.assertIn("RISK_DECISION", stages)
        self.assertIn("FILL", stages)
        self.assertIn("PORTFOLIO_IMPACT", stages)

    def test_cancel_filled_order_not_supported(self) -> None:
        result = submit_paper_order(
            self.store,
            {
                "side": "BUY",
                "quantity": 1,
                "client_order_id": "cancel-test",
                "idempotency_key": "cancel-test-key",
            },
        )
        order_id = str(result["submission"]["order_id"])
        with self.assertRaises(ValueError) as ctx:
            cancel_interactive_order(ledger=self.store.paper_ledger, order_id=order_id)
        self.assertIn("NOT_SUPPORTED", str(ctx.exception))

    def test_submit_blocked_without_env(self) -> None:
        os.environ.pop("IMP_PAPER_EXECUTION", None)
        ledger = PaperExecutionLedger.open_session(
            replay_session_id=self.store.session_id,
            instrument_id=self.store.instrument_id,
            symbol=self.store.symbol,
            execution_mode="NONE",
            execution_authority="BLOCKED",
        )
        with self.assertRaises(ValueError) as ctx:
            submit_interactive_order(
                ledger=ledger,
                bars=self.store.bars_for_execution(),
                symbol=self.store.symbol,
                instrument_id=self.store.instrument_id,
                side="BUY",
                quantity=1,
                observation_time=self.store.prediction_cutoff(),
                client_order_id="blocked",
                idempotency_key="blocked-key",
            )
        self.assertIn("NOT_AUTHORIZED", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
