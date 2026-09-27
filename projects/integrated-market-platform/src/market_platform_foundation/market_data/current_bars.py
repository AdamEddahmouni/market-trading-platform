"""Provider-neutral current OHLCV bars for live product surfaces.

The normal source is Moomoo OpenD subscribed 1m klines (``get_cur_kline``),
read through the same ``tools/moomoo`` transport the production L1 adapter
uses. Subscribed klines do not consume the vendor's 30-day history-kline
symbol quota. No replay, capture, or fixture bars are ever substituted: when
the provider cannot answer, the series is ``UNAVAILABLE``.

Timing: the vendor ``time_key`` is the bar *end* in America/New_York (RTH runs
``09:31`` through ``16:00``). A bar is complete only when its end is at or
before the as-of clock; at most one later bar is reported separately as the
forming bar and never feeds structural analysis.
"""

from __future__ import annotations

import math
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from ..market_sessions import us_equity_session_label

SCHEMA_VERSION = "current-bars/1.0.0"
PROVIDER = "MOOMOO_OPEND"
SOURCE_ID = "MOOMOO_OPEND_CUR_KLINE_1M"
TIMING_BASIS = "vendor time_key is bar end, America/New_York"
TIMEFRAMES: dict[str, int] = {"1m": 1, "5m": 5, "15m": 15}
SESSION_SCOPES = ("EXTENDED", "RTH")
ET = ZoneInfo("America/New_York")
MINUTE_NS = 60_000_000_000
# US-equity session segments in ET minutes of day, [start, end).
SEGMENTS: tuple[tuple[str, int, int], ...] = (
    ("PREMARKET", 4 * 60, 9 * 60 + 30),
    ("REGULAR", 9 * 60 + 30, 16 * 60),
    ("AFTER_HOURS", 16 * 60, 20 * 60),
)
SCOPE_SESSIONS = {"EXTENDED": frozenset(("PREMARKET", "REGULAR", "AFTER_HOURS")), "RTH": frozenset(("REGULAR",))}
STALE_TOLERANCE_NS = 3 * MINUTE_NS
# A closed-market series may be the latest session only if it ended within a
# long weekend; older data is stale rather than "last session".
CLOSED_SESSION_MAX_AGE_NS = 4 * 24 * 60 * MINUTE_NS
CACHE_TTL_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class Bar:
    start_ns: int
    end_ns: int
    open: float
    high: float
    low: float
    close: float
    volume: float | None
    session: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "time": self.start_ns // 1_000_000_000,
            "start": _iso(self.start_ns),
            "end": _iso(self.end_ns),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "session": self.session,
        }


@dataclass(frozen=True, slots=True)
class BarSeries:
    """Complete bars plus an optional forming bar and the series' own clock."""

    instrument_id: str
    timeframe: str
    session_scope: str
    state: str
    reason: str | None
    provider_reason: str | None
    received_ns: int | None
    bars: tuple[Bar, ...]
    forming: Bar | None

    @property
    def latest_end_ns(self) -> int | None:
        return self.bars[-1].end_ns if self.bars else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "instrument_id": self.instrument_id,
            "timeframe": self.timeframe,
            "session_scope": self.session_scope,
            "provider": PROVIDER,
            "source_id": SOURCE_ID,
            "timing_basis": TIMING_BASIS,
            "state": self.state,
            "reason": self.reason,
            "provider_reason": self.provider_reason,
            "received_at": _iso(self.received_ns) if self.received_ns else None,
            "latest_complete_bar_end": _iso(self.latest_end_ns) if self.latest_end_ns else None,
            "bar_count": len(self.bars),
            "bars": [bar.to_dict() for bar in self.bars],
            "forming": self.forming.to_dict() if self.forming else None,
        }


def _iso(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1_000_000_000, tz=UTC).isoformat().replace("+00:00", "Z")


def _et(ns: int) -> datetime:
    return datetime.fromtimestamp(ns / 1_000_000_000, tz=ET)


def session_of(start_ns: int) -> str | None:
    """Session segment containing a bar that starts at ``start_ns``; None overnight/weekend."""

    moment = _et(start_ns)
    if moment.weekday() >= 5:
        return None
    minute = moment.hour * 60 + moment.minute
    return next((name for name, low, high in SEGMENTS if low <= minute < high), None)


