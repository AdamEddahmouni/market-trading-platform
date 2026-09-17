"""Item 7 Lane D — governed persistence load + collection status assembly."""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from ..paper_forward_bridge.session_policy import is_within_us_equity_rth
from ..persistence.repository import IntelligenceRepository
from .corpus_collector import (
    LABEL_SOURCE_FIXTURE,
    CorpusCollectionReport,
    PathATrainingCandidateRow,
    floor_counters,
    run_corpus_collection_pipeline,
)
from .corpus_join_diagnostics import CorpusJoinDiagnostics, diagnose_corpus_join_edges
from .corpus_persistence import (
    GovernedPersistenceLoadOptions,
    GovernedPersistenceLoadReport,
    discover_governed_persistence_paths,
    load_governed_intelligence_repository,
    resolve_persistence_root,
)

STATUS_REAL_CORPUS_SOFTWARE_READY = "ITEM7_REAL_CORPUS_COLLECTION_SOFTWARE_READY"
BLOCKER_RTH_OR_FUTURE_OUTCOMES_REQUIRED = "RTH_OR_FUTURE_OUTCOMES_REQUIRED"
ACCEPTANCE_GOVERNED_CORPUS = "GOVERNED_PATH_A_TRAINING_CORPUS_READY"


def _now_ns(explicit: int | None) -> int:
    return explicit if explicit is not None else time.time_ns()


def assess_rth_open(now_ns: int) -> bool:
    return is_within_us_equity_rth(now_ns)


def derive_acceptance_label(
    *,
    pit_valid_governed_rows: int,
    governed_training_manifest_status: str,
    specialist_floor_met: bool,
    calibration_floor_met: bool,
) -> tuple[str, tuple[str, ...]]:
    blockers: list[str] = []
    if pit_valid_governed_rows <= 0:
        blockers.append("NO_GOVERNED_PATH_A_TRAINING_CORPUS")
        blockers.append(BLOCKER_RTH_OR_FUTURE_OUTCOMES_REQUIRED)
        return STATUS_REAL_CORPUS_SOFTWARE_READY, tuple(dict.fromkeys(blockers))
    if specialist_floor_met and calibration_floor_met:
        if governed_training_manifest_status == "GOVERNED_MANIFEST_FLOORS_MET_PENDING_ATTESTATION":
            return ACCEPTANCE_GOVERNED_CORPUS, ()
        blockers.append("GOVERNED_MANIFEST_ATTESTATION_REQUIRED")
    else:
        blockers.append("GOVERNED_ROWS_INSUFFICIENT_FOR_FLOORS")
    return STATUS_REAL_CORPUS_SOFTWARE_READY, tuple(blockers)


def enrich_collection_report(
    report: CorpusCollectionReport,
    *,
    acceptance_label: str,
    blockers: tuple[str, ...],
    rth_open: bool | None,
    persistence_load: GovernedPersistenceLoadReport | None,
    join_diagnostics: CorpusJoinDiagnostics | None,
) -> CorpusCollectionReport:
    extra_notes = list(report.notes)
    if blockers:
        extra_notes.append(f"Blockers: {', '.join(blockers)}.")
    if rth_open is False:
        extra_notes.append("US equity RTH closed; lawful real collection requires RTH observations and future settlements.")
    return replace(
        report,
        status=acceptance_label if acceptance_label else report.status,
        notes=tuple(extra_notes),
        acceptance_label=acceptance_label,
        market_rth_open=rth_open,
        blockers=blockers,
        persistence_load=persistence_load.to_dict() if persistence_load else None,
        join_diagnostics=join_diagnostics.to_dict() if join_diagnostics else None,
    )


def run_governed_corpus_collection_status(
    *,
    training_cutoff_ns: int,
    repo_root: Path | None = None,
    persistence_root: Path | None = None,
    intelligence_jsonl: Iterable[Path] = (),
    forecast_dir: Iterable[Path] = (),
    use_mongo_if_configured: bool = False,
    include_fixture_proof: bool = False,
    now_ns: int | None = None,
) -> tuple[CorpusCollectionReport, tuple[PathATrainingCandidateRow, ...], IntelligenceRepository, GovernedPersistenceLoadReport]:
    """Load governed persistence (read-only), diagnose joins, and run collection pipeline."""

    root = persistence_root or resolve_persistence_root()
    jsonl_paths = tuple(intelligence_jsonl)
    forecast_dirs = tuple(forecast_dir)
    if root is not None and not jsonl_paths and not forecast_dirs:
        discovered = discover_governed_persistence_paths(root)
        jsonl_paths = discovered.intelligence_jsonl_paths
        forecast_dirs = discovered.forecast_dirs
    options = GovernedPersistenceLoadOptions(
        persistence_root=root,
        intelligence_jsonl_paths=jsonl_paths,
        forecast_dirs=forecast_dirs,
        use_mongo_if_configured=use_mongo_if_configured,
    )
    repository, load_report = load_governed_intelligence_repository(options)
    join_diag = diagnose_corpus_join_edges(repository, training_cutoff_ns=training_cutoff_ns)
    report, rows = run_corpus_collection_pipeline(
        repository=repository,
        repo_root=repo_root,
        persistence_root=root,
        training_cutoff_ns=training_cutoff_ns,
        include_fixture_proof=include_fixture_proof,
    )
    governed_pit = [row for row in rows if row.label_source != LABEL_SOURCE_FIXTURE and row.pit_passed]
    floors = floor_counters(governed_pit, governed_only=True)
    acceptance, blockers = derive_acceptance_label(
        pit_valid_governed_rows=report.pit_valid_governed_rows,
        governed_training_manifest_status=report.governed_training_manifest_status,
        specialist_floor_met=floors.specialist_floor_met,
        calibration_floor_met=floors.calibration_floor_met,
    )
    rth_open = assess_rth_open(_now_ns(now_ns))
    enriched = enrich_collection_report(
        report,
        acceptance_label=acceptance,
        blockers=blockers,
        rth_open=rth_open,
        persistence_load=load_report,
        join_diagnostics=join_diag,
    )
    return enriched, rows, repository, load_report


def operator_collect_gate(
    *,
    require_rth: bool,
    now_ns: int | None = None,
) -> tuple[bool, str | None]:
    """When ``require_rth`` is set, refuse operator collection outside US equity RTH."""

    if not require_rth:
        return True, None
    if assess_rth_open(_now_ns(now_ns)):
        return True, None
    return False, BLOCKER_RTH_OR_FUTURE_OUTCOMES_REQUIRED


__all__ = [
    "ACCEPTANCE_GOVERNED_CORPUS",
    "BLOCKER_RTH_OR_FUTURE_OUTCOMES_REQUIRED",
    "STATUS_REAL_CORPUS_SOFTWARE_READY",
    "assess_rth_open",
    "derive_acceptance_label",
    "enrich_collection_report",
    "operator_collect_gate",
    "run_governed_corpus_collection_status",
]
