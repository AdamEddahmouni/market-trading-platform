"""PIT-safe bounded execution event buffer for live internal simulation."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from .live_admission import ADMISSION_EXECUTION
from .observational_state import _session_price

LIVE_L1_TIMEFRAME = "LIVE_L1_SNAPSHOT"
# A live L1 bar's participation volume is the venue's own count of shares traded in the trailing window that ends at
# the bar: the change in the cumulative day volume Moomoo carries on every QUOTE push and market snapshot. A bar with
# no earlier count inside the window, or whose count went down (a new day), has no volume evidence and fills nothing.
TRADED_VOLUME_WINDOW_NS = 60_000_000_000
TRADED_VOLUME_BASIS = "VENUE_TRADED_VOLUME_60S"
# Market snapshots (every 2 s) carry the touch; QUOTE pushes do not. A snapshot's bid/ask prices the pushes that
# follow it for this long, after which a push is priced at its own last trade only.
TOUCH_MAX_AGE_NS = 5_000_000_000


def _is_l1_capability(capability: str) -> bool:
    cap = capability.upper()
    return "L1" in cap or cap in {"BASIC_QUOTE", "QUOTE"}


def _positive(payload: dict[str, Any], *keys: str) -> Decimal | None:
    for key in keys:
        value = payload.get(key)
        if value is None or value == "" or isinstance(value, bool):
            continue
        try:
            number = Decimal(str(value))
        except (InvalidOperation, ValueError):
            continue
        if number.is_finite() and number > 0:
            return number
    return None


def _touch(payload: dict[str, Any]) -> tuple[Decimal, Decimal] | None:
    bid, ask = _positive(payload, "bid_price", "best_bid"), _positive(payload, "ask_price", "best_ask")
    return (bid, ask) if bid is not None and ask is not None and ask >= bid else None


def _cumulative_volume(payload: dict[str, Any]) -> int | None:
    value = payload.get("volume")
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return int(number) if number.is_finite() and number >= 0 else None


def _snapshot_price(payload: dict[str, Any]) -> Decimal | None:
    """The price of the payload's own session: the last regular trade during regular hours, never a stale
    extended-hours field (Moomoo keeps the previous session's ``after_price`` in regular-hours quotes)."""
    value, _field = _session_price(payload)
    if value is not None and value > 0:
        return Decimal(str(value))
    touch = _touch(payload)
    return (touch[0] + touch[1]) / 2 if touch else None


def _quantum(price_scale: int) -> Decimal:
    text = str(int(price_scale))
    return Decimal(1).scaleb(-(len(text) - 1)) if text.strip("0") == "1" else Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class BufferedExecutionEvent:
    instrument_id: str
    available_time_ns: int
    event_time_ns: int
    capability: str
    envelope: dict[str, Any]
    admission_execution: str
    provider_generation: int
    quality_flags: tuple[str, ...]
    provider: str
    quality: str


@dataclass
class LiveExecutionEventBuffer:
    max_events: int = 2000
    provider_generation: int = 0
    events_by_instrument: dict[str, deque[BufferedExecutionEvent]] = field(
        default_factory=lambda: defaultdict(deque)
    )

    def clear(self) -> None:
        self.events_by_instrument.clear()

    def on_generation_change(self, generation: int) -> None:
        self.provider_generation = generation
        self.clear()

    def append_admitted(self, result: dict[str, Any], *, provider_generation: int) -> bool:
        admission = result.get("admission") if isinstance(result.get("admission"), dict) else {}
        if admission.get("execution") != ADMISSION_EXECUTION:
            return False
        envelope = result.get("envelope")
        record = result.get("record") if isinstance(result.get("record"), dict) else {}
        if not isinstance(envelope, dict):
            return False
        instrument = str(envelope.get("instrument_id") or record.get("instrument_id") or "").upper()
        if not instrument:
            return False
        if self.provider_generation == 0 and provider_generation:
            self.provider_generation = int(provider_generation)
        clocks = record.get("clocks") if isinstance(record.get("clocks"), dict) else {}
        available_ns = int(envelope.get("available_time") or clocks.get("received_time_ns") or 0)
        event_time_ns = int(envelope.get("event_time") or clocks.get("event_time_ns") or available_ns)
        capability = str(record.get("capability") or envelope.get("event_type") or "")
        item = BufferedExecutionEvent(
            instrument_id=instrument,
            available_time_ns=available_ns,
            event_time_ns=event_time_ns,
            capability=capability,
            envelope=envelope,
            admission_execution=str(admission.get("execution") or ""),
            provider_generation=int(provider_generation),
            quality_flags=tuple(result.get("quality_flags") or ()),
            provider=str(record.get("provider") or envelope.get("publisher_id") or "moomoo"),
            quality="PASS",
        )
        bucket = self.events_by_instrument[instrument]
        bucket.append(item)
        while len(bucket) > self.max_events:
            bucket.popleft()
        return True

    def _visible_events(
        self,
        *,
        observation_time_ns: int,
        instrument_id: str | None = None,
        provider_generation: int | None = None,
    ) -> list[BufferedExecutionEvent]:
        generation = self.provider_generation if provider_generation is None else provider_generation
        if instrument_id:
            instruments = [instrument_id.upper()]
        else:
            instruments = list(self.events_by_instrument)
        visible: list[BufferedExecutionEvent] = []
        for key in instruments:
            for row in self.events_by_instrument.get(key, ()):
                if not _is_l1_capability(row.capability):
                    continue
                if row.available_time_ns > observation_time_ns:
                    continue
                if generation and row.provider_generation != generation:
                    continue
                if row.admission_execution != ADMISSION_EXECUTION:
                    continue
                visible.append(row)
        visible.sort(key=lambda row: (row.available_time_ns, row.event_time_ns))
        return visible

    def bars_for_execution(
        self,
        *,
        observation_time_ns: int,
        price_scale: int = 100,
        instrument_id: str | None = None,
        provider_generation: int | None = None,
    ) -> list[dict[str, Any]]:
        """Build LIVE_L1_SNAPSHOT bars ordered by available_time, never event_time.

        eligible iff available_time <= observation_time_ns (knowledge horizon).
        BarConservativeSimulator still requires available_time > intent.created_time.
        Open and close are the session price; high is the ask and low the bid when a touch is known (a market buy
        pays the ask, a sale receives the bid), rounded against the account. Volume is the venue's traded shares in
        the trailing TRADED_VOLUME_WINDOW_NS, from earlier events only (no look-ahead).
        """

        quantum = _quantum(price_scale)
        bars: list[dict[str, Any]] = []
        counts: dict[str, list[tuple[int, int]]] = defaultdict(list)
        window_start: dict[str, int] = defaultdict(int)
        touches: dict[str, tuple[int, Decimal, Decimal]] = {}
        for row in self._visible_events(
            observation_time_ns=observation_time_ns,
            instrument_id=instrument_id,
            provider_generation=provider_generation,
        ):
            payload = row.envelope.get("payload") if isinstance(row.envelope.get("payload"), dict) else {}
            history = counts[row.instrument_id]
            cumulative = _cumulative_volume(payload)
            volume = 0
            if cumulative is not None:
                first = window_start[row.instrument_id]
                while first < len(history) and history[first][0] < row.available_time_ns - TRADED_VOLUME_WINDOW_NS:
                    first += 1
                window_start[row.instrument_id] = first
                if first < len(history) and cumulative >= history[first][1]:
                    volume = cumulative - history[first][1]
                history.append((row.available_time_ns, cumulative))
            own_touch = _touch(payload)
            if own_touch is not None:
                touches[row.instrument_id] = (row.available_time_ns, *own_touch)
            price = _snapshot_price(payload)
            if price is None:
                continue
            high = low = price
            touch = touches.get(row.instrument_id)
            if touch is not None and row.available_time_ns - touch[0] <= TOUCH_MAX_AGE_NS:
                low, high = min(price, touch[1]), max(price, touch[2])
            close = price.quantize(quantum, rounding=ROUND_HALF_UP)
            high = high.quantize(quantum, rounding=ROUND_CEILING)
            low = low.quantize(quantum, rounding=ROUND_FLOOR)
            minor = {name: int(value * price_scale) for name, value in (("open", close), ("high", high), ("low", low))}
            bars.append(
                {
                    "available_time": row.available_time_ns,
                    "bar_payload": {
                        "close": str(close),
                        "event_time": row.event_time_ns,
                        "high": str(high),
                        "low": str(low),
                        "open": str(close),
                        "provider": row.provider,
                        "quality": row.quality,
                        "source": "LIVE_L1_SNAPSHOT",
                        "timeframe": LIVE_L1_TIMEFRAME,
                        "volume": volume,
                        "volume_basis": TRADED_VOLUME_BASIS,
                    },
                    "close_minor": minor["open"],
                    "event_time": row.event_time_ns,
                    "event_type": "BAR_OHLCV_1M",
                    "high_minor": minor["high"],
                    "instrument_id": row.instrument_id,
                    "low_minor": minor["low"],
                    "open_minor": minor["open"],
                    "provider": row.provider,
                    "provider_generation": row.provider_generation,
                    "quality": row.quality,
                    "source": "LIVE_L1_SNAPSHOT",
                    "volume": volume,
                    "volume_basis": TRADED_VOLUME_BASIS,
                }
            )
        return bars

    def bars_after_intent(
        self,
        *,
        created_time_ns: int,
        observation_time_ns: int,
        price_scale: int = 100,
        instrument_id: str | None = None,
        provider_generation: int | None = None,
    ) -> list[dict[str, Any]]:
        return [
            bar
            for bar in self.bars_for_execution(
                observation_time_ns=observation_time_ns,
                price_scale=price_scale,
                instrument_id=instrument_id,
                provider_generation=provider_generation,
            )
            if int(bar["available_time"]) > created_time_ns
        ]

    def latest_quote_available_time(self, *, observation_time_ns: int, instrument_id: str | None = None) -> int | None:
        visible = self._visible_events(observation_time_ns=observation_time_ns, instrument_id=instrument_id)
        if not visible:
            return None
        return max(row.available_time_ns for row in visible)

    def report(self) -> dict[str, Any]:
        return {
            "event_count": sum(len(rows) for rows in self.events_by_instrument.values()),
            "instruments": sorted(self.events_by_instrument),
            "max_events": self.max_events,
            "provider_generation": self.provider_generation,
        }