def _price(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _parse_time_key(text: Any) -> int | None:
    raw = str(text or "").strip().replace("T", " ")
    try:
        parsed = datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
    return int(parsed.replace(tzinfo=ET).timestamp()) * 1_000_000_000


def normalize_vendor_1m(
    rows: Iterable[Mapping[str, Any]], *, as_of_ns: int,
) -> tuple[list[Bar], Bar | None, int]:
    """Canonical 1m bars from vendor rows: (complete, forming, rejected_count).

    Rows are rejected when malformed (unparseable time, non-positive or
    non-finite prices, OHLC inconsistency, negative volume), outside the
    04:00-20:00 ET weekday segments, or ending beyond the forming minute.
    Duplicate bar ends keep the last vendor row. Output is ordered by end time.
    """

    by_end: dict[int, Bar] = {}
    rejected = 0
    for row in rows:
        end_ns = _parse_time_key(row.get("time_key")) if isinstance(row, Mapping) else None
        values = [_price(row.get(key)) for key in ("open", "high", "low", "close")] if end_ns else [None]
        if end_ns is None or any(value is None for value in values):
            rejected += 1
            continue
        open_, high, low, close = (float(value) for value in values)  # type: ignore[arg-type]
        if low > high or not (low <= open_ <= high) or not (low <= close <= high):
            rejected += 1
            continue
        raw_volume = row.get("volume")
        volume: float | None
        try:
            volume = float(raw_volume) if raw_volume is not None else None
        except (TypeError, ValueError):
            volume = None
        if volume is not None and (not math.isfinite(volume) or volume < 0):
            rejected += 1
            continue
        start_ns = end_ns - MINUTE_NS
        session = session_of(start_ns)
        if session is None or start_ns >= as_of_ns:
            rejected += 1
            continue
        by_end[end_ns] = Bar(start_ns, end_ns, open_, high, low, close, volume, session)
    ordered = [by_end[key] for key in sorted(by_end)]
    complete = [bar for bar in ordered if bar.end_ns <= as_of_ns]
    forming = next((bar for bar in ordered if bar.end_ns > as_of_ns), None)
    return complete, forming, rejected


def scope_filter(bars: Sequence[Bar], scope: str) -> list[Bar]:
    allowed = SCOPE_SESSIONS[scope]
    return [bar for bar in bars if bar.session in allowed]


def aggregate(
    bars: Sequence[Bar], minutes: int, *, as_of_ns: int, forming: Bar | None = None,
) -> tuple[list[Bar], Bar | None]:
    """Deterministic N-minute bars that never cross a session segment or day.

    Buckets align to ET clock multiples of ``minutes`` (04:00, 09:30, 16:00, and
    20:00 are aligned for 1, 5, and 15). A bucket is complete only when its end
    is at or before ``as_of_ns``; otherwise it is the forming bucket.
    """

    if minutes == 1:
        return list(bars), forming
    source = list(bars) + ([forming] if forming is not None else [])
    buckets: dict[tuple[str, str, int], list[Bar]] = {}
    for bar in source:
        moment = _et(bar.start_ns)
        minute = moment.hour * 60 + moment.minute
        key = (moment.strftime("%Y-%m-%d"), bar.session, minute - minute % minutes)
        buckets.setdefault(key, []).append(bar)
    complete: list[Bar] = []
    forming_bucket: Bar | None = None
    for (day, session, first_minute), members in sorted(buckets.items(), key=lambda item: item[1][0].start_ns):
        members.sort(key=lambda bar: bar.start_ns)
        day_start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=ET)
        start_ns = int((day_start + timedelta(minutes=first_minute)).timestamp()) * 1_000_000_000
        end_ns = start_ns + minutes * MINUTE_NS
        volumes = [bar.volume for bar in members if bar.volume is not None]
        merged = Bar(
            start_ns, end_ns, members[0].open, max(bar.high for bar in members),
            min(bar.low for bar in members), members[-1].close,
            sum(volumes) if volumes else None, session,
        )
        if end_ns <= as_of_ns and not (forming is not None and forming in members):
            complete.append(merged)
        else:
            forming_bucket = merged
    return complete, forming_bucket


def _segment_start_ns(now: datetime, session: str) -> int:
    start_minute = next(low for name, low, _high in SEGMENTS if name == session)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight + timedelta(minutes=start_minute)).timestamp()) * 1_000_000_000


def freshness(latest_end_ns: int | None, *, now_ns: int, scope: str) -> tuple[str, str | None]:
    """Series state relative to the bars that could exist now for ``scope``.

    CURRENT: the scope's session is open and the latest complete bar is within
    three minutes of the latest bar that could be complete. SESSION_CLOSED: the
    scope's session is closed and the latest bar is recent enough to be the last
    session. STALE otherwise. No holiday calendar is applied, so a holiday reads
    as SESSION_CLOSED only while the latest bar is within four days.
    """

    if latest_end_ns is None:
        return "UNAVAILABLE", "INSUFFICIENT_BARS"
    now = _et(now_ns)
    label = us_equity_session_label(now)
    if label in SCOPE_SESSIONS[scope]:
        expected = now_ns - now_ns % MINUTE_NS
        if latest_end_ns >= expected - STALE_TOLERANCE_NS:
            return "CURRENT", None
        if now_ns - _segment_start_ns(now, label) < STALE_TOLERANCE_NS:
            return "CURRENT", None
        return "STALE", "STALE_BAR_SOURCE"
    if now_ns - latest_end_ns <= CLOSED_SESSION_MAX_AGE_NS:
        return "SESSION_CLOSED", None
    return "STALE", "STALE_BAR_SOURCE"


