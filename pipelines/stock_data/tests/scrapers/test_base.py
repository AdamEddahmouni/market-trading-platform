"""Tests for `src.scrapers.base.BaseScraper`.

The abstract `BaseScraper` is large and exercises several collaborators
(database, signal handling, ThreadPoolExecutor, rich progress bar). The
tests in this file mock those collaborators via the autouse
`scraper_dependencies` fixture in `tests/scrapers/conftest.py`, then
verify behaviour via a `MockScraper` concrete subclass that records its
processed items.
"""

from __future__ import annotations

import signal
import sys
from unittest.mock import MagicMock

import pytest

from src.scrapers.base import BaseScraper
from tests.scrapers.conftest import MockScraper


# ── Initialization ─────────────────────────────────────────────


class TestInitialization:
    def test_init_sets_defaults(self, scraper_dependencies, mocker):
        scraper = MockScraper("prices", name="PriceScraper")
        assert scraper.stage == "prices"
        assert scraper.name == "PriceScraper"
        assert scraper.shutdown_requested is False
        assert scraper.success_count == 0
        assert scraper.error_count == 0
        assert scraper.start_time == 0.0
        assert scraper._original_sigint is None
        # Throttler is a real DomainThrottler (not under test here).
        assert scraper.throttler is not None

    def test_init_creates_stealth_session(self, scraper_dependencies):
        # StealthSession is mocked at `src.scrapers.base.StealthSession`
        # (autouse fixture). It returns a single MagicMock instance which
        # is what BaseScraper stores as `self.http`.
        import src.scrapers.base as base
        scraper = MockScraper("prices")
        assert scraper.http is not None
        assert base.StealthSession.called

    def test_init_calls_ensure_progress_table(self, scraper_dependencies):
        # The autouse fixture mocks `ensure_progress_table`; calling
        # MockScraper triggers `BaseScraper.__init__` which calls it once.
        import src.scrapers.base as base
        MockScraper("prices")
        base.ensure_progress_table.assert_called_once()

    def test_name_falls_back_to_stage_when_empty(self, scraper_dependencies):
        scraper = MockScraper("prices")
        # `MockScraper` doesn't pass `name`, so it falls back to `stage`.
        assert scraper.name == "prices"


# ── Signal Handler ─────────────────────────────────────────────


class TestSignalHandler:
    def test_setup_installs_signal_handler(self, scraper_dependencies):
        scraper = MockScraper("prices")
        scraper._setup_signal_handler()
        handler = signal.getsignal(signal.SIGINT)
        assert handler is not None
        assert scraper._original_sigint is not None

    def test_single_invocation_sets_shutdown_requested(self, scraper_dependencies):
        scraper = MockScraper("prices")
        scraper._setup_signal_handler()
        handler = signal.getsignal(signal.SIGINT)
        handler(signal.SIGINT, None)
        assert scraper.shutdown_requested is True

    def test_double_invocation_calls_sys_exit(self, scraper_dependencies):
        scraper = MockScraper("prices")
        scraper._setup_signal_handler()
        handler = signal.getsignal(signal.SIGINT)
        handler(signal.SIGINT, None)  # first Ctrl+C
        with pytest.raises(SystemExit) as exc_info:
            handler(signal.SIGINT, None)  # second Ctrl+C → sys.exit(1)
        assert exc_info.value.code == 1

    def test_restore_resets_handler(self, scraper_dependencies):
        scraper = MockScraper("prices")
        original_handler = signal.getsignal(signal.SIGINT)
        scraper._setup_signal_handler()
        assert signal.getsignal(signal.SIGINT) is not original_handler
        scraper._restore_signal_handler()
        assert signal.getsignal(signal.SIGINT) is original_handler


# ── Progress Tracking Methods ──────────────────────────────────


class TestProgressTracking:
    def test_mark_progress_delegates_to_save_progress(
        self, scraper_dependencies,
    ):
        import src.scrapers.base as base
        scraper = MockScraper("prices")
        scraper.mark_progress("AAPL", "complete", "ok")
        base.save_progress.assert_called_once_with(
            "prices", "AAPL", "complete", "ok"
        )

    def test_mark_in_progress_delegates(self, scraper_dependencies):
        import src.scrapers.base as base
        scraper = MockScraper("prices")
        scraper.mark_in_progress("AAPL")
        base.mark_in_progress.assert_called_once_with("prices", "AAPL")


