"""Resolve scheduling clock for enrichment worker ticks."""

from __future__ import annotations

from typing import Any

from ...clock import monotonic_wall_ns


def resolve_outbox_schedule_now_ns(outbox: Any, explicit_now_ns: int | None) -> int:
    """Prefer explicit decision time; else latest pending detection time; else monotonic."""

    if explicit_now_ns is not None:
        return int(explicit_now_ns)
    if hasattr(outbox, "list_pending"):
        pending = outbox.list_pending()
        if pending:
            return max(row.detected_at_ns for row in pending)
    return monotonic_wall_ns()


__all__ = ["resolve_outbox_schedule_now_ns"]
