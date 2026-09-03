"""The meeting demo script, walked end to end against a real server instance.

This is the primary acceptance test: if it passes, the demo works.
"""

from __future__ import annotations

import csv
import json
import threading
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

from apps.research_screener import export as export_module
from apps.research_screener.paths import FrozenLayout
from apps.research_screener.server import build_server, find_free_port

pytestmark = pytest.mark.skipif(
    not FrozenLayout().available, reason="private frozen artifact root not present"
)

from .synthetic_provider import SyntheticProvider


@pytest.fixture(scope="module")
def server(tmp_path_factory: pytest.TempPathFactory):
    """Module-scoped server. Session is reset to a clean state per-test."""
    export_dir = tmp_path_factory.mktemp("screener-exports")
    instance = build_server(find_free_port(8900), export_dir=export_dir)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    host, port = instance.server_address[0], instance.server_address[1]
    try:
        yield f"http://{host}:{port}", Path(export_dir)
    finally:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=5)


def _get(base: str, path: str):
    with urlopen(f"{base}{path}", timeout=30) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _post(base: str, path: str):
    request = Request(f"{base}{path}", method="POST")
    with urlopen(request, timeout=60) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


# ---------------------------------------------------------------- demo steps


def test_step_2_application_serves_the_dashboard(server) -> None:
    base, _ = server
    with urlopen(f"{base}/", timeout=30) as response:
        body = response.read().decode("utf-8")
    assert response.status == 200
    assert "Short Squeeze Scanner" in body
    assert "EXPERIMENTAL RESEARCH CLASSIFICATION" in body
    # Advanced Research dashboard still available
    with urlopen(f"{base}/advanced", timeout=30) as adv_response:
        adv_body = adv_response.read().decode("utf-8")
    assert adv_response.status == 200
    assert "Short Squeeze Research Screener" in adv_body
    assert "RESEARCH TOOL — NOT A TRADING RECOMMENDATION" in adv_body


def test_step_3_provider_health_is_visible(server) -> None:
    base, _ = server
    status, payload = _get(base, "/api/health")
    assert status == 200
    names = {entry["name"] for entry in payload["providers"]}
    assert {"IB Gateway", "Market Data", "Historical Bars", "Finviz Elite",
            "NewsAPI", "Finnhub", "SEC EDGAR", "Sentiment"} <= names
    for entry in payload["providers"]:
        assert entry["state"] in {
            "CONNECTED", "DISCONNECTED", "AVAILABLE", "UNAVAILABLE",
            "CONFIGURED", "NOT CONFIGURED", "NOT USED",
        }
        assert entry["detail"]


def test_steps_4_and_5_frozen_mode_shows_thirteen_symbols(server) -> None:
    base, _ = server
    status, payload = _get(base, "/api/screener?mode=FROZEN_RESEARCH")
    assert status == 200
    assert payload["row_count"] == 13
    assert payload["header"]["mode_label"] == "FROZEN RESEARCH — 2026-07-18"
    assert payload["global_preflight_verdict"] == "PREFLIGHT_REJECTED"


def test_steps_6_to_13_xncr_drilldown(server) -> None:
    base, _ = server
    status, detail = _get(base, "/api/symbol?symbol=XNCR&mode=FROZEN_RESEARCH")
    assert status == 200
    assert len(detail["rules"]) == 25
    outcomes = {rule["outcome"] for rule in detail["rules"]}
    assert {"PASS", "FAIL", "UNKNOWN"} <= outcomes
    for rule in detail["rules"]:
        assert rule["reason"], f"{rule['rule_id']} has no explanation"
    assert detail["identity"]["boundary_time"] == "2026-07-18T13:37:55.017661Z"
    assert detail["provenance"]["phase3a_result_id"]
    assert detail["chart"]["available"] is True
    assert detail["chart"]["forward_window_shown"] is False
    assert detail["research_detection"]["status"] == "UNEVALUABLE"
    assert detail["outcome"]["status"] == "INCOMPLETE"


