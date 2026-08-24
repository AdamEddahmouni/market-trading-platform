"""
Ultra-Fast Combined Price + Actions Scraper.
Uses yf.download() for BATCHED fetching — many tickers in ONE API call.
Fallback: individual Ticker.history() for tickers that fail in batch mode.
Uses ThreadPoolExecutor for parallelism across batches.

Resume-from-crash: tracks per-ticker progress in scraping_progress table.
Now uses BaseScraper for signal handling and progress infrastructure.
"""

import time
from collections import Counter
from datetime import date, datetime, timezone
from typing import List, Dict, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import yfinance as yf
import numpy as np

from src.acquisition import AcquisitionOutcome, classify_failure, safe_error_detail
from src.config import (
    CONCURRENT_WORKERS, MAX_RETRIES, MAX_HISTORY_PERIOD, PRICE_FIELDS,
    PRICE_BATCH_SIZE,
)
from src.refresh import FetchRange, plan_fetch_range
from src.database import (
    get_all_ticker_ids, fast_bulk_insert,
    get_connection, save_progress, mark_in_progress,
    ensure_progress_table, latest_attempts_for_stage,
    latest_daily_price_dates, record_attempt,
)
from src.scrapers.base import BaseScraper
from src.ui import LiveProgress
from sqlalchemy.sql import text


# ── Pure Helper Functions (stateless) ──────────────────────────

def download_batch(ticker_batch: List[Dict]) -> Optional[pd.DataFrame]:
    """Fetch historical data for MANY tickers in a single yf.download() call."""
    symbols = [t["ticker"] for t in ticker_batch]
    batch_str = " ".join(symbols)

    for attempt in range(MAX_RETRIES):
        try:
            data = yf.download(
                tickers=batch_str,
                period=MAX_HISTORY_PERIOD,
                auto_adjust=False,
                actions=True,
                threads=False,
                progress=False,
                group_by="ticker",
            )
            if data is not None and not data.empty:
                if data.index.tz is not None:
                    data.index = data.index.tz_localize(None)
                return data
            return None
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.5)
            else:
                print(f"    [WARN] Batch download failed for {len(ticker_batch)} tickers: {e}")
                return None


def fetch_ticker_history(ticker: str) -> Optional[pd.DataFrame]:
    """Fallback: fetch a SINGLE ticker via Ticker.history()."""
    for attempt in range(MAX_RETRIES):
        try:
            t = yf.Ticker(ticker)
            hist = t.history(
                period=MAX_HISTORY_PERIOD,
                auto_adjust=False,
                actions=True,
            )
            if hist is not None and not hist.empty:
                if hist.index.tz is not None:
                    hist.index = hist.index.tz_localize(None)
                return hist
            return None
        except Exception:
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.3)
            else:
                return None


def fetch_ticker_range(ticker: str, fetch_range: FetchRange) -> pd.DataFrame | None:
    """Fetch one ticker for a planned full-history or bounded date range."""
    client = yf.Ticker(ticker)
    kwargs: dict[str, object] = {"auto_adjust": False, "actions": True}
    if fetch_range.full_history:
        kwargs["period"] = MAX_HISTORY_PERIOD
    else:
        if fetch_range.start is None:
            raise ValueError("bounded fetch requires a start date")
        kwargs["start"] = fetch_range.start.isoformat()
        kwargs["end"] = fetch_range.end.isoformat()
    last_error: BaseException | None = None
    for attempt in range(MAX_RETRIES):
        try:
            result = client.history(**kwargs)
            if result is not None and not result.empty and result.index.tz is not None:
                result.index = result.index.tz_localize(None)
            return result
        except Exception as exc:
            last_error = exc
            outcome = classify_failure(exc)
            if outcome not in (
                AcquisitionOutcome.TRANSIENT,
                AcquisitionOutcome.THROTTLED,
            ):
                raise
            if attempt < MAX_RETRIES - 1:
                time.sleep(0.5 * (2 ** attempt))
    if last_error is not None:
        raise last_error
    return None


