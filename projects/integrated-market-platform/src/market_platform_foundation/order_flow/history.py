"""Runtime-local admitted flow history, independent of the bounded print tape.

No candle reconstruction or replay/backfill. Empty seconds are not observations.
Receive silence is reported as unverified continuity, never as proven zero flow.
"""
from __future__ import annotations

import math
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from zoneinfo import ZoneInfo
from typing import Any

SECOND = 1_000_000_000
RESOLUTIONS = {"1s": 1, "5s": 5, "15s": 15, "1m": 60, "5m": 300}
RANGES = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}
MAX_POINTS = 2000


def iso(ns: int | None) -> str | None:
    return datetime.fromtimestamp(ns / SECOND, UTC).isoformat().replace("+00:00", "Z") if ns else None


def request_window(now_ns: int, session: str, range_name: str, start_ms: int | None,
                   end_ms: int | None, resolution: str) -> tuple[int, int, int]:
    if range_name not in {*RANGES, "session"} or resolution not in {*RESOLUTIONS, "auto"}:
        raise ValueError("INVALID_FLOW_RANGE_OR_RESOLUTION")
    end = now_ns if end_ms is None else int(end_ms) * 1_000_000
    if range_name == "session":
        local = datetime.fromtimestamp(end / SECOND, UTC).astimezone(
            UTC if session == "24_7" else ZoneInfo("America/New_York"))
        # Equity session scope follows the current market phase; closed means today's RTH.
        hour, minute = ((0, 0) if session == "24_7" else (4, 0) if session == "PREMARKET"
                        else (16, 0) if session == "AFTER_HOURS" else (9, 30))
        start = int(local.replace(hour=hour, minute=minute, second=0, microsecond=0).timestamp() * SECOND)
        start = min(start, end - SECOND)
    else:
        start = end - RANGES[range_name] * SECOND
    if start_ms is not None:
        start = int(start_ms) * 1_000_000
    if start < 0 or end <= start or end > now_ns or end - start > 86400 * SECOND:
        raise ValueError("INVALID_FLOW_WINDOW")
    span = (end - start) / SECOND
    seconds = (1 if span <= 300 else 5 if span <= 900 else 15 if span <= 3600 else 60) if resolution == "auto" else RESOLUTIONS[resolution]
    seconds = max(seconds, math.ceil(span / MAX_POINTS))
    seconds = next((r for r in RESOLUTIONS.values() if r >= seconds), seconds)
    return start, end, seconds


@dataclass
class Capture:
    day: str
    anchor_ns: int
    buckets: dict[tuple[int, int], dict[str, Any]] = field(default_factory=dict)
    seen: OrderedDict[tuple[str, str], int] = field(default_factory=OrderedDict)
    gaps: list[dict[str, Any]] = field(default_factory=list)
    last_received_ns: int = 0
    watermark_ns: int = 0
    dedupe_floor_ns: int = 0
    stopped_ns: int | None = None
    segment: int = 0
    dropped_late: int = 0
    baseline: float = 0.0
    truncated: bool = False
    interruption_ns: int | None = None
    provider: str | None = None


