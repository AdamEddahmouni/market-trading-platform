"""Replay session state backed by admitted fixture pipeline outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..adapters.equity_intraday_jsonl import EquityIntradayJsonlAdapter, SOURCE_OBJECT_ID
from ..assistant.audit_store import AssistantAuditStore
from ..assistant.service import AssistantResearchService
from ..canonical import canonical_bytes, sha256_bytes
from ..contracts.identity import sort_events
from ..features.bar_features import derive_bar_features
from ..risk_simulation.evaluation import run_risk_simulation_evaluation
from ..storage.bounded_memory_cache import BoundedMemoryCache
from ..strategy.evaluation import run_strategy_evaluation


def _bars_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bars = [event for event in events if event.get("event_type") == "BAR_OHLCV_1M"]
    return sorted(bars, key=lambda row: (int(row["available_time"]), str(row["normalized_event_id"])))


def _epoch_ns_to_iso(epoch_ns: int) -> str:
    seconds = epoch_ns // 1_000_000_000
    nanos = epoch_ns % 1_000_000_000
    from datetime import datetime, timezone

    dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{nanos:09d}Z"


@dataclass
class ReplayStore:
    """In-memory replay store projecting canonical pipeline outputs."""

    collection_root: Any
    timezone: str = "America/New_York"
    mode: str = "REPLAY"
    assistant_audit_root: Path | None = None
    cursor_index: int = 0
    page_size: int = 10
    _events: list[dict[str, Any]] = field(default_factory=list, init=False, repr=False)
    _bars: list[dict[str, Any]] = field(default_factory=list, init=False, repr=False)
    _evaluation: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _strategy: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _instrument_id: str = field(default="", init=False, repr=False)
    _session_id: str = field(default="", init=False, repr=False)
    _assistant_service: AssistantResearchService = field(init=False, repr=False)
    _feature_cache: BoundedMemoryCache = field(init=False, repr=False)

    @property
    def assistant_service(self) -> AssistantResearchService:
        return self._assistant_service

    def load(self) -> None:
        self._feature_cache = BoundedMemoryCache(max_bytes=256 * 1024, max_entries=32)
        ingest_run_id = sha256_bytes(
            canonical_bytes({"collection_root_id": "ROOT-2E7C91F4", "source_object_id": SOURCE_OBJECT_ID})
        )
        adapter = EquityIntradayJsonlAdapter(ingest_run_id=ingest_run_id)
        result = adapter.ingest_collection(self.collection_root)
        self._events = sort_events(result.canonical_events)
        self._bars = _bars_from_events(self._events)
        if not self._bars:
            raise ValueError("UI_STORE_NO_BARS")
        self._instrument_id = str(self._bars[0]["instrument_id"])
        self._evaluation = run_risk_simulation_evaluation(self._events)
        self._strategy = run_strategy_evaluation(self._events)
        self.cursor_index = len(self._bars) - 1
        self._session_id = sha256_bytes(
            canonical_bytes(
                {
                    "instrument_id": self._instrument_id,
                    "source_object_id": SOURCE_OBJECT_ID,
                    "bar_count": len(self._bars),
                }
            )
        )
        audit_root = self.assistant_audit_root
        if audit_root is None:
            audit_root = Path(__file__).resolve().parents[3] / "evidence" / "ui1" / "assistant-audit"
        self._assistant_service = AssistantResearchService(AssistantAuditStore(audit_root))

    @property
    def instrument_id(self) -> str:
        return self._instrument_id

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def bars(self) -> list[dict[str, Any]]:
        return self._bars

    @property
    def evaluation(self) -> dict[str, Any]:
        return self._evaluation

    @property
    def strategy(self) -> dict[str, Any]:
        return self._strategy

    def current_bar(self) -> dict[str, Any]:
        return self._bars[self.cursor_index]

    def prediction_cutoff(self) -> int:
        return int(self.current_bar()["available_time"])

    def as_of_time(self) -> str:
        return _epoch_ns_to_iso(self.prediction_cutoff())

    def bars_visible(self) -> list[dict[str, Any]]:
        cutoff = self.prediction_cutoff()
        return [bar for bar in self._bars if int(bar["available_time"]) <= cutoff]

    def bar_features_at_cutoff(self) -> list[dict[str, object]]:
        key = self._feature_cache.cache_key(
            "replay.bar_features",
            instrument_id=self._instrument_id,
            prediction_cutoff=self.prediction_cutoff(),
        )
        payload = self._feature_cache.get_or_load(
            key,
            lambda: canonical_bytes(self._compute_bar_features_payload()),
        )
        import json

        from ..canonical import _pairs_no_duplicates

        decoded = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates)
        if not isinstance(decoded, list):
            return []
        return [row for row in decoded if isinstance(row, dict)]

    def _compute_bar_features_payload(self) -> list[dict[str, object]]:
        bars_by_instrument = {self._instrument_id: self.current_bar()}
        features, _ = derive_bar_features(
            bars_by_instrument,
            prediction_cutoff=self.prediction_cutoff(),
        )
        return features

    def feature_cache_report(self) -> dict[str, object]:
        return self._feature_cache.report()

    def set_cursor_index(self, index: int) -> None:
        if index < 0 or index >= len(self._bars):
            raise ValueError("UI_REPLAY_CURSOR_OUT_OF_RANGE")
        self.cursor_index = index

    def set_cursor_by_time(self, available_time: int) -> None:
        for idx, bar in enumerate(self._bars):
            if int(bar["available_time"]) == available_time:
                self.cursor_index = idx
                return
        raise ValueError("UI_REPLAY_TIME_NOT_FOUND")
