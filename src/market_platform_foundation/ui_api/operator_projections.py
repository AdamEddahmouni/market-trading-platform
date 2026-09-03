"""Operator workstation state API (watchlists, recents, workspace, captures, startup)."""

from __future__ import annotations

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
