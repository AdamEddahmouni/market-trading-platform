"""Admitted replay fixture loader with SHA binding."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...canonical import load_json_strict, sha256_bytes

_DEFAULT_SLICE = (
    Path(__file__).resolve().parents[4]
    / "tests"
    / "fixtures"
    / "research"
    / "options_flow_replay_admitted_slice.json"
)


@dataclass(frozen=True, slots=True)
class AdmittedOptionsFlowReplayDataset:
    admission_id: str
    fixture_id: str
    symbol: str
    replay_mode: str
    source_sha256: str
    collection_relative_path: str
    activity_count: int


def verify_and_load_replay_slice(
    *,
    slice_path: Path | None = None,
) -> tuple[dict[str, Any], AdmittedOptionsFlowReplayDataset]:
    path = slice_path or _DEFAULT_SLICE
    raw_bytes = path.read_bytes()
    source_sha256 = sha256_bytes(raw_bytes)
    payload = load_json_strict(path)
    if not isinstance(payload, dict):
        raise ValueError("OPTIONS_FLOW_REPLAY_SLICE_INVALID")
    activities = payload.get("activities")
    if not isinstance(activities, list):
        raise ValueError("OPTIONS_FLOW_REPLAY_ACTIVITIES_INVALID")
    rel = path.relative_to(path.resolve().parents[4]).as_posix()
    dataset = AdmittedOptionsFlowReplayDataset(
        admission_id=str(payload.get("admission_id", "")),
        fixture_id=str(payload.get("fixture_id", "")),
        symbol=str(payload.get("symbol", "")).upper(),
        replay_mode=str(payload.get("replay_mode", "SYNTHETIC_FIXTURE_ONLY")),
        source_sha256=source_sha256,
        collection_relative_path=rel,
        activity_count=len(activities),
    )
    if dataset.admission_id != "ADMITTED-OPTIONS-FLOW-REPLAY-NVDA-001":
        raise ValueError("OPTIONS_FLOW_REPLAY_ADMISSION_MISMATCH")
    return payload, dataset


__all__ = ["AdmittedOptionsFlowReplayDataset", "verify_and_load_replay_slice"]
