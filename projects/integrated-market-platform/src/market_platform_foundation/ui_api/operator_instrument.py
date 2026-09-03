"""Canonical active operator instrument — one source, ordered fallbacks.

Identity only. Does not persist or restore execution eligibility.
"""

from __future__ import annotations

from typing import Any

from ..local_state.startup import open_local_state
from ..market_data.live_config import live_observational_enabled

EXPLORE_SELECTED_PREFERENCE = "explore_selected_instrument"
SESSION_PREFERRED_PREFERENCE = "paper_session_preferred_instrument"

SOURCE_ORDER_TICKET = "ORDER_TICKET"
SOURCE_WORKSPACE = "WORKSPACE"
SOURCE_EXPLORE = "EXPLORE"
SOURCE_PAPER_SESSION = "PAPER_SESSION"
SOURCE_SCOPE = "SCOPE"
SOURCE_FIXTURE_DEFAULT = "FIXTURE_DEFAULT"
SOURCE_NONE = "NONE"


def normalize_instrument_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text or None


def _preference_instrument(repo: Any, key: str) -> str | None:
    if repo is None:
        return None
    prefs = repo.get_preferences()
    return normalize_instrument_id(prefs.get(key))


def _workspace_instrument(repo: Any) -> str | None:
    if repo is None:
        return None
    workspace = repo.load_active_workspace()
    if not workspace or workspace.get("fallback"):
        return None
    layout = workspace.get("layout") or {}
    return normalize_instrument_id(layout.get("selected_instrument"))


def _first_scoped_symbol() -> str | None:
    from ..market_data.live_runtime import get_live_runtime

    runtime = get_live_runtime(create=False)
    if runtime is None or not runtime.scope_symbols:
        return None
    return normalize_instrument_id(runtime.scope_symbols[0])


def persist_explore_selected_instrument(instrument_id: str) -> None:
    ident = normalize_instrument_id(instrument_id)
    if ident is None:
        return
    repo = open_local_state()
    if repo is None:
        return
    repo.set_preference(EXPLORE_SELECTED_PREFERENCE, ident)


def persist_session_preferred_instrument(instrument_id: str) -> None:
    ident = normalize_instrument_id(instrument_id)
    if ident is None:
        return
    repo = open_local_state()
    if repo is None:
        return
    repo.set_preference(SESSION_PREFERRED_PREFERENCE, ident)


def resolve_active_operator_instrument(
    store: Any,
    *,
    explicit: Any = None,
) -> tuple[str | None, str]:
    """Resolve the operator instrument.

    Order:
      explicit OrderTicket selection
      active Workspace instrument
      selected Explore instrument
      paper-session preferred instrument if explicitly stored
      first scoped symbol
      no instrument
    FIXTURE_REPLAY may then fall back to the admitted fixture identity.
    LIVE_OBSERVATIONAL never silently falls back to that fixture.
    """
    ticket = normalize_instrument_id(explicit)
    if ticket:
        return ticket, SOURCE_ORDER_TICKET

    repo = open_local_state()
    workspace = _workspace_instrument(repo)
    if workspace:
        return workspace, SOURCE_WORKSPACE

    explore = _preference_instrument(repo, EXPLORE_SELECTED_PREFERENCE)
    if explore:
        return explore, SOURCE_EXPLORE

    session_preferred = _preference_instrument(repo, SESSION_PREFERRED_PREFERENCE)
    if session_preferred:
        return session_preferred, SOURCE_PAPER_SESSION

    scoped = _first_scoped_symbol()
    if scoped:
        return scoped, SOURCE_SCOPE

    if live_observational_enabled():
        return None, SOURCE_NONE

    fixture = normalize_instrument_id(getattr(store, "instrument_id", None))
    if fixture:
        return fixture, SOURCE_FIXTURE_DEFAULT
    return None, SOURCE_NONE
