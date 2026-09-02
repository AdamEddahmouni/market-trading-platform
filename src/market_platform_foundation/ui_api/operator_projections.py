"""Operator workstation state API (watchlists, recents, workspace, captures, startup)."""

from __future__ import annotations

import os
import socket
import time
from pathlib import Path
from typing import Any

from ..local_state.capture_index import refresh_capture_catalog
from ..local_state.paths import persistence_enabled, state_dir
from ..local_state.schema import LAYOUT_SCHEMA_VERSION, SCHEMA_VERSION
from ..local_state.startup import open_local_state, startup_report
from ..market_data.live_config import (
    live_internal_simulation_enabled,
    live_observational_enabled,
    moomoo_live_enabled,
)
from ..operating_modes import live_execution_env_enabled, paper_execution_env_enabled
from .operator_config import PROVIDER_FIELDS, build_config_payload, provider_env_path, write_provider_values
from .store import ReplayStore


def _repo():
    return open_local_state()


def build_startup_payload(store: ReplayStore) -> dict[str, Any]:
    from ..market_data.live_runtime import get_live_runtime
    from ..market_data.provider_lifecycle import ProviderConnectionState

    runtime = get_live_runtime(create=False)
    live_healthy = False
    if runtime is not None:
        live_healthy = runtime.lifecycle.connection_state in {
            ProviderConnectionState.CONNECTED,
            ProviderConnectionState.CONNECTED_DEGRADED,
        } and int(getattr(runtime, "_fresh_event_count", 0)) > 0
    report = startup_report(live_healthy=live_healthy)
    report["restore_details"] = getattr(store, "restore_details", {})
    report["execution_deferred"] = getattr(store, "execution_deferred", False)
    report["active_session_id"] = store.paper_ledger.session_id
    report["safety"] = {
        "IMP_LIVE_EXECUTION": live_execution_env_enabled(),
        "IMP_LIVE_INTERNAL_SIMULATION": live_internal_simulation_enabled(),
        "IMP_LIVE_OBSERVATIONAL": live_observational_enabled(),
        "IMP_MOOMOO_LIVE": moomoo_live_enabled(),
        "IMP_PAPER_EXECUTION": paper_execution_env_enabled(),
        "read_only": True,
    }
    return report


def build_operator_state_payload(store: ReplayStore) -> dict[str, Any]:
    repo = _repo()
    watchlists = [] if repo is None else repo.list_watchlists()
    recents = [] if repo is None else repo.list_recent_instruments()
    workspace = None if repo is None else repo.load_active_workspace()
    prefs = {} if repo is None else repo.get_preferences()
    captures = [] if repo is None else repo.list_captures()
    sessions = [] if repo is None else repo.list_sessions()
    from .operator_instrument import resolve_active_operator_instrument

    active_instrument, active_source = resolve_active_operator_instrument(store)
    return {
        "active_instrument": active_instrument,
        "active_instrument_source": active_source,
        "captures": captures,
        "layout_schema_version": LAYOUT_SCHEMA_VERSION,
        "persistence_enabled": persistence_enabled(),
        "preferences": prefs,
        "recent_instruments": recents,
        "research_runs": [] if repo is None else repo.list_research_runs(),
        "restore_details": getattr(store, "restore_details", {}),
        "safety": {
            "IMP_LIVE_EXECUTION": live_execution_env_enabled(),
            "IMP_LIVE_INTERNAL_SIMULATION": live_internal_simulation_enabled(),
            "IMP_LIVE_OBSERVATIONAL": live_observational_enabled(),
            "IMP_MOOMOO_LIVE": moomoo_live_enabled(),
            "IMP_PAPER_EXECUTION": paper_execution_env_enabled(),
            "read_only": True,
        },
        "schema_version": SCHEMA_VERSION,
        "sessions": sessions,
        "state_dir": str(state_dir()),
        "watchlists": watchlists,
        "workspace": workspace,
    }


def build_operator_readiness_payload(store: ReplayStore) -> dict[str, Any]:
    from tools.platform.bootstrap import collect_preflight
    from tools.provider_readiness import collect_readiness

    def probe_local(host: str, port: int) -> bool:
        try:
            with socket.create_connection((host, port), timeout=0.25):
                return True
        except OSError:
            return False

    preflight = collect_preflight()
    provider_report = collect_readiness(
        os.environ,
        repository_root=Path(__file__).resolve().parents[3],
        probe_local=probe_local,
        probe_local_services=True,
    )
    labels = {
        "finviz": "Finviz discovery",
        "moomoo_observational": "Moomoo observational",
        "ibkr_observational": "IBKR observational",
        "anthropic": "Anthropic assistant",
    }
    providers: list[dict[str, Any]] = []
    for row in provider_report.get("providers", []):
        item = dict(row)
        provider_id = str(row.get("provider", "provider"))
        item["label"] = labels.get(provider_id, provider_id.replace("_", " ").title())
        item["next_action"] = str(row.get("next_action") or "No action required.")
        providers.append(item)
    provider_action = any(
        row.get("gate_state") == "ENABLED"
        and row.get("transport_state") in {"UNAVAILABLE", "BLOCKED_NON_LOOPBACK"}
        for row in providers
    )
    status = str(preflight["status"])
    if status == "READY" and provider_action:
        status = "ACTION_REQUIRED"
    return {
        "schema_version": "operator-readiness/1.0",
        "status": status,
        "checks": preflight["checks"],
        "providers": providers,
        "secrets_included": False,
        "as_of_context": {
            "data_mode": store.data_mode,
            "execution_mode": store.execution_mode,
            "execution_authority": store.execution_authority,
        },
    }


