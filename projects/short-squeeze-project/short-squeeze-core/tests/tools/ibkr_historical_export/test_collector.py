"""End-to-end collector behaviour against a synthetic session (no socket)."""

from __future__ import annotations

import json

import pytest

from tools.ibkr_historical_export import collector as collector_mod
from tools.ibkr_historical_export.cohort import DETECTION_CONTEXT, FROZEN_FORWARD
from tools.ibkr_historical_export.collector import (
    ConnectionResult,
    ResilientConnection,
    probe_and_connect,
    reconnect_using_result,
    run_collection,
)
from tools.ibkr_historical_export.paths import PrivateLayout
from tools.ibkr_historical_export.statuses import CollectionStatus

from ._fakes import FakeSession, make_bar, make_candidate, session_factory


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(collector_mod.time, "sleep", lambda *_a, **_k: None)


# --------------------------------------------------------------- connection

def _precheck(*ports):
    accept = set(ports)
    return lambda host, port: port in accept


def test_probe_falls_back_to_second_port():
    factory = session_factory(connect_ports={4001}, ready_ports={4001})
    session, result = probe_and_connect(factory, precheck=_precheck(4001))
    assert result.status is CollectionStatus.CONNECTION_SUCCESS
    assert result.observed_port == 4001
    assert result.client_id == 27185


def test_probe_client_id_fallback_when_occupied():
    factory = session_factory(
        connect_ports={4002}, ready_ports={4002}, occupied_client_ids={27185},
    )
    session, result = probe_and_connect(factory, precheck=_precheck(4002))
    assert result.status is CollectionStatus.CONNECTION_SUCCESS
    assert result.observed_port == 4002
    assert result.client_id == 27186


def test_probe_fails_when_no_port_accepts():
    factory = session_factory(connect_ports=set(), ready_ports=set())
    session, result = probe_and_connect(factory, precheck=_precheck())
    assert session is None
    assert result.status is CollectionStatus.CONNECTION_FAILED


def test_probe_skips_ports_that_fail_precheck():
    factory = session_factory(connect_ports={4002, 4001}, ready_ports={4002, 4001})
    session, result = probe_and_connect(factory, precheck=_precheck(4001))
    assert result.observed_port == 4001
    # 4002 was skipped by the precheck (client_id None), then 4001 connected.
    assert any(a["port"] == 4002 and a["client_id"] is None for a in result.attempts)


def test_reconnect_using_result_reuses_observed_port():
    factory = session_factory(connect_ports={4001}, ready_ports={4001})
    session, result = probe_and_connect(factory, precheck=_precheck(4001))
    session.connection_closed()
    reconnected, reconnect_result = reconnect_using_result(
        factory, result, precheck=_precheck(4001),
    )
    assert reconnect_result.status is CollectionStatus.CONNECTION_SUCCESS
    assert reconnect_result.observed_port == 4001
    assert reconnected.isConnected()


def test_resilient_connection_reconnects_after_drop():
    factory = session_factory(connect_ports={4001}, ready_ports={4001})
    session, result = probe_and_connect(factory, precheck=_precheck(4001))
    session.record_endpoint("127.0.0.1", 4001, result.client_id)
    session.connection_closed()
    resilient = ResilientConnection(factory, result)
    resilient._session = session
    active = resilient.ensure_session()
    assert active.isConnected()
    assert resilient.reconnect_events


# --------------------------------------------------------------- full run

def _connected_session():
    return FakeSession(
        contract_script={"XNCR": [make_candidate("XNCR", 111)]},
        historical_script={
            ("XNCR", DETECTION_CONTEXT): {
                "bars": [
                    make_bar("XNCR", DETECTION_CONTEXT, 111, 1_784_000_000),
                    make_bar("XNCR", DETECTION_CONTEXT, 111, 1_784_000_060,
                             timestamp_utc="2026-07-17T13:39:00Z"),
                ],
                "completed": True,
            },
            ("XNCR", FROZEN_FORWARD): {"bars": [], "completed": True},
        },
    )


