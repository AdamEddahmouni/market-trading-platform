from __future__ import annotations

import json
import threading
from urllib.request import Request, urlopen

import pytest

from apps.research_screener.deployment import DeploymentMode, resolve_runtime
from apps.research_screener.frozen_demo import load_frozen_demo
from apps.research_screener.server import build_server, find_free_port
from apps.research_screener.trend import trend


def test_deployment_modes_enforce_binding_and_port(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    local = resolve_runtime(DeploymentMode.LOCAL_FULL)
    assert (local.host, local.port, local.load_private, local.enable_local_ibkr) == (
        "127.0.0.1", 8787, True, True,
    )
    monkeypatch.setenv("PORT", "9341")
    cloud = resolve_runtime(DeploymentMode.CLOUD_PROVIDER_MODE)
    assert (cloud.host, cloud.port, cloud.load_private, cloud.enable_local_ibkr) == (
        "0.0.0.0", 9341, False, False,
    )
    with pytest.raises(ValueError):
        build_server(0, host="0.0.0.0", deployment_mode=DeploymentMode.LOCAL_FULL)


def test_cloud_preflight_uses_demo_and_does_not_probe_or_print_private_path(capsys):
    from apps.research_screener.__main__ import main

    assert main(["--mode", "FROZEN_DEMO", "--check"]) == 0
    output = capsys.readouterr().out
    assert "sanitized frozen demo" in output
    assert "not probed" in output
    assert ".private" not in output
    assert "C:\\Users" not in output


def test_cloud_provider_configuration_reads_named_environment_only(monkeypatch):
    from apps.research_screener.live_providers import configure_environment, reset_runtime

    monkeypatch.setenv("FINVIZ_API_KEY", "synthetic-finviz")
    monkeypatch.setenv("NEWSAPI_KEY", "synthetic-news")
    monkeypatch.setenv("FINNHUB_KEY", "synthetic-finnhub")
    runtime = configure_environment()
    try:
        assert runtime.finviz.configured
        assert runtime.news.configured
        assert runtime.finnhub.configured
        assert runtime.credentials.path is None
        assert set(runtime.credentials.values) == {
            "FINVIZ_API_KEY", "NEWSAPI_KEY", "FINNHUB_KEY",
        }
    finally:
        reset_runtime()


def test_cloud_ibkr_enabled_from_environment(monkeypatch):
    from apps.research_screener.config import resolve_application_config

    monkeypatch.setenv("IBKR_ENABLED", "true")
    monkeypatch.setenv("IBKR_HOST", "ib-gateway.example.invalid")
    monkeypatch.setenv("IBKR_PORT", "4002")
    monkeypatch.setenv("IBKR_CLIENT_ID", "27201")
    config = resolve_application_config(
        cli={"SQUEEZE_APP_MODE": "CLOUD_PROVIDER_MODE"},
    )
    assert config.providers.ibkr.enabled is True
    assert config.providers.ibkr.host == "ib-gateway.example.invalid"
    assert config.providers.ibkr.port == 4002
    assert config.providers.ibkr.client_id == 27201


def test_cloud_ibkr_defaults_disabled_without_explicit_env(monkeypatch):
    from apps.research_screener.config import resolve_application_config

    monkeypatch.delenv("IBKR_ENABLED", raising=False)
    config = resolve_application_config(
        cli={"SQUEEZE_APP_MODE": "CLOUD_PROVIDER_MODE"},
    )
    assert config.providers.ibkr.enabled is False


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([1], "INSUFFICIENT_HISTORY"),
        ([1, 2, 3], "ASCENDING"),
        ([3, 2, 1], "DESCENDING"),
        ([2, 2, 2], "FLAT"),
    ],
)
def test_trend_states(values, expected):
    result = trend(values, field="pressure")
    assert result["state"] == expected
    assert result["field"] == "pressure"
    if len(values) >= 2:
        assert result["first"] == values[0]
        assert result["latest"] == values[-1]
        assert result["change"] == values[-1] - values[0]


def test_sanitized_frozen_demo_has_exact_totals_and_no_private_material():
    demo = load_frozen_demo()
    assert demo["mode"] == "FROZEN_DEMO"
    assert len(demo["rows"]) == 13
    assert demo["totals"] == {"PASS": 97, "FAIL": 20, "UNKNOWN": 208}
    assert all(len(row["rules"]) == 25 for row in demo["rows"])
    assert all(row["research_detection"] == "UNEVALUABLE" for row in demo["rows"])
    assert all(row["outcome_status"] == "INCOMPLETE" for row in demo["rows"])
    encoded = json.dumps(demo).lower()
    for forbidden in ("raw_ohlcv", "frozen-forward", ".private", "c:\\\\", "account"):
        assert forbidden not in encoded


