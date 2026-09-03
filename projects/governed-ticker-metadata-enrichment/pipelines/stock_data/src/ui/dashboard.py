"""Multi-stage pipeline progress dashboard.

`LivePipelineDashboard` keeps per-stage status records and renders an
up-to-date table showing each stage's state (pending, running, complete,
error) along with elapsed time, record counts, and rate. The panel is
rendered on demand — `pipeline.run_all` calls `dashboard.print()`
between stages, so it works alongside the per-stage `LiveProgress` bars
without nesting rich Live contexts.

Example:

    with LivePipelineDashboard(stages=[
        "Discover", "Prices", "Fundamentals", "Export",
    ]) as dash:
        dash.start("Discover")
        run_discovery()
        dash.complete("Discover", records=5234)
        dash.start("Prices")
        run_prices()
        dash.complete("Prices", records=2_000_000, errors=12)
    dash.print_summary()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from rich.table import Table

from src.ui._styles import (
    COLOR_COMPLETE,
    COLOR_ERROR,
    COLOR_PENDING,
    COLOR_RECORD,
    COLOR_RUNNING,
    console,
)


class StageStatus(str, Enum):
    """Lifecycle status of a pipeline stage."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class StageState:
    """Per-stage state tracked by `LivePipelineDashboard`."""
    name: str
    status: StageStatus = StageStatus.PENDING
    records: int = 0
    errors: int = 0
    started_at: Optional[float] = None
    finished_at: Optional[float] = None

    @property
    def elapsed_seconds(self) -> float:
        """Wall-clock duration of this stage, in seconds."""
        if self.started_at is None:
            return 0.0
        end = self.finished_at if self.finished_at is not None else time.monotonic()
        return end - self.started_at

    @property
    def rate_per_sec(self) -> float:
        """Records-per-second if the stage has finished."""
        elapsed = self.elapsed_seconds
        if elapsed <= 0 or self.records == 0:
            return 0.0
        return self.records / elapsed


def _format_duration(seconds: float) -> str:
    """Compact human duration (`1m 23s`, `4.5s`, `0s`)."""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def _status_style(status: StageStatus) -> str:
    if status is StageStatus.RUNNING:
        return COLOR_RUNNING
    if status is StageStatus.COMPLETE:
        return COLOR_COMPLETE
    if status is StageStatus.ERROR:
        return COLOR_ERROR
    return COLOR_PENDING


def _status_glyph(status: StageStatus) -> str:
    if status is StageStatus.RUNNING:
        return "[*]"
    if status is StageStatus.COMPLETE:
        return "[OK]"
    if status is StageStatus.ERROR:
        return "[!!]"
    return "[ ]"


class LivePipelineDashboard:
    """Sequential pipeline progress dashboard.

    Stages are passed in execution order; their state updates are
    idempotent (calling `start` twice just resets the `started_at`
    timestamp). The dashboard itself owns no live rendering — the
    orchestrator calls `render()` between stage transitions.
    """

    def __init__(self, stages: List[str], title: str = "Pipeline Progress"):
        if not stages:
            raise ValueError("dashboard requires at least one stage")
        self.stages = list(stages)
        self.title = title
        self.states: Dict[str, StageState] = {s: StageState(name=s) for s in stages}
        self.overall_start = time.monotonic()
        self.overall_end: Optional[float] = None

    # ── Stage state transitions ──

    def start(self, name: str) -> None:
        """Mark `name` as RUNNING."""
        self._require(name).status = StageStatus.RUNNING
        self._require(name).started_at = time.monotonic()

    def complete(self, name: str, records: int = 0, errors: int = 0) -> None:
        """Mark `name` as COMPLETE with final counts."""
        s = self._require(name)
        s.status = StageStatus.COMPLETE
        s.records = records
        s.errors = errors
        s.finished_at = time.monotonic()

    def fail(self, name: str, errors: int = 0) -> None:
        """Mark `name` as ERROR. Use this for mid-stage crashes."""
        s = self._require(name)
        s.status = StageStatus.ERROR
        s.errors = errors
        s.finished_at = time.monotonic()

    def finalize(self) -> None:
        """Stamp the overall end time; called when orchestration is done."""
        self.overall_end = time.monotonic()

    # ── Rendering ──

    def render(self) -> Table:
        """Return a `rich.Table` snapshot of the dashboard state."""
        table = Table(title=self.title, show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim", justify="right", width=3)
        table.add_column("Stage", style="bold white", no_wrap=True)
        table.add_column("Status", width=10)
        table.add_column("Records", justify="right", style=COLOR_RECORD)
        table.add_column("Errors", justify="right")
        table.add_column("Elapsed", justify="right", style=COLOR_RUNNING)
        table.add_column("Rate", justify="right", style="dim")

        for idx, name in enumerate(self.stages, start=1):
            s = self.states[name]
            style = _status_style(s.status)
            table.add_row(
                str(idx),
                s.name,
                f"{_status_glyph(s.status)} [{style}]{s.status.value}[/]",
                f"{s.records:,}",
                f"{s.errors:,}",
                _format_duration(s.elapsed_seconds),
                f"{s.rate_per_sec:.1f}/s" if s.rate_per_sec else "—",
            )

        overall = (self.overall_end or time.monotonic()) - self.overall_start
        total_records = sum(s.records for s in self.states.values())
        total_errors = sum(s.errors for s in self.states.values())
        table.add_section()
        table.add_row(
            "", "TOTAL", "", f"{total_records:,}", f"{total_errors:,}",
            _format_duration(overall), "",
        )
        return table

    def print(self) -> None:
        """Print the dashboard to the shared `console`."""
        console.print(self.render())

    def print_summary(self) -> None:
        """Print a final summary panel after orchestration has finished."""
        self.finalize()
        console.print(self.render())

    # ── Internal helpers ──

    def _require(self, name: str) -> StageState:
        if name not in self.states:
            raise KeyError(
                f"stage '{name}' is not registered on this dashboard; "
                f"registered stages: {self.stages}"
            )
        return self.states[name]
