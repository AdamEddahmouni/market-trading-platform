from __future__ import annotations

from unittest.mock import patch

from apps.research_screener.finviz_live import FinvizClient


CSV = """Ticker,Company,Change,Relative Volume,Short Float,Short Ratio,Shares Float
AAA,Alpha Co,12.5,3.2,18.5,2.1,10M
"""


def test_fetch_symbol_uses_ticker_filter_and_caches_row():
    client = FinvizClient("test-key")
    with patch("apps.research_screener.finviz_live.requests.get") as get:
        get.return_value.status_code = 200
        get.return_value.text = CSV
        result = client.fetch_symbol("AAA")
        assert result["success"] is True
        assert result["symbol"] == "AAA"
        row = client.get_row("AAA")
        assert row is not None
        assert row.short_float_pct == 18.5
        assert row.rel_volume == 3.2
        params = get.call_args.kwargs["params"]
        assert params["f"] == "t=AAA"


def test_ensure_symbols_fetches_missing_only():
    client = FinvizClient("test-key")
    with patch("apps.research_screener.finviz_live.requests.get") as get:
        get.return_value.status_code = 200
        get.return_value.text = CSV
        summary = client.ensure_symbols(["AAA", "BBB"])
        assert summary["fetched"] == 2
        assert client.get_row("AAA") is not None
