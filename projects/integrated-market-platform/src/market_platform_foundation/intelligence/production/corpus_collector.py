"""Item 7 Lane G — lawful Path A training corpus collection and export.

Collects **candidate** rows with full provenance. Exporting candidates does not
mint a governed production corpus, PRODUCTION artifacts, or empirical proof.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable, Mapping

from ...canonical import canonical_bytes, sha256_bytes
from ..baselines.features import FeatureVectorBuilder
from ..contracts.common import (
    ContractKind,
    ContractReference,
    Direction,
    IntelligenceScope,
    OutcomeResolutionStatus,
    QualityState,
    QualitySummary,
)
from ..contracts.forecast import ForecastV1
from ..contracts.outcome import OutcomeV1, outcome_v1_from_dict
from ..contracts.signal import SignalV1
from ..contracts.snapshot import SnapshotV1
from ..evaluation.types import forecast_role
from ..fusion.calibration_data import MINIMUM_CALIBRATION_SAMPLES, MINIMUM_CLASS_COUNT
from ..fusion.types import CONTROL_FORECAST_STAGE, ForecastContributorRole
from ..outcomes.opend_capture_ledger import iter_jsonl_envelopes
from ..persistence.repository import IntelligenceRepository
from .identity import (
    MINIMUM_SPECIALIST_CLASS_COUNT,
    MINIMUM_SPECIALIST_SAMPLES,
    PATH_A_PRODUCTION_FEATURE_SCHEMA,
    path_a_horizon,
    matches_path_a_identity,
)
from .readiness import TRAINING_MANIFEST_KIND
from .training_build import load_governed_training_manifest

CORPUS_COLLECTOR_VERSION = "1.0.0"

STATUS_PIPELINE_READY = "ITEM7_CORPUS_COLLECTION_PIPELINE_READY"
STATUS_PIPELINE_BLOCKED = "ITEM7_CORPUS_COLLECTION_PIPELINE_BLOCKED"

CANDIDATE_CORPUS_KIND = "path_a_training_corpus_candidate_v1"
PIT_VALIDATED_CORPUS_KIND = "path_a_training_corpus_pit_validated_v1"
MANIFEST_CANDIDATE_KIND = "path_a_production_training_manifest_candidate_v1"

LABEL_SOURCE_OUTCOME_V1 = "OUTCOME_V1_SETTLED"
LABEL_SOURCE_FIXTURE = "FIXTURE_ONLY"

FORBIDDEN_LABEL_SOURCES = frozenset({"manual", "operator_invented", "quote_synthetic"})

DEFAULT_JSONL_SEARCH_GLOBS = (
    "artifacts/**/*.jsonl",
    ".local/**/*.jsonl",
)


class CorpusLayer(StrEnum):
    CANDIDATE_CORPUS = "CANDIDATE_CORPUS"
    PIT_VALIDATED_CORPUS = "PIT_VALIDATED_CORPUS"
    GOVERNED_TRAINING_MANIFEST = "GOVERNED_TRAINING_MANIFEST"
    PRODUCTION_ARTIFACT = "PRODUCTION_ARTIFACT"


@dataclass(frozen=True, slots=True)
class PathATrainingCandidateRow:
    row_id: str
    snapshot_id: str
    decision_time_ns: int
    horizon_duration_ns: int
    label: int
    label_source: str
    label_available_time_ns: int
    momentum: float
    net_signed_share: float
    feature_lineage: tuple[dict[str, str], ...]
    source_event_ids: tuple[str, ...]
    forecast_id: str | None
    outcome_id: str | None
    provider_id: str | None
    dataset_id: str | None
    dataset_version: str | None
    dataset_content_hash: str | None
    pit_passed: bool
    pit_reasons: tuple[str, ...]
    corpus_layer: CorpusLayer
    collection_mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_id": self.row_id,
            "snapshot_id": self.snapshot_id,
            "decision_time_ns": self.decision_time_ns,
            "horizon_duration_ns": self.horizon_duration_ns,
            "label": self.label,
            "label_source": self.label_source,
            "label_available_time_ns": self.label_available_time_ns,
            "momentum": self.momentum,
            "net_signed_share": self.net_signed_share,
            "feature_lineage": [dict(item) for item in self.feature_lineage],
            "source_event_ids": list(self.source_event_ids),
            "forecast_id": self.forecast_id,
            "outcome_id": self.outcome_id,
            "provider_id": self.provider_id,
            "dataset_id": self.dataset_id,
            "dataset_version": self.dataset_version,
            "dataset_content_hash": self.dataset_content_hash,
            "pit_passed": self.pit_passed,
            "pit_reasons": list(self.pit_reasons),
            "corpus_layer": self.corpus_layer.value,
            "collection_mode": self.collection_mode,
        }


@dataclass(frozen=True, slots=True)
class CorpusFloorCounters:
    total_rows: int = 0
    class_0: int = 0
    class_1: int = 0
    specialist_floor_samples: int = MINIMUM_SPECIALIST_SAMPLES
    specialist_floor_per_class: int = MINIMUM_SPECIALIST_CLASS_COUNT
    calibration_floor_samples: int = MINIMUM_CALIBRATION_SAMPLES
    calibration_floor_per_class: int = MINIMUM_CLASS_COUNT

    @property
    def specialist_floor_met(self) -> bool:
        if self.total_rows < self.specialist_floor_samples:
            return False
        return (
            self.class_0 >= self.specialist_floor_per_class
            and self.class_1 >= self.specialist_floor_per_class
        )

    @property
    def calibration_floor_met(self) -> bool:
        if self.total_rows < self.calibration_floor_samples:
            return False
        return (
            self.class_0 >= self.calibration_floor_per_class
            and self.class_1 >= self.calibration_floor_per_class
        )


@dataclass(frozen=True, slots=True)
class JsonlOutcomeScanSummary:
    paths_scanned: int = 0
    settled_outcome_envelopes: int = 0
    parse_errors: int = 0


@dataclass(frozen=True, slots=True)
class CorpusCollectionReport:
    status: str
    pipeline_version: str = CORPUS_COLLECTOR_VERSION
    governed_candidate_rows: int = 0
    pit_valid_governed_rows: int = 0
    fixture_only_rows: int = 0
    class_0_governed: int = 0
    class_1_governed: int = 0
    governed_training_manifest_status: str = "NO_GOVERNED_PATH_A_TRAINING_CORPUS"
    production_artifact_status: str = "PRODUCTION_FORECAST_BLOCKED_NO_GOVERNED_PATH_A_TRAINING_CORPUS"
    corpus_layers: dict[str, str] = field(default_factory=dict)
    jsonl_scan: JsonlOutcomeScanSummary | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "artifact_kind": "item7_path_a_corpus_collection_report_v1",
            "status": self.status,
            "pipeline_version": self.pipeline_version,
            "governed_candidate_rows": self.governed_candidate_rows,
            "pit_valid_governed_rows": self.pit_valid_governed_rows,
            "fixture_only_rows": self.fixture_only_rows,
            "class_counts_governed": {"0": self.class_0_governed, "1": self.class_1_governed},
            "governed_training_manifest_status": self.governed_training_manifest_status,
            "production_artifact_status": self.production_artifact_status,
            "corpus_layers": dict(self.corpus_layers),
            "notes": list(self.notes),
        }
        if self.jsonl_scan is not None:
            body["jsonl_scan"] = {
                "paths_scanned": self.jsonl_scan.paths_scanned,
                "settled_outcome_envelopes": self.jsonl_scan.settled_outcome_envelopes,
                "parse_errors": self.jsonl_scan.parse_errors,
            }
        return body


def label_from_settled_outcome(outcome: OutcomeV1) -> tuple[int | None, str | None]:
    if outcome.resolution_status != OutcomeResolutionStatus.SETTLED:
        return None, "OUTCOME_NOT_SETTLED"
    direction = outcome.realized_direction
    if direction == Direction.LONG:
        return 1, None
    if direction == Direction.SHORT:
        return 0, None
    return None, "OUTCOME_DIRECTION_UNLABELABLE"


def _forecast_excluded_from_production_corpus(forecast: ForecastV1) -> tuple[str, ...]:
    reasons: list[str] = []
    role = forecast_role(forecast)
    if role == ForecastContributorRole.CONTROL.value:
        reasons.append("CONTROL_ROLE_REJECTED")
    elif role == ForecastContributorRole.RESEARCH.value:
        reasons.append("RESEARCH_ROLE_REJECTED")
    stage = str(forecast.metadata.get("forecast_stage") or "")
    if stage == CONTROL_FORECAST_STAGE:
        reasons.append("CONTROL_STAGE_REJECTED")
    identity = matches_path_a_identity(target=forecast.target, horizon=forecast.horizon)
    reasons.extend(identity)
    return tuple(dict.fromkeys(reasons))


def _iter_store_records(repository: IntelligenceRepository, bucket: str, model: type) -> tuple[Any, ...]:
    stores = getattr(repository, "_stores", None)
    if not isinstance(stores, dict):
        return ()
    raw_bucket = stores.get(bucket)
    if not isinstance(raw_bucket, dict):
        return ()
    decode = getattr(repository, "_decode", None)
    if decode is None:
        return ()
    rows: list[Any] = []
    for body in raw_bucket.values():
        decoded = decode(model, body)
        if decoded is not None:
            rows.append(decoded)
    return tuple(rows)


def _signals_for_snapshot(repository: IntelligenceRepository, snapshot_id: str) -> tuple[SignalV1, ...]:
    signals = _iter_store_records(repository, "signals", SignalV1)
    matched: list[SignalV1] = []
    for signal in signals:
        ref = signal.source_snapshot_ref
        if ref is None or ref.id != snapshot_id:
            continue
        matched.append(signal)
    return tuple(sorted(matched, key=lambda row: str(row.signal_id)))


def _feature_values(
    snapshot: SnapshotV1,
    signals: tuple[SignalV1, ...],
) -> tuple[float, float, tuple[dict[str, str], ...]] | None:
    builder = FeatureVectorBuilder(PATH_A_PRODUCTION_FEATURE_SCHEMA)
    vector, diagnostics = builder.extract(snapshot, signals, allow_degraded=False)
    if vector is None or diagnostics:
        return None
    momentum = None
    nss = None
    lineage: list[dict[str, str]] = []
    for signal in signals:
        calc = signal.calculation_lineage or {}
        lineage.append(
            {
                "signal_type": str(signal.signal_type),
                "calculator_id": str(calc.get("calculator_id") or ""),
                "calculator_version": str(calc.get("calculator_version") or ""),
            }
        )
        if signal.signal_type == "momentum_simple":
            momentum = float(signal.value)
        elif signal.signal_type == "net_signed_share":
            nss = float(signal.value)
    if momentum is None or nss is None:
        return None
    return momentum, nss, tuple(lineage)


def pit_validate_candidate(
    *,
    snapshot: SnapshotV1,
    signals: tuple[SignalV1, ...],
    label: int,
    label_source: str,
    label_available_time_ns: int,
    training_cutoff_ns: int | None = None,
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if label_source.lower() in FORBIDDEN_LABEL_SOURCES:
        reasons.append("MANUAL_LABEL_SOURCE_REJECTED")
    if label not in (0, 1):
        reasons.append("INVALID_LABEL")
    horizon = path_a_horizon()
    decision = snapshot.decision_time_ns
    if label_available_time_ns <= decision:
        reasons.append("LABEL_AVAILABLE_BEFORE_FORECAST")
    if label_available_time_ns < decision + horizon.duration_ns:
        reasons.append("LABEL_AVAILABLE_BEFORE_HORIZON_COMPLETION")
    if training_cutoff_ns is not None and label_available_time_ns > training_cutoff_ns:
        reasons.append("FUTURE_LABEL_PAST_CUTOFF")
    if snapshot.quality.state == QualityState.INVALID:
        reasons.append("SNAPSHOT_QUALITY_REJECTED")
    for signal in signals:
        if signal.as_of_time_ns > decision:
            reasons.append("SIGNAL_PIT_VIOLATION")
            break
        if signal.source_snapshot_ref is None or signal.source_snapshot_ref.id != snapshot.snapshot_id:
            reasons.append("SIGNAL_SNAPSHOT_MISMATCH")
            break
    if _feature_values(snapshot, signals) is None:
        reasons.append("FEATURE_EXTRACTION_FAILED")
    return (not reasons, tuple(dict.fromkeys(reasons)))


def _row_id(*, snapshot_id: str, decision_time_ns: int, outcome_id: str | None) -> str:
    payload = {
        "snapshot_id": snapshot_id,
        "decision_time_ns": decision_time_ns,
        "outcome_id": outcome_id or "",
    }
    return f"PTR-{sha256_bytes(canonical_bytes(payload))[:16]}"


def collect_candidates_from_repository(
    repository: IntelligenceRepository,
    *,
    collection_mode: str = "GOVERNED_REPOSITORY",
    training_cutoff_ns: int | None = None,
) -> tuple[PathATrainingCandidateRow, ...]:
    forecasts = _iter_store_records(repository, "forecasts", ForecastV1)
    outcomes = _iter_store_records(repository, "outcomes", OutcomeV1)
    forecasts_by_id = {str(row.forecast_id): row for row in forecasts}
    rows: list[PathATrainingCandidateRow] = []

    for outcome in outcomes:
        forecast = forecasts_by_id.get(str(outcome.forecast_id))
        if forecast is None:
            continue
        exclusion = _forecast_excluded_from_production_corpus(forecast)
        if exclusion:
            continue
        label, _label_error = label_from_settled_outcome(outcome)
        if label is None:
            continue
        snapshot = repository.get_snapshot(str(forecast.snapshot_id))
        if snapshot is None:
            continue
        signals = _signals_for_snapshot(repository, snapshot.snapshot_id)
        extracted = _feature_values(snapshot, signals)
        if extracted is None:
            continue
        momentum, nss, lineage = extracted
        label_available = int(outcome.adjudicated_at_ns)
        pit_ok, pit_reasons = pit_validate_candidate(
            snapshot=snapshot,
            signals=signals,
            label=label,
            label_source=LABEL_SOURCE_OUTCOME_V1,
            label_available_time_ns=label_available,
            training_cutoff_ns=training_cutoff_ns,
        )
        layer = CorpusLayer.PIT_VALIDATED_CORPUS if pit_ok else CorpusLayer.CANDIDATE_CORPUS
        event_ids = tuple(
            sorted({ref.id for ref in snapshot.source_event_refs if ref.kind == ContractKind.EVENT.value})
        )
        metadata = dict(outcome.metadata or {})
        rows.append(
            PathATrainingCandidateRow(
                row_id=_row_id(
                    snapshot_id=snapshot.snapshot_id,
                    decision_time_ns=snapshot.decision_time_ns,
                    outcome_id=str(outcome.outcome_id),
                ),
                snapshot_id=snapshot.snapshot_id,
                decision_time_ns=snapshot.decision_time_ns,
                horizon_duration_ns=forecast.horizon.duration_ns,
                label=label,
                label_source=LABEL_SOURCE_OUTCOME_V1,
                label_available_time_ns=label_available,
                momentum=momentum,
                net_signed_share=nss,
                feature_lineage=lineage,
                source_event_ids=event_ids,
                forecast_id=str(forecast.forecast_id),
                outcome_id=str(outcome.outcome_id),
                provider_id=str(metadata.get("provider_id") or metadata.get("data_provider") or "") or None,
                dataset_id=str(metadata.get("dataset_id") or "") or None,
                dataset_version=str(metadata.get("dataset_version") or "") or None,
                dataset_content_hash=str(metadata.get("dataset_content_hash") or "") or None,
                pit_passed=pit_ok,
                pit_reasons=pit_reasons,
                corpus_layer=layer,
                collection_mode=collection_mode,
            )
        )
    return tuple(sorted(rows, key=lambda row: (row.decision_time_ns, row.row_id)))


def build_fixture_proof_candidates(
    *,
    training_cutoff_ns: int,
    instrument_id: str = "AAPL",
) -> tuple[PathATrainingCandidateRow, ...]:
    """Synthetic rows for pipeline proof only — never governed production corpus."""

    horizon = path_a_horizon()
    scope = IntelligenceScope(
        instrument_ids=(f"canonical:EQUITY:XNYS:{instrument_id}",),
        context_id="fixture-only",
    )
    quality = QualitySummary(state=QualityState.GOOD)
    rows: list[PathATrainingCandidateRow] = []
    for index in range(MINIMUM_SPECIALIST_SAMPLES):
        decision = training_cutoff_ns - ((MINIMUM_SPECIALIST_SAMPLES - index) * horizon.duration_ns * 2)
        label = 1 if index % 2 == 0 else 0
        label_available = decision + horizon.duration_ns
        snapshot_id = f"fixture-snap-{index}"
        snapshot = SnapshotV1(
            snapshot_id=snapshot_id,
            schema_version="1",
            decision_time_ns=decision,
            scope=scope,
            quality=quality,
        )
        signals = (
            SignalV1(
                signal_id=f"fixture-mom-{index}",
                schema_version="1",
                signal_type="momentum_simple",
                scope=scope,
                as_of_time_ns=decision,
                value=-0.01 + index * 0.003,
                quality=quality,
                source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snapshot_id),
                calculation_window=horizon,
                calculation_lineage={"calculator_id": "momentum-calculator", "calculator_version": "1"},
                unit="decimal_return",
            ),
            SignalV1(
                signal_id=f"fixture-nss-{index}",
                schema_version="1",
                signal_type="net_signed_share",
                scope=scope,
                as_of_time_ns=decision,
                value=-0.2 + index * 0.05,
                quality=quality,
                source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id=snapshot_id),
                calculation_window=horizon,
                calculation_lineage={"calculator_id": "cvd-calculator", "calculator_version": "1"},
                unit="share",
            ),
        )
        pit_ok, pit_reasons = pit_validate_candidate(
            snapshot=snapshot,
            signals=signals,
            label=label,
            label_source=LABEL_SOURCE_FIXTURE,
            label_available_time_ns=label_available,
            training_cutoff_ns=training_cutoff_ns,
        )
        layer = CorpusLayer.PIT_VALIDATED_CORPUS if pit_ok else CorpusLayer.CANDIDATE_CORPUS
        rows.append(
            PathATrainingCandidateRow(
                row_id=_row_id(snapshot_id=snapshot_id, decision_time_ns=decision, outcome_id=None),
                snapshot_id=snapshot_id,
                decision_time_ns=decision,
                horizon_duration_ns=horizon.duration_ns,
                label=label,
                label_source=LABEL_SOURCE_FIXTURE,
                label_available_time_ns=label_available,
                momentum=-0.01 + index * 0.003,
                net_signed_share=-0.2 + index * 0.05,
                feature_lineage=(
                    {
                        "signal_type": "momentum_simple",
                        "calculator_id": "momentum-calculator",
                        "calculator_version": "1",
                    },
                    {
                        "signal_type": "net_signed_share",
                        "calculator_id": "cvd-calculator",
                        "calculator_version": "1",
                    },
                ),
                source_event_ids=(),
                forecast_id=None,
                outcome_id=None,
                provider_id="FIXTURE_ONLY",
                dataset_id="fixture-path-a-corpus",
                dataset_version="0",
                dataset_content_hash=None,
                pit_passed=pit_ok,
                pit_reasons=pit_reasons,
                corpus_layer=layer,
                collection_mode="FIXTURE_ONLY",
            )
        )
    return tuple(rows)


def floor_counters(rows: Iterable[PathATrainingCandidateRow], *, governed_only: bool = True) -> CorpusFloorCounters:
    class_0 = 0
    class_1 = 0
    total = 0
    for row in rows:
        if governed_only and row.label_source == LABEL_SOURCE_FIXTURE:
            continue
        if governed_only and not row.pit_passed:
            continue
        total += 1
        if row.label == 0:
            class_0 += 1
        else:
            class_1 += 1
    return CorpusFloorCounters(total_rows=total, class_0=class_0, class_1=class_1)


def export_candidate_corpus(
    rows: Iterable[PathATrainingCandidateRow],
    *,
    training_cutoff_ns: int,
    target_instrument_id: str = "AAPL",
) -> dict[str, Any]:
    materialized = tuple(rows)
    return {
        "artifact_kind": CANDIDATE_CORPUS_KIND,
        "pipeline_version": CORPUS_COLLECTOR_VERSION,
        "corpus_layer": CorpusLayer.CANDIDATE_CORPUS.value,
        "production_claim": False,
        "target_instrument_id": target_instrument_id,
        "training_cutoff_ns": training_cutoff_ns,
        "rows": [row.to_dict() for row in materialized],
    }


def export_pit_validated_corpus(
    rows: Iterable[PathATrainingCandidateRow],
    *,
    training_cutoff_ns: int,
    target_instrument_id: str = "AAPL",
) -> dict[str, Any]:
    validated = tuple(row for row in rows if row.pit_passed)
    return {
        "artifact_kind": PIT_VALIDATED_CORPUS_KIND,
        "pipeline_version": CORPUS_COLLECTOR_VERSION,
        "corpus_layer": CorpusLayer.PIT_VALIDATED_CORPUS.value,
        "production_claim": False,
        "target_instrument_id": target_instrument_id,
        "training_cutoff_ns": training_cutoff_ns,
        "rows": [row.to_dict() for row in validated],
    }


def export_manifest_candidate(
    rows: Iterable[PathATrainingCandidateRow],
    *,
    training_cutoff_ns: int,
    target_instrument_id: str = "AAPL",
    scope: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Shape-compatible with ``path_a_production_training_manifest_v1`` examples but not governed."""

    pit_rows = [row for row in rows if row.pit_passed and row.label_source != LABEL_SOURCE_FIXTURE]
    scope_body = dict(scope or {})
    if not scope_body:
        scope_body = {
            "instrument_ids": [f"canonical:EQUITY:XNYS:{target_instrument_id}"],
            "context_id": "path-a-corpus-collector-candidate",
        }
    examples = [
        {
            "snapshot_id": row.snapshot_id,
            "decision_time_ns": row.decision_time_ns,
            "label": row.label,
            "label_available_time_ns": row.label_available_time_ns,
            "momentum": row.momentum,
            "net_signed_share": row.net_signed_share,
            "provenance": {
                "label_source": row.label_source,
                "forecast_id": row.forecast_id,
                "outcome_id": row.outcome_id,
                "feature_lineage": [dict(item) for item in row.feature_lineage],
                "source_event_ids": list(row.source_event_ids),
                "pit_passed": row.pit_passed,
            },
        }
        for row in pit_rows
    ]
    return {
        "artifact_kind": MANIFEST_CANDIDATE_KIND,
        "reference_manifest_kind": TRAINING_MANIFEST_KIND,
        "corpus_layer": CorpusLayer.GOVERNED_TRAINING_MANIFEST.value,
        "governance_status": "MANIFEST_CANDIDATE_NOT_GOVERNED",
        "production_claim": False,
        "production_artifact_status": "PRODUCTION_FORECAST_BLOCKED_NO_GOVERNED_PATH_A_TRAINING_CORPUS",
        "target_instrument_id": target_instrument_id,
        "training_cutoff_ns": training_cutoff_ns,
        "calibration_cutoff_ns": training_cutoff_ns,
        "scope": scope_body,
        "examples": examples,
    }


