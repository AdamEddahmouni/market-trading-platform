"""UI API projections for Paper forward-testing bridge."""

from __future__ import annotations

import time
from typing import Any

from ..intelligence.paper_forward_bridge import (
    ForwardTestMode,
    ForwardTestRepository,
    ForwardTestService,
    ForwardTestServiceError,
    create_forward_test_repository,
)
from ..local_state.startup import open_local_state
from ..operating_modes import paper_execution_env_enabled
from .account_registry import resolve_paper_portfolio_identity
from .paper_projections import _paper_envelope, preview_paper_order, submit_paper_order
from .store import ReplayStore


def _forward_store(store: ReplayStore) -> ForwardTestRepository:
    bucket = getattr(store, "forward_test_store", None)
    if bucket is None:
        repo = open_local_state()
        bucket = create_forward_test_repository(
            connection=repo.connection if repo is not None else None,
        )
        store.forward_test_store = bucket
    return bucket


def _forward_service(store: ReplayStore) -> ForwardTestService:
    return ForwardTestService(_forward_store(store))


def _require_account(body: dict[str, Any], store: ReplayStore) -> tuple[str, str]:
    requested = body.get("account_id")
    identity = resolve_paper_portfolio_identity(store)
    account_id = str(requested or identity.account_id)
    if str(identity.account_id) != account_id:
        raise ValueError("FORWARD_TEST_ACCOUNT_MISMATCH")
    mode = str(identity.mode).upper()
    if mode != "PAPER":
        raise ValueError("FORWARD_TEST_PAPER_MODE_REQUIRED")
    return account_id, mode


def build_forward_test_sessions_payload(store: ReplayStore, *, account_id: str) -> dict[str, Any]:
    service = _forward_service(store)
    sessions = service._store.list_sessions(account_id=account_id)
    return _paper_envelope(
        store,
        {
            "forward_tests": {
                "schema_version": "intelligence/paper_forward_bridge/api/1.0.0",
                "sessions": [item.to_dict() for item in sessions],
            }
        },
    )


def build_forward_test_decisions_payload(
    store: ReplayStore,
    *,
    account_id: str,
    session_id: str | None = None,
) -> dict[str, Any]:
    service = _forward_service(store)
    decisions = service.list_decisions(account_id=account_id, session_id=session_id)
    return _paper_envelope(
        store,
        {
            "forward_tests": {
                "schema_version": "intelligence/paper_forward_bridge/api/1.0.0",
                "decisions": [item.to_dict() for item in decisions],
            }
        },
    )


def build_forward_test_detail_payload(
    store: ReplayStore,
    *,
    account_id: str,
    forward_test_id: str,
) -> dict[str, Any]:
    service = _forward_service(store)
    decision = service.get_decision(forward_test_id=forward_test_id, account_id=account_id)
    return _paper_envelope(
        store,
        {
            "forward_test": decision.to_dict(),
        },
    )


