"""Deterministic finding extraction from BUILD 16 reports (BUILD 17)."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from ..evaluation.types import EvaluationReportV1, SliceStatus
from .identity import derive_finding_id, derive_finding_policy_id
from .types import (
    EvidenceTier,
    MetricObservation,
    ResearchFindingType,
    ResearchFindingV1,
    ResearchKnowledgeFootprint,
)

FINDING_POLICY_VERSION = "finding-policy-v1"
DEFAULT_HIGH_CONFIDENCE_WRONG_RATE = 0.25
DEFAULT_CALIBRATION_ECE_GAP = 0.10
DEFAULT_MIN_SLICE_SAMPLE = 5


@dataclass(frozen=True, slots=True)
class FindingExtractionPolicy:
    policy_name: str
    high_confidence_wrong_rate_threshold: float = DEFAULT_HIGH_CONFIDENCE_WRONG_RATE
    calibration_ece_gap_threshold: float = DEFAULT_CALIBRATION_ECE_GAP
    minimum_slice_sample: int = DEFAULT_MIN_SLICE_SAMPLE
    implementation_version: str = FINDING_POLICY_VERSION

    @property
    def policy_id(self) -> str:
        return derive_finding_policy_id(
            policy_name=self.policy_name,
            thresholds={
                "high_confidence_wrong_rate_threshold": self.high_confidence_wrong_rate_threshold,
                "calibration_ece_gap_threshold": self.calibration_ece_gap_threshold,
                "minimum_slice_sample": self.minimum_slice_sample,
            },
            implementation_version=self.implementation_version,
        )


DEFAULT_FINDING_POLICY = FindingExtractionPolicy(policy_name="default-v1")


def evidence_tier_from_mode(mode: str, scenario_id: str | None) -> EvidenceTier:
    if scenario_id:
        return EvidenceTier.COUNTERFACTUAL
    if mode == "ACTUAL_LIVE":
        return EvidenceTier.ACTUAL_LIVE
    return EvidenceTier.OBSERVED_REPLAY


def footprint_from_report_accurate(report: EvaluationReportV1, *, mode: str, scenario_id: str | None) -> ResearchKnowledgeFootprint:
    slice_keys = tuple(
        sorted(f"{item.dimension}:{item.value}" for item in report.slice_results)
    )
    comparison_keys: list[str] = []
    if report.control_comparison is not None:
        comparison_keys.append(
            f"matched:{report.control_comparison.matched_count}"
        )
    return ResearchKnowledgeFootprint(
        evaluation_report_ids=(report.report_id,),
        evaluation_spec_ids=(report.evaluation_spec_id,),
        cohort_fingerprints=(report.cohort_fingerprint,),
        slice_keys=slice_keys,
        comparison_keys=tuple(comparison_keys),
        mode=mode,
        scenario_id=scenario_id,
        evidence_tier=evidence_tier_from_mode(mode, scenario_id),
    )


def extract_findings(
    report: EvaluationReportV1,
    *,
    mode: str,
    scenario_id: str | None = None,
    policy: FindingExtractionPolicy = DEFAULT_FINDING_POLICY,
) -> tuple[ResearchFindingV1, ...]:
  findings: list[ResearchFindingV1] = []
  footprint = footprint_from_report_accurate(report, mode=mode, scenario_id=scenario_id)
  tier = evidence_tier_from_mode(mode, scenario_id)
  sample_count = report.aggregate_metrics.sample_count

  if report.error_summary is not None and sample_count > 0:
    wrong = (
        report.error_summary.false_up_count
        + report.error_summary.false_down_count
    )
    high_conf_wrong = report.error_summary.high_confidence_wrong_count
    if wrong > 0:
      rate = high_conf_wrong / wrong
      if rate >= policy.high_confidence_wrong_rate_threshold:
        finding = _build_finding(
          report=report,
          finding_type=ResearchFindingType.ERROR_CONCENTRATION,
          observation_summary=(
            f"High-confidence wrong rate {rate:.3f} exceeds threshold "
            f"{policy.high_confidence_wrong_rate_threshold}"
          ),
          metrics=(
            MetricObservation(
              metric_name="high_confidence_wrong_rate",
              value=rate,
              sample_count=wrong,
            ),
          ),
          sample_count=wrong,
          mode=mode,
          scenario_id=scenario_id,
          tier=tier,
          policy_id=policy.policy_id,
        )
        findings.append(finding)

  if report.calibration is not None and report.calibration.ece is not None:
    ece = report.calibration.ece
    if ece >= policy.calibration_ece_gap_threshold:
      finding = _build_finding(
        report=report,
        finding_type=ResearchFindingType.CALIBRATION_GAP,
        observation_summary=(
          f"Calibration ECE {ece:.4f} exceeds threshold "
          f"{policy.calibration_ece_gap_threshold}"
        ),
        metrics=(
          MetricObservation(metric_name="ece", value=ece, sample_count=sample_count),
        ),
        sample_count=sample_count,
        mode=mode,
        scenario_id=scenario_id,
        tier=tier,
        policy_id=policy.policy_id,
      )
      findings.append(finding)

  if report.control_comparison is not None and report.control_comparison.matched_count > 0:
    delta = report.control_comparison.aggregate_brier_delta
    if delta is not None and delta > 0:
      finding = _build_finding(
        report=report,
        finding_type=ResearchFindingType.NO_DEMONSTRATED_IMPROVEMENT,
        observation_summary=(
          "Candidate aggregate Brier delta vs control is non-negative on matched cohort"
        ),
        metrics=(
          MetricObservation(
            metric_name="brier_delta_candidate_minus_control",
            value=delta,
            sample_count=report.control_comparison.matched_count,
          ),
        ),
        sample_count=report.control_comparison.matched_count,
        mode=mode,
        scenario_id=scenario_id,
        tier=tier,
        policy_id=policy.policy_id,
        comparison_key=f"matched:{report.control_comparison.matched_count}",
      )
      findings.append(finding)

  for slice_result in report.slice_results:
    if slice_result.status == SliceStatus.INSUFFICIENT_SAMPLE:
      continue
    if slice_result.sample_count < policy.minimum_slice_sample:
      continue
    overall_brier = report.aggregate_metrics.brier_score
    slice_brier = slice_result.metrics.brier_score
    if overall_brier is None or slice_brier is None:
      continue
    delta = abs(slice_brier - overall_brier)
    if delta < 0.05:
      continue
    finding = _build_finding(
      report=report,
      finding_type=ResearchFindingType.HORIZON_SENSITIVITY,
      observation_summary=(
        f"Slice {slice_result.dimension}={slice_result.value} Brier "
        f"{slice_brier:.4f} differs from overall {overall_brier:.4f}"
      ),
      metrics=(
        MetricObservation(
          metric_name="brier_score",
          value=slice_brier,
          sample_count=slice_result.sample_count,
          baseline_value=overall_brier,
          delta=slice_brier - overall_brier,
        ),
      ),
      sample_count=slice_result.sample_count,
      mode=mode,
      scenario_id=scenario_id,
      tier=tier,
      policy_id=policy.policy_id,
      slice_dimension=slice_result.dimension,
      slice_value=slice_result.value,
    )
    findings.append(finding)

  return tuple(findings)


def _build_finding(
    *,
    report: EvaluationReportV1,
    finding_type: ResearchFindingType,
    observation_summary: str,
    metrics: tuple[MetricObservation, ...],
    sample_count: int,
    mode: str,
    scenario_id: str | None,
    tier: EvidenceTier,
    policy_id: str,
    slice_dimension: str | None = None,
    slice_value: str | None = None,
    comparison_key: str | None = None,
) -> ResearchFindingV1:
    provisional = ResearchFindingV1(
        finding_id="pending",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        finding_type=finding_type,
        evaluation_report_id=report.report_id,
        evaluation_spec_id=report.evaluation_spec_id,
        cohort_fingerprint=report.cohort_fingerprint,
        metric_observations=metrics,
        sample_count=sample_count,
        mode=mode,
        evidence_tier=tier,
        slice_dimension=slice_dimension,
        slice_value=slice_value,
        comparison_key=comparison_key,
        scenario_id=scenario_id,
        finding_policy_id=policy_id,
        observation_summary=observation_summary,
    )
    finding_id = derive_finding_id(provisional)
    return ResearchFindingV1(
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
        slice_dimension=provisional.slice_dimension,
        slice_value=provisional.slice_value,
        comparison_key=provisional.comparison_key,
        scenario_id=provisional.scenario_id,
        finding_policy_id=provisional.finding_policy_id,
        observation_summary=provisional.observation_summary,
    )


__all__ = [
    "DEFAULT_FINDING_POLICY",
    "FindingExtractionPolicy",
    "extract_findings",
    "evidence_tier_from_mode",
    "footprint_from_report_accurate",
]
