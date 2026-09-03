"""Orchestration: connection probe, contract qualification, bar collection, and
offline verification + preflight -- writing only to the private Git-ignored root.

The live IBKR session is used only for the probe/qualify/collect stages; verification
and preflight are fully offline. No orders, account data, case association, or outcome
computation ever occur here.
"""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from . import policy
from .cohort import (
    CASE_IDS,
    FROZEN_SYMBOLS,
    REQUEST_SPECS,
    HistoricalRequestSpec,
)
from .errors import classify_historical_error, is_request_ending, is_transient
from .models import ContractResolution, HistoricalRequestResult
from .paths import PrivateLayout
from .preflight_bundle import run_bundle_preflight
from .resolution import resolve_contract
from .serialization import (
    canonical_json,
    serialize_bars_csv,
    serialize_bars_jsonl,
    sha256_and_length,
)
from .statuses import (
    REQUEST_TIME_PRECISION_TRUNCATED_TO_SECOND,
    CollectionStatus,
    ContractStatus,
    HistoricalStatus,
    PreflightStatus,
)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


@dataclass(slots=True)
class ConnectionResult:
    status: CollectionStatus
    observed_port: int | None = None
    client_id: int | None = None
    server_version: int | None = None
    current_time_epoch: int | None = None
    attempts: list[dict] = field(default_factory=list)


# ------------------------------------------------------------------ connection

