"""Batch 11 — read-only guards, isolation, export and startup resilience.

These are the tests that must fail loudly if the application ever gains the ability to
trade, to reach account state, to mutate a research artifact, or to start depending on a
live provider for its frozen demo.
"""

from __future__ import annotations

import json
import threading
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import pytest

from apps.research_screener import export as export_module
from apps.research_screener import guard, session_state, snapshot as snapshot_module
from apps.research_screener.server import build_server, find_free_port

from .synthetic_provider import SyntheticProvider

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_DIR = REPO_ROOT / "apps" / "research_screener"


# ------------------------------------------------------------------- guards


def test_application_source_contains_no_order_or_account_method():
    assert guard.scan_source_for_forbidden(APP_DIR) == []


def test_application_interface_offers_no_trading_action():
    assert guard.scan_ui_for_trading_actions(APP_DIR) == []


def test_guard_verify_is_clean():
    assert guard.verify() == []


def test_forbidden_set_covers_every_method_named_in_the_brief():
    required = {
        "placeOrder", "cancelOrder", "reqOpenOrders", "reqAllOpenOrders",
        "reqAutoOpenOrders", "reqPositions", "reqAccountSummary", "reqAccountUpdates",
        "reqExecutions", "reqPnL", "reqPnLSingle", "reqCompletedOrders",
    }
    assert required <= guard.FORBIDDEN_API_METHODS


def test_scanner_and_market_data_are_allowed_only_in_the_application():
    from tools.ibkr_historical_export import guard as research_guard

    scanner_surface = {
        "reqScannerParameters", "reqScannerSubscription", "cancelScannerSubscription",
        "reqMktData", "cancelMktData", "reqMarketDataType",
    }
    # Permitted here...
    assert scanner_surface <= guard.ALLOWED_API_METHODS
    # ...while the Batch 05 research exporter still forbids the requesting half of that
    # surface. It never names the cancel calls, because it can never open one.
    requesting_surface = {
        "reqScannerParameters", "reqScannerSubscription", "reqMktData", "reqMarketDataType",
    }
    assert requesting_surface <= research_guard.FORBIDDEN_API_METHODS
    assert requesting_surface.isdisjoint(research_guard.ALLOWED_API_METHODS)
    assert research_guard.scan_source_for_forbidden(
        REPO_ROOT / "tools" / "ibkr_historical_export"
    ) == []


def test_guard_detects_an_injected_violation(tmp_path):
    (tmp_path / "bad.py").write_text("session.reqPositions()\n", encoding="utf-8")
    violations = guard.scan_source_for_forbidden(tmp_path)
    assert any("reqPositions" in item for item in violations)


def test_guard_detects_an_injected_trading_control(tmp_path):
    (tmp_path / "bad.html").write_text(
        "<button class='x'>Buy</button>", encoding="utf-8"
    )
    assert guard.scan_ui_for_trading_actions(tmp_path)


def test_guard_does_not_flag_prose_mentioning_trading():
    """The footer says there is no buy/sell action. That sentence is not a control."""
    text = (APP_DIR / "static" / "index.html").read_text(encoding="utf-8").lower()
    assert "no orders" in text
    assert "no trading action" in text
    assert guard.scan_ui_for_trading_actions(APP_DIR) == []


# ----------------------------------------------------------------- isolation


def test_current_mode_writes_no_research_artifact(tmp_path):
    """A full current-screen cycle must not touch any tracked artifact."""
    tracked = sorted(
        path for path in (REPO_ROOT / "src" / "squeeze_core").rglob("*.json")
        if "__pycache__" not in path.parts
    )
    before = {path: path.stat().st_mtime_ns for path in tracked}

    session = session_state.ScreenerSession(
        provider=SyntheticProvider(), symbols_per_cycle=10
    )
    session.refresh_discovery("BROAD_MOVERS")
    session.refresh_all()
    session.detail("AAA")
    session.summary()

    assert {path: path.stat().st_mtime_ns for path in tracked} == before


