"""Focused regression tests for audit remediation correctness + soft security gates."""

from __future__ import annotations

from urllib.error import HTTPError
from urllib.request import Request, urlopen
import threading

from apps.research_screener import session_state
from apps.research_screener.deployment import DeploymentMode
from apps.research_screener.finviz_live import FinvizRow
from apps.research_screener.methodologies.adam_v1 import evaluate_adam
from apps.research_screener.methodologies.evidence import EvidenceInput
from apps.research_screener.methodologies.projection import evidence_from_row
from apps.research_screener.server import ScreenerHandler, build_server
from apps.research_screener.session_state import _sec_filing_event_time, catalyst_fields
from tests.app.synthetic_provider import (
    FakeFinvizProvider,
    SyntheticProvider,
    fake_external_providers,
)


UNITS = {
    "published_short_interest_pct": "PERCENT",
    "days_to_cover": "DAYS",
    "float_shares": "SHARES",
    "current_percentage_change": "PERCENT",
    "relative_volume": "RATIO",
}


def evidence(key: str, value: float, *, admissible: bool = True):
    return EvidenceInput(
        key=key,
        value=value,
        unit=UNITS[key],
        provider="TEST",
        provider_field=key,
        event_time="2026-07-27T12:00:00Z",
        received_time="2026-07-27T12:00:00Z",
        display_available=True,
        research_admissible=admissible,
        point_in_time_eligible=True,
        fresh=True,
    )


def test_sec_catalyst_age_uses_filed_at_not_retrieved_at():
    sec_data = {
        "available": True,
        "catalyst_count": 1,
        "most_recent": {"filed_at": "2026-07-20T15:00:00Z", "form_type": "8-K"},
        "retrieved_at": "2026-07-27T16:00:00Z",
    }
    assert _sec_filing_event_time(sec_data) == "2026-07-20T15:00:00Z"

    session = session_state.ScreenerSession(
        provider=SyntheticProvider(symbols=("AAA",)),
        external_providers=fake_external_providers(),
        symbols_per_cycle=5,
    )
    session.refresh_discovery("BROAD_MOVERS")
    session.refresh_all()
    state = session.states["AAA"]
    session.external_providers._sec_cache["AAA"] = sec_data
    fields = catalyst_fields(state, session.external_providers)
    assert fields["sec_filings"].event_time == "2026-07-20T15:00:00Z"
    assert fields["sec_filings"].received_time == "2026-07-27T16:00:00Z"
    assert "catalyst_age_hours" in fields
    # Age must reflect filing time (~7 days), not retrieval (near zero).
    assert fields["catalyst_age_hours"].value > 24


def test_finviz_floor_sixty_five_is_evaluable_not_unevaluable_for_low_coverage():
    inputs = {
        "published_short_interest_pct": evidence("published_short_interest_pct", 30),
        "days_to_cover": evidence("days_to_cover", 7),
        "float_shares": evidence("float_shares", 10_000_000),
        "current_percentage_change": evidence("current_percentage_change", 20),
        "relative_volume": evidence("relative_volume", 10),
    }
    result = evaluate_adam(inputs)
    assert result.metadata["pressure_supported_weight"] == 65
    assert result.metadata["ignition_supported_weight"] == 65
    assert result.pressure is not None
    assert result.ignition is not None
    assert result.evidence_coverage["category"] == "LOW_COVERAGE"
    assert result.classification != "UNEVALUABLE"


def test_borrow_availability_pct_float_requires_both_admissible_legs():
    row = {
        "fields": {
            "borrow_availability": {
                "status": "KNOWN",
                "value": 50_000.0,
                "unit": "SHARES",
                "provider": "IBKR",
                "provider_field": "Shortable Shares",
                "event_time": "2026-07-27T12:00:00Z",
                "received_time": "2026-07-27T12:00:00Z",
                "freshness": "CURRENT",
                "research_admissibility": "RESEARCH_ADMISSIBLE",
                "evidence_id": "borrow",
            },
            "float_shares": {
                "status": "KNOWN",
                "value": 8_000_000.0,
                "unit": "SHARES",
                "provider": "Finviz Elite",
                "provider_field": "Shares Float",
                "event_time": "2026-07-27T12:00:00Z",
                "received_time": "2026-07-27T12:00:00Z",
                "freshness": "CURRENT",
                "research_admissibility": "RESEARCH_ADMISSIBLE",
                "evidence_id": "float",
            },
        }
    }
    inputs = evidence_from_row(row)
    item = inputs["borrow_availability_pct_float"]
    assert item.research_admissible is True
    assert item.eligible_for("PERCENT_OF_FLOAT") is True
    assert abs(item.value - (100.0 * 50_000 / 8_000_000)) < 1e-9

    row["fields"]["borrow_availability"]["research_admissibility"] = "RESEARCH_INADMISSIBLE"
    denied = evidence_from_row(row)["borrow_availability_pct_float"]
    assert denied.research_admissible is False
    assert denied.eligible_for("PERCENT_OF_FLOAT") is False