def _default_transport() -> Any:
    from ..providers.adapters.moomoo_opend_equity_quote import (
        _load_tools_transport_module,
        opend_endpoint,
        opend_is_loopback,
    )

    host, port = opend_endpoint()
    if not opend_is_loopback(host):
        return None
    module = _load_tools_transport_module()
    session_cls = getattr(module, "OpendCurrentKlineSession", None) if module is not None else None
    return session_cls(host=host, port=port) if session_cls is not None else None


def _default_reachable() -> bool:
    from ..providers.adapters.moomoo_opend_equity_quote import opend_reachable

    return opend_reachable()


class CurrentBarsService:
    """Short-TTL cache of current 1m bars per instrument; derives 5m/15m on read."""

    def __init__(
        self,
        *,
        transport_factory: Callable[[], Any] = _default_transport,
        reachable: Callable[[], bool] = _default_reachable,
        now_ns: Callable[[], int] = time.time_ns,
        monotonic: Callable[[], float] = time.monotonic,
        ttl_seconds: float = CACHE_TTL_SECONDS,
    ) -> None:
        self._transport_factory = transport_factory
        self._reachable = reachable
        self._now_ns = now_ns
        self._monotonic = monotonic
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
        self._transport: Any | None = None
        self._cache: dict[str, tuple[float, int, list[Bar], Bar | None, str | None]] = {}

    def transport(self) -> Any | None:
        with self._lock:
            if self._transport is None:
                self._transport = self._transport_factory()
            return self._transport

    def _load_1m(self, instrument_id: str) -> tuple[int, list[Bar], Bar | None, str | None]:
        with self._lock:
            cached = self._cache.get(instrument_id)
            if cached is not None and self._monotonic() - cached[0] < self._ttl:
                return cached[1], cached[2], cached[3], cached[4]
            received = self._now_ns()
            if not self._reachable():
                result: tuple[int, list[Bar], Bar | None, str | None] = (received, [], None, "OPEND_UNAVAILABLE")
            else:
                transport = self.transport()
                # Same US-equity provider code rule as the live runtime's L1 subscriptions.
                code = f"US.{instrument_id.strip().upper()}"
                payload = transport.fetch_current_kline_1m(code) if transport is not None else {
                    "reason_code": "MOOMOO_TRANSPORT_NOT_IMPLEMENTED", "rows": None}
                received = self._now_ns()
                reason = payload.get("reason_code") if isinstance(payload, dict) else "MOOMOO_PROTOCOL_ERROR"
                rows = payload.get("rows") if isinstance(payload, dict) else None
                if reason or not isinstance(rows, list):
                    result = (received, [], None, str(reason or "MOOMOO_PROTOCOL_ERROR"))
                else:
                    complete, forming, _rejected = normalize_vendor_1m(rows, as_of_ns=received)
                    result = (received, complete, forming, None)
            self._cache[instrument_id] = (self._monotonic(), *result)
            return result

    def read(self, instrument_id: str, *, timeframe: str = "5m", scope: str = "EXTENDED") -> BarSeries:
        if timeframe not in TIMEFRAMES:
            raise ValueError("UNSUPPORTED_TIMEFRAME")
        if scope not in SESSION_SCOPES:
            raise ValueError("UNSUPPORTED_SESSION_SCOPE")
        received, complete_1m, forming_1m, provider_reason = self._load_1m(instrument_id)
        if provider_reason is not None:
            return BarSeries(instrument_id, timeframe, scope, "UNAVAILABLE", "BAR_SOURCE_UNAVAILABLE",
                             provider_reason, received, (), None)
        scoped = scope_filter(complete_1m, scope)
        scoped_forming = forming_1m if forming_1m is not None and forming_1m.session in SCOPE_SESSIONS[scope] else None
        bars, forming = aggregate(scoped, TIMEFRAMES[timeframe], as_of_ns=received, forming=scoped_forming)
        state, reason = freshness(bars[-1].end_ns if bars else None, now_ns=received, scope=scope)
        return BarSeries(instrument_id, timeframe, scope, state, reason, None, received, tuple(bars), forming)


_SERVICE: CurrentBarsService | None = None
_SERVICE_LOCK = threading.Lock()


def current_bars_service() -> CurrentBarsService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = CurrentBarsService()
        return _SERVICE


__all__ = [
    "Bar",
    "BarSeries",
    "CurrentBarsService",
    "SCHEMA_VERSION",
    "SESSION_SCOPES",
    "TIMEFRAMES",
    "aggregate",
    "current_bars_service",
    "freshness",
    "normalize_vendor_1m",
    "scope_filter",
    "session_of",
]