class FlowHistoryStore:
    """At most 32 instruments × one calendar day of observed seconds.

    Tick identities exist only in a bounded 120-second correction horizon
    (50,000 maximum). Older arrivals are rejected visibly rather than counted
    twice after identity eviction. All projections are atomic snapshots.
    """
    def __init__(self, *, time_zone: str = "America/New_York", max_instruments: int = 32,
                 max_buckets: int = 86400):
        self.time_zone = ZoneInfo(time_zone)
        self.max_instruments, self.max_buckets = max_instruments, max_buckets
        self._captures: OrderedDict[str, Capture] = OrderedDict()
        self._pending: dict[str, int] = {}
        self._evicted_subscriptions: set[str] = set()
        self._lock = threading.RLock()

    def _day(self, ns: int) -> str:
        return datetime.fromtimestamp(ns / SECOND, self.time_zone).date().isoformat()

    def begin(self, instrument: str, anchor_ns: int) -> None:
        with self._lock:
            key = instrument.upper()
            capture = self._captures.get(key)
            self._pending[key] = anchor_ns
            if capture and capture.stopped_ns is not None:
                self._gap(capture, capture.stopped_ns, anchor_ns, "SUBSCRIPTION_INTERRUPTION")
                capture.stopped_ns = None

    def end(self, instrument: str, now_ns: int) -> None:
        with self._lock:
            capture = self._captures.get(instrument.upper())
            if capture:
                capture.stopped_ns = now_ns
            self._pending.pop(instrument.upper(), None)
            self._evicted_subscriptions.discard(instrument.upper())

    def interrupt(self, now_ns: int) -> None:
        """Record provider loss even when reconnect happens between UI polls."""
        with self._lock:
            for capture in self._captures.values():
                if capture.interruption_ns is None:
                    capture.interruption_ns = min(now_ns, capture.last_received_ns or now_ns)

    @staticmethod
    def _gap(capture: Capture, start: int, end: int, reason: str) -> None:
        if end > start:
            capture.gaps.append({"start_ms": start // 1_000_000, "end_ms": end // 1_000_000, "reason": reason})
            capture.segment += 1

    def append(self, instrument: str, row: dict[str, Any]) -> bool:
        with self._lock:
            key = instrument.upper()
            event = int(row.get("event_time_ns") or 0)
            received = int(row.get("received_ns") or row.get("available_time_ns") or 0)
            quantity = abs(float(row.get("quantity") or 0))
            if event <= 0 or received <= 0 or not math.isfinite(quantity):
                return False
            day = self._day(received)
            capture = self._captures.get(key)
            if capture is None or day > capture.day:
                capture = Capture(day, max(received if capture or key in self._evicted_subscriptions else self._pending.get(key, received),
                                          int(datetime.fromtimestamp(received / SECOND, self.time_zone)
                                              .replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * SECOND)))
                self._captures[key] = capture
                self._evicted_subscriptions.discard(key)
            if day != capture.day or self._day(event) != day:
                return False
            self._captures.move_to_end(key)
            while len(self._captures) > self.max_instruments:
                evicted, _ = self._captures.popitem(last=False)
                # Lost aggregates require a new capture anchor on the next print.
                if evicted in self._pending:
                    self._evicted_subscriptions.add(evicted)
            identity = (str(row.get("provider") or ""), str(row.get("trade_id") or ""))
            if identity in capture.seen:
                return False
            if event < max(capture.dedupe_floor_ns, capture.watermark_ns - 120 * SECOND):
                capture.dropped_late += 1
                return False
            provider = identity[0]
            if capture.provider is not None and provider != capture.provider:
                self._gap(capture, capture.last_received_ns, max(received, capture.last_received_ns + 1_000_000), "PROVIDER_CHANGE")
            capture.provider = provider
            if capture.interruption_ns is not None:
                self._gap(capture, capture.interruption_ns, received, "PROVIDER_INTERRUPTION")
                capture.interruption_ns = None
            elif capture.last_received_ns and received - capture.last_received_ns > 30 * SECOND:
                self._gap(capture, capture.last_received_ns, received, "CONTINUITY_UNVERIFIED")
            capture.last_received_ns = max(capture.last_received_ns, received)
            capture.watermark_ns = max(capture.watermark_ns, event)
            capture.seen[identity] = event
            while capture.seen and (len(capture.seen) > 50000 or
                    next(iter(capture.seen.values())) < capture.watermark_ns - 120 * SECOND):
                _, discarded = capture.seen.popitem(last=False)
                capture.dedupe_floor_ns = max(capture.dedupe_floor_ns, discarded + 1)
            second = event // SECOND
            # Continuity belongs to event time, not the arrival order. Prints
            # inside an uncertain interval stay isolated rather than bridging it.
            event_ms = event // 1_000_000
            segment = sum(event_ms >= gap["end_ms"] for gap in capture.gaps)
            if any(gap["start_ms"] < event_ms < gap["end_ms"] for gap in capture.gaps):
                segment = -second - 1
            bucket = capture.buckets.setdefault((second, segment), {
                "time_ms": second * 1000, "end_ms": (second + 1) * 1000,
                "buy_volume": 0.0, "sell_volume": 0.0, "unknown_volume": 0.0,
                "trade_count": 0, "native_count": 0, "inferred_count": 0, "unknown_count": 0,
                "event_at": None, "received_at": None, "segment": segment,
                "providers": [],
            })
            if provider not in bucket["providers"]:
                bucket["providers"].append(provider)
            side = str(row.get("aggressor_side") or "UNKNOWN").upper()
            provenance = str(row.get("aggressor_provenance") or "UNKNOWN").upper()
            known = side in {"BUY", "SELL"} and provenance != "UNKNOWN"
            bucket[("buy_volume" if side == "BUY" else "sell_volume") if known else "unknown_volume"] += quantity
            bucket["trade_count"] += 1
            bucket["native_count" if known and provenance == "EXCHANGE_NATIVE" else "inferred_count" if known else "unknown_count"] += 1
            bucket["event_at"] = max(bucket["event_at"] or "", iso(event) or "")
            bucket["received_at"] = max(bucket["received_at"] or "", iso(received) or "")
            while len(capture.buckets) > self.max_buckets:
                oldest = min(capture.buckets)
                removed = capture.buckets.pop(oldest)
                capture.baseline += removed["buy_volume"] - removed["sell_volume"]
                capture.dedupe_floor_ns = max(capture.dedupe_floor_ns, (oldest[0] + 1) * SECOND)
                capture.truncated = True
            return True

    def project(self, instrument: str, *, start: int, end: int, seconds: int,
                now_ns: int) -> dict[str, Any]:
        with self._lock:
            capture = self._captures.get(instrument.upper())
            start_ms, end_ms = start // 1_000_000, end // 1_000_000
            coverage: dict[str, Any] = {"requested_start_ms": start_ms, "requested_end_ms": end_ms,
                "actual_start_ms": None, "actual_end_ms": None, "anchor_at": None,
                "basis": "PARTIAL_CAPTURE", "complete": False, "truncated": False,
                "gaps": [], "persistence": "RUNTIME_LOCAL", "dropped_late_trades": 0}
            if not capture or capture.day != self._day(now_ns):
                return {"points": [], "coverage": coverage, "resolution_seconds": seconds, "latest": None}
            # Eviction carries forward the stable captured CVD baseline below.
            rows = sorted(capture.buckets.values(), key=lambda b: b["time_ms"])
            baseline = capture.baseline
            truncated = capture.truncated
            # Canonical day bounds memory naturally; a smaller configured retention bound is explicit.
            retained = rows[-self.max_buckets:]
            selected = []
            cvd = baseline
            for row in retained:
                delta = row["buy_volume"] - row["sell_volume"]
                cvd += delta
                if start_ms <= row["time_ms"] < end_ms:
                    selected.append({**row, "delta": delta, "cvd": cvd})
            gaps = [dict(g) for g in capture.gaps if g["start_ms"] < end_ms and g["end_ms"] > start_ms]
            if capture.interruption_ns is not None and capture.interruption_ns < end:
                gaps.append({"start_ms": capture.interruption_ns // 1_000_000, "end_ms": end_ms,
                             "reason": "PROVIDER_INTERRUPTION"})
            complete = (capture.anchor_ns <= start and not gaps and not truncated and not capture.dropped_late
                        and capture.stopped_ns is None and now_ns - capture.last_received_ns <= 30 * SECOND)
            coverage.update(actual_start_ms=selected[0]["time_ms"] if selected else None,
                actual_end_ms=selected[-1]["end_ms"] if selected else None, anchor_at=iso(capture.anchor_ns),
                basis="SINCE_SUBSCRIPTION" if complete else "PARTIAL_CAPTURE", complete=complete,
                truncated=truncated, gaps=gaps, dropped_late_trades=capture.dropped_late)
            points = aggregate(selected, seconds)
            while len(points) > MAX_POINTS and seconds < 86400:
                seconds *= 2
                points = aggregate(selected, seconds)
            if len(points) > MAX_POINTS:
                points = points[-MAX_POINTS:]
                coverage.update(complete=False, truncated=True, basis="PARTIAL_CAPTURE")
            recent = [r for r in rows if r["time_ms"] >= now_ns // 1_000_000 - 60000]
            latest = {"cvd": cvd, "event_at": rows[-1]["event_at"], "received_at": iso(capture.last_received_ns),
                "recent_delta": sum(r["buy_volume"] - r["sell_volume"] for r in recent),
                "trades_per_minute": sum(r["trade_count"] for r in recent)} if rows else None
            return {"points": points, "coverage": coverage, "resolution_seconds": seconds, "latest": latest}


def aggregate(rows: list[dict[str, Any]], seconds: int) -> list[dict[str, Any]]:
    """Sum impulse metrics; retain the absolute captured CVD at bucket close."""
    grouped: dict[tuple[int, int], dict[str, Any]] = {}
    fields = ("delta", "buy_volume", "sell_volume", "unknown_volume", "trade_count",
              "native_count", "inferred_count", "unknown_count")
    for row in rows:
        slot = row["time_ms"] // (seconds * 1000) * seconds * 1000
        key = (slot, row["segment"])
        if key not in grouped:
            grouped[key] = {**row, "time_ms": row["time_ms"], "end_ms": row["end_ms"]}
        else:
            bucket = grouped[key]
            for name in fields:
                bucket[name] += row[name]
            bucket.update(cvd=row["cvd"], end_ms=row["end_ms"], event_at=row["event_at"], received_at=row["received_at"])
            bucket["providers"] = sorted(set(bucket["providers"]) | set(row["providers"]))
    for bucket in grouped.values():
        classified = bucket["buy_volume"] + bucket["sell_volume"]
        total = classified + bucket["unknown_volume"]
        bucket["classified_volume"] = classified
        bucket["classified_volume_pct"] = classified / total * 100 if total else None
    return list(grouped.values())
