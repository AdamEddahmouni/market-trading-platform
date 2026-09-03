"""Platformization P4 / sub-milestone 4A — broker paper execution tests.

Fixture-first: the Tradier adapter is exercised against recorded sandbox
responses (``tests/fixtures/providers/tradier_sandbox_orders.json``) with no
network. Covers the P4-* assertions (P4-PROV-001, P4-IDEM-001, P4-AMB-001,
P4-MAP-001, P4-FILL-001, P4-TRACE-001, P4-SAFE-001/002/003, P4-AUDIT-001).
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.envelope import validate_envelope  # noqa: E402
from market_platform_foundation.operating_modes import resolve_execution_authority  # noqa: E402
from market_platform_foundation.paper.contracts import build_instrument_ref  # noqa: E402
from market_platform_foundation.paper.broker_paper import (  # noqa: E402
    cancel_broker_paper_order,
    submit_broker_paper_order,
)
from market_platform_foundation.paper.execution import submit_interactive_order  # noqa: E402
from market_platform_foundation.paper.ledger import PaperExecutionLedger  # noqa: E402
from market_platform_foundation.risk.policy import build_risk_policy  # noqa: E402
from market_platform_foundation.providers.adapters.tradier_paper import (  # noqa: E402
    TRADIER_SANDBOX_ENDPOINT,
    TradierReplayStore,
    make_tradier_paper_provider,
)
from market_platform_foundation.providers.broker_execution import (  # noqa: E402
    build_broker_execution_envelope,
    is_ambiguous_broker_status,
    map_broker_status,
)
from market_platform_foundation.providers.composition import (  # noqa: E402
    ProviderComposition,
    with_broker_paper_execution,
)

INSTRUMENT = build_instrument_ref(instrument_id="BIYA", symbol="BIYA")

GATED_ENV = {
    "IMP_TRADIER_PAPER": "1",
    "IMP_BROKER_PAPER_EXECUTION": "1",
    "IMP_TRADIER_TOKEN": "sandbox-test-token",
    "IMP_TRADIER_ENDPOINT": TRADIER_SANDBOX_ENDPOINT,
    "IMP_TRADIER_ACCOUNT_ID": "acct-test",
}

SYMBOL_MAP = {"BIYA": "BIYA"}


def _broker_ledger() -> PaperExecutionLedger:
    ledger = PaperExecutionLedger.open_session(
        replay_session_id="p4-4a-session",
        instrument_id="BIYA",
        symbol="BIYA",
        execution_mode="BROKER_PAPER",
        execution_authority="PAPER_ONLY",
        data_mode="BROKER_DELAYED",
        data_provider="TRADIER",
        execution_provider="TRADIER",
        policy=build_risk_policy(
            max_order_notional_minor=100_000_00,
            max_position_notional_minor=1_000_000_00,
        ),
    )
    ledger.apply_live_mark(
        instrument_id="BIYA",
        mark_minor=11600,
        mark_provider="TRADIER_FIXTURE",
        mark_as_of_ns=1787000000000000000,
        mark_quality="PASS",
    )
    return ledger


def _provider(
    *,
    env: dict[str, str] | None = None,
    symbol_map: dict[str, str] | None = None,
    enable_identity_symbol: bool = True,
) -> object:
    return make_tradier_paper_provider(
        env=env if env is not None else dict(GATED_ENV),
        symbol_map=symbol_map if symbol_map is not None else dict(SYMBOL_MAP),
        replay_store=TradierReplayStore.load(),
        enable_identity_symbol=enable_identity_symbol,
    )


class BrokerPaperSafetyTests(unittest.TestCase):
    def test_p4_safe_001_gates_required(self) -> None:
        """No broker request is possible without every gate (P4-SAFE-001)."""
        provider = _provider(env={})
        result = provider.place_order({"instrument_id": "BIYA", "instrument": {"symbol": "BIYA", "instrument_id": "BIYA"}})
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, "EXECUTION_NOT_ENABLED")

        no_token = dict(GATED_ENV)
        no_token.pop("IMP_TRADIER_TOKEN")
        self.assertEqual(
            _provider(env=no_token).place_order({}).reason_code,
            "TRADIER_TOKEN_NOT_CONFIGURED",
        )

        prod = dict(GATED_ENV)
        prod["IMP_TRADIER_ENDPOINT"] = "https://api.tradier.com/v1"
        result = _provider(env=prod).place_order({})
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.reason_code, "TRADIER_PRODUCTION_ENDPOINT_BLOCKED")

        no_exec = dict(GATED_ENV)
        no_exec.pop("IMP_BROKER_PAPER_EXECUTION")
        self.assertEqual(_provider(env=no_exec).place_order({}).reason_code, "EXECUTION_NOT_ENABLED")

        no_tradier = dict(GATED_ENV)
        no_tradier.pop("IMP_TRADIER_PAPER")
        self.assertEqual(_provider(env=no_tradier).place_order({}).reason_code, "EXECUTION_NOT_ENABLED")

    def test_p4_safe_003_guard_unchanged(self) -> None:
        """submit_interactive_order is not loosened; broker entry point is distinct."""
        interactive = PaperExecutionLedger.open_session(
            replay_session_id="p4-guard",
            instrument_id="BIYA",
            symbol="BIYA",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="AUTHORIZED",
            data_mode="FIXTURE_REPLAY",
        )
        with self.assertRaises(ValueError):
            submit_broker_paper_order(
                ledger=interactive,
                provider=_provider(),
                instrument=INSTRUMENT,
                side="BUY",
                quantity=1,
                observation_time=1,
                client_order_id="cli-x",
                idempotency_key="key-x",
            )
        broker_ledger = _broker_ledger()
        with self.assertRaises(ValueError):
            submit_interactive_order(
                ledger=broker_ledger,
                bars=[],
                symbol="BIYA",
                instrument_id="BIYA",
                side="BUY",
                quantity=1,
                observation_time=1,
                client_order_id="cli-y",
                idempotency_key="key-y",
            )

    def test_broker_paper_authority_requires_own_gate(self) -> None:
        prior_bp = os.environ.pop("IMP_BROKER_PAPER_EXECUTION", None)
        prior_pp = os.environ.pop("IMP_PAPER_EXECUTION", None)
        try:
            self.assertEqual(resolve_execution_authority(requested_mode="BROKER_PAPER"), "BLOCKED")
            os.environ["IMP_BROKER_PAPER_EXECUTION"] = "1"
            self.assertEqual(resolve_execution_authority(requested_mode="BROKER_PAPER"), "PAPER_ONLY")
            os.environ.pop("IMP_BROKER_PAPER_EXECUTION")
            os.environ["IMP_PAPER_EXECUTION"] = "1"
            self.assertEqual(resolve_execution_authority(requested_mode="BROKER_PAPER"), "BLOCKED")
            self.assertEqual(resolve_execution_authority(requested_mode="INTERNAL_SIMULATION"), "AUTHORIZED")
        finally:
            for key, value in (("IMP_BROKER_PAPER_EXECUTION", prior_bp), ("IMP_PAPER_EXECUTION", prior_pp)):
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


class BrokerPaperMapTests(unittest.TestCase):
    def test_p4_map_001_unknown_broker_status_fails_closed(self) -> None:
        for status, imp in (
            ("accepted", "ACTIVATED"),
            ("working", "WORKING"),
            ("filled", "FILLED"),
            ("rejected", "REJECTED"),
            ("cancelled", "CANCELLED"),
            ("expired", "EXPIRED"),
        ):
            self.assertEqual(map_broker_status(status), imp)
        with self.assertRaises(ValueError):
            map_broker_status("mystery-status")
        self.assertTrue(is_ambiguous_broker_status("ambiguous"))

    def test_p4_map_001_unmapped_symbol_fails_closed(self) -> None:
        provider = _provider(enable_identity_symbol=False)
        with self.assertRaises(ValueError):
            provider.resolve_symbol_mapping(instrument_id="NOPE", symbol="NOPE")
        result = provider.place_order(
            {"instrument_id": "NOPE", "instrument": {"symbol": "NOPE", "instrument_id": "NOPE"}}
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason_code, "UNMAPPED_INSTRUMENT")


class BrokerPaperProvTests(unittest.TestCase):
    def test_p4_prov_001_envelope_is_canonical(self) -> None:
        mapping = _provider().resolve_symbol_mapping(instrument_id="BIYA", symbol="BIYA")
        envelope = build_broker_execution_envelope(
            broker_event_type="ORDER_STATUS",
            instrument_id="BIYA",
            symbol_mapping=mapping,
            provider_id="tradier.paper",
            entitlement="TRADIER_PAPER_SANDBOX",
            event_time_ns=1,
            receive_time_ns=2,
            available_time_ns=2,
            raw_source_reference="tradier:place_order:cli",
            source_record_id="TR-0001",
            payload={"broker_order_id": "TR-0001", "status": "filled", "event_time_ns": 1, "receive_time_ns": 2},
            ingest_run_id="ingest-test",
        )
        self.assertEqual(envelope["event_type"], "BROKER_EXECUTION_EVENT")
        self.assertEqual(envelope["provider_metadata"]["provider_id"], "tradier.paper")
        self.assertEqual(envelope["provider_metadata"]["raw_source_reference"], "tradier:place_order:cli")
        self.assertEqual(
            validate_envelope(
                envelope,
                timestamp_states={
                    "event_time": "REQUIRED",
                    "source_publish_time": "REQUIRED",
                    "live_received_time": "REQUIRED",
                    "historical_ingested_time": "FORBIDDEN",
                    "available_time": "REQUIRED",
                },
                acquisition_mode="live",
            ),
            [],
        )


class BrokerPaperSubmissionTests(unittest.TestCase):
    def test_p4_fill_001_broker_fill_drives_ledger(self) -> None:
        ledger = _broker_ledger()
        result = submit_broker_paper_order(
            ledger=ledger,
            provider=_provider(),
            instrument=INSTRUMENT,
            side="BUY",
            quantity=100,
            observation_time=1787000000000000000,
            client_order_id="cli-broker-market-1",
            idempotency_key="key-broker-market-1",
        )
        self.assertEqual(result["duplicate"], False)
        self.assertEqual(result["broker_order_id"], "TR-FILL-0001")
        self.assertEqual(result["broker_status"], "filled")
        self.assertIsNotNone(result["fill"])
        self.assertEqual(result["fill"]["fill_quantity"], 100)
        order = ledger.lookup_order(result["order_id"])
        self.assertEqual(order["state"], "FILLED")
        self.assertEqual(order["broker_order_id"], "TR-FILL-0001")
        fills = ledger.project_fills()
        self.assertEqual(len(fills), 1)
        self.assertEqual(fills[0]["fill_quantity"], 100)
        positions = ledger.project_positions()
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["quantity"], 100)
        self.assertEqual(positions[0]["side"], "LONG")
        # audit ids (P4-AUDIT-001)
        self.assertEqual(order["client_order_id"], "cli-broker-market-1")
        self.assertIn("intent_id", order)

    def test_p4_idem_001_no_duplicate_submission(self) -> None:
        store = TradierReplayStore.load()
        ledger = _broker_ledger()
        provider = make_tradier_paper_provider(env=dict(GATED_ENV), symbol_map=dict(SYMBOL_MAP), replay_store=store)
        submit_broker_paper_order(
            ledger=ledger,
            provider=provider,
            instrument=INSTRUMENT,
            side="BUY",
            quantity=100,
            observation_time=1787000000000000000,
            client_order_id="cli-broker-limit-1",
            idempotency_key="key-broker-limit-1",
            order_type="LIMIT",
            limit_price_minor=11600,
        )
        self.assertEqual(store.call_count("place_order"), 1)
        second = submit_broker_paper_order(
            ledger=ledger,
            provider=provider,
            instrument=INSTRUMENT,
            side="BUY",
            quantity=100,
            observation_time=1787000000000000000,
            client_order_id="cli-broker-limit-1",
            idempotency_key="key-broker-limit-1",
            order_type="LIMIT",
            limit_price_minor=11600,
        )
        self.assertEqual(second["duplicate"], True)
        self.assertEqual(store.call_count("place_order"), 1)

    def test_p4_amb_001_no_blind_retry(self) -> None:
        store = TradierReplayStore.load()
        ledger = _broker_ledger()
        provider = make_tradier_paper_provider(env=dict(GATED_ENV), symbol_map=dict(SYMBOL_MAP), replay_store=store)
        result = submit_broker_paper_order(
            ledger=ledger,
            provider=provider,
            instrument=INSTRUMENT,
            side="BUY",
            quantity=1,
            observation_time=1787000000000000000,
            client_order_id="cli-broker-ambiguous-1",
            idempotency_key="key-broker-ambiguous-1",
        )
        self.assertEqual(result["ambiguous"], True)
        self.assertEqual(store.call_count("place_order"), 1)
        # a retry resolves via the ledger idempotency key, never a re-submit
        retry = submit_broker_paper_order(
            ledger=ledger,
            provider=provider,
            instrument=INSTRUMENT,
            side="BUY",
            quantity=1,
            observation_time=1787000000000000000,
            client_order_id="cli-broker-ambiguous-1",
            idempotency_key="key-broker-ambiguous-1",
        )
        self.assertEqual(retry["duplicate"], True)
        self.assertEqual(store.call_count("place_order"), 1)
        # no fills, order stays opened-pending resolution
        self.assertEqual(ledger.project_fills(), [])
        order = ledger.lookup_order(result["order_id"])
        self.assertEqual(order["state"], "SUBMITTED")
        self.assertIn("BROKER_AMBIGUOUS_OUTCOME", order.get("reason_codes", []))

    def test_broker_reject_is_terminal_without_fills(self) -> None:
        ledger = _broker_ledger()
        result = submit_broker_paper_order(
            ledger=ledger,
            provider=_provider(),
            instrument=INSTRUMENT,
            side="BUY",
            quantity=100,
            observation_time=1787000000000000000,
            client_order_id="cli-broker-reject-1",
            idempotency_key="key-broker-reject-1",
        )
        self.assertEqual(result["broker_status"], "rejected")
        self.assertEqual(ledger.lookup_order(result["order_id"])["state"], "REJECTED")
        self.assertEqual(ledger.project_fills(), [])

    def test_working_limit_cancels_and_trace_reports_broker_fields(self) -> None:
        ledger = _broker_ledger()
        result = submit_broker_paper_order(
            ledger=ledger,
            provider=_provider(),
            instrument=INSTRUMENT,
            side="BUY",
            quantity=100,
            observation_time=1787000000000000000,
            client_order_id="cli-broker-limit-1",
            idempotency_key="key-broker-limit-1",
            order_type="LIMIT",
            limit_price_minor=11600,
        )
        order_id = result["order_id"]
        self.assertEqual(result["broker_order_id"], "TR-WORK-0001")
        self.assertEqual(ledger.lookup_order(order_id)["state"], "WORKING")

        cancelled = cancel_broker_paper_order(ledger=ledger, provider=_provider(), order_id=order_id)
        self.assertEqual(cancelled["state"], "CANCELLED")
        self.assertEqual(ledger.lookup_order(order_id)["state"], "CANCELLED")

        trace = ledger.project_execution_trace(order_id=order_id)
        self.assertEqual(trace["broker_order_id"], "TR-WORK-0001")
        self.assertEqual(trace["broker_order_submitted"], True)
        self.assertEqual(trace["broker_cancels"], 1)


class BrokerPaperCompositionTests(unittest.TestCase):
    def test_composition_slot_injection(self) -> None:
        composition = ProviderComposition()
        self.assertEqual(composition.paper_execution.provider_id, "stub.execution.disabled")
        with_broker_paper_execution(
            composition,
            env=dict(GATED_ENV),
            symbol_map=dict(SYMBOL_MAP),
            replay_store=TradierReplayStore.load(),
        )
        self.assertEqual(composition.paper_execution.provider_id, "tradier.paper")
        # a malformed intent fails closed (BROKER_REQUEST_INVALID), never a
        # blind network call from an under-specified request
        malformed = composition.paper_execution.place_order(
            {"instrument_id": "BIYA", "instrument": {"symbol": "BIYA", "instrument_id": "BIYA"}}
        )
        self.assertEqual(malformed.status, "unavailable")
        self.assertEqual(malformed.reason_code, "BROKER_REQUEST_INVALID")
        # a canonical intent round-trips through the injected slot
        result = composition.paper_execution.place_order(
            {
                "client_order_id": "cli-broker-limit-1",
                "created_time": 1787000000000000000,
                "desired_quantity": 100,
                "idempotency_key": "key-broker-limit-1",
                "instrument": {"instrument_id": "BIYA", "symbol": "BIYA"},
                "instrument_id": "BIYA",
                "intent_id": "intent-composition-1",
                "side": "BUY",
            }
        )
        self.assertEqual(result.status, "ok")


class BrokerPaperLifecycleFixtureTests(unittest.TestCase):
    """Contract assertions for tradier_sandbox_lifecycle.json (P4 4A wire prep).

    Covers the canonical statuses absent from tradier_sandbox_orders.json:
    partially_filled, accepted, expired. Each asserts the adapter normalizes
    the record into a canonical ORDER_STATUS envelope (ADR-PROV-001) without
    dropping fill provenance.
    """

    def _place(self, client_order_id: str, idempotency_key: str) -> object:
        return _provider().place_order(
            {
                "client_order_id": client_order_id,
                "created_time": 1787000000000000000,
                "desired_quantity": 100,
                "idempotency_key": idempotency_key,
                "instrument": {"instrument_id": "BIYA", "symbol": "BIYA"},
                "instrument_id": "BIYA",
                "intent_id": f"intent-{client_order_id}",
                "side": "BUY",
            }
        )

    def test_p4_wire_001_partially_filled_carries_split_fills(self) -> None:
        result = self._place("cli-broker-partial-1", "key-broker-partial-1")
        self.assertEqual(result.status, "ok")
        envelope = result.events[0]
        payload = envelope["payload"]
        self.assertEqual(payload["status"], "partially_filled")
        self.assertEqual(payload["broker_status_raw"], "partially_filled")
        self.assertEqual(len(payload["fills"]), 2)
        fill_ids = {fill["broker_fill_id"] for fill in payload["fills"]}
        self.assertEqual(fill_ids, {"TR-FL-0010", "TR-FL-0011"})
        self.assertEqual(sum(fill["quantity"] for fill in payload["fills"]), 40)
        self.assertEqual(envelope["source_record_id"], "TR-PART-0001")
        self.assertEqual(envelope["provider_metadata"]["provider_id"], "tradier.paper")

    def test_p4_wire_002_accepted_maps_open_ack(self) -> None:
        result = self._place("cli-broker-accepted-1", "key-broker-accepted-1")
        self.assertEqual(result.status, "ok")
        payload = result.events[0]["payload"]
        self.assertEqual(payload["status"], "accepted")
        self.assertEqual(payload["broker_status_raw"], "open")
        self.assertNotIn("fills", payload)
        # accepted is a real IMP state: ACTIVATED (P4-MAP-001)
        self.assertEqual(map_broker_status("accepted"), "ACTIVATED")
        self.assertNotIn("fills", payload)

    def test_p4_wire_003_expired_is_terminal_without_fills(self) -> None:
        result = self._place("cli-broker-expired-1", "key-broker-expired-1")
        self.assertEqual(result.status, "ok")
        payload = result.events[0]["payload"]
        self.assertEqual(payload["status"], "expired")
        self.assertEqual(payload["broker_status_raw"], "expired")
        self.assertNotIn("fills", payload)

    def test_p4_wire_004_lifecycle_fixture_records_are_distinct(self) -> None:
        store = TradierReplayStore.load()
        for operation in ("place_order",):
            count = sum(1 for r in store._records if r["operation"] == operation)
        self.assertGreaterEqual(count, 7)


if __name__ == "__main__":
    unittest.main()
