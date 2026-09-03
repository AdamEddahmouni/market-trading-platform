"""Fixture-first MBO adapter for ES queue research — Order Flow OF10."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...order_flow.queue import build_queue_snapshot, parse_mbo_orders

DEFAULT_MBO_FIXTURE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "providers"
    / "order_flow"
    / "es_mbo_slice.json"
)


class FixtureMboProvider:
    """Offline MBO adapter using bounded ES synthetic slice."""

    provider_id = "mbo.fixture.order_flow"
    capability = "mbo"
    entitlement = "MBO_DEMO_FIXTURE"

    def __init__(self, *, fixture_path: Path | None = None) -> None:
        self.fixture_path = fixture_path or DEFAULT_MBO_FIXTURE
        self._fixture = self._load_fixture()
        self._snapshots_by_time = self._index_snapshots()

    def _load_fixture(self) -> dict[str, Any]:
        payload = json.loads(
            self.fixture_path.read_text(encoding="utf-8"),
            object_pairs_hook=_pairs_no_duplicates,
        )
        if not isinstance(payload, dict):
            raise ValueError("MBO_FIXTURE_INVALID")
        return payload

    def _index_snapshots(self) -> dict[str, list[dict[str, Any]]]:
        indexed: dict[str, list[dict[str, Any]]] = {}
        snapshots = self._fixture.get("snapshots", [])
        if not isinstance(snapshots, list):
            return indexed
        for snapshot in snapshots:
            if not isinstance(snapshot, dict):
                continue
            event_time = str(snapshot.get("event_time", ""))
            orders = snapshot.get("orders", [])
            if event_time and isinstance(orders, list):
                indexed[event_time] = orders
        return indexed

    def symbol(self) -> str:
        return str(self._fixture.get("symbol", "")).upper()

    def orders_for_event_time(self, event_time: str) -> list[dict[str, Any]]:
        return list(self._snapshots_by_time.get(event_time, []))

    def queue_snapshot_for_event_time(self, event_time: str):
        orders = self.orders_for_event_time(event_time)
        if not orders:
            return None
        return build_queue_snapshot(orders, event_time=event_time)

    def all_queue_snapshots(self):
        snapshots = []
        for event_time in sorted(self._snapshots_by_time):
            snapshot = self.queue_snapshot_for_event_time(event_time)
            if snapshot is not None:
                snapshots.append(snapshot)
        return snapshots


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


__all__ = [
    "DEFAULT_MBO_FIXTURE",
    "FixtureMboProvider",
]