def discover_jsonl_paths(repo_root: Path, *, extra_globs: Iterable[str] = ()) -> tuple[Path, ...]:
    globs = (*DEFAULT_JSONL_SEARCH_GLOBS, *extra_globs)
    found: set[Path] = set()
    for pattern in globs:
        for path in repo_root.glob(pattern):
            if not path.is_file():
                continue
            normalized = str(path).replace("\\", "/")
            if "/forward-test-campaigns/" in normalized and "FTEP-V1-00" in normalized:
                continue
            if ".worktrees/weekday-opend-hop-d1ba" in normalized:
                continue
            found.add(path.resolve())
    return tuple(sorted(found))


def scan_jsonl_for_settled_outcomes(paths: Iterable[Path]) -> JsonlOutcomeScanSummary:
    paths_scanned = 0
    settled = 0
    parse_errors = 0
    for path in paths:
        if not path.is_file():
            continue
        paths_scanned += 1
        for _line, record, error in iter_jsonl_envelopes(path):
            if error is not None:
                parse_errors += 1
                continue
            if record is None:
                continue
            body = record.get("body") if isinstance(record.get("body"), dict) else record
            if not isinstance(body, dict):
                continue
            status = str(body.get("resolution_status") or "").upper()
            if status != OutcomeResolutionStatus.SETTLED.value:
                continue
            try:
                outcome_v1_from_dict(body)
            except (TypeError, ValueError):
                parse_errors += 1
                continue
            settled += 1
    return JsonlOutcomeScanSummary(
        paths_scanned=paths_scanned,
        settled_outcome_envelopes=settled,
        parse_errors=parse_errors,
    )


