"""Frozen Historical Cost Sensitivity v4 (IMP-POST-RTH-CLOSE-08 Lane E)."""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any, Mapping

from ...canonical import canonical_bytes, sha256_bytes
from ...market_data.historical_development.builder import HistoricalDevelopmentBuildResult
from ...paper.calibration.bar_ohlcv_prospective_proof import resolve_runtime_git_sha
from ...paper.calibration.dual_corpus import CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT
from ...paper.calibration.dual_corpus.contamination_auditor import audit_research_contamination_run
from .baseline_pack import (
    BaselinePackRunResult,
    build_baseline_pack_contamination_manifest,
    compute_experiment_definition_hash,
    verify_frozen_experiment_definition,
)
from .baseline_pack_v2 import OPEND_AAPL_VERIFIED_NORMALIZED_FINGERPRINT, verify_pinned_opend_corpus_fingerprint
from .baseline_pack_v3 import (
    BOUNDED_HISTORICAL_OBSERVATION,
    _execute_baseline_pack_once,
    canonical_baseline_pack_v3_evidence_dir,
    load_pinned_opend_build_v3,
)
from .fill_economics import ACCOUNTING_VERSION, COST_MODEL_VERSION
from .features import HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION
from .simulator import SIMULATOR_RESEARCH_RESULT_KIND
from .types import HistoricalResearchSplitName

HISTORICAL_COST_SENSITIVITY_V4 = "HISTORICAL_COST_SENSITIVITY_V4"
HISTORICAL_COST_SENSITIVITY_V4_EXPERIMENT_ID = "imp-simulator-cost-sensitivity-v4-lane-e"
HISTORICAL_COST_SENSITIVITY_V4_HYPOTHESIS_ID = "LANE-E-HYP-SIMULATOR-COST-SENSITIVITY-V4"
HISTORICAL_COST_SENSITIVITY_V4_DEFINITION_KIND = "historical_cost_sensitivity_experiment_definition_v4"
HISTORICAL_COST_SENSITIVITY_V4_DEFINITION_SCHEMA = "imp.historical-cost-sensitivity/4.0.0"
HISTORICAL_COST_SENSITIVITY_V4_INCREMENT_ID = "IMP-SIMULATOR-COST-SENSITIVITY-V4"

CANONICAL_COST_SENSITIVITY_V4_EVIDENCE_REL = (
    "evidence/historical-research/imp-simulator-cost-sensitivity-v4"
)
V3_PARENT_EXPERIMENT_HASH = (
    "81EFC1B1E2650010962F81F5B58B7E614E1AC1C2232E7862890CBB37BF5F3F61"
)
PRE_REGISTERED_METHODOLOGY_FILENAME = "pre_registered_methodology_v1.json"


def canonical_cost_sensitivity_v4_evidence_dir(repository_root: Path) -> Path:
    return repository_root / CANONICAL_COST_SENSITIVITY_V4_EVIDENCE_REL


def load_pre_registered_methodology(repository_root: Path) -> dict[str, Any]:
    path = canonical_cost_sensitivity_v4_evidence_dir(repository_root) / PRE_REGISTERED_METHODOLOGY_FILENAME
    if not path.is_file():
        raise ValueError("PRE_REGISTERED_METHODOLOGY_MISSING")
    body = json.loads(path.read_text(encoding="utf-8"))
    if not body.get("spec_ready"):
        raise ValueError("METHODOLOGY_NOT_SPEC_READY")
    return body


def _load_v3_frozen_definition(repository_root: Path) -> dict[str, Any]:
    frozen_path = canonical_baseline_pack_v3_evidence_dir(repository_root) / "frozen_experiment_definition.json"
    if not frozen_path.is_file():
        raise ValueError("V3_FROZEN_DEFINITION_MISSING")
    return json.loads(frozen_path.read_text(encoding="utf-8"))


