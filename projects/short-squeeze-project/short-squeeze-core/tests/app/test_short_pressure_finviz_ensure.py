"""short_pressure_fields uses per-symbol Finviz export when screener cache misses."""

from __future__ import annotations

from unittest.mock import MagicMock

from apps.research_screener.finviz_live import FinvizRow
from apps.research_screener.live_providers import ProviderBundle
from apps.research_screener.session_state import CandidateState, short_pressure_fields
from apps.research_screener.truth import ValueStatus


def test_short_pressure_fields_fetches_missing_finviz_symbol():
    row = FinvizRow(
        ticker="GME",
        float_shares=50_000_000.0,
        short_float_pct=18.5,
        short_ratio=2.1,
    )
    finviz = MagicMock()
    finviz.configured = True
    finviz.cached_at = "2026-08-17T21:00:00Z"
    finviz.get_row.side_effect = [None, row]
    finviz.ensure_symbols.return_value = {"fetched": 1, "missing_before": 1}

    bundle = ProviderBundle(finviz=finviz)
    candidate = MagicMock()
    candidate.symbol = "GME"
    state = CandidateState(candidate=candidate)

    fields = short_pressure_fields(state, bundle)

    finviz.ensure_symbols.assert_called_once_with(["GME"])
    assert fields["published_short_interest"].status == ValueStatus.KNOWN
    assert fields["published_short_interest"].value == 18.5
    assert fields["float_shares"].status == ValueStatus.KNOWN
    assert fields["days_to_cover"].status == ValueStatus.KNOWN
