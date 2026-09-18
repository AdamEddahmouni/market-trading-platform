"""Frozen Historical Baseline Pack v2 (OpenD real corpus; IMP-05 Lane R2)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from ...canonical import canonical_bytes, sha256_bytes
from ...paper.calibration.bar_ohlcv_prospective_proof import resolve_runtime_git_sha
from ...paper.calibration.dual_corpus import CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT
from ...market_data.historical_development.builder import (
    HistoricalDevelopmentBuildResult,
    load_historical_development_build_from_evidence_corpus,
)
from ...paper.calibration.dual_corpus.contamination_auditor import audit_research_contamination_run
from .baseline_pack import (
    BaselinePackRunResult,
    build_baseline_pack_contamination_manifest,
    compute_experiment_definition_hash,
    default_baseline_pack_run_parameters,
    verify_frozen_experiment_definition,
)
from .metrics import compute_component_research_metrics
from .pipeline import run_historical_research_harness
from .prediction_coupling import build_signal_interpretations_from_predictions
from .simulator import SIMULATOR_RESEARCH_RESULT_KIND
from .types import ChronologicalSplitPolicy, HistoricalResearchRunConfig, HistoricalResearchSplitName
from .features import DEFAULT_HISTORICAL_RESEARCH_FEATURES, HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION
from .strategies import (
    BASELINE_STRATEGY_MEAN_REVERSION_5M_SIGN_V1,
    BASELINE_STRATEGY_MOMENTUM_5M_SIGN_V1,
    BASELINE_STRATEGY_NO_TRADE_V1,
    BASELINE_STRATEGY_VOLUME_MOMENTUM_5M_V1,
)
from .types import HISTORICAL_RESEARCH_HARNESS_VERSION

HISTORICAL_BASELINE_PACK_V2 = "HISTORICAL_BASELINE_V2_OPEND"
HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID = "imp-integrate-experiment-05-r2-opend-baseline-pack-v2"
HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID = "LANE-E-HYP-OPEND-MULTI-SESSION-V2"
HISTORICAL_BASELINE_PACK_V2_DEFINITION_KIND = "historical_baseline_pack_experiment_definition_v2"
HISTORICAL_BASELINE_PACK_V2_DEFINITION_SCHEMA = "imp.historical-baseline-pack/2.0.0"
HISTORICAL_BASELINE_PACK_V2_RANDOM_SEED = 0

OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT = (
    "355FDBB852B94B964B62331839B58C3A336D1B52DB2F17FA05D30BA31389885B"
)
OPEND_AAPL_VERIFIED_SESSION_DATES: tuple[str, ...] = (
    "2026-09-10",
    "2026-09-11",
    "2026-09-14",
    "2026-09-15",
    "2026-09-16",
)
LANE_B_VERIFICATION_RECEIPT_REL = "evidence/market_data/lane_b/real-historical-provider-verification.json"

CANONICAL_BASELINE_PACK_V2_EVIDENCE_REL = (
    "evidence/historical-research/imp-integrate-experiment-05-r2-opend-baseline-pack-v2"
)

PRIOR_V2_FREEZE_CODE_SHA = "7d67d48edc5760e218f946ee7fd836d6b5c431a2"
PRIOR_V2_EXPERIMENT_DEFINITION_HASH = (
    "109F3499BD70CB006707BAA2242EDCD5A4614714C61481BF2540B56655677F74"
)
BOUNDED_HISTORICAL_OBSERVATION = "BOUNDED_HISTORICAL_OBSERVATION"

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


def canonical_baseline_pack_v2_evidence_dir(repository_root: Path) -> Path:
    return repository_root / CANONICAL_BASELINE_PACK_V2_EVIDENCE_REL


def recompute_normalized_corpus_fingerprint(
    *,
    bars: Sequence[Mapping[str, Any]],
    historical_provenance: Mapping[str, Any],
) -> str:
    """Canonical normalized bar fingerprint (bars + provenance), Lane B compatible."""

    return sha256_bytes(
        canonical_bytes(
            {
                "bars": list(bars),
                "provenance": dict(historical_provenance),
            }
        )
    )


def verify_pinned_opend_corpus_fingerprint(
    *,
    repository_root: Path,
    corpus_dir: Path,
    expected_normalized_fingerprint: str = OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT,
) -> dict[str, Any]:
    """Recompute normalized fingerprint from pinned corpus; fail closed on mismatch."""

    manifest_path = corpus_dir / "dataset_manifest.json"
    if not manifest_path.is_file():
        return {
            "ok": False,
            "reason_code": "CORPUS_MANIFEST_MISSING",
            "expected_normalized_fingerprint": expected_normalized_fingerprint,
            "computed_normalized_fingerprint": None,
        }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    provenance = (manifest.get("lineage") or {}).get("historical_provenance")
    if not isinstance(provenance, dict):
        return {
            "ok": False,
            "reason_code": "HISTORICAL_PROVENANCE_MISSING",
            "expected_normalized_fingerprint": expected_normalized_fingerprint,
            "computed_normalized_fingerprint": None,
        }
    normalized_files = sorted((corpus_dir / "normalized").glob("*_normalized.json"))
    if not normalized_files:
        return {
            "ok": False,
            "reason_code": "CORPUS_NORMALIZED_MISSING",
            "expected_normalized_fingerprint": expected_normalized_fingerprint,
            "computed_normalized_fingerprint": None,
        }
    bars = json.loads(normalized_files[0].read_text(encoding="utf-8"))
    computed = recompute_normalized_corpus_fingerprint(bars=bars, historical_provenance=provenance)
    session_dates = list((manifest.get("interval") or {}).get("session_dates") or [])
    row_count = int(manifest.get("row_count") or len(bars))
    lane_b_path = repository_root / LANE_B_VERIFICATION_RECEIPT_REL
    lane_b_fp = None
    if lane_b_path.is_file():
        lane_b = json.loads(lane_b_path.read_text(encoding="utf-8"))
        lane_b_fp = str((lane_b.get("moomoo") or {}).get("normalized_fingerprint") or "")
    ok = computed == expected_normalized_fingerprint
    if ok and lane_b_fp and lane_b_fp != expected_normalized_fingerprint:
        ok = False
        reason = "LANE_B_RECEIPT_FINGERPRINT_MISMATCH"
    elif not ok:
        reason = "DATASET_REPRODUCIBILITY_FAILURE"
    else:
        reason = None
    return {
        "ok": ok,
        "reason_code": reason,
        "expected_normalized_fingerprint": expected_normalized_fingerprint,
        "computed_normalized_fingerprint": computed,
        "manifest_dataset_fingerprint": str(manifest.get("dataset_fingerprint") or ""),
        "row_count": row_count,
        "session_dates": session_dates,
        "lane_b_receipt_fingerprint": lane_b_fp,
        "verification_method": "recompute_normalized_corpus_fingerprint(bars, lineage.historical_provenance)",
    }


def build_opend_v2_dataset_identity(
    *,
    repository_root: Path,
    corpus_dir: Path,
    fingerprint_verification: Mapping[str, Any],
) -> dict[str, Any]:
    manifest = json.loads((corpus_dir / "dataset_manifest.json").read_text(encoding="utf-8"))
    interval = manifest.get("interval") or {}
    return {
        "dataset_id": str(manifest.get("dataset_id") or "HIST-DEV-AAPL"),
        "dataset_fingerprint": str(fingerprint_verification["computed_normalized_fingerprint"]),
        "manifest_dataset_fingerprint": str(manifest.get("dataset_fingerprint") or ""),
        "provider_id": "moomoo.real_historical",
        "provider_lineage_id": str(
            ((manifest.get("lineage") or {}).get("historical_provenance") or {}).get("provider_id")
            or "moomoo.opend"
        ),
        "instrument": "AAPL",
        "start_date": str(interval.get("start_date") or OPEND_AAPL_VERIFIED_SESSION_DATES[0]),
        "end_date": str(interval.get("end_date") or OPEND_AAPL_VERIFIED_SESSION_DATES[-1]),
        "session_dates": list(interval.get("session_dates") or OPEND_AAPL_VERIFIED_SESSION_DATES),
        "row_count": int(fingerprint_verification.get("row_count") or manifest.get("row_count") or 0),
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "corpus_pin_path": corpus_dir.relative_to(repository_root).as_posix(),
        "lane_b_verification_receipt_path": LANE_B_VERIFICATION_RECEIPT_REL,
    }


def build_frozen_baseline_pack_v2_experiment_definition(
    *,
    repository_root: Path,
    dataset_identity: dict[str, Any],
    code_sha: str | None = None,
    created_timestamp_ns: int | None = None,
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
        "artifact_kind": HISTORICAL_BASELINE_PACK_V2_DEFINITION_KIND,
        "schema_version": HISTORICAL_BASELINE_PACK_V2_DEFINITION_SCHEMA,
        "evidence_label": HISTORICAL_BASELINE_PACK_V2,
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "experiment_id": HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID,
        "hypothesis_id": HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID,
        "harness_version": HISTORICAL_RESEARCH_HARNESS_VERSION,
        "feature_version": HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION,
        "execution_status": "DEFINITION_FROZEN_NOT_EXECUTED",
        "target_definition": {
            "label_kind": "historical_research_forward_return_label_v1",
            "forward_horizon_bars": 1,
        },
        "feature_definitions": feature_specs,
        "baseline_strategies": list(_BASELINE_STRATEGY_SPECS),
        "run_parameters": default_baseline_pack_run_parameters(),
        "dataset": dataset_identity,
        "research_code_sha": research_code_sha,
        "created_timestamp_ns": created_timestamp_ns if created_timestamp_ns is not None else time.time_ns(),
        "governance": {
            "authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
            "item9_effect": "NONE",
            "item7_effect": "NONE",
            "ftep_effect": "NONE",
            "live_authority": "NONE",
            "promotional_language_forbidden": True,
            "prior_frozen_experiment_immutable": "imp-research-validation-04-lane-c-baseline-pack-v1",
        },
    }
    body["experiment_definition_hash"] = sha256_bytes(canonical_bytes(body))
    return body


def freeze_baseline_pack_v2_definition_to_disk(
    *,
    repository_root: Path,
    corpus_dir: Path | None = None,
    artifact_root: Path | None = None,
    code_sha: str | None = None,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    evidence_dir = artifact_root or canonical_baseline_pack_v2_evidence_dir(repository_root)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    pinned_corpus = corpus_dir or (evidence_dir / "corpus_pin")
    fingerprint_verification = verify_pinned_opend_corpus_fingerprint(
        repository_root=repository_root,
        corpus_dir=pinned_corpus,
    )
    if not fingerprint_verification.get("ok"):
        raise ValueError(str(fingerprint_verification.get("reason_code") or "DATASET_REPRODUCIBILITY_FAILURE"))
    dataset_identity = build_opend_v2_dataset_identity(
        repository_root=repository_root,
        corpus_dir=pinned_corpus,
        fingerprint_verification=fingerprint_verification,
    )
    definition = build_frozen_baseline_pack_v2_experiment_definition(
        repository_root=repository_root,
        dataset_identity=dataset_identity,
        code_sha=code_sha,
    )
    frozen_path = evidence_dir / "frozen_experiment_definition.json"
    frozen_path.write_text(json.dumps(definition, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verification_path = evidence_dir / "dataset_fingerprint_verification.json"
    verification_body = {
        **fingerprint_verification,
        "experiment_id": HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID,
        "hypothesis_id": HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID,
        "corpus_pin_path": pinned_corpus.relative_to(repository_root).as_posix(),
    }
    verification_path.write_text(json.dumps(verification_body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    freeze_receipt = {
        "artifact_kind": "historical_baseline_pack_v2_freeze_receipt_v1",
        "EXPERIMENT_DEFINITION_FROZEN": "YES",
        "execution_status": "NOT_EXECUTED",
        "performance_run": "NO",
        "experiment_id": HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID,
        "hypothesis_id": HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID,
        "experiment_definition_hash": definition["experiment_definition_hash"],
        "dataset_fingerprint": dataset_identity["dataset_fingerprint"],
        "research_code_sha": definition["research_code_sha"],
        "frozen_definition_path": frozen_path.relative_to(repository_root).as_posix(),
        "dataset_fingerprint_verification_path": verification_path.relative_to(repository_root).as_posix(),
        "canonical_evidence_dir": CANONICAL_BASELINE_PACK_V2_EVIDENCE_REL,
    }
    receipt_path = evidence_dir / "baseline_pack_v2_freeze_receipt.json"
    receipt_path.write_text(json.dumps(freeze_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return frozen_path, definition, freeze_receipt


def load_pinned_opend_build(repository_root: Path) -> HistoricalDevelopmentBuildResult:
    """Load pinned OpenD corpus for integrity checks (not execution)."""

    corpus_dir = canonical_baseline_pack_v2_evidence_dir(repository_root) / "corpus_pin"
    return load_historical_development_build_from_evidence_corpus(
        repository_root=repository_root,
        corpus_dir=corpus_dir,
    )


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


def _dev_validate_coupling_counts(
    predictions: list[dict[str, Any]],
    *,
    instrument_id: str,
) -> dict[str, Any]:
    dev_rows = [
        row
        for row in predictions
        if row.get("split") == HistoricalResearchSplitName.HISTORICAL_DEVELOPMENT_VALIDATE.value
    ]
    signals = sum(1 for row in dev_rows if int(row.get("predicted_direction", 0)) != 0)
    interpretations, _audit = build_signal_interpretations_from_predictions(
        dev_rows,
        instrument_id=instrument_id,
    )
    return {
        "directional_signals": signals,
        "trade_intents": len(interpretations),
    }


def amend_pre_execution_freeze_for_coupling_sha(
    *,
    repository_root: Path,
    coupling_code_sha: str,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    """Pre-execution freeze amendment: coupling SHA only (no parameter tuning)."""

    evidence_dir = canonical_baseline_pack_v2_evidence_dir(repository_root)
    corpus_pin = evidence_dir / "corpus_pin"
    fingerprint_verification = verify_pinned_opend_corpus_fingerprint(
        repository_root=repository_root,
        corpus_dir=corpus_pin,
    )
    if not fingerprint_verification.get("ok"):
        raise ValueError(str(fingerprint_verification.get("reason_code") or "DATASET_REPRODUCIBILITY_FAILURE"))

    frozen_path = evidence_dir / "frozen_experiment_definition.json"
    if not frozen_path.is_file():
        raise ValueError("FROZEN_DEFINITION_MISSING")
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    verify = verify_frozen_experiment_definition(frozen)
    if not verify.get("ok"):
        raise ValueError(str(verify.get("reason_code") or "EXPERIMENT_DEFINITION_HASH_MISMATCH"))

    prior_hash = str(frozen.get("experiment_definition_hash") or "")
    prior_sha = str(frozen.get("research_code_sha") or "")
    created_ns = int(frozen.get("created_timestamp_ns") or time.time_ns())
    amendment_body = {
        "artifact_kind": "historical_baseline_pack_v2_pre_execution_amendment_v1",
        "EXPERIMENT_DEFINITION_FROZEN": "YES",
        "amendment_kind": "R1_PREDICTION_COUPLED_SIMULATOR_CODE_SHA",
        "reason": (
            "Record post-merge main research_code_sha before first performance run; "
            "baselines, split, costs, sessions, and lookbacks unchanged."
        ),
        "prior_experiment_definition_hash": prior_hash,
        "prior_research_code_sha": prior_sha,
        "coupling_code_sha": coupling_code_sha,
        "dataset_fingerprint": OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT,
        "fingerprint_verification": fingerprint_verification,
        "amended_timestamp_ns": time.time_ns(),
    }
    amendment_path = evidence_dir / "pre_execution_freeze_amendment.json"
    amendment_path.write_text(json.dumps(amendment_body, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    frozen["pre_execution_freeze_amendment"] = {
        "amendment_kind": amendment_body["amendment_kind"],
        "prior_experiment_definition_hash": prior_hash,
        "prior_research_code_sha": prior_sha,
        "coupling_code_sha": coupling_code_sha,
        "amended_timestamp_ns": amendment_body["amended_timestamp_ns"],
        "amendment_receipt_path": amendment_path.relative_to(repository_root).as_posix(),
    }
    frozen["research_code_sha"] = coupling_code_sha
    frozen["execution_status"] = "DEFINITION_FROZEN_READY_FOR_EXECUTION"
    frozen["created_timestamp_ns"] = created_ns
    frozen["experiment_definition_hash"] = compute_experiment_definition_hash(frozen)
    frozen_path.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    freeze_receipt = {
        "artifact_kind": "historical_baseline_pack_v2_freeze_receipt_v1",
        "EXPERIMENT_DEFINITION_FROZEN": "YES",
        "execution_status": frozen["execution_status"],
        "performance_run": "NO",
        "experiment_id": HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID,
        "hypothesis_id": HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID,
        "experiment_definition_hash": frozen["experiment_definition_hash"],
        "prior_experiment_definition_hash": prior_hash,
        "dataset_fingerprint": OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT,
        "research_code_sha": coupling_code_sha,
        "pre_execution_amendment_path": amendment_path.relative_to(repository_root).as_posix(),
        "frozen_definition_path": frozen_path.relative_to(repository_root).as_posix(),
        "canonical_evidence_dir": CANONICAL_BASELINE_PACK_V2_EVIDENCE_REL,
    }
    receipt_path = evidence_dir / "baseline_pack_v2_freeze_receipt.json"
    receipt_path.write_text(json.dumps(freeze_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return frozen_path, frozen, amendment_body


def run_frozen_historical_baseline_pack_v2(
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

    corpus_pin = canonical_baseline_pack_v2_evidence_dir(repository_root) / "corpus_pin"
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

    run_params = frozen_definition.get("run_parameters") or default_baseline_pack_run_parameters()
    split_policy = ChronologicalSplitPolicy(
        train_fraction=float(run_params["split_policy"]["train_fraction"]),
        development_validate_fraction=float(run_params["split_policy"]["development_validate_fraction"]),
    )
    forward_horizon_bars = int(run_params.get("forward_horizon_bars", 1))
    simulator_version = str(run_params.get("simulator_version", "paper_bar_conservative_v1"))
    cost_slippage_bps = float(run_params.get("cost_slippage_bps", 5.0))

    out_root = artifact_root or (
        repository_root / "artifacts" / "historical-research-harness" / "baseline-pack-v2"
    )
    pack_dir = out_root / "pack-runs"
    pack_dir.mkdir(parents=True, exist_ok=True)

    instrument_id = str((build.manifest.get("universe") or ["canonical:EQUITY:XNAS:AAPL"])[0])
    baseline_results: list[dict[str, Any]] = []
    split_assignments_ref: list[dict[str, Any]] = []
    feature_lineage: list[dict[str, Any]] = []

    for spec in _BASELINE_STRATEGY_SPECS:
        strategy_id = str(spec["strategy_id"])
        config = HistoricalResearchRunConfig(
            experiment_id=HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID,
            hypothesis_id=HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID,
            forward_horizon_bars=forward_horizon_bars,
            split_policy=split_policy,
            strategy_id=strategy_id,
            strategy_version=str(spec.get("strategy_version", "1.0.0")),
            simulator_version=simulator_version,
            cost_slippage_bps=cost_slippage_bps,
            metadata={
                "evidence_label": HISTORICAL_BASELINE_PACK_V2,
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
        sim_block = harness_result.body.get("simulator") or {}
        if sim_block.get("result_kind") != SIMULATOR_RESEARCH_RESULT_KIND:
            return BaselinePackRunResult(
                ok=False,
                pack_run_id="",
                experiment_definition_hash=expected_hash,
                dataset_fingerprint=dataset_fp,
                artifact_dir=pack_dir,
                body={"failed_strategy_id": strategy_id, "simulator": sim_block},
                reason_code="SIMULATOR_RESULT_KIND_MISMATCH",
            )
        coupling = _dev_validate_coupling_counts(predictions, instrument_id=instrument_id)
        fills = int(dev_metrics.get("simulated_fills") or 0)
        turnover = int(dev_metrics.get("turnover") or 0)
        coupling["fills"] = fills
        coupling["turnover"] = turnover
        coupling["gross_pnl"] = dev_metrics.get("gross_pnl")
        coupling["net_pnl"] = dev_metrics.get("net_pnl")
        coupling["estimated_costs"] = dev_metrics.get("estimated_costs")
        if strategy_id == BASELINE_STRATEGY_NO_TRADE_V1:
            if not (
                coupling["directional_signals"] == 0
                and coupling["trade_intents"] == 0
                and fills == 0
                and turnover == 0
            ):
                return BaselinePackRunResult(
                    ok=False,
                    pack_run_id="",
                    experiment_definition_hash=expected_hash,
                    dataset_fingerprint=dataset_fp,
                    artifact_dir=pack_dir,
                    body={"failed_strategy_id": strategy_id, "coupling": coupling},
                    reason_code="NO_TRADE_BASELINE_INVARIANT_FAILED",
                )
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

    research_code_sha = resolve_runtime_git_sha(start=repository_root)
    pack_run_id = sha256_bytes(
        canonical_bytes(
            {
                "pack": HISTORICAL_BASELINE_PACK_V2,
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
    first_run_fingerprint: str | None = None
    second_run_fingerprint: str | None = None
    if deterministic_rerun and baseline_results:
        first_strategy = str(_BASELINE_STRATEGY_SPECS[0]["strategy_id"])
        first_run_fingerprint = str(baseline_results[0].get("run_fingerprint") or "")
        rerun_config = HistoricalResearchRunConfig(
            experiment_id=HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID,
            hypothesis_id=HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID,
            forward_horizon_bars=forward_horizon_bars,
            split_policy=split_policy,
            strategy_id=first_strategy,
            strategy_version="1.0.0",
            simulator_version=simulator_version,
            cost_slippage_bps=cost_slippage_bps,
            metadata={"evidence_label": HISTORICAL_BASELINE_PACK_V2, "baseline_index": 0},
        )
        rerun = run_historical_research_harness(
            repository_root=repository_root,
            build=build,
            config=rerun_config,
            artifact_root=out_root,
        )
        second_run_fingerprint = str(rerun.body.get("run_fingerprint") or "") if rerun.ok else None
        rerun_match = rerun.ok and rerun.run_id == baseline_results[0]["run_id"]

    pack_body: dict[str, Any] = {
        "artifact_kind": "historical_baseline_pack_run_v2",
        "schema_version": HISTORICAL_BASELINE_PACK_V2_DEFINITION_SCHEMA,
        "evidence_label": HISTORICAL_BASELINE_PACK_V2,
        "observation_language": BOUNDED_HISTORICAL_OBSERVATION,
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "pack_run_id": pack_run_id,
        "experiment_id": HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID,
        "hypothesis_id": HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID,
        "experiment_definition_hash": expected_hash,
        "frozen_definition_path": str(
            canonical_baseline_pack_v2_evidence_dir(repository_root) / "frozen_experiment_definition.json"
        ),
        "dataset_fingerprint": dataset_fp,
        "dataset_identity": frozen_definition.get("dataset"),
        "research_code_sha": research_code_sha,
        "frozen_research_code_sha": frozen_definition.get("research_code_sha"),
        "feature_version": HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION,
        "simulator_version": simulator_version,
        "prediction_coupled_simulator": True,
        "baseline_results": baseline_results,
        "contamination_manifest_path": None,
        "contamination_audit": contamination_report,
        "reproducibility": {
            "dataset_fingerprint": dataset_fp,
            "experiment_definition_hash": expected_hash,
            "first_run_fingerprint": first_run_fingerprint,
            "second_run_fingerprint": second_run_fingerprint,
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


def publish_baseline_pack_v2_evidence_receipt(
    *,
    repository_root: Path,
    frozen_definition: dict[str, Any],
    pack_result: BaselinePackRunResult,
) -> Path:
    evidence_dir = canonical_baseline_pack_v2_evidence_dir(repository_root)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    frozen_path = evidence_dir / "frozen_experiment_definition.json"

    pack_manifest = dict(pack_result.body)
    pack_manifest["frozen_definition_path"] = frozen_path.relative_to(repository_root).as_posix()
    pack_manifest["canonical_evidence_dir"] = CANONICAL_BASELINE_PACK_V2_EVIDENCE_REL
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
        "artifact_kind": "historical_baseline_pack_v2_evidence_receipt_v1",
        "evidence_label": HISTORICAL_BASELINE_PACK_V2,
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
    receipt_path = evidence_dir / "baseline_pack_v2_evidence_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_path


__all__ = [
    "CANONICAL_BASELINE_PACK_V2_EVIDENCE_REL",
    "HISTORICAL_BASELINE_PACK_V2",
    "HISTORICAL_BASELINE_PACK_V2_EXPERIMENT_ID",
    "HISTORICAL_BASELINE_PACK_V2_HYPOTHESIS_ID",
    "OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT",
    "OPEND_AAPL_VERIFIED_SESSION_DATES",
    "amend_pre_execution_freeze_for_coupling_sha",
    "build_frozen_baseline_pack_v2_experiment_definition",
    "build_opend_v2_dataset_identity",
    "canonical_baseline_pack_v2_evidence_dir",
    "compute_experiment_definition_hash",
    "freeze_baseline_pack_v2_definition_to_disk",
    "load_pinned_opend_build",
    "publish_baseline_pack_v2_evidence_receipt",
    "recompute_normalized_corpus_fingerprint",
    "run_frozen_historical_baseline_pack_v2",
    "verify_frozen_experiment_definition",
    "verify_pinned_opend_corpus_fingerprint",
]
