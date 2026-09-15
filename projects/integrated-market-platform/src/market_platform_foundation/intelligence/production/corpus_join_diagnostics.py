"""Join-edge diagnostics for Path A governed corpus collection (Item 7 Lane D)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.common import OutcomeResolutionStatus
from ..contracts.forecast import ForecastV1
from ..contracts.outcome import OutcomeV1
from ..contracts.signal import SignalV1
from ..contracts.snapshot import SnapshotV1
from ..persistence.repository import IntelligenceRepository
from .corpus_collector import (
    _feature_values,
    _forecast_excluded_from_production_corpus,
    _iter_store_records,
    _signals_for_snapshot,
    label_from_settled_outcome,
    pit_validate_candidate,
    LABEL_SOURCE_OUTCOME_V1,
)
from .corpus_collector import CorpusFloorCounters, floor_counters


@dataclass(frozen=True, slots=True)
class CorpusJoinSample:
    outcome_id: str | None
    forecast_id: str | None
    snapshot_id: str | None
    edge: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "forecast_id": self.forecast_id,
            "snapshot_id": self.snapshot_id,
            "edge": self.edge,
        }


@dataclass(frozen=True, slots=True)
class CorpusJoinDiagnostics:
    outcome_total: int = 0
    forecast_total: int = 0
    snapshot_total: int = 0
    signal_total: int = 0
    settled_outcomes: int = 0
    production_eligible_forecasts: int = 0
    joinable_governed_rows: int = 0
    pit_valid_governed_rows: int = 0
    missing_edges: dict[str, int] = field(default_factory=dict)
    samples: tuple[CorpusJoinSample, ...] = ()
    floor_counters: CorpusFloorCounters | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "artifact_kind": "item7_path_a_corpus_join_diagnostics_v1",
            "outcome_total": self.outcome_total,
            "forecast_total": self.forecast_total,
            "snapshot_total": self.snapshot_total,
            "signal_total": self.signal_total,
            "settled_outcomes": self.settled_outcomes,
            "production_eligible_forecasts": self.production_eligible_forecasts,
            "joinable_governed_rows": self.joinable_governed_rows,
            "pit_valid_governed_rows": self.pit_valid_governed_rows,
            "missing_edges": dict(sorted(self.missing_edges.items())),
            "samples": [sample.to_dict() for sample in self.samples],
        }
        if self.floor_counters is not None:
            body["floor_counters"] = {
                "total_rows": self.floor_counters.total_rows,
                "class_0": self.floor_counters.class_0,
                "class_1": self.floor_counters.class_1,
                "specialist_floor_met": self.floor_counters.specialist_floor_met,
                "calibration_floor_met": self.floor_counters.calibration_floor_met,
            }
        return body


def _is_production_eligible_forecast(forecast: ForecastV1) -> bool:
    return not _forecast_excluded_from_production_corpus(forecast)


def _note_edge(
    edges: dict[str, int],
    edge: str,
    *,
    samples: list[CorpusJoinSample],
    outcome_id: str | None,
    forecast_id: str | None,
    snapshot_id: str | None,
    max_samples: int,
) -> None:
    edges[edge] = edges.get(edge, 0) + 1
    if len(samples) < max_samples:
        samples.append(
            CorpusJoinSample(
                outcome_id=outcome_id,
                forecast_id=forecast_id,
                snapshot_id=snapshot_id,
                edge=edge,
            )
        )


def diagnose_corpus_join_edges(
    repository: IntelligenceRepository,
    *,
    training_cutoff_ns: int | None = None,
    max_samples: int = 8,
) -> CorpusJoinDiagnostics:
    """Report why settled outcomes do or do not become governed corpus rows."""

    forecasts = _iter_store_records(repository, "forecasts", ForecastV1)
    outcomes = _iter_store_records(repository, "outcomes", OutcomeV1)
    snapshots = _iter_store_records(repository, "snapshots", SnapshotV1)
    signals = _iter_store_records(repository, "signals", SignalV1)
    forecasts_by_id = {str(row.forecast_id): row for row in forecasts}

    production_eligible = sum(1 for row in forecasts if _is_production_eligible_forecast(row))
    settled = sum(1 for row in outcomes if row.resolution_status == OutcomeResolutionStatus.SETTLED)

    edges: dict[str, int] = {}
    samples: list[CorpusJoinSample] = []
    joinable = 0
    pit_valid = 0
    pit_rows: list = []

    for outcome in outcomes:
        forecast = forecasts_by_id.get(str(outcome.forecast_id))
        if forecast is None:
            _note_edge(
                edges,
                "FORECAST_NOT_FOUND",
                samples=samples,
                outcome_id=str(outcome.outcome_id),
                forecast_id=str(outcome.forecast_id),
                snapshot_id=None,
                max_samples=max_samples,
            )
            continue
        exclusion = _forecast_excluded_from_production_corpus(forecast)
        if exclusion:
            edge = exclusion[0]
            _note_edge(
                edges,
                edge,
                samples=samples,
                outcome_id=str(outcome.outcome_id),
                forecast_id=str(forecast.forecast_id),
                snapshot_id=str(forecast.snapshot_id),
                max_samples=max_samples,
            )
            continue
        if outcome.resolution_status != OutcomeResolutionStatus.SETTLED:
            _note_edge(
                edges,
                "OUTCOME_NOT_SETTLED",
                samples=samples,
                outcome_id=str(outcome.outcome_id),
                forecast_id=str(forecast.forecast_id),
                snapshot_id=str(forecast.snapshot_id),
                max_samples=max_samples,
            )
            continue
        label, label_error = label_from_settled_outcome(outcome)
        if label is None:
            _note_edge(
                edges,
                label_error or "OUTCOME_UNLABELABLE",
                samples=samples,
                outcome_id=str(outcome.outcome_id),
                forecast_id=str(forecast.forecast_id),
                snapshot_id=str(forecast.snapshot_id),
                max_samples=max_samples,
            )
            continue
        snapshot = repository.get_snapshot(str(forecast.snapshot_id))
        if snapshot is None:
            _note_edge(
                edges,
                "SNAPSHOT_NOT_FOUND",
                samples=samples,
                outcome_id=str(outcome.outcome_id),
                forecast_id=str(forecast.forecast_id),
                snapshot_id=str(forecast.snapshot_id),
                max_samples=max_samples,
            )
            continue
        signal_rows = _signals_for_snapshot(repository, snapshot.snapshot_id)
        if not signal_rows:
            _note_edge(
                edges,
                "SIGNALS_MISSING_FOR_SNAPSHOT",
                samples=samples,
                outcome_id=str(outcome.outcome_id),
                forecast_id=str(forecast.forecast_id),
                snapshot_id=str(snapshot.snapshot_id),
                max_samples=max_samples,
            )
            continue
        if _feature_values(snapshot, signal_rows) is None:
            _note_edge(
                edges,
                "FEATURE_EXTRACTION_FAILED",
                samples=samples,
                outcome_id=str(outcome.outcome_id),
                forecast_id=str(forecast.forecast_id),
                snapshot_id=str(snapshot.snapshot_id),
                max_samples=max_samples,
            )
            continue
        joinable += 1
        label_available = int(outcome.adjudicated_at_ns)
        pit_ok, pit_reasons = pit_validate_candidate(
            snapshot=snapshot,
            signals=signal_rows,
            label=label,
            label_source=LABEL_SOURCE_OUTCOME_V1,
            label_available_time_ns=label_available,
            training_cutoff_ns=training_cutoff_ns,
        )
        if pit_ok:
            pit_valid += 1
            pit_rows.append(label)
        else:
            edge = pit_reasons[0] if pit_reasons else "PIT_VALIDATION_FAILED"
            _note_edge(
                edges,
                edge,
                samples=samples,
                outcome_id=str(outcome.outcome_id),
                forecast_id=str(forecast.forecast_id),
                snapshot_id=str(snapshot.snapshot_id),
                max_samples=max_samples,
            )

    for forecast in forecasts:
        if not _is_production_eligible_forecast(forecast):
            continue
        if not any(str(outcome.forecast_id) == str(forecast.forecast_id) for outcome in outcomes):
            _note_edge(
                edges,
                "OUTCOME_MISSING_FOR_FORECAST",
                samples=samples,
                outcome_id=None,
                forecast_id=str(forecast.forecast_id),
                snapshot_id=str(forecast.snapshot_id),
                max_samples=max_samples,
            )

    counters = None
    if pit_valid:
        from .corpus_collector import collect_candidates_from_repository

        rows = collect_candidates_from_repository(repository, training_cutoff_ns=training_cutoff_ns)
        pit_only = [row for row in rows if row.pit_passed]
        counters = floor_counters(pit_only, governed_only=True)

    return CorpusJoinDiagnostics(
        outcome_total=len(outcomes),
        forecast_total=len(forecasts),
        snapshot_total=len(snapshots),
        signal_total=len(signals),
        settled_outcomes=settled,
        production_eligible_forecasts=production_eligible,
        joinable_governed_rows=joinable,
        pit_valid_governed_rows=pit_valid,
        missing_edges=edges,
        samples=tuple(samples),
        floor_counters=counters,
    )


__all__ = ["CorpusJoinDiagnostics", "CorpusJoinSample", "diagnose_corpus_join_edges"]