def test_steps_14_and_15_another_symbol_differs_on_percentage_change(server) -> None:
    base, _ = server
    _, xncr = _get(base, "/api/symbol?symbol=XNCR&mode=FROZEN_RESEARCH")
    _, avtx = _get(base, "/api/symbol?symbol=AVTX&mode=FROZEN_RESEARCH")

    def pct(detail):
        return next(
            rule for rule in detail["rules"] if rule["rule_id"] == "PERCENTAGE_CHANGE_MINIMUM"
        )

    assert pct(xncr)["outcome"] == "PASS"
    assert pct(avtx)["outcome"] == "FAIL"
    assert pct(xncr)["observed_value"] != pct(avtx)["observed_value"]


def test_step_16_current_mode_degrades_gracefully(server) -> None:
    """A provider failure must leave the app running and report the cause.

    The session is injected with a failing synthetic provider so the test never contacts
    IB Gateway. Frozen mode must remain completely unaffected.
    """
    from apps.research_screener import session_state

    provider = SyntheticProvider(collect_fails=True)
    session_state.reset_session(
        session_state.ScreenerSession(provider=provider, symbols_per_cycle=5)
    )

    base, _ = server
    # Discovery adds candidates even though the provider can't collect data.
    _post(base, "/api/discovery/refresh?profile=BROAD_MOVERS")

    status, payload = _get(base, "/api/live/candidates")
    assert status == 200
    assert payload["header"]["mode"] == "CURRENT"
    assert payload["row_count"] == 3

    # Now refresh the candidates. With collect_fails=True, each refresh will fail.
    _post(base, "/api/live/refresh")
    _, after_refresh = _get(base, "/api/live/candidates")
    for row in after_refresh["rows"]:
        assert row["stale"] is True, (
            f"{row['symbol']} should be stale after a failing refresh"
        )

    # The application is still serving: frozen mode is unaffected by the dead provider.
    assert _get(base, "/api/screener?mode=FROZEN_RESEARCH")[1]["row_count"] == 13

    session_state.reset_session()


def test_current_mode_evaluates_rules_when_provider_is_available(server) -> None:
    """Batch 11: current mode evaluates rules with admissible provider evidence.

    The provider is synthetic so the assertion holds on any machine.
    """
    from apps.research_screener import session_state

    provider = SyntheticProvider(symbols=("FAKE",))
    session_state.reset_session(
        session_state.ScreenerSession(provider=provider, symbols_per_cycle=5)
    )

    base, _ = server
    _post(base, "/api/discovery/refresh?profile=BROAD_MOVERS")
    _post(base, "/api/live/refresh")

    _, payload = _get(base, "/api/live/candidates")
    assert payload["available"] is True
    row = payload["rows"][0]
    assert row["symbol"] == "FAKE"

    # Batch 11: rules genuinely evaluate. Not everything is UNKNOWN.
    counts = row["phase3a"]["counts"]
    assert sum(counts.values()) == 25
    assert counts["PASS"] > 0 or counts["FAIL"] > 0, (
        "Current mode must evaluate rules when admissible evidence exists"
    )

    _, detail = _get(base, "/api/live/candidate?symbol=FAKE")
    assert len(detail["rules"]) == 25
    outcomes = {rule["outcome"] for rule in detail["rules"]}
    assert outcomes != {"UNKNOWN"}, (
        "Batch 11 evaluates rules; at least some must have PASS or FAIL"
    )

    session_state.reset_session()


def test_manual_symbol_invalid_input_is_handled(server) -> None:
    """An invalid ticker must be reported without contaminating the candidate list."""
    from apps.research_screener import session_state

    # Start with a clean session.
    session_state.reset_session(
        session_state.ScreenerSession(provider=SyntheticProvider(symbols=()))
    )

    base, _ = server
    status, payload = _get(
        base, "/api/screener?mode=CURRENT&symbols=THIS_IS_NOT_A_TICKER_AT_ALL"
    )
    assert status == 200
    assert payload["errors"], "an invalid symbol must be reported back"
    assert "THIS_IS_NOT_A_TICKER_AT_ALL" in str(payload["errors"])

    session_state.reset_session()


