"""RT-01 bounded in-memory trace collector."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from .enums import CollectorOutcome
from .span import TraceSpan
from .validation import validate_spans


@dataclass
class CollectorCounts:
    accepted: int = 0
    written: int = 0
    dropped: int = 0
    failed: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "accepted": self.accepted,
            "written": self.written,
            "dropped": self.dropped,
            "failed": self.failed,
        }


@dataclass
class InMemoryTraceCollector:
    max_spans: int = 10_000
    spans: list[TraceSpan] = field(default_factory=list)
    counts: CollectorCounts = field(default_factory=CollectorCounts)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _available: bool = True

    def mark_unavailable(self) -> None:
        with self._lock:
            self._available = False

    def record(self, span: TraceSpan) -> CollectorOutcome:
        with self._lock:
            self.counts.accepted += 1
            if not self._available:
                self.counts.failed += 1
                return CollectorOutcome.FAILED
            if len(self.spans) >= self.max_spans:
                self.counts.dropped += 1
                return CollectorOutcome.DROPPED
            self.spans.append(span)
            self.counts.written += 1
            return CollectorOutcome.WRITTEN

    def export_spans(self) -> list[dict[str, Any]]:
        with self._lock:
            return [span.to_dict() for span in self.spans]

    def validate(self) -> list[dict[str, str]]:
        findings = validate_spans(self.spans)
        return [{"code": f.code, "message": f.message, "span_id": f.span_id or ""} for f in findings]

    def clear(self) -> None:
        with self._lock:
            self.spans.clear()
            self.counts = CollectorCounts()


__all__ = ["CollectorCounts", "InMemoryTraceCollector"]