def _run(tmp_path):
    from tools.ibkr_historical_export.collector import ConnectionResult
    session = _connected_session()
    layout = PrivateLayout(tmp_path)
    connection = ConnectionResult(
        status=CollectionStatus.CONNECTION_SUCCESS, observed_port=4002,
        client_id=27185, server_version=187, current_time_epoch=1_784_000_000,
    )
    factory = session_factory(
        contract_script={"XNCR": [make_candidate("XNCR", 111)]},
        historical_script={
            ("XNCR", DETECTION_CONTEXT): {
                "bars": [
                    make_bar("XNCR", DETECTION_CONTEXT, 111, 1_784_000_000),
                    make_bar("XNCR", DETECTION_CONTEXT, 111, 1_784_000_060,
                             timestamp_utc="2026-07-17T13:39:00Z"),
                ],
                "completed": True,
            },
            ("XNCR", FROZEN_FORWARD): {"bars": [], "completed": True},
        },
    )
    resilient = ResilientConnection(factory, connection)
    resilient._session = session
    summary = run_collection(resilient, layout)
    return summary, layout


def test_full_run_writes_summary_and_statuses(tmp_path):
    summary, layout = _run(tmp_path)
    by_symbol = {s["symbol"]: s for s in summary["symbols"]}
    assert len(summary["symbols"]) == 15
    xncr = by_symbol["XNCR"]
    assert xncr["contract_status"] == "CONTRACT_RESOLVED"
    reqs = {r["request_name"]: r for r in xncr["requests"]}
    assert reqs[DETECTION_CONTEXT]["historical_status"] == "HISTORICAL_REQUEST_SUCCESS"
    assert reqs[DETECTION_CONTEXT]["bar_count"] == 2
    assert reqs[DETECTION_CONTEXT]["preflight_status"] == "PREFLIGHT_READY"
    assert "MISSING_ADJUSTMENT_SEMANTICS" not in reqs[DETECTION_CONTEXT]["preflight_reason_codes"]
    # Weekend forward window: empty and preflight not applicable.
    assert reqs[FROZEN_FORWARD]["historical_status"] == "SUCCESS_EMPTY"
    assert reqs[FROZEN_FORWARD]["preflight_status"] == "PREFLIGHT_NOT_APPLICABLE_EMPTY"


def test_unscripted_symbols_are_not_resolved(tmp_path):
    summary, _ = _run(tmp_path)
    by_symbol = {s["symbol"]: s for s in summary["symbols"]}
    assert by_symbol["PESI"]["contract_status"] == "CONTRACT_NOT_RESOLVED"
    assert by_symbol["PESI"]["requests"] == []


def test_raw_and_provenance_artifacts_exist(tmp_path):
    _, layout = _run(tmp_path)
    assert layout.raw_csv("XNCR", DETECTION_CONTEXT).exists()
    assert layout.raw_jsonl("XNCR", DETECTION_CONTEXT).exists()
    assert layout.sha256_manifest.exists()
    assert layout.artifact_manifest.exists()
    assert layout.request_manifest.exists()
    assert layout.contract_candidates("XNCR").exists()
    assert layout.preflight_report("XNCR", DETECTION_CONTEXT).exists()
    # Empty forward window still produces raw files (header-only CSV).
    assert layout.raw_csv("XNCR", FROZEN_FORWARD).exists()


def test_hashes_reverify(tmp_path):
    _, layout = _run(tmp_path)
    manifest = json.loads(layout.sha256_manifest.read_text(encoding="utf-8"))
    from tools.ibkr_historical_export.serialization import sha256_and_length
    for relative, expected in manifest.items():
        sha, length = sha256_and_length((layout.root / relative).read_bytes())
        assert sha == expected["sha256"]
        assert length == expected["byte_length"]


def test_run_is_byte_deterministic(tmp_path):
    _, layout1 = _run(tmp_path / "a")
    _, layout2 = _run(tmp_path / "b")
    csv1 = layout1.raw_csv("XNCR", DETECTION_CONTEXT).read_bytes()
    csv2 = layout2.raw_csv("XNCR", DETECTION_CONTEXT).read_bytes()
    assert csv1 == csv2


def test_no_account_identifiers_in_outputs(tmp_path):
    import re
    # IBKR account identifiers look like U1234567 / DU1234567; portfolio/balance data
    # must never appear. (The honest disclosure text legitimately says "non-account".)
    account_id = re.compile(r"\b(?:DU|DF|U)\d{6,}\b")
    for path in _run(tmp_path)[1].root.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            assert not account_id.search(text), f"account id leaked into {path.name}"
            lower = text.lower()
            for token in ("portfolio", "\"balance\"", "buyingpower", "netliquidation"):
                assert token not in lower, f"{token} leaked into {path.name}"
