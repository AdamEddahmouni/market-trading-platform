"""
Market Data Pipeline - Main Orchestrator.
Coordinates the entire data collection, storage, and export pipeline.

Usage:
    python -m src.pipeline discover       # Stage 1: Discover all tickers
    python -m src.pipeline prices         # Stage 2: Scrape all price data
    python -m src.pipeline fundamentals   # Stage 3: Scrape all fundamentals
    python -m src.pipeline supplemental   # Stage 4: Supplemental web scraping
    python -m src.pipeline indexes        # Stage 5: Index membership
    python -m src.pipeline export         # Stage 6: Export to Parquet+CSV
    python -m src.pipeline options        # Stage 7: Options chain data
    python -m src.pipeline earnings       # Stage 8: Earnings calendar
    python -m src.pipeline insiders       # Stage 9: Insider trading (SEC Form 4)
    python -m src.pipeline all            # Run all stages sequentially
    python -m src.pipeline all-dash       # Run all stages with progress dashboard
    python -m src.pipeline filter         # Interactive ticker filter wizard
    python -m src.pipeline export-menu    # Interactive export sub-menu
    python -m src.pipeline stats          # Show database statistics
    python -m src.pipeline cleanup        # Clean up unpriceable tickers
    python -m src.pipeline validate       # Validate market caps
    python -m src.pipeline test <ticker>  # Test scrape a single ticker
    python -m src.pipeline watch          # Live stats monitor
"""

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import CONCURRENT_WORKERS
from src.database import (
    init_database, get_ticker_count, get_data_stats,
    ensure_progress_table,
)
from src.cli_args import parse_pipeline_argv, parse_filter_args


# Forward / direct-dispatch table for commands handled outside the plain
# argparse `command` mapping (interactive wizards, dashboards that
# bypass the simple per-stage dispatcher below).
_DIRECT_DISPATCH = {
    "filter": "_run_interactive_filter",
    "export-menu": "_run_interactive_export",
    "all-dash": "_run_all_with_dashboard",
}


def print_header(title: str):
    """Print a section header (rich if available, plain fallback otherwise)."""
    try:
        from src.ui import print_header as rich_header
        rich_header(title)
    except Exception:
        print()
        print("=" * 70)
        print(f"  {title}")
        print("=" * 70)
        print()


def print_filter_summary(filter_spec):
    """Echo the active ticker filter to the user."""
    from src.ui.filter import count_filter
    if filter_spec is None or not filter_spec:
        return
    n = count_filter(filter_spec)
    print(f"  [FILTER] Applying ticker filter ({filter_spec.describe()}) — {n:,} tickers match.")


def stage_discover():
    """Stage 1: Discover all tickers from multiple sources."""
    print_header("STAGE 1: TICKER DISCOVERY")
    from src.scrapers.tickers import run_ticker_discovery
    start = time.time()
    count = run_ticker_discovery()
    elapsed = time.time() - start
    print(f"\n[[OK]] Discovered {count} tickers in {elapsed:.1f}s")
    return count


