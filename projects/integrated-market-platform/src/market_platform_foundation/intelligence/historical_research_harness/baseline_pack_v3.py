"""Frozen Historical Baseline Pack v3 (OpenD fill economics; IMP-05 Lane R3)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping

from ...canonical import canonical_bytes, sha256_bytes
from ...execution.simulator import SIMULATOR_VERSION
from ...market_data.historical_development.builder import (
    HistoricalDevelopmentBuildResult,
    load_historical_development_build_from_evidence_corpus,
)
from ...paper.calibration.bar_ohlcv_prospective_proof import resolve_runtime_git_sha
from ...paper.calibration.dual_corpus import CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT
from ...paper.calibration.dual_corpus.contamination_auditor import audit_research_contamination_run
from .baseline_pack import (
    BaselinePackRunResult,
    build_baseline_pack_contamination_manifest,
    compute_experiment_definition_hash,
    default_baseline_pack_run_parameters,
    verify_frozen_experiment_definition,
)
from .baseline_pack_v2 import (
    OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT,
    _BASELINE_STRATEGY_SPECS,
    _dev_validate_coupling_counts,
    _metrics_for_split,
    verify_pinned_opend_corpus_fingerprint,
)
from .features import HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION
from .fill_economics import ACCOUNTING_VERSION, COST_MODEL_VERSION
from .pipeline import run_historical_research_harness
from .prediction_coupling import build_signal_interpretations_from_predictions
from .simulator import SIMULATOR_RESEARCH_RESULT_KIND
from .strategies import BASELINE_STRATEGY_NO_TRADE_V1
from .types import ChronologicalSplitPolicy, HistoricalResearchRunConfig, HistoricalResearchSplitName

HISTORICAL_BASELINE_PACK_V3 = "HISTORICAL_BASELINE_V3_OPEND_FILL_ECONOMICS"
HISTORICAL_BASELINE_PACK_V3_EXPERIMENT_ID = "imp-integrate-experiment-05-r3-opend-fill-economics-v3"
HISTORICAL_BASELINE_PACK_V3_HYPOTHESIS_ID = "LANE-H-HYP-SIMULATOR-FILL-ECONOMICS-V3"
HISTORICAL_BASELINE_PACK_V3_DEFINITION_KIND = "historical_baseline_pack_experiment_definition_v3"
HISTORICAL_BASELINE_PACK_V3_DEFINITION_SCHEMA = "imp.historical-baseline-pack/3.0.0"
BOUNDED_HISTORICAL_OBSERVATION = "BOUNDED_HISTORICAL_OBSERVATION"

CANONICAL_BASELINE_PACK_V3_EVIDENCE_REL = (
    "evidence/historical-research/imp-integrate-experiment-05-r3-opend-fill-economics-v3"
)

V2_IMMUTABLE_EXPERIMENT_HASH = (
    "E8C9ADB9E295EBE913C254FCBBBDDC48A794D9FDE79492CB341138855A67C2A4"
)


def canonical_baseline_pack_v3_evidence_dir(repository_root: Path) -> Path:
    return repository_root / CANONICAL_BASELINE_PACK_V3_EVIDENCE_REL


def load_pinned_opend_build_v3(repository_root: Path) -> HistoricalDevelopmentBuildResult:
    corpus_dir = canonical_baseline_pack_v3_evidence_dir(repository_root) / "corpus_pin"
    return load_historical_development_build_from_evidence_corpus(
        repository_root=repository_root,
        corpus_dir=corpus_dir,
    )


def _pack_execution_fingerprint(baseline_results: list[dict[str, Any]]) -> str:
    rows = [
        {
            "baseline_index": row.get("baseline_index"),
            "strategy_id": row.get("strategy_id"),
            "run_id": row.get("run_id"),
            "run_fingerprint": row.get("run_fingerprint"),
        }
        for row in baseline_results
    ]
    return sha256_bytes(canonical_bytes({"baselines": rows}))


def promote_pre_execution_v3_freeze_to_disk(
    *,
    repository_root: Path,
    code_sha: str | None = None,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    """Finalize v3 freeze from committed pre-execution definition (Lane A landed)."""

    evidence_dir = canonical_baseline_pack_v3_evidence_dir(repository_root)
    pre_path = evidence_dir / "pre_execution_frozen_experiment_definition.json"
    if not pre_path.is_file():
        raise ValueError("PRE_EXECUTION_DEFINITION_MISSING")

    corpus_pin = evidence_dir / "corpus_pin"
    fingerprint_verification = verify_pinned_opend_corpus_fingerprint(
        repository_root=repository_root,
        corpus_dir=corpus_pin,
    )
    if not fingerprint_verification.get("ok"):
        raise ValueError(str(fingerprint_verification.get("reason_code") or "DATASET_REPRODUCIBILITY_FAILURE"))

    frozen = json.loads(pre_path.read_text(encoding="utf-8"))
    if str(frozen.get("experiment_id") or "") != HISTORICAL_BASELINE_PACK_V3_EXPERIMENT_ID:
        raise ValueError("EXPERIMENT_ID_MISMATCH")

    dataset_fp = str((frozen.get("dataset") or {}).get("dataset_fingerprint") or "")
    if dataset_fp != OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT:
        raise ValueError("DATASET_FINGERPRINT_MISMATCH")

    research_sha = code_sha or resolve_runtime_git_sha(start=repository_root)
    run_params = dict(frozen.get("run_parameters") or default_baseline_pack_run_parameters())
    run_params["simulator_version"] = SIMULATOR_VERSION
    run_params["prediction_coupled_simulator"] = True

    frozen["artifact_kind"] = HISTORICAL_BASELINE_PACK_V3_DEFINITION_KIND
    frozen["schema_version"] = HISTORICAL_BASELINE_PACK_V3_DEFINITION_SCHEMA
    frozen["evidence_label"] = HISTORICAL_BASELINE_PACK_V3
    frozen["feature_version"] = HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION
    frozen["accounting_version"] = ACCOUNTING_VERSION
    frozen["cost_model_version"] = COST_MODEL_VERSION
    frozen["research_code_sha"] = research_sha
    frozen["run_parameters"] = run_params
    frozen["execution_status"] = "DEFINITION_FROZEN_READY_FOR_EXECUTION"
    frozen["experiment_definition_hash"] = compute_experiment_definition_hash(frozen)

    frozen_path = evidence_dir / "frozen_experiment_definition.json"
    frozen_path.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    verification_path = evidence_dir / "dataset_fingerprint_verification.json"
    verification_body = {
        **fingerprint_verification,
        "experiment_id": HISTORICAL_BASELINE_PACK_V3_EXPERIMENT_ID,
        "hypothesis_id": HISTORICAL_BASELINE_PACK_V3_HYPOTHESIS_ID,
        "corpus_pin_path": corpus_pin.relative_to(repository_root).as_posix(),
        "verified_at_promotion": True,
    }
    verification_path.write_text(json.dumps(verification_body, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    template_path = evidence_dir / "pre_execution_freeze_template.json"
    if template_path.is_file():
        template = json.loads(template_path.read_text(encoding="utf-8"))
        template["SIMULATOR_VERSION"] = SIMULATOR_VERSION
        template["ACCOUNTING_VERSION"] = ACCOUNTING_VERSION
        template["COST_MODEL_VERSION"] = COST_MODEL_VERSION
        template["CODE_SHA"] = research_sha
        template["EXPERIMENT_HASH"] = frozen["experiment_definition_hash"]
        template_path.write_text(json.dumps(template, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    freeze_receipt = {
        "artifact_kind": "historical_baseline_pack_v3_freeze_receipt_v1",
        "EXPERIMENT_DEFINITION_FROZEN": "YES",
        "execution_status": frozen["execution_status"],
        "performance_run": "NO",
        "experiment_id": HISTORICAL_BASELINE_PACK_V3_EXPERIMENT_ID,
        "hypothesis_id": HISTORICAL_BASELINE_PACK_V3_HYPOTHESIS_ID,
        "experiment_definition_hash": frozen["experiment_definition_hash"],
        "dataset_fingerprint": dataset_fp,
        "research_code_sha": research_sha,
        "accounting_version": ACCOUNTING_VERSION,
        "cost_model_version": COST_MODEL_VERSION,
        "simulator_version": SIMULATOR_VERSION,
        "frozen_definition_path": frozen_path.relative_to(repository_root).as_posix(),
        "pre_execution_definition_path": pre_path.relative_to(repository_root).as_posix(),
        "dataset_fingerprint_verification_path": verification_path.relative_to(repository_root).as_posix(),
        "canonical_evidence_dir": CANONICAL_BASELINE_PACK_V3_EVIDENCE_REL,
        "prior_immutable_experiment_hash": V2_IMMUTABLE_EXPERIMENT_HASH,
        "promoted_timestamp_ns": time.time_ns(),
    }
    receipt_path = evidence_dir / "baseline_pack_v3_freeze_receipt.json"
    receipt_path.write_text(json.dumps(freeze_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return frozen_path, frozen, freeze_receipt


def _execute_baseline_pack_once(
    *,
    repository_root: Path,
    build: HistoricalDevelopmentBuildResult,
    frozen_definition: Mapping[str, Any],
    expected_hash: str,
    dataset_fp: str,
    artifact_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    run_params = frozen_definition.get("run_parameters") or default_baseline_pack_run_parameters()
    split_policy = ChronologicalSplitPolicy(
        train_fraction=float(run_params["split_policy"]["train_fraction"]),
        development_validate_fraction=float(run_params["split_policy"]["development_validate_fraction"]),
    )
    forward_horizon_bars = int(run_params.get("forward_horizon_bars", 1))
    simulator_version = str(run_params.get("simulator_version", SIMULATOR_VERSION))
    cost_slippage_bps = float(run_params.get("cost_slippage_bps", 5.0))

    instrument_id = str((build.manifest.get("universe") or ["canonical:EQUITY:XNAS:AAPL"])[0])
    baseline_results: list[dict[str, Any]] = []
    split_assignments_ref: list[dict[str, Any]] = []
    feature_lineage: list[dict[str, Any]] = []

    for spec in _BASELINE_STRATEGY_SPECS:
        strategy_id = str(spec["strategy_id"])
        config = HistoricalResearchRunConfig(
            experiment_id=HISTORICAL_BASELINE_PACK_V3_EXPERIMENT_ID,
            hypothesis_id=HISTORICAL_BASELINE_PACK_V3_HYPOTHESIS_ID,
            forward_horizon_bars=forward_horizon_bars,
            split_policy=split_policy,
            strategy_id=strategy_id,
            strategy_version=str(spec.get("strategy_version", "1.0.0")),
            simulator_version=simulator_version,
            cost_slippage_bps=cost_slippage_bps,
            metadata={
                "evidence_label": HISTORICAL_BASELINE_PACK_V3,
                "baseline_index": spec["baseline_index"],
            },
        )
        harness_result = run_historical_research_harness(
            repository_root=repository_root,
            build=build,
            config=config,
            artifact_root=artifact_root,
        )
        if not harness_result.ok:
            raise RuntimeError(harness_result.reason_code or "HARNESS_RUN_FAILED")

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
        sim_block = harness_result.body.get("simulator") or {}
        if sim_block.get("result_kind") != SIMULATOR_RESEARCH_RESULT_KIND:
            raise RuntimeError("SIMULATOR_RESULT_KIND_MISMATCH")

        coupling = _dev_validate_coupling_counts(predictions, instrument_id=instrument_id)
        fills = int(dev_metrics.get("simulated_fills") or dev_metrics.get("fills") or 0)
        turnover = dev_metrics.get("turnover")
        coupling["signals"] = coupling.pop("directional_signals")
        coupling["intents"] = coupling.pop("trade_intents")
        coupling["fills"] = fills
        coupling["turnover"] = turnover
        coupling["gross_pnl"] = dev_metrics.get("gross_pnl")
        coupling["transaction_costs"] = dev_metrics.get("transaction_costs")
        coupling["net_pnl"] = dev_metrics.get("net_pnl")
        coupling["traded_notional"] = dev_metrics.get("traded_notional")
        coupling["exposure"] = dev_metrics.get("exposure")
        coupling["drawdown"] = dev_metrics.get("drawdown")
        coupling["directional_accuracy"] = dev_metrics.get("directional_accuracy")

        if strategy_id == BASELINE_STRATEGY_NO_TRADE_V1:
            if not (
                coupling["signals"] == 0
                and coupling["intents"] == 0
                and fills == 0
                and (turnover == 0 or turnover == 0.0)
            ):
                raise RuntimeError("NO_TRADE_BASELINE_INVARIANT_FAILED")

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
                "coupling_observation": coupling,
                "metrics_by_split": {
                    HistoricalResearchSplitName.HISTORICAL_DEVELOPMENT_VALIDATE.value: dev_metrics,
                    HistoricalResearchSplitName.HISTORICAL_RESEARCH_TEST.value: holdout_metrics,
                },
                "manifest_path": str(harness_result.artifact_path),
            }
        )

    return baseline_results, split_assignments_ref, feature_lineage


def run_frozen_historical_baseline_pack_v3(
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
    if frozen_definition.get("execution_status") not in {
        "DEFINITION_FROZEN_READY_FOR_EXECUTION",
        "DEFINITION_FROZEN_NOT_EXECUTED",
    }:
        return BaselinePackRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            dataset_fingerprint="",
            artifact_dir=Path(),
            body={},
            reason_code="EXECUTION_STATUS_NOT_FROZEN",
        )

    corpus_pin = canonical_baseline_pack_v3_evidence_dir(repository_root) / "corpus_pin"
    fingerprint_verification = verify_pinned_opend_corpus_fingerprint(
        repository_root=repository_root,
        corpus_dir=corpus_pin,
    )
    if not fingerprint_verification.get("ok"):
        return BaselinePackRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            dataset_fingerprint="",
            artifact_dir=Path(),
            body={"fingerprint_verification": fingerprint_verification},
            reason_code=str(fingerprint_verification.get("reason_code") or "DATASET_REPRODUCIBILITY_FAILURE"),
        )

    if not build.ok:
        return BaselinePackRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            dataset_fingerprint="",
            artifact_dir=Path(),
            body={},
            reason_code=build.reason_code or "BUILD_NOT_OK",
        )

    dataset_fp = str((frozen_definition.get("dataset") or {}).get("dataset_fingerprint") or "")
    if dataset_fp != OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT:
        return BaselinePackRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            dataset_fingerprint=dataset_fp,
            artifact_dir=Path(),
            body={},
            reason_code="DATASET_FINGERPRINT_MISMATCH",
        )

    out_root = artifact_root or (repository_root / "artifacts" / "historical-research-harness" / "baseline-pack-v3")
    pack_dir = out_root / "pack-runs"
    pack_dir.mkdir(parents=True, exist_ok=True)

    run_params = frozen_definition.get("run_parameters") or {}
    simulator_version = str(run_params.get("simulator_version", SIMULATOR_VERSION))

    try:
        baseline_results, split_assignments_ref, feature_lineage = _execute_baseline_pack_once(
            repository_root=repository_root,
            build=build,
            frozen_definition=frozen_definition,
            expected_hash=expected_hash,
            dataset_fp=dataset_fp,
            artifact_root=out_root,
        )
    except RuntimeError as exc:
        return BaselinePackRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            dataset_fingerprint=dataset_fp,
            artifact_dir=pack_dir,
            body={},
            reason_code=str(exc),
        )

    first_run_fingerprint = _pack_execution_fingerprint(baseline_results)
    second_run_fingerprint: str | None = None
    rerun_match: bool | None = None
    if deterministic_rerun:
        try:
            rerun_results, _, _ = _execute_baseline_pack_once(
                repository_root=repository_root,
                build=build,
                frozen_definition=frozen_definition,
                expected_hash=expected_hash,
                dataset_fp=dataset_fp,
                artifact_root=out_root,
            )
            second_run_fingerprint = _pack_execution_fingerprint(rerun_results)
            rerun_match = second_run_fingerprint == first_run_fingerprint
        except RuntimeError:
            rerun_match = False

    research_code_sha = resolve_runtime_git_sha(start=repository_root)
    pack_run_id = sha256_bytes(
        canonical_bytes(
            {
                "pack": HISTORICAL_BASELINE_PACK_V3,
                "experiment_definition_hash": expected_hash,
                "dataset_fingerprint": dataset_fp,
                "research_code_sha": research_code_sha,
                "baseline_run_ids": [row["run_id"] for row in baseline_results],
                "first_run_fingerprint": first_run_fingerprint,
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

    pack_body: dict[str, Any] = {
        "artifact_kind": "historical_baseline_pack_run_v3",
        "schema_version": HISTORICAL_BASELINE_PACK_V3_DEFINITION_SCHEMA,
        "evidence_label": HISTORICAL_BASELINE_PACK_V3,
        "observation_language": BOUNDED_HISTORICAL_OBSERVATION,
        "result_kind": SIMULATOR_RESEARCH_RESULT_KIND,
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "pack_run_id": pack_run_id,
        "experiment_id": HISTORICAL_BASELINE_PACK_V3_EXPERIMENT_ID,
        "hypothesis_id": HISTORICAL_BASELINE_PACK_V3_HYPOTHESIS_ID,
        "experiment_definition_hash": expected_hash,
        "frozen_definition_path": str(
            canonical_baseline_pack_v3_evidence_dir(repository_root) / "frozen_experiment_definition.json"
        ),
        "dataset_fingerprint": dataset_fp,
        "dataset_identity": frozen_definition.get("dataset"),
        "research_code_sha": research_code_sha,
        "frozen_research_code_sha": frozen_definition.get("research_code_sha"),
        "feature_version": HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION,
        "accounting_version": frozen_definition.get("accounting_version", ACCOUNTING_VERSION),
        "cost_model_version": frozen_definition.get("cost_model_version", COST_MODEL_VERSION),
        "simulator_version": simulator_version,
        "prediction_coupled_simulator": True,
        "baseline_results": baseline_results,
        "contamination_audit": contamination_report,
        "reproducibility": {
            "dataset_fingerprint": dataset_fp,
            "experiment_definition_hash": expected_hash,
            "first_run_fingerprint": first_run_fingerprint,
            "second_run_fingerprint": second_run_fingerprint,
            "deterministic_rerun_match": rerun_match,
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

    if rerun_match is False:
        return BaselinePackRunResult(
            ok=False,
            pack_run_id=pack_run_id,
            experiment_definition_hash=expected_hash,
            dataset_fingerprint=dataset_fp,
            artifact_dir=run_artifact_dir,
            body=pack_body,
            reason_code="DETERMINISTIC_RERUN_FINGERPRINT_MISMATCH",
        )

    return BaselinePackRunResult(
        ok=True,
        pack_run_id=pack_run_id,
        experiment_definition_hash=expected_hash,
        dataset_fingerprint=dataset_fp,
        artifact_dir=run_artifact_dir,
        body=pack_body,
        reason_code=None,
    )


def publish_baseline_pack_v3_evidence_receipt(
    *,
    repository_root: Path,
    frozen_definition: dict[str, Any],
    pack_result: BaselinePackRunResult,
) -> Path:
    evidence_dir = canonical_baseline_pack_v3_evidence_dir(repository_root)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    frozen_path = evidence_dir / "frozen_experiment_definition.json"

    pack_manifest = dict(pack_result.body)
    pack_manifest["frozen_definition_path"] = frozen_path.relative_to(repository_root).as_posix()
    pack_manifest["canonical_evidence_dir"] = CANONICAL_BASELINE_PACK_V3_EVIDENCE_REL
    pack_manifest_path = evidence_dir / "baseline_pack_run_manifest.json"
    pack_manifest_path.write_text(json.dumps(pack_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    contamination_src = pack_result.artifact_dir / "contamination_manifest.json"
    if contamination_src.is_file():
        contamination_body = json.loads(contamination_src.read_text(encoding="utf-8"))
        (evidence_dir / "contamination_manifest.json").write_text(
            json.dumps(contamination_body, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    protocol_path = evidence_dir / "experiment_protocol_v3.json"
    if protocol_path.is_file():
        protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
        protocol["contamination_auditor_execution_status"] = "EXECUTED"
        protocol["performance_run_authorized"] = True
        protocol["execution_phase"] = "EXECUTED_BOUNDED_HISTORICAL_OBSERVATION"
        protocol_path.write_text(json.dumps(protocol, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    receipt = {
        "artifact_kind": "historical_baseline_pack_v3_evidence_receipt_v1",
        "evidence_label": HISTORICAL_BASELINE_PACK_V3,
        "observation_language": BOUNDED_HISTORICAL_OBSERVATION,
        "EXPERIMENT_DEFINITION_FROZEN": "YES",
        "performance_run": "YES",
        "execution_status": "EXECUTED_BOUNDED_HISTORICAL_OBSERVATION",
        "experiment_definition_hash": pack_result.experiment_definition_hash,
        "dataset_fingerprint": pack_result.dataset_fingerprint,
        "pack_run_id": pack_result.pack_run_id,
        "frozen_definition_path": frozen_path.relative_to(repository_root).as_posix(),
        "pack_run_manifest_path": pack_manifest_path.relative_to(repository_root).as_posix(),
        "execution_research_code_sha": pack_manifest.get("research_code_sha"),
        "frozen_research_code_sha": frozen_definition.get("research_code_sha"),
        "contamination_status": (pack_result.body.get("contamination_audit") or {}).get("CONTAMINATION_STATUS"),
        "reproducibility": pack_result.body.get("reproducibility"),
    }
    receipt_path = evidence_dir / "baseline_pack_v3_evidence_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_path


__all__ = [
    "CANONICAL_BASELINE_PACK_V3_EVIDENCE_REL",
    "HISTORICAL_BASELINE_PACK_V3",
    "HISTORICAL_BASELINE_PACK_V3_EXPERIMENT_ID",
    "HISTORICAL_BASELINE_PACK_V3_HYPOTHESIS_ID",
    "canonical_baseline_pack_v3_evidence_dir",
    "load_pinned_opend_build_v3",
    "promote_pre_execution_v3_freeze_to_disk",
    "publish_baseline_pack_v3_evidence_receipt",
    "run_frozen_historical_baseline_pack_v3",
]
