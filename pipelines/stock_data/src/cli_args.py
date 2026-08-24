"""Centralized argparse for the pipeline CLI.

Holds the canonical `build_parser()` so callers (scripts/run.py,
src/pipeline.py) see consistent flags. Also exports
`build_filtered_argv(spec)` / `parse_filter_args(namespace)` utilities
to round-trip `FilterSpec` ↔ CLI argv, which is how the interactive
filter wizard feeds into pipeline commands without coupling.
"""

from __future__ import annotations

import argparse
from typing import List, Optional, Sequence

from src.ui.filter import FilterSpec, parse_filter_args


# ── Parser construction ─────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser used by `pipeline.main`."""
    parser = argparse.ArgumentParser(
        prog="python -m src.pipeline",
        description=(
            "Market Data Pipeline orchestrator. Run a stage with: "
            "`python -m src.pipeline <command> [flags]`."
        ),
    )

    # Both positionals are declared `nargs='?'` so the legacy
    # `python scripts/run.py prices 10` form keeps working without
    # argparse rejecting the trailing integer.
    parser.add_argument("command", nargs="?", help="Pipeline stage to run")
    parser.add_argument("max_tickers", nargs="?", type=int, default=None,
                        help="Optional integer limit for stages that accept one.")

    # ── Behavior flags ──
    parser.add_argument(
        "--retry-errored", action="store_true",
        help="Re-scrape tickers that previously errored.",
    )
    parser.add_argument(
        "--execute", action="store_true",
        help="Actually apply cleanup / validation changes (otherwise dry-run).",
    )
    parser.add_argument(
        "--through",
        type=str,
        default=None,
        help="Inclusive refresh date in strict YYYY-MM-DD format.",
    )

    # ── Ticker filter flags ──
    filter_grp = parser.add_argument_group("Ticker filter (scrape & export)")
    filter_grp.add_argument(
        "--exchange", type=str, default=None,
        help="Comma-separated exchanges (e.g., NASDAQ,NYSE).",
    )
    filter_grp.add_argument(
        "--sector", type=str, default=None,
        help="Comma-separated sectors (e.g., Technology,Healthcare).",
    )
    filter_grp.add_argument(
        "--industry", type=str, default=None,
        help="Comma-separated industries (e.g., Banks,Software).",
    )
    filter_grp.add_argument(
        "--country", type=str, default=None,
        help="Comma-separated countries (e.g., 'United States').",
    )
    filter_grp.add_argument(
        "--is-etf", dest="is_etf", type=str, default=None,
        help="yes | no | (blank for both).",
    )
    filter_grp.add_argument(
        "--min-cap", dest="min_cap", type=str, default=None,
        help="Minimum market cap (e.g., 1B, 500M, 100K).",
    )
    filter_grp.add_argument(
        "--max-cap", dest="max_cap", type=str, default=None,
        help="Maximum market cap (e.g., 100B).",
    )
    filter_grp.add_argument(
        "--ticker-regex", dest="ticker_regex", type=str, default=None,
        help="Regex applied to the ticker symbol (e.g., '^A').",
    )
    filter_grp.add_argument(
        "--company-regex", dest="company_regex", type=str, default=None,
        help="Substring/regex applied to company name.",
    )
    filter_grp.add_argument(
        "--limit", type=int, default=None,
        help="Cap the number of tickers selected by the filter.",
    )

    return parser


def parse_pipeline_argv(argv: Sequence[str]) -> argparse.Namespace:
    """Parse `argv` (excluding program name) into a namespace."""
    return build_parser().parse_args(list(argv))


# ── FilterSpec <-> argv round-trip ───────────────────────────


def build_filtered_argv(spec: FilterSpec) -> List[str]:
    """Convert a `FilterSpec` back into CLI argv tokens.

    Used by the interactive filter wizard so a user-constructed spec
    can drive `pipeline.main` without re-entering flags manually.
    """
    out: List[str] = []
    if spec.exchanges:
        out += ["--exchange", ",".join(spec.exchanges)]
    if spec.sectors:
        out += ["--sector", ",".join(spec.sectors)]
    if spec.industries:
        out += ["--industry", ",".join(spec.industries)]
    if spec.countries:
        out += ["--country", ",".join(spec.countries)]
    if spec.is_etf is not None:
        out += ["--is-etf", "yes" if spec.is_etf else "no"]
    if spec.min_market_cap is not None:
        out += ["--min-cap", _money_arg(spec.min_market_cap)]
    if spec.max_market_cap is not None:
        out += ["--max-cap", _money_arg(spec.max_market_cap)]
    if spec.ticker_regex:
        out += ["--ticker-regex", spec.ticker_regex]
    if spec.company_name_regex:
        out += ["--company-regex", spec.company_name_regex]
    if spec.limit is not None:
        out += ["--limit", str(spec.limit)]
    return out


def _register_sqlite_functions(engine):
    """Register custom SQLite helpers used by SQL generated elsewhere.

    `regexp(expr, item)` enables `WHERE col REGEXP :param` queries —
    stock SQLite has no REGEXP operator, so without this the
    `FilterSpec.to_sql()` output would raise `OperationalError: no
    such function: REGEXP` at execution time. Delegates to Python's
    `re.search`. Invalid regex silently evaluates to False so a
    mistyped CLI flag never crashes a long-running scrape.
    """
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _connection_record):
        def regexp(expr, item):
            if expr is None or item is None:
                return False
            try:
                return bool(re.search(expr, item))
            except re.error:
                return False
        dbapi_connection.create_function("regexp", 2, regexp, deterministic=True)


def _money_arg(value: float) -> str:
    """Format a dollar numeric into the smallest readable K/M/B unit."""
    for suffix, mult in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if abs(value) >= mult and value % mult == 0:
            return f"{int(value / mult)}{suffix}"
    return f"{value:g}"


# Re-export the helper used by pipeline.main.
__all__ = [
    "build_parser",
    "parse_pipeline_argv",
    "build_filtered_argv",
    "parse_filter_args",
]
