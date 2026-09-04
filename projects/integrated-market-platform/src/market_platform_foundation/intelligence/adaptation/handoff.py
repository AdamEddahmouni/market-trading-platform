"""BUILD 17 observation handoff from research triggers (BUILD 24)."""

from __future__ import annotations

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..research_experiments.identity import derive_finding_id
from ..research_experiments.types import (
    EvidenceTier,
    MetricObservation,
    ResearchFindingType,
    ResearchFindingV1,
)
from .types import ResearchTriggerV1


def register_finding_from_trigger(
    trigger: ResearchTriggerV1,
    *,
    mode: str,
    scenario_id: str | None = None,
) -> ResearchFindingV1:
    """Convert a governed research trigger into a BUILD 17 observation finding."""

    metric_rows: list[MetricObservation] = []
    for metric_name, value in sorted(trigger.observed_metric_summary.items()):
        metric_rows.append(
            MetricObservation(
                metric_name=metric_name,
                value=value,
                sample_count=trigger.sample_counts.get(metric_name, sum(trigger.sample_counts.values())),
            )
        )
    if not metric_rows:
        metric_rows.append(
            MetricObservation(
                metric_name="adaptation_evidence_count",
                value=float(len(trigger.source_evidence_refs)),
                sample_count=sum(trigger.sample_counts.values()) or len(trigger.source_evidence_refs),
            )
        )

    draft = ResearchFindingV1(
        finding_id="DERIVE",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        finding_type=ResearchFindingType.MONITORING_OBSERVATION,
        evaluation_report_id=f"RTRIG-SRC:{trigger.research_trigger_id}",
        evaluation_spec_id=trigger.adaptation_policy_ref,
        cohort_fingerprint=trigger.dedup_key,
        metric_observations=tuple(metric_rows),
        sample_count=sum(trigger.sample_counts.values()) or len(trigger.source_evidence_refs),
        mode=mode,
        scenario_id=scenario_id,
        evidence_tier=EvidenceTier.ACTUAL_LIVE,
        slice_dimension="research_class",
        slice_value=trigger.suggested_research_class.value,
        observation_summary=trigger.observation_summary,
        limitations=trigger.limitations,
        metadata={
            "research_trigger_id": trigger.research_trigger_id,
            "adaptation_assessment_ref": trigger.adaptation_assessment_ref,
            "priority": trigger.priority.value,
            "source_evidence_refs": [
                {"kind": ref.kind, "id": ref.id} for ref in trigger.source_evidence_refs
            ],
        },
    )
    finding_id = derive_finding_id(draft)
    return ResearchFindingV1(
        finding_id=finding_id,
        schema_version=draft.schema_version,
        finding_type=draft.finding_type,
        evaluation_report_id=draft.evaluation_report_id,
        evaluation_spec_id=draft.evaluation_spec_id,
        cohort_fingerprint=draft.cohort_fingerprint,
        metric_observations=draft.metric_observations,
        sample_count=draft.sample_count,
        mode=draft.mode,
        scenario_id=draft.scenario_id,
        evidence_tier=draft.evidence_tier,
        slice_dimension=draft.slice_dimension,
        slice_value=draft.slice_value,
        observation_summary=draft.observation_summary,
        limitations=draft.limitations,
        metadata=draft.metadata,
    )


__all__ = ["register_finding_from_trigger"]
