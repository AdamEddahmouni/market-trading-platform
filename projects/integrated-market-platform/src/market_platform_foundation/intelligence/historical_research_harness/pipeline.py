"""Historical research harness pipeline orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...market_data.historical_development.builder import HistoricalDevelopmentBuildResult
from ...market_data.historical_development.e2e_demo import (
    normalized_bars_to_replay_events,
)
from ...paper.calibration.bar_ohlcv_prospective_proof import resolve_runtime_git_sha
from ...paper.calibration.dual_corpus import CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT
from ...paper.calibration.dual_corpus.consumption import (
    assert_corpus_consumable_for_selection_or_training,
)
from ...replay.feature_lifecycle import run_feature_replay, run_feature_root_hash
from ..research_experiments.types import (
    ComponentMutationSpec,
    DataSpecification,
    ExperimentKind,
    ExperimentManifestV1,
    FalsificationCriterion,
    MetricPlan,
    ResearchKnowledgeFootprint,
)
from .features import (
    HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION,
    reconstruct_historical_research_features,
)
from .labels import historical_research_forward_return_label
from .manifest import (
    build_historical_research_run_manifest,
    config_fingerprint,
    derive_historical_research_run_id,
)
from .metrics import compute_component_research_metrics
from .simulator import run_historical_development_simulator_research
from .split import (
    assign_chronological_splits,
    decision_times_for_split,
    filter_events_to_decision_times,
)
from .types import (
    HISTORICAL_RESEARCH_LABEL_KIND,
    HistoricalResearchRunConfig,
    HistoricalResearchSplitName,
)

INGEST_RUN_PREFIX = "HIST-RESEARCH"


@dataclass(frozen=True, slots=True)
class HistoricalResearchHarnessResult:
    ok: bool
    run_id: str
    artifact_path: Path
    body: dict[str, Any]
    reason_code: str | None = None


def _load_normalized_bars(build: HistoricalDevelopmentBuildResult) -> list[dict[str, Any]]:
    normalized_path = build.paths.normalized_dir
    json_files = sorted(normalized_path.glob("*_normalized.json"))
    if not json_files:
        return []
    bars = json.loads(json_files[0].read_text(encoding="utf-8"))
    if not isinstance(bars, list):
        return []
    return [dict(row) for row in bars]


def _momentum_sign_prediction(features: dict[str, Any]) -> int:
    momentum = features.get("values", {}).get("momentum_5m")
    if momentum is None:
        return 0
    if momentum > 0:
        return 1
    if momentum < 0:
        return -1
    return 0


def default_historical_research_experiment_manifest(
    config: HistoricalResearchRunConfig,
    *,
    decision_start_ns: int,
    decision_end_ns: int,
    instrument_ids: tuple[str, ...],
) -> ExperimentManifestV1:
    return ExperimentManifestV1(
        experiment_id=config.experiment_id,
        schema_version="research-experiment/1.0.0",
        research_hypothesis_id=config.hypothesis_id,
        experiment_kind=ExperimentKind.MODEL_VARIANT,
        treatment=ComponentMutationSpec(
            component="historical_research_strategy",
            parameter="candidate",
            candidate_ref=config.strategy_id,
        ),
        control=ComponentMutationSpec(
            component="historical_research_strategy",
            parameter="baseline",
            baseline_ref="abstain",
        ),
        data_spec=DataSpecification(
            target_kind=HISTORICAL_RESEARCH_LABEL_KIND,
            horizon_ns=config.forward_horizon_bars * 60_000_000_000,
            mode="HISTORICAL_DEVELOPMENT",
            decision_start_ns=decision_start_ns,
            decision_end_ns=decision_end_ns,
            instrument_ids=instrument_ids,
        ),
        metric_plan=MetricPlan(primary_metric="directional_accuracy"),
        success_criteria="development_only_not_promotional",
        falsification=FalsificationCriterion(
            description="No demonstrated improvement on HISTORICAL_RESEARCH_TEST without new run"
        ),
        knowledge_footprint=ResearchKnowledgeFootprint(
            decision_start_ns=decision_start_ns,
            decision_end_ns=decision_end_ns,
            mode="HISTORICAL_DEVELOPMENT",
        ),
        metadata={
            "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
            "historical_research_harness": True,
        },
    )


def run_historical_research_harness(
    *,
    repository_root: Path,
    build: HistoricalDevelopmentBuildResult,
    config: HistoricalResearchRunConfig,
    artifact_root: Path | None = None,
) -> HistoricalResearchHarnessResult:
    assert_corpus_consumable_for_selection_or_training(
        corpus_evidence_authority=CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        purpose="historical_research_harness",
    )
    if not build.ok or not build.normalized_fingerprint:
        return HistoricalResearchHarnessResult(
            ok=False,
            run_id="",
            artifact_path=Path(),
            body={},
            reason_code=build.reason_code or "BUILD_NOT_OK",
        )
    bars = _load_normalized_bars(build)
    if not bars:
        return HistoricalResearchHarnessResult(
            ok=False,
            run_id="",
            artifact_path=Path(),
            body={},
            reason_code="NORMALIZED_BARS_EMPTY",
        )
    clocks = sorted({int(bar["available_time"]) for bar in bars})
    assignments = assign_chronological_splits(clocks, config.split_policy)
    ingest_run_id = f"{INGEST_RUN_PREFIX}-{build.normalized_fingerprint[:12]}"
    events = normalized_bars_to_replay_events(bars, ingest_run_id=ingest_run_id)
    feature_state = run_feature_replay(
        events,
        clocks=clocks,
        decision_times=clocks,
        prediction_cutoff=clocks[-1],
    )
    feature_root_hash = run_feature_root_hash(feature_state)
    predictions: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    instruments = tuple(sorted({str(bar.get("instrument_id", "")) for bar in bars if bar.get("instrument_id")}))
    for assignment in assignments:
        split_rows.append(
            {
                "decision_time_ns": assignment.decision_time_ns,
                "split": assignment.split.value,
            }
        )
        features = reconstruct_historical_research_features(
            events,
            prediction_cutoff_ns=assignment.decision_time_ns,
        )
        label = historical_research_forward_return_label(
            events,
            decision_time_ns=assignment.decision_time_ns,
            forward_horizon_bars=config.forward_horizon_bars,
        )
        predicted_direction = _momentum_sign_prediction(features)
        predictions.append(
            {
                "decision_time_ns": assignment.decision_time_ns,
                "split": assignment.split.value,
                "predicted_direction": predicted_direction,
                "features": features["values"],
            }
        )
        if label is not None:
            labels.append({**label, "split": assignment.split.value})
        warnings.extend(features.get("warnings") or [])
    dev_validate_times = decision_times_for_split(
        assignments,
        HistoricalResearchSplitName.HISTORICAL_DEVELOPMENT_VALIDATE,
    )
    dev_validate_events = filter_events_to_decision_times(events, dev_validate_times)
    simulator_result = run_historical_development_simulator_research(
        dev_validate_events,
        simulator_version=config.simulator_version,
        cost_slippage_bps=config.cost_slippage_bps,
    )
    dev_validate_predictions = [
        row
        for row in predictions
        if row["split"] == HistoricalResearchSplitName.HISTORICAL_DEVELOPMENT_VALIDATE.value
    ]
    dev_validate_labels = [
        row
        for row in labels
        if row["split"] == HistoricalResearchSplitName.HISTORICAL_DEVELOPMENT_VALIDATE.value
    ]
    metrics = compute_component_research_metrics(
        predictions=dev_validate_predictions,
        labels=dev_validate_labels,
        simulator_summary=simulator_result,
    )
    metrics["evaluation_split"] = HistoricalResearchSplitName.HISTORICAL_DEVELOPMENT_VALIDATE.value
    research_code_sha = resolve_runtime_git_sha(start=repository_root)
    config_fp = config_fingerprint(config)
    dataset_fingerprint = str(build.manifest.get("dataset_fingerprint") or build.normalized_fingerprint)
    source_dataset_id = str(build.manifest.get("dataset_id") or build.run_id)
    run_id = derive_historical_research_run_id(
        experiment_id=config.experiment_id,
        dataset_fingerprint=dataset_fingerprint,
        config_fingerprint=config_fp,
        research_code_sha=research_code_sha,
    )
    experiment_manifest = default_historical_research_experiment_manifest(
        config,
        decision_start_ns=clocks[0],
        decision_end_ns=clocks[-1],
        instrument_ids=instruments,
    )
    out_root = artifact_root or (repository_root / "artifacts" / "historical-research-harness")
    run_dir = out_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_dir / "run_manifest.json"
    experiment_manifest_path = run_dir / "experiment_manifest.json"
    experiment_manifest_path.write_text(
        json.dumps(
            {
                "experiment_id": experiment_manifest.experiment_id,
                "schema_version": experiment_manifest.schema_version,
                "research_hypothesis_id": experiment_manifest.research_hypothesis_id,
                "experiment_kind": experiment_manifest.experiment_kind.value,
                "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    body = build_historical_research_run_manifest(
        run_id=run_id,
        config=config,
        experiment_manifest=experiment_manifest,
        research_code_sha=research_code_sha,
        source_dataset_id=source_dataset_id,
        dataset_fingerprint=dataset_fingerprint,
        instruments=instruments,
        interval="1m",
        feature_schema_version=HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION,
        target_label_kind=HISTORICAL_RESEARCH_LABEL_KIND,
        split_policy_id=config.split_policy.policy_id,
        split_assignments=split_rows,
        metrics=metrics,
        simulator_result=simulator_result,
        outputs={
            "feature_root_hash": feature_root_hash,
            "experiment_manifest_path": str(experiment_manifest_path),
            "predictions_path": str(run_dir / "predictions.json"),
            "labels_path": str(run_dir / "labels.json"),
        },
        warnings=tuple(sorted(set(warnings))),
        contamination_status="NOT_CONTAMINATED_WITH_PROSPECTIVE_OR_ITEM9",
        config_fp=config_fp,
    )
    (run_dir / "predictions.json").write_text(
        json.dumps(predictions, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (run_dir / "labels.json").write_text(
        json.dumps(labels, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return HistoricalResearchHarnessResult(
        ok=True,
        run_id=run_id,
        artifact_path=manifest_path,
        body=body,
    )


__all__ = [
    "HistoricalResearchHarnessResult",
    "default_historical_research_experiment_manifest",
    "run_historical_research_harness",
]
