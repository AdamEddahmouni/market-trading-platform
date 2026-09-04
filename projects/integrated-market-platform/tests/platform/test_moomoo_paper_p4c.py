"""Platformization P4 / sub-milestone 4C — Moomoo paper execution adapter tests.

Fixture-first, offline, CI-safe: exercises ``MoomooPaperExecutionProvider``
against recorded simulated-environment responses
(``tests/fixtures/providers/moomoo_paper_*.json``) behind the frozen
broker-neutral contract from 4A. No live orders; the observational Moomoo
runtime (``market_platform_foundation.market_data.*``) must stay untouched.
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
from market_platform_foundation.paper.broker_paper import (  # noqa: E402
    cancel_broker_paper_order,
    submit_broker_paper_order,
)
from market_platform_foundation.paper.contracts import build_instrument_ref  # noqa: E402
from market_platform_foundation.paper.execution import submit_interactive_order  # noqa: E402
from market_platform_foundation.paper.ledger import PaperExecutionLedger  # noqa: E402
from market_platform_foundation.providers.adapters.moomoo_paper import (  # noqa: E402
    MOOMOO_PROVIDER_ID,
    MoomooReplayStore,
    make_moomoo_paper_provider,
)
from market_platform_foundation.providers.composition import (  # noqa: E402
    ProviderComposition,
    with_broker_paper_execution,
    with_moomoo_paper_execution,
)

INSTRUMENT = build_instrument_ref(instrument_id="BIYA", symbol="BIYA")

GATED_ENV = {
    "IMP_MOOMOO_PAPER": "1",
    "IMP_MOOMOO_PAPER_EXECUTION": "1",
    "IMP_MOOMOO_PAPER_KEY": "openapi-test-key",
    "IMP_MOOMOO_PAPER_SECRET": "openapi-test-secret",
    "IMP_MOOMOO_PAPER_HOST": "127.0.0.1",
    "IMP_MOOMOO_PAPER_PORT": "11111",
    "IMP_MOOMOO_PAPER_TRADE_ENV": "SIMULATE",
}

SYMBOL_MAP = {"BIYA": "US.BIYA"}

CANONICAL_INTENT = {
    "client_order_id": "cli-moomoo-limit-1",
    "created_time": 1787000000000000000,
    "desired_quantity": 100,
    "idempotency_key": "key-moomoo-limit-1",
    "instrument": {"instrument_id": "BIYA", "symbol": "BIYA"},
    "instrument_id": "BIYA",
    "intent_id": "intent-moomoo-1",
    "side": "BUY",
}


def _moomoo_ledger() -> PaperExecutionLedger:
    return PaperExecutionLedger.open_session(
        replay_session_id="p4-4c-session",
        instrument_id="BIYA",
        symbol="BIYA",
        execution_mode="BROKER_PAPER",
        execution_authority="PAPER_ONLY",
        data_mode="BROKER_DELAYED",
        data_provider="MOOMOO",
        execution_provider="MOOMOO",
    )


def _provider(
    *,
    env: dict[str, str] | None = None,
    symbol_map: dict[str, str] | None = None,
    enable_identity_symbol: bool = False,
    replay_store: MoomooReplayStore | None = None,
) -> object:
    return make_moomoo_paper_provider(
        env=env if env is not None else dict(GATED_ENV),
        symbol_map=symbol_map if symbol_map is not None else dict(SYMBOL_MAP),
        transport=replay_store if replay_store is not None else MoomooReplayStore.load(),
        enable_identity_symbol=enable_identity_symbol,
    )


class MoomooPaperSafetyTests(unittest.TestCase):
    def test_p4c_safe_001_all_gates_required_zero_requests(self) -> None:
        """No broker request is possible without every gate (P4-SAFE-001)."""
        provider = _provider(env={})
        result = provider.place_order(dict(CANONICAL_INTENT))
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, "EXECUTION_NOT_ENABLED")
        self.assertEqual(provider._transport.call_count("place_order"), 0)

        for missing in (
            "IMP_MOOMOO_PAPER",
            "IMP_MOOMOO_PAPER_EXECUTION",
            "IMP_MOOMOO_PAPER_KEY",
            "IMP_MOOMOO_PAPER_SECRET",
        ):
            env = dict(GATED_ENV)
            env.pop(missing)
            probe = _provider(env=env)
            outcome = probe.place_order(dict(CANONICAL_INTENT))
            self.assertEqual(outcome.status, "unavailable", missing)
            self.assertEqual(probe._transport.call_count("place_order"), 0, missing)
        no_key = dict(GATED_ENV)
        no_key.pop("IMP_MOOMOO_PAPER_KEY")
        self.assertEqual(_provider(env=no_key).place_order({}).reason_code, "MOOMOO_CREDENTIALS_NOT_CONFIGURED")

    def test_p4c_safe_002_simulated_environment_guard(self) -> None:
        """Non-loopback hosts, bad ports, and non-SIMULATE trade envs are blocked."""
        wan = dict(GATED_ENV)
        wan["IMP_MOOMOO_PAPER_HOST"] = "gateway.moomoo.com"
        result = _provider(env=wan).place_order({})
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.reason_code, "MOOMOO_NON_LOCALHOST_HOST_BLOCKED")

        bad_port = dict(GATED_ENV)
        bad_port["IMP_MOOMOO_PAPER_PORT"] = "99999"
        self.assertEqual(_provider(env=bad_port).place_order({}).reason_code, "MOOMOO_PORT_INVALID")
        nan_port = dict(GATED_ENV)
        nan_port["IMP_MOOMOO_PAPER_PORT"] = "not-a-port"
        self.assertEqual(_provider(env=nan_port).place_order({}).reason_code, "MOOMOO_PORT_INVALID")

        real_env = dict(GATED_ENV)
        real_env["IMP_MOOMOO_PAPER_TRADE_ENV"] = "REAL"
        result = _provider(env=real_env).place_order({})
        self.assertEqual(result.status, "blocked")
        self.assertEqual(result.reason_code, "MOOMOO_PRODUCTION_TRADE_ENV_BLOCKED")
        self.assertEqual(_provider(env=real_env)._transport.call_count("place_order"), 0)

    def test_p4c_unmatched_transport_fails_closed(self) -> None:
        """No fixture record => explicit not-implemented, never a blind call."""
        provider = _provider()
        intent = dict(CANONICAL_INTENT, client_order_id="cli-unrecorded", idempotency_key="key-unrecorded")
        result = provider.place_order(intent)
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.reason_code, "MOOMOO_TRANSPORT_NOT_IMPLEMENTED")

    def test_p4c_broker_authority_gate_is_shared_and_mode_guards_unchanged(self) -> None:
        prior_bp = os.environ.pop("IMP_BROKER_PAPER_EXECUTION", None)
        try:
            self.assertEqual(resolve_execution_authority(requested_mode="BROKER_PAPER"), "BLOCKED")
            os.environ["IMP_BROKER_PAPER_EXECUTION"] = "1"
            self.assertEqual(resolve_execution_authority(requested_mode="BROKER_PAPER"), "PAPER_ONLY")
        finally:
            if prior_bp is None:
                os.environ.pop("IMP_BROKER_PAPER_EXECUTION", None)
            else:
                os.environ["IMP_BROKER_PAPER_EXECUTION"] = prior_bp

        interactive = PaperExecutionLedger.open_session(
            replay_session_id="p4-4c-guard",
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
                observation_time=1787000000000000000,
                client_order_id="cli-x",
                idempotency_key="key-x",
            )
        broker_ledger = _moomoo_ledger()
        with self.assertRaises(ValueError):
            submit_interactive_order(
                ledger=broker_ledger,
                bars=[],
                symbol="BIYA",
                instrument_id="BIYA",
                side="BUY",
                quantity=1,
                observation_time=1787000000000000000,
                client_order_id="cli-y",
                idempotency_key="key-y",
            )


class MoomooPaperMapTests(unittest.TestCase):
    def test_p4c_map_001_unknown_broker_status_never_advances_lifecycle(self) -> None:
        ledger = _moomoo_ledger()
        result = submit_broker_paper_order(
            ledger=ledger,
            provider=_provider(),
            instrument=INSTRUMENT,
            side="BUY",
            quantity=100,
            observation_time=1787000000000000000,
            client_order_id="cli-moomoo-unknown-1",
            idempotency_key="key-moomoo-unknown-1",
        )
        self.assertTrue(result["rejected"])
        self.assertIn("BROKER_STATUS_UNMAPPED", result["reason_codes"])
        order = ledger.lookup_order(result["order_id"])
        self.assertEqual(order["state"], "REJECTED")
        self.assertEqual(ledger.project_fills(), [])

    def test_p4c_map_001_unmapped_symbol_fails_closed(self) -> None:
        provider = _provider(enable_identity_symbol=False)
        with self.assertRaises(ValueError):
            provider.resolve_symbol_mapping(instrument_id="NOPE", symbol="NOPE")
        result = provider.place_order(
            {"instrument_id": "NOPE", "instrument": {"symbol": "NOPE", "instrument_id": "NOPE"}}
        )
        self.assertEqual(result.status, "error")
        self.assertEqual(result.reason_code, "UNMAPPED_INSTRUMENT")


class MoomooPaperProvTests(unittest.TestCase):
    def test_p4c_prov_001_envelope_is_canonical(self) -> None:
        provider = _provider()
        result = provider.place_order(dict(CANONICAL_INTENT))
        self.assertEqual(result.status, "ok")
        envelope = result.events[0]
        self.assertEqual(envelope["event_type"], "BROKER_EXECUTION_EVENT")
        metadata = envelope["provider_metadata"]
        self.assertEqual(metadata["provider_id"], MOOMOO_PROVIDER_ID)
        self.assertEqual(metadata["entitlement"], "MOOMOO_PAPER_SIMULATED")
        self.assertTrue(metadata["raw_source_reference"].startswith("moomoo:"))
        self.assertEqual(metadata["symbol_mapping"]["provider_symbol"], "US.BIYA")
        payload = envelope["payload"]
        self.assertEqual(payload["broker_order_id"], "MM-WORK-0001")
        self.assertEqual(payload["status"], "working")
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


class MoomooPaperSubmissionTests(unittest.TestCase):
    def test_p4c_fill_001_broker_fill_drives_ledger_in_broker_paper_only(self) -> None:
        ledger = _moomoo_ledger()
        result = submit_broker_paper_order(
            ledger=ledger,
            provider=_provider(),
            instrument=INSTRUMENT,
            side="BUY",
            quantity=100,
            observation_time=1787000000000000000,
            client_order_id="cli-moomoo-market-1",
            idempotency_key="key-moomoo-market-1",
        )
        self.assertFalse(result["duplicate"])
        self.assertEqual(result["broker_order_id"], "MM-FILL-0001")
        self.assertEqual(result["broker_status"], "filled")
        self.assertIsNotNone(result["fill"])
        self.assertEqual(result["fill"]["fill_quantity"], 100)
        order = ledger.lookup_order(result["order_id"])
        self.assertEqual(order["state"], "FILLED")
        self.assertEqual(order["broker_order_id"], "MM-FILL-0001")
        fills = ledger.project_fills()
        self.assertEqual(len(fills), 1)
        positions = ledger.project_positions()
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["quantity"], 100)
        self.assertEqual(positions[0]["side"], "LONG")
        self.assertEqual(order["client_order_id"], "cli-moomoo-market-1")

    def test_p4c_idem_001_retry_storm_never_duplicates(self) -> None:
        store = MoomooReplayStore.load()
        ledger = _moomoo_ledger()
        provider = make_moomoo_paper_provider(
            env=dict(GATED_ENV), symbol_map=dict(SYMBOL_MAP), transport=store
        )
        broker_ids: set[str] = set()
        first_order_id = None
        for attempt in range(5):
            result = submit_broker_paper_order(
                ledger=ledger,
                provider=provider,
                instrument=INSTRUMENT,
                side="BUY",
                quantity=100,
                observation_time=1787000000000000000,
                client_order_id="cli-moomoo-limit-1",
                idempotency_key="key-moomoo-limit-1",
                order_type="LIMIT",
                limit_price_minor=11600,
            )
            if attempt == 0:
                first_order_id = result["order_id"]
                self.assertFalse(result["duplicate"])
            else:
                self.assertTrue(result["duplicate"])
            if result.get("broker_order_id"):
                broker_ids.add(str(result["broker_order_id"]))
        # exactly one submission record, at most one broker order id
        self.assertEqual(store.call_count("place_order"), 1)
        self.assertLessEqual(len(broker_ids), 1)
        self.assertEqual(len(ledger.project_orders()), 1)
        self.assertEqual(first_order_id, ledger.project_orders()[0]["order_id"])

    def test_p4c_amb_001_disconnect_timeout_is_ambiguous_not_retried(self) -> None:
        store = MoomooReplayStore.load()
        ledger = _moomoo_ledger()
        provider = make_moomoo_paper_provider(
            env=dict(GATED_ENV), symbol_map=dict(SYMBOL_MAP), transport=store
        )
        result = submit_broker_paper_order(
            ledger=ledger,
            provider=provider,
            instrument=INSTRUMENT,
            side="BUY",
            quantity=1,
            observation_time=1787000000000000000,
            client_order_id="cli-moomoo-ambiguous-1",
            idempotency_key="key-moomoo-ambiguous-1",
        )
        self.assertTrue(result["ambiguous"])
        self.assertEqual(store.call_count("place_order"), 1)
        retry = submit_broker_paper_order(
            ledger=ledger,
            provider=provider,
            instrument=INSTRUMENT,
            side="BUY",
            quantity=1,
            observation_time=1787000000000000000,
            client_order_id="cli-moomoo-ambiguous-1",
            idempotency_key="key-moomoo-ambiguous-1",
        )
        self.assertTrue(retry["duplicate"])
        self.assertEqual(store.call_count("place_order"), 1)
        self.assertEqual(ledger.project_fills(), [])
        order = ledger.lookup_order(result["order_id"])
        self.assertEqual(order["state"], "SUBMITTED")
        self.assertIn("BROKER_AMBIGUOUS_OUTCOME", order.get("reason_codes", []))

    def test_p4c_reject_is_terminal_without_fills(self) -> None:
        ledger = _moomoo_ledger()
        result = submit_broker_paper_order(
            ledger=ledger,
            provider=_provider(),
            instrument=INSTRUMENT,
            side="BUY",
            quantity=100,
            observation_time=1787000000000000000,
            client_order_id="cli-moomoo-reject-1",
            idempotency_key="key-moomoo-reject-1",
        )
        self.assertEqual(result["broker_status"], "rejected")
        self.assertEqual(ledger.lookup_order(result["order_id"])["state"], "REJECTED")
        self.assertEqual(ledger.project_fills(), [])

    def test_p4c_working_limit_cancel_and_trace_reports_broker_fields(self) -> None:
        ledger = _moomoo_ledger()
        result = submit_broker_paper_order(
            ledger=ledger,
            provider=_provider(),
            instrument=INSTRUMENT,
            side="BUY",
            quantity=100,
            observation_time=1787000000000000000,
            client_order_id="cli-moomoo-limit-1",
            idempotency_key="key-moomoo-limit-1",
            order_type="LIMIT",
            limit_price_minor=11600,
        )
        order_id = result["order_id"]
        self.assertEqual(result["broker_order_id"], "MM-WORK-0001")
        self.assertEqual(ledger.lookup_order(order_id)["state"], "WORKING")

        cancelled = cancel_broker_paper_order(ledger=ledger, provider=_provider(), order_id=order_id)
        self.assertEqual(cancelled["state"], "CANCELLED")
        self.assertEqual(ledger.lookup_order(order_id)["state"], "CANCELLED")

        trace = ledger.project_execution_trace(order_id=order_id)
        self.assertEqual(trace["broker_order_id"], "MM-WORK-0001")
        self.assertTrue(trace["broker_order_submitted"])
        self.assertEqual(trace["broker_cancels"], 1)


class MoomooAdapterLocalMethodTests(unittest.TestCase):
    def test_fetch_order_returns_canonical_status_event(self) -> None:
        provider = _provider()
        result = provider.fetch_order("MM-FILL-0001")
        self.assertEqual(result.status, "ok")
        envelope = result.events[0]
        self.assertEqual(envelope["payload"]["broker_order_id"], "MM-FILL-0001")
        self.assertEqual(envelope["payload"]["status"], "filled")
        self.assertEqual(envelope["payload"]["fills"][0]["broker_fill_id"], "MM-FL-0001")

    def test_fetch_order_ungated_is_unavailable(self) -> None:
        provider = _provider(env={})
        result = provider.fetch_order("MM-FILL-0001")
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(provider._transport.call_count("fetch_order"), 0)

    def test_fetch_account_and_positions_round_trip(self) -> None:
        provider = _provider()
        account = provider.fetch_account()
        self.assertEqual(account.status, "ok")
        self.assertEqual(account.events[0]["trade_env"], "SIMULATE")
        self.assertEqual(account.events[0]["provider_id"], MOOMOO_PROVIDER_ID)
        positions = provider.fetch_positions()
        self.assertEqual(positions.status, "ok")
        self.assertEqual(positions.events[0]["positions"], [])


class MoomooObservationalSeparationTests(unittest.TestCase):
    def test_observation_runtime_has_no_execution_coupling(self) -> None:
        """The observational Moomoo runtime stays untouched by the execution adapter."""
        market_data = ROOT / "src" / "market_platform_foundation" / "market_data"
        for name in ("live_config.py", "live_runtime.py", "internal_simulation_gate.py"):
            source = (market_data / name).read_text(encoding="utf-8")
            self.assertNotIn("IMP_MOOMOO_PAPER", source, name)
            self.assertNotIn("moomoo_paper", source, name)
            self.assertNotIn("MoomooPaperExecutionProvider", source, name)
        adapter = (
            ROOT / "src" / "market_platform_foundation" / "providers" / "adapters" / "moomoo_paper.py"
        ).read_text(encoding="utf-8")
        self.assertFalse(
            any("market_data" in line and "import" in line for line in adapter.splitlines()),
            "adapter must not import observational runtime internals",
        )
        # the adapter never references observational-runtime internals or any
        # forbidden trade verb from the observational security boundary
        for forbidden in ("live_runtime", "live_config", "unlock_trade", "OpenTradeContext"):
            self.assertNotIn(forbidden, adapter, forbidden)


class MoomooPaperCompositionTests(unittest.TestCase):
    def test_composition_slot_injection(self) -> None:
        composition = ProviderComposition()
        self.assertEqual(composition.paper_execution.provider_id, "stub.execution.disabled")
        with_moomoo_paper_execution(
            composition,
            env=dict(GATED_ENV),
            symbol_map=dict(SYMBOL_MAP),
            transport=MoomooReplayStore.load(),
        )
        self.assertEqual(composition.paper_execution.provider_id, MOOMOO_PROVIDER_ID)
        malformed = composition.paper_execution.place_order({"instrument_id": "BIYA"})
        self.assertEqual(malformed.status, "unavailable")
        self.assertEqual(malformed.reason_code, "BROKER_REQUEST_INVALID")
        result = composition.paper_execution.place_order(dict(CANONICAL_INTENT))
        self.assertEqual(result.status, "ok")

    def test_tradier_and_moomoo_never_coactive(self) -> None:
        tradier_composition = ProviderComposition()
        with_broker_paper_execution(tradier_composition, env={}, symbol_map={})
        with self.assertRaises(ValueError):
            with_moomoo_paper_execution(tradier_composition, env=dict(GATED_ENV), symbol_map=dict(SYMBOL_MAP))
        self.assertEqual(tradier_composition.paper_execution.provider_id, "tradier.paper")

        moomoo_composition = ProviderComposition()
        with_moomoo_paper_execution(moomoo_composition, env=dict(GATED_ENV), symbol_map=dict(SYMBOL_MAP))
        with self.assertRaises(ValueError):
            with_broker_paper_execution(moomoo_composition, env={}, symbol_map={})
        self.assertEqual(moomoo_composition.paper_execution.provider_id, MOOMOO_PROVIDER_ID)

        # replacing the same provider remains allowed (reconfiguration)
        with_moomoo_paper_execution(moomoo_composition, env={}, symbol_map={})
        self.assertEqual(moomoo_composition.paper_execution.provider_id, MOOMOO_PROVIDER_ID)


if __name__ == "__main__":
    unittest.main()
