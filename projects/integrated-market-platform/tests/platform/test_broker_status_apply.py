"""Workstream L regression tests.

E1b: ``apply_broker_status_event`` orchestrator — polled broker statuses
advance a live paper order through ``append_order_state`` and new fills are
deduped on ``broker_fill_id`` so a partially-filled-then-completed order no
longer freezes (each fill applied exactly once).

E11: CREATED orders are consistently non-cancellable on both execution paths
(``PAPER_ORDER_CANCEL_INVALID_STATE``) because ``VALID_ORDER_TRANSITIONS``
defines no ``CREATED -> CANCEL_PENDING`` edge.

E9: one ``BarConservativeSimulator`` per ledger session — participation-cap
allocations accumulate across submissions sharing a bar; previews stay dry.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.execution.simulator import BarConservativeSimulator  # noqa: E402
from market_platform_foundation.paper.broker_paper import (  # noqa: E402
    apply_broker_status_event,
    cancel_broker_paper_order,
    submit_broker_paper_order,
)
from market_platform_foundation.paper.contracts import (  # noqa: E402
    build_instrument_ref,
    build_user_order_intent,
)
from market_platform_foundation.paper.execution import (  # noqa: E402
    cancel_interactive_order,
    execute_normalized_intent_for_parity,
    preview_interactive_order,
    submit_interactive_order,
)
from market_platform_foundation.paper.ledger import PaperExecutionLedger  # noqa: E402
from market_platform_foundation.local_state.startup import (  # noqa: E402
    ledger_from_session,
    session_record_from_ledger,
)
from market_platform_foundation.providers.adapters.tradier_paper import (  # noqa: E402
    TRADIER_SANDBOX_ENDPOINT,
    TradierReplayStore,
    make_tradier_paper_provider,
)
from market_platform_foundation.providers.broker_execution import (  # noqa: E402
    normalize_broker_fill,
)
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY  # noqa: E402

INSTRUMENT = build_instrument_ref(instrument_id="BIYA", symbol="BIYA")

GATED_ENV = {
    "IMP_TRADIER_PAPER": "1",
    "IMP_BROKER_PAPER_EXECUTION": "1",
    "IMP_TRADIER_TOKEN": "sandbox-test-token",
    "IMP_TRADIER_ENDPOINT": TRADIER_SANDBOX_ENDPOINT,
    "IMP_TRADIER_ACCOUNT_ID": "acct-test",
}

BROKER_ORDER_ID = "TR-PART-0001"

# Cumulative post-completion status: the two original sandbox fills replayed
# plus one new execution — mirrors how brokers answer fetch_order.
FILLED_CUMULATIVE_PAYLOAD = {
    "broker_order_id": BROKER_ORDER_ID,
    "status": "filled",
    "status_raw": "closed",
    "event_time_ns": 1787000000900000000,
    "receive_time_ns": 1787000000900500000,
    "avg_fill_price_minor": 11613,
    "filled_quantity": 60,
    "fills": [
        {
            "broker_fill_id": "TR-FL-0010",
            "quantity": 25,
            "price_minor": 11600,
            "event_time_ns": 1787000000600000000,
            "receive_time_ns": 1787000000600100000,
        },
        {
            "broker_fill_id": "TR-FL-0011",
            "quantity": 15,
            "price_minor": 11625,
            "event_time_ns": 1787000000600200000,
            "receive_time_ns": 1787000000600500000,
        },
        {
            "broker_fill_id": "TR-FL-0012",
            "quantity": 20,
            "price_minor": 11610,
            "event_time_ns": 1787000000900000000,
            "receive_time_ns": 1787000000900100000,
        },
    ],
}


def _broker_ledger() -> PaperExecutionLedger:
    return PaperExecutionLedger.open_session(
        replay_session_id="wl-e1b-session",
        instrument_id="BIYA",
        symbol="BIYA",
        execution_mode="BROKER_PAPER",
        execution_authority="PAPER_ONLY",
        data_mode="BROKER_DELAYED",
        data_provider="TRADIER",
        execution_provider="TRADIER",
    )


def _interactive_ledger() -> PaperExecutionLedger:
    return PaperExecutionLedger.open_session(
        replay_session_id="wl-e9-session",
        instrument_id="BIYA",
        symbol="BIYA",
        execution_mode="INTERNAL_SIMULATION",
        execution_authority="PAPER_ONLY",
    )


def _fixture_provider(store: TradierReplayStore | None = None) -> object:
    return make_tradier_paper_provider(
        env=dict(GATED_ENV),
        symbol_map={"BIYA": "BIYA"},
        replay_store=store or TradierReplayStore.load(),
    )


def _submit_partial_from_fixture() -> tuple[PaperExecutionLedger, str]:
    """Submit cli-broker-partial-1 from tradier_sandbox_lifecycle.json."""
    ledger = _broker_ledger()
    result = submit_broker_paper_order(
        ledger=ledger,
        provider=_fixture_provider(),
        instrument=dict(INSTRUMENT),
        side="BUY",
        quantity=100,
        observation_time=1787000000000000000,
        client_order_id="cli-broker-partial-1",
        idempotency_key="key-broker-partial-1",
    )
    assert result["order"]["state"] == "PARTIALLY_FILLED", result["order"]
    return ledger, result["order_id"]


class _ScriptedFetchProvider:
    """fetch_order stub yielding queued steps: payload dict | status str | Exception."""

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.fetch_calls = 0

    def fetch_order(self, broker_order_id: str):  # noqa: ANN201
        self.fetch_calls += 1
        step = self._script.pop(0)
        if isinstance(step, Exception):
            raise step
        if isinstance(step, str):
            return SimpleNamespace(status=step, reason_code="SCRIPTED", events=())
        return SimpleNamespace(
            status="ok",
            reason_code=None,
            events=[{"broker_event_type": "ORDER_STATUS", "payload": step}],
        )


def _fill_payload(**overrides: object) -> dict:
    body = {
        "broker_order_id": BROKER_ORDER_ID,
        "status": "partially_filled",
        "status_raw": "partially_filled",
        "event_time_ns": 1787000000700000000,
        "receive_time_ns": 1787000000700500000,
        "filled_quantity": 25,
        "fills": [
            {
                "broker_fill_id": "TR-FL-0020",
                "quantity": 25,
                "price_minor": 11600,
                "event_time_ns": 1787000000700000000,
                "receive_time_ns": 1787000000700100000,
            }
        ],
    }
    body.update(overrides)
    return body


class BrokerStatusOrchestratorTests(unittest.TestCase):
    """E1b: polled statuses advance the lifecycle; fills dedupe exactly once."""

    def test_partial_fill_can_be_cancelled_without_losing_fills(self) -> None:
        ledger, order_id = _submit_partial_from_fixture()

        class _CancelProvider:
            def cancel_order(self, **_: object):  # noqa: ANN201
                return SimpleNamespace(status="ok", reason_code=None)

        result = cancel_broker_paper_order(
            ledger=ledger,
            provider=_CancelProvider(),
            order_id=order_id,
        )

        self.assertEqual(result["state"], "CANCELLED")
        self.assertEqual(ledger.lookup_order(order_id)["state"], "CANCELLED")
        self.assertGreater(sum(int(row["fill_quantity"]) for row in ledger.project_fills()), 0)

    def test_partial_fill_restart_replay_and_idempotency_preserve_progress(self) -> None:
        ledger, order_id = _submit_partial_from_fixture()
        session = session_record_from_ledger(ledger)
        os.environ["IMP_BROKER_PAPER_EXECUTION"] = "1"
        try:
            restored = ledger_from_session(
                session,
                list(ledger.events),
                dict(ledger.idempotency_index),
            )
        finally:
            os.environ.pop("IMP_BROKER_PAPER_EXECUTION", None)

        result = apply_broker_status_event(
            ledger=restored,
            provider=_ScriptedFetchProvider([dict(FILLED_CUMULATIVE_PAYLOAD)]),
            order_id=order_id,
        )
        duplicate = submit_broker_paper_order(
            ledger=restored,
            provider=_ScriptedFetchProvider([]),
            instrument=dict(INSTRUMENT),
            side="BUY",
            quantity=100,
            observation_time=1787000000000000000,
            client_order_id="cli-broker-partial-1",
            idempotency_key="key-broker-partial-1",
        )

        self.assertEqual(result["state"], "FILLED")
        self.assertEqual(len(restored.project_fills()), 3)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(restored.lookup_order(order_id)["state"], "FILLED")

    def test_partial_fill_sequence_reaches_filled_each_fill_once(self) -> None:
        ledger, order_id = _submit_partial_from_fixture()
        self.assertEqual(len(ledger.project_fills()), 2)

        provider = _fixture_provider()
        provider._replay.add_record(
            operation="fetch_order",
            match={"broker_order_id": BROKER_ORDER_ID},
            response=dict(FILLED_CUMULATIVE_PAYLOAD),
        )
        result = apply_broker_status_event(ledger=ledger, provider=provider, order_id=order_id)

        self.assertTrue(result["advanced"])
        self.assertEqual(result["applied_states"], ["FILLED"])
        self.assertEqual(result["previous_state"], "PARTIALLY_FILLED")
        self.assertEqual(result["state"], "FILLED")
        self.assertEqual(len(result["fills"]), 1, "only the new fill may be appended")

        fills = ledger.project_fills()
        broker_fill_ids = [str(fill.get("broker_fill_id")) for fill in fills]
        self.assertEqual(len(broker_fill_ids), len(set(broker_fill_ids)), "duplicate fill applied")
        self.assertEqual(sorted(broker_fill_ids), ["TR-FL-0010", "TR-FL-0011", "TR-FL-0012"])
        self.assertEqual(sum(int(fill["fill_quantity"]) for fill in fills), 60)
        self.assertEqual(ledger.lookup_order(order_id)["state"], "FILLED")

    def test_repeated_poll_of_same_status_is_idempotent(self) -> None:
        ledger, order_id = _submit_partial_from_fixture()
        before_events = len(ledger.events)

        result = apply_broker_status_event(
            ledger=ledger,
            provider=_ScriptedFetchProvider([dict(FILLED_CUMULATIVE_PAYLOAD)]),
            order_id=order_id,
        )
        self.assertTrue(result["advanced"])
        after_first = len(ledger.events)

        again = apply_broker_status_event(
            ledger=ledger,
            provider=_ScriptedFetchProvider([dict(FILLED_CUMULATIVE_PAYLOAD)]),
            order_id=order_id,
        )
        self.assertFalse(again["advanced"])
        self.assertTrue(again["terminal"])
        self.assertEqual(len(ledger.events), after_first)
        self.assertGreater(after_first, before_events)

    def test_unknown_status_mapping_fails_closed_without_mutation(self) -> None:
        ledger, order_id = _submit_partial_from_fixture()
        baseline = len(ledger.events)

        with self.assertRaises(ValueError) as ctx:
            apply_broker_status_event(
                ledger=ledger,
                provider=_ScriptedFetchProvider([_fill_payload(status="meh")]),
                order_id=order_id,
            )
        self.assertIn("BROKER_STATUS_EVENT_INVALID", str(ctx.exception))
        self.assertEqual(len(ledger.events), baseline)
        self.assertEqual(ledger.lookup_order(order_id)["state"], "PARTIALLY_FILLED")
        self.assertEqual(len(ledger.project_fills()), 2)

    def test_malformed_payloads_fail_closed(self) -> None:
        cases = {
            "missing_broker_order_id": {"fills": []},
            "fill_quantity_wrong_type": _fill_payload(
                fills=[{"broker_fill_id": "X", "quantity": "abc", "price_minor": 1,
                        "event_time_ns": 1, "receive_time_ns": 2}]
            ),
            "fill_quantity_nan": _fill_payload(
                fills=[{"broker_fill_id": "X", "quantity": float("nan"), "price_minor": 1,
                        "event_time_ns": 1, "receive_time_ns": 2}]
            ),
            "fill_time_missing": _fill_payload(
                fills=[{"broker_fill_id": "X", "quantity": 1, "price_minor": 1}]
            ),
        }
        for label, payload in cases.items():
            with self.subTest(case=label):
                ledger, order_id = _submit_partial_from_fixture()
                baseline = len(ledger.events)
                with self.assertRaises(ValueError):
                    apply_broker_status_event(
                        ledger=ledger,
                        provider=_ScriptedFetchProvider([payload]),
                        order_id=order_id,
                    )
                self.assertEqual(len(ledger.events), baseline)
                self.assertEqual(ledger.lookup_order(order_id)["state"], "PARTIALLY_FILLED")

    def test_invalid_fill_values_fail_closed(self) -> None:
        for label, payload in {
            "negative_quantity": _fill_payload(
                fills=[{"broker_fill_id": "X", "quantity": -5, "price_minor": 11600,
                        "event_time_ns": 1, "receive_time_ns": 2}]
            ),
            "negative_price": _fill_payload(
                fills=[{"broker_fill_id": "X", "quantity": 5, "price_minor": -11600,
                        "event_time_ns": 1, "receive_time_ns": 2}]
            ),
            "time_inversion": _fill_payload(
                fills=[{"broker_fill_id": "X", "quantity": 5, "price_minor": 11600,
                        "event_time_ns": 30, "receive_time_ns": 20}]
            ),
        }.items():
            with self.subTest(case=label):
                ledger, order_id = _submit_partial_from_fixture()
                baseline = len(ledger.events)
                with self.assertRaises(ValueError):
                    apply_broker_status_event(
                        ledger=ledger,
                        provider=_ScriptedFetchProvider([payload]),
                        order_id=order_id,
                    )
                self.assertEqual(len(ledger.events), baseline)
                self.assertEqual(len(ledger.project_fills()), 2)

    def test_ambiguous_and_unavailable_polls_do_not_mutate(self) -> None:
        for label, provider in {
            "ambiguous": _ScriptedFetchProvider(["ambiguous"]),
            "unavailable": _ScriptedFetchProvider(["unavailable"]),
            "error": _ScriptedFetchProvider(["error"]),
        }.items():
            with self.subTest(case=label):
                ledger, order_id = _submit_partial_from_fixture()
                baseline = len(ledger.events)
                result = apply_broker_status_event(ledger=ledger, provider=provider, order_id=order_id)
                self.assertFalse(result["advanced"])
                self.assertEqual(len(ledger.events), baseline)
                self.assertEqual(ledger.lookup_order(order_id)["state"], "PARTIALLY_FILLED")

    def test_terminal_order_short_circuits_without_provider_call(self) -> None:
        ledger, order_id = _submit_partial_from_fixture()
        provider = _fixture_provider()
        provider._replay.add_record(
            operation="fetch_order",
            match={"broker_order_id": BROKER_ORDER_ID},
            response=dict(FILLED_CUMULATIVE_PAYLOAD),
        )
        apply_broker_status_event(ledger=ledger, provider=provider, order_id=order_id)

        sentinel = _ScriptedFetchProvider([])
        result = apply_broker_status_event(ledger=ledger, provider=sentinel, order_id=order_id)
        self.assertFalse(result["advanced"])
        self.assertTrue(result["terminal"])
        self.assertEqual(sentinel.fetch_calls, 0)

    def test_missing_broker_order_id_raises(self) -> None:
        # Ambiguous submission resolves nothing: no broker id is ever recorded.
        store = TradierReplayStore()
        store.add_record(
            operation="place_order",
            match={"client_order_id": "cli-amb", "idempotency_key": "key-amb"},
            response={
                "broker_order_id": "TR-AMB-0001",
                "status": "ambiguous",
                "status_raw": "unknown",
                "event_time_ns": 1787000000000000000,
                "receive_time_ns": 1787000000000500000,
            },
        )
        ledger = _broker_ledger()
        submitted = submit_broker_paper_order(
            ledger=ledger,
            provider=_fixture_provider(store),
            instrument=dict(INSTRUMENT),
            side="BUY",
            quantity=10,
            observation_time=1787000000000000000,
            client_order_id="cli-amb",
            idempotency_key="key-amb",
        )
        self.assertTrue(submitted.get("ambiguous"))
        with self.assertRaises(ValueError) as ctx:
            apply_broker_status_event(
                ledger=ledger,
                provider=_ScriptedFetchProvider([]),
                order_id=submitted["order_id"],
            )
        self.assertIn("BROKER_ORDER_ID_UNKNOWN", str(ctx.exception))


class CreatedCancelConsistencyTests(unittest.TestCase):
    """E11: CREATED is non-cancellable on both paths with the same sentinel."""

    @staticmethod
    def _created_order(order_id: str) -> dict:
        return {
            "allocation_model": "test",
            "created_time": 1,
            "direction": "long",
            "instrument_id": "BIYA",
            "intent_id": "int-created",
            "order_id": order_id,
            "quantity": 10,
            "risk_decision": "APPROVE",
            "source_capability": "TEST",
            "state": "CREATED",
        }

    def test_interactive_created_cancel_is_invalid_state(self) -> None:
        ledger = _interactive_ledger()
        ledger.append_order(self._created_order("ord-created"), intent={"intent_id": "int-created"})
        with self.assertRaises(ValueError) as ctx:
            cancel_interactive_order(ledger=ledger, order_id="ord-created")
        self.assertIn("PAPER_ORDER_CANCEL_INVALID_STATE", str(ctx.exception))
        self.assertEqual(ledger.lookup_order("ord-created")["state"], "CREATED")
        self.assertEqual(ledger.open_order_count, 0)

    def test_broker_created_cancel_fails_closed_before_provider_call(self) -> None:
        ledger = _broker_ledger()
        ledger.append_order(self._created_order("ord-created"), intent={"intent_id": "int-created"})

        class _ExplodingProvider:
            def cancel_order(self, **_: object) -> None:
                raise AssertionError("provider must not be called for CREATED orders")

        with self.assertRaises(ValueError) as ctx:
            cancel_broker_paper_order(ledger=ledger, provider=_ExplodingProvider(), order_id="ord-created")
        self.assertIn("PAPER_ORDER_CANCEL_INVALID_STATE", str(ctx.exception))
        self.assertEqual(ledger.lookup_order("ord-created")["state"], "CREATED")


class SimulatorAllocationPersistenceTests(unittest.TestCase):
    """E9: participation caps accumulate across submissions sharing a bar."""

    @staticmethod
    def _bars(volume: int) -> list[dict]:
        return [
            {
                "available_time": 2_000_000,
                "normalized_event_id": "bar-1",
                "source": "TEST",
                "bar_payload": {"high": "116.50", "low": "116.00", "volume": volume},
            }
        ]

    def test_submissions_on_one_bar_aggregate_within_cap(self) -> None:
        # Default policy cap is 1/100: a 1000-share bar admits 10 shares total.
        ledger = _interactive_ledger()
        bars = self._bars(volume=1000)

        first = submit_interactive_order(
            ledger=ledger, bars=bars, symbol="BIYA", instrument_id="BIYA",
            side="BUY", quantity=10, observation_time=1_000_000,
            client_order_id="e9-c1", idempotency_key="e9-k1",
        )
        self.assertEqual(first["order"]["state"], "FILLED", "first submission must consume the cap")

        second = submit_interactive_order(
            ledger=ledger, bars=bars, symbol="BIYA", instrument_id="BIYA",
            side="BUY", quantity=10, observation_time=1_000_000,
            client_order_id="e9-c2", idempotency_key="e9-k2",
        )
        total_filled = sum(int(fill["fill_quantity"]) for fill in ledger.project_fills())
        self.assertLessEqual(total_filled, 10, "aggregate fill exceeded the bar participation cap")
        self.assertNotEqual(second["order"]["state"], "FILLED")
        self.assertEqual(second["decision"] if "decision" in second else second["order"]["risk_decision"], "APPROVE")

    def test_preview_does_not_consume_bar_capacity(self) -> None:
        ledger = _interactive_ledger()
        bars = self._bars(volume=1000)
        for index in range(2):
            preview = preview_interactive_order(
                ledger=ledger, bars=bars, symbol="BIYA", instrument_id="BIYA",
                side="BUY", quantity=10, observation_time=1_000_000,
                client_order_id=f"e9-pre-{index}", idempotency_key=f"e9-pre-{index}",
            )
            self.assertIsNotNone(preview.get("fill_preview"))
        self.assertEqual(ledger.project_fills(), [])

        submitted = submit_interactive_order(
            ledger=ledger, bars=bars, symbol="BIYA", instrument_id="BIYA",
            side="BUY", quantity=10, observation_time=1_000_000,
            client_order_id="e9-c3", idempotency_key="e9-k3",
        )
        self.assertEqual(submitted["order"]["state"], "FILLED")
        self.assertEqual(int(submitted["fill"]["fill_quantity"]), 10)

    def test_shared_parity_simulator_accumulates_like_internal_path(self) -> None:
        bars = self._bars(volume=1000)
        shared = BarConservativeSimulator(policy=dict(DEFAULT_RISK_POLICY))

        def _intent(client_id: str) -> dict:
            return build_user_order_intent(
                instrument=dict(INSTRUMENT),
                side="BUY",
                quantity=10,
                observation_time=1_000_000,
                client_order_id=client_id,
                idempotency_key=client_id,
            )

        _, order_one, fill_one = execute_normalized_intent_for_parity(
            intent=_intent("e9-p1"), policy=dict(DEFAULT_RISK_POLICY), bars=bars, simulator=shared,
        )
        _, order_two, fill_two = execute_normalized_intent_for_parity(
            intent=_intent("e9-p2"), policy=dict(DEFAULT_RISK_POLICY), bars=bars, simulator=shared,
        )
        self.assertIsNotNone(fill_one)
        self.assertIsNone(fill_two)
        self.assertEqual(order_one["state"], "FILLED")
        self.assertEqual(order_two["state"], "REJECTED")
        self.assertEqual(order_two["reason_codes"], ["SIM_NO_ELIGIBLE_VOLUME"])

    def test_normalize_broker_fill_rejects_bad_direction(self) -> None:
        from market_platform_foundation.providers.broker_execution import BrokerFillEvent

        fill_event = BrokerFillEvent(
            broker_fill_id="X",
            broker_order_id=BROKER_ORDER_ID,
            event_time_ns=1,
            price_minor=1,
            quantity=1,
            receive_time_ns=2,
        )
        with self.assertRaises(ValueError) as ctx:
            normalize_broker_fill(
                fill_event, order_id="o", instrument_id="BIYA", direction="sideways",
            )
        self.assertIn("BROKER_FILL_DIRECTION_INVALID", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
