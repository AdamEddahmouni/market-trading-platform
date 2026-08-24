"""
Scraper-specific pytest fixtures and a `MockScraper` concrete subclass
for testing the abstract `BaseScraper`.

The `scraper_dependencies` autouse fixture replaces the heavy collaborators
(`StealthSession`, `LiveProgress`, plus the database functions used by
`BaseScraper`) with mocks for every test in this directory. Tests that need
to drive specific behavior on those collaborators should reach for the
`mocker` fixture or override these mocks explicitly.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.scrapers.base import BaseScraper


# ── Mocked Subclass ────────────────────────────────────────────


class MockScraper(BaseScraper):
    """A minimal concrete subclass of `BaseScraper` for tests.

    Notes:
      - Inherits all methods (`run`, `_setup_signal_handler`,
        `_process_items`, `mark_progress`, etc.).
      - `_process_single` returns the configured `return_value` and
        records the ticker in `processed_items`. Tests can set `_raises`
        to make it raise instead.
      - `BaseScraper` declares `_process_single` as `@abstractmethod`;
        providing it here makes the class concrete.
    """

    def __init__(self, stage: str, name: str = "", return_value: bool = True):
        super().__init__(stage, name=name)
        self.processed_items: list[str] = []
        self._return_value = return_value
        self._raises: Exception | None = None

    def _process_single(self, item):
        self.processed_items.append(item["ticker"])
        if self._raises is not None:
            raise self._raises
        return self._return_value


# ── Dependency Mocking ─────────────────────────────────────────


@pytest.fixture(autouse=True)
def scraper_dependencies(mocker):
    """Replace heavy collaborators with mocks for every scraper test.

    Mocks:
      - `src.scrapers.base.stealth_session_factory` not needed; instead we
        stub `StealthSession` at the import location.
      - `src.scrapers.base.LiveProgress` - replaced with a context manager
        mock so no rich live display is rendered.
      - `src.scrapers.base.ensure_progress_table`,
        `get_all_ticker_ids`, `save_progress`, `mark_in_progress`,
        `reset_stale_progress`, `get_connection` - mocked so no SQLite is
        touched.
    """
    # Stealth HTTP session (constructed in BaseScraper.__init__).
    mocker.patch(
        "src.scrapers.base.StealthSession",
        return_value=MagicMock(name="StealthSession"),
    )

    # Rich progress bar (constructed in BaseScraper._process_items).
    fake_pbar = MagicMock(name="LiveProgress")
    fake_pbar.advance = MagicMock(name="advance")
    fake_pbar.__enter__ = MagicMock(return_value=fake_pbar)
    fake_pbar.__exit__ = MagicMock(return_value=False)
    mocker.patch("src.scrapers.base.LiveProgress", return_value=fake_pbar)

    # Database progress tracking.
    mocker.patch("src.scrapers.base.ensure_progress_table", return_value=None)
    mocker.patch(
        "src.scrapers.base.reset_stale_progress",
        return_value=0,  # No stale entries by default; override per test.
    )
    mocker.patch(
        "src.scrapers.base.save_progress",
        return_value=None,
    )
    mocker.patch(
        "src.scrapers.base.mark_in_progress",
        return_value=None,
    )

    # `get_all_ticker_ids` and `get_connection` are used inside
    # `_get_pending_items`. Override per-test using the `tickers` and
    # `progress_rows` fixtures below (or inline `mocker.patch`).
    mocker.patch(
        "src.scrapers.base.get_all_ticker_ids",
        return_value=[],
    )

    # Default get_connection stub returning a mockable connection.
    fake_conn_cm = MagicMock(name="ConnectionContextManager")
    fake_conn = fake_conn_cm.__enter__.return_value  # `with` returns this
    fake_conn.execute.return_value.fetchall.return_value = []
    fake_conn_cm.__exit__.return_value = False
    mocker.patch(
        "src.scrapers.base.get_connection",
        return_value=fake_conn_cm,
    )

    return {
        "fake_pbar": fake_pbar,
        "fake_conn": fake_conn,
        "fake_conn_cm": fake_conn_cm,
    }


# ── Helper Fixtures ────────────────────────────────────────────


@pytest.fixture
def make_tickers(mocker):
    """Return a helper that patches `get_all_ticker_ids` with given items."""
    def _make(tickers):
        items = [{"id": i + 1, "ticker": t} for i, t in enumerate(tickers)]
        mocker.patch("src.scrapers.base.get_all_ticker_ids", return_value=items)
        return items

    return _make


@pytest.fixture
def make_progress(mocker):
    """Return a helper that patches `get_connection.execute().fetchall()`."""
    def _make(rows):
        """`rows` is an iterable of (ticker, status) tuples."""
        # Reach into the autouse fixture's fake connection setup by
        # patching symbol ancored at the base module.
        mock_conn = mocker.patch("src.scrapers.base.get_connection")
        ctx = MagicMock(name="ConnectionContextManager")
        ctx.__enter__.return_value = ctx  # body sees the cm itself
        ctx.__exit__.return_value = False
        ctx.execute.return_value.fetchall.return_value = list(rows)
        mock_conn.return_value = ctx
        return ctx

    return _make
