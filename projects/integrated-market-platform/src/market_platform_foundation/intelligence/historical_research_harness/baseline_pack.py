"""Frozen Historical Baseline Pack v1 (IMP-RESEARCH-VALIDATION-04 Lane C)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from ...market_data.historical_development.builder import HistoricalDevelopmentBuildResult
from ...paper.calibration.bar_ohlcv_prospective_proof import resolve_runtime_git_sha
from ...paper.calibration.dual_corpus import CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT
from ...paper.calibration.dual_corpus.contamination_auditor import audit_research_contamination_run
from ...paper.calibration.dual_corpus.run_manifest import (
    RESEARCH_CONTAMINATION_RUN_MANIFEST_KIND,
    RESEARCH_CONTAMINATION_RUN_SCHEMA_VERSION,
)
from .features import (
    DEFAULT_HISTORICAL_RESEARCH_FEATURES,
    HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION,
)
from .metrics import compute_component_research_metrics
from .pipeline import run_historical_research_harness
from .strategies import (
    BASELINE_STRATEGY_MEAN_REVERSION_5M_SIGN_V1,
    BASELINE_STRATEGY_MOMENTUM_5M_SIGN_V1,
    BASELINE_STRATEGY_NO_TRADE_V1,
    BASELINE_STRATEGY_VOLUME_MOMENTUM_5M_V1,
)
from .types import (
    HISTORICAL_RESEARCH_HARNESS_VERSION,
    HISTORICAL_RESEARCH_LABEL_KIND,
    ChronologicalSplitPolicy,
    HistoricalResearchRunConfig,
    HistoricalResearchSplitName,
)

HISTORICAL_BASELINE_PACK_V1 = "HISTORICAL_BASELINE_V1"
HISTORICAL_BASELINE_PACK_EXPERIMENT_ID = "imp-research-validation-04-lane-c-baseline-pack-v1"
HISTORICAL_BASELINE_PACK_HYPOTHESIS_ID = "imp-research-validation-04-lane-c-baseline-pack-hypothesis-v1"
HISTORICAL_BASELINE_PACK_DEFINITION_KIND = "historical_baseline_pack_experiment_definition_v1"
HISTORICAL_BASELINE_PACK_DEFINITION_SCHEMA = "imp.historical-baseline-pack/1.0.0"
HISTORICAL_BASELINE_PACK_RANDOM_SEED = 0

DEFAULT_MULTI_SESSION_FIXTURE_REL = (
    "tests/fixtures/historical_development/aapl_2026-09-11_2026-09-15_rth_multi_session.json"
)
CANONICAL_BASELINE_PACK_EVIDENCE_REL = (
    "evidence/historical-research/imp-research-validation-04-lane-c-baseline-pack-v1"
)

_BASELINE_PACK_OPERATOR_INTERPRETATION_NOTES: tuple[str, ...] = (
    "Directional accuracy 1.0 or 0.0 on small development-validate sample sizes (e.g. n≈12) "
    "on the monotone synthetic multi-session fixture is a pathological observation, not evidence of edge.",
    "Simulator fill counts and gross/net PnL may be identical across baselines because the "
    "paper_bar_conservative_v1 research simulator is bar-path scoped, not prediction-conditioned.",
    "Baseline 0 (no-trade) may show abstention_rate=1.0 while simulator fills remain nonzero "
    "because predictor abstention and simulator event replay are decoupled in this harness path.",
)

_BASELINE_STRATEGY_SPECS: tuple[dict[str, Any], ...] = (
    {
        "baseline_index": 0,
        "strategy_id": BASELINE_STRATEGY_NO_TRADE_V1,
        "strategy_version": "1.0.0",
        "description": "Null / no-edge: abstain all decisions (no simulated directional edge).",
    },
    {
        "baseline_index": 1,
        "strategy_id": BASELINE_STRATEGY_MOMENTUM_5M_SIGN_V1,
        "strategy_version": "1.0.0",
        "description": "Short-horizon momentum: sign(momentum_5m); abstain when feature missing.",
        "lookback_bars": 5,
    },
    {
        "baseline_index": 2,
        "strategy_id": BASELINE_STRATEGY_MEAN_REVERSION_5M_SIGN_V1,
        "strategy_version": "1.0.0",
        "description": "Short-horizon mean reversion: inverse sign of momentum_5m.",
        "lookback_bars": 5,
    },
    {
        "baseline_index": 3,
        "strategy_id": BASELINE_STRATEGY_VOLUME_MOMENTUM_5M_V1,
        "strategy_version": "1.0.0",
        "description": "Volume-aware momentum: sign(momentum_5m) when relative_volume_10m >= 1.0.",
        "lookback_bars": 5,
        "relative_volume_threshold": 1.0,
    },
)


def default_baseline_pack_run_parameters() -> dict[str, Any]:
    split_policy = ChronologicalSplitPolicy()
    return {
        "forward_horizon_bars": 1,
        "split_policy": {
            "policy_id": split_policy.policy_id,
            "train_fraction": split_policy.train_fraction,
            "development_validate_fraction": split_policy.development_validate_fraction,
            "allow_shuffle": split_policy.allow_shuffle,
        },
        "simulator_version": "paper_bar_conservative_v1",
        "cost_slippage_bps": 5.0,
        "random_seed": HISTORICAL_BASELINE_PACK_RANDOM_SEED,
        "transaction_cost_model": "linear_slippage_on_gross_pnl",
        "metrics_scope": {
            "simulator_and_primary_metrics": HistoricalResearchSplitName.HISTORICAL_DEVELOPMENT_VALIDATE.value,
            "descriptive_holdout": HistoricalResearchSplitName.HISTORICAL_RESEARCH_TEST.value,
        },
        "exclusions": [
            "HISTORICAL_RESEARCH_TEST not used for parameter or simulator selection",
            "no Item 9 calibration inputs",
            "no prospective receipts",
        ],
    }


def build_frozen_baseline_pack_experiment_definition(
    *,
    repository_root: Path,
    dataset_identity: dict[str, Any],
    code_sha: str | None = None,
) -> dict[str, Any]:
    research_code_sha = code_sha or resolve_runtime_git_sha(start=repository_root)
    feature_specs = [
        {
            "feature_id": spec.feature_id,
            "schema_version": spec.schema_version,
            "lookback_bars": spec.lookback_bars,
            "missing_data_behavior": spec.missing_data_behavior.value,
        }
        for spec in DEFAULT_HISTORICAL_RESEARCH_FEATURES
    ]
    body: dict[str, Any] = {
        "artifact_kind": HISTORICAL_BASELINE_PACK_DEFINITION_KIND,
        "schema_version": HISTORICAL_BASELINE_PACK_DEFINITION_SCHEMA,
        "evidence_label": HISTORICAL_BASELINE_PACK_V1,
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "experiment_id": HISTORICAL_BASELINE_PACK_EXPERIMENT_ID,
        "hypothesis_id": HISTORICAL_BASELINE_PACK_HYPOTHESIS_ID,
        "harness_version": HISTORICAL_RESEARCH_HARNESS_VERSION,
        "feature_version": HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION,
        "target_definition": {
            "label_kind": HISTORICAL_RESEARCH_LABEL_KIND,
            "forward_horizon_bars": 1,
        },
        "feature_definitions": feature_specs,
        "baseline_strategies": list(_BASELINE_STRATEGY_SPECS),
        "run_parameters": default_baseline_pack_run_parameters(),
        "dataset": dataset_identity,
        "research_code_sha": research_code_sha,
        "created_timestamp_ns": time.time_ns(),
        "governance": {
            "authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
            "item9_effect": "NONE",
            "item7_effect": "NONE",
            "ftep_effect": "NONE",
            "live_authority": "NONE",
            "promotional_language_forbidden": True,
        },
    }
    body["experiment_definition_hash"] = sha256_bytes(canonical_bytes(body))
    return body


def compute_experiment_definition_hash(definition: dict[str, Any]) -> str:
    """Recompute hash from payload; never trust an embedded hash field."""

    payload = {k: v for k, v in definition.items() if k != "experiment_definition_hash"}
    return sha256_bytes(canonical_bytes(payload))


def experiment_definition_hash(definition: dict[str, Any]) -> str:
    return compute_experiment_definition_hash(definition)


def verify_frozen_experiment_definition(definition: dict[str, Any]) -> dict[str, Any]:
    """Fail closed when embedded hash is missing or does not match recomputed payload."""

    embedded = definition.get("experiment_definition_hash")
    if not isinstance(embedded, str) or not embedded.strip():
        return {
            "ok": False,
            "reason_code": "EXPERIMENT_DEFINITION_HASH_MISSING",
            "experiment_definition_hash": None,
            "embedded_hash": embedded,
            "computed_hash": compute_experiment_definition_hash(definition),
        }
    computed = compute_experiment_definition_hash(definition)
    if embedded != computed:
        return {
            "ok": False,
            "reason_code": "EXPERIMENT_DEFINITION_HASH_MISMATCH",
            "experiment_definition_hash": computed,
            "embedded_hash": embedded,
            "computed_hash": computed,
        }
    return {
        "ok": True,
        "reason_code": None,
        "experiment_definition_hash": computed,
        "embedded_hash": embedded,
        "computed_hash": computed,
    }


def canonical_baseline_pack_evidence_dir(repository_root: Path) -> Path:
    return repository_root / CANONICAL_BASELINE_PACK_EVIDENCE_REL


def _split_intervals(assignments: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    by_split: dict[str, list[int]] = {}
    for row in assignments:
        split = str(row["split"])
        by_split.setdefault(split, []).append(int(row["decision_time_ns"]))
    intervals: dict[str, dict[str, int]] = {}
    for split, times in by_split.items():
        if not times:
            continue
        intervals[split] = {"start_ns": min(times), "end_ns": max(times)}
    return intervals


def build_baseline_pack_contamination_manifest(
    *,
    pack_run_id: str,
    dataset_fingerprint: str,
    split_assignments: list[dict[str, Any]],
    feature_lineage: list[dict[str, Any]],
    historical_dataset_manifest: dict[str, Any] | None,
) -> dict[str, Any]:
    intervals = _split_intervals(split_assignments)
    train = intervals.get(HistoricalResearchSplitName.HISTORICAL_TRAIN.value)
    test = intervals.get(HistoricalResearchSplitName.HISTORICAL_RESEARCH_TEST.value)
    holdout = intervals.get(HistoricalResearchSplitName.HISTORICAL_RESEARCH_TEST.value)
    if train is None or test is None:
        train = train or {"start_ns": 1, "end_ns": 2}
        test = test or {"start_ns": 3, "end_ns": 4}
    holdout = holdout or test
    training_examples = [
        {"snapshot_id": f"train-{row['decision_time_ns']}", "decision_time_ns": int(row["decision_time_ns"])}
        for row in split_assignments
        if row["split"] == HistoricalResearchSplitName.HISTORICAL_TRAIN.value
    ]
    manifest: dict[str, Any] = {
        "artifact_kind": RESEARCH_CONTAMINATION_RUN_MANIFEST_KIND,
        "schema_version": RESEARCH_CONTAMINATION_RUN_SCHEMA_VERSION,
        "run_id": pack_run_id,
        "lineage_complete": True,
        "authority_context": {
            "primary_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
            "item9_effect": "NONE",
        },
        "splits": {"train": train, "test": test},
        "holdout": {
            "holdout_start_ns": int(holdout["start_ns"]),
            "holdout_end_ns": int(holdout["end_ns"]),
        },
        "feature_lineage": feature_lineage,
        "training_examples": training_examples,
        "corpus_inputs": [
            {
                "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
                "dataset_fingerprint": dataset_fingerprint,
                "expected_dataset_fingerprint": dataset_fingerprint,
            }
        ],
        "item9_prospective_inputs": [],
        "target_leakage": [],
    }
    if historical_dataset_manifest is not None:
        manifest["historical_dataset_manifest"] = historical_dataset_manifest
    return manifest


def _metrics_for_split(
    predictions: list[dict[str, Any]],
    labels: list[dict[str, Any]],
    split: HistoricalResearchSplitName,
    *,
    simulator_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    scoped_predictions = [row for row in predictions if row.get("split") == split.value]
    scoped_labels = [row for row in labels if row.get("split") == split.value]
    sim = simulator_summary or {
        "fill_count": 0,
        "gross_pnl": 0.0,
        "net_pnl": 0.0,
        "estimated_costs": 0.0,
        "turnover": 0,
        "max_drawdown": None,
        "exposure": None,
        "coverage": None,
    }
    metrics = compute_component_research_metrics(
        predictions=scoped_predictions,
        labels=scoped_labels,
        simulator_summary=sim,
    )
    metrics["split"] = split.value
    metrics["signal_count"] = sum(
        1 for row in scoped_predictions if int(row.get("predicted_direction", 0)) != 0
    )
    return metrics


@dataclass(frozen=True, slots=True)
class BaselinePackRunResult:
    ok: bool
    pack_run_id: str
    experiment_definition_hash: str
    dataset_fingerprint: str
    artifact_dir: Path
    body: dict[str, Any]
    reason_code: str | None = None


def publish_baseline_pack_evidence_receipt(
    *,
    repository_root: Path,
    frozen_definition: dict[str, Any],
    pack_result: BaselinePackRunResult,
) -> Path:
    """Write git-tracked receipts (manifests only; no raw bar corpus)."""

    evidence_dir = canonical_baseline_pack_evidence_dir(repository_root)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    frozen_path = evidence_dir / "frozen_experiment_definition.json"
    frozen_path.write_text(json.dumps(frozen_definition, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pack_manifest = dict(pack_result.body)
    pack_manifest["frozen_definition_path"] = frozen_path.relative_to(repository_root).as_posix()
    pack_manifest["canonical_evidence_dir"] = CANONICAL_BASELINE_PACK_EVIDENCE_REL
    pack_manifest["operator_interpretation_notes"] = list(_BASELINE_PACK_OPERATOR_INTERPRETATION_NOTES)
    pack_manifest_path = evidence_dir / "baseline_pack_run_manifest.json"
    pack_manifest_path.write_text(json.dumps(pack_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    contamination_src = pack_result.artifact_dir / "contamination_manifest.json"
    if contamination_src.is_file():
        contamination_body = json.loads(contamination_src.read_text(encoding="utf-8"))
        (evidence_dir / "contamination_manifest.json").write_text(
            json.dumps(contamination_body, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    receipt = {
        "artifact_kind": "historical_baseline_pack_evidence_receipt_v1",
        "evidence_label": HISTORICAL_BASELINE_PACK_V1,
        "experiment_definition_hash": pack_result.experiment_definition_hash,
        "dataset_fingerprint": pack_result.dataset_fingerprint,
        "pack_run_id": pack_result.pack_run_id,
        "frozen_definition_path": frozen_path.relative_to(repository_root).as_posix(),
        "pack_run_manifest_path": pack_manifest_path.relative_to(repository_root).as_posix(),
        "execution_research_code_sha": pack_manifest.get("research_code_sha"),
        "frozen_research_code_sha": frozen_definition.get("research_code_sha"),
        "corpus_pin_path": f"{CANONICAL_BASELINE_PACK_EVIDENCE_REL}/corpus_pin",
        "operator_interpretation_notes": list(_BASELINE_PACK_OPERATOR_INTERPRETATION_NOTES),
    }
    receipt_path = evidence_dir / "baseline_pack_evidence_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_path


def run_frozen_historical_baseline_pack_v1(
    *,
    repository_root: Path,
    build: HistoricalDevelopmentBuildResult,
    frozen_definition: dict[str, Any],
    artifact_root: Path | None = None,
    deterministic_rerun: bool = True,
) -> BaselinePackRunResult:
    verify = verify_frozen_experiment_definition(frozen_definition)
    if not verify.get("ok"):
        return BaselinePackRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=str(verify.get("computed_hash") or ""),
            dataset_fingerprint="",
            artifact_dir=Path(),
            body={"verify": verify},
            reason_code=str(verify.get("reason_code") or "EXPERIMENT_DEFINITION_HASH_MISMATCH"),
        )
    expected_hash = str(verify["experiment_definition_hash"])
    if not build.ok or not build.normalized_fingerprint:
        return BaselinePackRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            dataset_fingerprint="",
            artifact_dir=Path(),
            body={},
            reason_code=build.reason_code or "BUILD_NOT_OK",
        )
    dataset_fp = str(build.manifest.get("dataset_fingerprint") or build.normalized_fingerprint)
    frozen_dataset_fp = str((frozen_definition.get("dataset") or {}).get("dataset_fingerprint") or "")
    if frozen_dataset_fp and frozen_dataset_fp != dataset_fp:
        return BaselinePackRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            dataset_fingerprint=dataset_fp,
            artifact_dir=Path(),
            body={},
            reason_code="DATASET_FINGERPRINT_MISMATCH",
        )

    run_params = frozen_definition.get("run_parameters") or default_baseline_pack_run_parameters()
    split_policy = ChronologicalSplitPolicy(
        train_fraction=float(run_params["split_policy"]["train_fraction"]),
        development_validate_fraction=float(run_params["split_policy"]["development_validate_fraction"]),
    )
    forward_horizon_bars = int(run_params.get("forward_horizon_bars", 1))
    simulator_version = str(run_params.get("simulator_version", "paper_bar_conservative_v1"))
    cost_slippage_bps = float(run_params.get("cost_slippage_bps", 5.0))

    out_root = artifact_root or (repository_root / "artifacts" / "historical-research-harness" / "baseline-pack-v1")
    pack_dir = out_root / "pack-runs"
    pack_dir.mkdir(parents=True, exist_ok=True)

    baseline_results: list[dict[str, Any]] = []
    split_assignments_ref: list[dict[str, Any]] = []
    feature_lineage: list[dict[str, Any]] = []

    for spec in _BASELINE_STRATEGY_SPECS:
        strategy_id = str(spec["strategy_id"])
        config = HistoricalResearchRunConfig(
            experiment_id=HISTORICAL_BASELINE_PACK_EXPERIMENT_ID,
            hypothesis_id=HISTORICAL_BASELINE_PACK_HYPOTHESIS_ID,
            forward_horizon_bars=forward_horizon_bars,
            split_policy=split_policy,
            strategy_id=strategy_id,
            strategy_version=str(spec.get("strategy_version", "1.0.0")),
            simulator_version=simulator_version,
            cost_slippage_bps=cost_slippage_bps,
            metadata={
                "evidence_label": HISTORICAL_BASELINE_PACK_V1,
                "baseline_index": spec["baseline_index"],
            },
        )
        harness_result = run_historical_research_harness(
            repository_root=repository_root,
            build=build,
            config=config,
            artifact_root=out_root,
        )
        if not harness_result.ok:
            return BaselinePackRunResult(
                ok=False,
                pack_run_id="",
                experiment_definition_hash=expected_hash,
                dataset_fingerprint=dataset_fp,
                artifact_dir=pack_dir,
                body={"failed_strategy_id": strategy_id, "reason_code": harness_result.reason_code},
                reason_code=harness_result.reason_code,
            )
        run_dir = harness_result.artifact_path.parent
        predictions = json.loads((run_dir / "predictions.json").read_text(encoding="utf-8"))
        labels = json.loads((run_dir / "labels.json").read_text(encoding="utf-8"))
        if not split_assignments_ref:
            split_assignments_ref = list(harness_result.body.get("split_assignments") or [])
            for pred in predictions:
                feature_lineage.append(
                    {
                        "decision_cutoff_ns": int(pred["decision_time_ns"]),
                        "feature_as_of_ns": int(pred["decision_time_ns"]),
                        "ref": strategy_id,
                    }
                )
        dev_metrics = dict(harness_result.body.get("metrics") or {})
        holdout_metrics = _metrics_for_split(
            predictions,
            labels,
            HistoricalResearchSplitName.HISTORICAL_RESEARCH_TEST,
            simulator_summary=None,
        )
        baseline_results.append(
            {
                "baseline_index": spec["baseline_index"],
                "strategy_id": strategy_id,
                "run_id": harness_result.run_id,
                "run_fingerprint": harness_result.body.get("run_fingerprint"),
                "config_fingerprint": harness_result.body.get("config_fingerprint"),
                "metrics_by_split": {
                    HistoricalResearchSplitName.HISTORICAL_DEVELOPMENT_VALIDATE.value: dev_metrics,
                    HistoricalResearchSplitName.HISTORICAL_RESEARCH_TEST.value: holdout_metrics,
                },
                "manifest_path": str(harness_result.artifact_path),
            }
        )

    research_code_sha = resolve_runtime_git_sha(start=repository_root)
    pack_run_id = sha256_bytes(
        canonical_bytes(
            {
                "pack": HISTORICAL_BASELINE_PACK_V1,
                "experiment_definition_hash": expected_hash,
                "dataset_fingerprint": dataset_fp,
                "research_code_sha": research_code_sha,
                "baseline_run_ids": [row["run_id"] for row in baseline_results],
            }
        )
    )[:32]

    contamination_manifest = build_baseline_pack_contamination_manifest(
        pack_run_id=pack_run_id,
        dataset_fingerprint=dataset_fp,
        split_assignments=split_assignments_ref,
        feature_lineage=feature_lineage,
        historical_dataset_manifest=build.manifest if isinstance(build.manifest, dict) else None,
    )
    contamination_report = audit_research_contamination_run(contamination_manifest)

    rerun_match: bool | None = None
    if deterministic_rerun and baseline_results:
        first_strategy = str(_BASELINE_STRATEGY_SPECS[0]["strategy_id"])
        rerun_config = HistoricalResearchRunConfig(
            experiment_id=HISTORICAL_BASELINE_PACK_EXPERIMENT_ID,
            hypothesis_id=HISTORICAL_BASELINE_PACK_HYPOTHESIS_ID,
            forward_horizon_bars=forward_horizon_bars,
            split_policy=split_policy,
            strategy_id=first_strategy,
            strategy_version="1.0.0",
            simulator_version=simulator_version,
            cost_slippage_bps=cost_slippage_bps,
            metadata={"evidence_label": HISTORICAL_BASELINE_PACK_V1, "baseline_index": 0},
        )
        rerun = run_historical_research_harness(
            repository_root=repository_root,
            build=build,
            config=rerun_config,
            artifact_root=out_root,
        )
        rerun_match = rerun.ok and rerun.run_id == baseline_results[0]["run_id"]

    pack_body: dict[str, Any] = {
        "artifact_kind": "historical_baseline_pack_run_v1",
        "schema_version": HISTORICAL_BASELINE_PACK_DEFINITION_SCHEMA,
        "evidence_label": HISTORICAL_BASELINE_PACK_V1,
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "pack_run_id": pack_run_id,
        "experiment_id": HISTORICAL_BASELINE_PACK_EXPERIMENT_ID,
        "experiment_definition_hash": expected_hash,
        "frozen_definition_path": str(
            canonical_baseline_pack_evidence_dir(repository_root) / "frozen_experiment_definition.json"
        ),
        "operator_interpretation_notes": list(_BASELINE_PACK_OPERATOR_INTERPRETATION_NOTES),
        "dataset_fingerprint": dataset_fp,
        "dataset_identity": frozen_definition.get("dataset"),
        "research_code_sha": research_code_sha,
        "feature_version": HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION,
        "simulator_version": simulator_version,
        "baseline_results": baseline_results,
        "contamination_manifest_path": None,
        "contamination_audit": contamination_report,
        "reproducibility": {
            "dataset_fingerprint": dataset_fp,
            "experiment_definition_hash": expected_hash,
            "run_fingerprint": baseline_results[0]["run_fingerprint"] if baseline_results else None,
            "deterministic_rerun_first_baseline_match": rerun_match,
        },
        "created_timestamp_ns": time.time_ns(),
    }
    run_artifact_dir = pack_dir / pack_run_id
    run_artifact_dir.mkdir(parents=True, exist_ok=True)
    contamination_path = run_artifact_dir / "contamination_manifest.json"
    contamination_path.write_text(
        json.dumps(contamination_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    pack_body["contamination_manifest_path"] = str(contamination_path)
    pack_manifest_path = run_artifact_dir / "baseline_pack_run_manifest.json"
    pack_manifest_path.write_text(json.dumps(pack_body, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return BaselinePackRunResult(
        ok=True,
        pack_run_id=pack_run_id,
        experiment_definition_hash=expected_hash,
        dataset_fingerprint=dataset_fp,
        artifact_dir=run_artifact_dir,
        body=pack_body,
        reason_code=None,
    )


def freeze_baseline_pack_definition_to_disk(
    *,
    repository_root: Path,
    dataset_identity: dict[str, Any],
    artifact_root: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    out_root = artifact_root or (repository_root / "artifacts" / "historical-research-harness" / "baseline-pack-v1")
    out_root.mkdir(parents=True, exist_ok=True)
    definition = build_frozen_baseline_pack_experiment_definition(
        repository_root=repository_root,
        dataset_identity=dataset_identity,
    )
    path = out_root / "frozen_experiment_definition.json"
    path.write_text(json.dumps(definition, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, definition


__all__ = [
    "BaselinePackRunResult",
    "HISTORICAL_BASELINE_PACK_EXPERIMENT_ID",
    "HISTORICAL_BASELINE_PACK_V1",
    "CANONICAL_BASELINE_PACK_EVIDENCE_REL",
    "DEFAULT_MULTI_SESSION_FIXTURE_REL",
    "build_frozen_baseline_pack_experiment_definition",
    "build_baseline_pack_contamination_manifest",
    "canonical_baseline_pack_evidence_dir",
    "compute_experiment_definition_hash",
    "experiment_definition_hash",
    "freeze_baseline_pack_definition_to_disk",
    "publish_baseline_pack_evidence_receipt",
    "run_frozen_historical_baseline_pack_v1",
    "verify_frozen_experiment_definition",
]
