"""Promotion governance engine (BUILD 20)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..research_experiments.types import ComplexityBudget, EvidenceTier, ExperimentManifestV1
from ..training.types import CandidateArtifactV1
from ..validation.statistics import evaluate_statistical_criteria, moving_block_bootstrap_ci
from ..validation.types import (
    ContaminationDisposition,
    KnowledgeAssessmentStatus,
    StatisticalPlan,
    ValidationReportV1,
)
from .complexity import required_improvement_for_complexity
from .eligibility import assess_promotion_eligibility
from .errors import PromotionError
from .identity import (
    derive_challenger_registration_id,
    derive_champion_assignment_id,
    derive_lifecycle_event_id,
    derive_promotion_decision_id,
)
from .shadow import aggregate_shadow_metric, shadow_paired_deltas
from .types import (
    ChampionAssignmentReason,
    ChampionAssignmentStatus,
    ChampionAssignmentV1,
    ChallengerLifecycleEventV1,
    ChallengerLifecycleState,
    ChallengerRegistrationV1,
    ChampionScopeV1,
    ComplexityGateResult,
    EligibilityDisposition,
    GuardrailGateResult,
    MetricDirection,
    MetricGateResult,
    PromotionDecisionKind,
    PromotionDecisionV1,
    PromotionEligibilityAssessmentV1,
    PromotionPolicyV1,
    PromotionReasonCode,
    ShadowEvidenceManifestV1,
    StatisticalGateResult,
    StatisticalRequirementKind,
)


class PromotionEngine:
    """Deterministic champion-challenger promotion gate."""

    def assess_eligibility(
        self,
        *,
        policy: PromotionPolicyV1,
        candidate: CandidateArtifactV1,
        validation_report: ValidationReportV1,
        candidate_artifact_bytes: bytes | None = None,
    ) -> PromotionEligibilityAssessmentV1:
        return assess_promotion_eligibility(
            policy=policy,
            candidate=candidate,
            validation_report=validation_report,
            candidate_artifact_bytes=candidate_artifact_bytes,
        )

    def register_challenger(
        self,
        *,
        policy: PromotionPolicyV1,
        candidate: CandidateArtifactV1,
        validation_report: ValidationReportV1,
        current_champion: ChampionAssignmentV1,
        eligibility: PromotionEligibilityAssessmentV1 | None = None,
        registered_at_ns: int,
        candidate_artifact_bytes: bytes | None = None,
    ) -> ChallengerRegistrationV1:
        assessment = eligibility or self.assess_eligibility(
            policy=policy,
            candidate=candidate,
            validation_report=validation_report,
            candidate_artifact_bytes=candidate_artifact_bytes,
        )
        if assessment.disposition != EligibilityDisposition.ELIGIBLE:
            raise PromotionError(
                "CHALLENGER_NOT_ELIGIBLE",
                details={"reason_codes": [code.value for code in assessment.reason_codes]},
            )
        if current_champion.champion_scope != policy.champion_scope:
            raise PromotionError("CHAMPION_SCOPE_MISMATCH")
        registration_id = derive_challenger_registration_id(
            promotion_policy_id=policy.promotion_policy_id,
            candidate_id=candidate.candidate_id,
            candidate_artifact_hash=candidate.artifact_hash,
            current_champion_assignment_id=current_champion.assignment_id,
            champion_scope=policy.champion_scope,
        )
        return ChallengerRegistrationV1(
            challenger_registration_id=registration_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            candidate_id=candidate.candidate_id,
            candidate_artifact_hash=candidate.artifact_hash,
            champion_scope=policy.champion_scope,
            current_champion_assignment_id=current_champion.assignment_id,
            validation_report_id=validation_report.validation_report_id,
            promotion_policy_id=policy.promotion_policy_id,
            eligibility_assessment_id=assessment.assessment_id,
            registered_at_ns=registered_at_ns,
            minimum_shadow_samples=policy.minimum_shadow_samples,
            minimum_shadow_duration_ns=policy.minimum_shadow_duration_ns,
            lifecycle_state=ChallengerLifecycleState.REGISTERED,
        )

    def mark_challenger_stale_if_champion_changed(
        self,
        registration: ChallengerRegistrationV1,
        *,
        current_champion_assignment_id: str,
    ) -> ChallengerRegistrationV1:
        if registration.current_champion_assignment_id == current_champion_assignment_id:
            return registration
        return replace(
            registration,
            lifecycle_state=ChallengerLifecycleState.STALE,
            metadata={
                **registration.metadata,
                "stale_reason": PromotionReasonCode.CHAMPION_CHANGED.value,
            },
        )

    def evaluate_promotion(
        self,
        *,
        policy: PromotionPolicyV1,
        candidate: CandidateArtifactV1,
        validation_report: ValidationReportV1,
        challenger_registration: ChallengerRegistrationV1,
        current_champion: ChampionAssignmentV1,
        shadow_evidence: ShadowEvidenceManifestV1 | None = None,
        experiment: ExperimentManifestV1 | None = None,
        champion_complexity: ComplexityBudget = ComplexityBudget.SAME_COMPLEXITY,
        statistical_plan: StatisticalPlan | None = None,
    ) -> PromotionDecisionV1:
        reason_codes: list[PromotionReasonCode] = []
        decision = PromotionDecisionKind.PROMOTE

        registration = self.mark_challenger_stale_if_champion_changed(
            challenger_registration,
            current_champion_assignment_id=current_champion.assignment_id,
        )
        if registration.lifecycle_state == ChallengerLifecycleState.STALE:
            return self._invalid_decision(
                policy=policy,
                candidate=candidate,
                validation_report=validation_report,
                challenger_registration=registration,
                current_champion=current_champion,
                shadow_evidence=shadow_evidence,
                reason_codes=[PromotionReasonCode.CHAMPION_CHANGED, PromotionReasonCode.CHALLENGER_STALE],
            )

        eligibility = self.assess_eligibility(
            policy=policy,
            candidate=candidate,
            validation_report=validation_report,
        )
        if eligibility.disposition != EligibilityDisposition.ELIGIBLE:
            return self._invalid_decision(
                policy=policy,
                candidate=candidate,
                validation_report=validation_report,
                challenger_registration=registration,
                current_champion=current_champion,
                shadow_evidence=shadow_evidence,
                reason_codes=list(eligibility.reason_codes),
            )

        if policy.require_shadow_evidence and shadow_evidence is None:
            return self._inconclusive_decision(
                policy=policy,
                candidate=candidate,
                validation_report=validation_report,
                challenger_registration=registration,
                current_champion=current_champion,
                shadow_evidence=None,
                reason_codes=[PromotionReasonCode.INSUFFICIENT_SHADOW_SAMPLE],
            )

        if shadow_evidence is not None:
            if shadow_evidence.champion_assignment_id != current_champion.assignment_id:
                return self._invalid_decision(
                    policy=policy,
                    candidate=candidate,
                    validation_report=validation_report,
                    challenger_registration=registration,
                    current_champion=current_champion,
                    shadow_evidence=shadow_evidence,
                    reason_codes=[PromotionReasonCode.CHAMPION_CHANGED],
                )
            if shadow_evidence.evidence_tier not in policy.allowed_shadow_evidence_tiers:
                return self._invalid_decision(
                    policy=policy,
                    candidate=candidate,
                    validation_report=validation_report,
                    challenger_registration=registration,
                    current_champion=current_champion,
                    shadow_evidence=shadow_evidence,
                    reason_codes=[PromotionReasonCode.SHADOW_EVIDENCE_MODE_INVALID],
                )
            if policy.require_forward_shadow_evidence and shadow_evidence.evidence_tier not in {
                EvidenceTier.ACTUAL_LIVE,
            }:
                return self._invalid_decision(
                    policy=policy,
                    candidate=candidate,
                    validation_report=validation_report,
                    challenger_registration=registration,
                    current_champion=current_champion,
                    shadow_evidence=shadow_evidence,
                    reason_codes=[PromotionReasonCode.SHADOW_EVIDENCE_MODE_INVALID],
                )
            if shadow_evidence.sample_count < policy.minimum_shadow_samples:
                return self._inconclusive_decision(
                    policy=policy,
                    candidate=candidate,
                    validation_report=validation_report,
                    challenger_registration=registration,
                    current_champion=current_champion,
                    shadow_evidence=shadow_evidence,
                    reason_codes=[PromotionReasonCode.INSUFFICIENT_SHADOW_SAMPLE],
                )
            if (
                policy.minimum_shadow_duration_ns > 0
                and shadow_evidence.duration_ns < policy.minimum_shadow_duration_ns
            ):
                return self._inconclusive_decision(
                    policy=policy,
                    candidate=candidate,
                    validation_report=validation_report,
                    challenger_registration=registration,
                    current_champion=current_champion,
                    shadow_evidence=shadow_evidence,
                    reason_codes=[PromotionReasonCode.INSUFFICIENT_SHADOW_DURATION],
                )
            if not shadow_evidence.settlement_complete:
                return self._inconclusive_decision(
                    policy=policy,
                    candidate=candidate,
                    validation_report=validation_report,
                    challenger_registration=registration,
                    current_champion=current_champion,
                    shadow_evidence=shadow_evidence,
                    reason_codes=[PromotionReasonCode.SETTLEMENT_INCOMPLETE],
                )

        challenger_complexity = (
            experiment.complexity_budget if experiment is not None else ComplexityBudget.SAME_COMPLEXITY
        )
        required_margin = required_improvement_for_complexity(
            policy.complexity_policy,
            champion_complexity=champion_complexity,
            challenger_complexity=challenger_complexity,
        )

        primary_result = self._evaluate_primary_metric(
            policy=policy,
            candidate=candidate,
            validation_report=validation_report,
            shadow_evidence=shadow_evidence,
            required_margin=required_margin,
        )
        if not primary_result.passed:
            decision = PromotionDecisionKind.RETAIN_CHAMPION
            reason_codes.append(PromotionReasonCode.PRIMARY_METRIC_FAILED)

        guardrail_results = self._evaluate_guardrails(
            policy=policy,
            candidate=candidate,
            validation_report=validation_report,
            shadow_evidence=shadow_evidence,
        )
        for guardrail in guardrail_results:
            if guardrail.passed is False:
                decision = PromotionDecisionKind.RETAIN_CHAMPION
                reason_codes.append(PromotionReasonCode.GUARDRAIL_FAILED)
            if guardrail.passed is None:
                decision = PromotionDecisionKind.INCONCLUSIVE
                reason_codes.append(PromotionReasonCode.MISSING_REQUIRED_GUARDRAIL)

        statistical_result = self._evaluate_statistical_requirement(
            policy=policy,
            validation_report=validation_report,
            shadow_evidence=shadow_evidence,
            statistical_plan=statistical_plan,
            candidate_id=candidate.candidate_id,
        )
        if statistical_result.passed is False:
            decision = PromotionDecisionKind.RETAIN_CHAMPION
            reason_codes.append(PromotionReasonCode.STATISTICAL_REQUIREMENT_FAILED)
        elif statistical_result.passed is None and policy.statistical_requirement != StatisticalRequirementKind.NONE:
            decision = PromotionDecisionKind.INCONCLUSIVE
            reason_codes.append(PromotionReasonCode.STATISTICAL_REQUIREMENT_FAILED)

        complexity_result = ComplexityGateResult(
            champion_complexity=champion_complexity,
            challenger_complexity=challenger_complexity,
            required_improvement=required_margin,
            actual_improvement=primary_result.delta,
            passed=primary_result.passed if primary_result.delta is not None else None,
        )
        if (
            challenger_complexity != champion_complexity
            and primary_result.delta is not None
            and not primary_result.passed
        ):
            reason_codes.append(PromotionReasonCode.COMPLEXITY_NOT_JUSTIFIED)
            decision = PromotionDecisionKind.RETAIN_CHAMPION

        if decision == PromotionDecisionKind.PROMOTE:
            reason_codes.append(PromotionReasonCode.PROMOTION_CRITERIA_MET)

        return self._build_decision(
            policy=policy,
            candidate=candidate,
            validation_report=validation_report,
            challenger_registration=registration,
            current_champion=current_champion,
            shadow_evidence=shadow_evidence,
            decision=decision,
            reason_codes=tuple(dict.fromkeys(reason_codes)),
            primary_result=primary_result,
            guardrail_results=guardrail_results,
            statistical_result=statistical_result,
            complexity_result=complexity_result,
        )

    def create_champion_assignment(
        self,
        *,
        decision: PromotionDecisionV1,
        candidate: CandidateArtifactV1,
        effective_from_ns: int,
        previous_champion: ChampionAssignmentV1 | None = None,
    ) -> ChampionAssignmentV1:
        if decision.decision != PromotionDecisionKind.PROMOTE:
            raise PromotionError("PROMOTION_NOT_APPROVED")
        assignment_id = derive_champion_assignment_id(
            champion_scope=decision.champion_scope,
            candidate_id=candidate.candidate_id,
            candidate_artifact_hash=candidate.artifact_hash,
            promotion_decision_id=decision.promotion_decision_id,
            previous_assignment_id=previous_champion.assignment_id if previous_champion else None,
            effective_from_ns=effective_from_ns,
            assignment_reason=ChampionAssignmentReason.PROMOTION.value,
        )
        return ChampionAssignmentV1(
            assignment_id=assignment_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            champion_scope=decision.champion_scope,
            candidate_id=candidate.candidate_id,
            candidate_artifact_hash=candidate.artifact_hash,
            promotion_decision_id=decision.promotion_decision_id,
            previous_assignment_id=previous_champion.assignment_id if previous_champion else None,
            effective_from_ns=effective_from_ns,
            assignment_reason=ChampionAssignmentReason.PROMOTION,
            status=ChampionAssignmentStatus.ACTIVE,
        )

    def bootstrap_champion(
        self,
        *,
        champion_scope: ChampionScopeV1,
        candidate: CandidateArtifactV1,
        effective_from_ns: int,
        candidate_artifact_bytes: bytes | None = None,
    ) -> ChampionAssignmentV1:
        assignment_id = derive_champion_assignment_id(
            champion_scope=champion_scope,
            candidate_id=candidate.candidate_id,
            candidate_artifact_hash=candidate.artifact_hash,
            promotion_decision_id=None,
            previous_assignment_id=None,
            effective_from_ns=effective_from_ns,
            assignment_reason=ChampionAssignmentReason.BOOTSTRAP.value,
        )
        return ChampionAssignmentV1(
            assignment_id=assignment_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            champion_scope=champion_scope,
            candidate_id=candidate.candidate_id,
            candidate_artifact_hash=candidate.artifact_hash,
            promotion_decision_id=None,
            previous_assignment_id=None,
            effective_from_ns=effective_from_ns,
            assignment_reason=ChampionAssignmentReason.BOOTSTRAP,
            status=ChampionAssignmentStatus.ACTIVE,
            metadata={"bootstrap": True, "artifact_bytes_verified": candidate_artifact_bytes is not None},
        )

    def lifecycle_event(
        self,
        *,
        registration: ChallengerRegistrationV1,
        to_state: ChallengerLifecycleState,
        effective_at_ns: int,
        from_state: ChallengerLifecycleState | None = None,
        reason_code: PromotionReasonCode | None = None,
    ) -> ChallengerLifecycleEventV1:
        event_id = derive_lifecycle_event_id(
            challenger_registration_id=registration.challenger_registration_id,
            to_state=to_state.value,
            effective_at_ns=effective_at_ns,
            reason_code=reason_code.value if reason_code else None,
        )
        return ChallengerLifecycleEventV1(
            event_id=event_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            challenger_registration_id=registration.challenger_registration_id,
            from_state=from_state or registration.lifecycle_state,
            to_state=to_state,
            effective_at_ns=effective_at_ns,
            reason_code=reason_code,
        )

    def _evaluate_primary_metric(
        self,
        *,
        policy: PromotionPolicyV1,
        candidate: CandidateArtifactV1,
        validation_report: ValidationReportV1,
        shadow_evidence: ShadowEvidenceManifestV1 | None,
        required_margin: float,
    ) -> MetricGateResult:
        champion_value: float | None = None
        challenger_value: float | None = None
        delta: float | None = None

        if shadow_evidence is not None and shadow_evidence.sample_count > 0:
            champion_value = aggregate_shadow_metric(
                shadow_evidence.matched_observations,
                metric_name=policy.primary_metric,
                role="champion",
            )
            challenger_value = aggregate_shadow_metric(
                shadow_evidence.matched_observations,
                metric_name=policy.primary_metric,
                role="challenger",
            )
            if champion_value is not None and challenger_value is not None:
                delta = challenger_value - champion_value
        else:
            for holdout in validation_report.holdout_results:
                if holdout.candidate_id != candidate.candidate_id:
                    continue
                challenger_value = holdout.candidate_metrics.get(policy.primary_metric)
                champion_value = holdout.control_metrics.get(policy.primary_metric)
                delta = holdout.primary_delta
                break

        passed = self._metric_passes(
            direction=policy.primary_metric_direction,
            delta=delta,
            required_margin=required_margin,
        )
        return MetricGateResult(
            metric_name=policy.primary_metric,
            direction=policy.primary_metric_direction,
            champion_value=champion_value,
            challenger_value=challenger_value,
            delta=delta,
            required_improvement=required_margin,
            passed=passed,
        )

    def _evaluate_guardrails(
        self,
        *,
        policy: PromotionPolicyV1,
        candidate: CandidateArtifactV1,
        validation_report: ValidationReportV1,
        shadow_evidence: ShadowEvidenceManifestV1 | None,
    ) -> tuple[GuardrailGateResult, ...]:
        results: list[GuardrailGateResult] = []
        holdout = next(
            (row for row in validation_report.holdout_results if row.candidate_id == candidate.candidate_id),
            None,
        )
        for rule in policy.guardrails:
            champion_value: float | None = None
            challenger_value: float | None = None
            if shadow_evidence is not None:
                champion_value = aggregate_shadow_metric(
                    shadow_evidence.matched_observations,
                    metric_name=rule.metric_name,
                    role="champion",
                )
                challenger_value = aggregate_shadow_metric(
                    shadow_evidence.matched_observations,
                    metric_name=rule.metric_name,
                    role="challenger",
                )
            elif holdout is not None:
                champion_value = holdout.control_metrics.get(rule.metric_name)
                challenger_value = holdout.candidate_metrics.get(rule.metric_name)
            passed: bool | None
            if champion_value is None or challenger_value is None:
                passed = None
            else:
                regression = challenger_value - champion_value
                if rule.direction == MetricDirection.LOWER_IS_BETTER:
                    passed = regression <= (rule.max_regression or 0.0)
                else:
                    passed = regression >= -(rule.max_regression or 0.0)
                if rule.max_absolute is not None:
                    passed = passed and challenger_value <= rule.max_absolute
            results.append(
                GuardrailGateResult(
                    rule=rule,
                    champion_value=champion_value,
                    challenger_value=challenger_value,
                    passed=passed,
                )
            )
        return tuple(results)

    def _evaluate_statistical_requirement(
        self,
        *,
        policy: PromotionPolicyV1,
        validation_report: ValidationReportV1,
        shadow_evidence: ShadowEvidenceManifestV1 | None,
        statistical_plan: StatisticalPlan | None,
        candidate_id: str,
    ) -> StatisticalGateResult:
        if policy.statistical_requirement == StatisticalRequirementKind.NONE:
            return StatisticalGateResult(
                requirement=policy.statistical_requirement,
                sample_count=0,
                mean_delta=None,
                ci_lower=None,
                ci_upper=None,
                passed=True,
            )
        if policy.statistical_requirement == StatisticalRequirementKind.HOLDOUT_PAIRED_CI_IMPROVEMENT:
            holdout = next(
                (row for row in validation_report.holdout_results if row.candidate_id == candidate_id),
                None,
            )
            if holdout is None or holdout.paired_delta is None or statistical_plan is None:
                return StatisticalGateResult(
                    requirement=policy.statistical_requirement,
                    sample_count=0,
                    mean_delta=None,
                    ci_lower=None,
                    ci_upper=None,
                    passed=None,
                )
            verdict = evaluate_statistical_criteria(holdout.paired_delta, statistical_plan)
            return StatisticalGateResult(
                requirement=policy.statistical_requirement,
                sample_count=holdout.paired_delta.sample_count,
                mean_delta=holdout.paired_delta.mean_delta,
                ci_lower=holdout.paired_delta.ci_lower,
                ci_upper=holdout.paired_delta.ci_upper,
                passed=verdict == "MEETS_PRE_REGISTERED_CRITERIA",
            )
        if policy.statistical_requirement == StatisticalRequirementKind.SHADOW_PAIRED_CI_IMPROVEMENT:
            if shadow_evidence is None or statistical_plan is None:
                return StatisticalGateResult(
                    requirement=policy.statistical_requirement,
                    sample_count=0,
                    mean_delta=None,
                    ci_lower=None,
                    ci_upper=None,
                    passed=None,
                )
            deltas = shadow_paired_deltas(
                shadow_evidence.matched_observations,
                metric_name=policy.primary_metric,
            )
            paired = moving_block_bootstrap_ci(deltas, statistical_plan)
            verdict = evaluate_statistical_criteria(paired, statistical_plan)
            return StatisticalGateResult(
                requirement=policy.statistical_requirement,
                sample_count=paired.sample_count,
                mean_delta=paired.mean_delta,
                ci_lower=paired.ci_lower,
                ci_upper=paired.ci_upper,
                passed=verdict == "MEETS_PRE_REGISTERED_CRITERIA",
            )
        return StatisticalGateResult(
            requirement=policy.statistical_requirement,
            sample_count=0,
            mean_delta=None,
            ci_lower=None,
            ci_upper=None,
            passed=None,
        )

    @staticmethod
    def _metric_passes(
        *,
        direction: MetricDirection,
        delta: float | None,
        required_margin: float,
    ) -> bool:
        if delta is None:
            return False
        if direction == MetricDirection.LOWER_IS_BETTER:
            return delta <= -required_margin
        return delta >= required_margin

    def _build_decision(
        self,
        *,
        policy: PromotionPolicyV1,
        candidate: CandidateArtifactV1,
        validation_report: ValidationReportV1,
        challenger_registration: ChallengerRegistrationV1,
        current_champion: ChampionAssignmentV1,
        shadow_evidence: ShadowEvidenceManifestV1 | None,
        decision: PromotionDecisionKind,
        reason_codes: tuple[PromotionReasonCode, ...],
        primary_result: MetricGateResult,
        guardrail_results: tuple[GuardrailGateResult, ...],
        statistical_result: StatisticalGateResult,
        complexity_result: ComplexityGateResult,
    ) -> PromotionDecisionV1:
        decision_id = derive_promotion_decision_id(
            promotion_policy_id=policy.promotion_policy_id,
            current_champion_assignment_id=current_champion.assignment_id,
            challenger_registration_id=challenger_registration.challenger_registration_id,
            candidate_artifact_hash=candidate.artifact_hash,
            validation_report_ids=(validation_report.validation_report_id,),
            shadow_evidence_id=shadow_evidence.shadow_evidence_id if shadow_evidence else None,
        )
        return PromotionDecisionV1(
            promotion_decision_id=decision_id,
            schema_version=INTELLIGENCE_SCHEMA_VERSION,
            promotion_policy_id=policy.promotion_policy_id,
            champion_scope=policy.champion_scope,
            current_champion_assignment_id=current_champion.assignment_id,
            challenger_registration_id=challenger_registration.challenger_registration_id,
            candidate_id=candidate.candidate_id,
            candidate_artifact_hash=candidate.artifact_hash,
            validation_report_ids=(validation_report.validation_report_id,),
            shadow_evidence_id=shadow_evidence.shadow_evidence_id if shadow_evidence else None,
            artifact_integrity_status=True,
            contamination_status=validation_report.contamination_disposition,
            knowledge_status=validation_report.knowledge_assessment_status,
            primary_metric_result=primary_result,
            guardrail_results=guardrail_results,
            statistical_result=statistical_result,
            complexity_result=complexity_result,
            decision=decision,
            reason_codes=reason_codes,
        )

    def _invalid_decision(
        self,
        *,
        policy: PromotionPolicyV1,
        candidate: CandidateArtifactV1,
        validation_report: ValidationReportV1,
        challenger_registration: ChallengerRegistrationV1,
        current_champion: ChampionAssignmentV1,
        shadow_evidence: ShadowEvidenceManifestV1 | None,
        reason_codes: list[PromotionReasonCode],
    ) -> PromotionDecisionV1:
        return self._build_decision(
            policy=policy,
            candidate=candidate,
            validation_report=validation_report,
            challenger_registration=challenger_registration,
            current_champion=current_champion,
            shadow_evidence=shadow_evidence,
            decision=PromotionDecisionKind.INVALID,
            reason_codes=tuple(dict.fromkeys(reason_codes)),
            primary_result=MetricGateResult(
                metric_name=policy.primary_metric,
                direction=policy.primary_metric_direction,
                champion_value=None,
                challenger_value=None,
                delta=None,
                required_improvement=policy.required_improvement,
                passed=False,
            ),
            guardrail_results=(),
            statistical_result=StatisticalGateResult(
                requirement=policy.statistical_requirement,
                sample_count=0,
                mean_delta=None,
                ci_lower=None,
                ci_upper=None,
                passed=None,
            ),
            complexity_result=ComplexityGateResult(
                champion_complexity=ComplexityBudget.SAME_COMPLEXITY,
                challenger_complexity=ComplexityBudget.SAME_COMPLEXITY,
                required_improvement=policy.required_improvement,
                actual_improvement=None,
                passed=None,
            ),
        )

    def _inconclusive_decision(
        self,
        *,
        policy: PromotionPolicyV1,
        candidate: CandidateArtifactV1,
        validation_report: ValidationReportV1,
        challenger_registration: ChallengerRegistrationV1,
        current_champion: ChampionAssignmentV1,
        shadow_evidence: ShadowEvidenceManifestV1 | None,
        reason_codes: list[PromotionReasonCode],
    ) -> PromotionDecisionV1:
        return self._build_decision(
            policy=policy,
            candidate=candidate,
            validation_report=validation_report,
            challenger_registration=challenger_registration,
            current_champion=current_champion,
            shadow_evidence=shadow_evidence,
            decision=PromotionDecisionKind.INCONCLUSIVE,
            reason_codes=tuple(dict.fromkeys(reason_codes)),
            primary_result=MetricGateResult(
                metric_name=policy.primary_metric,
                direction=policy.primary_metric_direction,
                champion_value=None,
                challenger_value=None,
                delta=None,
                required_improvement=policy.required_improvement,
                passed=False,
            ),
            guardrail_results=(),
            statistical_result=StatisticalGateResult(
                requirement=policy.statistical_requirement,
                sample_count=0,
                mean_delta=None,
                ci_lower=None,
                ci_upper=None,
                passed=None,
            ),
            complexity_result=ComplexityGateResult(
                champion_complexity=ComplexityBudget.SAME_COMPLEXITY,
                challenger_complexity=ComplexityBudget.SAME_COMPLEXITY,
                required_improvement=policy.required_improvement,
                actual_improvement=None,
                passed=None,
            ),
        )


__all__ = ["PromotionEngine"]