def test_estimated_dtc_and_finviz_day_change_are_research_inadmissible():
    from apps.research_screener import discovery as discovery_module
    from apps.research_screener.session_state import (
        CandidateState,
        metric_fields,
        short_pressure_fields,
    )

    estimated = FinvizRow(
        ticker="AAA",
        company="AAA Inc",
        sector="Technology",
        industry="Software",
        country="USA",
        price=7.0,
        change_pct=12.5,
        volume=2_000_000,
        avg_volume=1_000_000,
        rel_volume=2.0,
        market_cap=70_000_000,
        shares_outstanding=10_000_000,
        float_shares=8_000_000,
        short_float_pct=20.0,
        short_ratio=None,
        earnings_date=None,
        provider_columns=("Ticker", "Float", "Short Float", "Change", "Avg Volume"),
    )
    FakeFinvizProvider.cached_at = "2026-07-27T12:00:00Z"
    externals = fake_external_providers(finviz_rows={"AAA": estimated})
    state = CandidateState(
        candidate=discovery_module.CurrentDiscoveryCandidate(
            symbol="AAA", profile_id="MANUAL_SYMBOL"
        ),
        evaluation=None,
        collection=None,
    )
    pressure = short_pressure_fields(state, externals)
    metrics = metric_fields(state, externals)
    assert pressure["days_to_cover"].research_admissibility == "RESEARCH_INADMISSIBLE"
    assert pressure["days_to_cover"].selection_reason == "ESTIMATED_WHEN_SHORT_RATIO_MISSING"
    assert metrics["percentage_change"].research_admissibility == "RESEARCH_INADMISSIBLE"
    assert metrics["percentage_change"].provider == "Finviz Elite"


def test_provider_capabilities_works_without_handler_instance():
    session_state.reset_session()
    try:
        payload = ScreenerHandler._provider_capabilities("LOCAL_FULL")
        assert "providers" in payload
        assert "IBKR" in payload["providers"]
    finally:
        session_state.reset_session()


def _start_server(tmp_path, mode=DeploymentMode.CLOUD_PROVIDER_MODE):
    server = build_server(
        0,
        export_dir=tmp_path,
        deployment_mode=mode,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    base = f"http://{host}:{port}"
    return server, thread, base


def test_sensitive_api_lock_default_off_and_on(tmp_path, monkeypatch):
    monkeypatch.delenv("LOCK_SENSITIVE_API", raising=False)
    server, thread, base = _start_server(tmp_path)
    try:
        with urlopen(base + "/api/logs/status", timeout=10) as response:
            assert response.status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    monkeypatch.setenv("LOCK_SENSITIVE_API", "1")
    server, thread, base = _start_server(tmp_path)
    try:
        try:
            urlopen(base + "/api/logs/status", timeout=10)
            raise AssertionError("expected 403 when LOCK_SENSITIVE_API=1 in cloud mode")
        except HTTPError as exc:
            assert exc.code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        monkeypatch.delenv("LOCK_SENSITIVE_API", raising=False)


def test_csrf_protection_opt_in_default_off(tmp_path, monkeypatch):
    monkeypatch.delenv("CSRF_PROTECTION", raising=False)
    server, thread, base = _start_server(tmp_path)
    try:
        req = Request(base + "/api/live/auto?enabled=false", method="POST", data=b"")
        with urlopen(req, timeout=10) as response:
            assert response.status == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    monkeypatch.setenv("CSRF_PROTECTION", "1")
    server, thread, base = _start_server(tmp_path)
    try:
        req = Request(base + "/api/live/auto?enabled=false", method="POST", data=b"")
        try:
            urlopen(req, timeout=10)
            raise AssertionError("expected CSRF rejection")
        except HTTPError as exc:
            assert exc.code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        monkeypatch.delenv("CSRF_PROTECTION", raising=False)