def run_corpus_collection_pipeline(
    *,
    repository: IntelligenceRepository | None = None,
    repo_root: Path | None = None,
    training_cutoff_ns: int,
    include_fixture_proof: bool = False,
    jsonl_paths: Iterable[Path] | None = None,
) -> tuple[CorpusCollectionReport, tuple[PathATrainingCandidateRow, ...]]:
    governed_rows: list[PathATrainingCandidateRow] = []
    if repository is not None:
        governed_rows.extend(
            collect_candidates_from_repository(
                repository,
                training_cutoff_ns=training_cutoff_ns,
            )
        )

    scan_summary = None
    if repo_root is not None:
        paths = tuple(jsonl_paths) if jsonl_paths is not None else discover_jsonl_paths(repo_root)
        scan_summary = scan_jsonl_for_settled_outcomes(paths)

    fixture_rows: tuple[PathATrainingCandidateRow, ...] = ()
    if include_fixture_proof:
        fixture_rows = build_fixture_proof_candidates(training_cutoff_ns=training_cutoff_ns)

    all_rows = tuple([*governed_rows, *fixture_rows])
    governed_pit = [row for row in governed_rows if row.pit_passed]
    class_0 = sum(1 for row in governed_pit if row.label == 0)
    class_1 = sum(1 for row in governed_pit if row.label == 1)

    manifest_status = "NO_GOVERNED_PATH_A_TRAINING_CORPUS"
    if governed_pit and floor_counters(governed_pit).specialist_floor_met:
        manifest_status = "GOVERNED_MANIFEST_FLOORS_MET_PENDING_ATTESTATION"
    elif governed_pit:
        manifest_status = "GOVERNED_ROWS_INSUFFICIENT_FOR_FLOORS"

    notes = (
        "Collector exports candidates only; FIXTURE_ONLY rows are not governed production corpus.",
        "GOVERNED_TRAINING_MANIFEST requires attestation beyond this pipeline.",
    )
    if not governed_rows and include_fixture_proof:
        notes = (
            *notes,
            "No governed Path A rows in repository or scanned JSONL joins; fixture proof exercised export machinery.",
        )

    report = CorpusCollectionReport(
        status=STATUS_PIPELINE_READY,
        governed_candidate_rows=len(governed_rows),
        pit_valid_governed_rows=len(governed_pit),
        fixture_only_rows=len(fixture_rows),
        class_0_governed=class_0,
        class_1_governed=class_1,
        governed_training_manifest_status=manifest_status,
        production_artifact_status="PRODUCTION_FORECAST_BLOCKED_NO_GOVERNED_PATH_A_TRAINING_CORPUS",
        corpus_layers={
            CorpusLayer.CANDIDATE_CORPUS.value: CANDIDATE_CORPUS_KIND,
            CorpusLayer.PIT_VALIDATED_CORPUS.value: PIT_VALIDATED_CORPUS_KIND,
            CorpusLayer.GOVERNED_TRAINING_MANIFEST.value: MANIFEST_CANDIDATE_KIND,
            CorpusLayer.PRODUCTION_ARTIFACT.value: "NOT_EMITTED_BY_COLLECTOR",
        },
        jsonl_scan=scan_summary,
        notes=notes,
    )
    return report, all_rows


