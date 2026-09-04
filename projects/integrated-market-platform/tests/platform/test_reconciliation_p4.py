"""Platformization P4 / sub-milestone 4B — reconciliation engine tests.

Proves the PLATFORM-P4-001 reconciliation assertions:

- ``P4-REC-001``: reports are deterministic under identical snapshots
  (content-derived report id, no wall clock), and mismatches are recorded as
  append-only ledger events, never patched in place.
- ``P4-REC-002``: no unexplained ledger/broker mismatch is silently absorbed;
  an unresolved difference either has a root-cause correction event or is
  explicitly held open in ``RECONCILIATION_HOLD``.

Broker snapshots are constructed from the canonical models
(``BrokerOrderSnapshot`` / ``BrokerPositionSnapshot`` / ``BrokerAccountSnapshot``);
the engine itself is offline and performs no network I/O.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.contracts import build_instrument_ref  # noqa: E402
from market_platform_foundation.paper.broker_paper import submit_broker_paper_order  # noqa: E402
from market_platform_foundation.paper.ledger import EVENT_TYPES, PaperExecutionLedger  # noqa: E402
from market_platform_foundation.platform.reconciliation import (  # noqa: E402
    MATCHED,
    MISMATCH,
    UNAVAILABLE,
    BrokerOrderSnapshot,
    ReconciliationViolation,
    assert_no_unexplained_mismatch,
    build_reconciliation_report,
    hold_reconciliation,
    record_reconciliation,
    resolve_reconciliation_field,
)
from market_platform_foundation.providers.adapters.tradier_paper import (  # noqa: E402
    TRADIER_SANDBOX_ENDPOINT,
    TradierReplayStore,
    make_tradier_paper_provider,
)
from market_platform_foundation.providers.broker_execution import (  # noqa: E402
    BrokerAccountSnapshot,
    BrokerPositionSnapshot,
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


def _broker_ledger() -> PaperExecutionLedger:
    return PaperExecutionLedger.open_session(
        replay_session_id="p4-4b-session",
        instrument_id="BIYA",
        symbol="BIYA",
        execution_mode="BROKER_PAPER",
        execution_authority="PAPER_ONLY",
        data_mode="BROKER_DELAYED",
        data_provider="TRADIER",
        execution_provider="TRADIER",
    )


def _provider() -> object:
    return make_tradier_paper_provider(
        env=dict(GATED_ENV),
        symbol_map=dict(SYMBOL_MAP),
        replay_store=TradierReplayStore.load(),
    )


def _filled_ledger() -> PaperExecutionLedger:
    """BROKER_PAPER ledger with one filled broker order (TR-FILL-0001, 100 @ 11620)."""
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
    assert result["broker_order_id"] == "TR-FILL-0001"
    assert result["broker_status"] == "filled"
    return ledger


def _order_snapshot(
    *,
    broker_order_id: str = "TR-FILL-0001",
    status: str = "filled",
    filled_quantity: int = 100,
    avg_fill_price_minor: int | None = 11620,
    fills: tuple[dict, ...] | None = ({"quantity": 100, "price_minor": 11620},),
) -> BrokerOrderSnapshot:
    return BrokerOrderSnapshot(
        broker_order_id=broker_order_id,
        status=status,
        filled_quantity=filled_quantity,
        avg_fill_price_minor=avg_fill_price_minor,
        fills=fills,
        event_time_ns=1787000000100000000,
        receive_time_ns=1787000000100500000,
        raw_source_reference=f"tradier:fetch_order:{broker_order_id}",
    )


def _consistent_snapshots(ledger: PaperExecutionLedger) -> dict[str, object]:
    account = ledger.project_account()
    return {
        "orders": [_order_snapshot()],
        "positions": [
            BrokerPositionSnapshot(
                instrument_id="BIYA",
                quantity=100,
                avg_price_minor=11620,
                as_of_ns=AS_OF_NS,
            )
        ],
        "account": BrokerAccountSnapshot(
            cash_minor=int(account["cash_minor"]),
            buying_power_minor=int(account["cash_minor"]),
            as_of_ns=AS_OF_NS,
        ),
    }


def _report(ledger: PaperExecutionLedger, snapshots: dict[str, object]) -> dict:
    return build_reconciliation_report(
        ledger,
        order_snapshots=snapshots["orders"],  # type: ignore[arg-type]
        position_snapshots=snapshots["positions"],  # type: ignore[arg-type]
        account_snapshot=snapshots["account"],  # type: ignore[arg-type]
        as_of_ns=AS_OF_NS,
    )


class ReconciliationDeterminismTests(unittest.TestCase):
    """P4-REC-001: deterministic reports and append-only recording."""

    def test_identical_inputs_produce_identical_reports(self) -> None:
        ledger = _filled_ledger()
        snapshots = _consistent_snapshots(ledger)
        first = _report(ledger, snapshots)
        second = _report(ledger, snapshots)
        self.assertEqual(first, second)
        self.assertEqual(first["report_id"], second["report_id"])
        self.assertEqual(first["overall_status"], MATCHED)

    def test_report_id_is_content_derived(self) -> None:
        ledger = _filled_ledger()
        snapshots = _consistent_snapshots(ledger)
        base = _report(ledger, snapshots)
        drifted = dict(snapshots)
        drifted_orders = [_order_snapshot(filled_quantity=90)]
        drifted["orders"] = drifted_orders  # type: ignore[assignment]
        changed = _report(ledger, drifted)  # type: ignore[arg-type]
        self.assertNotEqual(base["report_id"], changed["report_id"])
        self.assertEqual(changed["overall_status"], MISMATCH)

    def test_recording_is_append_only(self) -> None:
        ledger = _filled_ledger()
        snapshots = _consistent_snapshots(ledger)
        drifted_orders = [_order_snapshot(filled_quantity=90)]
        snapshots["orders"] = drifted_orders  # type: ignore[assignment]
        report = _report(ledger, snapshots)
        self.assertEqual(report["overall_status"], MISMATCH)

        record_reconciliation(ledger, report)
        record_reconciliation(ledger, report)
        recorded = [
            event
            for event in ledger.events
            if event["event_type"] == "ReconciliationRecorded"
        ]
        self.assertEqual(len(recorded), 2)
        # nothing was patched: both events carry the same report id and the
        # underlying order/fill events are untouched
        self.assertEqual({event["payload"]["report_id"] for event in recorded}, {report["report_id"]})
        self.assertEqual(len(ledger.project_fills()), 1)

    def test_reconciliation_event_types_are_registered(self) -> None:
        self.assertIn("ReconciliationRecorded", EVENT_TYPES)
        self.assertIn("ReconciliationCorrectionRecorded", EVENT_TYPES)


class ReconciliationMatchedTests(unittest.TestCase):
    def test_fully_matched_report_reconciles(self) -> None:
        ledger = _filled_ledger()
        report = _report(ledger, _consistent_snapshots(ledger))
        self.assertEqual(report["overall_status"], MATCHED)
        self.assertEqual(report["mismatch_fields"], [])
        self.assertEqual(report["unavailable_fields"], [])
        self.assertEqual(report["counts"]["orders"], 1)
        self.assertEqual(report["counts"]["matched_orders"], 1)
        self.assertEqual(report["counts"]["mismatch_orders"], 0)
        self.assertEqual(report["scope"]["orders"][0]["order_id"], ledger.project_orders()[0]["order_id"])

    def test_recorded_match_sets_broker_reconciled(self) -> None:
        ledger = _filled_ledger()
        record_reconciliation(ledger, _report(ledger, _consistent_snapshots(ledger)))
        risk = ledger.project_risk()
        self.assertEqual(risk["reconciliation_status"], "BROKER_RECONCILED")
        self.assertEqual(risk["last_reconciliation"]["overall_status"], MATCHED)
        # before any report, BROKER_PAPER is pending
        fresh = _broker_ledger()
        self.assertEqual(fresh.project_risk()["reconciliation_status"], "RECONCILIATION_PENDING")


class ReconciliationMismatchTests(unittest.TestCase):
    """P4-REC-002: mismatches surface and are never silently absorbed."""

    def test_quantity_drift_is_a_mismatch(self) -> None:
        ledger = _filled_ledger()
        snapshots = _consistent_snapshots(ledger)
        snapshots["orders"] = [_order_snapshot(filled_quantity=90)]  # type: ignore[assignment]
        report = _report(ledger, snapshots)
        self.assertEqual(report["overall_status"], MISMATCH)
        self.assertIn("orders.TR-FILL-0001.filled_quantity", report["mismatch_fields"])
        self.assertIn("FILLED_QUANTITY_DRIFT", report["scope"]["orders"][0]["reason_codes"])

    def test_stale_position_snapshot_is_a_mismatch(self) -> None:
        ledger = _filled_ledger()
        snapshots = _consistent_snapshots(ledger)
        snapshots["positions"] = [  # type: ignore[assignment]
            BrokerPositionSnapshot(
                instrument_id="BIYA",
                quantity=80,
                avg_price_minor=11620,
                as_of_ns=AS_OF_NS,
            )
        ]
        report = _report(ledger, snapshots)
        self.assertEqual(report["overall_status"], MISMATCH)
        self.assertIn("positions.BIYA.quantity", report["mismatch_fields"])

    def test_cash_drift_is_a_mismatch(self) -> None:
        ledger = _filled_ledger()
        snapshots = _consistent_snapshots(ledger)
        cash = int(ledger.project_account()["cash_minor"])
        snapshots["account"] = BrokerAccountSnapshot(  # type: ignore[assignment]
            cash_minor=cash + 1000,
            buying_power_minor=cash,
            as_of_ns=AS_OF_NS,
        )
        report = _report(ledger, snapshots)
        self.assertEqual(report["overall_status"], MISMATCH)
        self.assertIn("account.cash_minor", report["mismatch_fields"])

    def test_broker_order_missing_from_ledger_is_a_mismatch(self) -> None:
        ledger = _filled_ledger()
        snapshots = _consistent_snapshots(ledger)
        snapshots["orders"] = [  # type: ignore[assignment]
            _order_snapshot(),
            _order_snapshot(broker_order_id="TR-UNKNOWN-99", status="filled", filled_quantity=1),
        ]
        report = _report(ledger, snapshots)
        self.assertEqual(report["overall_status"], MISMATCH)
        self.assertIn("orders.TR-UNKNOWN-99.presence", report["mismatch_fields"])
        self.assertIn("BROKER_ORDER_MISSING_FROM_LEDGER", report["scope"]["orders"][1]["reason_codes"])

    def test_unexplained_mismatch_fails_closed(self) -> None:
        ledger = _filled_ledger()
        snapshots = _consistent_snapshots(ledger)
        snapshots["orders"] = [_order_snapshot(filled_quantity=90)]  # type: ignore[assignment]
        report = _report(ledger, snapshots)
        record_reconciliation(ledger, report)
        self.assertEqual(ledger.project_risk()["reconciliation_status"], MISMATCH)
        with self.assertRaises(ReconciliationViolation):
            assert_no_unexplained_mismatch(ledger, report)


class ReconciliationHoldTests(unittest.TestCase):
    def test_held_report_enters_reconciliation_hold(self) -> None:
        ledger = _filled_ledger()
        snapshots = _consistent_snapshots(ledger)
        snapshots["orders"] = [_order_snapshot(filled_quantity=90)]  # type: ignore[assignment]
        report = _report(ledger, snapshots)
        record_reconciliation(ledger, report)
        hold_reconciliation(
            ledger,
            report_id=report["report_id"],
            reason_codes=["OPERATOR_INVESTIGATING"],
            operator_id="PRINCIPAL-001",
        )
        risk = ledger.project_risk()
        self.assertEqual(risk["reconciliation_status"], "RECONCILIATION_HOLD")
        # a held report is not an unexplained mismatch (P4-REC-002)
        assert_no_unexplained_mismatch(ledger, report)


class ReconciliationResolveTests(unittest.TestCase):
    def test_resolved_field_reconciles(self) -> None:
        ledger = _filled_ledger()
        snapshots = _consistent_snapshots(ledger)
        snapshots["orders"] = [_order_snapshot(filled_quantity=90)]  # type: ignore[assignment]
        report = _report(ledger, snapshots)
        record_reconciliation(ledger, report)
        self.assertEqual(ledger.project_risk()["reconciliation_status"], MISMATCH)
        resolve_reconciliation_field(
            ledger,
            report_id=report["report_id"],
            field="orders.TR-FILL-0001.filled_quantity",
            observed_value=90,
            raw_source_reference="tradier:fetch_order:TR-FILL-0001",
            reason_codes=["BROKER_PARTIAL_FILL_RECORDING_DELAY"],
        )
        self.assertEqual(ledger.project_risk()["reconciliation_status"], "BROKER_RECONCILED")
        assert_no_unexplained_mismatch(ledger, report)

    def test_partial_resolution_remains_mismatch(self) -> None:
        ledger = _filled_ledger()
        snapshots = _consistent_snapshots(ledger)
        snapshots["orders"] = [  # type: ignore[assignment]
            _order_snapshot(filled_quantity=90, status="partially_filled"),
        ]
        report = _report(ledger, snapshots)
        record_reconciliation(ledger, report)
        self.assertIn("orders.TR-FILL-0001.state", report["mismatch_fields"])
        resolve_reconciliation_field(
            ledger,
            report_id=report["report_id"],
            field="orders.TR-FILL-0001.filled_quantity",
            observed_value=90,
            raw_source_reference="tradier:fetch_order:TR-FILL-0001",
        )
        # the state field is still unexplained -> still MISMATCH, never absorbed
        self.assertEqual(ledger.project_risk()["reconciliation_status"], MISMATCH)
        with self.assertRaises(ReconciliationViolation):
            assert_no_unexplained_mismatch(ledger, report)


class ReconciliationUnavailableTests(unittest.TestCase):
    def test_missing_account_snapshot_is_unavailable(self) -> None:
        ledger = _filled_ledger()
        snapshots = _consistent_snapshots(ledger)
        snapshots["account"] = None  # type: ignore[assignment]
        report = _report(ledger, snapshots)
        self.assertEqual(report["overall_status"], UNAVAILABLE)
        self.assertIn("account.cash_minor", report["unavailable_fields"])
        record_reconciliation(ledger, report)
        self.assertEqual(ledger.project_risk()["reconciliation_status"], "RECONCILIATION_PENDING")

    def test_ledger_order_missing_from_snapshot_is_unavailable(self) -> None:
        ledger = _filled_ledger()
        snapshots = _consistent_snapshots(ledger)
        snapshots["orders"] = []  # type: ignore[assignment]
        report = _report(ledger, snapshots)
        self.assertEqual(report["overall_status"], UNAVAILABLE)
        self.assertIn("orders.TR-FILL-0001.state", report["unavailable_fields"])
        self.assertIn("BROKER_ORDER_NOT_IN_SNAPSHOT", report["scope"]["orders"][0]["reason_codes"])

    def test_ambiguous_broker_status_is_unavailable(self) -> None:
        ledger = _filled_ledger()
        snapshots = _consistent_snapshots(ledger)
        snapshots["orders"] = [_order_snapshot(status="ambiguous")]  # type: ignore[assignment]
        report = _report(ledger, snapshots)
        self.assertEqual(report["overall_status"], UNAVAILABLE)
        self.assertIn("orders.TR-FILL-0001.state", report["unavailable_fields"])


class InternalModeRegressionTests(unittest.TestCase):
    def test_internal_simulation_stays_internal_authoritative(self) -> None:
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="p4-4b-internal",
            instrument_id="BIYA",
            symbol="BIYA",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="AUTHORIZED",
            data_mode="FIXTURE_REPLAY",
        )
        self.assertEqual(ledger.project_risk()["reconciliation_status"], "INTERNAL_AUTHORITATIVE")


if __name__ == "__main__":
    unittest.main()
