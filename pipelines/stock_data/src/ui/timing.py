"""Per-stage timing summary tables.

`StageTimingSummary` captures the elapsed duration, record count, and
calculated records-per-second for one completed stage. `render_timing`
formats a list of summaries into a `rich.Table` for terminal output.

The summary is meant to be printed AFTER a stage finishes, either on
its own (single-stage runs) or alongside the multi-stage dashboard
post-run summary in `pipeline.run_all`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from rich.table import Table

from src.ui._styles import COLOR_RECORD, COLOR_RUNNING, console


@dataclass(frozen=True)
class StageTimingSummary:
    """Immutable timing record for a single finished stage."""
    name: str
    elapsed_seconds: float
    records: int = 0
    errors: int = 0

    @property
    def records_per_sec(self) -> float:
        if self.elapsed_seconds <= 0:
            return 0.0
        return self.records / self.elapsed_seconds

    @property
    def formatted_duration(self) -> str:
        """Compact human-friendly duration."""
        s = self.elapsed_seconds
        if s < 1:
            return f"{s*1000:.0f}ms"
        if s < 60:
            return f"{s:.1f}s"
        minutes, secs = divmod(int(s), 60)
        if minutes < 60:
            return f"{minutes}m {secs:02d}s"
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes:02d}m"

    @property
    def formatted_rate(self) -> str:
        return f"{self.records_per_sec:,.0f}/s" if self.records_per_sec else "—"

    def to_row(self) -> tuple:
        """Render this stage as a tuple suitable for `Table.add_row`."""
        return (
            self.name,
            self.formatted_duration,
            f"{self.records:,}",
            f"{self.errors:,}",
            self.formatted_rate,
        )


def render_timing(summaries: Iterable[StageTimingSummary],
                  title: str = "Stage Timing") -> Table:
    """Build (but don't print) a timing table for the given summaries."""
    table = Table(title=title, header_style="bold cyan", show_header=True)
    table.add_column("Stage", style="bold white", no_wrap=True)
    table.add_column("Elapsed", justify="right", style=COLOR_RUNNING)
    table.add_column("Records", justify="right", style=COLOR_RECORD)
    table.add_column("Errors", justify="right")
    table.add_column("Rate", justify="right", style="dim")

    summaries = list(summaries)
    for summary in summaries:
        table.add_row(*summary.to_row())

    if summaries:
        total_elapsed = sum(s.elapsed_seconds for s in summaries)
        total_records = sum(s.records for s in summaries)
        total_errors = sum(s.errors for s in summaries)
        table.add_section()
        overall = StageTimingSummary(
            name="TOTAL",
            elapsed_seconds=total_elapsed,
            records=total_records,
            errors=total_errors,
        )
        table.add_row(*overall.to_row())
    return table


def print_timing(summaries: Iterable[StageTimingSummary],
                 title: str = "Stage Timing") -> None:
    """Print a timing table to the shared `console`."""
    console.print(render_timing(summaries, title=title))
