#!/usr/bin/env python3
"""
CLI Entry Point - Thin wrapper that delegates to the pipeline module.
Provides a clean 'python scripts/run.py <command>' interface.

Usage:
    python scripts/run.py discover       # Discover all tickers
    python scripts/run.py prices         # Scrape price data
    python scripts/run.py fundamentals   # Scrape fundamentals
    python scripts/run.py supplemental   # Supplemental web scraping
    python scripts/run.py indexes        # Index membership
    python scripts/run.py export         # Export to Parquet/CSV
    python scripts/run.py options        # Options chain data
    python scripts/run.py earnings       # Earnings calendar
    python scripts/run.py insiders       # Insider trading (SEC Form 4)
    python scripts/run.py all            # Run all stages (plain text)
    python scripts/run.py all-dash       # Run all stages w/ progress dashboard
    python scripts/run.py filter         # Interactive ticker filter wizard
    python scripts/run.py export-menu    # Interactive export sub-menu
    python scripts/run.py stats          # Show database stats
    python scripts/run.py cleanup        # Clean up tickers
    python scripts/run.py validate       # Validate market caps
    python scripts/run.py test <ticker>  # Test single ticker
    python scripts/run.py help           # Show full help

Options:
    --retry-errored    Re-scrape tickers that previously errored
    --execute          Actually apply changes (for cleanup)

Filter flags (apply to scrape stages AND export-menu):
    --exchange NASDAQ,NYSE
    --sector Tech,Healthcare
    --industry "Banks,Software"
    --country "United States"
    --is-etf yes|no
    --min-cap 1B | --max-cap 100B
    --ticker-regex '^A' | --company-regex Apple
    --limit 500

Examples:
    python scripts/run.py discover
    python scripts/run.py prices --retry-errored
    python scripts/run.py options 10
    python scripts/run.py cleanup --execute
    python scripts/run.py test AAPL
    python scripts/run.py all-dash
    python scripts/run.py prices --exchange NASDAQ --sector Tech --limit 50
    python scripts/run.py export-menu --ticker-regex '^A' --format csv
"""

import sys
from pathlib import Path

# Add project root to Python path for imports
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))


# ── Dispatch table ──────────────────────────────────────────
# New menu entries that bypass argparse and go straight to their
# dedicated handlers. Keep these small and explicit.
_DIRECT_DISPATCH = {
    "help": "_show_help",
    "watch": "_run_watch",
    "filter_picker": "_run_filter_picker",
    "export_menu": "_run_export_menu",
    "all_dash": "_run_all_dash",
}


def main():
    args = sys.argv[1:]

    if not args:
        # No args → show interactive menu
        from src.operator_console import show_menu
        cmd = show_menu()
        if cmd is None or cmd == "quit":
            return
        if cmd in _DIRECT_DISPATCH:
            _invoke(_DIRECT_DISPATCH[cmd])
            return
        # Re-invoke pipeline with the selected command.
        sys.argv = [sys.argv[0], cmd]
        from src.pipeline import main as pipeline_main
        pipeline_main()
        return

    if args[0] in ("help", "--help", "-h"):
        _invoke("_show_help")
        return

    from src.pipeline import main as pipeline_main
    pipeline_main()


def _invoke(handler_name: str):
    """Look up the handler by name in this module (kept tiny + dispatch-only)."""
    handler = globals().get(handler_name)
    if handler is None:
        print(f"Internal error: handler {handler_name} not found", file=sys.stderr)
        sys.exit(1)
    handler()


def _show_help():
    from src.operator_console import print_help
    print_help()


def _run_watch():
    from src.pipeline import run_watch
    run_watch()


def _run_filter_picker():
    """Interactive filter wizard followed by count/preview + optional export."""
    from src.operator_console import console
    from src.operator_console.filter import (
        FilterSpec,
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
    console.print(f"\n[[OK]] {n:,} tickers match the filter "
                  f"(showing first 20):")
    sample = ", ".join(t["ticker"] for t in matches[:20])
    console.print(f"  {sample}{'...' if len(matches) > 20 else ''}")
    if n == 0:
        return

    # Offer follow-up: scrape with this filter, or export with this filter.
    from rich.prompt import Confirm
    if Confirm.ask("Use this filter as a limit for a scrape stage?", default=False):
        from src.cli_args import build_filtered_argv
        # Drop into pipeline.run with the spec encoded as CLI args.
        argv_extra = build_filtered_argv(spec)
        sys.argv = [sys.argv[0], "prices"] + argv_extra
        from src.pipeline import main as pipeline_main
        pipeline_main()
        return

    if Confirm.ask("Export a slice using this filter?", default=True):
        from src.operator_console.export import ExportRequest, execute_filtered_export
        from rich.prompt import Prompt
        fmt = Prompt.ask("Format", choices=["csv", "parquet", "both"], default="both")
        request = ExportRequest(
            tables=tuple([
                "daily_prices", "weekly_prices", "monthly_prices",
                "fundamentals", "dividends", "splits",
                "income_statements_annual", "income_statements_quarterly",
                "balance_sheets_annual", "balance_sheets_quarterly",
                "cash_flow_annual", "cash_flow_quarterly",
                "options_chain", "insider_trades", "earnings_calendar",
                "supplemental_data", "index_membership",
            ]),
            format=fmt,
            ticker_filter=spec,
        )
        execute_filtered_export(request)


def _run_export_menu():
    """Run the interactive export sub-menu from the dispatch menu."""
    from src.operator_console.export import (
        execute_filtered_export,
        show_export_menu,
    )
    request = show_export_menu()
    if request is None:
        return
    execute_filtered_export(request)


def _run_all_dash():
    """Run the full pipeline with the multi-stage dashboard."""
    from src.pipeline import run_all_with_dashboard
    run_all_with_dashboard()


if __name__ == "__main__":
    main()
