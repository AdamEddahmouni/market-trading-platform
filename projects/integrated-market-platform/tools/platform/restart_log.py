"""The one restart log the owner reviews (owner decision 3, 2026-10-23: "every restart is logged for review").

One JSON line per event: what came back (or did not), why, when, after how long, and whether Paper resumed.
The keeper writes it; ``report`` prints it as a plain table. The file is bounded: it rotates at ``MAX_BYTES``
and keeps ``KEEP`` older files, so it can never grow without limit.

Records only reason codes, counts and times: no environment, credential or request body is written.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

SCHEMA = "imp-restart-log/1.0.0"
MAX_BYTES = 5 * 1024 * 1024
KEEP = 4
COMPONENTS = ("PC", "KEEPER", "OPEND", "COLLECTOR", "PLATFORM", "PAPER_CONTROLLER")
_DETAIL_CHARS = 300


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class RestartLog:
    def __init__(self, path: Path, *, max_bytes: int = MAX_BYTES, keep: int = KEEP,
                 clock: Callable[[], float] = time.time) -> None:
        self.path, self.max_bytes, self.keep, self.clock = Path(path), int(max_bytes), int(keep), clock

    def record(self, component: str, event: str, *, cause: str | None = None, outcome: str | None = None,
               attempt: int | None = None, down_seconds: float | None = None, **detail: Any) -> dict[str, Any]:
        if component not in COMPONENTS:
            raise ValueError(f"RESTART_LOG_COMPONENT_UNKNOWN:{component}")
        now = self.clock()
        entry = {"schema": SCHEMA, "at": _iso(now), "at_epoch": round(now, 3), "component": component, "event": event,
                 "cause": cause, "outcome": outcome, "attempt": attempt,
                 "down_seconds": None if down_seconds is None else round(max(0.0, float(down_seconds)), 1),
                 "detail": {key: (value if isinstance(value, (int, float, bool)) or value is None else str(value)[:_DETAIL_CHARS])
                            for key, value in sorted(detail.items())}}
        line = json.dumps(entry, sort_keys=True) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._rotate(len(line.encode("utf-8")))
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line)
        return entry

    def _rotate(self, incoming: int) -> None:
        try:
            size = self.path.stat().st_size
        except OSError:
            return
        if size + incoming <= self.max_bytes:
            return
        # Oldest first: .KEEP is dropped, every other file moves one place up, the live file becomes .1.
        self._numbered(self.keep).unlink(missing_ok=True)
        for index in range(self.keep - 1, 0, -1):
            source = self._numbered(index)
            if source.exists():
                os.replace(source, self._numbered(index + 1))
        os.replace(self.path, self._numbered(1))

    def _numbered(self, index: int) -> Path:
        return self.path.with_name(f"{self.path.name}.{index}")

    def read(self, days: float | None = None) -> list[dict[str, Any]]:
        """Every readable entry, oldest first; ``days`` keeps only the most recent days. A torn line is skipped."""
        since = None if days is None else self.clock() - float(days) * 86400
        entries: list[dict[str, Any]] = []
        for path in [self._numbered(index) for index in range(self.keep, 0, -1)] + [self.path]:
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict) and (since is None or float(entry.get("at_epoch") or 0) >= since):
                    entries.append(entry)
        return entries


def report(entries: Iterable[dict[str, Any]]) -> str:
    """A plain table, newest last, in the PC's local time."""
    rows = [("When (local)", "What", "Event", "Why", "Result", "Down")]
    for entry in entries:
        try:
            when = datetime.fromtimestamp(float(entry["at_epoch"])).strftime("%Y-%m-%d %H:%M:%S")
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            when = str(entry.get("at") or "?")
        down = entry.get("down_seconds")
        rows.append((when, str(entry.get("component") or ""), str(entry.get("event") or ""), str(entry.get("cause") or ""),
                     str(entry.get("outcome") or ""), "" if down is None else _duration(float(down))))
    if len(rows) == 1:
        return "No restarts recorded."
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return "\n".join("  ".join(cell.ljust(width) for cell, width in zip(row, widths)).rstrip() for row in rows)


def _duration(seconds: float) -> str:
    seconds = int(round(seconds))
    if seconds < 120:
        return f"{seconds}s"
    if seconds < 7200:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


__all__ = ["COMPONENTS", "KEEP", "MAX_BYTES", "RestartLog", "SCHEMA", "report"]
