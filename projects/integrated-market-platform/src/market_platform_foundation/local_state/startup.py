"""Startup / crash recovery for durable local IMP state."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..operating_modes import (
    PAPER_EXECUTION_AUTHORITIES,
    resolve_execution_authority,
)
from ..paper.ledger import PaperExecutionLedger, order_state_open_count_delta
from .capture_index import refresh_capture_catalog
from .connection import CorruptStateError, LocalStateConnection
from .opend import diagnose_opend
from .paths import database_path, persistence_enabled, state_dir
from .repository import SESSION_CLOSED, SESSION_OPEN, LocalStateRepository
from .schema import SCHEMA_VERSION

_CONNECTION: LocalStateConnection | None = None
_REPOSITORY: LocalStateRepository | None = None


def configuration_hash(
    *,
    data_mode: str,
    execution_mode: str,
    data_provider: str,
    execution_provider: str,
    starting_cash_minor: int,
    policy_version: str | None = None,
) -> str:
    return sha256_bytes(
        canonical_bytes(
            {
                "data_mode": data_mode,
                "data_provider": data_provider,
                "execution_mode": execution_mode,
                "execution_provider": execution_provider,
                "policy_version": policy_version,
                "starting_cash_minor": starting_cash_minor,
            }
        )
    )


def open_local_state(*, force: bool = False) -> LocalStateRepository | None:
    global _CONNECTION, _REPOSITORY
    if not persistence_enabled() and not force:
        return None
    if _REPOSITORY is not None:
        return _REPOSITORY
    path = database_path(create_dir=True)
    _CONNECTION = LocalStateConnection(path)
    _REPOSITORY = LocalStateRepository(_CONNECTION)
    refresh_capture_catalog(_REPOSITORY)
    return _REPOSITORY


def reset_local_state_for_tests() -> None:
    global _CONNECTION, _REPOSITORY
    if _CONNECTION is not None:
        _CONNECTION.close()
    _CONNECTION = None
    _REPOSITORY = None


def session_record_from_ledger(ledger: PaperExecutionLedger, *, status: str = SESSION_OPEN) -> dict[str, Any]:
    created = int(ledger.events[0]["event_time"]) if ledger.events else 0
    closed = None
    if status == SESSION_CLOSED:
        for event in reversed(ledger.events):
            if event["event_type"] == "PaperSessionClosed":
                closed = int(event["event_time"])
                break
    return {
        "closed_at": closed,
        "configuration_hash": configuration_hash(
            data_mode=ledger.data_mode,
            execution_mode=ledger.execution_mode,
            data_provider=ledger.data_provider,
            execution_provider=ledger.execution_provider,
            starting_cash_minor=int(ledger.policy["initial_cash_minor"]),
            policy_version=str(ledger.policy.get("policy_version")),
        ),
        "created_at": created,
        "data_mode": ledger.data_mode,
        "data_provider": ledger.data_provider,
        "execution_mode": ledger.execution_mode,
        "execution_provider": ledger.execution_provider,
        "instrument_id": ledger._primary_instrument_id(),
        "paper_account_id": ledger.paper_account_id,
        "policy": ledger.policy,
        "replay_session_id": ledger.session_id,
        "session_id": ledger.session_id,
        "starting_cash_minor": int(ledger.policy["initial_cash_minor"]),
        "status": status,
        "symbol": ledger._primary_symbol(),
    }


def persist_ledger(ledger: PaperExecutionLedger, *, events: list[dict[str, Any]] | None = None) -> None:
    repo = open_local_state()
    if repo is None:
        return
    closed = any(event["event_type"] == "PaperSessionClosed" for event in ledger.events)
    repo.persist_paper_events(
        session=session_record_from_ledger(ledger, status=SESSION_CLOSED if closed else SESSION_OPEN),
        events=events if events is not None else ledger.events,
        idempotency_index=ledger.idempotency_index,
    )
    last_seq = int(ledger.events[-1]["sequence"]) if ledger.events else 0
    repo.save_snapshot(
        session_id=ledger.session_id,
        last_event_sequence=last_seq,
        projection={
            "live_mark_as_of_ns": ledger._live_mark_as_of_ns,
            "live_mark_minor": ledger._live_mark_minor,
            "live_mark_provider": ledger._live_mark_provider,
            "live_mark_quality": ledger._live_mark_quality,
            "marks_by_instrument": {
                key: dict(value) for key, value in ledger._marks_by_instrument.items()
            },
        },
    )


def ledger_from_session(row: dict[str, Any], events: list[dict[str, Any]], idempotency: dict[str, str]) -> PaperExecutionLedger:
    import json

    from ..risk.policy import DEFAULT_RISK_POLICY

    policy = row.get("policy")
    if isinstance(policy, str):
        policy = json.loads(policy)
    if not isinstance(policy, dict):
        raw_policy = row.get("policy_json")
        policy = json.loads(raw_policy) if raw_policy else {}
    legacy_cash_account = "cash_account" not in policy
    legacy_long_only = "long_only" not in policy
    policy = {**DEFAULT_RISK_POLICY, **policy}
    if legacy_cash_account:
        policy["cash_account"] = False
    if legacy_long_only:
        policy["long_only"] = False
    ledger = PaperExecutionLedger(
        paper_account_id=str(row["paper_account_id"]),
        session_id=str(row["session_id"]),
        events=[],
        idempotency_index=dict(idempotency),
        policy=dict(policy or {}),
        data_mode=str(row["data_mode"]),
        execution_mode=str(row["execution_mode"]),
        # Restore derives authority from the stored execution mode so each
        # mode is gated by its own env flag (INTERNAL_SIMULATION ->
        # IMP_PAPER_EXECUTION, BROKER_PAPER -> IMP_BROKER_PAPER_EXECUTION,
        # LIVE -> IMP_LIVE_EXECUTION); a stale IMP_PAPER_EXECUTION alone can
        # no longer resurrect a BROKER_PAPER session.
        execution_authority=resolve_execution_authority(requested_mode=str(row["execution_mode"])),
        data_provider=str(row["data_provider"]),
        execution_provider=str(row["execution_provider"]),
    )
    for event in events:
        reconstructed = dict(event)
        reconstructed.setdefault("data_mode", ledger.data_mode)
        reconstructed.setdefault("data_provider", ledger.data_provider)
        reconstructed.setdefault("execution_mode", ledger.execution_mode)
        reconstructed.setdefault("execution_provider", ledger.execution_provider)
        reconstructed.setdefault("paper_account_id", ledger.paper_account_id)
        ledger.events.append(reconstructed)
    open_orders = 0
    order_states: dict[str, str] = {}
    for event in ledger.events:
        if event["event_type"] != "OrderStateChanged":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        order_id = str(payload.get("order_id", ""))
        state = str(payload.get("state", ""))
        prior = order_states.get(order_id)
        open_orders = max(0, open_orders + order_state_open_count_delta(prior, state))
        order_states[order_id] = state
    ledger.open_order_count = open_orders
    ledger.persist_sink = persist_ledger_batch
    repo = open_local_state()
    snapshot = repo.load_snapshot(str(row["session_id"])) if repo is not None else None
    marks = snapshot.get("marks_by_instrument") if isinstance(snapshot, dict) else None
    if isinstance(marks, dict):
        for instrument_id, mark in marks.items():
            if not isinstance(mark, dict) or mark.get("mark_minor") is None:
                continue
            ledger.apply_live_mark(
                instrument_id=str(instrument_id),
                mark_minor=int(mark["mark_minor"]),
                mark_provider=str(mark.get("mark_provider") or "UNKNOWN"),
                mark_as_of_ns=int(mark.get("mark_as_of_ns") or 0),
                # A persisted mark is evidence of the last observation, not a
                # fresh live health assertion after restart.
                mark_quality="RESTORED",
            )
    elif snapshot and snapshot.get("live_mark_minor") is not None:
        ledger.apply_live_mark(
            instrument_id=ledger._primary_instrument_id(),
            mark_minor=int(snapshot["live_mark_minor"]),
            mark_provider=str(snapshot.get("live_mark_provider") or "MOOMOO"),
            mark_as_of_ns=int(snapshot.get("live_mark_as_of_ns") or 0),
            mark_quality="RESTORED",
        )
    elif ledger.data_mode == "LIVE_OBSERVATIONAL":
        fills = ledger.project_fills()
        if fills:
            last = fills[-1]
            ledger.apply_live_mark(
                instrument_id=str(last.get("instrument_id") or ledger._primary_instrument_id()),
                mark_minor=int(last["fill_price_minor"]),
                mark_provider=str(ledger.data_provider or "MOOMOO"),
                mark_as_of_ns=int(last.get("fill_time") or 0),
                mark_quality="RESTORED",
            )
    return ledger


def persist_ledger_batch(ledger: PaperExecutionLedger, events: list[dict[str, Any]]) -> None:
    persist_ledger(ledger, events=events)


def compatible_resume(*, stored: dict[str, Any], current: dict[str, Any]) -> bool:
    current_policy_identity = _policy_identity(current)
    return (
        stored.get("data_mode") == current.get("data_mode")
        and stored.get("data_provider") == current.get("data_provider")
        and stored.get("execution_provider") == current.get("execution_provider")
        and int(stored.get("starting_cash_minor") or 0) == int(current.get("starting_cash_minor") or 0)
        # Older direct restore callers supplied only transport/session fields.
        # The persisted current session record remains authoritative in that
        # compatibility case; normal startup callers include the identity and
        # therefore enforce exact policy matching.
        and (
            not current_policy_identity
            or _policy_identity(stored) == current_policy_identity
        )
    )


def _policy_identity(record: dict[str, Any]) -> str:
    import json

    policy = record.get("policy")
    if isinstance(policy, str):
        policy = json.loads(policy)
    if not isinstance(policy, dict):
        raw = record.get("policy_json")
        policy = json.loads(raw) if isinstance(raw, str) and raw else {}
    return str(policy.get("risk_policy_identity_hash") or "")


def startup_report(*, live_healthy: bool = False) -> dict[str, Any]:
    report: dict[str, Any] = {
        "crash_recovery": "NONE",
        "execution_deferred": True,
        "opend": diagnose_opend(),
        "persistence_enabled": persistence_enabled(),
        "previous_session": None,
        "restore": "NONE",
        "schema_version": SCHEMA_VERSION,
        "state_dir": str(state_dir()),
        "state_error": None,
    }
    try:
        repo = open_local_state()
    except CorruptStateError as exc:
        report["crash_recovery"] = "CORRUPT_DB"
        report["state_error"] = str(exc)
        report["opend"] = diagnose_opend()
        return report
    if repo is None:
        return report
    report["schema_version"] = repo.connection.schema_version()
    previous = repo.latest_open_session()
    if previous is None:
        report["restore"] = "FRESH"
        return report
    report["previous_session"] = {
        "session_id": previous["session_id"],
        "status": previous["status"],
        "data_mode": previous["data_mode"],
        "execution_mode": previous["execution_mode"],
    }


    report["crash_recovery"] = "OPEN_SESSION_DETECTED"
    report["restore"] = "PENDING_OPERATOR"
    if (
        live_healthy
        and resolve_execution_authority(requested_mode=str(previous.get("execution_mode") or ""))
        in PAPER_EXECUTION_AUTHORITIES
    ):
        report["execution_deferred"] = False
    return report


def _execution_gate_env_name(execution_mode: str) -> str:
    """Env flag that gates the given execution mode (for restore diagnostics)."""
    if execution_mode == "BROKER_PAPER":
        return "IMP_BROKER_PAPER_EXECUTION"
    if execution_mode == "LIVE":
        return "IMP_LIVE_EXECUTION"
    return "IMP_PAPER_EXECUTION"


def restore_open_ledger(*, current_config: dict[str, Any]) -> tuple[PaperExecutionLedger | None, dict[str, Any]]:
    repo = open_local_state()
    details = {"reason": "NO_STORE", "same_session": False}
    if repo is None:
        return None, details
    previous = repo.latest_open_session()
    if previous is None:
        details["reason"] = "NO_OPEN_SESSION"
        return None, details
    if not compatible_resume(stored=previous, current=current_config):
        details["reason"] = "CONFIG_INCOMPATIBLE"
        details["stored_hash"] = previous.get("configuration_hash")
        details["current_hash"] = current_config.get("configuration_hash")
        current_policy_identity = _policy_identity(current_config)
        if current_policy_identity and _policy_identity(previous) != current_policy_identity:
            events = repo.load_events(str(previous["session_id"]))
            idempotency = repo.load_idempotency(str(previous["session_id"]))
            legacy = ledger_from_session(previous, events, idempotency)
            legacy.close_session(reason_code="POLICY_INCOMPATIBLE")
            details["legacy_session_closed"] = True
        return None, details
    events = repo.load_events(str(previous["session_id"]))
    idempotency = repo.load_idempotency(str(previous["session_id"]))
    ledger = ledger_from_session(previous, events, idempotency)
    details["reason"] = "RESTORED"
    details["same_session"] = True
    details["session_id"] = ledger.session_id
    if ledger.execution_authority == "BLOCKED":
        details["env_override"] = _execution_gate_env_name(str(ledger.execution_mode))
    return ledger, details