def build_frozen_cost_sensitivity_v4_definition(
    *,
    repository_root: Path,
    code_sha: str | None = None,
) -> dict[str, Any]:
    """Materialize v4 frozen definition from Lane C pre-registration + immutable v3 parent."""

    methodology = load_pre_registered_methodology(repository_root)
    v3 = _load_v3_frozen_definition(repository_root)
    if str(methodology.get("parent_experiment_definition_hash") or "") != V3_PARENT_EXPERIMENT_HASH:
        raise ValueError("PARENT_EXPERIMENT_HASH_MISMATCH")
    if str(v3.get("experiment_definition_hash") or "") != V3_PARENT_EXPERIMENT_HASH:
        raise ValueError("V3_EMBEDDED_HASH_MISMATCH")

    grid = list(methodology["cost_slippage_bps_grid"])
    if len(grid) != int(methodology["cost_slippage_bps_grid_size_max"]):
        raise ValueError("COST_GRID_SIZE_MISMATCH")

    research_sha = code_sha or resolve_runtime_git_sha(start=repository_root)
    run_params = copy.deepcopy(v3.get("run_parameters") or {})
    run_params["cost_slippage_bps_grid"] = grid
    run_params["cost_slippage_bps_reference"] = float(methodology["v3_baseline_cost_slippage_bps"])

    frozen: dict[str, Any] = {
        "artifact_kind": HISTORICAL_COST_SENSITIVITY_V4_DEFINITION_KIND,
        "schema_version": HISTORICAL_COST_SENSITIVITY_V4_DEFINITION_SCHEMA,
        "evidence_label": HISTORICAL_COST_SENSITIVITY_V4,
        "increment_id": HISTORICAL_COST_SENSITIVITY_V4_INCREMENT_ID,
        "experiment_id": HISTORICAL_COST_SENSITIVITY_V4_EXPERIMENT_ID,
        "hypothesis_id": HISTORICAL_COST_SENSITIVITY_V4_HYPOTHESIS_ID,
        "accounting_version": ACCOUNTING_VERSION,
        "cost_model_version": COST_MODEL_VERSION,
        "feature_version": HISTORICAL_RESEARCH_FEATURE_SCHEMA_VERSION,
        "baseline_strategies": copy.deepcopy(v3.get("baseline_strategies") or []),
        "feature_definitions": copy.deepcopy(v3.get("feature_definitions") or []),
        "target_definition": copy.deepcopy(v3.get("target_definition") or {}),
        "dataset": copy.deepcopy(v3.get("dataset") or {}),
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "run_parameters": run_params,
        "pre_registered_methodology_path": (
            canonical_cost_sensitivity_v4_evidence_dir(repository_root).relative_to(repository_root).as_posix()
            + f"/{PRE_REGISTERED_METHODOLOGY_FILENAME}"
        ),
        "parent_experiment_id": str(methodology.get("parent_experiment_id") or ""),
        "parent_experiment_definition_hash": V3_PARENT_EXPERIMENT_HASH,
        "source_finding_ids": list(methodology.get("source_finding_ids") or []),
        "primary_metric": methodology.get("primary_metric", "net_pnl"),
        "secondary_metrics": list(methodology.get("secondary_metrics") or []),
        "invariants": list(methodology.get("invariants") or []),
        "research_code_sha": research_sha,
        "governance": {
            "authority": "HISTORICAL_DEVELOPMENT",
            "observation_class": BOUNDED_HISTORICAL_OBSERVATION,
            "ftep_effect": "NONE",
            "item7_effect": "NONE",
            "item9_effect": "NONE",
            "live_authority": "NONE",
            "parent_experiment_immutable": "imp-integrate-experiment-05-r3-opend-fill-economics-v3",
            "promotional_language_forbidden": True,
        },
        "execution_status": "DEFINITION_FROZEN_READY_FOR_EXECUTION",
        "created_timestamp_ns": time.time_ns(),
    }
    frozen["experiment_definition_hash"] = compute_experiment_definition_hash(frozen)
    return frozen


