"""Quality candidate selection: Finviz ranking, screen cap, and discovery merge."""

from __future__ import annotations

from apps.research_screener import session_state
from apps.research_screener.finviz_live import (
    FinvizRow,
    finviz_rank_key,
    finviz_row_completeness,
    finviz_row_is_usable,
    select_ranked_finviz_top_n,
)
from apps.research_screener.live_providers import ProviderBundle

from .synthetic_provider import FakeFinvizProvider, FakeNewsProvider, SyntheticProvider


def _filled(
    ticker: str,
    *,
    short_float_pct: float = 20.0,
    float_shares: float = 5_000_000,
    rel_volume: float = 2.0,
    price: float = 5.0,
    change_pct: float = 10.0,
) -> FinvizRow:
    return FinvizRow(
        ticker=ticker,
        company=f"{ticker} Co",
        short_float_pct=short_float_pct,
        float_shares=float_shares,
        rel_volume=rel_volume,
        price=price,
        change_pct=change_pct,
    )


def test_finviz_ranking_skips_sparse_and_prefers_high_short_float():
    sparse = FinvizRow(ticker="SPARSE", price=9.0, change_pct=50.0)
    low = _filled("LOW", short_float_pct=5.0, rel_volume=10.0, change_pct=40.0)
    mid = _filled("MID", short_float_pct=25.0, rel_volume=1.5, change_pct=5.0)
    high = _filled("HIGH", short_float_pct=40.0, rel_volume=3.0, change_pct=8.0)
    incomplete_core = FinvizRow(
        ticker="HALF", short_float_pct=99.0, float_shares=1_000_000, price=3.0,
    )  # missing rel_volume

    assert not finviz_row_is_usable(sparse)
    assert not finviz_row_is_usable(incomplete_core)
    assert finviz_row_is_usable(high)
    assert finviz_row_completeness(high) == 5

    ranked = select_ranked_finviz_top_n(
        [sparse, low, mid, high, incomplete_core], limit=10,
    )
    assert [row.ticker for row in ranked] == ["HIGH", "MID", "LOW"]
    assert finviz_rank_key(high) < finviz_rank_key(mid) < finviz_rank_key(low)


def test_finviz_ranking_uses_rel_volume_then_change_as_tiebreakers():
    a = _filled("A", short_float_pct=30.0, rel_volume=5.0, change_pct=1.0)
    b = _filled("B", short_float_pct=30.0, rel_volume=8.0, change_pct=1.0)
    c = _filled("C", short_float_pct=30.0, rel_volume=8.0, change_pct=-20.0)
    ranked = select_ranked_finviz_top_n([a, b, c], limit=3)
    assert [row.ticker for row in ranked] == ["C", "B", "A"]


def test_finviz_top_n_excludes_ibkr_symbols():
    rows = [_filled("AAA", short_float_pct=50.0), _filled("ZZZ", short_float_pct=10.0)]
    ranked = select_ranked_finviz_top_n(rows, exclude={"AAA"}, limit=5)
    assert [row.ticker for row in ranked] == ["ZZZ"]


def test_refresh_discovery_caps_and_merges_ranked_finviz_only(monkeypatch):
    monkeypatch.setattr(session_state, "CURRENT_SCREEN_CAP", 5)
    monkeypatch.setattr(session_state, "FINVIZ_TOP_N", 10)

    ibkr = ("IB1", "IB2")
    finviz_rows = {
        "IB1": _filled("IB1", short_float_pct=99.0),  # already in IBKR — not added again
        "F1": _filled("F1", short_float_pct=40.0, rel_volume=4.0),
        "F2": _filled("F2", short_float_pct=30.0, rel_volume=3.0),
        "F3": _filled("F3", short_float_pct=20.0, rel_volume=2.0),
        "F4": _filled("F4", short_float_pct=10.0, rel_volume=1.0),
        "SPARSE": FinvizRow(ticker="SPARSE", price=1.0, change_pct=90.0),
    }
    # Flood the fake cache with many more sparse/low rows to mimic a large export.
    for index in range(50):
        finviz_rows[f"X{index:02d}"] = FinvizRow(
            ticker=f"X{index:02d}", price=float(index), change_pct=float(index),
        )

    session = session_state.ScreenerSession(
        provider=SyntheticProvider(symbols=ibkr),
        symbols_per_cycle=10,
        external_providers=ProviderBundle(
            finviz=FakeFinvizProvider(finviz_rows),
            news=FakeNewsProvider(),
        ),
    )
    result = session.refresh_discovery("BROAD_MOVERS")

    assert result["error"] is None
    assert result["cap"] == 5
    assert result["discovered"] == 5
    assert len(session.states) == 5
    assert "IB1" in session.states
    assert {"F1", "F2", "F3"}.issubset(session.states)
    assert "IB2" not in session.states
    assert "SPARSE" not in session.states
    assert all(f"X{i:02d}" not in session.states for i in range(50))
    assert session.states["F1"].candidate.profile_id == "FINVIZ_SCREENER"


def test_refresh_discovery_prunes_prior_finviz_flood(monkeypatch):
    monkeypatch.setattr(session_state, "CURRENT_SCREEN_CAP", 4)
    monkeypatch.setattr(session_state, "FINVIZ_TOP_N", 2)

    session = session_state.ScreenerSession(
        provider=SyntheticProvider(symbols=("AAA",)),
        symbols_per_cycle=10,
        external_providers=ProviderBundle(
            finviz=FakeFinvizProvider({
                "F1": _filled("F1", short_float_pct=40.0),
                "F2": _filled("F2", short_float_pct=30.0),
                "OLD": _filled("OLD", short_float_pct=5.0),
            }),
            news=FakeNewsProvider(),
        ),
    )
    # Simulate a prior flood still sitting in session state.
    from apps.research_screener import discovery as discovery_module

    for ticker in ("OLD", "FLOOD1", "FLOOD2", "FLOOD3"):
        session.states[ticker] = session_state.CandidateState(
            candidate=discovery_module.CurrentDiscoveryCandidate(
                symbol=ticker, profile_id="FINVIZ_SCREENER",
            )
        )
    assert len(session.states) == 4

    result = session.refresh_discovery("BROAD_MOVERS")
    assert result["discovered"] == 3  # AAA + F1 + F2
    assert set(session.states) == {"AAA", "F1", "F2"}
    assert "OLD" not in session.states
    assert "FLOOD1" not in session.states


def test_ibkr_priority_when_cap_smaller_than_ibkr_plus_finviz(monkeypatch):
    """High short-float Finviz names can displace low-squeeze IBKR fillers."""
    monkeypatch.setattr(session_state, "CURRENT_SCREEN_CAP", 3)
    monkeypatch.setattr(session_state, "FINVIZ_TOP_N", 15)

    session = session_state.ScreenerSession(
        provider=SyntheticProvider(symbols=("A", "B", "C")),
        symbols_per_cycle=10,
        external_providers=ProviderBundle(
            finviz=FakeFinvizProvider({
                "Z1": _filled("Z1", short_float_pct=90.0),
                "Z2": _filled("Z2", short_float_pct=80.0),
            }),
            news=FakeNewsProvider(),
        ),
    )
    result = session.refresh_discovery("BROAD_MOVERS")
    assert result["discovered"] == 3
    assert set(session.states) == {"A", "Z1", "Z2"}
