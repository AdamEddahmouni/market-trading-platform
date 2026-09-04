"""E14 regression — broker fill-id and timestamp integrity.

Backfilled fill ids are identity-bearing: they must be derived from the fill's
own timestamps (event/receive) in addition to order, poll index and economics,
so same-price same-size fills at different event times never collide.
``BrokerFillEvent.from_record`` must fail closed (BROKER_FILL_TIMESTAMP_MISSING)
on a fill record without ``event_time_ns`` instead of coercing to 0.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.providers.broker_execution import (
    BrokerFillEvent,
    BrokerOrderStatusEvent,
    ensure_broker_fill_ids,
)


def _fill(*, event_time_ns: int, receive_time_ns: int, price_minor: int = 11600, quantity: int = 25) -> BrokerFillEvent:
    return BrokerFillEvent(
        broker_fill_id="",
        broker_order_id="TR-1",
        event_time_ns=event_time_ns,
        price_minor=price_minor,
        quantity=quantity,
        receive_time_ns=receive_time_ns,
    )


def _status_event(fills: tuple[BrokerFillEvent, ...]) -> BrokerOrderStatusEvent:
    return BrokerOrderStatusEvent(
        broker_order_id="TR-1",
        broker_status_raw="partially_filled",
        event_time_ns=1787000000600000000,
        receive_time_ns=1787000000600500000,
        status="PARTIALLY_FILLED",
        avg_fill_price_minor=11600,
        filled_quantity=sum(f.quantity for f in fills),
        fills=fills,
    )


class EnsureBrokerFillIdsTests(unittest.TestCase):
    def test_same_price_size_fills_at_different_times_get_distinct_ids(self) -> None:
        event = _status_event(
            (
                _fill(event_time_ns=1787000000600000000, receive_time_ns=1787000000600100000),
                _fill(event_time_ns=1787000000600200000, receive_time_ns=1787000000600500000),
            )
        )
        rebuilt = ensure_broker_fill_ids(event)
        ids = {f.broker_fill_id for f in rebuilt.fills}
        self.assertEqual(len(ids), 2)
        self.assertTrue(all(ids))

    def test_backfill_is_deterministic(self) -> None:
        fills = (
            _fill(event_time_ns=1787000000600000000, receive_time_ns=1787000000600100000),
            _fill(event_time_ns=1787000000600200000, receive_time_ns=1787000000600500000),
        )
        first = ensure_broker_fill_ids(_status_event(fills))
        second = ensure_broker_fill_ids(_status_event(fills))
        self.assertEqual(
            [f.broker_fill_id for f in first.fills],
            [f.broker_fill_id for f in second.fills],
        )

    def test_existing_fill_ids_are_preserved(self) -> None:
        stamped = BrokerFillEvent(
            broker_fill_id="TR-FL-0010",
            broker_order_id="TR-1",
            event_time_ns=1787000000600000000,
            price_minor=11600,
            quantity=25,
            receive_time_ns=1787000000600100000,
        )
        rebuilt = ensure_broker_fill_ids(_status_event((stamped,)))
        self.assertEqual(rebuilt.fills[0].broker_fill_id, "TR-FL-0010")

    def test_timestamps_participate_in_identity(self) -> None:
        # Same economics and index; only the timestamps differ -> different id.
        a = ensure_broker_fill_ids(
            _status_event((_fill(event_time_ns=1000, receive_time_ns=1100),))
        ).fills[0].broker_fill_id
        b = ensure_broker_fill_ids(
            _status_event((_fill(event_time_ns=2000, receive_time_ns=2100),))
        ).fills[0].broker_fill_id
        self.assertNotEqual(a, b)


class BrokerFillEventFromRecordTests(unittest.TestCase):
    def test_missing_event_time_fails_closed(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            BrokerFillEvent.from_record(
                {"broker_fill_id": "TR-FL-0001", "price_minor": 11600, "quantity": 25},
                broker_order_id="TR-1",
            )
        self.assertIn("BROKER_FILL_TIMESTAMP_MISSING", str(ctx.exception))

    def test_none_event_time_fails_closed(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            BrokerFillEvent.from_record(
                {
                    "broker_fill_id": "TR-FL-0001",
                    "price_minor": 11600,
                    "quantity": 25,
                    "event_time_ns": None,
                },
                broker_order_id="TR-1",
            )
        self.assertIn("BROKER_FILL_TIMESTAMP_MISSING", str(ctx.exception))

    def test_stamped_record_round_trips(self) -> None:
        fill = BrokerFillEvent.from_record(
            {
                "broker_fill_id": "TR-FL-0001",
                "price_minor": 11600,
                "quantity": 25,
                "event_time_ns": 1787000000600000000,
                "receive_time_ns": 1787000000600100000,
            },
            broker_order_id="TR-1",
        )
        self.assertEqual(fill.event_time_ns, 1787000000600000000)
        self.assertEqual(fill.receive_time_ns, 1787000000600100000)

    def test_missing_receive_time_defaults_to_event_time(self) -> None:
        fill = BrokerFillEvent.from_record(
            {
                "broker_fill_id": "TR-FL-0001",
                "price_minor": 11600,
                "quantity": 25,
                "event_time_ns": 1787000000600000000,
            },
            broker_order_id="TR-1",
        )
        self.assertEqual(fill.receive_time_ns, fill.event_time_ns)


if __name__ == "__main__":
    unittest.main()
