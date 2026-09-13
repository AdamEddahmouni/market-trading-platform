"""Join Paper ledger fills/PnL onto a forward-test decision without log scraping."""

from __future__ import annotations

import json
from typing import Any

from ...local_state.connection import LocalStateConnection


def paper_execution_from_ledger(
    connection: LocalStateConnection,
    *,
    paper_order_id: str | None,
) -> tuple[int | None, int, int | None]:
    """Return (realized_pnl_minor, fill_count, unrealized_pnl_minor) for an order."""
    if not paper_order_id:
        return None, 0, None
    fill_count = 0
    realized: int | None = None
    unrealized: int | None = None
    rows = connection.execute(
        """
        SELECT event_type, payload_json
        FROM paper_events
        ORDER BY sequence ASC
        """
    ).fetchall()
    awaiting_position = False
    for row in rows:
        event_type = str(row[0])
        payload = json.loads(row[1]) if row[1] else {}
        if not isinstance(payload, dict):
            continue
        if event_type == "FillRecorded" and str(payload.get("order_id") or "") == paper_order_id:
            fill_count += 1
            awaiting_position = True
            continue
        if awaiting_position and event_type == "PositionChanged":
            if "realized_pnl_minor" in payload:
                realized = int(payload["realized_pnl_minor"])
            if payload.get("unrealized_pnl_minor") is not None:
                unrealized = int(payload["unrealized_pnl_minor"])
            awaiting_position = False
    return realized, fill_count, unrealized


def paper_execution_from_observations(payloads: tuple[dict[str, Any], ...]) -> tuple[int | None, int]:
    realized: int | None = None
    fill_count = 0
    for payload in payloads:
        if payload.get("realized_pnl_minor") is not None:
            realized = int(payload["realized_pnl_minor"])
        if payload.get("fill_count") is not None:
            fill_count = max(fill_count, int(payload["fill_count"]))
        if payload.get("fill") or payload.get("fill_id"):
            fill_count = max(fill_count, 1)
    return realized, fill_count