def promote_cost_sensitivity_v4_freeze_to_disk(
    *,
    repository_root: Path,
    code_sha: str | None = None,
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    evidence_dir = canonical_cost_sensitivity_v4_evidence_dir(repository_root)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    frozen = build_frozen_cost_sensitivity_v4_definition(repository_root=repository_root, code_sha=code_sha)
    frozen_path = evidence_dir / "frozen_experiment_definition.json"
    frozen_path.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    corpus_pin = canonical_baseline_pack_v3_evidence_dir(repository_root) / "corpus_pin"
    fingerprint_verification = verify_pinned_opend_corpus_fingerprint(
        repository_root=repository_root,
        corpus_dir=corpus_pin,
    )
    verification_path = evidence_dir / "dataset_fingerprint_verification.json"
    verification_path.write_text(
        json.dumps(
            {
                **fingerprint_verification,
                "experiment_id": HISTORICAL_COST_SENSITIVITY_V4_EXPERIMENT_ID,
                "hypothesis_id": HISTORICAL_COST_SENSITIVITY_V4_HYPOTHESIS_ID,
                "corpus_pin_path": corpus_pin.relative_to(repository_root).as_posix(),
                "verified_at_promotion": True,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    freeze_receipt = {
        "artifact_kind": "historical_cost_sensitivity_v4_freeze_receipt_v1",
        "EXPERIMENT_DEFINITION_FROZEN": "YES",
        "performance_run": "NO",
        "experiment_id": HISTORICAL_COST_SENSITIVITY_V4_EXPERIMENT_ID,
        "hypothesis_id": HISTORICAL_COST_SENSITIVITY_V4_HYPOTHESIS_ID,
        "experiment_definition_hash": frozen["experiment_definition_hash"],
        "parent_experiment_definition_hash": V3_PARENT_EXPERIMENT_HASH,
        "dataset_fingerprint": (frozen.get("dataset") or {}).get("dataset_fingerprint"),
        "cost_slippage_bps_grid": frozen["run_parameters"]["cost_slippage_bps_grid"],
        "frozen_definition_path": frozen_path.relative_to(repository_root).as_posix(),
        "pre_registered_methodology_path": frozen["pre_registered_methodology_path"],
        "promoted_timestamp_ns": time.time_ns(),
    }
    receipt_path = evidence_dir / "cost_sensitivity_v4_freeze_receipt.json"
    receipt_path.write_text(json.dumps(freeze_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return frozen_path, frozen, freeze_receipt


def _scenario_definition(
    frozen_definition: Mapping[str, Any],
    *,
    cost_slippage_bps: float,
) -> dict[str, Any]:
    scenario = copy.deepcopy(dict(frozen_definition))
    run_params = dict(scenario.get("run_parameters") or {})
    run_params["cost_slippage_bps"] = float(cost_slippage_bps)
    scenario["run_parameters"] = run_params
    return scenario


def _validate_split_row(row: Mapping[str, Any], *, baseline_index: int, bps: float) -> dict[str, Any]:
    dev = dict((row.get("metrics_by_split") or {}).get(HistoricalResearchSplitName.HISTORICAL_DEVELOPMENT_VALIDATE.value) or {})
    coupling = dict(row.get("coupling_observation") or {})
    return {
        "baseline_index": baseline_index,
        "strategy_id": row.get("strategy_id"),
        "cost_slippage_bps": bps,
        "simulated_fills": dev.get("simulated_fills"),
        "traded_notional": dev.get("traded_notional"),
        "gross_pnl": dev.get("gross_pnl"),
        "transaction_costs": dev.get("transaction_costs"),
        "estimated_costs": dev.get("estimated_costs"),
        "net_pnl": dev.get("net_pnl"),
        "fills_coupling": coupling.get("fills"),
        "gross_pnl_coupling": coupling.get("gross_pnl"),
        "net_pnl_coupling": coupling.get("net_pnl"),
    }


def _assert_bps_invariants(
    *,
    reference_rows: list[dict[str, Any]],
    scenario_rows: list[dict[str, Any]],
    cost_slippage_bps: float,
) -> list[str]:
    violations: list[str] = []
    if cost_slippage_bps == 0.0:
        return violations
    ref_by_index = {int(row["baseline_index"]): row for row in reference_rows}
    for row in scenario_rows:
        idx = int(row["baseline_index"])
        ref = ref_by_index.get(idx)
        if ref is None:
            violations.append(f"missing_reference_baseline_{idx}")
            continue
        if row.get("simulated_fills") != ref.get("simulated_fills"):
            violations.append(f"fills_changed_baseline_{idx}")
        if row.get("gross_pnl") != ref.get("gross_pnl"):
            violations.append(f"gross_pnl_changed_baseline_{idx}")
        if row.get("fills_coupling") != ref.get("fills_coupling"):
            violations.append(f"coupling_fills_changed_baseline_{idx}")
        if row.get("gross_pnl_coupling") != ref.get("gross_pnl_coupling"):
            violations.append(f"coupling_gross_pnl_changed_baseline_{idx}")
    return violations


def run_frozen_cost_sensitivity_v4(
    *,
    repository_root: Path,
    build: HistoricalDevelopmentBuildResult,
    frozen_definition: dict[str, Any],
    artifact_root: Path | None = None,
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
            dataset_fingerprint=dataset_fp,
            artifact_dir=Path(),
            body={"fingerprint_verification": fingerprint_verification},
            reason_code=str(fingerprint_verification.get("reason_code") or "DATASET_REPRODUCIBILITY_FAILURE"),
        )

    if not build.ok:
        return BaselinePackRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            dataset_fingerprint=dataset_fp,
            artifact_dir=Path(),
            body={},
            reason_code=build.reason_code or "BUILD_NOT_OK",
        )

    grid = list((frozen_definition.get("run_parameters") or {}).get("cost_slippage_bps_grid") or [])
    if not grid:
        return BaselinePackRunResult(
            ok=False,
            pack_run_id="",
            experiment_definition_hash=expected_hash,
            dataset_fingerprint=dataset_fp,
            artifact_dir=Path(),
            body={},
            reason_code="COST_GRID_EMPTY",
        )

    out_root = artifact_root or (
        repository_root / "artifacts" / "historical-research-harness" / "cost-sensitivity-v4"
    )
    pack_dir = out_root / "pack-runs"
    pack_dir.mkdir(parents=True, exist_ok=True)

    scenario_results: list[dict[str, Any]] = []
    reference_component_rows: list[dict[str, Any]] | None = None
    invariant_violations: list[str] = []
    split_assignments_ref: list[dict[str, Any]] = []
    feature_lineage: list[dict[str, Any]] = []

    for bps in grid:
        scenario_def = _scenario_definition(frozen_definition, cost_slippage_bps=float(bps))
        try:
            baseline_results, split_assignments_ref, feature_lineage = _execute_baseline_pack_once(
                repository_root=repository_root,
                build=build,
                frozen_definition=scenario_def,
                expected_hash=expected_hash,
                dataset_fp=dataset_fp,
                artifact_root=out_root / f"bps-{bps}",
            )
        except RuntimeError as exc:
            return BaselinePackRunResult(
                ok=False,
                pack_run_id="",
                experiment_definition_hash=expected_hash,
                dataset_fingerprint=dataset_fp,
                artifact_dir=pack_dir,
                body={"failed_cost_slippage_bps": bps},
                reason_code=str(exc),
            )

        component_rows = [
            _validate_split_row(row, baseline_index=int(row["baseline_index"]), bps=float(bps))
            for row in baseline_results
        ]
        if reference_component_rows is None:
            reference_component_rows = component_rows
        else:
            invariant_violations.extend(
                _assert_bps_invariants(
                    reference_rows=reference_component_rows,
                    scenario_rows=component_rows,
                    cost_slippage_bps=float(bps),
                )
            )

        scenario_results.append(
            {
                "cost_slippage_bps": float(bps),
                "baseline_results": baseline_results,
                "component_metrics": component_rows,
            }
        )

    research_code_sha = resolve_runtime_git_sha(start=repository_root)
    pack_run_id = sha256_bytes(
        canonical_bytes(
            {
                "pack": HISTORICAL_COST_SENSITIVITY_V4,
                "experiment_definition_hash": expected_hash,
                "dataset_fingerprint": dataset_fp,
                "research_code_sha": research_code_sha,
                "scenario_bps": grid,
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
    if contamination_report.get("CONTAMINATION_STATUS") != "PASS":
        invariant_violations.append("contamination_audit_not_pass")

    pack_body: dict[str, Any] = {
        "artifact_kind": "historical_cost_sensitivity_run_v4",
        "schema_version": HISTORICAL_COST_SENSITIVITY_V4_DEFINITION_SCHEMA,
        "evidence_label": HISTORICAL_COST_SENSITIVITY_V4,
        "observation_language": BOUNDED_HISTORICAL_OBSERVATION,
        "result_kind": SIMULATOR_RESEARCH_RESULT_KIND,
        "corpus_evidence_authority": CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
        "pack_run_id": pack_run_id,
        "experiment_id": HISTORICAL_COST_SENSITIVITY_V4_EXPERIMENT_ID,
        "hypothesis_id": HISTORICAL_COST_SENSITIVITY_V4_HYPOTHESIS_ID,
        "experiment_definition_hash": expected_hash,
        "parent_experiment_definition_hash": V3_PARENT_EXPERIMENT_HASH,
        "dataset_fingerprint": dataset_fp,
        "research_code_sha": research_code_sha,
        "cost_slippage_bps_grid": grid,
        "scenario_results": scenario_results,
        "component_sensitivity_table": [
            row for scenario in scenario_results for row in scenario["component_metrics"]
        ],
        "invariant_violations": invariant_violations,
        "contamination_audit": contamination_report,
        "created_timestamp_ns": time.time_ns(),
    }

    run_artifact_dir = pack_dir / pack_run_id
    run_artifact_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = run_artifact_dir / "cost_sensitivity_run_manifest.json"
    manifest_path.write_text(json.dumps(pack_body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    contamination_path = run_artifact_dir / "contamination_manifest.json"
    contamination_path.write_text(
        json.dumps(contamination_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if invariant_violations:
        return BaselinePackRunResult(
            ok=False,
            pack_run_id=pack_run_id,
            experiment_definition_hash=expected_hash,
            dataset_fingerprint=dataset_fp,
            artifact_dir=run_artifact_dir,
            body=pack_body,
            reason_code="COST_SENSITIVITY_INVARIANT_VIOLATION",
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


def publish_cost_sensitivity_v4_evidence_receipt(
    *,
    repository_root: Path,
    frozen_definition: dict[str, Any],
    pack_result: BaselinePackRunResult,
) -> Path:
    evidence_dir = canonical_cost_sensitivity_v4_evidence_dir(repository_root)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = evidence_dir / "cost_sensitivity_run_manifest.json"
    pack_manifest = dict(pack_result.body)
    pack_manifest["frozen_definition_path"] = (
        evidence_dir / "frozen_experiment_definition.json"
    ).relative_to(repository_root).as_posix()
    manifest_path.write_text(json.dumps(pack_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    receipt = {
        "artifact_kind": "historical_cost_sensitivity_v4_evidence_receipt_v1",
        "evidence_label": HISTORICAL_COST_SENSITIVITY_V4,
        "observation_language": BOUNDED_HISTORICAL_OBSERVATION,
        "EXPERIMENT_DEFINITION_FROZEN": "YES",
        "performance_run": "YES" if pack_result.ok else "NO",
        "execution_status": "EXECUTED_BOUNDED_HISTORICAL_OBSERVATION" if pack_result.ok else "EXECUTION_FAILED",
        "experiment_definition_hash": pack_result.experiment_definition_hash,
        "parent_experiment_definition_hash": V3_PARENT_EXPERIMENT_HASH,
        "dataset_fingerprint": pack_result.dataset_fingerprint,
        "pack_run_id": pack_result.pack_run_id,
        "cost_sensitivity_run_manifest_path": manifest_path.relative_to(repository_root).as_posix(),
        "contamination_status": (pack_result.body.get("contamination_audit") or {}).get("CONTAMINATION_STATUS"),
        "invariant_violations": pack_result.body.get("invariant_violations"),
    }
    receipt_path = evidence_dir / "cost_sensitivity_v4_evidence_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt_path


__all__ = [
    "CANONICAL_COST_SENSITIVITY_V4_EVIDENCE_REL",
    "HISTORICAL_COST_SENSITIVITY_V4",
    "HISTORICAL_COST_SENSITIVITY_V4_EXPERIMENT_ID",
    "HISTORICAL_COST_SENSITIVITY_V4_HYPOTHESIS_ID",
    "build_frozen_cost_sensitivity_v4_definition",
    "canonical_cost_sensitivity_v4_evidence_dir",
    "load_pre_registered_methodology",
    "promote_cost_sensitivity_v4_freeze_to_disk",
    "publish_cost_sensitivity_v4_evidence_receipt",
    "run_frozen_cost_sensitivity_v4",
]
