"""Narrow adaptation repository queries (BUILD 24)."""

from __future__ import annotations

from ..research_experiments.types import ResearchLifecycleState
from .types import ResearchTriggerV1


def query_triggers_by_dedup_key(
    triggers: tuple[ResearchTriggerV1, ...],
    *,
    dedup_key: str,
) -> tuple[ResearchTriggerV1, ...]:
    return tuple(trigger for trigger in triggers if trigger.dedup_key == dedup_key)


def query_open_research_dedup_keys(
    lifecycle_events,
    *,
    findings_metadata: tuple[dict, ...] = (),
) -> frozenset[str]:
    """Return dedup keys for research tracks that remain open."""

    closed_states = {
        ResearchLifecycleState.SUPPORTED.value,
        ResearchLifecycleState.NOT_SUPPORTED.value,
        ResearchLifecycleState.REJECTED.value,
        ResearchLifecycleState.CANCELLED.value,
        ResearchLifecycleState.SUPERSEDED.value,
    }
    open_keys: set[str] = set()
    for metadata in findings_metadata:
        trigger_id = metadata.get("research_trigger_id")
        dedup_key = metadata.get("cohort_fingerprint") or metadata.get("dedup_key")
        if trigger_id and dedup_key:
            entity_id = metadata.get("finding_id")
            states = {
                event.lifecycle_state.value
                for event in lifecycle_events
                if event.entity_id == entity_id
            }
            if states and not states.intersection(closed_states):
                open_keys.add(str(dedup_key))
    return frozenset(open_keys)


def consumed_evidence_ref_ids(triggers: tuple[ResearchTriggerV1, ...]) -> frozenset[str]:
    ids: set[str] = set()
    for trigger in triggers:
        for ref in trigger.source_evidence_refs:
            ids.add(ref.id)
    return frozenset(ids)


__all__ = [
    "consumed_evidence_ref_ids",
    "query_open_research_dedup_keys",
    "query_triggers_by_dedup_key",
]