def _socket_open(host: str, port: int, timeout: float = 3.0) -> bool:
    """Fast raw-TCP pre-check so a filtered port fails quickly, not on the OS timeout."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def probe_and_connect(
    session_factory, timeout: float = policy.CONNECTION_TIMEOUT_S, *, precheck=_socket_open,
):
    """Probe localhost ports/client IDs in frozen order. Returns (session, result)."""
    attempts: list[dict] = []
    for port in policy.PORT_PROBE_ORDER:
        if precheck is not None and not precheck(policy.HOST, port):
            attempts.append({
                "host": policy.HOST, "port": port, "client_id": None,
                "socket_connected": False, "ready": False, "error": "port not accepting TCP",
            })
            continue
        for client_id in policy.CLIENT_ID_SEQUENCE:
            session = session_factory()
            error_note = ""
            try:
                session.connect(policy.HOST, port, client_id)
                session.start_run_loop()
                connected = session.isConnected()
                ready = session.wait_ready(timeout) if connected else False
            except Exception as exc:  # noqa: BLE001 - any connect failure = port unusable
                connected = False
                ready = False
                error_note = f"{type(exc).__name__}: {exc}"
                try:
                    session.shutdown()
                except Exception:  # noqa: BLE001
                    pass
            attempts.append({
                "host": policy.HOST, "port": port, "client_id": client_id,
                "socket_connected": bool(connected), "ready": bool(ready),
                "error": error_note,
            })
            if ready and session.isConnected():
                session.record_endpoint(policy.HOST, port, client_id)
                server_version = session.get_server_version()
                current_time = session.fetch_current_time(timeout)
                return session, ConnectionResult(
                    status=CollectionStatus.CONNECTION_SUCCESS,
                    observed_port=port, client_id=client_id,
                    server_version=server_version, current_time_epoch=current_time,
                    attempts=attempts,
                )
            session.shutdown()
            if not connected:
                # Socket pre-check passed but API handshake failed -> next client ID,
                # unless nothing connected at all.
                break
    return None, ConnectionResult(status=CollectionStatus.CONNECTION_FAILED, attempts=attempts)


def connect_configured(
    session_factory,
    host: str,
    port: int,
    client_id_sequence: tuple[int, ...],
    timeout: float = policy.CONNECTION_TIMEOUT_S,
    *,
    precheck=_socket_open,
):
    """Connect to an explicitly configured gateway host (cloud sidecar or remote API)."""
    attempts: list[dict] = []
    if precheck is not None and not precheck(host, port):
        attempts.append({
            "host": host,
            "port": port,
            "client_id": None,
            "socket_connected": False,
            "ready": False,
            "error": "port not accepting TCP",
        })
        return None, ConnectionResult(status=CollectionStatus.CONNECTION_FAILED, attempts=attempts)
    for client_id in client_id_sequence:
        session = session_factory()
        error_note = ""
        try:
            session.connect(host, port, client_id)
            session.start_run_loop()
            connected = session.isConnected()
            ready = session.wait_ready(timeout) if connected else False
        except Exception as exc:  # noqa: BLE001
            connected = False
            ready = False
            error_note = f"{type(exc).__name__}: {exc}"
            try:
                session.shutdown()
            except Exception:  # noqa: BLE001
                pass
        attempts.append({
            "host": host,
            "port": port,
            "client_id": client_id,
            "socket_connected": bool(connected),
            "ready": bool(ready),
            "error": error_note,
        })
        if ready and session.isConnected():
            session.record_endpoint(host, port, client_id)
            server_version = session.get_server_version()
            current_time = session.fetch_current_time(timeout)
            return session, ConnectionResult(
                status=CollectionStatus.CONNECTION_SUCCESS,
                observed_port=port,
                client_id=client_id,
                server_version=server_version,
                current_time_epoch=current_time,
                attempts=attempts,
            )
        session.shutdown()
        if not connected:
            break
    return None, ConnectionResult(status=CollectionStatus.CONNECTION_FAILED, attempts=attempts)


def _session_is_live(
    session,
    timeout: float = policy.CONNECTION_PING_TIMEOUT_S,
    *,
    verify_with_ping: bool = False,
) -> bool:
    """True when the session reports an open API socket.

    ``verify_with_ping`` optionally issues ``reqCurrentTime``, but IBKR often answers
    that slowly even on healthy sockets, so the default is connection-state only.
    """
    try:
        if hasattr(session, "is_live"):
            if not session.is_live():
                return False
        elif not session.isConnected():
            return False
        if verify_with_ping and hasattr(session, "ping"):
            return bool(session.ping(timeout))
        return True
    except Exception:  # noqa: BLE001
        return False


def reconnect_using_result(
    session_factory,
    connection: ConnectionResult,
    *,
    host: str = policy.HOST,
    timeout: float = policy.CONNECTION_TIMEOUT_S,
    precheck=_socket_open,
) -> tuple[Any, ConnectionResult]:
    """Reconnect on a prior successful port/client_id, then fall back to full probe."""
    attempts: list[dict] = list(connection.attempts)
    port = connection.observed_port
    client_id = connection.client_id
    if port is not None and client_id is not None:
        if precheck is not None and not precheck(host, port):
            attempts.append({
                "host": host, "port": port, "client_id": client_id,
                "socket_connected": False, "ready": False,
                "error": "port not accepting TCP (reconnect)",
            })
        else:
            session = session_factory()
            error_note = ""
            try:
                session.connect(host, port, client_id)
                session.start_run_loop()
                connected = session.isConnected()
                ready = session.wait_ready(timeout) if connected else False
            except Exception as exc:  # noqa: BLE001
                connected = False
                ready = False
                error_note = f"{type(exc).__name__}: {exc}"
                try:
                    session.shutdown()
                except Exception:  # noqa: BLE001
                    pass
            attempts.append({
                "host": host, "port": port, "client_id": client_id,
                "socket_connected": bool(connected), "ready": bool(ready),
                "error": error_note or "reconnect attempt",
            })
            if ready and session.isConnected():
                session.record_endpoint(host, port, client_id)
                server_version = session.get_server_version()
                current_time = session.fetch_current_time(timeout)
                return session, ConnectionResult(
                    status=CollectionStatus.CONNECTION_SUCCESS,
                    observed_port=port,
                    client_id=client_id,
                    server_version=server_version,
                    current_time_epoch=current_time,
                    attempts=attempts,
                )
            session.shutdown()

    session, result = probe_and_connect(session_factory, timeout, precheck=precheck)
    if result.attempts:
        attempts.extend(result.attempts)
    result.attempts = attempts
    return session, result


@dataclass(slots=True)
class ResilientConnection:
    """Keeps one live IBKR session, transparently reconnecting after API drops."""

    session_factory: Any
    connection: ConnectionResult
    host: str = policy.HOST
    _session: Any = None
    reconnect_events: list[dict] = field(default_factory=list)

    def ensure_session(
        self,
        timeout: float = policy.CONNECTION_TIMEOUT_S,
        *,
        ping_timeout: float = policy.CONNECTION_PING_TIMEOUT_S,
    ) -> Any:
        if self._session is not None and _session_is_live(self._session, ping_timeout):
            return self._session
        return self._reconnect(timeout)

    def _reconnect(self, timeout: float) -> Any:
        if self._session is not None:
            try:
                if hasattr(self._session, "reconnect"):
                    if self._session.reconnect(timeout) and _session_is_live(
                        self._session, verify_with_ping=True,
                    ):
                        self.reconnect_events.append({
                            "strategy": "in_place",
                            "port": self.connection.observed_port,
                            "client_id": self.connection.client_id,
                        })
                        return self._session
            except Exception:  # noqa: BLE001
                pass
            try:
                self._session.shutdown()
            except Exception:  # noqa: BLE001
                pass
            self._session = None

        last_error = ""
        for attempt in range(policy.RECONNECT_ATTEMPTS):
            if attempt:
                time.sleep(policy.RECONNECT_BACKOFF_S)
            session, result = reconnect_using_result(
                self.session_factory,
                self.connection,
                host=self.host,
                timeout=timeout,
            )
            if session is not None and result.status is CollectionStatus.CONNECTION_SUCCESS:
                self._session = session
                self.connection = result
                self.reconnect_events.append({
                    "strategy": "new_session",
                    "attempt": attempt + 1,
                    "port": result.observed_port,
                    "client_id": result.client_id,
                })
                return session
            last_error = (
                result.attempts[-1].get("error", "reconnect failed")
                if result.attempts
                else "reconnect failed"
            )
        raise ConnectionError(
            f"IB Gateway reconnect failed after {policy.RECONNECT_ATTEMPTS} attempt(s): "
            f"{last_error}"
        )

    def shutdown(self) -> None:
        if self._session is not None:
            try:
                self._session.shutdown()
            except Exception:  # noqa: BLE001
                pass
        self._session = None


# ------------------------------------------------------------------ qualify

def qualify_contract(session, req_id: int, symbol: str) -> ContractResolution:
    candidates, _errors = session.request_contract_details(
        req_id, symbol, policy.CONTRACT_DETAILS_TIMEOUT_S
    )
    return resolve_contract(symbol, candidates)


# ------------------------------------------------------------------ collect

def collect_historical(
    session, req_id: int, spec: HistoricalRequestSpec, symbol: str, con_id: int,
) -> HistoricalRequestResult:
    """One historical request, with at most one transient retry."""
    from .session import make_conid_contract  # local import keeps ibapi optional

    started = _now_iso()
    attempt = 0
    while True:
        contract = make_conid_contract(con_id, symbol)
        bars, errors, completed = session.request_historical(
            req_id + attempt, spec, symbol, con_id, contract, policy.HISTORICAL_TIMEOUT_S,
        )
        ending = [(c, m) for (c, m, _t) in errors if is_request_ending(c)]
        transient = any(is_transient(c) for (c, _m, _t) in errors)
        if not completed and not ending:
            status = HistoricalStatus.HISTORICAL_REQUEST_TIMEOUT
        elif bars:
            status = HistoricalStatus.HISTORICAL_REQUEST_SUCCESS
        elif ending:
            code, msg = ending[-1]
            status = classify_historical_error(code, msg)
        else:
            status = HistoricalStatus.SUCCESS_EMPTY

        should_retry = (
            attempt == 0
            and transient
            and status in (
                HistoricalStatus.HISTORICAL_REQUEST_TIMEOUT,
                HistoricalStatus.HISTORICAL_REQUEST_ERROR,
            )
        )
        if not should_retry:
            break
        time.sleep(policy.RETRY_BACKOFF_S)
        attempt += 1

    completed_at = _now_iso()
    first_ts = bars[0].timestamp_utc if bars else None
    last_ts = bars[-1].timestamp_utc if bars else None
    return HistoricalRequestResult(
        request_name=spec.request_name,
        requested_symbol=symbol,
        resolved_con_id=con_id,
        status=status,
        bars=tuple(bars),
        error_codes=tuple(c for (c, _m, _t) in errors),
        retrieval_started_at=started,
        retrieval_completed_at=completed_at,
        first_timestamp_utc=first_ts,
        last_timestamp_utc=last_ts,
        notes=(REQUEST_TIME_PRECISION_TRUNCATED_TO_SECOND,),
    )


# ------------------------------------------------------------------ persistence

def write_raw_artifacts(layout: PrivateLayout, result: HistoricalRequestResult) -> dict:
    """Write JSONL + CSV deterministically, hash exactly, re-read, and verify."""
    jsonl_bytes = serialize_bars_jsonl(result.bars)
    csv_bytes = serialize_bars_csv(result.bars)
    jsonl_path = layout.raw_jsonl(result.requested_symbol, result.request_name)
    csv_path = layout.raw_csv(result.requested_symbol, result.request_name)
    jsonl_path.write_bytes(jsonl_bytes)
    csv_path.write_bytes(csv_bytes)

    jsonl_sha, jsonl_len = sha256_and_length(jsonl_path.read_bytes())
    csv_sha, csv_len = sha256_and_length(csv_path.read_bytes())
    # Re-hash the in-memory bytes and compare against the on-disk read.
    assert (jsonl_sha, jsonl_len) == sha256_and_length(jsonl_bytes)
    assert (csv_sha, csv_len) == sha256_and_length(csv_bytes)
    return {
        "symbol": result.requested_symbol,
        "request_name": result.request_name,
        "jsonl_sha256": jsonl_sha,
        "jsonl_byte_length": jsonl_len,
        "csv_sha256": csv_sha,
        "csv_byte_length": csv_len,
        "csv_relative_path": layout.raw_relative_csv(result.requested_symbol, result.request_name),
    }


__all__ = [
    "ConnectionResult",
    "ResilientConnection",
    "connect_configured",
    "probe_and_connect",
    "reconnect_using_result",
    "qualify_contract",
    "collect_historical",
    "write_raw_artifacts",
    "run_collection",
]


# ------------------------------------------------------------------ full run

def run_collection(resilient: ResilientConnection, layout: PrivateLayout) -> dict:
    """Qualify all symbols, collect both requests per resolved contract, persist, and
    run offline preflight. Returns the sanitized aggregate summary payload."""
    layout.ensure()
    connection = resilient.connection

    # Persist connection probe (no account data).
    layout.probe_result.write_bytes(canonical_json({
        "status": connection.status.value,
        "host": policy.HOST,
        "observed_port": connection.observed_port,
        "client_id": connection.client_id,
        "server_version": connection.server_version,
        "current_time_epoch": connection.current_time_epoch,
        "attempts": connection.attempts,
    }))

    req_counter = 1000
    resolutions: dict[str, ContractResolution] = {}
    per_symbol_summary: list[dict] = []
    artifact_records: list[dict] = []
    request_manifest: list[dict] = []

    for symbol in FROZEN_SYMBOLS:
        req_counter += 1
        active = resilient.ensure_session()
        resolution = qualify_contract(active, req_counter, symbol)
        resolutions[symbol] = resolution
        # Private contract candidates (full payload) -- never committed.
        layout.contract_candidates(symbol).write_bytes(canonical_json({
            "requested_symbol": symbol,
            "case_id": CASE_IDS[symbol],
            "status": resolution.status.value,
            "reason": resolution.reason,
            "resolved": resolution.resolved.as_dict() if resolution.resolved else None,
            "candidates": [c.as_dict() for c in resolution.candidates],
        }))

        symbol_entry: dict = {
            "symbol": symbol,
            "case_id": CASE_IDS[symbol],
            "contract_status": resolution.status.value,
            "resolved_con_id": resolution.resolved.con_id if resolution.resolved else None,
            "resolved_local_symbol": resolution.resolved.local_symbol if resolution.resolved else None,
            "resolved_primary_exchange": resolution.resolved.primary_exchange if resolution.resolved else None,
            "requests": [],
        }

        if resolution.status is not ContractStatus.CONTRACT_RESOLVED or resolution.resolved is None:
            per_symbol_summary.append(symbol_entry)
            continue

        con_id = resolution.resolved.con_id
        for index, spec in enumerate(REQUEST_SPECS):
            req_counter += 10
            active = resilient.ensure_session()
            result = collect_historical(active, req_counter, spec, symbol, con_id)
            artifacts = write_raw_artifacts(layout, result)
            artifact_records.append(artifacts)
            request_manifest.append({
                "symbol": symbol,
                "request_name": spec.request_name,
                "end_datetime": spec.end_datetime,
                "duration_str": spec.duration_str,
                "bar_size_setting": spec.bar_size_setting,
                "what_to_show": spec.what_to_show,
                "use_rth": spec.use_rth,
                "format_date": spec.format_date,
                "status": result.status.value,
                "bar_count": result.bar_count,
                "first_timestamp_utc": result.first_timestamp_utc,
                "last_timestamp_utc": result.last_timestamp_utc,
                "retrieval_started_at": result.retrieval_started_at,
                "retrieval_completed_at": result.retrieval_completed_at,
                "error_codes": list(result.error_codes),
                "notes": list(result.notes),
            })

            # Offline preflight for a nonempty CSV; N/A for empty windows.
            preflight_status, preflight_reasons = _run_preflight_for(
                layout, result, spec, artifacts,
            )
            symbol_entry["requests"].append({
                "request_name": spec.request_name,
                "historical_status": result.status.value,
                "bar_count": result.bar_count,
                "first_timestamp_utc": result.first_timestamp_utc,
                "last_timestamp_utc": result.last_timestamp_utc,
                "csv_sha256": artifacts["csv_sha256"],
                "csv_byte_length": artifacts["csv_byte_length"],
                "jsonl_sha256": artifacts["jsonl_sha256"],
                "jsonl_byte_length": artifacts["jsonl_byte_length"],
                "preflight_status": preflight_status.value,
                "preflight_reason_codes": preflight_reasons,
                "error_codes": list(result.error_codes),
            })
            if index < len(REQUEST_SPECS) - 1:
                time.sleep(policy.INTER_REQUEST_DELAY_S)

        per_symbol_summary.append(symbol_entry)

    # Diagnostics (provider messages) -- private only.
    diag_lines = "".join(
        canonical_json({
            "request_id": d.request_id, "error_code": d.error_code,
            "error_message": d.error_message, "error_time": d.error_time,
        }).decode("utf-8").replace("\n", " ").strip() + "\n"
        for d in resilient.ensure_session().all_diagnostics()
    )
    layout.api_diagnostics.write_text(diag_lines, encoding="utf-8")

    layout.request_manifest.write_bytes(canonical_json(request_manifest))
    layout.artifact_manifest.write_bytes(canonical_json(artifact_records))
    layout.sha256_manifest.write_bytes(canonical_json({
        rec["csv_relative_path"]: {"sha256": rec["csv_sha256"], "byte_length": rec["csv_byte_length"]}
        for rec in artifact_records
    }))

    summary = {
        "batch": "ibkr-batch-05",
        "connection": {
            "status": resilient.connection.status.value,
            "observed_port": resilient.connection.observed_port,
            "client_id": resilient.connection.client_id,
            "server_version": resilient.connection.server_version,
            "reconnect_events": list(resilient.reconnect_events),
        },
        "generated_at": _now_iso(),
        "symbols": per_symbol_summary,
    }
    layout.collection_summary.write_bytes(canonical_json(summary))
    return summary


def _run_preflight_for(layout, result, spec, artifacts) -> tuple[PreflightStatus, list[str]]:
    if result.status is HistoricalStatus.SUCCESS_EMPTY or result.bar_count == 0:
        return PreflightStatus.PREFLIGHT_NOT_APPLICABLE_EMPTY, []
    csv_bytes = layout.raw_csv(result.requested_symbol, result.request_name).read_bytes()
    retrieval = datetime.now(UTC)
    outcome = run_bundle_preflight(
        bundle_id=f"IBKR_BATCH05_{result.requested_symbol}_{spec.request_name}",
        symbol=result.requested_symbol,
        csv_bytes=csv_bytes,
        artifact_relative_path=artifacts["csv_relative_path"],
        artifact_sha256=artifacts["csv_sha256"],
        artifact_byte_length=artifacts["csv_byte_length"],
        retrieval_time=retrieval,
        export_time=retrieval,
        expected_start_time=spec.expected_window_start,
        expected_end_time=spec.expected_window_end,
    )
    report_path = layout.preflight_report(result.requested_symbol, result.request_name)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_bytes(canonical_json(outcome.report.model_dump(mode="json")))
    return outcome.status, list(outcome.reason_codes)