def manifest_candidate_is_not_governed_loader_input(payload: Mapping[str, Any]) -> bool:
    """True when ``training_build.load_governed_training_manifest`` would reject the payload."""

    kind = str(payload.get("artifact_kind") or "")
    if kind != TRAINING_MANIFEST_KIND:
        return True
    return load_governed_training_manifest_from_mapping(payload) is None


def load_governed_training_manifest_from_mapping(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    import tempfile

    if str(payload.get("artifact_kind") or "") != TRAINING_MANIFEST_KIND:
        return None
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(dict(payload), handle)
        path = Path(handle.name)
    try:
        return load_governed_training_manifest(path)
    finally:
        path.unlink(missing_ok=True)


def assert_not_governed_production_manifest(payload: Mapping[str, Any]) -> tuple[str, ...]:
    reasons: list[str] = []
    kind = str(payload.get("artifact_kind") or "")
    if kind == MANIFEST_CANDIDATE_KIND:
        reasons.append("MANIFEST_CANDIDATE_NOT_GOVERNED")
    if kind != TRAINING_MANIFEST_KIND:
        reasons.append("NOT_GOVERNED_MANIFEST_KIND")
    if payload.get("production_claim") is True:
        reasons.append("PRODUCTION_CLAIM_FORBIDDEN")
    return tuple(dict.fromkeys(reasons))


__all__ = [
    "CANDIDATE_CORPUS_KIND",
    "CORPUS_COLLECTOR_VERSION",
    "CorpusCollectionReport",
    "CorpusFloorCounters",
    "CorpusLayer",
    "JsonlOutcomeScanSummary",
    "MANIFEST_CANDIDATE_KIND",
    "PIT_VALIDATED_CORPUS_KIND",
    "PathATrainingCandidateRow",
    "STATUS_PIPELINE_READY",
    "assert_not_governed_production_manifest",
    "build_fixture_proof_candidates",
    "collect_candidates_from_repository",
    "discover_jsonl_paths",
    "export_candidate_corpus",
    "export_manifest_candidate",
    "export_pit_validated_corpus",
    "floor_counters",
    "label_from_settled_outcome",
    "pit_validate_candidate",
    "run_corpus_collection_pipeline",
    "scan_jsonl_for_settled_outcomes",
]
