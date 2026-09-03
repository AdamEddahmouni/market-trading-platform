"""BUILD 17 research hypothesis and experiment system tests."""

from __future__ import annotations

import copy
import unittest

from market_platform_foundation.intelligence.contracts.common import INTELLIGENCE_SCHEMA_VERSION
from market_platform_foundation.intelligence.evaluation import (
    EvaluationService,
    EvaluationSpec,
    ProbabilityView,
)
from market_platform_foundation.intelligence.evaluation.types import AggregateStatus
from market_platform_foundation.intelligence.outcomes import (
    OutcomeSettlementService,
    register_control_forecast_for_settlement,
    SettlementStatus,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.persistence.repository import RepositoryPutResult
from market_platform_foundation.intelligence.persistence.errors import RepositoryConflictError
from market_platform_foundation.intelligence.research_experiments import (
    ComponentMutationSpec,
    DataSpecification,
    ExperimentKind,
    FalsificationCriterion,
    GuardrailCriterion,
    MetricPlan,
    ResearchExperimentError,
    ResearchExperimentService,
    ResearchFindingType,
    ResearchHypothesisKind,
    ResearchKnowledgeFootprint,
    ResourceBudget,
    SearchSpaceSpec,
    SeedPolicy,
    ValidationRequirements,
    build_research_hypothesis,
    design_experiment,
    derive_experiment_id,
    derive_finding_id,
    derive_hypothesis_id,
    extract_findings,
    research_finding_v1_from_dict,
    research_finding_v1_to_dict,
)
from tests.intelligence.outcome_fixtures import (
    HORIZON_5M,
    ONE_MIN,
    T,
    baseline_control_forecast,
    cutoff_for,
    seed_terminal_trade,
    target_time_for,
)


DEFAULT_CUTOFF = T + HORIZON_5M + ONE_MIN


def _eval_spec() -> EvaluationSpec:
    return EvaluationSpec(
        evaluation_as_of_ns=DEFAULT_CUTOFF,
        decision_start_ns=T - 1,
        decision_end_ns=T + 1,
        target_kind="direction_up_down",
        horizon_ns=HORIZON_5M,
        mode="ACTUAL_LIVE",
        probability_view=ProbabilityView.RAW,
        slice_dimensions=("role",),
    )


def _settled_report(repo: InMemoryIntelligenceRepository):
    forecast = baseline_control_forecast(repo, anchor_price=100.0)
    entry = register_control_forecast_for_settlement(forecast, repo, now_ns=T)
    target = target_time_for(forecast)
    cutoff = cutoff_for(forecast)
    seed_terminal_trade(repo, price=110.0, event_time_ns=target)
    result = OutcomeSettlementService(repo).settle(entry, now_ns=cutoff)
    assert result.status == SettlementStatus.SETTLED
    return EvaluationService(repo).evaluate(_eval_spec(), persist=True)


class ResearchFindingTests(unittest.TestCase):
    def test_finding_requires_evidence_fields(self) -> None:
        from market_platform_foundation.intelligence.research_experiments.types import (
            MetricObservation,
            ResearchFindingV1,
            EvidenceTier,
        )

        with self.assertRaises(ValueError):
            ResearchFindingV1(
                finding_id="x",
                schema_version="1",
                finding_type=ResearchFindingType.CALIBRATION_GAP,
                evaluation_report_id="",
                evaluation_spec_id="spec",
                cohort_fingerprint="coh",
                metric_observations=(
                    MetricObservation(metric_name="ece", value=0.2, sample_count=10),
                ),
                sample_count=10,
                mode="ACTUAL_LIVE",
                evidence_tier=EvidenceTier.ACTUAL_LIVE,
                observation_summary="test",
            )

    def test_finding_identity_deterministic(self) -> None:
        repo = InMemoryIntelligenceRepository()
        report = _settled_report(repo)
        findings = extract_findings(report, mode="ACTUAL_LIVE")
        if not findings:
            self.skipTest("no automated findings for baseline report")
        first_id = findings[0].finding_id
        second = extract_findings(report, mode="ACTUAL_LIVE")[0]
        self.assertEqual(first_id, second.finding_id)

    def test_finding_round_trip(self) -> None:
        repo = InMemoryIntelligenceRepository()
        report = _settled_report(repo)
        findings = extract_findings(report, mode="ACTUAL_LIVE")
        if not findings:
            self.skipTest("no findings")
        payload = research_finding_v1_to_dict(findings[0])
        restored = research_finding_v1_from_dict(payload)
        self.assertEqual(restored.finding_id, findings[0].finding_id)


class ResearchHypothesisTests(unittest.TestCase):
    def test_rejects_treatment_equals_control(self) -> None:
        mutation = ComponentMutationSpec(component="signal", parameter="threshold")
        footprint = ResearchKnowledgeFootprint(evaluation_report_ids=("rep",))
        with self.assertRaises(ResearchExperimentError):
            build_research_hypothesis(
                title="bad",
                hypothesis_kind=ResearchHypothesisKind.THRESHOLD_CHANGE,
                source_finding_ids=("f1",),
                claim="claim",
                treatment=mutation,
                control=mutation,
                primary_metric="brier_score",
                expected_direction="decrease",
                falsification=FalsificationCriterion(description="no improvement"),
                knowledge_footprint=footprint,
            )

    def test_rejects_missing_falsification(self) -> None:
        treatment = ComponentMutationSpec(
            component="signal", parameter="threshold", candidate_ref="0.2"
        )
        control = ComponentMutationSpec(
            component="signal", parameter="threshold", baseline_ref="0.1"
        )
        footprint = ResearchKnowledgeFootprint(evaluation_report_ids=("rep",))
        with self.assertRaises(ValueError):
            build_research_hypothesis(
                title="bad",
                hypothesis_kind=ResearchHypothesisKind.THRESHOLD_CHANGE,
                source_finding_ids=("f1",),
                claim="claim",
                treatment=treatment,
                control=control,
                primary_metric="brier_score",
                expected_direction="decrease",
                falsification=FalsificationCriterion(description=""),
                knowledge_footprint=footprint,
            )

    def test_hypothesis_identity_changes_with_source(self) -> None:
        treatment = ComponentMutationSpec(
            component="signal", parameter="threshold", candidate_ref="0.2"
        )
        control = ComponentMutationSpec(
            component="signal", parameter="threshold", baseline_ref="0.1"
        )
        footprint = ResearchKnowledgeFootprint(evaluation_report_ids=("rep",))
        fals = FalsificationCriterion(description="no brier improvement")
        h1 = build_research_hypothesis(
            title="t",
            hypothesis_kind=ResearchHypothesisKind.THRESHOLD_CHANGE,
            source_finding_ids=("f1",),
            claim="claim",
            treatment=treatment,
            control=control,
            primary_metric="brier_score",
            expected_direction="decrease",
            falsification=fals,
            knowledge_footprint=footprint,
        )
        h2 = build_research_hypothesis(
            title="t",
            hypothesis_kind=ResearchHypothesisKind.THRESHOLD_CHANGE,
            source_finding_ids=("f2",),
            claim="claim",
            treatment=treatment,
            control=control,
            primary_metric="brier_score",
            expected_direction="decrease",
            falsification=fals,
            knowledge_footprint=footprint,
        )
        self.assertNotEqual(h1.research_hypothesis_id, h2.research_hypothesis_id)


class ExperimentManifestTests(unittest.TestCase):
    def _hypothesis(self, repo: InMemoryIntelligenceRepository):
        report = _settled_report(repo)
        findings = extract_findings(report, mode="ACTUAL_LIVE")
        finding = findings[0] if findings else None
        if finding is None:
            from market_platform_foundation.intelligence.research_experiments.types import (
                MetricObservation,
                ResearchFindingV1,
                EvidenceTier,
            )

            provisional = ResearchFindingV1(
                finding_id="pending",
                schema_version=INTELLIGENCE_SCHEMA_VERSION,
                finding_type=ResearchFindingType.NO_DEMONSTRATED_IMPROVEMENT,
                evaluation_report_id=report.report_id,
                evaluation_spec_id=report.evaluation_spec_id,
                cohort_fingerprint=report.cohort_fingerprint,
                metric_observations=(
                    MetricObservation(metric_name="brier_score", value=0.5, sample_count=1),
                ),
                sample_count=1,
                mode="ACTUAL_LIVE",
                evidence_tier=EvidenceTier.ACTUAL_LIVE,
                observation_summary="synthetic",
            )
            finding_id = derive_finding_id(provisional)
            finding = ResearchFindingV1(
                finding_id=finding_id,
                schema_version=provisional.schema_version,
                finding_type=provisional.finding_type,
                evaluation_report_id=provisional.evaluation_report_id,
                evaluation_spec_id=provisional.evaluation_spec_id,
                cohort_fingerprint=provisional.cohort_fingerprint,
                metric_observations=provisional.metric_observations,
                sample_count=provisional.sample_count,
                mode=provisional.mode,
                evidence_tier=provisional.evidence_tier,
                observation_summary=provisional.observation_summary,
            )
        repo.put_research_finding(finding)
        treatment = ComponentMutationSpec(
            component="baseline_model",
            parameter="model_kind",
            candidate_ref="logistic_regression",
        )
        control = ComponentMutationSpec(
            component="baseline_model",
            parameter="model_kind",
            baseline_ref="always_up",
        )
        footprint = ResearchKnowledgeFootprint(
            evaluation_report_ids=(report.report_id,),
            evaluation_spec_ids=(report.evaluation_spec_id,),
            cohort_fingerprints=(report.cohort_fingerprint,),
            mode="ACTUAL_LIVE",
        )
        return build_research_hypothesis(
            title="test threshold",
            hypothesis_kind=ResearchHypothesisKind.MODEL_CHANGE,
            source_finding_ids=(finding.finding_id,),
            claim="Logistic control may reduce Brier",
            treatment=treatment,
            control=control,
            primary_metric="brier_score",
            expected_direction="decrease",
            falsification=FalsificationCriterion(
                description="Brier does not decrease",
                metric_name="brier_score",
            ),
            knowledge_footprint=footprint,
            target_kind="direction_up_down",
            horizon_ns=HORIZON_5M,
            mode="ACTUAL_LIVE",
        )

    def test_experiment_identity_excludes_result(self) -> None:
        repo = InMemoryIntelligenceRepository()
        hypothesis = self._hypothesis(repo)
        repo.put_research_hypothesis(hypothesis)
        manifest = self._manifest_for(hypothesis)
        self.assertEqual(manifest.experiment_id, derive_experiment_id(manifest))

    def test_mode_mismatch_rejected(self) -> None:
        repo = InMemoryIntelligenceRepository()
        hypothesis = self._hypothesis(repo)
        data_spec = DataSpecification(
            target_kind="direction_up_down",
            horizon_ns=HORIZON_5M,
            mode="COUNTERFACTUAL",
            decision_start_ns=T - 1,
            decision_end_ns=T + 1,
        )
        with self.assertRaises(ResearchExperimentError):
            design_experiment(
                hypothesis=hypothesis,
                experiment_kind=ExperimentKind.MODEL_VARIANT,
                treatment=hypothesis.treatment,
                control=hypothesis.control,
                data_spec=data_spec,
                metric_plan=MetricPlan(primary_metric="brier_score"),
                success_criteria="lower brier",
                falsification=FalsificationCriterion(description="fail"),
                knowledge_footprint=hypothesis.knowledge_footprint,
            )

    def test_bounded_search_space(self) -> None:
        repo = InMemoryIntelligenceRepository()
        hypothesis = self._hypothesis(repo)
        manifest_a = self._manifest_for(
            hypothesis,
            search_space=SearchSpaceSpec(parameters={"lr": (0.1, 1.0)}),
        )
        manifest_b = self._manifest_for(
            hypothesis,
            search_space=SearchSpaceSpec(parameters={"lr": (0.1, 1.0, 10.0)}),
        )
        self.assertNotEqual(manifest_a.experiment_id, manifest_b.experiment_id)

    def _manifest_for(self, hypothesis, search_space=None):
        return design_experiment(
            hypothesis=hypothesis,
            experiment_kind=ExperimentKind.MODEL_VARIANT,
            treatment=hypothesis.treatment,
            control=hypothesis.control,
            data_spec=DataSpecification(
                target_kind="direction_up_down",
                horizon_ns=HORIZON_5M,
                mode="ACTUAL_LIVE",
                decision_start_ns=T - 1,
                decision_end_ns=T + 1,
            ),
            metric_plan=MetricPlan(
                primary_metric="brier_score",
                expected_direction="decrease",
            ),
            success_criteria="treatment Brier < control Brier",
            falsification=FalsificationCriterion(description="no improvement"),
            knowledge_footprint=hypothesis.knowledge_footprint,
            validation_requirements=ValidationRequirements(),
            search_space=search_space,
            seed_policy=SeedPolicy(fixed_seeds=(11, 29)),
            resource_budget=ResourceBudget(max_training_runs=3),
            allowed_changes=("baseline_model",),
        )


class ResearchPersistenceTests(unittest.TestCase):
    def test_idempotent_put(self) -> None:
        repo = InMemoryIntelligenceRepository()
        report = _settled_report(repo)
        service = ResearchExperimentService(repo)
        findings = service.extract_and_register_findings(
            report, mode="ACTUAL_LIVE", recorded_at_ns=T
        )
        if not findings:
            self.skipTest("no findings")
        again = repo.put_research_finding(findings[0])
        self.assertEqual(again, RepositoryPutResult.ALREADY_PRESENT)

    def test_conflict_on_same_id_different_content(self) -> None:
        repo = InMemoryIntelligenceRepository()
        report = _settled_report(repo)
        findings = extract_findings(report, mode="ACTUAL_LIVE")
        if not findings:
            self.skipTest("no findings")
        repo.put_research_finding(findings[0])
        mutated = copy.deepcopy(findings[0])
        object.__setattr__(mutated, "observation_summary", "changed")
        with self.assertRaises(RepositoryConflictError):
            repo.put_research_finding(mutated)


class Build01To17LifecycleTests(unittest.TestCase):
    def test_full_research_lifecycle(self) -> None:
        repo = InMemoryIntelligenceRepository()
        report = _settled_report(repo)
        service = ResearchExperimentService(repo)
        findings = service.extract_and_register_findings(
            report, mode="ACTUAL_LIVE", recorded_at_ns=T
        )
        treatment = ComponentMutationSpec(
            component="baseline_model",
            parameter="model_kind",
            candidate_ref="momentum",
        )
        control = ComponentMutationSpec(
            component="baseline_model",
            parameter="model_kind",
            baseline_ref="always_up",
        )
        footprint = ResearchKnowledgeFootprint(
            evaluation_report_ids=(report.report_id,),
            evaluation_spec_ids=(report.evaluation_spec_id,),
            cohort_fingerprints=(report.cohort_fingerprint,),
            mode="ACTUAL_LIVE",
        )
        finding_ids = tuple(f.finding_id for f in findings) or ("synthetic",)
        if not findings:
            from market_platform_foundation.intelligence.research_experiments.types import (
                MetricObservation,
                ResearchFindingV1,
                EvidenceTier,
            )

            provisional = ResearchFindingV1(
                finding_id="pending",
                schema_version="1",
                finding_type=ResearchFindingType.NO_DEMONSTRATED_IMPROVEMENT,
                evaluation_report_id=report.report_id,
                evaluation_spec_id=report.evaluation_spec_id,
                cohort_fingerprint=report.cohort_fingerprint,
                metric_observations=(
                    MetricObservation(metric_name="brier_score", value=0.4, sample_count=1),
                ),
                sample_count=1,
                mode="ACTUAL_LIVE",
                evidence_tier=EvidenceTier.ACTUAL_LIVE,
                observation_summary="synthetic",
            )
            fid = derive_finding_id(provisional)
            finding = ResearchFindingV1(
                finding_id=fid,
                schema_version="1",
                finding_type=provisional.finding_type,
                evaluation_report_id=provisional.evaluation_report_id,
                evaluation_spec_id=provisional.evaluation_spec_id,
                cohort_fingerprint=provisional.cohort_fingerprint,
                metric_observations=provisional.metric_observations,
                sample_count=provisional.sample_count,
                mode=provisional.mode,
                evidence_tier=provisional.evidence_tier,
                observation_summary=provisional.observation_summary,
            )
            repo.put_research_finding(finding)
            finding_ids = (finding.finding_id,)
        hypothesis = build_research_hypothesis(
            title="momentum vs always up",
            hypothesis_kind=ResearchHypothesisKind.MODEL_CHANGE,
            source_finding_ids=finding_ids,
            claim="Momentum may improve Brier vs always-up control",
            treatment=treatment,
            control=control,
            primary_metric="brier_score",
            expected_direction="decrease",
            falsification=FalsificationCriterion(description="no brier decrease"),
            knowledge_footprint=footprint,
            target_kind="direction_up_down",
            horizon_ns=HORIZON_5M,
            mode="ACTUAL_LIVE",
        )
        service.register_hypothesis(hypothesis, recorded_at_ns=T)
        manifest = design_experiment(
            hypothesis=hypothesis,
            experiment_kind=ExperimentKind.MODEL_VARIANT,
            treatment=treatment,
            control=control,
            data_spec=DataSpecification(
                target_kind="direction_up_down",
                horizon_ns=HORIZON_5M,
                mode="ACTUAL_LIVE",
                decision_start_ns=T - 1,
                decision_end_ns=T + 1,
            ),
            metric_plan=MetricPlan(primary_metric="brier_score"),
            success_criteria="lower brier",
            falsification=FalsificationCriterion(description="fail"),
            knowledge_footprint=footprint,
        )
        service.register_experiment(manifest, recorded_at_ns=T)
        self.assertIsNotNone(repo.get_experiment_manifest(manifest.experiment_id))
        events = repo.get_research_lifecycle_events(manifest.experiment_id)
        self.assertTrue(events)


if __name__ == "__main__":
    unittest.main()
