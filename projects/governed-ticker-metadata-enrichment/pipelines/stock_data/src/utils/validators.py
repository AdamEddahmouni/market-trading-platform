"""
Data Validation and Cleanup Utilities.
Provides:
  - Ticker cleanup (marking unpriceable tickers as inactive)
  - Market cap validation via yfinance
  - Ticker pattern analysis
"""

import re
import sys
import time
from typing import List, Dict, Optional, Tuple
from pathlib import Path

from src.database import get_connection, init_database
from sqlalchemy.sql import text


# ── Ticker Cleanup Patterns ────────────────────────────────────
# These patterns identify tickers that Yahoo Finance cannot provide data for.

DEAD_PATTERNS = [
    (r'\$', 'preferred_share (dollar sign)'),
    (r'\.(W|U|R|WS|WT)$', 'warrant_unit_right (dot suffix)'),
    (r'\.[A-Z]$', 'class_share (dot letter)'),
]


def is_unpriceable(ticker: str) -> tuple:
    """Check if a ticker matches any dead pattern. Returns (is_dead, reason)."""
    t = ticker.strip().upper()
    for pattern, reason in DEAD_PATTERNS:
        if re.search(pattern, t):
            return True, reason
    return False, None


def analyze_and_cleanup_tickers(dry_run: bool = True) -> List[Tuple]:
    """
    Analyze all tickers and mark unpriceable ones as inactive.
    Returns list of (ticker_id, ticker, exchange, reason, status) for dead tickers.
    """
    with get_connection() as conn:
        tickers = conn.execute(
            text("SELECT id, ticker, exchange FROM tickers WHERE is_active = 1 ORDER BY ticker")
        ).fetchall()

        progress = conn.execute(
            text("SELECT ticker, status FROM scraping_progress WHERE stage = 'prices'")
        ).fetchall()
        progress_map = {r[0]: r[1] for r in progress}

    print(f"{'='*70}")
    print(f"  TICKER CLEANUP -- {'DRY RUN' if dry_run else 'LIVE RUN'}")
    print(f"{'='*70}")

    dead_tickers = []
    for ticker_id, ticker, exchange in tickers:
        is_dead, reason = is_unpriceable(ticker)
        if is_dead:
            status = progress_map.get(ticker, 'untried')
            dead_tickers.append((ticker_id, ticker, exchange, reason, status))

    by_reason = {}
    for tid, t, ex, reason, status in dead_tickers:
        by_reason.setdefault(reason, []).append((t, ex, status))

    print(f"\nTotal active tickers: {len(tickers)}")
    print(f"Unpriceable tickers found: {len(dead_tickers)}")
    print(f"Priceable tickers remaining: {len(tickers) - len(dead_tickers)}")
    print()

    print(f"{'PATTERN':<40} {'COUNT':>8} {'ALREADY_ERRORED':>18}")
    print("-" * 70)
    unpriceable_set = {t[1] for t in dead_tickers}
    for reason, items in sorted(by_reason.items(), key=lambda x: -len(x[1])):
        already_errored = sum(1 for _, _, s in items if s == 'error')
        print(f"  {reason:<38} {len(items):>8} {already_errored:>18}")

    # Samples
    print("\n=== SAMPLES ===")
    for reason, items in sorted(by_reason.items(), key=lambda x: -len(x[1])):
        print(f"\n  {reason} ({len(items)} total):")
        for t, ex, status in items[:5]:
            print(f"    {t:<15} ({ex:<15}) [{status}]")
        if len(items) > 5:
            print(f"    ... and {len(items)-5} more")

    # Clean tickers that also failed
    print(f"\n\n{'='*70}")
    print("  CLEAN TICKERS THAT ALSO FAILED")
    clean_failures = []
    for ticker_id, ticker, exchange in tickers:
        if ticker not in unpriceable_set:
            status = progress_map.get(ticker, 'untried')
            if status == 'error':
                clean_failures.append((ticker, exchange))
    print(f"  Clean tickers that errored: {len(clean_failures)}")
    if clean_failures:
        print("  (Delisted companies or genuine Yahoo Finance limitations)")
        print(f"  Samples: {clean_failures[:10]}")

    # Perform cleanup
    if not dry_run and dead_tickers:
        with get_connection() as conn:
            dead_ids = [str(t[0]) for t in dead_tickers]
            dead_tickers_list = [t[1] for t in dead_tickers]

            for tid in dead_ids:
                conn.execute(
                    text("UPDATE tickers SET is_active = 0 WHERE id = :id"),
                    {"id": tid}
                )
            print(f"\n  Marked {len(dead_ids)} tickers as inactive")

            for t in dead_tickers_list:
                conn.execute(
                    text("DELETE FROM scraping_progress WHERE ticker = :t AND stage = 'prices'"),
                    {"t": t}
                )
            print(f"  Cleared progress entries for {len(dead_tickers_list)} tickers")

    print(f"\n{'='*70}")
    if dry_run:
        print(f"  DRY RUN COMPLETE -- No changes made")
        print(f"  Run with --execute flag to apply changes")
    else:
        print(f"  CLEANUP COMPLETE")
    print(f"{'='*70}")

    return dead_tickers


