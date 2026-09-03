"""Availability-aware replay with bar state and quality observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..contracts.identity import sort_events
from ..contracts.temporal import check_tc001, check_tc003, decision_hash
from ..data_quality.observations import consumer_eligibility, evaluate_bar_event
from ..state.bar_book import BarBookState
from ..storage.dataset_cache import DatasetCache
from .lifecycle import dispatch_visible


@dataclass
class QualityReplayState:
    replay_clock: int = 0
    visible_events: list[dict[str, Any]] = field(default_factory=list)
    bar_book: BarBookState = field(default_factory=BarBookState)
    quality_observations: list[dict[str, Any]] = field(default_factory=list)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    artifact_manifest: list[str] = field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0

    def snapshot_quality_by_dimension(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.quality_observations:
            dimension = str(row["dimension"])
            counts[dimension] = counts.get(dimension, 0) + 1
        return counts


def run_quality_replay(
    events: list[dict[str, Any]],
    *,
    clocks: list[int],
    decision_times: list[int],
    cache: DatasetCache | None = None,
) -> QualityReplayState:
    ordered = sort_events(events)
    state = QualityReplayState()
    prior_bars: dict[str, dict[str, Any]] = {}
    for clock in clocks:
        state.replay_clock = clock
        newly_visible = dispatch_visible(ordered, clock)
        for event in newly_visible:
            if event in state.visible_events:
                continue
            state.visible_events.append(event)
            instrument_id = str(event.get("instrument_id", ""))
            prior = prior_bars.get(instrument_id)
            for observation in evaluate_bar_event(event, prior_bar=prior):
                state.quality_observations.append(observation)
            status, _reasons = state.bar_book.apply_event(event)
            if status == "APPLIED":
                state.artifact_manifest.append(str(event["normalized_event_id"]))
                prior_bars[instrument_id] = event
        if not decision_times:
            continue
        decision_time = decision_times[0]
        consumed = [
            {
                "available_time": int(event["available_time"]),
                "normalized_event_id": str(event["normalized_event_id"]),
            }
            for event in state.visible_events
        ]
        tc001_status, tc001_reasons = check_tc001(consumed, decision_time)
        eligibility, eligibility_reasons = consumer_eligibility(state.quality_observations)
        decision = {
            "consumer_eligibility": eligibility,
            "decision_time": decision_time,
            "eligibility_reason_codes": eligibility_reasons,
            "reason_codes": tc001_reasons,
            "replay_clock": clock,
            "status": tc001_status,
            "visible_event_count": len(state.visible_events),
        }
        decision["decision_hash"] = decision_hash(decision)
        state.decisions.append(decision)
        decision_times = decision_times[1:]
    if cache is not None:
        state.cache_hits = cache.hits
        state.cache_misses = cache.misses
    return state


def run_quality_root_hash(state: QualityReplayState) -> str:
    body = {
        "artifact_manifest": state.artifact_manifest,
        "decisions": state.decisions,
        "quality_observation_ids": [
            row["quality_observation_id"] for row in state.quality_observations
        ],
        "visible_event_ids": [event["normalized_event_id"] for event in state.visible_events],
    }
    return sha256_bytes(canonical_bytes(body))


def verify_tc003_on_correction(
    *,
    prior_state: QualityReplayState,
    post_state: QualityReplayState,
    correction_available_time: int,
    replay_clock_at_apply: int,
) -> tuple[str, list[str]]:
    if not prior_state.decisions or not post_state.decisions:
        return "BLOCKED", ["TC003_MISSING_DECISION"]
    prior_hash = str(prior_state.decisions[-1]["decision_hash"])
    post_hash = str(post_state.decisions[-1]["decision_hash"])
    return check_tc003(
        prior_decision_hash=prior_hash,
        post_correction_hash=post_hash,
        correction_available_time=correction_available_time,
        replay_clock_at_apply=replay_clock_at_apply,
    )
