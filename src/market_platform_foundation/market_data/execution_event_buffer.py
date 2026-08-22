"""PIT-safe bounded execution event buffer for live internal simulation."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

from .live_admission import ADMISSION_EXECUTION

# Participation uses this synthetic size so a 1/100 cap can fill 1 share.
# It is SIMULATION_POLICY, not venue-reported market volume.
SIMULATION_POLICY_VOLUME = 100
LIVE_L1_TIMEFRAME = "LIVE_L1_SNAPSHOT"


def _is_l1_capability(capability: str) -> bool:
    cap = capability.upper()
    return "L1" in cap or cap in {"BASIC_QUOTE", "QUOTE"}


def _snapshot_price(payload: dict[str, Any]) -> float | None:
    for key in (
        "after_price",
        "last_price",
        "last",
        "bid_price",
        "best_bid",
        "ask_price",
        "best_ask",
    ):
        value = payload.get(key)
        if value is None or value == "":
            continue
        try:
            price = float(value)
        except (TypeError, ValueError):
            continue
        if price > 0:
            return price
    return None


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
        """

        bars: list[dict[str, Any]] = []
        for row in self._visible_events(
            observation_time_ns=observation_time_ns,
            instrument_id=instrument_id,
            provider_generation=provider_generation,
        ):
            payload = row.envelope.get("payload") if isinstance(row.envelope.get("payload"), dict) else {}
            price = _snapshot_price(payload)
            if price is None:
                continue
            price_minor = int(round(float(price) * price_scale))
            display = f"{float(price):.4f}"
            bars.append(
                {
                    "available_time": row.available_time_ns,
                    "bar_payload": {
                        "close": display,
                        "event_time": row.event_time_ns,
                        "high": display,
                        "low": display,
                        "open": display,
                        "provider": row.provider,
                        "quality": row.quality,
                        "source": "LIVE_L1_SNAPSHOT",
                        "timeframe": LIVE_L1_TIMEFRAME,
                        "volume": SIMULATION_POLICY_VOLUME,
                        "volume_basis": "SIMULATION_POLICY",
                    },
                    "close_minor": price_minor,
                    "event_time": row.event_time_ns,
                    "event_type": "BAR_OHLCV_1M",
                    "high_minor": price_minor,
                    "instrument_id": row.instrument_id,
                    "low_minor": price_minor,
                    "open_minor": price_minor,
                    "provider": row.provider,
                    "provider_generation": row.provider_generation,
                    "quality": row.quality,
                    "source": "LIVE_L1_SNAPSHOT",
                    "volume": SIMULATION_POLICY_VOLUME,
                    "volume_basis": "SIMULATION_POLICY",
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
