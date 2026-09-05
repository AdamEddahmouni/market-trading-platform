"""Replay session state backed by admitted fixture pipeline outputs."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..adapters.equity_intraday_jsonl import (
    COLLECTION_RELATIVE_PATH,
    PINNED_SHA256,
    EquityIntradayJsonlAdapter,
    SOURCE_OBJECT_ID,
)
from ..assistant.audit_store import AssistantAuditStore
from ..assistant.inference_factory import resolve_assistant_inference
from ..assistant.service import AssistantResearchService
from ..canonical import _pairs_no_duplicates, canonical_bytes, sha256_bytes
from ..contracts.identity import sort_events
from ..features.bar_features import derive_bar_features
from ..features.institutional import configure_institutional_ledger
from ..providers.whale_ledger import bootstrap_default_providers
from ..risk_simulation.evaluation import run_risk_simulation_evaluation
from ..storage.bounded_memory_cache import BoundedMemoryCache
from ..strategy.evaluation import run_strategy_evaluation
from ..paper.ledger import PaperExecutionLedger


TRACKED_ASSISTANT_AUDIT_ROOT = (
    Path(__file__).resolve().parents[3] / "evidence" / "ui1" / "assistant-audit"
)


def _bars_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bars = [event for event in events if event.get("event_type") == "BAR_OHLCV_1M"]
    return sorted(bars, key=lambda row: (int(row["available_time"]), str(row["normalized_event_id"])))


def _epoch_ns_to_iso(epoch_ns: int) -> str:
    seconds = epoch_ns // 1_000_000_000
    nanos = epoch_ns % 1_000_000_000
    from datetime import datetime, timezone

    dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{nanos:09d}Z"


def _replay_source_digest(collection_root: Any) -> str:
    source_path = Path(collection_root) / COLLECTION_RELATIVE_PATH
    if not source_path.is_file():
        raise ValueError("UI_STORE_SOURCE_MISSING")
    digest = sha256_bytes(source_path.read_bytes())
    if digest != PINNED_SHA256:
        raise ValueError("UI_STORE_SOURCE_HASH_MISMATCH")
    return digest


def _build_replay_payload(collection_root: str, source_digest: str) -> bytes:
    """Build the immutable expensive portion of a replay store."""

    if source_digest != PINNED_SHA256:
        raise ValueError("UI_STORE_SOURCE_HASH_MISMATCH")
    ingest_run_id = sha256_bytes(
        canonical_bytes({"collection_root_id": "ROOT-2E7C91F4", "source_object_id": SOURCE_OBJECT_ID})
    )
    adapter = EquityIntradayJsonlAdapter(ingest_run_id=ingest_run_id)
    result = adapter.ingest_collection(Path(collection_root))
    events = sort_events(result.canonical_events)
    bars = _bars_from_events(events)
    if not bars:
        raise ValueError("UI_STORE_NO_BARS")
    instrument_id = str(bars[0]["instrument_id"])
    session_id = sha256_bytes(
        canonical_bytes(
            {
                "instrument_id": instrument_id,
                "source_object_id": SOURCE_OBJECT_ID,
                "bar_count": len(bars),
            }
        )
    )
    return canonical_bytes(
        {
            "evaluation": run_risk_simulation_evaluation(events),
            "events": events,
            "instrument_id": instrument_id,
            "session_id": session_id,
            "strategy": run_strategy_evaluation(events),
        }
    )


@lru_cache(maxsize=4)
def _cached_replay_payload(collection_root: str, source_digest: str) -> bytes:
    """Cache only immutable canonical bytes keyed by verified source content."""

    return _build_replay_payload(collection_root, source_digest)


@dataclass
class ReplayStore:
    """In-memory replay store projecting canonical pipeline outputs."""

    collection_root: Any
    timezone: str = "America/New_York"
    mode: str = "REPLAY"
    data_mode: str = "FIXTURE_REPLAY"
    execution_mode: str = "NONE"
    execution_authority: str = "BLOCKED"
    data_provider: str = "INTERNAL"
    execution_provider: str = "INTERNAL"
    assistant_audit_root: Path | None = None
    strategy_repository: Any | None = None
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
    paper_ledger: PaperExecutionLedger = field(init=False, repr=False)
    execution_deferred: bool = field(default=False, init=False)
    restore_details: dict[str, Any] = field(default_factory=dict, init=False)

    @property
    def assistant_service(self) -> AssistantResearchService:
        return self._assistant_service

    def load(self) -> None:
        self._feature_cache = BoundedMemoryCache(max_bytes=256 * 1024, max_entries=32)
        collection_root = str(Path(self.collection_root).resolve())
        source_digest = _replay_source_digest(collection_root)
        encoded = _cached_replay_payload(collection_root, source_digest)
        decoded = json.loads(encoded.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates)
        if not isinstance(decoded, dict) or not isinstance(decoded.get("events"), list):
            raise ValueError("UI_STORE_CACHE_PAYLOAD_INVALID")
        self._events = [event for event in decoded["events"] if isinstance(event, dict)]
        self._bars = _bars_from_events(self._events)
        if not self._bars:
            raise ValueError("UI_STORE_NO_BARS")
        self._instrument_id = str(decoded.get("instrument_id", ""))
        evaluation = decoded.get("evaluation")
        strategy = decoded.get("strategy")
        if not isinstance(evaluation, dict) or not isinstance(strategy, dict):
            raise ValueError("UI_STORE_CACHE_PAYLOAD_INVALID")
        self._evaluation = evaluation
        self._strategy = strategy
        self.cursor_index = len(self._bars) - 1
        self._session_id = str(decoded.get("session_id", ""))
        ledger = bootstrap_default_providers()
        configure_institutional_ledger(ledger)
        audit_root = self.assistant_audit_root
        if audit_root is None:
            # Tests and ad-hoc ReplayStore constructions must not write into
            # the tracked evidence tree. Callers that intentionally persist
            # assistant-audit evidence pass an explicit root (e.g. the server
            # and evidence-generating tools use TRACKED_ASSISTANT_AUDIT_ROOT).
            audit_root = Path(tempfile.mkdtemp(prefix="imp-assistant-audit-"))
        self._assistant_service = AssistantResearchService(
            AssistantAuditStore(audit_root),
            inference=resolve_assistant_inference(),
        )
        self.paper_ledger = PaperExecutionLedger.open_session(
            replay_session_id=self._session_id,
            instrument_id=self._instrument_id,
            symbol=self.symbol,
        )
        self._bind_local_state()

    def _bind_local_state(self) -> None:
        from ..local_state.startup import (
            persist_ledger,
            persist_ledger_batch,
            restore_open_ledger,
            session_record_from_ledger,
        )
        from ..market_data.live_config import live_observational_enabled, moomoo_live_enabled

        if live_observational_enabled():
            self.data_mode = "LIVE_OBSERVATIONAL"
            self.data_provider = "MOOMOO" if moomoo_live_enabled() else self.data_provider
        self.paper_ledger.data_mode = self.data_mode
        self.paper_ledger.data_provider = self.data_provider
        self.execution_deferred = False
        self.restore_details = {"reason": "PERSISTENCE_DISABLED"}
        current = session_record_from_ledger(self.paper_ledger)
        current["data_mode"] = self.data_mode
        current["data_provider"] = self.data_provider
        current["execution_provider"] = "INTERNAL"
        restored, details = restore_open_ledger(current_config=current)
        self.restore_details = details
        if restored is not None:
            self.paper_ledger = restored
            self.execution_deferred = True
            self.execution_mode = restored.execution_mode
            self.execution_authority = restored.execution_authority
            self.data_mode = restored.data_mode
            self.data_provider = restored.data_provider
            self.execution_provider = restored.execution_provider
            return
        self.paper_ledger.persist_sink = persist_ledger_batch
        persist_ledger(self.paper_ledger)

    @property
    def symbol(self) -> str:
        return self._instrument_id

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

    def bars_for_execution(self) -> list[dict[str, Any]]:
        """Admitted bars from replay cursor forward for deterministic fill simulation."""

        cutoff = self.prediction_cutoff()
        return [bar for bar in self._bars if int(bar["available_time"]) >= cutoff]

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
