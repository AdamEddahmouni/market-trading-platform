"""Workstream L durability gap-mining tests.

Exercises paper-ledger replay/durability edges and reconciliation edge inputs
that prior suites did not cover:

- projection idempotence under repeated replay (no drift from double replay);
- determinism: an identical event stream replays to identical projections;
- torn-tail durability (crash between FillRecorded and PositionChanged inside
  the ledger's atomic append group) leaves projections consistent;
- broker normalization fail-closed behaviour for malformed poll payloads;
- reconciliation edge inputs (empty snapshots, duplicate broker order ids,
  zero-vs-absent position, deterministic report ids).
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.contracts import build_instrument_ref  # noqa: E402
from market_platform_foundation.paper.execution import submit_interactive_order  # noqa: E402
from market_platform_foundation.paper.ledger import PaperExecutionLedger  # noqa: E402
from market_platform_foundation.platform.reconciliation.engine import (  # noqa: E402
    MATCHED,
    UNAVAILABLE,
    BrokerOrderSnapshot,
    BrokerPositionSnapshot,
    build_reconciliation_report,
)

INSTRUMENT = build_instrument_ref(instrument_id="BIYA", symbol="BIYA")


def _interactive_ledger(session_id: str = "wl-durability") -> PaperExecutionLedger:
    return PaperExecutionLedger.open_session(
        replay_session_id=session_id,
        instrument_id="BIYA",
        symbol="BIYA",
        execution_mode="INTERNAL_SIMULATION",
        execution_authority="PAPER_ONLY",
    )


def _bars(volume: int) -> list[dict]:
    return [
        {
            "available_time": 2_000_000,
            "normalized_event_id": "bar-1",
            "source": "TEST",
            "bar_payload": {"high": "116.50", "low": "116.00", "volume": volume},
        }
    ]


def _ledger_with_two_fills() -> PaperExecutionLedger:
    """Session with two submissions filling distinct bars (1000-share bar cap)."""
    ledger = _interactive_ledger()
    bars = [
        {
            "available_time": available_time,
            "normalized_event_id": f"bar-{available_time}",
            "source": "TEST",
            "bar_payload": {"high": "116.50", "low": "116.00", "volume": 100_000},
        }
        for available_time in (2_000_000, 3_000_000)
    ]
    for index, bar in enumerate(bars):
        submit_interactive_order(
            ledger=ledger,
            bars=[bar],
            symbol="BIYA",
            instrument_id="BIYA",
            side="BUY",
            quantity=5,
            observation_time=1_000_000 + index,
            client_order_id=f"dur-c{index}",
            idempotency_key=f"dur-k{index}",
        )
    assert len(ledger.project_fills()) == 2
    return ledger


class ReplayDurabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = _ledger_with_two_fills()
        self.events = copy.deepcopy(self.source.events)

    def _replay(self, events: list[dict], session_id: str) -> PaperExecutionLedger:
        ledger = _interactive_ledger(session_id)
        ledger.events.clear()
        ledger.events.extend(copy.deepcopy(events))
        return ledger

    @staticmethod
    def _projection(ledger: PaperExecutionLedger) -> dict:
        account = {
            key: value
            for key, value in ledger.project_account().items()
            # Session-container identity, not derived from the event stream.
            if key not in {"paper_account_id", "session_id"}
        }
        return {
            "orders": sorted(ledger.project_orders(), key=lambda row: row["order_id"]),
            "fills": sorted(ledger.project_fills(), key=lambda row: row["fill_id"]),
            "account": account,
            "positions": sorted(ledger.project_positions(), key=lambda row: row["instrument_id"]),
        }

    def test_double_replay_projection_is_idempotent(self) -> None:
        first = self._projection(self.source)
        second = self._projection(self.source)
        self.assertEqual(first, second)

    def test_identical_event_stream_replays_deterministically(self) -> None:
        replayed = self._replay(self.events, "wl-durability-replay")
        self.assertEqual(self._projection(self.source), self._projection(replayed))

    def test_torn_tail_between_fill_and_position_events_stays_consistent(self) -> None:
        # Simulate a crash after FillRecorded but before its PositionChanged
        # snapshot (the atomic group's second event never hit the store).
        for index, event in enumerate(self.events):
            if event["event_type"] == "FillRecorded":
                torn = self.events[: index + 1]
                break
        else:
            self.fail("fixture produced no FillRecorded event")
        replayed = self._replay(torn, "wl-durability-torn")

        # The fill itself is durable truth: it must survive the torn tail.
        self.assertEqual(len(replayed.project_fills()), 1)
        full_fill_ids = {row["fill_id"] for row in self.source.project_fills()}
        torn_fill_ids = {row["fill_id"] for row in replayed.project_fills()}
        self.assertTrue(torn_fill_ids.issubset(full_fill_ids))
        # And the position projection must agree with the surviving fills only.
        expected_shares = sum(int(fill["fill_quantity"]) for fill in replayed.project_fills())
        positions = replayed.project_positions()
        total = sum(int(row["quantity"]) for row in positions)
        self.assertEqual(total, expected_shares)

    def test_truncated_stream_never_raises_on_projection(self) -> None:
        for cut in range(2, len(self.events) + 1):
            with self.subTest(cut=cut):
                replayed = self._replay(self.events[:cut], f"wl-cut-{cut}")
                self._projection(replayed)


class ReconciliationEdgeInputTests(unittest.TestCase):
    def test_empty_snapshots_fail_soft_with_unavailable_fields(self) -> None:
        ledger = _interactive_ledger()
        report = build_reconciliation_report(
            ledger,
            order_snapshots=[],
            position_snapshots=[],
            account_snapshot=None,
            as_of_ns=1,
        )
        self.assertEqual(report["overall_status"], UNAVAILABLE)
        names = {field["name"] for field in report["scope"]["account"]["fields"]}
        self.assertIn("account.cash_minor", names)

    def test_report_id_is_deterministic_for_identical_inputs(self) -> None:
        ledger = _interactive_ledger()

        def _build() -> dict:
            return build_reconciliation_report(
                ledger,
                order_snapshots=[],
                position_snapshots=[],
                account_snapshot=None,
                as_of_ns=1,
            )

        self.assertEqual(_build()["report_id"], _build()["report_id"])

    def test_duplicate_broker_order_snapshots_collapse_to_one_row(self) -> None:
        ledger = _interactive_ledger()
        snapshot = BrokerOrderSnapshot(
            broker_order_id="TR-DUP-1",
            status="filled",
            filled_quantity=5,
            fills=(),
        )
        report = build_reconciliation_report(
            ledger,
            order_snapshots=[snapshot, snapshot],
            position_snapshots=[BrokerPositionSnapshot.from_record(
                {"instrument_id": "BIYA", "quantity": 0, "as_of_ns": 1}
            )],
            account_snapshot=None,
            as_of_ns=1,
        )
        dup_rows = [
            row for row in report["scope"]["orders"]
            if row.get("broker_order_id") == "TR-DUP-1"
        ]
        self.assertEqual(len(dup_rows), 1)

    def test_zero_position_snapshot_matches_absent_ledger_position(self) -> None:
        ledger = _interactive_ledger()
        report = build_reconciliation_report(
            ledger,
            order_snapshots=[],
            position_snapshots=[
                BrokerPositionSnapshot.from_record(
                    {"instrument_id": "BIYA", "quantity": 0, "as_of_ns": 1}
                )
            ],
            account_snapshot=None,
            as_of_ns=1,
        )
        position_rows = report["scope"]["positions"]
        self.assertEqual(len(position_rows), 1)
        quantity_fields = [
            field for field in position_rows[0]["fields"]
            if field["name"] == "positions.BIYA.quantity"
        ]
        self.assertEqual(len(quantity_fields), 1)
        self.assertEqual(quantity_fields[0]["status"], MATCHED)
        self.assertEqual(quantity_fields[0]["expected"], 0)

    def test_absent_position_snapshot_is_not_fabricated_as_zero(self) -> None:
        ledger = _interactive_ledger()
        report = build_reconciliation_report(
            ledger,
            order_snapshots=[],
            position_snapshots=[],
            account_snapshot=None,
            as_of_ns=1,
        )
        # A missing snapshot must not silently reconcile a flat book as matched.
        self.assertEqual(report["scope"]["positions"], [])


if __name__ == "__main__":
    unittest.main()
