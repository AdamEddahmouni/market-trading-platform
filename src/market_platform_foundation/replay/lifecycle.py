"""Deterministic availability-aware replay lifecycle stub."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..contracts.identity import sort_events
from ..contracts.temporal import check_tc001, decision_hash


@dataclass
class ReplayState:
    replay_clock: int = 0
    visible_events: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    artifact_manifest: list[str] = field(default_factory=list)


def dispatch_visible(events: list[dict[str, Any]], replay_clock: int) -> list[dict[str, Any]]:
    return [
        event
        for event in events
        if int(event["available_time"]) <= replay_clock
    ]


def run_replay(
    events: list[dict[str, Any]],
    *,
    clocks: list[int],
    decision_times: list[int],
) -> ReplayState:
    ordered = sort_events(events)
    state = ReplayState()
    for clock in clocks:
        state.replay_clock = clock
        newly_visible = dispatch_visible(ordered, clock)
        for event in newly_visible:
            if event not in state.visible_events:
                state.visible_events.append(event)
                state.artifact_manifest.append(str(event["normalized_event_id"]))
        if decision_times:
            decision_time = decision_times[0]
            consumed = [
                {"available_time": event["available_time"], "normalized_event_id": event["normalized_event_id"]}
                for event in state.visible_events
            ]
            status, reasons = check_tc001(consumed, decision_time)
            decision = {
                "decision_time": decision_time,
                "reason_codes": reasons,
                "replay_clock": clock,
                "status": status,
                "visible_event_count": len(state.visible_events),
            }
            decision["decision_hash"] = decision_hash(decision)
            state.decisions.append(decision)
            decision_times = decision_times[1:]
    return state


def run_root_hash(state: ReplayState) -> str:
    body = {
        "artifact_manifest": state.artifact_manifest,
        "decisions": state.decisions,
        "visible_event_ids": [event["normalized_event_id"] for event in state.visible_events],
    }
    return sha256_bytes(canonical_bytes(body))