# ── _reset_stale_progress ──────────────────────────────────────


class TestResetStaleProgress:
    def test_logs_count_when_stale_entries_exist(self, scraper_dependencies):
        import src.scrapers.base as base
        # Override autouse default (returns 0) to simulate stale entries.
        base.reset_stale_progress.return_value = 5
        scraper = MockScraper("prices")
        scraper._reset_stale_progress()
        base.reset_stale_progress.assert_called_once_with("prices")

    def test_silent_when_no_stale_entries(self, scraper_dependencies):
        # Default autouse mock returns 0 → no log line is printed.
        import src.scrapers.base as base
        scraper = MockScraper("prices")
        # Should not raise.
        scraper._reset_stale_progress()
        base.reset_stale_progress.assert_called_once_with("prices")


# ── _get_pending_items ─────────────────────────────────────────


class TestGetPendingItems:
    def test_returns_all_when_no_progress(
        self, scraper_dependencies, make_tickers, make_progress
    ):
        make_tickers(["AAPL", "MSFT", "GOOG"])
        make_progress([])

        scraper = MockScraper("prices")
        pending = scraper._get_pending_items()
        assert {t["ticker"] for t in pending} == {"AAPL", "MSFT", "GOOG"}

    def test_skips_complete_items_by_default(
        self, scraper_dependencies, make_tickers, make_progress
    ):
        make_tickers(["AAPL", "MSFT", "GOOG"])
        make_progress([("AAPL", "complete"), ("MSFT", "complete")])

        scraper = MockScraper("prices")
        pending = scraper._get_pending_items()
        assert [t["ticker"] for t in pending] == ["GOOG"]

    def test_skips_errored_items_by_default(
        self, scraper_dependencies, make_tickers, make_progress
    ):
        make_tickers(["AAPL", "MSFT", "GOOG"])
        make_progress([("AAPL", "error")])

        scraper = MockScraper("prices")
        pending = scraper._get_pending_items()
        assert {t["ticker"] for t in pending} == {"MSFT", "GOOG"}

    def test_retry_errored_includes_errored(
        self, scraper_dependencies, make_tickers, make_progress
    ):
        make_tickers(["AAPL", "MSFT", "GOOG"])
        make_progress([("AAPL", "complete"), ("MSFT", "error")])

        scraper = MockScraper("prices")
        pending = scraper._get_pending_items(retry_errored=True)
        # AAPL (complete) skipped, MSFT (error) re-included, GOOG (pending).
        assert {t["ticker"] for t in pending} == {"MSFT", "GOOG"}


# ── run() lifecycle ────────────────────────────────────────────


class TestRunLifecycle:
    def test_run_with_no_items_prints_and_returns(
        self, scraper_dependencies, make_tickers, make_progress
    ):
        make_tickers([])
        make_progress([])

        scraper = MockScraper("prices")
        # Should not raise; should not call _process_items.
        scraper.run()
        # No signal handler set/restore cycle happened beyond setup.
        # No items processed.
        assert scraper.processed_items == []
        assert scraper.success_count == 0
        assert scraper.error_count == 0

    def test_run_with_max_items_limits_batch(
        self, scraper_dependencies, make_tickers, make_progress, mocker
    ):
        make_tickers([f"T{i}" for i in range(10)])
        make_progress([])

        scraper = MockScraper("prices")
        scraper.run(max_items=3)
        assert len(scraper.processed_items) == 3
        assert scraper.success_count == 3

    def test_run_processes_all_pending_items(
        self, scraper_dependencies, make_tickers, make_progress
    ):
        make_tickers(["A", "B", "C", "D"])
        make_progress([])

        scraper = MockScraper("prices")
        scraper.run()
        assert sorted(scraper.processed_items) == ["A", "B", "C", "D"]
        assert scraper.success_count == 4
        assert scraper.error_count == 0

    def test_run_restores_signal_handler_after_finish(
        self, scraper_dependencies, make_tickers, make_progress
    ):
        make_tickers(["A", "B"])
        make_progress([])
        pre = signal.getsignal(signal.SIGINT)
        scraper = MockScraper("prices")
        scraper.run()
        assert signal.getsignal(signal.SIGINT) is pre


