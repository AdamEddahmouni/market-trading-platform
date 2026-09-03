"""Replay captured observational JSONL through canonical replay clocks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..data_quality.observations import consumer_eligibility
from ..replay.lifecycle import ReplayState, run_replay
from .book_features import compute_book_features
from .capture import read_envelopes
from .normalization import classified_trade_from_ticker, levels_from_order_book, replay_envelope_from_capture
from .quality import assess_book, assess_quote, assess_ticker


def load_replay_events(path: Path) -> list[dict[str, Any]]:
    return [replay_envelope_from_capture(row) for row in read_envelopes(path)]


def replay_captured_path(
    path: Path,
    *,
    clocks: list[int] | None = None,
    decision_times: list[int] | None = None,
) -> ReplayState:
    events = load_replay_events(path)
    if not events:
        return ReplayState()
    ordered_times = sorted(int(event["available_time"]) for event in events)
    replay_clocks = clocks or [ordered_times[-1]]
    decisions = decision_times or [ordered_times[-1]]
    return run_replay(events, clocks=replay_clocks, decision_times=decisions)


def characterize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    trades = []
    flags: list[str] = []
    book_features = None
    for record in records:
        payload = record.get("raw_payload") or {}
        capability = str(record.get("capability") or "")
        if "TICK" in capability:
            trades.append(classified_trade_from_ticker(payload))
            flags.extend(assess_ticker(payload))
        elif "DEPTH" in capability or "ORDER_BOOK" in capability:
            flags.extend(assess_book(payload))
            bids, asks = levels_from_order_book(payload)
            book_features = compute_book_features(bids, asks)
        else:
            flags.extend(assess_quote(payload))
    observations = [
        {"dimension": "validity", "state": flag, "severity": "ERROR"}
        for flag in flags
        if flag == "INVALID_QUOTE"
    ]
    eligibility, reasons = consumer_eligibility(observations)
    return {
        "book_features": None if book_features is None else book_features.to_dict(),
        "consumer_eligibility": eligibility,
        "eligibility_reason_codes": reasons,
        "quality_flags": sorted(set(flags)),
        "trade_count": len(trades),
        "unknown_aggressor_count": sum(
            1 for trade in trades if trade.aggressor_source.value == "UNKNOWN"
        ),
    }