def test_unknown_frozen_symbol_is_reported_not_invented(server) -> None:
    base, _ = server
    status, payload = _get(base, "/api/symbol?symbol=NOTREAL&mode=FROZEN_RESEARCH")
    assert status == 200
    assert payload["available"] is False
    assert "not one of the 13" in payload["error"]


def test_step_17_export_writes_valid_json_and_csv(server) -> None:
    base, export_dir = server
    status, result = _post(base, "/api/export?mode=FROZEN_RESEARCH")
    assert status == 200
    assert result["row_count"] == 13

    json_path = Path(result["written"]["json"])
    csv_path = Path(result["written"]["csv"])
    assert json_path.is_file() and csv_path.is_file()
    assert json_path.parent == export_dir

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["export_kind"] == "RESEARCH_SNAPSHOT"
    assert "NOT a backtest dataset" in payload["notice"]
    assert len(payload["rows"]) == 13

    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 13
    assert set(rows[0]) == set(export_module.CSV_COLUMNS)
    for row in rows:
        assert row["research_detection"] == "UNEVALUABLE"
        assert row["outcome_status"] == "INCOMPLETE"
        assert row["global_preflight_status"] == "PREFLIGHT_REJECTED"
        # Missing stays empty. It never becomes a zero.
        assert row["short_float"] == ""
        assert row["short_float_status"] == "NOT_COLLECTED"
        assert row["reference_price"] == ""
        assert row["percentage_change"] != ""


def test_export_contains_no_credentials(server) -> None:
    base, _ = server
    _, result = _post(base, "/api/export?mode=FROZEN_RESEARCH")
    text = Path(result["written"]["json"]).read_text(encoding="utf-8").lower()
    for banned in ("password", "secret", "api_key", "apikey", "access_token", "refresh_token"):
        assert banned not in text


def test_professor_mode_is_reachable(server) -> None:
    base, _ = server
    status, payload = _get(base, "/api/professor")
    assert status == 200
    assert payload["case_count"] == 13
    assert payload["rule_case_pairs"] == 325
    assert payload["outcome_totals"] == {"PASS": 97, "FAIL": 20, "UNKNOWN": 208}
    assert any("UNKNOWN means insufficient admissible evidence" in n for n in payload["notes"])


def test_step_18_refresh_is_stable_and_deterministic(server) -> None:
    base, _ = server
    first = _get(base, "/api/screener?mode=FROZEN_RESEARCH")[1]
    second = _get(base, "/api/screener?mode=FROZEN_RESEARCH")[1]
    assert first["rows"] == second["rows"]
    assert _get(base, "/api/health")[0] == 200


def test_sorting_and_filtering_work_without_a_score(server) -> None:
    base, _ = server
    _, by_pass = _get(base, "/api/screener?mode=FROZEN_RESEARCH&sort=pass_count&desc=true")
    counts = [row["phase3a"]["counts"]["PASS"] for row in by_pass["rows"]]
    assert counts == sorted(counts, reverse=True)

    _, filtered = _get(base, "/api/screener?mode=FROZEN_RESEARCH&symbol=XN")
    assert [row["symbol"] for row in filtered["rows"]] == ["XNCR"]

    assert "score" not in json.dumps(by_pass["sort_keys"])


def test_server_refuses_a_non_localhost_bind() -> None:
    from apps.research_screener.server import ScreenerHandler, ScreenerServer

    for host in ("0.0.0.0", "192.168.1.10", ""):
        with pytest.raises(ValueError):
            ScreenerServer((host, 8999), ScreenerHandler)