def test_current_session_state_is_ephemeral():
    first = session_state.reset_session(
        session_state.ScreenerSession(provider=SyntheticProvider())
    )
    first.refresh_discovery("BROAD_MOVERS")
    assert first.states
    second = session_state.reset_session(
        session_state.ScreenerSession(provider=SyntheticProvider())
    )
    assert second.states == {}
    session_state.reset_session()


def test_frozen_mode_never_uses_the_current_session():
    """Frozen rows must be identical whether or not a current screen exists."""
    session_state.reset_session(session_state.ScreenerSession(provider=SyntheticProvider()))
    baseline = snapshot_module.frozen_snapshot()

    session = session_state.get_session()
    session.refresh_discovery("BROAD_MOVERS")
    session.refresh_all()

    after = snapshot_module.frozen_snapshot()
    assert [row["symbol"] for row in after["rows"]] == [row["symbol"] for row in baseline["rows"]]
    assert [row["phase3a"]["counts"] for row in after["rows"]] == [
        row["phase3a"]["counts"] for row in baseline["rows"]
    ]
    session_state.reset_session()


def test_frozen_totals_are_unchanged_by_batch_11():
    summary = snapshot_module.frozen_snapshot()
    rows = summary["rows"]
    assert len(rows) == 13
    totals = {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}
    for row in rows:
        for key in totals:
            totals[key] += row["phase3a"]["counts"][key]
    assert totals == {"PASS": 97, "FAIL": 20, "UNKNOWN": 208}


def test_private_frozen_snapshot_exposes_integration_acceptance_summary():
    snapshot = snapshot_module.frozen_snapshot()

    assert snapshot["outcome_totals"] == {
        "PASS": 97,
        "FAIL": 20,
        "UNKNOWN": 208,
    }
    assert snapshot["phase3e_started"] is False


def test_professor_panels_are_reported_separately():
    session_state.reset_session(session_state.ScreenerSession(provider=SyntheticProvider()))
    session = session_state.get_session()
    session.refresh_discovery("BROAD_MOVERS")
    session.refresh_all()

    payload = snapshot_module.professor_summary()
    historical = payload["historical_research"]
    current = payload["current_operational_screen"]
    assert historical["case_count"] == 13
    assert historical["outcome_totals"] == {"PASS": 97, "FAIL": 20, "UNKNOWN": 208}
    assert current["candidate_count"] == 3
    # The two are never summed anywhere in the payload.
    assert historical["case_count"] + current["candidate_count"] != historical["case_count"]
    assert "never summed" in payload["separation_note"]
    session_state.reset_session()


# -------------------------------------------------------------------- export


def test_current_export_carries_missingness_and_no_credentials(tmp_path):
    session = session_state.reset_session(
        session_state.ScreenerSession(provider=SyntheticProvider())
    )
    session.refresh_discovery("BROAD_MOVERS")
    session.refresh_all()

    payload = snapshot_module.current_snapshot()
    details = {row["symbol"]: snapshot_module.current_detail(row["symbol"])
               for row in payload["rows"]}
    written = export_module.write_export(payload, tmp_path, details=details)

    document = json.loads(Path(written["json"]).read_text(encoding="utf-8"))
    assert document["row_count"] == 3
    assert document["export_kind"] == "RESEARCH_SNAPSHOT"

    csv_text = Path(written["csv"]).read_text(encoding="utf-8")
    header, *lines = [line for line in csv_text.splitlines() if line.strip()]
    assert "discovery_profile" in header and "market_data_mode" in header
    # A missing field exports as an empty cell, never as 0.
    for line in lines:
        cells = line.split(",")
        assert "0" not in {cells[header.split(",").index("float_shares")]}
    session_state.reset_session()


def test_export_refuses_a_credential_shaped_key(tmp_path):
    with pytest.raises(export_module.CredentialInExportError):
        export_module.write_export(
            {"header": {"mode": "CURRENT"}, "rows": [], "row_count": 0},
            tmp_path,
            details={"AAA": {"api_key": "nope"}},
        )


# ------------------------------------------------------------------- server


@pytest.fixture
def server():
    session_state.reset_session(session_state.ScreenerSession(provider=SyntheticProvider()))
    port = find_free_port(8850)
    instance = build_server(port)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    instance.shutdown()
    session_state.reset_session()