def stage_prices(retry_errored: bool = False, ticker_filter=None):
    """Stage 2: Scrape all historical price data."""
    print_header("STAGE 2: HISTORICAL PRICES")
    from src.scrapers.prices import run_price_scraper

    print_filter_summary(ticker_filter)
    count = get_ticker_count()
    est_batches = max(1, count // 50)
    print(f"Estimated time: ~{est_batches * 2 / 60:.1f} min "
          f"({est_batches} batches of 50 @ ~2s/batch)")
    print(f"Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    start = time.time()
    run_price_scraper(retry_errored=retry_errored, ticker_filter=ticker_filter)
    elapsed = time.time() - start

    stats = get_data_stats()
    print(f"\n[[OK]] Price scraping complete in {elapsed/60:.1f} minutes")
    print(f"    Daily prices: {stats.get('daily_prices', 0):,} records")
    print(f"    Date range: {stats.get('price_date_range', {}).get('min', 'N/A')} -> "
          f"{stats.get('price_date_range', {}).get('max', 'N/A')}")


def stage_fundamentals(retry_errored: bool = False, ticker_filter=None):
    """Stage 3: Scrape all fundamentals and financial statements."""
    print_header("STAGE 3: FUNDAMENTALS & FINANCIAL STATEMENTS")

    print_filter_summary(ticker_filter)
    count = get_ticker_count()
    est = count * 2.0 / CONCURRENT_WORKERS
    print(f"Estimated time: ~{est/60:.1f} min "
          f"({count} tickers @ ~2s each across {CONCURRENT_WORKERS} workers)")
    print(f"Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    from src.scrapers.fundamentals import run_fundamentals_scraper
    start = time.time()
    run_fundamentals_scraper(retry_errored=retry_errored, ticker_filter=ticker_filter)
    elapsed = time.time() - start

    stats = get_data_stats()
    print(f"\n[[OK]] Fundamentals scraping complete in {elapsed/60:.1f} minutes")
    for table in ["income_statements_annual", "income_statements_quarterly",
                   "balance_sheets_annual", "balance_sheets_quarterly",
                   "cash_flow_annual", "cash_flow_quarterly",
                   "fundamentals"]:
        print(f"    {table}: {stats.get(table, 0):,} records")


def stage_supplemental(max_tickers: Optional[int] = None,
                       retry_errored: bool = False, ticker_filter=None):
    """Stage 4: Supplemental web scraping."""
    print_header("STAGE 4: SUPPLEMENTAL WEB SCRAPING")

    print_filter_summary(ticker_filter)
    count = get_ticker_count()
    est = count * 6.0
    print(f"Estimated time: {est/60:.1f} min ({count} tickers @ 6s each)")
    if max_tickers:
        print(f"Limited to {max_tickers} tickers for testing")
    print("Sources: Yahoo Finance, NASDAQ.com, SEC EDGAR, MarketBeat")
    print(f"Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    from src.scrapers.supplemental import run_supplemental_scraper
    start = time.time()
    run_supplemental_scraper(
        max_tickers=max_tickers,
        retry_errored=retry_errored,
        ticker_filter=ticker_filter,
    )
    elapsed = time.time() - start

    stats = get_data_stats()
    print(f"\n[[OK]] Supplemental scraping complete in {elapsed/60:.1f} minutes")
    print(f"    Supplemental records: {stats.get('supplemental_data', 0):,}")


def stage_indexes():
    """Stage 5: Fetch index memberships."""
    print_header("STAGE 5: INDEX MEMBERSHIP")
    from src.scrapers.indexes import run_index_fetcher
    start = time.time()
    run_index_fetcher()
    elapsed = time.time() - start
    print(f"\n[[OK]] Index fetching complete in {elapsed:.1f}s")


def stage_options(max_tickers: Optional[int] = None,
                  retry_errored: bool = False, ticker_filter=None):
    """Stage 7: Scrape options chain data."""
    print_header("STAGE 7: OPTIONS CHAIN")
    from src.scrapers.options import run_options_scraper

    print_filter_summary(ticker_filter)
    count = get_ticker_count()
    print(f"Estimated: ~{min(count, 4000) * 8 / 60:.1f} min "
          f"for exchange-listed tickers @ ~8s each")
    if max_tickers:
        print(f"Limited to {max_tickers} tickers for testing")
    print(f"Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    start = time.time()
    run_options_scraper(
        retry_errored=retry_errored,
        max_tickers=max_tickers,
        ticker_filter=ticker_filter,
    )
    elapsed = time.time() - start

    stats = get_data_stats()
    print(f"\n[[OK]] Options scraping complete in {elapsed/60:.1f} minutes")
    print(f"    Options chain records: {stats.get('options_chain', 0):,}")


def stage_earnings(max_tickers: Optional[int] = None,
                   retry_errored: bool = False, ticker_filter=None):
    """Stage 8: Scrape earnings calendar data."""
    print_header("STAGE 8: EARNINGS CALENDAR")
    from src.scrapers.earnings import run_earnings_scraper

    print_filter_summary(ticker_filter)
    count = get_ticker_count()
    print(f"Estimated: ~{count * 2 / CONCURRENT_WORKERS:.0f}s ({count} tickers @ ~2s each)")
    if max_tickers:
        print(f"Limited to {max_tickers} tickers for testing")
    print(f"Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    start = time.time()
    run_earnings_scraper(
        retry_errored=retry_errored,
        max_tickers=max_tickers,
        ticker_filter=ticker_filter,
    )
    elapsed = time.time() - start

    stats = get_data_stats()
    print(f"\n[[OK]] Earnings scraping complete in {elapsed/60:.1f} minutes")
    print(f"    Earnings records: {stats.get('earnings_calendar', 0):,}")


def stage_insiders(max_tickers: Optional[int] = None,
                   retry_errored: bool = False, ticker_filter=None):
    """Stage 9: Scrape insider trading data (SEC Form 4)."""
    print_header("STAGE 9: INSIDER TRADING (SEC FORM 4)")
    from src.scrapers.insiders import run_insider_scraper

    print_filter_summary(ticker_filter)
    count = get_ticker_count()
    print(f"Estimated: ~{count * 3 / CONCURRENT_WORKERS:.1f}s for SEC EDGAR @ ~3s/ticker")
    print("Rate limited to 10s between SEC requests")
    if max_tickers:
        print(f"Limited to {max_tickers} tickers for testing")
    print(f"Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    start = time.time()
    run_insider_scraper(
        retry_errored=retry_errored,
        max_tickers=max_tickers,
        ticker_filter=ticker_filter,
    )
    elapsed = time.time() - start

    stats = get_data_stats()
    print(f"\n[[OK]] Insider trading scrape complete in {elapsed/60:.1f} minutes")
    print(f"    Insider trade records: {stats.get('insider_trades', 0):,}")


def stage_export():
    """Stage 6: Export data to Parquet + CSV."""
    from src.ui import print_stage_header
    print_stage_header(6, "DATA EXPORT")

    start = time.time()

    print("Exporting prices to Parquet...")
    from src.exporters.parquet_export import (
        export_prices_to_parquet, export_financials_to_parquet,
        export_fundamentals_to_parquet,
    )
    export_prices_to_parquet()

    print("\nExporting financials to Parquet...")
    export_financials_to_parquet()

    print("\nExporting fundamentals to Parquet...")
    export_fundamentals_to_parquet()

    print("\nExporting new data types to Parquet...")
    from src.exporters.parquet_export import export_new_data_to_parquet
    export_new_data_to_parquet()

    print("\nExporting everything to CSV...")
    from src.exporters.csv_export import export_all_to_csv
    export_all_to_csv()

    elapsed = time.time() - start
    print(f"\n[[OK]] Export complete in {elapsed:.1f}s")


def show_stats():
    """Display database statistics."""
    try:
        from src.ui import _build_stats_table
        stats = get_data_stats()
        table = _build_stats_table(stats)
        from src.ui import console
        console.print(table)
        return
    except Exception:
        pass

    from src.ui import print_header as rich_header
    rich_header("DATABASE STATISTICS")
    stats = get_data_stats()

    print(f"{'Category':<35} {'Count':>12}")
    print("-" * 50)
    for table, count in stats.items():
        if not table.startswith("price"):
            label = table.replace("_", " ").title()
            print(f"{label:<35} {str(count):>12}")

    if "price_date_range" in stats:
        dr = stats["price_date_range"]
        print(f"\n{'Price Date Range:':<35} {dr.get('min', 'N/A')} -> {dr.get('max', 'N/A')}")

    ticker_count = get_ticker_count()
    print(f"\n{'Total Active Tickers':<35} {ticker_count:>12}")

    from src.config import DATABASE_PATH
    if DATABASE_PATH.exists():
        size_mb = DATABASE_PATH.stat().st_size / (1024 * 1024)
        print(f"{'Database Size':<35} {size_mb:.1f} MB")

    from src.config import PARQUET_DIR
    if PARQUET_DIR.exists():
        total_size = sum(
            f.stat().st_size for f in PARQUET_DIR.rglob("*") if f.is_file()
        )
        print(f"{'Parquet Exports Size':<35} {total_size / (1024*1024):.1f} MB")

    print()


def stage_cleanup():
    """Run ticker cleanup analysis (dry-run unless --execute was passed)."""
    print_header("TICKER CLEANUP")
    from src.utils.validators import analyze_and_cleanup_tickers
    dry_run = "--execute" not in sys.argv
    analyze_and_cleanup_tickers(dry_run=dry_run)


def stage_validate():
    """Run market cap validation."""
    print_header("MARKET CAP VALIDATION")
    from src.utils.validators import validate_market_caps
    validate_market_caps()


def test_single_ticker(ticker: str):
    """Test all scraping stages on a single ticker."""
    print_header(f"TESTING: {ticker.upper()}")

    from src.database import upsert_ticker

    ticker_id = upsert_ticker(ticker=ticker.upper(), source="manual_test")
    print(f"Ticker ID: {ticker_id}")

    print("\n--- Testing Price Scraper ---")
    from src.scrapers.prices import fetch_ticker_history, store_combined_data
    ticker_data = fetch_ticker_history(ticker)
    if ticker_data is not None:
        store_combined_data(ticker_id, ticker, ticker_data)
        print("[OK] Price data stored")
    else:
        print("[FAIL] Price data failed")

    print("\n--- Testing Fundamentals Scraper ---")
    from src.scrapers.fundamentals import process_ticker_fundamentals
    if process_ticker_fundamentals(ticker, ticker_id):
        print("[OK] Fundamentals stored")
    else:
        print("[FAIL] Fundamentals failed")

    print(f"\n--- Results for {ticker.upper()} ---")
    show_stats()


def run_all(retry_errored: bool = False):
    """Run the complete pipeline (plain text output)."""
    print_header("COMPLETE DATA PIPELINE")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    overall_start = time.time()

    print("Initializing database...")
    init_database()
    ensure_progress_table()

    stage_discover()
    stage_prices(retry_errored=retry_errored)
    stage_fundamentals(retry_errored=retry_errored)
    stage_supplemental(max_tickers=100, retry_errored=retry_errored)
    stage_indexes()
    stage_export()
    stage_options(max_tickers=100, retry_errored=retry_errored)
    stage_earnings(max_tickers=100, retry_errored=retry_errored)
    stage_insiders(max_tickers=50, retry_errored=retry_errored)

    overall_elapsed = time.time() - overall_start
    print_header("PIPELINE COMPLETE")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total time: {overall_elapsed/60:.1f} minutes ({overall_elapsed/3600:.2f} hours)")
    show_stats()


# ── Dashboard + interactive command handlers ─────────────────


def _run_all_with_dashboard(retry_errored: bool = False):
    """Like run_all() but with a multi-stage dashboard rendered between stages."""
    from src.ui.dashboard import LivePipelineDashboard

    print_header("COMPLETE DATA PIPELINE (Dashboard)")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    init_database()
    ensure_progress_table()

    dash = LivePipelineDashboard(
        stages=[
            "Discover", "Prices", "Fundamentals", "Supplemental",
            "Indexes", "Export", "Options", "Earnings", "Insiders",
        ],
        title="Pipeline Progress",
    )
    dash.print()

    for stage_name, fn, stat_key in [
        ("Discover",   stage_discover,                                                None),
        ("Prices",     lambda: stage_prices(retry_errored=retry_errored),             "daily_prices"),
        ("Fundamentals", lambda: stage_fundamentals(retry_errored=retry_errored),     "fundamentals"),
        ("Supplemental", lambda: stage_supplemental(max_tickers=100,
                                                   retry_errored=retry_errored),     "supplemental_data"),
        ("Indexes",    stage_indexes,                                                 "index_membership"),
        ("Export",     stage_export,                                                  None),
        ("Options",    lambda: stage_options(max_tickers=100,
                                              retry_errored=retry_errored),          "options_chain"),
        ("Earnings",   lambda: stage_earnings(max_tickers=100,
                                              retry_errored=retry_errored),          "earnings_calendar"),
        ("Insiders",   lambda: stage_insiders(max_tickers=50,
                                              retry_errored=retry_errored),          "insider_trades"),
    ]:
        dash.start(stage_name)
        try:
            fn()
            stat_val = get_data_stats().get(stat_key, 0) if stat_key else 0
            dash.complete(stage_name, records=stat_val)
        except Exception as exc:
            dash.fail(stage_name, errors=1)
            print(f"  [ERROR] Stage '{stage_name}' crashed: {exc}")
        dash.print()

    dash.print_summary()
    show_stats()


def _run_interactive_filter():
    """Interactive filter wizard then offer scrape / export follow-ups."""
    from src.ui import console
    from src.ui.filter import (
        apply_filter,
        count_filter,
        prompt_for_filters,
    )
    spec = prompt_for_filters()
    if spec is None:
        console.print("[dim]Filter cancelled.[/]")
        return

    n = count_filter(spec)
    matches = apply_filter(spec)
    console.print(f"\n[[OK]] {n:,} tickers match the filter (showing first 20):")
    sample = ", ".join(t["ticker"] for t in matches[:20])
    console.print(f"  {sample}{'...' if len(matches) > 20 else ''}")

    if n == 0:
        return

    from rich.prompt import Confirm
    if Confirm.ask("Run a scrape stage using this filter?", default=False):
        from src.cli_args import build_filtered_argv
        from rich.prompt import Prompt
        cmd = Prompt.ask("Scrape command", default="prices",
                         choices=["discover", "prices", "fundamentals", "supplemental",
                                  "indexes", "options", "earnings", "insiders", "test"])
        argv = [sys.argv[0], cmd] + build_filtered_argv(spec)
        sys.argv = argv
        main()
        return

    if Confirm.ask("Export a slice using this filter?", default=True):
        from src.ui.export import ExportRequest, execute_filtered_export
        from rich.prompt import Prompt
        fmt = Prompt.ask("Format", choices=["csv", "parquet", "both"], default="both")
        request = ExportRequest(
            tables=tuple([
                "daily_prices", "weekly_prices", "monthly_prices",
                "fundamentals",
                "income_statements_annual", "income_statements_quarterly",
                "balance_sheets_annual", "balance_sheets_quarterly",
                "cash_flow_annual", "cash_flow_quarterly",
                "dividends", "splits", "earnings_calendar",
                "options_chain", "insider_trades", "supplemental_data",
                "index_membership",
            ]),
            format=fmt,
            ticker_filter=spec,
        )
        execute_filtered_export(request)


def _run_interactive_export():
    """Run the interactive export sub-menu."""
    from src.ui.export import execute_filtered_export, show_export_menu
    request = show_export_menu()
    if request is None:
        return
    execute_filtered_export(request)


# ── argparse main() ──────────────────────────────────────────


def main():
    """Main entry point — argparse-driven."""
    if len(sys.argv) < 2:
        print(__doc__)
        return

    raw_args = sys.argv[1:]
    args = parse_pipeline_argv(raw_args)
    filter_spec = parse_filter_args(args)
    retry_errored = getattr(args, "retry_errored", False)
    command = (raw_args[0] or "").lower() if raw_args else ""

    # Make sure the DB exists before any stage runs.
    init_database()
    ensure_progress_table()

    # Direct-dispatch (interactive / dashboard).
    if command in _DIRECT_DISPATCH:
        _DIRECT_DISPATCH[command]()
        return

    if command == "discover":
        stage_discover()
    elif command == "prices":
        stage_prices(retry_errored=retry_errored, ticker_filter=filter_spec)
    elif command == "fundamentals":
        stage_fundamentals(retry_errored=retry_errored, ticker_filter=filter_spec)
    elif command == "supplemental":
        max_t = int(raw_args[1]) if len(raw_args) > 1 and raw_args[1].isdigit() else None
        stage_supplemental(max_tickers=max_t, retry_errored=retry_errored,
                           ticker_filter=filter_spec)
    elif command == "indexes":
        stage_indexes()
    elif command == "options":
        max_t = int(raw_args[1]) if len(raw_args) > 1 and raw_args[1].isdigit() else None
        stage_options(max_tickers=max_t, retry_errored=retry_errored,
                      ticker_filter=filter_spec)
    elif command == "earnings":
        max_t = int(raw_args[1]) if len(raw_args) > 1 and raw_args[1].isdigit() else None
        stage_earnings(max_tickers=max_t, retry_errored=retry_errored,
                       ticker_filter=filter_spec)
    elif command == "insiders":
        max_t = int(raw_args[1]) if len(raw_args) > 1 and raw_args[1].isdigit() else None
        stage_insiders(max_tickers=max_t, retry_errored=retry_errored,
                       ticker_filter=filter_spec)
    elif command == "export":
        stage_export()
    elif command == "stats":
        show_stats()
    elif command == "watch":
        run_watch()
    elif command == "cleanup":
        stage_cleanup()
    elif command == "validate":
        stage_validate()
    elif command == "test" and len(raw_args) > 1:
        test_single_ticker(raw_args[1])
    elif command == "all":
        _run_all_with_dashboard(retry_errored=retry_errored)
    else:
        print(f"Unknown command: {command}")
        print(__doc__)


def run_watch():
    """Live stats monitor. Refreshes every 3s."""
    from src.ui import watch_stats
    from src.database import get_data_stats
    print("\n  [WATCH] Live stats monitor. Press Ctrl+C to stop.\n")
    watch_stats(get_stats_fn=get_data_stats, refresh_seconds=3.0)


if __name__ == "__main__":
    main()
