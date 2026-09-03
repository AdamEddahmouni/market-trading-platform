"""Server-assembled AssistantContext snapshot for grounded retrieval."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..ui_api.store import ReplayStore


def build_evidence_context(
    store: ReplayStore,
    *,
    selection_ref: str | None = None,
) -> dict[str, Any]:
    """Assemble evidence context from ReplayStore projections (stdlib-only)."""
    from ..ui_api.projections import (
        build_as_of_context,
        build_capabilities,
        build_explain_payload,
        build_inspect_payload,
        build_quality_summary,
        build_workspace_institutional_flow_payload,
    )

    instrument_id = store.instrument_id
    institutional = build_workspace_institutional_flow_payload(store, instrument_id)
    families = institutional.get("families", [])
    if not isinstance(families, list):
        families = []

    available_explain_refs: list[str] = [
        "explain:replay:context",
        "explain:quality:system",
    ]
    for row in families:
        if not isinstance(row, dict):
            continue
        if row.get("available") and row.get("explanation_ref"):
            available_explain_refs.append(str(row["explanation_ref"]))

    strategy_rows = store.strategy.get("interpretations", [])
    if isinstance(strategy_rows, list):
        for row in strategy_rows:
            if not isinstance(row, dict):
                continue
            obs_time = row.get("observation_time", row.get("prediction_cutoff"))
            if obs_time is not None and int(obs_time) <= store.prediction_cutoff():
                available_explain_refs.append(f"explain:strategy:{int(obs_time)}")

    if selection_ref:
        explain_candidate = selection_ref.replace("inspect:", "explain:", 1)
        if explain_candidate not in available_explain_refs:
            available_explain_refs.append(explain_candidate)

    return {
        "as_of_context": build_as_of_context(store),
        "available_explain_refs": tuple(sorted(set(available_explain_refs))),
        "capabilities": build_capabilities(store),
        "institutional_flow": institutional,
        "instrument_id": instrument_id,
        "logical_id": "assistant.evidence_context",
        "quality": build_quality_summary(store),
        "replay_session_id": store.session_id,
        "resolve_explain": lambda ref: build_explain_payload(store, ref),
        "resolve_inspect": lambda ref: build_inspect_payload(store, ref),
        "selection_ref": selection_ref,
    }
