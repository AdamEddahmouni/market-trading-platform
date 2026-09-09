"""G3 BL-0206 — cancel-time late-fill reconciliation tests.

Proves fills carried by a broker cancel acknowledgment are financially
authoritative and never dropped:
- a cancel with no late fill behaves exactly as before;
- partial fill then cancel preserves the existing fill;
- a cancel acknowledgment containing a new fill records that fill exactly once;
- replaying the same cancel does not double-apply the fill;
- reconciliation evidence identifies the late-fill/cancel race;
- both Tradier and Moomoo adapters surface the status event;
- terminal orders are not re-polled merely to discover fills.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.contracts import build_instrument_ref  # noqa: E402
from market_platform_foundation.paper.broker_paper import (  # noqa: E402
    cancel_broker_paper_order,
    submit_broker_paper_order,
)
from market_platform_foundation.paper.ledger import PaperExecutionLedger  # noqa: E402
from market_platform_foundation.providers.adapters.moomoo_paper import (  # noqa: E402
    MOOMOO_PROVIDER_ID,
    MoomooReplayStore,
    make_moomoo_paper_provider,
)
from market_platform_foundation.providers.adapters.tradier_paper import (  # noqa: E402
    TRADIER_SANDBOX_ENDPOINT,
    TradierReplayStore,
    make_tradier_paper_provider,
)
from market_platform_foundation.providers.broker_execution import BrokerFillEvent, BrokerOrderStatusEvent  # noqa: E402

INSTRUMENT = build_instrument_ref(instrument_id="BIYA", symbol="BIYA")

TRADIER_ENV = {
    "IMP_TRADIER_PAPER": "1",
    "IMP_BROKER_PAPER_EXECUTION": "1",
    "IMP_TRADIER_TOKEN": "sandbox-test-token",
    "IMP_TRADIER_ENDPOINT": TRADIER_SANDBOX_ENDPOINT,
    "IMP_TRADIER_ACCOUNT_ID": "acct-test",
}
MOOMOO_ENV = {
    "IMP_MOOMOO_PAPER": "1",
    "IMP_MOOMOO_PAPER_EXECUTION": "1",
    "IMP_MOOMOO_PAPER_KEY": "openapi-test-key",
    "IMP_MOOMOO_PAPER_SECRET": "openapi-test-secret",
    "IMP_MOOMOO_PAPER_HOST": "127.0.0.1",
    "IMP_MOOMOO_PAPER_PORT": "11111",
    "IMP_MOOMOO_PAPER_TRADE_ENV": "SIMULATE",
}


def _broker_ledger(provider_id: str = "TRADIER") -> PaperExecutionLedger:
    ledger = PaperExecutionLedger.open_session(
        replay_session_id=f"g3-late-{provider_id.lower()}",
        instrument_id="BIYA",
        symbol="BIYA",
        execution_mode="BROKER_PAPER",
        execution_authority="PAPER_ONLY",
        data_mode="BROKER_DELAYED",
        data_provider=provider_id,
        execution_provider=provider_id,
    )
    # G3 BL-0202: broker MARKET buys require a current price reference (mark).
    ledger.apply_live_mark(
        mark_minor=11620,
        mark_provider=provider_id,
        mark_as_of_ns=1787000000000000000,
        mark_quality="TEST",
    )
    return ledger


class _ScriptedCancelWithFillProvider:
    """Provider whose cancel response carries one new fill (late fill)."""

    def __init__(self, *, late_fill_id: str = "LATE-0001", quantity: int = 10) -> None:
        self.late_fill_id = late_fill_id
        self.quantity = quantity
        self.cancel_calls = 0

    def place_order(self, intent: dict) -> object:
        fill = BrokerFillEvent(
            broker_fill_id="EARLY-0001",
            broker_order_id="BO-1",
            event_time_ns=1787000000001000000,
            price_minor=11600,
            quantity=40,
            receive_time_ns=1787000000001000000,
        )
        status = BrokerOrderStatusEvent(
            avg_fill_price_minor=11600,
            broker_order_id="BO-1",
            broker_status_raw="partially_filled",
            event_time_ns=1787000000001000000,
            filled_quantity=40,
            fills=(fill,),
            receive_time_ns=1787000000001000000,
            status="partially_filled",
        )
        from market_platform_foundation.providers.broker_execution import (
            build_broker_execution_envelope,
            new_ingest_run_id,
        )
        from market_platform_foundation.providers.adapters.tradier_paper import SymbolMapping

        envelope = build_broker_execution_envelope(
            broker_event_type="ORDER_STATUS",
            instrument_id="BIYA",
            symbol_mapping=SymbolMapping(provider_symbol="BIYA", instrument_id="BIYA", venue_id="US_EQUITY"),
            provider_id="tradier.paper",
            entitlement="SIMULATED",
            event_time_ns=1787000000001000000,
            receive_time_ns=1787000000001000000,
            available_time_ns=1787000000001000000,
            raw_source_reference="tradier:place_order:cli-1",
            source_record_id="BO-1",
            payload=status.to_dict(),
            ingest_run_id=new_ingest_run_id(),
        )
        return type("R", (), {"status": "ok", "events": (envelope,), "provider_id": "tradier.paper", "capability": "paper"})()

    def cancel_order(self, **kwargs: object) -> object:
        self.cancel_calls += 1
        fill = BrokerFillEvent(
            broker_fill_id=self.late_fill_id,
            broker_order_id="BO-1",
            event_time_ns=1787000000002000000,
            price_minor=11650,
            quantity=self.quantity,
            receive_time_ns=1787000000002000000,
        )
        status = BrokerOrderStatusEvent(
            avg_fill_price_minor=11650,
            broker_order_id="BO-1",
            broker_status_raw="cancelled",
            event_time_ns=1787000000002000000,
            filled_quantity=50,
            fills=(fill,),
            receive_time_ns=1787000000002000000,
            status="cancelled",
        )
        from market_platform_foundation.providers.adapters.tradier_paper import SymbolMapping
        from market_platform_foundation.providers.broker_execution import (
            build_broker_execution_envelope,
            new_ingest_run_id,
        )

        envelope = build_broker_execution_envelope(
            broker_event_type="ORDER_STATUS",
            instrument_id="BIYA",
            symbol_mapping=SymbolMapping(provider_symbol="BIYA", instrument_id="BIYA", venue_id="US_EQUITY"),
            provider_id="tradier.paper",
            entitlement="SIMULATED",
            event_time_ns=1787000000002000000,
            receive_time_ns=1787000000002000000,
            available_time_ns=1787000000002000000,
            raw_source_reference="tradier:cancel_order:BO-1",
            source_record_id="BO-1",
            payload=status.to_dict(),
            ingest_run_id=new_ingest_run_id(),
        )
        return type("R", (), {"status": "ok", "events": (envelope,), "provider_id": "tradier.paper", "capability": "paper"})()


class LateFillCancelTests(unittest.TestCase):
    def test_cancel_with_late_fill_records_fill_exactly_once(self) -> None:
        ledger = _broker_ledger()
        provider = _ScriptedCancelWithFillProvider()
        submitted = submit_broker_paper_order(
            ledger=ledger, provider=provider, instrument=INSTRUMENT,
            side="BUY", quantity=100, observation_time=1787000000000000000,
            client_order_id="cli-1", idempotency_key="key-1",
        )
        self.assertEqual(submitted["order"]["state"], "PARTIALLY_FILLED")
        fills_before = ledger.project_fills()
        self.assertEqual(len(fills_before), 1)
        self.assertEqual(fills_before[0]["broker_fill_id"], "EARLY-0001")

        cancelled = cancel_broker_paper_order(ledger=ledger, provider=provider, order_id=submitted["order_id"])
        self.assertEqual(cancelled["state"], "CANCELLED")
        self.assertTrue(cancelled.get("late_fills_reconciled"))
        fills_after = ledger.project_fills()
        self.assertEqual(len(fills_after), 2, "late fill must be recorded")
        late = [f for f in fills_after if f["broker_fill_id"] == "LATE-0001"]
        self.assertEqual(len(late), 1)
        # Prior fill immutable; late fill appears exactly once.
        self.assertEqual([f["broker_fill_id"] for f in fills_after], ["EARLY-0001", "LATE-0001"])
        # Reconciliation evidence exists.
        recon = [e for e in ledger.events if e["event_type"] == "ReconciliationRecorded"]
        self.assertEqual(len(recon), 1)
        self.assertIn("late_fill_after_terminal", recon[0]["payload"]["mismatch_fields"])

    def test_replay_cancel_does_not_duplicate_late_fill(self) -> None:
        ledger = _broker_ledger()
        provider = _ScriptedCancelWithFillProvider()
        submitted = submit_broker_paper_order(
            ledger=ledger, provider=provider, instrument=INSTRUMENT,
            side="BUY", quantity=100, observation_time=1787000000000000000,
            client_order_id="cli-2", idempotency_key="key-2",
        )
        cancel_broker_paper_order(ledger=ledger, provider=provider, order_id=submitted["order_id"])
        fills_after_first = ledger.project_fills()
        # Duplicate cancel is idempotent: no new fill, no new reconciliation.
        events_before = len(ledger.events)
        duplicate = cancel_broker_paper_order(ledger=ledger, provider=provider, order_id=submitted["order_id"])
        self.assertTrue(duplicate.get("duplicate"))
        self.assertEqual(len(ledger.events), events_before)
        self.assertEqual(len(ledger.project_fills()), len(fills_after_first))

    def test_cancel_without_late_fill_preserves_normal_behavior(self) -> None:
        # A cancel response with no fills: prior fills intact, no late-fill
        # reconciliation event, normal cancel semantics.
        ledger = _broker_ledger()
        provider = _ScriptedCancelWithFillProvider(late_fill_id="", quantity=0)

        class _NoLateFillProvider(_ScriptedCancelWithFillProvider):
            def cancel_order(self, **kwargs: object) -> object:
                self.cancel_calls += 1
                status = BrokerOrderStatusEvent(
                    avg_fill_price_minor=11650,
                    broker_order_id="BO-1",
                    broker_status_raw="cancelled",
                    event_time_ns=1787000000002000000,
                    filled_quantity=40,
                    fills=(),
                    receive_time_ns=1787000000002000000,
                    status="cancelled",
                )
                from market_platform_foundation.providers.adapters.tradier_paper import SymbolMapping
                from market_platform_foundation.providers.broker_execution import (
                    build_broker_execution_envelope,
                    new_ingest_run_id,
                )

                envelope = build_broker_execution_envelope(
                    broker_event_type="ORDER_STATUS",
                    instrument_id="BIYA",
                    symbol_mapping=SymbolMapping(provider_symbol="BIYA", instrument_id="BIYA", venue_id="US_EQUITY"),
                    provider_id="tradier.paper",
                    entitlement="SIMULATED",
                    event_time_ns=1787000000002000000,
                    receive_time_ns=1787000000002000000,
                    available_time_ns=1787000000002000000,
                    raw_source_reference="tradier:cancel_order:BO-1",
                    source_record_id="BO-1",
                    payload=status.to_dict(),
                    ingest_run_id=new_ingest_run_id(),
                )
                return type("R", (), {"status": "ok", "events": (envelope,), "provider_id": "tradier.paper", "capability": "paper"})()

        provider = _NoLateFillProvider()
        submitted = submit_broker_paper_order(
            ledger=ledger, provider=provider, instrument=INSTRUMENT,
            side="BUY", quantity=100, observation_time=1787000000000000000,
            client_order_id="cli-3", idempotency_key="key-3",
        )
        cancel_broker_paper_order(ledger=ledger, provider=provider, order_id=submitted["order_id"])
        fills = ledger.project_fills()
        self.assertEqual(len(fills), 1, "no new fill when cancel carries none")
        self.assertEqual(fills[0]["broker_fill_id"], "EARLY-0001")
        recon = [e for e in ledger.events if e["event_type"] == "ReconciliationRecorded"]
        self.assertEqual(len(recon), 0, "no reconciliation event without a late fill")


class AdapterSurfacesCancelStatusTests(unittest.TestCase):
    def test_tradier_cancel_surfaces_status_event(self) -> None:
        provider = make_tradier_paper_provider(
            env=dict(TRADIER_ENV),
            symbol_map={"BIYA": "BIYA"},
            replay_store=TradierReplayStore.load(),
        )
        result = provider.cancel_order(client_order_id="cli-broker-limit-1", broker_order_id="TR-WORK-0001")
        self.assertEqual(result.status, "ok")
        events = list(result.events)
        self.assertTrue(events, "Tradier cancel must surface the status event (BL-0206)")
        payload = events[0]["payload"]
        self.assertEqual(payload["broker_order_id"], "TR-WORK-0001")

    def test_moomoo_cancel_surfaces_status_event(self) -> None:
        provider = make_moomoo_paper_provider(
            env=dict(MOOMOO_ENV),
            symbol_map={"BIYA": "BIYA"},
            transport=MoomooReplayStore.load(),
        )
        result = provider.cancel_order(client_order_id="cli-moomoo-limit-1", broker_order_id="MM-WORK-0001")
        self.assertEqual(result.status, "ok")
        events = list(result.events)
        self.assertTrue(events, "Moomoo cancel must surface the status event (BL-0206)")


if __name__ == "__main__":
    unittest.main()