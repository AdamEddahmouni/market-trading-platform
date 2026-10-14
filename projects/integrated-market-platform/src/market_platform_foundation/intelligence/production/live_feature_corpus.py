"""Live point-in-time feature corpus for the Path A PRODUCTION specialist (Paper only, default off).

The PRODUCTION specialist (``model.fit_production_specialist``) and its calibrator need labelled
examples: a ``SnapshotV1`` plus the two schema signals (``momentum_simple`` and ``net_signed_share``
over 300 s) at a decision time, and the realised direction one Path A horizon later. Nothing in the
running platform records those from live data. This module does, from the existing pieces only:

    admitted live Moomoo QUOTE / TICKER observations
      -> the runtime's existing observation-ingress hook (``attach_observation_ingress``)
      -> existing BUILD 03 normalization (``EventV1``)
      -> a bounded in-memory window (this module; nothing is written to the canonical store)
      -> existing ``build_snapshot`` + ``FastSignalEngine`` at a fixed decision grid
      -> one JSONL ``decision`` row, accepted only if the specialist's own feature extractor accepts it
      -> one JSONL ``label`` row when the first quote at or after decision + horizon is observed.

What it never does: mint a forecast, call a model, place or size an order, backfill a missed grid
point, read a quote that was not yet available at the decision time, or invent a terminal price. A
grid point without enough evidence is recorded with its reason; a horizon without a terminal quote
inside the tolerance is recorded ``UNLABELABLE``.

The label is the sign of the quote midpoint change from the decision reference (the last quote
available at the decision time) to the terminal quote (the first quote available at or after
decision + horizon). An unchanged midpoint is ``UNLABELABLE``, never a class.

Snapshots are stored without their per-event reference list, which for liquid names runs to
thousands of ids per row; the row keeps the snapshot id, the event count and a SHA-256 digest of the
sorted event ids instead (``source_event_digest``). Signals are stored whole.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from ..contracts.common import IntelligenceScope
from ..contracts.event import EventV1
from ..contracts.signal import signal_v1_from_dict, signal_v1_to_dict
from ..contracts.snapshot import SnapshotV1, snapshot_v1_from_dict, snapshot_v1_to_dict
from .identity import PATH_A_PRODUCTION_FEATURE_SCHEMA, path_a_horizon

SCHEMA_VERSION = "imp-live-feature-corpus/1.0.0"
CONSUMER_ID = "paper-forecast-corpus"
DECISION_KIND = "decision"
LABEL_KIND = "label"
LABEL_RULE = "QUOTE_MIDPOINT_SIGN_AT_FIRST_QUOTE_AT_OR_AFTER_HORIZON"
WINDOW_NS = 300 * 1_000_000_000
DEFAULT_GRID_SECONDS = 30
DEFAULT_TERMINAL_TOLERANCE_NS = 60 * 1_000_000_000
# Liquid names print thousands of trades in five minutes; the snapshot must see the whole window.
MAX_WINDOW_EVENTS = 60_000


def _now_ns() -> int:
    return time.time_ns()


def _midpoint(event: EventV1) -> float | None:
    payload = event.payload or {}
    mid = payload.get("midpoint")
    if isinstance(mid, (int, float)) and mid > 0:
        return float(mid)
    bid, ask = payload.get("bid"), payload.get("ask")
    if isinstance(bid, (int, float)) and isinstance(ask, (int, float)) and bid > 0 and ask > 0 and ask >= bid:
        return (float(bid) + float(ask)) / 2.0
    return None


class _Receipt:
    """The router contract only needs ``duplicate``; the live runtime counts it."""

    __slots__ = ("event_id", "duplicate")

    def __init__(self, event_id: str, duplicate: bool) -> None:
        self.event_id = event_id
        self.duplicate = duplicate


class RollingEventWindow:
    """Bounded, per-instrument, in-memory window of normalized QUOTE and TRADE events.

    Implements the ``dispatch(event, *, context, ...)`` shape of ``ObservationIngressRouter`` so the
    live runtime can feed it through its existing opt-in hook. It keeps only what a decision and its
    settlement can still need (window + horizon + tolerance) and never writes anywhere.
    """

    EVENT_TYPES = ("QUOTE", "TRADE")

    def __init__(self, *, retain_ns: int, instruments: Callable[[], Iterable[str]] | None = None,
                 max_events_per_instrument: int = MAX_WINDOW_EVENTS * 2, clock: Callable[[], int] = _now_ns) -> None:
        self.retain_ns = int(retain_ns)
        self.instruments = instruments
        self.max_events = int(max_events_per_instrument)
        self.clock = clock
        self._events: dict[str, deque[EventV1]] = {}
        # Bounded duplicate index: the deque fixes the order of forgetting, the set answers membership in O(1).
        # This runs on the provider callback thread for every pushed event, so it must never scan.
        self._seen: dict[str, tuple[deque[str], set[str]]] = {}
        self._lock = threading.Lock()
        self.metrics = dict(accepted=0, duplicates=0, ignored=0, evicted=0)

    def dispatch(self, event: EventV1, *, context: Any = None, allow_duplicate_replay: bool = False) -> _Receipt:
        iid = event.instrument_id
        wanted = set(self.instruments()) if self.instruments is not None else None
        if not iid or str(event.event_type).upper() not in self.EVENT_TYPES or (wanted is not None and iid not in wanted):
            self.metrics["ignored"] += 1
            return _Receipt(event.event_id, False)
        with self._lock:
            order, seen = self._seen.setdefault(iid, (deque(), set()))
            if event.event_id in seen:
                self.metrics["duplicates"] += 1
                return _Receipt(event.event_id, True)
            order.append(event.event_id)
            seen.add(event.event_id)
            if len(order) > self.max_events:
                seen.discard(order.popleft())
            rows = self._events.setdefault(iid, deque())
            rows.append(event)
            self.metrics["accepted"] += 1
            self._evict(iid, self.clock())
        return _Receipt(event.event_id, False)

    def _evict(self, iid: str, now_ns: int) -> None:
        rows = self._events.get(iid)
        floor = now_ns - self.retain_ns
        while rows and (rows[0].available_time_ns < floor or len(rows) > self.max_events):
            rows.popleft()
            self.metrics["evicted"] += 1

    def events(self, iid: str, *, available_from_ns: int, available_to_ns: int) -> list[EventV1]:
        """Events whose availability falls in (from, to]: nothing later than the decision is visible."""
        with self._lock:
            return [e for e in self._events.get(iid, ()) if available_from_ns < e.available_time_ns <= available_to_ns]

    def last_quote_at_or_before(self, iid: str, available_ns: int) -> EventV1 | None:
        with self._lock:
            for event in reversed(self._events.get(iid, ())):
                if event.available_time_ns <= available_ns and event.event_type == "QUOTE" and _midpoint(event) is not None:
                    return event
        return None

    def first_quote_at_or_after(self, iid: str, available_ns: int) -> EventV1 | None:
        with self._lock:
            for event in self._events.get(iid, ()):
                if event.available_time_ns >= available_ns and event.event_type == "QUOTE" and _midpoint(event) is not None:
                    return event
        return None

    def counts(self) -> dict[str, int]:
        with self._lock:
            return {iid: len(rows) for iid, rows in self._events.items()}


def compute_decision(window: RollingEventWindow, iid: str, decision_time_ns: int) -> dict[str, Any]:
    """One grid point: the existing snapshot builder and signal engine over the visible window only."""
    row, snapshot, signals = decision_inputs(window, iid, decision_time_ns)
    if snapshot is None:
        return row
    refs = sorted(ref.id for ref in snapshot.source_event_refs)
    compact = snapshot_v1_to_dict(replace(snapshot, source_event_refs=()))
    compact["metadata"] = {**compact.get("metadata", {}), "source_event_count": len(refs),
                           "source_event_digest": hashlib.sha256("\n".join(refs).encode()).hexdigest(),
                           "source_event_refs_omitted": True}
    row.update(snapshot=compact, signals=[signal_v1_to_dict(s) for s in signals])
    return row


def decision_inputs(window: RollingEventWindow, iid: str, decision_time_ns: int, *,
                    scope: IntelligenceScope | None = None) -> tuple[dict[str, Any], SnapshotV1 | None, tuple]:
    """The decision row plus the snapshot and signals behind it (``None`` and ``()`` when refused).

    ``scope`` lets a caller key the snapshot by an exact alias of ``iid`` (its qualified canonical id). The
    observed events keep their own ``event_id``; only the instrument key they are filed under changes.
    """
    from ..persistence import InMemoryIntelligenceRepository
    from ..signals.engine import compute_from_snapshot
    from ..signals.models import SignalComputationRequest
    from ..snapshots import SnapshotBuildRequest, SnapshotCompositionPolicy
    from ..snapshots.builder import build_snapshot
    from .model import _extract_features

    scope = scope or IntelligenceScope(instrument_ids=(iid,))
    if len(scope.instrument_ids) != 1:
        raise ValueError("DECISION_SCOPE_MUST_NAME_ONE_INSTRUMENT")
    key = scope.instrument_ids[0]
    row: dict[str, Any] = dict(schema_version=SCHEMA_VERSION, kind=DECISION_KIND, instrument_id=iid,
                               decision_time_ns=decision_time_ns,
                               decision_time=datetime.fromtimestamp(decision_time_ns / 1e9, UTC).isoformat())
    events = window.events(iid, available_from_ns=decision_time_ns - WINDOW_NS, available_to_ns=decision_time_ns)
    reference = window.last_quote_at_or_before(iid, decision_time_ns)
    row["event_counts"] = dict(QUOTE=sum(e.event_type == "QUOTE" for e in events), TRADE=sum(e.event_type == "TRADE" for e in events))
    row["reference"] = None if reference is None else dict(
        event_id=reference.event_id, midpoint=_midpoint(reference), available_time_ns=reference.available_time_ns,
        age_ms=(decision_time_ns - reference.available_time_ns) // 1_000_000)
    if reference is None:
        row.update(accepted=False, reason="NO_REFERENCE_QUOTE")
        return row, None, ()
    if not events:
        row.update(accepted=False, reason="NO_EVENTS_IN_WINDOW")
        return row, None, ()
    if len(events) > MAX_WINDOW_EVENTS:
        row.update(accepted=False, reason="WINDOW_EVENT_CAP_EXCEEDED")
        return row, None, ()
    repository = InMemoryIntelligenceRepository()
    for event in events:
        repository.put_event(event if key == iid else replace(event, instrument_id=key))
    request = SnapshotBuildRequest(
        decision_time_ns=decision_time_ns, scope=scope,
        composition_policy=SnapshotCompositionPolicy(policy_id="paper-forecast-corpus", max_events=MAX_WINDOW_EVENTS,
                                                     lookback_ns=WINDOW_NS, event_types=RollingEventWindow.EVENT_TYPES,
                                                     include_signals=False))
    try:
        snapshot = build_snapshot(repository, request).snapshot
        signals = compute_from_snapshot(snapshot, repository, SignalComputationRequest(
            window_ns=WINDOW_NS, signal_types=frozenset(s.signal_type for s in PATH_A_PRODUCTION_FEATURE_SCHEMA.selectors))).signals
    except Exception as exc:  # noqa: BLE001 - an unbuildable grid point is recorded with its reason, never forced
        row.update(accepted=False, reason=f"{type(exc).__name__}:{str(exc)[:160]}")
        return row, None, ()
    vector = _extract_features(snapshot, signals)
    row["features"] = {s.signal_type: s.value for s in signals}
    if vector is None:
        row.update(accepted=False, reason="SPECIALIST_FEATURE_EXTRACTION_REFUSED")
        return row, None, ()
    row.update(accepted=True, reason=None, feature_vector=list(vector.values))
    return row, snapshot, tuple(signals)


def settle(window: RollingEventWindow, decision: dict[str, Any], *, now_ns: int,
           horizon_ns: int, tolerance_ns: int = DEFAULT_TERMINAL_TOLERANCE_NS) -> dict[str, Any] | None:
    """The label row for one accepted decision, or None while it cannot be settled yet."""
    due = decision["decision_time_ns"] + horizon_ns
    if now_ns < due:
        return None
    terminal = window.first_quote_at_or_after(decision["instrument_id"], due)
    base = dict(schema_version=SCHEMA_VERSION, kind=LABEL_KIND, instrument_id=decision["instrument_id"],
                decision_time_ns=decision["decision_time_ns"], horizon_ns=horizon_ns, label_rule=LABEL_RULE)
    if terminal is None or terminal.available_time_ns > due + tolerance_ns:
        if now_ns < due + tolerance_ns:
            return None
        return dict(base, label=None, status="UNLABELABLE", reason="NO_TERMINAL_QUOTE_IN_TOLERANCE")
    start, end = decision["reference"]["midpoint"], _midpoint(terminal)
    common = dict(terminal_event_id=terminal.event_id, terminal_midpoint=end, label_available_time_ns=terminal.available_time_ns,
                  reference_midpoint=start)
    if end == start:
        return dict(base, **common, label=None, status="UNLABELABLE", reason="MIDPOINT_UNCHANGED")
    return dict(base, **common, label=1 if end > start else 0, status="SETTLED", reason=None)


@dataclass
class LiveFeatureCorpusRecorder:
    """Fixed-grid recorder. ``tick`` is the whole unit of work; the thread only calls it."""

    window: RollingEventWindow
    directory: Path
    instruments: Callable[[], list[str]]
    session_open: Callable[[int], bool]
    grid_seconds: int = DEFAULT_GRID_SECONDS
    clock: Callable[[], int] = _now_ns
    horizon_ns: int = field(default_factory=lambda: path_a_horizon().duration_ns)
    pending: list[dict[str, Any]] = field(default_factory=list)
    last_grid_ns: int | None = None
    status: dict[str, Any] = field(default_factory=lambda: dict(decisions=0, accepted=0, settled=0, unlabelable=0, refusals={}))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _path(self, at_ns: int) -> Path:
        day = datetime.fromtimestamp(at_ns / 1e9, UTC).strftime("%Y-%m-%d")
        return Path(self.directory) / f"feature-corpus-{day}.jsonl"

    def _write(self, row: dict[str, Any]) -> None:
        path = self._path(row["decision_time_ns"])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    def tick(self) -> None:
        with self._lock:
            now = self.clock()
            for decision in list(self.pending):
                label = settle(self.window, decision, now_ns=now, horizon_ns=self.horizon_ns)
                if label is not None:
                    self._write(label)
                    self.pending.remove(decision)
                    self.status["settled" if label["status"] == "SETTLED" else "unlabelable"] += 1
            grid_ns = self.grid_seconds * 1_000_000_000
            point = now - now % grid_ns
            if point == self.last_grid_ns or not self.session_open(point):
                return
            # A missed grid point stays missed: only the current point is evaluated, never a backlog.
            self.last_grid_ns = point
            for iid in self.instruments():
                row = compute_decision(self.window, iid, point)
                self._write(row)
                self.status["decisions"] += 1
                if row["accepted"]:
                    self.status["accepted"] += 1
                    self.pending.append(dict(instrument_id=iid, decision_time_ns=point, reference=row["reference"]))
                else:
                    refusals = self.status["refusals"]
                    key = str(row["reason"]).split(":")[0]
                    refusals[key] = refusals.get(key, 0) + 1
            self.status.update(last_grid=datetime.fromtimestamp(point / 1e9, UTC).isoformat(), pending=len(self.pending),
                               window=self.window.counts(), window_metrics=dict(self.window.metrics))


def load_training_examples(paths: Iterable[Path]):
    """Join decision and SETTLED label rows into ``ProductionTrainingExample`` values, in decision-time order."""
    from .model import ProductionTrainingExample

    decisions: dict[tuple[str, int], dict[str, Any]] = {}
    labels: dict[tuple[str, int], dict[str, Any]] = {}
    for path in paths:
        with Path(path).open(encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                key = (row["instrument_id"], row["decision_time_ns"])
                if row.get("kind") == DECISION_KIND and row.get("accepted"):
                    decisions[key] = row
                elif row.get("kind") == LABEL_KIND and row.get("status") == "SETTLED":
                    labels[key] = row
    examples = []
    for key in sorted(set(decisions) & set(labels), key=lambda k: (k[1], k[0])):
        decision, label = decisions[key], labels[key]
        snapshot: SnapshotV1 = snapshot_v1_from_dict(decision["snapshot"])
        signals = tuple(signal_v1_from_dict(s) for s in decision["signals"])
        examples.append((key, ProductionTrainingExample(snapshot=snapshot, signals=signals, label=int(label["label"]),
                                                       label_available_time_ns=int(label["label_available_time_ns"]))))
    return examples


__all__ = [
    "CONSUMER_ID",
    "LABEL_RULE",
    "LiveFeatureCorpusRecorder",
    "RollingEventWindow",
    "SCHEMA_VERSION",
    "compute_decision",
    "decision_inputs",
    "load_training_examples",
    "settle",
]