# ── _process_items ─────────────────────────────────────────────


class TestProcessItems:
    def test_process_items_records_successes(
        self, scraper_dependencies, make_tickers, make_progress
    ):
        make_tickers([f"T{i}" for i in range(5)])
        make_progress([])

        scraper = MockScraper("prices", return_value=True)
        items = [{"id": i, "ticker": f"T{i}"} for i in range(5)]
        scraper._process_items(items)
        assert len(scraper.processed_items) == 5
        assert scraper.success_count == 5
        assert scraper.error_count == 0

    def test_process_items_records_errors(
        self, scraper_dependencies, make_tickers, make_progress
    ):
        make_tickers([f"T{i}" for i in range(3)])
        make_progress([])

        scraper = MockScraper("prices", return_value=False)
        items = [{"id": i, "ticker": f"T{i}"} for i in range(3)]
        scraper._process_items(items)
        assert scraper.success_count == 0
        assert scraper.error_count == 3

    def test_process_items_stops_submitting_on_shutdown(
        self, scraper_dependencies, make_tickers, make_progress
    ):
        make_tickers([f"T{i}" for i in range(20)])
        make_progress([])

        scraper = MockScraper("prices", return_value=True)
        scraper.shutdown_requested = True  # set BEFORE processing.
        items = [{"id": i, "ticker": f"T{i}"} for i in range(20)]
        scraper._process_items(items)
        # None should be processed because we bailed out before submitting.
        assert scraper.processed_items == []
        assert scraper.success_count == 0

    def test_process_single_wrapper_marks_in_progress(
        self, scraper_dependencies,
    ):
        import src.scrapers.base as base
        scraper = MockScraper("prices", return_value=True)
        scraper._process_single_wrapper({"id": 1, "ticker": "AAPL"})
        base.mark_in_progress.assert_called_once_with("prices", "AAPL")

    def test_process_single_wrapper_returns_False_on_exception(
        self, scraper_dependencies, make_tickers, make_progress
    ):
        make_tickers([])
        make_progress([])
        scraper = MockScraper("prices", return_value=True)
        scraper._raises = RuntimeError("boom")
        ok = scraper._process_single_wrapper({"id": 1, "ticker": "FAIL"})
        assert ok is False
        assert scraper.processed_items == ["FAIL"]


# ── Abstract Method ────────────────────────────────────────────


class TestAbstractMethod:
    def test_base_cannot_be_instantiated_directly(self):
        with pytest.raises(TypeError):
            BaseScraper("prices")  # type: ignore[abstract]


# ── get_stealth_session / cleanup ──────────────────────────────


class TestSessionUtilities:
    def test_get_stealth_session_returns_existing(
        self, scraper_dependencies
    ):
        scraper = MockScraper("prices")
        session = scraper.get_stealth_session()
        assert session is scraper.http

    def test_get_stealth_session_recreates_if_none(self, scraper_dependencies, mocker):
        scraper = MockScraper("prices")
        scraper.http = None
        # New mock session for the recreated instance.
        new_session = MagicMock(name="NewStealthSession")
        mocker.patch("src.scrapers.base.StealthSession", return_value=new_session)
        session = scraper.get_stealth_session()
        assert session is new_session

    def test_cleanup_closes_http(self, scraper_dependencies):
        scraper = MockScraper("prices")
        scraper.http.close = MagicMock()
        scraper.cleanup()
        scraper.http.close.assert_called_once()

    def test_cleanup_swallows_close_exceptions(self, scraper_dependencies):
        scraper = MockScraper("prices")
        scraper.http.close = MagicMock(side_effect=Exception("already closed"))
        # Must not raise.
        scraper.cleanup()

    def test_cleanup_handles_missing_http(self, scraper_dependencies):
        scraper = MockScraper("prices")
        del scraper.http  # simulate missing attribute
        # Must not raise.
        scraper.cleanup()
