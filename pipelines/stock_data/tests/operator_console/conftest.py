"""
UI test fixtures.

Filter / export tests do most of their work without touching the
database (they cover pure SQL generation, value parsing, etc.). Tests
that DO need the database lean on the autouse fixtures that already
exist in `tests/scrapers/conftest.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest

from src.operator_console.filter import FilterSpec


@dataclass
class _DummyNs:
    """argparse-like namespace used by `parse_filter_args` tests."""
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    is_etf: Optional[str] = None
    min_cap: Optional[str] = None
    max_cap: Optional[str] = None
    ticker_regex: Optional[str] = None
    company_regex: Optional[str] = None
    limit: Optional[int] = None


@pytest.fixture
def dummy_args():
    """Return a `_DummyNs` factory for `parse_filter_args` tests."""
    def _factory(**overrides):
        ns = _DummyNs(**overrides)
        return ns
    return _factory


@pytest.fixture
def preset_filter():
    """A non-empty FilterSpec for tests that exercise the describe workflows."""
    return FilterSpec(
        exchanges=("NASDAQ", "NYSE"),
        sectors=("Technology",),
        min_market_cap=1_000_000_000,
        max_market_cap=100_000_000_000,
        ticker_regex="^A",
        company_name_regex="Apple|Bank",
        limit=50,
    )
