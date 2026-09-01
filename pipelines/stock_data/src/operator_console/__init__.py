"""Terminal UI — Rich-based progress bars, interactive menu, dashboard,
ticker filtering, and exports.

Public surface (re-exported for callers like `pipeline.py`,
`scripts/run.py`, and `src.scrapers.base`):

    LiveProgress         - thread-safe progress bar (used by scrapers)
    console              - shared rich.console.Console
    print_header         - prominent section header
    print_stage_header   - numbered stage header
    print_ok / print_warn / print_error
    show_menu            - top-level command picker
    show_help            - alias of `print_help`
    print_help           - rich-formatted help text
    watch_stats          - live-refreshing stats panel
    _build_stats_table   - internal helper used by `show_stats()`

New in this package split (this __init__ re-exports them too):

    LivePipelineDashboard, StageState, StageStatus (from .dashboard)
    StageTimingSummary, render_timing, print_timing (from .timing)
    FilterSpec, prompt_for_filters, parse_filter_args, apply_filter (from .filter)
    ExportRequest, show_export_menu, execute_filtered_export (from .export)

Backward compatibility:
    `from src.operator_console import LiveProgress, show_menu, watch_stats, ...` keeps
    working without changes in callers.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, List, Optional, Tuple

from rich.align import Align
from rich.box import DOUBLE_EDGE, HEAVY, HEAVY_EDGE, SIMPLE
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

# ── Re-export the shared console + styles from `_styles` ──────
from src.operator_console._styles import (
    COLOR_BRAND_PRIMARY,
    COLOR_BRAND_SECONDARY,
    COLOR_RECORD,
    console,
)


# ── Inline definitions that wrap rich primitives ──────────────


class LiveProgress:
    """A live progress bar for parallel scrapers.

    Backwards-compatible implementation kept inline here so existing
    scrapers can `from src.operator_console import LiveProgress` without pulling in
    every dashboard / filter / export sibling on import.

    Usage:
        with LiveProgress(total=1000, description="Scraping...") as pbar:
            for result in results:
                pbar.advance(success=True)
                pbar.advance(success=False)  # counted as error

    Thread-safe: advances from any worker thread (uses internal lock).
    """

    def __init__(
        self,
        total: int,
        description: str = "Processing",
        stage_name: str = "",
        transient: bool = False,
    ):
        from rich.progress import (
            Progress, BarColumn, TextColumn,
            TimeRemainingColumn, TimeElapsedColumn,
            TaskProgressColumn, SpinnerColumn,
        )
        self.total = total
        self.stage_name = stage_name
        self.completed = 0
        self.errors = 0
        self.start_time = time.time()
        self._lock = threading.Lock()
        self._running = False

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn(
                f"[bold cyan]{'[' + stage_name + ']' if stage_name else ''}"
                " {task.description}"
            ),
            BarColumn(bar_width=30),
            TaskProgressColumn(),
            " |",
            TextColumn("{task.completed}/{task.total}"),
            " |",
            TimeRemainingColumn(),
            " |",
            TimeElapsedColumn(),
            " |",
            TextColumn("[green]OK {task.completed - task.fields[err_count]}"),
            TextColumn("[red]ERR {task.fields[err_count]}"),
            transient=transient,
        )
        self._task = self._progress.add_task(
            description, total=total, err_count=0
        )

    def __enter__(self):
        self._running = True
        self._progress.__enter__()
        return self

    def __exit__(self, *args):
        self._running = False
        self._progress.__exit__(*args)

    def advance(self, success: bool = True):
        """Advance the progress bar by one unit."""
        with self._lock:
            if not self._running:
                return
            if success:
                self.completed += 1
            else:
                self.errors += 1
            self._progress.update(
                self._task,
                advance=1,
                err_count=self.errors,
            )


# ── Header / status helpers ──────────────────────────────────


def print_header(title: str, subtitle: str = ""):
    text = Text(title, style="bold cyan", justify="center")
    if subtitle:
        text += Text(f"\n{subtitle}", style="dim white", justify="center")
    panel = Panel(
        Align.center(text),
        box=HEAVY_EDGE,
        border_style="cyan",
        padding=(1, 2),
        width=min(console.width, 80),
    )
    console.print()
    console.print(panel)
    console.print()


def print_stage_header(stage_num: int, title: str, detail: str = ""):
    text = Text(f"STAGE {stage_num}: {title}", style="bold yellow")
    if detail:
        text += Text(f"\n{detail}", style="white")
    panel = Panel(
        Align.left(text),
        box=HEAVY,
        border_style="yellow",
        padding=(0, 2),
        width=min(console.width, 72),
    )
    console.print()
    console.print(panel)


def print_ok(message: str):
    console.print(f"  [[OK]] {message}", style="green")


def print_warn(message: str):
    console.print(f"  [WARN] {message}", style="yellow")


def print_error(message: str):
    console.print(f"  [ERROR] {message}", style="red")


# ── Stats / live watcher ────────────────────────────────────


def _build_stats_table(stats: dict) -> Panel:
    """Build a rich Table from stats dict (used by `watch_stats`, etc.)."""
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    table = Table(
        title=f"Database Statistics -- {now_str}",
        box=HEAVY_EDGE,
        border_style="cyan",
        title_style="bold cyan",
        padding=(0, 2),
    )
    table.add_column("Category", style="bold white", no_wrap=True)
    table.add_column("Count", style="bold yellow", justify="right")

    data_tables = [
        ("Tickers (Active)", stats.get("tickers", 0)),
        ("Daily Prices", stats.get("daily_prices", 0)),
        ("Weekly Prices", stats.get("weekly_prices", 0)),
        ("Monthly Prices", stats.get("monthly_prices", 0)),
        ("Dividends", stats.get("dividends", 0)),
        ("Splits", stats.get("splits", 0)),
        ("Fundamentals", stats.get("fundamentals", 0)),
        ("Income (Annual)", stats.get("income_statements_annual", 0)),
        ("Income (Quarterly)", stats.get("income_statements_quarterly", 0)),
        ("Balance Sheets (Annual)", stats.get("balance_sheets_annual", 0)),
        ("Balance Sheets (Quarterly)", stats.get("balance_sheets_quarterly", 0)),
        ("Cash Flow (Annual)", stats.get("cash_flow_annual", 0)),
        ("Cash Flow (Quarterly)", stats.get("cash_flow_quarterly", 0)),
        ("Supplemental Data", stats.get("supplemental_data", 0)),
        ("Index Membership", stats.get("index_membership", 0)),
        ("Options Chain", stats.get("options_chain", 0)),
        ("Insider Trades", stats.get("insider_trades", 0)),
        ("Earnings Calendar", stats.get("earnings_calendar", 0)),
    ]
    for label, count in data_tables:
        style = "green" if count and count > 100 else ("yellow" if count and count > 0 else "dim")
        table.add_row(label, Text(str(count or 0), style=style))

    dr = stats.get("price_date_range", {})
    if dr.get("min"):
        table.add_section()
        date_range = f"{dr['min']}  ->  {dr['max']}"
        table.add_row("Price Date Range", Text(date_range, style="cyan"))

    table.add_section()
    total_records = sum(
        v for k, v in stats.items()
        if not k.startswith("price") and isinstance(v, (int, float))
    )
    table.add_row("Total Records", Text(f"{total_records:,}", style="bold green"))

    return Panel(
        Align.center(table),
        border_style="cyan",
        padding=(1, 1),
    )


def watch_stats(get_stats_fn: Callable, refresh_seconds: float = 3.0):
    """Live-updating stats monitor (refresh-per-second = 1/refresh_seconds)."""
    from rich.live import Live as RichLive
    try:
        with RichLive(refresh_per_second=1 / refresh_seconds, screen=True) as live:
            while True:
                stats = get_stats_fn()
                table = _build_stats_table(stats)
                live.update(table)
                time.sleep(refresh_seconds)
    except KeyboardInterrupt:
        console.print("\n[dim]Live watch stopped.[/]")


# ── Menu ────────────────────────────────────────────────────


# Use ASCII-safe symbols for Windows terminal compatibility.
# tuple: (key, label, description, command_str)
MENU_OPTIONS: List[Tuple[str, str, str, str]] = [
    ("d", "[DASH] Run All (with dashboard)", "Complete pipeline with multi-stage progress dashboard", "all_dash"),
    ("1", "[ALL]  Run All Stages", "Complete pipeline (legacy plain-text output)", "all"),
    ("2", "[DISC] Discover Tickers", "Fetch tickers from NASDAQ / NYSE", "discover"),
    ("3", "[PRC]  Scrape Prices", "Historical OHLCV price data", "prices"),
    ("4", "[FUN]  Scrape Fundamentals", "Company financials & metrics", "fundamentals"),
    ("5", "[WEB]  Supplemental Scraping", "Yahoo Finance, SEC EDGAR, MarketBeat", "supplemental"),
    ("6", "[IDX]  Index Membership", "S&P 500, Dow Jones, NASDAQ-100", "indexes"),
    ("7", "[OPT]  Options Chain", "Options data (exchange-listed tickers)", "options"),
    ("8", "[ERN]  Earnings Calendar", "EPS estimates & actuals", "earnings"),
    ("9", "[INS]  Insider Trading", "SEC Form 4 filings", "insiders"),
    ("10", "[EXP]  Export (default)", "Parquet + CSV export of everything", "export"),
    ("e", "[EXP+] Export sub-menu", "Pick tables / tickers / format", "export_menu"),
    ("f", "[FLT]  Filter tickers", "Filter preview / scoped scraping / scoped export", "filter_picker"),
    ("s", "[STA]  Show Stats", "Database statistics", "stats"),
    ("w", "[LIVE] Live Watch", "Real-time stats monitor (updates every 3s)", "watch"),
    ("h", "[HELP] Help", "Detailed command reference", "help"),
    ("q", "[QUIT] Quit", "Exit the pipeline menu", "quit"),
]


def show_menu() -> Optional[str]:
    """Display an interactive menu and return the selected command."""
    console.clear()
    title = Panel(
        Align.center(
            Text("Market Data Pipeline -- Control Panel", style="bold cyan"),
        ),
        box=DOUBLE_EDGE,
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(title)
    console.print()

    table = Table(show_header=False, box=SIMPLE, padding=(0, 2))
    table.add_column("Key", style="bold yellow", width=4)
    table.add_column("Command", style="bold white", no_wrap=True)
    table.add_column("Description", style="dim white")

    for key, label, desc, _cmd in MENU_OPTIONS:
        table.add_row(f" {key}) ", label, desc)

    console.print(table)
    console.print()

    choice = Prompt.ask(
        "[bold cyan]Enter choice[/]",
        choices=[opt[0] for opt in MENU_OPTIONS],
        default="d",
        show_choices=False,
    )

    for key, _label, _desc, cmd in MENU_OPTIONS:
        if key == choice:
            return cmd
    return None


# ── Help text (CLI) ────────────────────────────────────────


def print_help():
    """Print beautifully formatted help text."""
    console.print()
    title = Panel(
        Align.center(Text("Market Data Pipeline -- Help", style="bold cyan")),
        box=DOUBLE_EDGE,
        border_style="cyan",
    )
    console.print(title)
    console.print()

    main_table = Table(box=SIMPLE, padding=(0, 2))
    main_table.add_column("Command", style="bold yellow", width=32)
    main_table.add_column("Description", style="white")
    items = [
        ("python scripts/run.py", "Show the interactive menu"),
        ("python scripts/run.py <command>", "Run a specific stage directly"),
        ("python scripts/run.py all", "Run all stages sequentially"),
        ("python scripts/run.py all-dash", "Run all stages with dashboard"),
        ("python scripts/run.py stats", "Show database statistics"),
        ("python scripts/run.py watch", "Live stats monitor"),
        ("python scripts/run.py test <ticker>", "Test scrape a single ticker"),
        ("python scripts/run.py cleanup", "Clean up unpriceable tickers"),
        ("python scripts/run.py validate", "Validate market caps"),
        ("python scripts/run.py filter", "Interactive ticker filter wizard"),
        ("python scripts/run.py export-menu", "Interactive export sub-menu"),
        ("python scripts/run.py prices --exchange NASDAQ",
         "Scrape prices for a filter (use --exchange / --sector / ... )"),
        ("python scripts/run.py export-menu --ticker-regex '^A' --format csv",
         "Export a filtered slice"),
    ]
    for cmd, desc in items:
        main_table.add_row(cmd, desc)
    console.print(Panel(main_table, title="[bold]Usage[/]", border_style="cyan"))
    console.print()

    stages = [
        ("discover", "Discover all tickers from NASDAQ/NYSE"),
        ("prices", "Scrape historical OHLCV price data"),
        ("fundamentals", "Scrape fundamentals & financial statements"),
        ("supplemental [N]", "Supplemental web scraping (optionally limit to N tickers)"),
        ("indexes", "Fetch index membership data"),
        ("export", "Export all data to Parquet + CSV"),
        ("options [N]", "Scrape options chain (exchange-listed)"),
        ("earnings [N]", "Scrape earnings calendar"),
        ("insiders [N]", "Scrape SEC Form 4 insider trades"),
    ]
    stage_table = Table(box=SIMPLE, padding=(0, 2))
    stage_table.add_column("Stage", style="bold yellow", width=32)
    stage_table.add_column("Description", style="white")
    for cmd, desc in stages:
        stage_table.add_row(cmd, desc)
    console.print(Panel(stage_table, title="[bold]Pipeline Stages[/]", border_style="yellow"))
    console.print()

    opt_table = Table(box=SIMPLE, padding=(0, 2))
    opt_table.add_column("Flag", style="bold green", width=42)
    opt_table.add_column("Description", style="white")
    flags = [
        ("--retry-errored", "Re-scrape tickers that previously errored"),
        ("--execute", "Actually apply changes (for cleanup)"),
        ("--exchange NASDAQ,NYSE", "Comma-separated exchanges"),
        ("--sector Tech,Healthcare", "Comma-separated sectors"),
        ("--industry \"Banks,Software\"", "Comma-separated industries"),
        ("--country \"United States\"", "Comma-separated countries"),
        ("--is-etf yes|no", "Restrict to ETFs / common stocks"),
        ("--min-cap 1B, --max-cap 100B", "Market cap range (K/M/B/T)"),
        ("--ticker-regex '^A'", "Regex against the ticker symbol"),
        ("--company-regex Apple", "Substring/regex against company name"),
        ("--limit 500", "Cap the number of tickers"),
    ]
    for flag, desc in flags:
        opt_table.add_row(flag, desc)
    console.print(Panel(opt_table, title="[bold]Filter Flags[/]", border_style="green"))
    console.print()


# Alias used in some places (`scripts/run.py` calls `show_help`).
show_help = print_help


# ── Re-exports from sibling submodules ─────────────────────


# `dashboard`
from src.operator_console.dashboard import (
    LivePipelineDashboard,
    StageState,
    StageStatus,
)

# `timing`
from src.operator_console.timing import (
    StageTimingSummary,
    print_timing,
    render_timing,
)

# `filter`
from src.operator_console.filter import (
    FilterSpec,
    apply_filter,
    count_filter,
    parse_filter_args,
    prompt_for_filters,
)

# `export`
from src.operator_console.export import (
    EXPORT_GROUPS,
    ExportRequest,
    execute_filtered_export,
    show_export_menu,
)


__all__ = [
    # singletons
    "console",
    # progress / printer
    "LiveProgress",
    "print_header", "print_stage_header",
    "print_ok", "print_warn", "print_error",
    # menu / help / watcher
    "show_menu", "show_help", "print_help",
    "watch_stats", "_build_stats_table",
    "MENU_OPTIONS",
    # dashboard
    "LivePipelineDashboard", "StageState", "StageStatus",
    # timing
    "StageTimingSummary", "render_timing", "print_timing",
    # filter
    "FilterSpec", "apply_filter", "count_filter",
    "parse_filter_args", "prompt_for_filters",
    # export
    "EXPORT_GROUPS", "ExportRequest",
    "show_export_menu", "execute_filtered_export",
]


# Quick demo if invoked directly: `python -m src.operator_console`.
if __name__ == "__main__":
    cmd = show_menu()
    if cmd:
        console.print(f"[bold green]Selected:[/] {cmd}")
