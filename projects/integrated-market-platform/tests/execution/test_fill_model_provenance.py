"""Fill-model provenance, Live fail-closed, and deterministic replay."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.execution.book_aware import (  # noqa: E402
    BOOK_AWARE_SIMULATOR_VERSION,
    BookAwareL2Simulator,
)
from market_platform_foundation.execution.fill_model import (  # noqa: E402
    FILL_CLOCK_KIND_BAR_AVAILABLE,
    LIVE_EXECUTION_FORBIDDEN,
    SIMULATION_EVIDENCE_LAYER,
    FillModelLiveForbidden,
)
from market_platform_foundation.execution.simulator import (  # noqa: E402
    SIMULATOR_VERSION,
    SOURCE_CAPABILITY,
    BarConservativeSimulator,
)
from market_platform_foundation.paper.contracts import (  # noqa: E402
    build_instrument_ref,
    build_user_order_intent,
)
from market_platform_foundation.paper.execution import execute_order_intent  # noqa: E402
from market_platform_foundation.paper.ledger import PaperExecutionLedger  # noqa: E402
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY  # noqa: E402

DEFAULT_POLICY = DEFAULT_RISK_POLICY


def _bars() -> list[dict]:
    return [
        {
            "available_time": 1000,
            "normalized_event_id": "bar-1",
            "bar_payload": {
                "high": "101.0000",
                "low": "99.0000",
                "volume": 10000,
            },
        },
        {
            "available_time": 2000,
            "normalized_event_id": "bar-2",
            "bar_payload": {
                "high": "101.0000",
                "low": "99.0000",
                "volume": 10000,
            },
        },
    ]


def _intent(**extra: object) -> dict:
    body: dict = {
        "created_time": 500,
        "direction": "long",
        "instrument_id": "NVDA",
        "intent_id": "intent-prov-1",
        "quantity": 10,
    }
    body.update(extra)
    return body


def _approve(quantity: int = 10) -> dict:
    return {"decision": "APPROVE", "approved_quantity": quantity}


class FillModelProvenanceTests(unittest.TestCase):
    def test_fill_carries_simulator_identity_after_fill_id(self) -> None:
        sim = BarConservativeSimulator(policy=DEFAULT_POLICY)
        order, fill = sim.simulate(
            intent=_intent(),
            risk_decision=_approve(),
            bars=_bars(),
        )
        assert fill is not None
        self.assertEqual(fill["simulator_version"], SIMULATOR_VERSION)
        self.assertEqual(fill["source_capability"], SOURCE_CAPABILITY)
        self.assertEqual(fill["fill_model_registry_id"], "simulation.bar_conservative")
        self.assertEqual(fill["evidence_layer"], SIMULATION_EVIDENCE_LAYER)
        self.assertFalse(fill["is_market_truth"])
        self.assertEqual(fill["execution_mode"], "INTERNAL_SIMULATION")
        self.assertEqual(fill["fill_clock_kind"], FILL_CLOCK_KIND_BAR_AVAILABLE)
        self.assertEqual(fill["fill_time"], 1000)
        self.assertEqual(fill["activation_time"], 1000)
        self.assertEqual(fill["submit_time_ns"], 500)
        self.assertIsNotNone(fill.get("git_sha"))
        self.assertEqual(order["simulator_version"], SIMULATOR_VERSION)
        self.assertNotEqual(fill["fill_clock_kind"], "process_wall")

    def test_deterministic_replay_keeps_fill_id(self) -> None:
        intent = _intent()
        risk = _approve()
        bars = _bars()
        first = BarConservativeSimulator(policy=DEFAULT_POLICY)
        second = BarConservativeSimulator(policy=DEFAULT_POLICY)
        _, fill_a = first.simulate(intent=intent, risk_decision=risk, bars=bars)
        _, fill_b = second.simulate(intent=intent, risk_decision=risk, bars=bars)
        assert fill_a is not None and fill_b is not None
        self.assertEqual(fill_a["fill_id"], fill_b["fill_id"])
        self.assertEqual(fill_a["fill_quantity"], fill_b["fill_quantity"])
        self.assertEqual(fill_a["simulator_version"], fill_b["simulator_version"])

    def test_live_execution_mode_is_forbidden(self) -> None:
        sim = BarConservativeSimulator(policy=DEFAULT_POLICY)
        with self.assertRaises(FillModelLiveForbidden) as ctx:
            sim.simulate(
                intent=_intent(execution_mode="LIVE"),
                risk_decision=_approve(),
                bars=_bars(),
            )
        self.assertIn(LIVE_EXECUTION_FORBIDDEN, str(ctx.exception))

    def test_reject_still_carries_provenance(self) -> None:
        sim = BarConservativeSimulator(policy=DEFAULT_POLICY)
        order, fill = sim.simulate(
            intent=_intent(),
            risk_decision={"decision": "REJECT", "approved_quantity": 0},
            bars=_bars(),
        )
        self.assertIsNone(fill)
        self.assertEqual(order["state"], "REJECTED")
        self.assertEqual(order["simulator_version"], SIMULATOR_VERSION)
        self.assertFalse(order["is_market_truth"])
        self.assertEqual(order["evidence_layer"], SIMULATION_EVIDENCE_LAYER)

    def test_demo_none_mode_is_allowed_for_replay(self) -> None:
        sim = BarConservativeSimulator(policy=DEFAULT_POLICY)
        order, fill = sim.simulate(
            intent=_intent(execution_mode="NONE"),
            risk_decision=_approve(),
            bars=_bars(),
        )
        assert fill is not None
        self.assertEqual(fill["execution_mode"], "NONE")
        self.assertEqual(order["state"], "FILLED")

    def test_book_aware_records_its_own_model_version(self) -> None:
        sim = BookAwareL2Simulator(policy=DEFAULT_POLICY)
        _, fill = sim.simulate(
            intent=_intent(
                book_snapshot={
                    "best_bid": 100.0,
                    "best_ask": 100.04,
                    "bid_size": 200.0,
                    "ask_size": 50.0,
                },
                quantity=500,
            ),
            risk_decision=_approve(500),
            bars=_bars(),
        )
        assert fill is not None
        self.assertEqual(fill["simulator_version"], BOOK_AWARE_SIMULATOR_VERSION)
        self.assertEqual(fill["fill_model_registry_id"], "simulation.book_aware_l2_v1")
        self.assertFalse(fill["is_market_truth"])

    def test_paper_execute_live_ledger_is_forbidden(self) -> None:
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="fill-model-live",
            instrument_id="NVDA",
            symbol="NVDA",
            execution_mode="LIVE",
            execution_authority="BLOCKED",
        )
        intent = build_user_order_intent(
            instrument=build_instrument_ref(instrument_id="NVDA", symbol="NVDA"),
            side="BUY",
            quantity=1,
            observation_time=500,
            client_order_id="live-forbidden",
            idempotency_key="live-forbidden",
        )
        with self.assertRaises(FillModelLiveForbidden):
            execute_order_intent(intent=intent, ledger=ledger, bars=_bars())

    def test_paper_execute_stamps_internal_simulation_fill(self) -> None:
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="fill-model-paper",
            instrument_id="NVDA",
            symbol="NVDA",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )
        intent = build_user_order_intent(
            instrument=build_instrument_ref(instrument_id="NVDA", symbol="NVDA"),
            side="BUY",
            quantity=1,
            observation_time=500,
            client_order_id="paper-stamp",
            idempotency_key="paper-stamp",
        )
        _decision, order, fill = execute_order_intent(
            intent=intent,
            ledger=ledger,
            bars=_bars(),
        )
        assert fill is not None
        self.assertEqual(fill["execution_mode"], "INTERNAL_SIMULATION")
        self.assertEqual(fill["simulator_version"], SIMULATOR_VERSION)
        self.assertEqual(order["evidence_layer"], SIMULATION_EVIDENCE_LAYER)


if __name__ == "__main__":
    unittest.main()
