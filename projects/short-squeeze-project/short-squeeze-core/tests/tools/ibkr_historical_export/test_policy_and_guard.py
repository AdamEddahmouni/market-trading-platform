"""Connection policy and the forbidden-method static guard."""

from __future__ import annotations

import pytest

from tools.ibkr_historical_export import guard, policy


def test_localhost_only_host():
    assert policy.HOST == "127.0.0.1"


def test_assert_localhost_rejects_remote():
    policy.assert_localhost("127.0.0.1")
    policy.assert_localhost("localhost")
    with pytest.raises(ValueError):
        policy.assert_localhost("10.0.0.5")
    with pytest.raises(ValueError):
        policy.assert_localhost("example.com")


def test_port_probe_order():
    assert policy.PORT_PROBE_ORDER == (4002, 4001, 4004, 4003)


def test_client_id_sequence():
    assert policy.CLIENT_ID_PRIMARY == 27185
    assert policy.CLIENT_ID_SEQUENCE == (27185, 27186, 27187, 27188)
    assert 0 not in policy.CLIENT_ID_SEQUENCE


def test_pacing_and_timeouts():
    assert policy.INTER_REQUEST_DELAY_S >= 2
    assert policy.IDENTICAL_REQUEST_MIN_INTERVAL_S >= 15
    assert policy.MAX_TRANSIENT_RETRIES == 1
    assert policy.RETRY_BACKOFF_S >= 20
    assert policy.CONNECTION_TIMEOUT_S == 15
    assert policy.CONTRACT_DETAILS_TIMEOUT_S == 30
    assert policy.HISTORICAL_TIMEOUT_S == 60


def test_guard_scan_is_clean():
    violations = guard.scan_source_for_forbidden(guard.package_dir())
    assert violations == [], violations


def test_forbidden_methods_cover_handoff_list():
    required = {
        "placeOrder", "cancelOrder", "reqOpenOrders", "reqAllOpenOrders",
        "reqAutoOpenOrders", "reqPositions", "reqPositionsMulti", "reqAccountSummary",
        "reqAccountUpdates", "reqAccountUpdatesMulti", "reqExecutions",
        "reqCompletedOrders", "reqPnL", "reqPnLSingle", "reqMarketDataType",
        "reqMktData", "reqRealTimeBars", "reqScannerSubscription",
    }
    assert required <= guard.FORBIDDEN_API_METHODS


def test_allowed_and_forbidden_are_disjoint():
    assert guard.ALLOWED_API_METHODS & guard.FORBIDDEN_API_METHODS == set()


def test_guard_detects_injected_violation(tmp_path):
    # A synthetic module that references a forbidden method must be caught.
    pkg = tmp_path / "fakepkg"
    pkg.mkdir()
    (pkg / "bad.py").write_text("def go(client):\n    client.placeOrder(1, None, None)\n", encoding="utf-8")
    violations = guard.scan_source_for_forbidden(pkg)
    assert any("placeOrder" in v for v in violations)
