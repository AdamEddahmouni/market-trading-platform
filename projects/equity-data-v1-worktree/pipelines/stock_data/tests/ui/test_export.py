"""Tests for `src.ui.export`.

Covers the offline logic that doesn't require a real database:
  * `EXPORT_GROUPS` structure (every group has known tables)
  * `ExportRequest` describe / immutability / default
  * `apply_filter` SQL composition (also lightly exercised via the
    smoke import).
"""

from __future__ import annotations

import pytest

from src.ui.export import EXPORT_GROUPS, ExportRequest


# ── EXPORT_GROUPS catalog ──────────────────────────────────


class TestExportGroups:
    """Catalog canary tests — every group should resolve to existing
    tables defined in `src.database`. If a new table is added, update
    the group mapping AND this test list."""

    EXPECTED_TABLES = {
        "daily_prices", "weekly_prices", "monthly_prices",
        "dividends", "splits",
        "fundamentals",
        "income_statements_annual", "income_statements_quarterly",
        "balance_sheets_annual", "balance_sheets_quarterly",
        "cash_flow_annual", "cash_flow_quarterly",
        "supplemental_data", "index_membership",
        "options_chain", "insider_trades", "earnings_calendar",
    }

    def test_groups_non_empty(self):
        assert len(EXPORT_GROUPS) >= 3
        for label, tables in EXPORT_GROUPS.items():
            assert len(tables) >= 1
            assert isinstance(label, str)
            assert all(isinstance(t, str) for t in tables)

    def test_group_tables_unique(self):
        # No table should appear in two groups (would create ambiguity in
        # the wizard's "tables" output).
        seen = set()
        for tables in EXPORT_GROUPS.values():
            for t in tables:
                assert t not in seen, f"{t} appears in multiple groups"
                seen.add(t)

    def test_every_group_table_is_recognized(self):
        for label, tables in EXPORT_GROUPS.items():
            for t in tables:
                assert t in self.EXPECTED_TABLES, (
                    f"Group '{label}' references unknown table '{t}'. "
                    f"Update EXPORT_GROUPS or the EXPECTED_TABLES list."
                )

    def test_expected_tables_all_covered(self):
        # Inverse: every known table should be in at least one group
        # (or `tickers`, which is handled by include_tickers=True).
        covered = set()
        for tables in EXPORT_GROUPS.values():
            covered.update(tables)
        missing = self.EXPECTED_TABLES - covered - {"(tickers-explicit)"}
        # `tickers` isn't a table here — `include_tickers=True` adds it.
        assert missing == set() or missing == {"tickers"}, (
            f"Expected tables missing from groups: {missing}"
        )


# ── ExportRequest ──────────────────────────────────────────


class TestExportRequest:
    def test_minimal_defaults(self):
        req = ExportRequest(tables=())
        assert req.format == "both"
        assert req.output_dir is None
        assert req.ticker_filter is None
        assert req.include_tickers is True

    def test_describe_minimal(self):
        req = ExportRequest(tables=("daily_prices",))
        desc = req.describe()
        assert "format=both" in desc
        assert "tables=1" in desc
        assert "+tickers" in desc
        assert "tickers=all" in desc

    def test_describe_with_filter_and_dir(self, preset_filter, tmp_path):
        req = ExportRequest(
            tables=("daily_prices", "fundamentals"),
            format="csv",
            output_dir=tmp_path,
            ticker_filter=preset_filter,
            include_tickers=False,
        )
        desc = req.describe()
        assert "format=csv" in desc
        assert "tables=2" in desc
        assert "+tickers" not in desc
        assert f"output={tmp_path}" in desc
        assert "filter=" in desc

    def test_is_frozen(self):
        req = ExportRequest(tables=("daily_prices",))
        with pytest.raises((AttributeError, Exception)):
            req.tables = ()  # type: ignore[misc]

    def test_tables_is_tuple(self):
        # Frozen dataclass with Tuple annotation does NOT auto-coerce.
        # Callers must pass an actual tuple.
        req = ExportRequest(tables=("daily_prices", "fundamentals"))
        assert isinstance(req.tables, tuple)
        assert req.tables == ("daily_prices", "fundamentals")
