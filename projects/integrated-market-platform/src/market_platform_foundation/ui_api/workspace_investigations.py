"""Durable operator investigation context; never an execution authority."""

from __future__ import annotations

from typing import Any

from ..local_state.startup import open_local_state


def _repo():
    repo = open_local_state()
    if repo is None:
        raise ValueError("LOCAL_STATE_DISABLED")
    return repo


def _require_writable_context(*, data_mode: str, execution_mode: str, execution_authority: str) -> None:
    if execution_mode != "INTERNAL_SIMULATION" or execution_authority != "PAPER_ONLY":
        raise PermissionError("PAPER_AUTHORITY_REQUIRED")


def list_investigations() -> dict[str, Any]:
    return {"investigations": _repo().list_investigations()}


def get_investigation(workspace_id: str) -> dict[str, Any]:
    row = _repo().get_investigation(workspace_id)
    if row is None:
        raise KeyError(workspace_id)
    return row


def create_investigation(
    body: dict[str, Any], *, data_mode: str, execution_mode: str = "NONE",
    execution_authority: str = "BLOCKED", opportunity_repository: Any = None,
) -> dict[str, Any]:
    _require_writable_context(data_mode=data_mode, execution_mode=execution_mode, execution_authority=execution_authority)
    instrument_id = body.get("instrument_id")
    title = body.get("title")
    source_kind = body.get("source_kind", "instrument")
    source_id = body.get("source_id")
    opportunity_id = body.get("opportunity_id")
    if not isinstance(instrument_id, str) or not instrument_id.strip() or len(instrument_id) > 120:
        raise ValueError("INSTRUMENT_ID_INVALID")
    if not isinstance(title, str) or not title.strip() or len(title) > 160:
        raise ValueError("WORKSPACE_TITLE_INVALID")
    if source_kind not in {"instrument", "radar_attention"}:
        raise ValueError("WORKSPACE_SOURCE_KIND_INVALID")
    if source_kind == "radar_attention" and (not isinstance(source_id, str) or not source_id.strip()):
        raise ValueError("WORKSPACE_SOURCE_ID_REQUIRED")
    if source_id is not None and (not isinstance(source_id, str) or len(source_id) > 160):
        raise ValueError("WORKSPACE_SOURCE_ID_INVALID")
    if opportunity_id is not None and (not isinstance(opportunity_id, str) or len(opportunity_id) > 160):
        raise ValueError("WORKSPACE_OPPORTUNITY_ID_INVALID")
    if opportunity_id and source_kind != "radar_attention":
        raise ValueError("WORKSPACE_OPPORTUNITY_SOURCE_INVALID")
    if opportunity_id:
        getter = getattr(opportunity_repository, "get_opportunity", None)
        opportunity = getter(opportunity_id) if callable(getter) else None
        if opportunity is None:
            raise ValueError("WORKSPACE_OPPORTUNITY_NOT_FOUND")
        if instrument_id.strip() not in opportunity.scope.instrument_ids:
            raise ValueError("WORKSPACE_OPPORTUNITY_INSTRUMENT_MISMATCH")
    return _repo().create_investigation(
        title=title.strip(), instrument_id=instrument_id.strip(),
        source_kind=source_kind, source_id=source_id,
        opportunity_id=opportunity_id.strip() if isinstance(opportunity_id, str) else None,
    )


def save_note(
    workspace_id: str, body: dict[str, Any], *, data_mode: str,
    execution_mode: str = "NONE", execution_authority: str = "BLOCKED",
) -> dict[str, Any]:
    _require_writable_context(data_mode=data_mode, execution_mode=execution_mode, execution_authority=execution_authority)
    note = body.get("note")
    expected_note = body.get("expected_note")
    if not isinstance(note, str) or len(note) > 10000:
        raise ValueError("WORKSPACE_NOTE_INVALID")
    if not isinstance(expected_note, str) or len(expected_note) > 10000:
        raise ValueError("WORKSPACE_EXPECTED_NOTE_INVALID")
    row = _repo().update_investigation_note(workspace_id, note, expected_note)
    if row is None:
        raise KeyError(workspace_id)
    return row
