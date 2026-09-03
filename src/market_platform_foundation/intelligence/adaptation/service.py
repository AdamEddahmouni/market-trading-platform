"""Adaptation orchestration service (BUILD 24)."""

from __future__ import annotations

from dataclasses import dataclass

from ..persistence.repository import IntelligenceRepository, RepositoryPutResult
from .engine import AdaptationContext, AdaptationEngine, EvidenceBundle
from .handoff import register_finding_from_trigger
from .identity import derive_adaptation_campaign_id, derive_adaptation_event_id
from .types import (
    AdaptationAssessmentResult,
    AdaptationCampaignV1,
    AdaptationEventType,
    AdaptationEventV1,
    AdaptationPolicyV1,
    AdaptationReasonCode,
    ResearchTriggerV1,
)
from ..research_experiments.types import ResearchFindingV1


@dataclass
class AdaptationService:
    repository: IntelligenceRepository
    engine: AdaptationEngine | None = None

    def __post_init__(self) -> None:
        if self.engine is None:
            self.engine = AdaptationEngine()

    def assess_and_persist(
        self,
        *,
        policy: AdaptationPolicyV1,
        bundle: EvidenceBundle,
        context: AdaptationContext,
        persist: bool = True,
    ) -> tuple[AdaptationAssessmentResult, ...]:
        evidence = self.engine.normalize_bundle(bundle, champion_scope=policy.champion_scope)
        results = self.engine.assess(policy=policy, evidence=evidence, context=context)
        if persist:
            self.repository.put_adaptation_policy(policy)
            for result in results:
                self.repository.put_adaptation_assessment(result.assessment)
                if result.trigger is not None:
                    self.repository.put_research_trigger(result.trigger)
                    self._record_event(
                        event_type=AdaptationEventType.TRIGGERED,
                        trigger=result.trigger,
                        effective_at_ns=context.reference_time_ns,
                    )
        return results

    def register_finding_from_trigger(
        self,
        trigger: ResearchTriggerV1,
        *,
        mode: str,
        scenario_id: str | None = None,
        recorded_at_ns: int,
        persist: bool = True,
    ) -> ResearchFindingV1:
        finding = register_finding_from_trigger(trigger, mode=mode, scenario_id=scenario_id)
        if persist:
            self.repository.put_research_finding(finding)
            campaign_id = derive_adaptation_campaign_id(
                research_trigger_id=trigger.research_trigger_id,
                downstream_refs={"research_finding_id": finding.finding_id},
            )
            self.repository.put_adaptation_campaign(
                AdaptationCampaignV1(
                    adaptation_campaign_id=campaign_id,
                    schema_version=trigger.schema_version,
                    research_trigger_id=trigger.research_trigger_id,
                    research_finding_id=finding.finding_id,
                )
            )
            self._record_event(
                event_type=AdaptationEventType.TRIGGER_CONSUMED_BY_FINDING,
                trigger=trigger,
                effective_at_ns=recorded_at_ns,
                metadata={"finding_id": finding.finding_id},
            )
        return finding

    def _record_event(
        self,
        *,
        event_type: AdaptationEventType,
        trigger: ResearchTriggerV1,
        effective_at_ns: int,
        metadata: dict | None = None,
    ) -> RepositoryPutResult:
        from ..promotion.identity import champion_scope_identity_payload

        event_id = derive_adaptation_event_id(
            event_type=event_type.value,
            champion_scope=champion_scope_identity_payload(trigger.champion_scope),
            effective_at_ns=effective_at_ns,
            source_key=trigger.research_trigger_id,
        )
        event = AdaptationEventV1(
            event_id=event_id,
            schema_version=trigger.schema_version,
            event_type=event_type,
            champion_scope=trigger.champion_scope,
            effective_at_ns=effective_at_ns,
            reason_codes=(AdaptationReasonCode.RESEARCH_TRIGGER_ISSUED,),
            metadata=dict(metadata or {}),
        )
        return self.repository.put_adaptation_event(event)


__all__ = ["AdaptationService"]