def build_operator_config_payload() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[3]
    return build_config_payload(
        path=provider_env_path(root=root),
        environment=os.environ,
        environment_path=root / ".env",
    )


def save_provider_config(body: dict[str, Any]) -> dict[str, Any]:
    provider = str(body.get("provider") or "").strip().lower()
    values = body.get("values")
    if not provider or not isinstance(values, dict):
        raise ValueError("PROVIDER_AND_VALUES_REQUIRED")
    root = Path(__file__).resolve().parents[3]
    destination = root / ".env" if provider == "anthropic" else provider_env_path(root=root)
    write_provider_values(provider, {str(key): str(value) for key, value in values.items()}, path=destination)
    return build_operator_config_payload()


def queue_provider_refresh(provider: str) -> dict[str, Any]:
    normalized = str(provider or "").strip().lower()
    if normalized not in {provider_id for provider_id, _, _ in PROVIDER_FIELDS}:
        raise ValueError("PROVIDER_NOT_SUPPORTED")
    operation = {
        "operation_id": f"provider-refresh-{normalized}-{os.getpid()}-{int(time.time() * 1000)}",
        "action": "provider_refresh",
        "provider": normalized,
        "status": "QUEUED",
        "created_at": time.time(),
        "secrets_included": False,
    }
    root = Path(__file__).resolve().parents[3]
    from tools.platform.control_service import _write_operation

    _write_operation(root, operation)
    return operation


def update_watchlist(body: dict[str, Any]) -> dict[str, Any]:
    repo = _repo()
    if repo is None:
        raise ValueError("LOCAL_STATE_DISABLED")
    default = repo.ensure_default_watchlist()
    watchlist_id = str(body.get("watchlist_id") or default["watchlist_id"])
    instruments = [str(item).upper() for item in body.get("instrument_ids") or []]
    repo.replace_watchlist_items(watchlist_id, instruments)
    return {"watchlists": repo.list_watchlists()}


def record_recent(body: dict[str, Any]) -> dict[str, Any]:
    repo = _repo()
    if repo is None:
        raise ValueError("LOCAL_STATE_DISABLED")
    instrument_id = str(body.get("instrument_id") or "").upper()
    if not instrument_id:
        raise ValueError("INSTRUMENT_ID_REQUIRED")
    repo.record_recent_instrument(instrument_id)
    source = str(body.get("source") or "").upper()
    if source == "EXPLORE":
        from .operator_instrument import persist_explore_selected_instrument

        persist_explore_selected_instrument(instrument_id)
    return {"recent_instruments": repo.list_recent_instruments()}


def save_workspace(body: dict[str, Any]) -> dict[str, Any]:
    repo = _repo()
    if repo is None:
        raise ValueError("LOCAL_STATE_DISABLED")
    layout = body.get("layout")
    if not isinstance(layout, dict):
        raise ValueError("WORKSPACE_LAYOUT_REQUIRED")
    saved = repo.save_workspace(layout, workspace_id=body.get("workspace_id"), name=str(body.get("name") or "Active"))
    return saved


def save_preferences(body: dict[str, Any]) -> dict[str, Any]:
    repo = _repo()
    if repo is None:
        raise ValueError("LOCAL_STATE_DISABLED")
    prefs = body.get("preferences")
    if not isinstance(prefs, dict):
        raise ValueError("PREFERENCES_REQUIRED")
    # Safety-relevant env keys must never be writable through preferences:
    # the IMP_ catch-all plus any key carrying an execution/live/provider token.
    blocked_exact = {"EXECUTION_ENABLE"}
    blocked_substrings = ("EXECUTION", "LIVE", "TRADIER", "MOOMOO")
    for key, value in prefs.items():
        key_str = str(key)
        key_upper = key_str.upper()
        if (
            key_str.startswith("IMP_")
            or key_str in blocked_exact
            or any(token in key_upper for token in blocked_substrings)
        ):
            raise ValueError("SAFETY_ENV_NOT_WRITABLE")
        repo.set_preference(key_str, value)
    return {"preferences": repo.get_preferences()}


def refresh_captures() -> dict[str, Any]:
    repo = _repo()
    if repo is None:
        raise ValueError("LOCAL_STATE_DISABLED")
    indexed = refresh_capture_catalog(repo)
    return {"captures": repo.list_captures(), "indexed": len(indexed)}


def replay_capture(body: dict[str, Any]) -> dict[str, Any]:
    capture_id = str(body.get("capture_id") or "")
    repo = _repo()
    if repo is None:
        raise ValueError("LOCAL_STATE_DISABLED")
    captures = {row["capture_id"]: row for row in repo.list_captures()}
    row = captures.get(capture_id)
    if row is None:
        raise ValueError("CAPTURE_NOT_FOUND")
    if row["status"] != "AVAILABLE":
        raise ValueError(f"CAPTURE_{row['status']}")
    # Provenance only: the caller (runtime/store) owns feed selection; mutating
    # os.environ from a request thread leaked state across requests and had no
    # unset path. data_mode uses the canonical DATA_MODES label accepted by
    # build_operating_context.
    return {
        "capture_id": capture_id,
        "data_mode": "HISTORICAL_CAPTURE",
        "events_path": row.get("events_path"),
        "provenance": f"HISTORICAL_CAPTURE · MOOMOO CAPTURE · {row.get('events_path')}",
        "status": "READY",
    }