# ── Market Cap Validation ──────────────────────────────────────

def validate_market_caps():
    """Run yfinance validation on tickers to populate market_cap column."""
    import yfinance as yf

    with get_connection() as conn:
        tickers = conn.execute(text("""
            SELECT id, ticker, market_cap
            FROM tickers
            WHERE exchange = 'NASDAQ' AND is_active = 1
            ORDER BY ticker
        """)).fetchall()

    tickers_list = [{"id": r[0], "ticker": r[1], "market_cap": r[2]} for r in tickers]
    total = len(tickers_list)
    already_have = sum(1 for t in tickers_list if t["market_cap"] is not None)

    print(f"[VALIDATE] NASDAQ tickers in DB: {total}")
    print(f"[VALIDATE] Already have market_cap: {already_have}")

    to_validate = [t for t in tickers_list if t["market_cap"] is None]
    print(f"[VALIDATE] Need validation: {len(to_validate)}")

    validated = 0
    errors = 0
    start_time = time.time()
    BATCH_SIZE = 50
    REQUEST_DELAY = 0.3

    for i, t in enumerate(to_validate):
        ticker = t["ticker"]
        ticker_id = t["id"]

        try:
            obj = yf.Ticker(ticker)
            info = obj.info

            if info and (info.get("regularMarketPrice") is not None or info.get("marketCap")):
                mc = info.get("marketCap")
                sector = info.get("sector")
                industry = info.get("industry")
                country = info.get("country")

                with get_connection() as conn:
                    conn.execute(text("""
                        UPDATE tickers
                        SET market_cap = :mc, sector = :sector,
                            industry = :industry, country = :country,
                            last_updated = datetime('now')
                        WHERE id = :id
                    """), {"mc": mc, "sector": sector, "industry": industry,
                           "country": country, "id": ticker_id})
                validated += 1
            else:
                errors += 1
        except Exception as e:
            errors += 1
            if errors <= 10:
                print(f"  [ERR] {ticker}: {str(e)[:60]}")

        time.sleep(REQUEST_DELAY)

        if (i + 1) % 500 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"  [{i+1}/{len(to_validate)}] validated={validated} errors={errors} rate={rate:.1f}/s")

    elapsed = time.time() - start_time
    print(f"\n[VALIDATE] Complete! Validated: {validated}, Errors: {errors}")
    print(f"  Time: {elapsed/60:.1f} min")

    with get_connection() as conn:
        with_mc = conn.execute(text(
            "SELECT COUNT(*) FROM tickers WHERE exchange='NASDAQ' AND market_cap IS NOT NULL"
        )).fetchone()[0]
        print(f"  NASDAQ tickers with market_cap: {with_mc}")


# ── Legacy Script Compatibility ────────────────────────────────

def run_cleanup():
    """Entry point for cleanup script."""
    dry_run = "--execute" not in sys.argv
    analyze_and_cleanup_tickers(dry_run=dry_run)


def run_market_cap_validation():
    """Entry point for market cap validation script."""
    validate_market_caps()
