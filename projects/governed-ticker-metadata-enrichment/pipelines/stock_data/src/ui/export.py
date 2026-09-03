"""Export sub-menu + filtered-slice export execution.

`ExportRequest` is the declarative spec for an export run. Users
construct it via the interactive `show_export_menu` or by calling
`execute_filtered_export` directly (CLI flags plan to do the latter).
The actual export work is delegated to the existing modules under
`src.exporters`.

Grouping rationale (5 user-facing groups hide ~15 underlying tables):

  1. Prices          - daily/weekly/monthly OHLCV
  2. Fundamentals    - fundamentals + 6 financial statement tables
  3. Corporate Acts  - dividends, splits, earnings_calendar
  4. Alternative     - insider_trades, options_chain, supplemental_data
  5. Metadata        - tickers (company info), index_membership
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

from rich.prompt import Confirm, Prompt
from rich.table import Table

from src.config import (
    CSV_EXPORT_DIR,
    DATABASE_PATH,
    PARQUET_DIR,
)
from src.database import get_connection
from src.ui._styles import COLOR_BRAND_PRIMARY, COLOR_RECORD, console
from src.ui.filter import FilterSpec, apply_filter, count_filter


# ── Group taxonomy ────────────────────────────────────────────


EXPORT_GROUPS: dict[str, List[str]] = {
    "Prices (Daily / Weekly / Monthly OHLCV)": [
        "daily_prices", "weekly_prices", "monthly_prices",
    ],
    "Fundamentals & Financial Statements": [
        "fundamentals",
        "income_statements_annual", "income_statements_quarterly",
        "balance_sheets_annual", "balance_sheets_quarterly",
        "cash_flow_annual", "cash_flow_quarterly",
    ],
    "Corporate Actions (Dividends, Splits, Earnings)": [
        "dividends", "splits", "earnings_calendar",
    ],
    "Alternative Data (Insiders, Options, Supplemental)": [
        "insider_trades", "options_chain", "supplemental_data",
    ],
    "Metadata (Tickers, Indexes)": [
        "index_membership",
    ],
}


# Tickers-by-themselves are exported via `tickers` table (no group).
METADATA_TICKERS_TABLE = "tickers"


# ── Public dataclass ──────────────────────────────────────────


@dataclass(frozen=True)
class ExportRequest:
    """An immutable request for one export run."""
    tables: Tuple[str, ...]
    format: str = "both"  # "csv" | "parquet" | "both"
    output_dir: Optional[Path] = None
    ticker_filter: Optional[FilterSpec] = None  # None = all tickers
    include_tickers: bool = True  # also export the `tickers` master table

    def describe(self) -> str:
        parts: List[str] = []
        parts.append(f"format={self.format}")
        parts.append(f"tables={len(self.tables)}")
        if self.include_tickers:
            parts.append("+tickers")
        if self.ticker_filter:
            parts.append(f"filter={self.ticker_filter.describe()}")
        else:
            parts.append("tickers=all")
        if self.output_dir:
            parts.append(f"output={self.output_dir}")
        return ", ".join(parts)


# ── Interactive sub-menu ──────────────────────────────────────


def show_export_menu() -> Optional[ExportRequest]:
    """Multi-step wizard for the export sub-menu.

    Returns `None` if the user cancels. Otherwise returns an
    `ExportRequest` ready for `execute_filtered_export`.
    """
    console.print(f"\n[{COLOR_BRAND_PRIMARY}]Export Configuration[/]")
    tables = _prompt_table_selection()
    if tables is None:
        return None

    format_choice = Prompt.ask(
        "\nOutput format",
        choices=["csv", "parquet", "both"],
        default="both",
    )

    output_dir = _prompt_output_dir(format_choice)
    if output_dir is None:
        return None

    # Optional ticker filter
    use_filter = Confirm.ask(
        "\nRestrict to a subset of tickers?", default=False
    )
    if use_filter:
        from src.ui.filter import prompt_for_filters  # lazy import (cycle-safe)
        spec = prompt_for_filters()
        if spec is None:
            ticker_filter: Optional[FilterSpec] = None
            console.print("[dim]Filter cancelled; exporting all tickers.[/]")
        else:
            ticker_filter = spec
    else:
        ticker_filter = None

    include_tickers = Confirm.ask(
        "Also export the [bold]tickers[/] master table?",
        default=True,
    )

    request = ExportRequest(
        tables=tuple(tables),
        format=format_choice,
        output_dir=output_dir,
        ticker_filter=ticker_filter,
        include_tickers=include_tickers,
    )
    console.print(f"\n[bold]Export request:[/] {request.describe()}")
    if not Confirm.ask("Run this export?", default=True):
        return None
    return request


def _prompt_table_selection() -> Optional[List[str]]:
    """Let the user pick one or more export groups (multi-step wizard)."""
    group_names = list(EXPORT_GROUPS.keys())
    table = Table(title="Available Export Groups", header_style="bold cyan")
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Group", style="bold white")
    table.add_column("Tables", style="dim")
    for idx, name in enumerate(group_names, start=1):
        tables_in_group = EXPORT_GROUPS[name]
        if len(tables_in_group) <= 3:
            preview = ", ".join(tables_in_group)
        else:
            preview = f"{', '.join(tables_in_group[:3])}, ... ({len(tables_in_group)} total)"
        table.add_row(str(idx), name, preview)
    console.print(table)
    console.print("  [dim]0 = select all groups[/]")

    raw = Prompt.ask(
        "\nSelect groups (e.g., [bold]1,3[/] or [bold]1[/] or [bold]0[/])",
        default="0",
    )
    if raw is None or raw.strip() == "":
        return None

    if raw.strip() == "0":
        selected = list(group_names)
    else:
        chosen: List[str] = []
        for token in (t.strip() for t in raw.split(",") if t.strip()):
            try:
                idx = int(token)
            except ValueError:
                console.print(f"  [yellow]Skipping invalid input[/] '{token}'")
                continue
            idx = max(1, min(len(group_names), idx))
            chosen.append(group_names[idx - 1])
        if not chosen:
            return None
        selected = chosen

    # Expand groups to table list, preserving order, dedup.
    seen: set[str] = set()
    tables: List[str] = []
    for group in selected:
        for t in EXPORT_GROUPS[group]:
            if t not in seen:
                seen.add(t)
                tables.append(t)
    return tables


def _prompt_output_dir(format_choice: str) -> Optional[Path]:
    default_dir = CSV_EXPORT_DIR if format_choice == "csv" else PARQUET_DIR
    default_path = str(default_dir)
    raw = Prompt.ask(
        "Output directory",
        default=default_path,
    )
    if raw is None or raw.strip() == "":
        return None
    path = Path(raw).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


# ── Execution ──────────────────────────────────────────────────


def execute_filtered_export(request: ExportRequest) -> int:
    """Run the export. Returns the total number of rows written."""
    total_rows = 0
    filter_spec = request.ticker_filter
    ticker_ids: Optional[List[int]] = None
    if filter_spec is not None:
        if not filter_spec:
            console.print("[dim]Filter is empty; treating as no filter.[/]")
        else:
            count = count_filter(filter_spec)
            tickers = apply_filter(filter_spec)
            ticker_ids = [t["id"] for t in tickers]
            console.print(
                f"  [dim]Filter matches[/] {count:,} [dim]tickers; "
                f"exporting rows for {len(ticker_ids):,} only.[/]"
            )

    if request.include_tickers:
        total_rows += _export_one_table(
            METADATA_TICKERS_TABLE, request, ticker_ids=ticker_ids,
        )

    for table in request.tables:
        total_rows += _export_one_table(table, request, ticker_ids=ticker_ids)

    console.print(f"\n[[OK]] Export complete. Wrote {total_rows:,} rows total.")
    return total_rows


def _export_one_table(table_name: str, request: ExportRequest,
                       ticker_ids: Optional[Sequence[int]]) -> int:
    """Dispatch a single table export to CSV / Parquet / both."""
    df = _table_to_dataframe(table_name, ticker_ids=ticker_ids)
    if df is None:
        console.print(f"  [dim]Skipping[/] {table_name} [dim](empty or error)[/]")
        return 0

    out_dir = request.output_dir or _default_dir_for(table_name, request.format)
    written = 0
    if request.format in ("csv", "both"):
        path = out_dir / f"{table_name}.csv"
        df.to_csv(path, index=False)
        written += len(df)
        console.print(f"  [green]csv[/]     {table_name} -> {path.relative_to(out_dir.parent)}  ({len(df):,} rows)")
    if request.format in ("parquet", "both"):
        path = out_dir / f"{table_name}.parquet"
        try:
            df.to_parquet(path, index=False, compression="snappy")
            written += len(df)
            console.print(f"  [green]parquet[/] {table_name} -> {path.relative_to(out_dir.parent)}  ({len(df):,} rows)")
        except ImportError:
            console.print(f"  [yellow]skipped[/] parquet for {table_name} (pyarrow not installed)")
    return written


def _default_dir_for(table_name: str, fmt: str) -> Path:
    """Fallback output dir relative to PARQUET_DIR / CSV_EXPORT_DIR."""
    if fmt == "csv":
        return CSV_EXPORT_DIR
    return PARQUET_DIR


def _table_to_dataframe(table_name: str,
                        ticker_ids: Optional[Sequence[int]]) -> Optional["pd.DataFrame"]:
    """Read a table (joined with `tickers`) into a pandas DataFrame."""
    import pandas as pd  # local import keeps `show_menu` cheap
    try:
        # Tables with no `ticker_id` column export themselves directly.
        bare = {
            METADATA_TICKERS_TABLE,
            "index_membership",
        }
        params: dict = {}
        clause = ""
        if ticker_ids:
            placeholders = ", ".join(f":tid_{i}" for i in range(len(ticker_ids)))
            clause = f" WHERE t.id IN ({placeholders})" if table_name != METADATA_TICKERS_TABLE \
                else f" WHERE id IN ({placeholders})"
            for i, tid in enumerate(ticker_ids):
                params[f"tid_{i}"] = int(tid)

        if table_name == METADATA_TICKERS_TABLE:
            sql = f"SELECT * FROM {table_name}{clause} ORDER BY ticker"
        elif table_name == "index_membership":
            sql = (f"SELECT im.* FROM index_membership im "
                   f"JOIN tickers t ON t.id = im.ticker_id{clause}")
        else:
            sql = (f"SELECT t.ticker, x.* FROM {table_name} x "
                   f"JOIN tickers t ON t.id = x.ticker_id{clause}")

        with get_connection() as conn:
            df = pd.read_sql_query(sql, conn, params=params)
        if df.empty:
            return None
        return df
    except Exception as exc:  # broad: log + skip vs. crashing the whole export
        console.print(f"  [yellow]read failed[/] {table_name}: {exc}")
        return None
