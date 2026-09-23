"""CONTROLLED REPLAY API helpers (clock advance only; never Live)."""

from __future__ import annotations

import os
from typing import Any

from ..news.timestamps import epoch_ns_from_iso
from .store import ReplayStore


def controlled_replay_enabled() -> bool:
    return str(os.environ.get("IMP_CONTROLLED_REPLAY") or "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def handle_advance_clock(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    """Set software as_of for controlled-replay freshness evaluation.

    Opt-in only. Does not enable Live clocks or broker authority.
    """

    if not controlled_replay_enabled() and not bool(getattr(store, "controlled_replay", False)):
        raise PermissionError("CONTROLLED_REPLAY_NOT_ENABLED")
    as_of_time = str(body.get("as_of_time") or "").strip()
    if not as_of_time:
        raise ValueError("CONTROLLED_REPLAY_AS_OF_REQUIRED")
    as_of_ns = epoch_ns_from_iso(as_of_time)
    if as_of_ns is None:
        raise ValueError("CONTROLLED_REPLAY_AS_OF_INVALID")
    store.as_of_time_ns = int(as_of_ns)
    store.last_source_time_ns = int(as_of_ns)
    store.opportunity_source = "CONTROLLED_REPLAY"
    store.controlled_replay = True
    store.data_mode = "FIXTURE_REPLAY"
    store.execution_authority = "BLOCKED"
    return {
        "ok": True,
        "as_of_time": as_of_time,
        "as_of_time_ns": int(as_of_ns),
        "evidence_class": "CONTROLLED_REPLAY",
        "execution_authority": "BLOCKED",
        "not_live_market_data": True,
    }


__all__ = ["controlled_replay_enabled", "handle_advance_clock"]
