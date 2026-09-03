"""Prepared immutable snapshot state for calculators (BUILD 06)."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.event import EventV1
from ..contracts.snapshot import SnapshotV1
from ..snapshots.resolver import SnapshotResolvedState
from ..temporal.validation import event_sort_key


_QUOTE_TYPES = frozenset({"QUOTE", "L1"})
_TRADE_TYPES = frozenset({"TRADE", "TICK"})
_BOOK_TYPES = frozenset({"BOOK", "DEPTH", "ORDER_BOOK"})


def _event_type_key(event: EventV1) -> str:
  return str(event.event_type).upper()


@dataclass(frozen=True, slots=True)
class PreparedSnapshotState:
  """Canonical sorted event partitions derived from resolved snapshot state."""

  snapshot: SnapshotV1
  events: tuple[EventV1, ...]
  quotes: tuple[EventV1, ...]
  trades: tuple[EventV1, ...]
  books: tuple[EventV1, ...]
  decision_time_ns: int

  @classmethod
  def from_resolved(cls, resolved: SnapshotResolvedState) -> PreparedSnapshotState:
    events = tuple(sorted(resolved.events, key=event_sort_key))
    quotes: list[EventV1] = []
    trades: list[EventV1] = []
    books: list[EventV1] = []
    for event in events:
      kind = _event_type_key(event)
      if kind in _QUOTE_TYPES:
        quotes.append(event)
      elif kind in _TRADE_TYPES:
        trades.append(event)
      elif kind in _BOOK_TYPES:
        books.append(event)
    return cls(
      snapshot=resolved.snapshot,
      events=events,
      quotes=tuple(quotes),
      trades=tuple(trades),
      books=tuple(books),
      decision_time_ns=resolved.snapshot.decision_time_ns,
    )

  def events_in_time_window(
    self,
    events: tuple[EventV1, ...],
    *,
    window_ns: int,
  ) -> tuple[EventV1, ...]:
    """Return events with event_time in (decision-window, decision] and available <= decision."""
    start_ns = self.decision_time_ns - window_ns
    selected: list[EventV1] = []
    for event in events:
      if event.available_time_ns > self.decision_time_ns:
        continue
      if event.event_time_ns <= start_ns:
        continue
      if event.event_time_ns > self.decision_time_ns:
        continue
      selected.append(event)
    return tuple(selected)

  def latest_quote(self) -> EventV1 | None:
    eligible = [
      event
      for event in self.quotes
      if event.available_time_ns <= self.decision_time_ns
      and event.event_time_ns <= self.decision_time_ns
    ]
    if not eligible:
      return None
    return max(eligible, key=event_sort_key)

  def latest_book(self) -> EventV1 | None:
    eligible = [
      event
      for event in self.books
      if event.available_time_ns <= self.decision_time_ns
      and event.event_time_ns <= self.decision_time_ns
    ]
    if not eligible:
      return None
    return max(eligible, key=event_sort_key)


__all__ = ["PreparedSnapshotState"]