def test_committed_integration_manifest_fixture_matches_runtime_contract():
    from apps.research_screener.api_contract import (
        API_VERSION, SCHEMA_VERSION, integration_manifest,
    )
    from apps.research_screener.frozen_demo import DEMO_PATH

    fixture = json.loads(
        (DEMO_PATH.parent / "integration_manifest_v1.json").read_text(encoding="utf-8")
    )
    runtime = integration_manifest("CLOUD_PROVIDER_MODE")
    assert fixture["api_version"] == API_VERSION
    assert fixture["schema_version"] == SCHEMA_VERSION
    assert fixture["methodology_ids"] == runtime["methodology_ids"]
    assert fixture["prohibited_capabilities"] == runtime["prohibited_capabilities"]


@pytest.fixture
def api_server(tmp_path):
    server = build_server(
        find_free_port(9140),
        export_dir=tmp_path,
        deployment_mode=DeploymentMode.LOCAL_FULL,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://{server.server_address[0]}:{server.server_address[1]}"
    try:
        yield base
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def get_json(base, path):
    with urlopen(base + path, timeout=30) as response:
        return response.status, json.loads(response.read())


def test_health_readiness_methodology_and_manifest_routes_are_versioned(api_server):
    for path in (
        "/health",
        "/ready",
        "/api/methodologies",
        "/api/v1/integration/manifest",
        "/api/current/candidates",
        "/api/frozen/candidate/XNCR",
    ):
        status, payload = get_json(api_server, path)
        assert status == 200, path
        assert payload["api_version"] == "1.0.0", path
        assert payload["schema_version"], path
        assert "data" in payload and "status" in payload, path
        assert "missingness" in payload and "provenance" in payload, path

    _, manifest = get_json(api_server, "/api/v1/integration/manifest")
    data = manifest["data"]
    assert data["prohibited_capabilities"]["trading"] == "UNSUPPORTED"
    assert data["prohibited_capabilities"]["orders"] == "UNSUPPORTED"
    assert data["predictive_validation"] == "NOT_COMPLETED"


def test_methodology_symbol_and_refresh_aliases(api_server):
    from apps.research_screener import session_state
    from tests.app.synthetic_provider import SyntheticProvider

    session_state.reset_session(
        session_state.ScreenerSession(provider=SyntheticProvider(symbols=("AAA",)))
    )
    request = Request(api_server + "/api/discovery/refresh?profile=BROAD_MOVERS", method="POST")
    with urlopen(request, timeout=30):
        pass
    request = Request(api_server + "/api/current/refresh", method="POST")
    with urlopen(request, timeout=60):
        pass
    _, payload = get_json(api_server, "/api/methodologies/AAA")
    assert len(payload["data"]["methodologies"]) == 3
    assert payload["data"]["methodologies"][1]["classification"] == (
        "REFERENCE_DEFINITION_INCOMPLETE"
    )
    session_state.reset_session()


def test_api_responses_do_not_leak_secrets_or_local_paths(api_server):
    for path in ("/health", "/ready", "/api/v1/integration/manifest"):
        _, payload = get_json(api_server, path)
        encoded = json.dumps(payload).lower()
        for forbidden in ("token=", "cookie", "c:\\\\users\\\\", ".private"):
            assert forbidden not in encoded


def test_cloud_capability_report_never_claims_local_ibkr_connected(tmp_path, monkeypatch):
    monkeypatch.delenv("IBKR_ENABLED", raising=False)
    server = build_server(
        find_free_port(9150),
        export_dir=tmp_path,
        host="0.0.0.0",
        deployment_mode=DeploymentMode.CLOUD_PROVIDER_MODE,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_address[1]}"
        _, health = get_json(base, "/api/health")
        gateway = next(item for item in health["providers"] if item["name"] == "IB Gateway")
        assert gateway["state"] == "UNAVAILABLE"
        assert "ibkr" in gateway["detail"].lower()
        assert health["readiness"]["demo_ready"] is True

        _, payload = get_json(base, "/api/capabilities")
        ibkr = payload["providers"]["IBKR"]
        assert ibkr["configured"] is False
        assert ibkr["connected"] is False
        assert "disabled" in ibkr["capabilities"]["DISCOVERY"]["detail"].lower()

        _, frozen = get_json(base, "/api/frozen/candidates")
        assert frozen["data"]["source_kind"] == "SANITIZED_AGGREGATE"
        assert frozen["data"]["row_count"] == 13

        request = Request(base + "/api/export?mode=FROZEN_RESEARCH", method="POST")
        with urlopen(request, timeout=30) as response:
            exported = json.loads(response.read())
        assert exported["row_count"] == 13
        assert all("\\" not in name and "/" not in name for name in exported["written"].values())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