def _get(base: str, path: str):
    with urllib.request.urlopen(base + path, timeout=60) as response:
        return json.loads(response.read())


def _post(base: str, path: str):
    request = urllib.request.Request(base + path, method="POST")
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read())


def test_startup_serves_frozen_mode_with_no_provider(server):
    payload = _get(server, "/api/frozen/candidates")
    assert payload["row_count"] == 13


def test_demo_ready_does_not_depend_on_a_live_provider(server):
    readiness = _get(server, "/api/readiness")
    assert readiness["demo_ready"] is True
    assert "Provider downtime cannot affect it" in readiness["demo_note"]
    assert isinstance(readiness["live_sources_ready"], bool)


def test_live_endpoints_round_trip(server):
    assert _get(server, "/api/live/candidates")["row_count"] == 0
    discovered = _post(server, "/api/discovery/refresh?profile=BROAD_MOVERS")
    assert discovered["discovered"] == 3
    _post(server, "/api/live/refresh")
    listing = _get(server, "/api/live/candidates")
    assert listing["row_count"] == 3
    detail = _get(server, "/api/live/candidate?symbol=AAA")
    assert len(detail["rules"]) == 25


def test_refresh_all_available_evidence_sweeps_every_tracked_candidate():
    provider = SyntheticProvider(symbols=("AAA", "BBB", "CCC", "DDD", "EEE"))
    session_state.reset_session(
        session_state.ScreenerSession(provider=provider, symbols_per_cycle=2)
    )
    port = find_free_port(8860)
    instance = build_server(port)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{port}"
        _post(base, "/api/discovery/refresh?profile=BROAD_MOVERS")
        refreshed = _post(base, "/api/refresh/all")
        assert refreshed["accepted"] is True
        assert refreshed["total"] == 5
        # Refresh is now asynchronous (202 Accepted); the background thread
        # may still be running. Verify sweep was accepted for all symbols.
        import time
        deadline = time.time() + 5
        while time.time() < deadline:
            if len(provider.collect_calls) >= 5:
                break
            time.sleep(0.1)
        assert set(provider.collect_calls) == {"AAA", "BBB", "CCC", "DDD", "EEE"}
    finally:
        instance.shutdown()
        session_state.reset_session()


def test_discovery_profiles_endpoint(server):
    payload = _get(server, "/api/discovery/profiles")
    assert len(payload["profiles"]) == 5  # +FINVIZ_SCREENER
    assert payload["selected"] in {p["profile_id"] for p in payload["profiles"]}


def test_sorting_puts_missing_values_last(server):
    _post(server, "/api/discovery/refresh?profile=BROAD_MOVERS")
    _post(server, "/api/live/refresh")
    for descending in ("false", "true"):
        rows = _get(
            server, f"/api/live/candidates?sort=relative_volume&desc={descending}"
        )["rows"]
        # Relative volume is UNKNOWN for every current row, so nothing may claim a value.
        assert all(row["fields"]["relative_volume"]["value"] is None for row in rows)


def test_numeric_filter_excludes_rows_with_no_value(server):
    _post(server, "/api/discovery/refresh?profile=BROAD_MOVERS")
    _post(server, "/api/live/refresh")
    rows = _get(server, "/api/live/candidates?min_relvol=1")["rows"]
    # Missing is not silently treated as satisfying (or as zero); the rows drop out.
    assert rows == []


def test_a_provider_outage_does_not_break_the_server():
    session = session_state.reset_session(
        session_state.ScreenerSession(provider=SyntheticProvider(collect_fails=True))
    )
    port = find_free_port(8870)
    instance = build_server(port)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{port}"
        _post(base, "/api/discovery/refresh?profile=BROAD_MOVERS")
        _post(base, "/api/live/refresh")
        assert _get(base, "/api/live/candidates")["row_count"] == 3
        assert _get(base, "/api/frozen/candidates")["row_count"] == 13
        assert _get(base, "/api/readiness")["demo_ready"] is True
    finally:
        instance.shutdown()
        session_state.reset_session()


def test_no_trading_route_exists(server):
    for path in ("/api/order", "/api/positions", "/api/account", "/api/trade"):
        with pytest.raises(Exception):
            _post(server, path)