def store_combined_data(
    ticker_id: int,
    ticker: str,
    df: pd.DataFrame,
    *,
    replace_existing: bool = False,
):
    """Store ALL data (prices, dividends, splits) from the DataFrame."""
    if df is None or df.empty:
        return

    if replace_existing:
        minimum_date = df.index.min().date()
        maximum_date = df.index.max().date()
        with get_connection() as conn:
            for table_name in ("daily_prices", "dividends", "splits"):
                conn.execute(
                    text(
                        f"DELETE FROM {table_name} "
                        "WHERE ticker_id = :ticker_id AND date BETWEEN :start AND :end"
                    ),
                    {
                        "ticker_id": ticker_id,
                        "start": minimum_date,
                        "end": maximum_date,
                    },
                )

    price_cols = [c for c in PRICE_FIELDS if c in df.columns]
    if price_cols:
        price_df = df[price_cols].copy()
        daily = pd.DataFrame({
            "ticker_id": ticker_id,
            "date": price_df.index.date,
            "open": price_df["Open"].values,
            "high": price_df["High"].values,
            "low": price_df["Low"].values,
            "close": price_df["Close"].values,
            "volume": price_df["Volume"].values,
            "adj_close": (
                price_df["Adj Close"].values
                if "Adj Close" in price_df.columns
                else np.full(len(price_df), np.nan)
            ),
        }).dropna(subset=["open", "close"])

        if not daily.empty:
            fast_bulk_insert("daily_prices", daily)

    if "Dividends" in df.columns:
        div = df["Dividends"]
        div_data = div[div > 0]
        if not div_data.empty:
            div_df = pd.DataFrame({
                "ticker_id": ticker_id,
                "date": div_data.index.date,
                "amount": div_data.values,
            })
            fast_bulk_insert("dividends", div_df)

    if "Stock Splits" in df.columns:
        sp = df["Stock Splits"]
        sp_data = sp[sp > 0]
        if not sp_data.empty:
            ratios = sp_data.values
            factors = [
                f"{r:.1f}:1" if r > 1 else f"1:{1/r:.1f}"
                for r in ratios
            ]
            split_df = pd.DataFrame({
                "ticker_id": ticker_id,
                "date": sp_data.index.date,
                "ratio": ratios,
                "split_factor": factors,
            })
            fast_bulk_insert("splits", split_df)


# ── Aggregation (post-processing) ─────────────────────────────

def aggregate_weekly_monthly(scraper_instance=None):
    """Compute weekly/monthly prices from stored daily data.
    
    Args:
        scraper_instance: Optional BaseScraper instance to use its shutdown flag.
    """
    ensure_progress_table()

    AGG_STAGE_WEEKLY = "agg_weekly"
    AGG_STAGE_MONTHLY = "agg_monthly"

    from src.database import reset_stale_progress
    reset_stale_progress(AGG_STAGE_WEEKLY)
    reset_stale_progress(AGG_STAGE_MONTHLY)

    with get_connection() as conn:
        ticker_ids = [
            r[0] for r in conn.execute(
                text("SELECT DISTINCT ticker_id FROM daily_prices ORDER BY ticker_id")
            ).fetchall()
        ]

    if not ticker_ids:
        print("  [AGG] No daily price data found, skipping aggregation.")
        return

    def is_shutdown():
        if scraper_instance:
            return scraper_instance.shutdown_requested
        return False

    # Weekly aggregation
    weekly_done = set()
    try:
        with get_connection() as conn:
            rows = conn.execute(
                text("SELECT ticker, status FROM scraping_progress WHERE stage = :stage"),
                {"stage": AGG_STAGE_WEEKLY}
            ).fetchall()
            weekly_done = {int(r[0]) for r in rows if r[1] == 'complete'}
    except Exception:
        pass

    weekly_pending = [tid for tid in ticker_ids if tid not in weekly_done]
    print(f"  [AGG] Weekly: {len(weekly_done)} already done, {len(weekly_pending)} remaining")

    if weekly_pending:
        for ticker_id in weekly_pending:
            if is_shutdown():
                print("  [AGG] Shutdown requested - stopping aggregation early.")
                break

            mark_in_progress(AGG_STAGE_WEEKLY, str(ticker_id))
            with get_connection() as conn:
                daily = pd.read_sql_query(
                    "SELECT date, open, high, low, close, volume, adj_close "
                    "FROM daily_prices WHERE ticker_id = :id ORDER BY date",
                    conn.connection,
                    params={"id": ticker_id},
                    parse_dates=["date"],
                )
            if daily.empty:
                save_progress(AGG_STAGE_WEEKLY, str(ticker_id), "complete")
                continue

            daily = daily.set_index("date")
            weekly = daily.resample("W-FRI").agg({
                "open": "first", "high": "max", "low": "min",
                "close": "last", "volume": "sum", "adj_close": "last",
            }).dropna(subset=["open"])

            if not weekly.empty:
                fast_bulk_insert("weekly_prices", pd.DataFrame({
                    "ticker_id": ticker_id,
                    "week_start": weekly.index.date,
                    "open": weekly["open"].values,
                    "high": weekly["high"].values,
                    "low": weekly["low"].values,
                    "close": weekly["close"].values,
                    "volume": weekly["volume"].values,
                    "adj_close": weekly["adj_close"].values,
                }))

            save_progress(AGG_STAGE_WEEKLY, str(ticker_id), "complete")

    # Monthly aggregation
    monthly_done = set()
    try:
        with get_connection() as conn:
            rows = conn.execute(
                text("SELECT ticker, status FROM scraping_progress WHERE stage = :stage"),
                {"stage": AGG_STAGE_MONTHLY}
            ).fetchall()
            monthly_done = {int(r[0]) for r in rows if r[1] == 'complete'}
    except Exception:
        pass

    monthly_pending = [tid for tid in ticker_ids if tid not in monthly_done]
    print(f"  [AGG] Monthly: {len(monthly_done)} already done, {len(monthly_pending)} remaining")

    if monthly_pending:
        for ticker_id in monthly_pending:
            if is_shutdown():
                print("  [AGG] Shutdown requested - stopping aggregation early.")
                break

            mark_in_progress(AGG_STAGE_MONTHLY, str(ticker_id))
            with get_connection() as conn:
                daily = pd.read_sql_query(
                    "SELECT date, open, high, low, close, volume, adj_close "
                    "FROM daily_prices WHERE ticker_id = :id ORDER BY date",
                    conn.connection,
                    params={"id": ticker_id},
                    parse_dates=["date"],
                )
            if daily.empty:
                save_progress(AGG_STAGE_MONTHLY, str(ticker_id), "complete")
                continue

            daily = daily.set_index("date")
            monthly = daily.resample("ME").agg({
                "open": "first", "high": "max", "low": "min",
                "close": "last", "volume": "sum", "adj_close": "last",
            }).dropna(subset=["open"])

            if not monthly.empty:
                fast_bulk_insert("monthly_prices", pd.DataFrame({
                    "ticker_id": ticker_id,
                    "month_start": monthly.index.date,
                    "open": monthly["open"].values,
                    "high": monthly["high"].values,
                    "low": monthly["low"].values,
                    "close": monthly["close"].values,
                    "volume": monthly["volume"].values,
                    "adj_close": monthly["adj_close"].values,
                }))

            save_progress(AGG_STAGE_MONTHLY, str(ticker_id), "complete")

    print("  [AGG] Weekly/monthly aggregation complete!")


