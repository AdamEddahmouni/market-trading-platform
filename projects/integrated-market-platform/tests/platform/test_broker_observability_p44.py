"""PLATFORM-P4-001 §5.1 — broker paper observability endpoint projections.

Covers the ``/paper/broker/*`` read-only observability surfaces backed by
``ui_api/broker_projections.py``:

- happy paths per endpoint driven by the recorded Tradier sandbox fixtures
  (``tests/fixtures/providers/tradier_sandbox_*.json``, no network);
- fail-closed degradation when the broker paper adapter is unconfigured,
  gated off, token-less, or pointed at a non-sandbox endpoint (structured
  sentinel payloads, never a crash);
- strict broker-view vs IMP-ledger-view separation (the two are never
  conflated, PLATFORM-P4-001 §5.1);
- deterministic output: identical inputs produce byte-stable canonical JSON
  (no wall clock, no random envelope ids projected).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes  # noqa: E402
from market_platform_foundation.paper.broker_paper import submit_broker_paper_order  # noqa: E402
from market_platform_foundation.paper.contracts import build_instrument_ref  # noqa: E402
from market_platform_foundation.paper.ledger import PaperExecutionLedger  # noqa: E402
from market_platform_foundation.platform.reconciliation import (  # noqa: E402
    BrokerOrderSnapshot,
    build_reconciliation_report,
    record_reconciliation,
)
from market_platform_foundation.providers.broker_execution import (  # noqa: E402
    BrokerAccountSnapshot,
    BrokerPositionSnapshot,
)
from market_platform_foundation.providers.adapters.tradier_paper import (  # noqa: E402
    TRADIER_SANDBOX_ENDPOINT,
    TradierReplayStore,
    make_tradier_paper_provider,
)
from market_platform_foundation.providers.composition import (  # noqa: E402
    ProviderComposition,
    configure_provider_composition,
    with_broker_paper_execution,
)
from market_platform_foundation.ui_api.broker_projections import (  # noqa: E402
    build_broker_account_payload,
    build_broker_health_payload,
    build_broker_orders_payload,
    build_broker_positions_payload,
    build_broker_reconciliation_payload,
)

INSTRUMENT = build_instrument_ref(instrument_id="BIYA", symbol="BIYA")
AS_OF_NS = 1787000000500000000

GATED_ENV = {
    "IMP_TRADIER_PAPER": "1",
    "IMP_BROKER_PAPER_EXECUTION": "1",
    "IMP_TRADIER_TOKEN": "sandbox-test-token",
    "IMP_TRADIER_ENDPOINT": TRADIER_SANDBOX_ENDPOINT,
    "IMP_TRADIER_ACCOUNT_ID": "acct-test",
}
SYMBOL_MAP = {"BIYA": "BIYA"}


def _ledger() -> PaperExecutionLedger:
    return PaperExecutionLedger.open_session(
        replay_session_id="p44-observability-session",
        instrument_id="BIYA",
        symbol="BIYA",
        execution_mode="BROKER_PAPER",
        execution_authority="PAPER_ONLY",
        data_mode="BROKER_DELAYED",
        data_provider="TRADIER",
        execution_provider="TRADIER",
    )


def _gated_provider() -> object:
    return make_tradier_paper_provider(
        env=dict(GATED_ENV),
        symbol_map=dict(SYMBOL_MAP),
        replay_store=TradierReplayStore.load(),
    )


def _store(ledger: PaperExecutionLedger) -> SimpleNamespace:
    """The projections only need ``paper_ledger`` from the ReplayStore."""
    return SimpleNamespace(paper_ledger=ledger)


def _configure(provider: object) -> None:
    composition = ProviderComposition()
    composition.paper_execution = provider  # type: ignore[assignment]
    configure_provider_composition(composition)


def _filled_ledger() -> PaperExecutionLedger:
    """BROKER_PAPER ledger with one filled broker order (TR-FILL-0001)."""
    ledger = _ledger()
    result = submit_broker_paper_order(
        ledger=ledger,
        provider=_gated_provider(),
        instrument=INSTRUMENT,
        side="BUY",
        quantity=100,
        observation_time=1787000000000000000,
        client_order_id="cli-broker-market-1",
        idempotency_key="key-broker-market-1",
    )
    assert result["broker_order_id"] == "TR-FILL-0001"
    return ledger


class ObservabilityTestCase(unittest.TestCase):
    def tearDown(self) -> None:
        configure_provider_composition(None)


class BrokerOrdersObservabilityTests(ObservabilityTestCase):
    def test_filled_order_happy_path_separates_views(self) -> None:
        ledger = _filled_ledger()
        _configure(_gated_provider())
        payload = build_broker_orders_payload(_store(ledger))
        self.assertTrue(payload["broker_view"]["available"])
        broker_orders = payload["broker_view"]["orders"]
        self.assertEqual(len(broker_orders), 1)
        record = broker_orders[0]
        # Broker-side view: verbatim broker lifecycle + provenance.
        self.assertEqual(record["broker_order_id"], "TR-FILL-0001")
        self.assertEqual(record["status"], "filled")
        self.assertEqual(record["broker_status_raw"], "filled")
        self.assertEqual(record["filled_quantity"], 100)
        self.assertEqual(record["avg_fill_price_minor"], 11620)
        self.assertEqual(
            record["provenance"]["raw_source_reference"],
            "tradier:fetch_order:TR-FILL-0001",
        )
        self.assertEqual(record["provenance"]["event_time_ns"], 1787000000105000000)
        self.assertEqual(record["provenance"]["receive_time_ns"], 1787000000105500000)
        self.assertNotIn("state", record)  # IMP lifecycle never leaks into broker view
        # IMP ledger view: IMP lifecycle states only.
        imp_orders = payload["imp_ledger_view"]["orders"]
        self.assertEqual(len(imp_orders), 1)
        self.assertEqual(imp_orders[0]["order_id"], record["imp_order_id"])
        self.assertEqual(imp_orders[0]["state"], "FILLED")
        self.assertEqual(payload["authority_boundary"], "BROKER_PAPER_OBSERVABILITY")

    def test_working_limit_order_is_visible_broker_side(self) -> None:
        ledger = _ledger()
        result = submit_broker_paper_order(
            ledger=ledger,
            provider=_gated_provider(),
            instrument=INSTRUMENT,
            side="BUY",
            quantity=10,
            order_type="LIMIT",
            limit_price_minor=11500,
            observation_time=1786999999000000000,
            client_order_id="cli-broker-limit-1",
            idempotency_key="key-broker-limit-1",
        )
        assert result["broker_order_id"] == "TR-WORK-0001"
        _configure(_gated_provider())
        payload = build_broker_orders_payload(_store(ledger))
        record = payload["broker_view"]["orders"][0]
        self.assertEqual(record["status"], "working")
        self.assertEqual(record["broker_status_raw"], "pending")
        imp_state = payload["imp_ledger_view"]["orders"][0]["state"]
        self.assertEqual(imp_state, "WORKING")

    def test_ambiguous_outcome_order_is_imp_view_only(self) -> None:
        ledger = _ledger()
        result = submit_broker_paper_order(
            ledger=ledger,
            provider=_gated_provider(),
            instrument=INSTRUMENT,
            side="BUY",
            quantity=100,
            observation_time=1787000000300000000,
            client_order_id="cli-broker-ambiguous-1",
            idempotency_key="key-broker-ambiguous-1",
        )
        assert result.get("ambiguous")
        _configure(_gated_provider())
        payload = build_broker_orders_payload(_store(ledger))
        # No broker order id was ever bound (P4-AMB-001): the submission
        # exists only in the IMP ledger view until fetch/reconciliation resolves.
        self.assertTrue(payload["broker_view"]["available"])
        self.assertEqual(payload["broker_view"]["orders"], [])
        imp_orders = payload["imp_ledger_view"]["orders"]
        self.assertEqual(len(imp_orders), 1)
        self.assertIsNone(imp_orders[0].get("broker_order_id"))

    def test_default_composition_stub_degrades_fail_closed(self) -> None:
        ledger = _filled_ledger()
        configure_provider_composition(ProviderComposition())  # disabled stub slot
        payload = build_broker_orders_payload(_store(ledger))
        self.assertFalse(payload["broker_view"]["available"])
        self.assertEqual(payload["broker_view"]["reason_code"], "EXECUTION_ADAPTER_NOT_IMPLEMENTED")
        # The IMP view stays fully readable next to the degraded broker view.
        self.assertEqual(len(payload["imp_ledger_view"]["orders"]), 1)

    def test_gated_off_adapter_reports_execution_not_enabled(self) -> None:
        ledger = _filled_ledger()
        _configure(make_tradier_paper_provider(env={}, replay_store=TradierReplayStore.load()))
        payload = build_broker_orders_payload(_store(ledger))
        self.assertFalse(payload["broker_view"]["available"])
        self.assertEqual(payload["broker_view"]["reason_code"], "EXECUTION_NOT_ENABLED")

    def test_missing_token_reports_tradier_token_not_configured(self) -> None:
        ledger = _filled_ledger()
        env = {k: v for k, v in GATED_ENV.items() if k != "IMP_TRADIER_TOKEN"}
        _configure(make_tradier_paper_provider(env=env, replay_store=TradierReplayStore.load()))
        payload = build_broker_account_payload(_store(ledger))
        self.assertFalse(payload["broker_view"]["available"])
        self.assertEqual(payload["broker_view"]["reason_code"], "TRADIER_TOKEN_NOT_CONFIGURED")


class BrokerAccountObservabilityTests(ObservabilityTestCase):
    def test_happy_path_keeps_cash_views_distinct(self) -> None:
        ledger = _filled_ledger()
        _configure(_gated_provider())
        payload = build_broker_account_payload(_store(ledger))
        self.assertTrue(payload["broker_view"]["available"])
        self.assertEqual(payload["broker_view"]["account"]["cash_minor"], 10000000)
        self.assertEqual(payload["broker_view"]["account"]["as_of_ns"], AS_OF_NS)
        imp_account = payload["imp_ledger_view"]["account"]
        self.assertNotEqual(imp_account["cash_minor"], 10000000)  # $1M IMP float vs sandbox cash
        self.assertIn("execution_mode", imp_account)

    def test_unconfigured_stub_degrades_fail_closed(self) -> None:
        ledger = _filled_ledger()
        configure_provider_composition(ProviderComposition())
        payload = build_broker_account_payload(_store(ledger))
        self.assertFalse(payload["broker_view"]["available"])
        self.assertEqual(payload["broker_view"]["reason_code"], "EXECUTION_ADAPTER_NOT_IMPLEMENTED")
        self.assertGreater(payload["imp_ledger_view"]["account"]["cash_minor"], 0)


class BrokerPositionsObservabilityTests(ObservabilityTestCase):
    def test_fixture_positions_happy_path(self) -> None:
        ledger = _filled_ledger()
        _configure(_gated_provider())
        payload = build_broker_positions_payload(_store(ledger))
        self.assertTrue(payload["broker_view"]["available"])
        self.assertEqual(payload["broker_view"]["positions"], [])
        # IMP view independently reports the filled position.
        self.assertEqual(len(payload["imp_ledger_view"]["positions"]), 1)
        self.assertEqual(payload["imp_ledger_view"]["positions"][0]["quantity"], 100)

    def test_non_empty_position_snapshot_is_projected(self) -> None:
        ledger = _filled_ledger()
        replay = TradierReplayStore()  # fresh: dispatch returns the first matching record
        replay.add_record(
            operation="fetch_positions",
            match={},
            response={
                "as_of_ns": AS_OF_NS,
                "positions": [
                    {
                        "instrument_id": "BIYA",
                        "quantity": 100,
                        "avg_price_minor": 11620,
                        "as_of_ns": AS_OF_NS,
                    }
                ],
            },
        )
        _configure(make_tradier_paper_provider(env=dict(GATED_ENV), symbol_map=dict(SYMBOL_MAP), replay_store=replay))
        payload = build_broker_positions_payload(_store(ledger))
        self.assertTrue(payload["broker_view"]["available"])
        self.assertEqual(
            payload["broker_view"]["positions"],
            [
                {
                    "as_of_ns": AS_OF_NS,
                    "avg_price_minor": 11620,
                    "broker_position_id": None,
                    "instrument_id": "BIYA",
                    "quantity": 100,
                }
            ],
        )


class ReconciliationObservabilityTests(ObservabilityTestCase):
    def test_pending_before_any_report(self) -> None:
        ledger = _filled_ledger()
        _configure(_gated_provider())
        payload = build_broker_reconciliation_payload(_store(ledger))
        self.assertEqual(payload["reconciliation_status"], "RECONCILIATION_PENDING")
        self.assertIsNone(payload["last_report"])
        self.assertEqual(payload["history"], [])

    def test_recorded_match_is_projected(self) -> None:
        ledger = _filled_ledger()
        report = build_reconciliation_report(
            ledger,
            order_snapshots=[
                BrokerOrderSnapshot(
                    broker_order_id="TR-FILL-0001",
                    status="filled",
                    filled_quantity=100,
                    avg_fill_price_minor=11620,
                    fills=({"quantity": 100, "price_minor": 11620},),
                    event_time_ns=1787000000100000000,
                    receive_time_ns=1787000000100500000,
                    raw_source_reference="tradier:fetch_order:TR-FILL-0001",
                )
            ],
            position_snapshots=[
                BrokerPositionSnapshot(
                    instrument_id="BIYA",
                    quantity=100,
                    avg_price_minor=11620,
                    as_of_ns=AS_OF_NS,
                )
            ],
            account_snapshot=BrokerAccountSnapshot(
                cash_minor=int(ledger.project_account()["cash_minor"]),
                buying_power_minor=int(ledger.project_account()["cash_minor"]),
                as_of_ns=AS_OF_NS,
            ),
            as_of_ns=AS_OF_NS,
        )
        record_reconciliation(ledger, report)
        _configure(_gated_provider())
        payload = build_broker_reconciliation_payload(_store(ledger))
        self.assertEqual(payload["reconciliation_status"], "BROKER_RECONCILED")
        self.assertEqual(payload["history"][0]["report_id"], report["report_id"])
        self.assertEqual(payload["last_report"]["report_id"], report["report_id"])

    def test_projection_is_read_only(self) -> None:
        ledger = _filled_ledger()
        before = len(ledger.events)
        _configure(_gated_provider())
        build_broker_reconciliation_payload(_store(ledger))
        self.assertEqual(len(ledger.events), before)


class BrokerHealthObservabilityTests(ObservabilityTestCase):
    def test_configured_tradier_adapter(self) -> None:
        ledger = _ledger()
        _configure(_gated_provider())
        payload = build_broker_health_payload(_store(ledger))
        self.assertEqual(payload["connection"], {"reason_code": None, "state": "CONFIGURED"})
        self.assertTrue(all(payload["configuration_gates"].values()))
        self.assertEqual(payload["sandbox_endpoint"], TRADIER_SANDBOX_ENDPOINT)
        self.assertTrue(payload["supports"]["fetch_account"])
        self.assertEqual(payload["adapter"], "TradierPaperExecutionProvider")

    def test_default_stub_is_unavailable_not_crashing(self) -> None:
        ledger = _ledger()
        configure_provider_composition(ProviderComposition())
        payload = build_broker_health_payload(_store(ledger))
        self.assertEqual(payload["connection"]["state"], "UNAVAILABLE")
        self.assertEqual(payload["connection"]["reason_code"], "EXECUTION_ADAPTER_NOT_IMPLEMENTED")
        self.assertIsNone(payload["configuration_gates"])
        self.assertFalse(payload["supports"]["fetch_account"])

    def test_production_endpoint_blocked(self) -> None:
        ledger = _ledger()
        env = dict(GATED_ENV, IMP_TRADIER_ENDPOINT="https://api.tradier.com/v1")
        _configure(make_tradier_paper_provider(env=env, replay_store=TradierReplayStore.load()))
        payload = build_broker_health_payload(_store(ledger))
        self.assertEqual(payload["connection"]["state"], "NOT_CONFIGURED")
        self.assertEqual(payload["connection"]["reason_code"], "TRADIER_PRODUCTION_ENDPOINT_BLOCKED")
        self.assertFalse(payload["configuration_gates"]["IMP_TRADIER_ENDPOINT_SANDBOX"])


class DeterminismTests(ObservabilityTestCase):
    def _payloads(self) -> tuple[bytes, bytes]:
        ledger = _filled_ledger()
        store = _store(ledger)
        builders = (
            build_broker_orders_payload,
            build_broker_account_payload,
            build_broker_positions_payload,
            build_broker_reconciliation_payload,
            build_broker_health_payload,
        )
        _configure(_gated_provider())
        first_bytes = b"".join(canonical_bytes(builder(store)) for builder in builders)
        _configure(_gated_provider())  # fresh provider instance, same configuration
        second_bytes = b"".join(canonical_bytes(builder(store)) for builder in builders)
        return first_bytes, second_bytes

    def test_identical_inputs_are_byte_stable(self) -> None:
        first_bytes, second_bytes = self._payloads()
        self.assertEqual(first_bytes, second_bytes)

    def test_no_random_ids_or_wall_clock_in_output(self) -> None:
        ledger = _filled_ledger()
        _configure(_gated_provider())
        blob = canonical_bytes(build_broker_orders_payload(_store(ledger)))
        self.assertNotIn(b"ingest_run_id", blob)
        self.assertNotIn(b"normalized_event_id", blob)


if __name__ == "__main__":
    unittest.main()
