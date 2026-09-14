"""In-sample and gated-OOS evaluation for a single Wave 1 family."""

from __future__ import annotations

from typing import Any

from .adapters.base import Wave1ExampleAdapter, get_family_adapter
from .config import Wave1FamilyConfig
from .export_gate import (
    ResearchExportPitAssessment,
    assess_research_export_pit,
    oos_evaluation_authorized,
    require_pit_pass_for_oos,
)
from .metrics import compute_primary_metric, realized_outcome_bps
from .negative_controls import run_negative_controls
from .reports import Wave1FamilyResult
from .statistics import evaluate_wave1_paired_delta


def _statistical_to_dict(statistical: dict[str, object] | None) -> dict[str, object] | None:
    if statistical is None:
        return None
    paired = statistical["paired"]
    return {
        "criterion_status": statistical["criterion_status"],
        "mean_delta": paired.mean_delta,
        "sample_count": paired.sample_count,
        "ci_lower": paired.ci_lower,
        "ci_upper": paired.ci_upper,
        "block_length": paired.block_length,
        "replicate_count": paired.replicate_count,
        "seed": paired.seed,
    }


def _filter_examples(adapter: Wave1ExampleAdapter, examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [ex for ex in examples if adapter.example_matches(ex)]


def _score_vectors(
    adapter: Wave1ExampleAdapter,
    examples: list[dict[str, Any]],
) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    candidate: list[float] = []
    baseline: list[float] = []
    outcomes: list[float] = []
    for ex in examples:
        c_score = adapter.candidate_score(ex)
        b_score = adapter.baseline_score(ex)
        outcome = realized_outcome_bps(ex)
        if c_score is None or b_score is None or outcome is None:
            continue
        candidate.append(c_score)
        baseline.append(b_score)
        outcomes.append(outcome)
    return tuple(candidate), tuple(baseline), tuple(outcomes)


def _losses_from_scores(
    candidate: tuple[float, ...],
    baseline: tuple[float, ...],
    outcomes: tuple[float, ...],
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    from .metrics import signed_prediction_error_bps

    cand_losses = tuple(-signed_prediction_error_bps(c, o) for c, o in zip(candidate, outcomes, strict=True))
    base_losses = tuple(-signed_prediction_error_bps(b, o) for b, o in zip(baseline, outcomes, strict=True))
    return cand_losses, base_losses


def evaluate_family_in_sample(
    config: Wave1FamilyConfig,
    examples: list[dict[str, Any]],
    *,
    seed: int = 20260914,
) -> Wave1FamilyResult:
    adapter = get_family_adapter(config)
    matched = _filter_examples(adapter, examples)
    candidate, baseline, outcomes = _score_vectors(adapter, matched)
    metrics = compute_primary_metric(
        config,
        candidate_scores=candidate,
        baseline_scores=baseline,
        outcomes_bps=outcomes,
    )
    sample_count = int(metrics.get("sample_count") or 0)
    status = "INSUFFICIENT_DATA" if sample_count < config.min_sample_oos else "IN_SAMPLE_ONLY"
    statistical = None
    if sample_count >= config.min_sample_oos:
        cand_losses, base_losses = _losses_from_scores(candidate, baseline, outcomes)
        statistical = _statistical_to_dict(evaluate_wave1_paired_delta(cand_losses, base_losses))
    neg_examples = run_negative_controls(config, matched, seed=seed)
    neg_deltas: dict[str, float | None] = {}
    for control_id, controlled in neg_examples.items():
        c2, b2, o2 = _score_vectors(adapter, controlled)
        m2 = compute_primary_metric(
            config,
            candidate_scores=c2,
            baseline_scores=b2,
            outcomes_bps=o2,
        )
        neg_deltas[control_id] = m2.get("delta") if isinstance(m2.get("delta"), (int, float)) else None
    return Wave1FamilyResult(
        family_id=config.family_id,
        hypothesis_ref=config.hypothesis_ref,
        adapter_kind=config.adapter_kind,
        oos_mode="IN_SAMPLE_ONLY",
        status=status,
        primary_metric=config.primary_metric,
        metrics=metrics,
        statistical_assessment=statistical,
        negative_control_deltas=neg_deltas,
        sample_count=sample_count,
        limitations=("OOS_BLOCKED_PENDING_PIT_PASS",),
    )


def evaluate_family_oos(
    config: Wave1FamilyConfig,
    examples: list[dict[str, Any]],
    *,
    export_manifest: dict[str, Any],
    validation_dataset_manifest: dict[str, Any] | None = None,
    seed: int = 20260914,
) -> Wave1FamilyResult:
    require_pit_pass_for_oos(
        export_manifest,
        validation_dataset_manifest=validation_dataset_manifest,
    )
    adapter = get_family_adapter(config)
    matched = _filter_examples(adapter, examples)
    candidate, baseline, outcomes = _score_vectors(adapter, matched)
    metrics = compute_primary_metric(
        config,
        candidate_scores=candidate,
        baseline_scores=baseline,
        outcomes_bps=outcomes,
    )
    sample_count = int(metrics.get("sample_count") or 0)
    delta = metrics.get("delta")
    status = "INSUFFICIENT_DATA"
    if sample_count >= config.min_sample_oos:
        status = "INCONCLUSIVE"
        if isinstance(delta, (int, float)) and delta > config.primary_metric_threshold_bps:
            status = "CANDIDATE_EDGE_OBSERVED"
    cand_losses, base_losses = _losses_from_scores(candidate, baseline, outcomes)
    statistical = (
        _statistical_to_dict(evaluate_wave1_paired_delta(cand_losses, base_losses))
        if sample_count
        else None
    )
    neg_examples = run_negative_controls(config, matched, seed=seed)
    neg_deltas: dict[str, float | None] = {}
    for control_id, controlled in neg_examples.items():
        c2, b2, o2 = _score_vectors(adapter, controlled)
        m2 = compute_primary_metric(
            config,
            candidate_scores=c2,
            baseline_scores=b2,
            outcomes_bps=o2,
        )
        neg_deltas[control_id] = m2.get("delta") if isinstance(m2.get("delta"), (int, float)) else None
    return Wave1FamilyResult(
        family_id=config.family_id,
        hypothesis_ref=config.hypothesis_ref,
        adapter_kind=config.adapter_kind,
        oos_mode="OOS_PIT_PASS",
        status=status,
        primary_metric=config.primary_metric,
        metrics=metrics,
        statistical_assessment=statistical,
        negative_control_deltas=neg_deltas,
        sample_count=sample_count,
        limitations=(),
    )


def evaluate_family(
    config: Wave1FamilyConfig,
    examples: list[dict[str, Any]],
    *,
    export_manifest: dict[str, Any] | None,
    validation_dataset_manifest: dict[str, Any] | None = None,
    allow_oos: bool = False,
    seed: int = 20260914,
) -> Wave1FamilyResult:
    assessment: ResearchExportPitAssessment | None = None
    if export_manifest is not None:
        assessment = assess_research_export_pit(
            export_manifest,
            validation_dataset_manifest=validation_dataset_manifest,
        )
    if (
        allow_oos
        and export_manifest is not None
        and assessment is not None
        and oos_evaluation_authorized(assessment)
    ):
        return evaluate_family_oos(
            config,
            examples,
            export_manifest=export_manifest,
            validation_dataset_manifest=validation_dataset_manifest,
            seed=seed,
        )
    return evaluate_family_in_sample(config, examples, seed=seed)