def create_forward_test_session(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    account_id, mode = _require_account(body, store)
    service = _forward_service(store)
    universe = tuple(str(item).upper() for item in body.get("universe") or [])
    if not universe:
        raise ValueError("FORWARD_TEST_UNIVERSE_REQUIRED")
    campaign_id = str(body.get("campaign_id", "")).strip()
    cohort_arm = str(body.get("cohort_arm", "")).strip()
    if not campaign_id:
        raise ValueError("FORWARD_TEST_CAMPAIGN_ID_REQUIRED")
    if not cohort_arm:
        raise ValueError("FORWARD_TEST_COHORT_ARM_REQUIRED")
    try:
        session = service.create_session(
            account_id=account_id,
            mode=mode,
            strategy_id=str(body.get("strategy_id", "")).strip(),
            strategy_version=str(body.get("strategy_version", "")).strip() or "1.0.0",
            universe=universe,
            evaluation_horizon_ns=int(body.get("evaluation_horizon_ns", 0)),
            created_at_ns=int(body.get("created_at_ns") or time.time_ns()),
            campaign_id=campaign_id,
            cohort_arm=cohort_arm,
            manifest_fingerprint=body.get("manifest_fingerprint"),
            config=body.get("config") if isinstance(body.get("config"), dict) else None,
        )
    except ForwardTestServiceError as exc:
        raise ValueError(str(exc)) from exc
    return _paper_envelope(store, {"session": session.to_dict()})


def create_forward_test_decision(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    account_id, mode = _require_account(body, store)
    service = _forward_service(store)
    test_mode_raw = str(body.get("test_mode", "SIGNAL_ONLY")).upper()
    test_mode = ForwardTestMode(test_mode_raw)
    run_kind_raw = str(body.get("run_kind", "FORWARD_TEST")).upper()
    if run_kind_raw != "FORWARD_TEST":
        raise ValueError("FORWARD_TEST_BACKTEST_BOUNDARY_VIOLATION")
    try:
        decision = service.create_decision(
            account_id=account_id,
            mode=mode,
            session_id=body.get("session_id"),
            symbol=str(body.get("symbol", "")).upper(),
            direction=str(body.get("direction", "")).upper(),
            decision_time_ns=int(body.get("decision_time_ns") or time.time_ns()),
            source_time_ns=int(body.get("source_time_ns") or body.get("decision_time_ns") or time.time_ns()),
            strategy_id=str(body.get("strategy_id", "")).strip(),
            strategy_version=str(body.get("strategy_version", "")).strip() or "1.0.0",
            test_mode=test_mode,
            quantity=int(body["quantity"]) if body.get("quantity") is not None else None,
            evaluation_horizon_ns=int(body["evaluation_horizon_ns"])
            if body.get("evaluation_horizon_ns") is not None
            else None,
            decision_payload=body.get("decision_payload")
            if isinstance(body.get("decision_payload"), dict)
            else None,
            research_artifact_ref=body.get("research_artifact_ref"),
            evidence_class=body.get("evidence_class"),
        )
    except ForwardTestServiceError as exc:
        raise ValueError(str(exc)) from exc
    return _paper_envelope(store, {"forward_test": decision.to_dict()})


def lock_forward_test_decision(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    account_id, _mode = _require_account(body, store)
    forward_test_id = str(body.get("forward_test_id", "")).strip()
    if not forward_test_id:
        raise ValueError("FORWARD_TEST_ID_REQUIRED")
    service = _forward_service(store)
    decision = service.lock_decision(
        forward_test_id=forward_test_id,
        account_id=account_id,
        locked_at_ns=int(body.get("locked_at_ns") or time.time_ns()),
    )
    return _paper_envelope(store, {"forward_test": decision.to_dict()})


def submit_forward_test_to_paper(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    if not paper_execution_env_enabled():
        raise ValueError("PAPER_EXECUTION_NOT_AUTHORIZED")
    account_id, _mode = _require_account(body, store)
    forward_test_id = str(body.get("forward_test_id", "")).strip()
    if not forward_test_id:
        raise ValueError("FORWARD_TEST_ID_REQUIRED")
    service = _forward_service(store)
    decision = service.get_decision(forward_test_id=forward_test_id, account_id=account_id)
    if decision.test_mode == ForwardTestMode.EXECUTION:
        preview_body = service.build_paper_order_request(
            forward_test_id=forward_test_id,
            account_id=account_id,
            instrument_id=body.get("instrument_id"),
        )
        preview = preview_paper_order(store, preview_body)
        submit_body = dict(preview_body)
        submit_body["preview_token"] = preview.get("preview", {}).get("preview_token")
        try:
            submit_result = submit_paper_order(store, submit_body)
        except ValueError as exc:
            rejected = service.submit_to_paper(
                forward_test_id=forward_test_id,
                account_id=account_id,
                submitted_at_ns=int(body.get("submitted_at_ns") or time.time_ns()),
                reject_reason=str(exc),
            )
            return _paper_envelope(
                store,
                {
                    "forward_test": rejected.to_dict(),
                    "paper_submit_error": str(exc),
                },
            )
        order = submit_result.get("order") or {}
        updated = service.submit_to_paper(
            forward_test_id=forward_test_id,
            account_id=account_id,
            submitted_at_ns=int(body.get("submitted_at_ns") or time.time_ns()),
            paper_order_id=str(order.get("order_id") or ""),
            paper_intent_id=str(order.get("intent_id") or ""),
        )
        return _paper_envelope(
            store,
            {
                "forward_test": updated.to_dict(),
                "paper_order": order,
            },
        )
    updated = service.submit_to_paper(
        forward_test_id=forward_test_id,
        account_id=account_id,
        submitted_at_ns=int(body.get("submitted_at_ns") or time.time_ns()),
    )
    return _paper_envelope(store, {"forward_test": updated.to_dict()})


def attach_forward_test_observation(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    account_id, _mode = _require_account(body, store)
    forward_test_id = str(body.get("forward_test_id", "")).strip()
    payload = body.get("payload")
    if not forward_test_id:
        raise ValueError("FORWARD_TEST_ID_REQUIRED")
    if not isinstance(payload, dict):
        raise ValueError("FORWARD_TEST_OBSERVATION_PAYLOAD_REQUIRED")
    service = _forward_service(store)
    decision = service.attach_observation(
        forward_test_id=forward_test_id,
        account_id=account_id,
        observed_at_ns=int(body.get("observed_at_ns") or time.time_ns()),
        source_time_ns=int(body.get("source_time_ns") or body.get("observed_at_ns") or time.time_ns()),
        payload=payload,
    )
    return _paper_envelope(store, {"forward_test": decision.to_dict()})


def evaluate_forward_test_decision(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    account_id, _mode = _require_account(body, store)
    forward_test_id = str(body.get("forward_test_id", "")).strip()
    if not forward_test_id:
        raise ValueError("FORWARD_TEST_ID_REQUIRED")
    service = _forward_service(store)
    try:
        decision = service.evaluate(
            forward_test_id=forward_test_id,
            account_id=account_id,
            now_ns=int(body.get("now_ns") or time.time_ns()),
            force=bool(body.get("force")),
        )
    except ForwardTestServiceError as exc:
        raise ValueError(str(exc)) from exc
    return _paper_envelope(store, {"forward_test": decision.to_dict()})


def build_forward_test_session_summary_payload(
    store: ReplayStore,
    *,
    account_id: str,
    session_id: str,
) -> dict[str, Any]:
    service = _forward_service(store)
    summary = service.get_session_summary(session_id=session_id, account_id=account_id)
    return _paper_envelope(store, summary)
