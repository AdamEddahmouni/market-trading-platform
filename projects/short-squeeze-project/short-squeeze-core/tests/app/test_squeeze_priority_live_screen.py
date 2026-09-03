"""Live 50-ticker screen: squeeze priority discovery trim and refresh scheduling."""

from __future__ import annotations

from apps.research_screener import session_state
from apps.research_screener.finviz_live import FinvizRow
from apps.research_screener.live_providers import ProviderBundle
from apps.research_screener.squeeze_priority import (
    rank_symbols_for_refresh,
    score_discovery_symbol,
)

from .synthetic_provider import FakeFinvizProvider, FakeNewsProvider, SyntheticProvider


def _filled(
    ticker: str,
    *,
    short_float_pct: float = 20.0,
    float_shares: float = 5_000_000,
    rel_volume: float = 2.0,
) -> FinvizRow:
    return FinvizRow(
        ticker=ticker,
        company=f"{ticker} Co",
        short_float_pct=short_float_pct,
        float_shares=float_shares,
        rel_volume=rel_volume,
        price=5.0,
        change_pct=10.0,
    )


def test_discovery_union_trims_to_cap_prefers_squeeze_finviz(monkeypatch):
    monkeypatch.setattr(session_state, "CURRENT_SCREEN_CAP", 3)
    monkeypatch.setattr(session_state, "FINVIZ_TOP_N", 10)

    session = session_state.ScreenerSession(
        provider=SyntheticProvider(symbols=("LOW1", "LOW2", "LOW3")),
        external_providers=ProviderBundle(
            finviz=FakeFinvizProvider({
                "LOW1": _filled("LOW1", short_float_pct=5.0),
                "HIGH": _filled("HIGH", short_float_pct=85.0),
                "MID": _filled("MID", short_float_pct=55.0),
            }),
            news=FakeNewsProvider(),
        ),
    )
    session.refresh_discovery("BROAD_MOVERS")
    assert set(session.states) == {"HIGH", "MID", "LOW1"}


def test_compute_symbols_per_cycle_respects_pacing_budget(monkeypatch):
    monkeypatch.setattr(session_state, "SYMBOLS_PER_CYCLE_MAX", 6)
    provider = SyntheticProvider(symbols=tuple(f"S{i}" for i in range(20)), budget=12)
    session = session_state.ScreenerSession(
        provider=provider,
        symbols_per_cycle=3,
        quote_refresh_s=15,
        external_providers=ProviderBundle(
            finviz=FakeFinvizProvider(), news=FakeNewsProvider(),
        ),
    )
    session.refresh_discovery("BROAD_MOVERS")
    take = session.compute_symbols_per_cycle()
    assert 1 <= take <= 6
    assert take <= 12


def test_refresh_all_prefers_stale_high_discovery_before_fresh_low(monkeypatch):
    monkeypatch.setattr(session_state, "SYMBOLS_PER_CYCLE_MAX", 1)
    from apps.research_screener import discovery as discovery_module

    provider = SyntheticProvider(symbols=("AAA", "BBB"), budget=10)
    session = session_state.ScreenerSession(
        provider=provider,
        symbols_per_cycle=1,
        external_providers=ProviderBundle(
            finviz=FakeFinvizProvider({
                "AAA": _filled("AAA", short_float_pct=10.0),
                "BBB": _filled("BBB", short_float_pct=90.0),
            }),
            news=FakeNewsProvider(),
        ),
    )
    session.refresh_discovery("BROAD_MOVERS")
    session.states["AAA"].discovery_score = 10.0
    session.states["BBB"].discovery_score = 500.0
    session.states["BBB"].stale = True

    result = session.refresh_all()
    assert result["symbols"] == ["BBB"]


def test_readiness_candidate_count_up_to_cap(monkeypatch):
    monkeypatch.setattr(session_state, "CURRENT_SCREEN_CAP", 50)
    symbols = tuple(f"T{i:02d}" for i in range(55))
    provider = SyntheticProvider(symbols=symbols)
    finviz = {sym: _filled(sym, short_float_pct=30.0 + i) for i, sym in enumerate(symbols)}
    session = session_state.ScreenerSession(
        provider=provider,
        external_providers=ProviderBundle(
            finviz=FakeFinvizProvider(finviz), news=FakeNewsProvider(),
        ),
    )
    session.refresh_discovery("BROAD_MOVERS")
    assert len(session.states) <= 50
    summary = session.summary()
    assert summary["readiness"]["candidate_count"] == len(session.states)
    assert summary["readiness"]["candidate_count"] <= 50


def test_score_discovery_symbol_ibkr_rank_bonus():
    row = _filled("X", short_float_pct=20.0)
    low_rank = score_discovery_symbol("X", row, ibkr_rank=1)
    high_rank = score_discovery_symbol("X", row, ibkr_rank=50)
    assert low_rank > high_rank


def test_rank_symbols_for_refresh_ordering():
    from apps.research_screener import discovery as discovery_module

    states = {
        "A": session_state.CandidateState(
            candidate=discovery_module.CurrentDiscoveryCandidate(symbol="A", profile_id="X"),
            discovery_score=1.0,
        ),
        "B": session_state.CandidateState(
            candidate=discovery_module.CurrentDiscoveryCandidate(symbol="B", profile_id="X"),
            discovery_score=100.0,
            stale=True,
        ),
    }
    order = rank_symbols_for_refresh(states)
    assert order[0] == "B"
