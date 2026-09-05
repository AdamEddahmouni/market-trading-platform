"""Finviz per-symbol export for symbols outside the bulk screener."""

from __future__ import annotations

from unittest.mock import MagicMock

from apps.research_screener import __main__ as screener_main
from apps.research_screener.live_providers import ProviderBundle


def test_refresh_all_ensures_symbols_when_screener_fails() -> None:
    finviz = MagicMock()
    finviz.configured = True
    finviz.fetch_screener.return_value = {
        "success": False,
        "error": "FINVIZ_EXPORT_EMPTY",
        "rows": 0,
    }
    finviz.ensure_symbols.return_value = {
        "requested": 2,
        "missing_before": 2,
        "fetched": 2,
        "errors": [],
    }
    finviz.get_row.return_value = MagicMock(
        float_shares=10_000_000.0,
        short_float_pct=18.5,
        short_ratio=2.1,
        rel_volume=3.2,
        shares_outstanding=None,
    )
    finviz.status.return_value = {"mapping_conflict_symbols": []}
    finviz.get_cached_rows.return_value = []

    bundle = ProviderBundle(finviz=finviz)
    result = bundle.refresh_all(["GME", "AVTX"])

    finviz.ensure_symbols.assert_called_once_with(["GME", "AVTX"])
    assert result["providers"]["finviz"]["screener_success"] is False
    assert result["providers"]["finviz"]["success"] is True
    assert bundle._finviz_enrichment["matched_candidates"] == 2


def test_bootstrap_ensures_finviz_for_cloud_bootstrap_symbols(monkeypatch) -> None:
    monkeypatch.setenv("CLOUD_BOOTSTRAP_SYMBOLS", "GME,BIYA")
    session = MagicMock()
    session.states = {}
    session.add_manual_symbols.return_value = ["GME", "BIYA"]
    session.external_providers = MagicMock()
    session.external_providers.finviz.configured = True
    session.external_providers.ensure_finviz_for_symbols.return_value = {
        "requested": 2,
        "missing_before": 2,
        "fetched": 2,
        "errors": [],
    }

    screener_main._bootstrap_live_data(session)

    session.external_providers.ensure_finviz_for_symbols.assert_called_once_with(
        ["GME", "BIYA"]
    )
