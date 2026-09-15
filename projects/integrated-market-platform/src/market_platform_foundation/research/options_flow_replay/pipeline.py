"""Replay fixture → transparent options-flow evidence artifact (cold path only)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifact import build_evidence_artifact
from .classify import decompose_replay_print
from .dataset import verify_and_load_replay_slice
from .models import DEFAULT_OPTIONS_FLOW_REPLAY_QUERY, OptionsFlowReplayQueryV1


def run_options_flow_replay_pipeline(
    query: OptionsFlowReplayQueryV1 | None = None,
    *,
    slice_path: Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    query = query or DEFAULT_OPTIONS_FLOW_REPLAY_QUERY
    payload, dataset = verify_and_load_replay_slice(slice_path=slice_path)
    if dataset.symbol != query.instrument_id:
        raise ValueError("OPTIONS_FLOW_REPLAY_INSTRUMENT_MISMATCH")
    if dataset.admission_id != query.admission_id:
        raise ValueError("OPTIONS_FLOW_REPLAY_ADMISSION_MISMATCH")
    activities = payload.get("activities") or []
    decomposed: list[dict[str, Any]] = []
    for index, activity in enumerate(activities):
        if not isinstance(activity, dict):
            continue
        row = decompose_replay_print(activity, index=index)
        trade_class = (row.get("trade_classification") or {}).get("trade_class")
        if trade_class in query.include_trade_classes:
            decomposed.append(row)
    stamp = generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return build_evidence_artifact(
        query=query,
        dataset=dataset,
        decomposed_prints=decomposed,
        generated_at=stamp,
    )


__all__ = ["run_options_flow_replay_pipeline"]
