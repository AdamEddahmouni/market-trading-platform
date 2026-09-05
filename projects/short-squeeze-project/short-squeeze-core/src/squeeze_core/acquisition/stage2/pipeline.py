"""Orchestrate the Phase 3E Stage 2 pipeline end-to-end."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from squeeze_core.acquisition.phase3a_freeze.cli import FREEZE_SUBDIR, generate as generate_phase3a_freeze
from squeeze_core.acquisition.phase3a_freeze.serialization import serialize
from squeeze_core.serialization import canonical_json_bytes

from ..cohort_registry import (
    boundary_map,
    cohort_cases_as_symbol_case_pairs,
    resolve_cohort_cases,
)
from .constants import (
    DEFAULT_BATCH05_ROOT,
    DEFAULT_FREEZE_SUBDIR,
    LEAKAGE_DIR,
    OUTCOMES_DIR,
    PHASE3A_FREEZE_DIR,
    PILOT_COHORT,
    PIPELINE_SUMMARY_PATH,
    STAGE2_BUILD_ROOT,
    SYNTHETIC_BATCH05_ROOT,
)
from .leakage import audit_post_outcome_case, serialize_audit_summary
from .outcomes import build_outcome, outcome_manifest_id_for, write_outcome_artifacts
from .phase3b import build_phase3b_outputs
from .phase3c import build_phase3c_outputs


@dataclass
class Stage2PipelineConfig:
    repo_root: Path
    batch05_root: Path | None = None
    freeze_root: Path | None = None
    stage2_root: Path = STAGE2_BUILD_ROOT
    offline: bool = False
    skip_freeze: bool = False
    force: bool = False
    cohort_track: str = "frozen"
    symbols: tuple[tuple[str, str], ...] | None = None


@dataclass
class Stage2PipelineResult:
    steps: dict[str, object] = field(default_factory=dict)
    passed_leakage: tuple[tuple[str, str], ...] = ()
    failed_symbols: tuple[str, ...] = ()
    summary_path: Path | None = None


def _resolve_batch05_root(config: Stage2PipelineConfig) -> Path:
    if config.batch05_root is not None:
        return config.batch05_root
    live = config.repo_root / DEFAULT_BATCH05_ROOT
    if config.offline or not (live / "raw").is_dir():
        return config.repo_root / SYNTHETIC_BATCH05_ROOT
    return live


def _resolve_freeze_root(config: Stage2PipelineConfig, batch05_root: Path) -> Path:
    if config.freeze_root is not None:
        return config.freeze_root
    return batch05_root / FREEZE_SUBDIR


def _mirror_phase3a_freeze(
    *,
    symbols: tuple[tuple[str, str], ...],
    freeze_root: Path,
    stage2_root: Path,
    force: bool,
) -> dict[str, object]:
    mirrored = 0
    for symbol, case_id in symbols:
        out_dir = stage2_root / "phase3a-freeze" / symbol
        metadata_path = out_dir / "freeze_metadata.json"
        if not force and metadata_path.is_file():
            mirrored += 1
            continue
        request_src = freeze_root / "requests" / f"{case_id}.json"
        result_src = freeze_root / "results" / f"{case_id}.json"
        if not request_src.is_file() or not result_src.is_file():
            continue
        out_dir.mkdir(parents=True, exist_ok=True)
        request_bytes = request_src.read_bytes()
        result_bytes = result_src.read_bytes()
        (out_dir / "frozen_request.json").write_bytes(request_bytes)
        (out_dir / "frozen_result.json").write_bytes(result_bytes)
        metadata = {
            "symbol": symbol,
            "case_id": case_id,
            "mirrored_from": str(freeze_root),
            "freeze_timestamp_utc": datetime.now(UTC).isoformat(),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        mirrored += 1
    return {"mirrored_count": mirrored, "freeze_root": str(freeze_root)}


def _resolve_symbols(config: Stage2PipelineConfig) -> tuple[tuple[str, str], ...]:
    if config.symbols is not None:
        return config.symbols
    return cohort_cases_as_symbol_case_pairs(resolve_cohort_cases(config.cohort_track))


def _generate_outcomes(
    *,
    symbols: tuple[tuple[str, str], ...],
    batch05_root: Path,
    stage2_root: Path,
    live_intake: bool,
    force: bool,
    boundary_by_symbol: dict[str, datetime],
) -> dict[str, object]:
    built: list[str] = []
    skipped: list[str] = []
    failures: dict[str, str] = {}
    for symbol, case_id in symbols:
        manifest_path = stage2_root / "outcomes" / symbol / "outcome-manifest.json"
        if not force and manifest_path.is_file():
            skipped.append(symbol)
            continue
        try:
            result = build_outcome(
                symbol=symbol,
                case_id=case_id,
                batch05_root=batch05_root,
                live_intake=live_intake,
                research_case_id=case_id,
                boundary=boundary_by_symbol.get(symbol),
            )
            write_outcome_artifacts(result, stage2_root / "outcomes")
            built.append(symbol)
        except (FileNotFoundError, ValueError) as exc:
            failures[symbol] = str(exc)
    return {
        "built": built,
        "skipped": skipped,
        "failures": failures,
    }


def _run_leakage_audit(
    *,
    symbols: tuple[tuple[str, str], ...],
    stage2_root: Path,
    force: bool,
    boundary_by_symbol: dict[str, datetime],
) -> tuple[dict[str, object], tuple[tuple[str, str], ...]]:
    leakage_dir = stage2_root / "leakage-audit"
    summary_path = leakage_dir / "leakage-audit.json"
    if not force and summary_path.is_file():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        passed = tuple(
            (symbol, case_id)
            for symbol, case_id in symbols
            if any(
                audit["case_attempt_id"] == case_id and audit["passed"]
                for audit in summary.get("audits", [])
            )
        )
        return {"resumed": True, "passed_count": summary.get("passed_count", 0)}, passed

    leakage_dir.mkdir(parents=True, exist_ok=True)
    audits = []
    passed_cases: list[tuple[str, str]] = []
    for symbol, case_id in symbols:
        manifest_path = stage2_root / "outcomes" / symbol / "outcome-manifest.json"
        if not manifest_path.is_file():
            continue
        manifest_id = outcome_manifest_id_for(case_id)
        audit = audit_post_outcome_case(
            case_id=case_id,
            outcome_manifest_id=manifest_id,
            boundary=boundary_by_symbol.get(symbol),
        )
        audits.append(audit)
        audit_path = leakage_dir / f"{case_id}.json"
        audit_path.write_bytes(serialize(audit))
        if audit.passed:
            passed_cases.append((symbol, case_id))

    summary_path.write_bytes(serialize_audit_summary(tuple(audits)))
    return {
        "passed_count": sum(1 for item in audits if item.passed),
        "failed_count": sum(1 for item in audits if not item.passed),
        "total": len(audits),
    }, tuple(passed_cases)


def run_stage2_pipeline(config: Stage2PipelineConfig) -> Stage2PipelineResult:
    """Execute the full Stage 2 pipeline and write ``pipeline-summary.json``."""
    repo_root = config.repo_root.resolve()
    stage2_root = (repo_root / config.stage2_root).resolve()
    stage2_root.mkdir(parents=True, exist_ok=True)

    batch05_root = _resolve_batch05_root(config).resolve()
    freeze_root = _resolve_freeze_root(config, batch05_root).resolve()
    live_intake = batch05_root == (repo_root / DEFAULT_BATCH05_ROOT).resolve()

    cohort_cases = resolve_cohort_cases(config.cohort_track)
    symbols = _resolve_symbols(config)
    boundary_by_symbol = boundary_map(cohort_cases)

    result = Stage2PipelineResult()
    steps: dict[str, object] = {}

    if not config.skip_freeze:
        missing_freeze = any(
            not (freeze_root / "requests" / f"{case_id}.json").is_file()
            for _, case_id in symbols
        )
        if not freeze_root.is_dir() or config.force or missing_freeze:
            generate_phase3a_freeze(
                batch05_root,
                freeze_root,
                cohort_track=config.cohort_track,
            )
        steps["phase3a_freeze"] = {
            "freeze_root": str(freeze_root),
            "cohort_track": config.cohort_track,
        }

    steps["mirror_phase3a_freeze"] = _mirror_phase3a_freeze(
        symbols=symbols,
        freeze_root=freeze_root,
        stage2_root=stage2_root,
        force=config.force,
    )
    steps["outcomes"] = _generate_outcomes(
        symbols=symbols,
        batch05_root=batch05_root,
        stage2_root=stage2_root,
        live_intake=live_intake,
        force=config.force,
        boundary_by_symbol=boundary_by_symbol,
    )

    leakage_step, passed_cases = _run_leakage_audit(
        symbols=symbols,
        stage2_root=stage2_root,
        force=config.force,
        boundary_by_symbol=boundary_by_symbol,
    )
    steps["leakage_audit"] = leakage_step
    result.passed_leakage = passed_cases

    if passed_cases:
        steps["phase3b"] = {
            "case_count": build_phase3b_outputs(
                stage2_root=stage2_root,
                passed_cases=passed_cases,
                freeze_root=freeze_root,
                force=config.force,
            ).case_count,
        }
        steps["phase3c"] = {
            "report_count": build_phase3c_outputs(
                stage2_root=stage2_root,
                force=config.force,
            ).report_count,
        }
    else:
        steps["phase3b"] = {"skipped": "no leakage-passing cases"}
        steps["phase3c"] = {"skipped": "no leakage-passing cases"}

    outcome_failures = steps["outcomes"].get("failures", {})
    if isinstance(outcome_failures, dict):
        result.failed_symbols = tuple(sorted(outcome_failures))

    summary = {
        "schema_version": "1.0.0",
        "pipeline": "phase-3e-stage2",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "batch05_root": str(batch05_root),
        "freeze_root": str(freeze_root),
        "stage2_root": str(stage2_root),
        "live_intake": live_intake,
        "offline": config.offline,
        "cohort_track": config.cohort_track,
        "symbol_count": len(symbols),
        "leakage_passed_count": len(passed_cases),
        "steps": steps,
    }
    summary_path = stage2_root / "pipeline-summary.json"
    summary_path.write_bytes(canonical_json_bytes(summary))
    result.steps = steps
    result.summary_path = summary_path
    return result


__all__ = ["Stage2PipelineConfig", "Stage2PipelineResult", "run_stage2_pipeline"]