# ── BaseScraper Subclass ───────────────────────────────────────

class PriceScraper(BaseScraper):
    """
    Price scraper using BaseScraper infrastructure.
    
    Unlike the per-ticker scrapers, prices uses BATCH processing via yf.download().
    This class overrides run() entirely while still benefiting from BaseScraper's
    signal handler, progress tracking helpers, and cleanup.
    """

    def __init__(self):
        super().__init__(stage="prices", name="PRICES")

    def run(
        self,
        retry_errored: bool = False,
        max_items: Optional[int] = None,
        aggregate: bool = True,
    ):
        """Override run() with batch-based price scraping logic."""
        self._setup_signal_handler()
        self._reset_stale_progress()
        self.start_time = time.time()

        tickers = get_all_ticker_ids()
        total = len(tickers)

        progress = {}
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    text("SELECT ticker, status FROM scraping_progress WHERE stage = :stage"),
                    {"stage": self.stage}
                ).fetchall()
                progress = {r[0]: r[1] for r in rows}
        except Exception:
            pass

        if retry_errored:
            skip_set = {t for t, s in progress.items() if s == 'complete'}
        else:
            skip_set = {t for t, s in progress.items() if s in ('complete', 'error')}
        remaining = [t for t in tickers if t["ticker"] not in skip_set]

        if max_items:
            remaining = remaining[:max_items]

        completed_count = len({t for t, s in progress.items() if s == 'complete'})
        print(f"  [{self.name}] Starting BATCHED scrape for {total} tickers")
        print(f"    Batch size: {PRICE_BATCH_SIZE}, Workers: {CONCURRENT_WORKERS}")
        print(f"    Already complete: {completed_count}, Remaining: {len(remaining)}")

        if not remaining:
            print("  Nothing to scrape!")
        else:
            batches = [
                remaining[i:i + PRICE_BATCH_SIZE]
                for i in range(0, len(remaining), PRICE_BATCH_SIZE)
            ]
            print(f"    Batches to download: {len(batches)}")

            # Phase 1 & 2: Batch downloads + individual fallback
            print("\n  [PHASE 1] Batch downloading (yf.download)...")
            self._process_batches(batches, remaining)

        # Post-processing
        if not self.shutdown_requested and aggregate:
            print("\n  [PRICES] Computing weekly/monthly aggregates...")
            aggregate_weekly_monthly(scraper_instance=self)
        elif not self.shutdown_requested:
            print("\n  [PRICES] Weekly/monthly aggregation disabled for this run.")
        else:
            print("\n  [PRICES] Skipping aggregation (shutdown requested).")

        self._restore_signal_handler()

    def refresh(
        self,
        through: date,
        retry_errored: bool = False,
        max_items: Optional[int] = None,
    ) -> dict[str, int]:
        """Incrementally refresh daily prices and actions without aggregation."""
        tickers = get_all_ticker_ids()
        latest_dates = latest_daily_price_dates()
        latest_attempts = latest_attempts_for_stage("price_refresh")
        terminal_outcomes = {
            AcquisitionOutcome.INVALID_SYMBOL.value,
            AcquisitionOutcome.NO_DATA.value,
            AcquisitionOutcome.SCHEMA_DRIFT.value,
        }
        skipped_terminal = 0
        if not retry_errored:
            eligible = []
            for item in tickers:
                attempt = latest_attempts.get(str(item["ticker"]))
                if attempt is not None and attempt["outcome"] in terminal_outcomes:
                    skipped_terminal += 1
                else:
                    eligible.append(item)
            tickers = eligible
        if max_items is not None:
            tickers = tickers[:max_items]

        outcomes: Counter[str] = Counter()
        if skipped_terminal:
            outcomes["skipped_terminal"] = skipped_terminal
        with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
            futures = {
                executor.submit(
                    self._refresh_one,
                    item,
                    latest_dates.get(int(item["id"])),
                    through,
                ): item
                for item in tickers
            }
            for future in as_completed(futures):
                outcome = future.result()
                outcomes[outcome.value] += 1

        print(
            f"  [PRICE_REFRESH] Processed {len(tickers)} tickers "
            f"through {through.isoformat()}: {dict(outcomes)}"
        )
        return dict(outcomes)

    def _refresh_one(
        self,
        item: dict[str, object],
        latest_stored: date | None,
        through: date,
    ) -> AcquisitionOutcome:
        ticker_id = int(item["id"])
        ticker = str(item["ticker"])
        started_at = datetime.now(timezone.utc)
        fetch_range: FetchRange | None = None
        outcome = AcquisitionOutcome.TRANSIENT
        observed_start: date | None = None
        observed_end: date | None = None
        detail = ""
        try:
            fetch_range = plan_fetch_range(latest_stored, through)
            result = fetch_ticker_range(ticker, fetch_range)
            if result is None or result.empty:
                outcome = AcquisitionOutcome.NO_DATA
            else:
                observed_start = result.index.min().date()
                observed_end = result.index.max().date()
                store_combined_data(
                    ticker_id,
                    ticker,
                    result,
                    replace_existing=True,
                )
                outcome = AcquisitionOutcome.COMPLETE
        except Exception as exc:
            outcome = classify_failure(exc)
            detail = safe_error_detail(exc)
        finally:
            finished_at = datetime.now(timezone.utc)
            record_attempt(
                "price_refresh",
                ticker,
                outcome.value,
                started_at,
                finished_at,
                requested_start=fetch_range.start if fetch_range else None,
                requested_end=fetch_range.end if fetch_range else None,
                observed_start=observed_start,
                observed_end=observed_end,
                detail=detail,
            )
        return outcome

    def _process_batches(self, batches, remaining):
        """Process all batches with parallel workers. Results stored in self.*_count."""
        start_time = time.time()
        self.success_count = 0
        self.error_count = 0
        batch_failures: List[str] = []
        total_done = sum(len(b) for b in batches)

        with LiveProgress(
            total=total_done,
            description=f"Batch downloading {total_done} tickers",
            stage_name=self.name,
        ) as pbar:
            with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
                future_map = {}
                for idx, batch in enumerate(batches):
                    if self.shutdown_requested:
                        print(f"    [SHUTDOWN] Stopping new batch submissions ({len(batches) - idx} remaining).")
                        break
                    future_map[executor.submit(self._process_single_batch, batch)] = idx

                for future in as_completed(future_map):
                    batch_idx = future_map[future]
                    batch = batches[batch_idx]
                    try:
                        s, e, failed = future.result()
                        self.success_count += s
                        self.error_count += e
                        batch_failures.extend(failed)
                    except Exception:
                        s, e, failed = self._process_individual(batch)
                        self.success_count += s
                        self.error_count += e

                    # Update progress bar with per-ticker success/failure
                    for _ in range(s):
                        pbar.advance(success=True)
                    for _ in range(e):
                        pbar.advance(success=False)

            # Phase 2: Retry failed tickers individually
            if batch_failures and not self.shutdown_requested:
                print(f"\n  [PHASE 2] Retrying {len(batch_failures)} failed tickers individually...")
                with LiveProgress(
                    total=len(batch_failures),
                    description="Retrying individual failures",
                    stage_name=self.name,
                    transient=True,
                ) as retry_bar:
                    failed_tickers_data = [t for t in remaining if t["ticker"] in batch_failures]
                    for i in range(0, len(failed_tickers_data), PRICE_BATCH_SIZE):
                        if self.shutdown_requested:
                            break
                        fb = failed_tickers_data[i:i + PRICE_BATCH_SIZE]
                        s, e, _ = self._process_individual(fb)
                        self.success_count += s
                        self.error_count += e
                        for _ in range(len(fb)):
                            retry_bar.advance()

        elapsed = time.time() - start_time
        print(f"  [{self.name}] {'Interrupted' if self.shutdown_requested else 'Complete'} "
              f"in {elapsed:.0f}s ({elapsed/60:.1f} min)!")
        print(f"    Success: {self.success_count}, Errors: {self.error_count}")

    def _process_single(self, item: dict) -> bool:
        """
        Satisfy abstract interface — PriceScraper uses batch processing via run() override,
        so this method is never called through BaseScraper's _process_items().
        """
        raise NotImplementedError(
            "PriceScraper uses batch processing. Call run() directly."
        )

    def _process_single_batch(self, batch: List[Dict]) -> Tuple[int, int, List[str]]:
        """Download and process a single batch of tickers."""
        data = download_batch(batch)
        if data is not None and not data.empty:
            return self._store_batch_data(data, batch)
        else:
            return self._process_individual(batch)

    def _store_batch_data(self, data: pd.DataFrame, batch: List[Dict]) -> Tuple[int, int, List[str]]:
        """Store data from a batch download."""
        success = 0
        errors = 0
        failed = []
        is_multi = isinstance(data.columns, pd.MultiIndex)

        for t in batch:
            ticker = t["ticker"]
            ticker_id = t["id"]
            mark_in_progress(self.stage, ticker)

            try:
                if is_multi:
                    try:
                        ticker_data = data.xs(ticker, level=1, axis=1).copy()
                    except KeyError:
                        save_progress(self.stage, ticker, "error", "No data in batch")
                        errors += 1
                        failed.append(ticker)
                        continue
                else:
                    ticker_data = data.copy()

                store_combined_data(ticker_id, ticker, ticker_data)
                save_progress(self.stage, ticker, "complete")
                success += 1
            except Exception as e:
                save_progress(self.stage, ticker, "error", str(e)[:200])
                errors += 1
                failed.append(ticker)

        return success, errors, failed

    def _process_individual(self, batch: List[Dict]) -> Tuple[int, int, List[str]]:
        """Process tickers one-by-one as fallback."""
        success = 0
        errors = 0
        failed = []

        for t in batch:
            ticker = t["ticker"]
            ticker_id = t["id"]
            mark_in_progress(self.stage, ticker)

            hist = fetch_ticker_history(ticker)
            if hist is not None:
                try:
                    store_combined_data(ticker_id, ticker, hist)
                    save_progress(self.stage, ticker, "complete")
                    success += 1
                except Exception as e:
                    save_progress(self.stage, ticker, "error", str(e)[:200])
                    errors += 1
                    failed.append(ticker)
            else:
                save_progress(self.stage, ticker, "error", "No data")
                errors += 1
                failed.append(ticker)

        return success, errors, failed


# ── Convenience Entry Point ────────────────────────────────────

def run_price_scraper(
    retry_errored: bool = False,
    ticker_filter=None,
    max_tickers: Optional[int] = None,
    aggregate: bool = True,
):
    """Run price scraper (convenience wrapper)."""
    scraper = PriceScraper()
    if ticker_filter is not None:
        scraper._ticker_filter = ticker_filter
    try:
        scraper.run(
            retry_errored=retry_errored,
            max_items=max_tickers,
            aggregate=aggregate,
        )
    finally:
        scraper.cleanup()


if __name__ == "__main__":
    from src.database import init_database
    init_database()
    run_price_scraper()

if __name__ == "__main__":
    from src.database import init_database
    init_database()
    run_price_scraper()
