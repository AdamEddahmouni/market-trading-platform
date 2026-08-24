"""
Base Scraper - Common base class for all stealth scrapers.
Provides:
  - Graceful shutdown handling (Ctrl+C)
  - Resume-from-crash progress tracking
  - ThreadPoolExecutor parallelism
  - Rate limiting per domain
  - Configurable retry logic
  - Consistent logging
"""

import signal
import sys
import time
from typing import List, Dict, Any, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from abc import ABC, abstractmethod
from datetime import datetime

from src.config import CONCURRENT_WORKERS, MAX_RETRIES
from src.database import (
    get_all_ticker_ids, save_progress, mark_in_progress,
    reset_stale_progress, get_connection, ensure_progress_table
)
from src.scrapers.http_client import StealthSession
from src.scrapers.rate_limiter import DomainThrottler
from src.ui import LiveProgress
from sqlalchemy.sql import text


class BaseScraper(ABC):
    """
    Abstract base class for all scrapers.
    
    Features:
    - Graceful Ctrl+C shutdown (press twice to force)
    - Resume-from-crash via database progress tracking
    - Parallel processing with configurable workers
    - Stealth HTTP client for evading bot detection
    - Consistent logging format
    """

    def __init__(self, stage: str, name: str = "", ticker_filter=None):
        self.stage = stage
        self.name = name or stage
        self.shutdown_requested = False
        self.success_count = 0
        self.error_count = 0
        self.start_time = 0.0
        self.http = StealthSession()
        self.throttler = DomainThrottler()
        self._original_sigint = None
        # Optional ticker filter applied inside `_get_pending_items`. When
        # set (non-empty), the scraper only processes tickers matching the
        # spec instead of `WHERE t.is_active = 1`.
        self._ticker_filter = ticker_filter
        # Ensure progress tracking table exists for any scraper
        ensure_progress_table()

    # ── Lifecycle ──────────────────────────────────────────────

    def run(self, retry_errored: bool = False, max_items: Optional[int] = None):
        """
        Run the scraper with progress tracking and resume support.
        This is the main entry point.
        """
        self._setup_signal_handler()
        self._reset_stale_progress()
        self.start_time = time.time()

        items = self._get_pending_items(retry_errored)

        if max_items:
            items = items[:max_items]

        if not items:
            print(f"  [{self.name}] Nothing to scrape!")
            return

        print(f"  [{self.name}] Processing {len(items)} items "
              f"({CONCURRENT_WORKERS} workers)...")

        self._process_items(items)

        elapsed = time.time() - self.start_time
        print(f"\n  [{self.name}] {'Interrupted' if self.shutdown_requested else 'Complete'} "
              f"in {elapsed:.0f}s ({elapsed/60:.1f} min)!")
        print(f"    Success: {self.success_count}, Errors: {self.error_count}")

        self._restore_signal_handler()

    def _setup_signal_handler(self):
        """Install Ctrl+C handler for graceful shutdown."""
        self.shutdown_requested = False

        def handler(signum, frame):
            if self.shutdown_requested:
                print("\n  [SHUTDOWN] Double Ctrl+C detected — forcing immediate exit.")
                sys.exit(1)
            self.shutdown_requested = True
            print(f"\n  [SHUTDOWN] Graceful shutdown requested. Finishing in-flight items...")
            print("  [SHUTDOWN] Press Ctrl+C again to force exit.")

        self._original_sigint = signal.getsignal(signal.SIGINT)
        signal.signal(signal.SIGINT, handler)

    def _restore_signal_handler(self):
        """Restore original signal handler."""
        if self._original_sigint:
            signal.signal(signal.SIGINT, self._original_sigint)

    # ── Progress Tracking ──────────────────────────────────────

    def _reset_stale_progress(self):
        """Reset stale 'in_progress' entries from a previous crash."""
        stale = reset_stale_progress(self.stage)
        if stale:
            print(f"  [{self.name}] Reset {stale} stale 'in_progress' entries "
                  f"(left from a crash)")

    def _get_pending_items(self, retry_errored: bool = False) -> List[Dict]:
        """
        Get items that still need processing.
        Override in subclass if different logic needed.

        Resolution order:
          1. If a ticker filter has been provided via `__init__`, apply it
             against the database (`apply_filter`) and use the result as
             the candidate universe.
          2. Otherwise, fall back to `get_all_ticker_ids()`.
        """
        if self._ticker_filter:
            from src.ui.filter import apply_filter
            all_items = apply_filter(self._ticker_filter)
        else:
            all_items = get_all_ticker_ids()

        with get_connection() as conn:
            progress = conn.execute(
                text("SELECT ticker, status FROM scraping_progress WHERE stage = :stage"),
                {"stage": self.stage}
            ).fetchall()
        progress_dict = {r[0]: r[1] for r in progress}

        if retry_errored:
            skip_set = {t for t, s in progress_dict.items() if s == 'complete'}
        else:
            skip_set = {t for t, s in progress_dict.items() if s in ('complete', 'error')}

        remaining = [t for t in all_items if t["ticker"] not in skip_set]
        completed = len({t for t, s in progress_dict.items() if s == 'complete'})
        errored = len({t for t, s in progress_dict.items() if s == 'error'})

        print(f"  [{self.name}] Total: {len(all_items)}, "
              f"Completed: {completed}, Errored: {errored}, "
              f"Remaining: {len(remaining)}")

        return remaining

    def mark_progress(self, ticker: str, status: str, details: str = ""):
        """Mark progress for an item."""
        save_progress(self.stage, ticker, status, details)

    def mark_in_progress(self, ticker: str):
        """Mark item as in progress."""
        mark_in_progress(self.stage, ticker)

    # ── Parallel Processing ────────────────────────────────────

    def _process_items(self, items: List[Dict]):
        """
        Process items in parallel using ThreadPoolExecutor.
        Each item is processed by _process_single.
        Shows a live rich progress bar while running.
        """
        total = len(items)
        with LiveProgress(
            total=total,
            description=f"Scraping {total} tickers",
            stage_name=self.name,
        ) as pbar:
            with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
                futures = {}
                for item in items:
                    if self.shutdown_requested:
                        remaining = len(items) - len(futures)
                        print(f"  [SHUTDOWN] Stopping new submissions ({remaining} remaining).")
                        break
                    future = executor.submit(self._process_single_wrapper, item)
                    futures[future] = item["ticker"]

                for future in as_completed(futures):
                    ticker = futures[future]
                    ok = False
                    try:
                        ok = future.result()
                        if ok:
                            save_progress(self.stage, ticker, "complete")
                            self.success_count += 1
                        else:
                            save_progress(self.stage, ticker, "error")
                            self.error_count += 1
                    except Exception as e:
                        save_progress(self.stage, ticker, "error", str(e)[:200])
                        self.error_count += 1

                    pbar.advance(success=ok)

    def _process_single_wrapper(self, item: Dict) -> bool:
        """Wrapper that marks in_progress and calls _process_single."""
        ticker = item["ticker"]
        self.mark_in_progress(ticker)
        try:
            return self._process_single(item)
        except Exception as e:
            print(f"    [ERROR] {ticker}: {str(e)[:100]}")
            return False

    @abstractmethod
    def _process_single(self, item: Dict) -> bool:
        """
        Process a single item. Must be implemented by subclasses.
        Returns True on success, False on failure.
        """
        raise NotImplementedError

    def _log_progress(self):
        """Log progress at intervals (fallback, used by price scraper)."""
        done = self.success_count + self.error_count
        if done % 100 == 0:
            elapsed = time.time() - self.start_time
            rate = done / elapsed if elapsed > 0 else 0
            print(f"    Progress: {done} ({rate:.1f}/s) "
                  f"[success={self.success_count}, errors={self.error_count}]")

    # ── Utilities ──────────────────────────────────────────────

    def get_stealth_session(self) -> StealthSession:
        """Get the shared stealth HTTP session."""
        if not hasattr(self, 'http') or self.http is None:
            self.http = StealthSession()
        return self.http

    def cleanup(self):
        """Clean up resources."""
        if hasattr(self, 'http') and self.http:
            try:
                self.http.close()
            except Exception:
                pass
