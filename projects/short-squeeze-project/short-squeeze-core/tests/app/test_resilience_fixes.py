"""Focused tests for Part 2 resilience fixes (bootstrap order, IBKR error arity, supervisor)."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from apps.research_screener import __main__ as screener_main
from apps.research_screener import session_state
from apps.research_screener.ibkr_session import QuoteTicks, build_session_class


# ------------------------------------------------------------------ bootstrap


def test_bootstrap_order_is_discovery_then_refresh_then_auto_refresh(monkeypatch):
    """Warm refresh must finish before start_auto_refresh (no overlap with _loop)."""
    monkeypatch.setenv("BOOTSTRAP_WARM_CYCLES", "1")
    monkeypatch.setattr(
        "apps.research_screener.collector_session.start_collectors_for_session",
        lambda *args, **kwargs: None,
    )
    order: list[str] = []
    session = MagicMock()
    session.states = {"AAA": object(), "BBB": object()}
    session.refresh_discovery.side_effect = lambda: (
        order.append("discovery"),
        {"discovered": 2, "ibkr": 2, "finviz": 0},
    )[-1]
    session.note_discovery_scan.side_effect = lambda: order.append("note_scan")
    session.refresh_all.side_effect = lambda **kwargs: (
        order.append(f"refresh_all:{kwargs.get('limit')}"),
        {"refreshed": 2},
    )[-1]
    session.start_auto_refresh.side_effect = lambda: order.append("start_auto_refresh")

    screener_main._bootstrap_live_data(session)

    assert order == [
        "discovery",
        "note_scan",
        "refresh_all:None",
        "start_auto_refresh",
    ]
    session.refresh_all.assert_called_once_with()


def test_bootstrap_still_starts_auto_refresh_when_discovery_fails(monkeypatch):
    monkeypatch.setattr(
        "apps.research_screener.collector_session.start_collectors_for_session",
        lambda *args, **kwargs: None,
    )
    order: list[str] = []
    session = MagicMock()
    session.states = {}
    session.refresh_discovery.side_effect = RuntimeError("scanner down")
    session.start_auto_refresh.side_effect = lambda: order.append("start_auto_refresh")
    session.refresh_all.side_effect = lambda **kwargs: order.append("refresh_all")

    screener_main._bootstrap_live_data(session)

    assert "start_auto_refresh" in order
    session.note_discovery_scan.assert_not_called()


def test_note_discovery_scan_seeds_last_scan_for_loop():
    session = session_state.ScreenerSession(
        provider=MagicMock(), symbols_per_cycle=2
    )
    assert session._last_scan_ts == 0.0
    session.note_discovery_scan(when=1_700_000_000.0)
    assert session._last_scan_ts == 1_700_000_000.0


# ------------------------------------------------------------------ IBKR error arity


@pytest.fixture(scope="module")
def app_session_cls():
    return build_session_class()


def test_error_old_positional_arity_records_code_and_message(app_session_cls):
    session = app_session_cls()
    session._ticks[12] = QuoteTicks(symbol="AAA", con_id=1)
    done = threading.Event()
    session._tick_done[12] = done

    # Old decoder: (reqId, errorCode, errorString, advancedOrderRejectJson)
    session.error(12, 354, "Requested market data is not subscribed", "")

    assert done.is_set()
    assert session._ticks[12].errors == [
        {"code": 354, "message": "Requested market data is not subscribed"}
    ]


def test_error_new_positional_arity_with_error_time(app_session_cls):
    session = app_session_cls()
    session._ticks[7] = QuoteTicks(symbol="BBB", con_id=2)
    done = threading.Event()
    session._tick_done[7] = done

    # New decoder: (reqId, errorTime, errorCode, errorString, advancedOrderRejectJson)
    session.error(7, 1_700_000_000, 200, "No security definition", "")

    assert done.is_set()
    assert session._ticks[7].errors == [
        {"code": 200, "message": "No security definition"}
    ]


def test_error_super_typeerror_falls_back_to_old_signature(app_session_cls, monkeypatch):
    session = app_session_cls()
    calls: list[tuple] = []

    def flaky_super(self, *args):
        calls.append(args)
        if len(args) >= 5:
            raise TypeError("old EWrapper.error takes 3 args")
        if len(args) == 4:
            raise TypeError("old EWrapper.error takes 3 args")
        # 3-arg form succeeds

    monkeypatch.setattr(
        type(session).__mro__[1],
        "error",
        flaky_super,
    )

    session.error(9, 354, "not subscribed", "")

    assert calls[0] == (9, 0, 354, "not subscribed", "")
    assert calls[-1] == (9, 354, "not subscribed")


# ------------------------------------------------------------------ supervisor


def test_supervised_script_forces_no_browser_on_restart():
    text = Path(__file__).resolve().parents[2].joinpath("run_supervised.ps1").read_text(
        encoding="utf-8"
    )
    assert "$attempt -ge 2" in text
    assert "--no-browser" in text
    assert "Crash restarts must not reopen" in text or "must not reopen tabs" in text
