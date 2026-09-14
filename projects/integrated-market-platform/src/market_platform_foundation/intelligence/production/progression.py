"""Item 7 Lane D — production forecast path progression and empirical-floor diagnostics.

Observes lawful quote → grid → pre-existing PRODUCTION ``ForecastV1`` → ledger →
settlement → specialist/calibration floors. Does not mint forecasts from quotes,
does not weaken contributor/calibration gates, and never claims ``ITEM7_COMPLETE``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ..contracts.common import Direction, OutcomeResolutionStatus
from ..contracts.forecast import ForecastV1
from ..contracts.outcome import OutcomeV1
from ..contracts.prediction_ledger import PredictionLedgerEntryV1
from ..evaluation.types import forecast_role
from ..fusion.calibration_data import MINIMUM_CALIBRATION_SAMPLES, MINIMUM_CLASS_COUNT
from ..fusion.types import (
    FINAL_FORECAST_STAGE,
    ForecastContributorRole,
    PRODUCTION_FORECAST_STAGE,
)
from ..outcomes.opend_capture_ledger import (
    enrich_funnel_from_repository,
    is_grid_point_candidate,
    is_tape_eligible_event,
    iter_jsonl_envelopes,
    materialize_opend_capture_jsonl,
    normalize_capture_record,
    pit_refusal_reason,
    scan_capture_funnel,
)
from ..outcomes.service import OutcomeSettlementService
from ..outcomes.types import SettlementStatus
from ..persistence.repository import IntelligenceRepository
from .identity import (
    MINIMUM_SPECIALIST_CLASS_COUNT,
    MINIMUM_SPECIALIST_SAMPLES,
    matches_path_a_identity,
)

ITEM7_STATUS_PARTIAL = "ITEM7_PARTIAL"
ITEM7_STATUS_COMPLETE_FORBIDDEN = "ITEM7_COMPLETE_NOT_ASSERTED"

ITEM7_STAGE_ORDER: tuple[str, ...] = (
    "raw",
    "normalized",
    "tape_eligible",
    "grid",
    "production_forecast_available",
    "forecast_bound",
    "ledger",
    "pending",
    "settled",
    "specialist_eligible",
    "calibration_eligible",
)


@dataclass(frozen=True, slots=True)
class EmpiricalFloorCounters:
    settled_labelable: int = 0
    class_0: int = 0
    class_1: int = 0
    specialist_floor_samples: int = MINIMUM_SPECIALIST_SAMPLES
    specialist_floor_per_class: int = MINIMUM_SPECIALIST_CLASS_COUNT
    calibration_floor_samples: int = MINIMUM_CALIBRATION_SAMPLES
    calibration_floor_per_class: int = MINIMUM_CLASS_COUNT

    def to_dict(self) -> dict[str, int]:
        return {
            "calibration_floor_per_class": self.calibration_floor_per_class,
            "calibration_floor_samples": self.calibration_floor_samples,
            "class_0": self.class_0,
            "class_1": self.class_1,
            "settled_labelable": self.settled_labelable,
            "specialist_floor_per_class": self.specialist_floor_per_class,
            "specialist_floor_samples": self.specialist_floor_samples,
        }


@dataclass(frozen=True, slots=True)
class Item7StageVector:
    """Boolean pass/fail per progression stage (aggregate path)."""

    raw: bool = False
    normalized: bool = False
    tape_eligible: bool = False
    grid: bool = False
    production_forecast_available: bool = False
    forecast_bound: bool = False
    ledger: bool = False
    pending: bool = False
    settled: bool = False
    specialist_eligible: bool = False
    calibration_eligible: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {name: getattr(self, name) for name in ITEM7_STAGE_ORDER}

    def first_failing_stage(self) -> str | None:
        for name in ITEM7_STAGE_ORDER:
            if not getattr(self, name):
                return name
        return None


@dataclass(frozen=True, slots=True)
class Item7ProgressionCounts:
    raw: int = 0
    normalized: int = 0
    tape_eligible: int = 0
    grid: int = 0
    production_forecast_available: int = 0
    forecast_bound: int = 0
    ledger: int = 0
    pending: int = 0
    settled: int = 0
    specialist_eligible: int = 0
    calibration_eligible: int = 0

    def to_dict(self) -> dict[str, int]:
        return {name: getattr(self, name) for name in ITEM7_STAGE_ORDER}


@dataclass(frozen=True, slots=True)
class Item7ProgressionReport:
    item7_status: str
    stage_vector: Item7StageVector
    counts: Item7ProgressionCounts
    first_failing_stage: str | None
    empirical_floors: EmpiricalFloorCounters
    production_contributor_ids: tuple[str, ...] = ()
    production_fused_forecast_ids: tuple[str, ...] = ()
    calibration_artifact_present: bool = False
    refusal_reasons: dict[str, int] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_kind": "item7_production_forecast_progression_v1",
            "calibration_artifact_present": self.calibration_artifact_present,
            "counts": self.counts.to_dict(),
            "empirical_floors": self.empirical_floors.to_dict(),
            "first_failing_stage": self.first_failing_stage,
            "item7_status": self.item7_status,
            "notes": list(self.notes),
            "production_contributor_ids": list(self.production_contributor_ids),
            "production_fused_forecast_ids": list(self.production_fused_forecast_ids),
            "readable_summary": self.readable_summary(),
            "refusal_reasons": dict(self.refusal_reasons),
            "stage_vector": self.stage_vector.to_dict(),
        }

    def readable_summary(self) -> str:
        failing = self.first_failing_stage or "none (all stages pass — still not ITEM7_COMPLETE)"
        return (
            f"Item 7 production forecast path: {self.item7_status}. "
            f"First failing stage: {failing}. "
            f"Settled labelable outcomes: {self.empirical_floors.settled_labelable} "
            f"(specialist floor {self.empirical_floors.specialist_floor_samples}, "
            f"calibration floor {self.empirical_floors.calibration_floor_samples})."
        )


def _iter_repository_forecasts(repository: IntelligenceRepository) -> tuple[ForecastV1, ...]:
    stores = getattr(repository, "_stores", None)
    if not isinstance(stores, dict):
        return ()
    bucket = stores.get("forecasts")
    if not isinstance(bucket, dict):
        return ()
    decode = getattr(repository, "_decode", None)
    if decode is None:
        return ()
    rows: list[ForecastV1] = []
    for body in bucket.values():
        forecast = decode(ForecastV1, body)
        if forecast is not None:
            rows.append(forecast)
    return tuple(sorted(rows, key=lambda row: str(row.forecast_id)))


def _iter_repository_outcomes(repository: IntelligenceRepository) -> tuple[OutcomeV1, ...]:
    stores = getattr(repository, "_stores", None)
    if not isinstance(stores, dict):
        return ()
    bucket = stores.get("outcomes")
    if not isinstance(bucket, dict):
        return ()
    decode = getattr(repository, "_decode", None)
    if decode is None:
        return ()
    rows: list[OutcomeV1] = []
    for body in bucket.values():
        outcome = decode(OutcomeV1, body)
        if outcome is not None:
            rows.append(outcome)
    return tuple(sorted(rows, key=lambda row: str(row.outcome_id)))


def _iter_repository_ledger(repository: IntelligenceRepository) -> tuple[PredictionLedgerEntryV1, ...]:
    stores = getattr(repository, "_stores", None)
    if not isinstance(stores, dict):
        return ()
    bucket = stores.get("prediction_ledger")
    if not isinstance(bucket, dict):
        return ()
    decode = getattr(repository, "_decode", None)
    if decode is None:
        return ()
    rows: list[PredictionLedgerEntryV1] = []
    for body in bucket.values():
        entry = decode(PredictionLedgerEntryV1, body)
        if entry is not None:
            rows.append(entry)
    return tuple(sorted(rows, key=lambda row: str(row.ledger_entry_id)))


def _is_production_raw_contributor(forecast: ForecastV1) -> bool:
    if forecast_role(forecast) != ForecastContributorRole.PRODUCTION.value:
        return False
    stage = str(forecast.metadata.get("forecast_stage") or "")
    if stage != PRODUCTION_FORECAST_STAGE:
        return False
    calibration = str(forecast.metadata.get("calibration_status") or "").upper()
    if calibration and calibration != "UNCALIBRATED":
        return False
    if forecast.estimate.calibrated_probability is not None:
        return False
    return not matches_path_a_identity(target=forecast.target, horizon=forecast.horizon)


def _is_hop_fused_production_forecast(forecast: ForecastV1) -> bool:
    if forecast_role(forecast) != ForecastContributorRole.PRODUCTION.value:
        return False
    stage = str(forecast.metadata.get("forecast_stage") or "")
    if stage != FINAL_FORECAST_STAGE:
        return False
    calibration = str(forecast.metadata.get("calibration_status") or "").upper()
    if calibration != "CALIBRATED":
        return False
    if forecast.estimate.calibrated_probability is None:
        return False
    return not matches_path_a_identity(target=forecast.target, horizon=forecast.horizon)


def _collect_lawful_production_forecasts(
    *,
    repository: IntelligenceRepository,
    contributor_paths: Iterable[Path | None],
    forecast_paths: Iterable[Path | None],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    from ...strategy.path_a_forecast_producer import load_paper_demo_contributors
    from ...strategy.path_a_forecast_store import load_paper_demo_forecasts

    contributor_ids: set[str] = set()
    fused_ids: set[str] = set()

    def _scan_loaded(forecasts: Iterable[ForecastV1]) -> None:
        for forecast in forecasts:
            if _is_production_raw_contributor(forecast):
                contributor_ids.add(str(forecast.forecast_id))
            if _is_hop_fused_production_forecast(forecast):
                fused_ids.add(str(forecast.forecast_id))

    for path in contributor_paths:
        if path is None:
            continue
        _scan_loaded(load_paper_demo_contributors(path))
    for path in forecast_paths:
        if path is None:
            continue
        _scan_loaded(load_paper_demo_forecasts(path))
    _scan_loaded(_iter_repository_forecasts(repository))
    return tuple(sorted(contributor_ids)), tuple(sorted(fused_ids))


def _label_from_outcome(outcome: OutcomeV1) -> int | None:
    if outcome.resolution_status != OutcomeResolutionStatus.SETTLED:
        return None
    if outcome.realized_direction == Direction.UP:
        return 1
    if outcome.realized_direction == Direction.DOWN:
        return 0
    return None


def _count_production_settled_labels(
    repository: IntelligenceRepository,
) -> EmpiricalFloorCounters:
    forecasts_by_id = {str(row.forecast_id): row for row in _iter_repository_forecasts(repository)}
    class_0 = 0
    class_1 = 0
    for outcome in _iter_repository_outcomes(repository):
        forecast = forecasts_by_id.get(str(outcome.forecast_id))
        if forecast is None:
            continue
        if forecast_role(forecast) != ForecastContributorRole.PRODUCTION.value:
            continue
        label = _label_from_outcome(outcome)
        if label is None:
            continue
        if label == 0:
            class_0 += 1
        else:
            class_1 += 1
    total = class_0 + class_1
    return EmpiricalFloorCounters(
        settled_labelable=total,
        class_0=class_0,
        class_1=class_1,
    )


def _specialist_floor_met(floors: EmpiricalFloorCounters) -> bool:
    if floors.settled_labelable < floors.specialist_floor_samples:
        return False
    return (
        floors.class_0 >= floors.specialist_floor_per_class
        and floors.class_1 >= floors.specialist_floor_per_class
    )


def _calibration_floor_met(floors: EmpiricalFloorCounters) -> bool:
    if floors.settled_labelable < floors.calibration_floor_samples:
        return False
    return (
        floors.class_0 >= floors.calibration_floor_per_class
        and floors.class_1 >= floors.calibration_floor_per_class
    )


def scan_capture_stage_counts(
    capture_path: Path,
    *,
    as_of_ns: int,
    session_start_ns: int,
) -> Item7ProgressionCounts:
    """Line-level capture funnel without persisting events."""

    raw = normalized = tape = grid = 0
    for line_index, record, parse_error in iter_jsonl_envelopes(capture_path):
        if parse_error is not None or record is None:
            continue
        raw += 1
        if pit_refusal_reason(record, as_of_ns=as_of_ns, session_start_ns=session_start_ns) is not None:
            continue
        event = normalize_capture_record(record, capture_path=capture_path, line_index=line_index)
        if event is None:
            continue
        normalized += 1
        if is_tape_eligible_event(event, as_of_ns=as_of_ns):
            tape += 1
        if is_grid_point_candidate(
            record,
            event,
            as_of_ns=as_of_ns,
            session_start_ns=session_start_ns,
        ):
            grid += 1
    return Item7ProgressionCounts(
        raw=raw,
        normalized=normalized,
        tape_eligible=tape,
        grid=grid,
    )


def build_item7_progression_report(
    *,
    repository: IntelligenceRepository,
    as_of_ns: int,
    session_start_ns: int,
    capture_path: Path | None = None,
    contributor_path: Path | None = None,
    forecast_path: Path | None = None,
    calibration_path: Path | None = None,
    forecast_bindings: dict[str, str] | None = None,
    materialize_capture: bool = False,
) -> Item7ProgressionReport:
    """Assemble Item 7 progression report from capture artifacts and repository state."""

    from ...strategy.path_a_forecast_producer import load_paper_demo_calibration

    bindings = dict(forecast_bindings or {})
    refusal_reasons: dict[str, int] = {}
    notes: list[str] = [
        "Software-only diagnostics; one settled example does not prove empirical Item 7.",
    ]

    bound_from_materialize = 0
    if capture_path is not None and capture_path.is_file():
        line_counts = scan_capture_stage_counts(
            capture_path,
            as_of_ns=as_of_ns,
            session_start_ns=session_start_ns,
        )
        funnel = scan_capture_funnel(
            capture_path,
            as_of_ns=as_of_ns,
            session_start_ns=session_start_ns,
        )
        if materialize_capture:
            partial = materialize_opend_capture_jsonl(
                capture_path,
                repository,
                as_of_ns=as_of_ns,
                session_start_ns=session_start_ns,
                forecast_bindings=bindings or None,
            )
            for reason, count in partial.refusal_reasons.items():
                refusal_reasons[reason] = refusal_reasons.get(reason, 0) + count
            funnel = partial.funnel
            bound_from_materialize = sum(1 for c in partial.candidates if c.forecast_id is not None)
        enriched = enrich_funnel_from_repository(funnel, repository, as_of_ns=as_of_ns)
        counts = Item7ProgressionCounts(
            raw=funnel.raw_envelopes,
            normalized=line_counts.normalized,
            tape_eligible=funnel.tape_eligible,
            grid=funnel.grid_points,
            forecast_bound=bound_from_materialize,
            ledger=enriched.materialized_ledger,
            pending=enriched.pending_settlement,
            settled=enriched.settled,
        )
    else:
        counts = Item7ProgressionCounts()
        settlement = OutcomeSettlementService(repository)
        pending = 0
        settled = 0
        for entry in _iter_repository_ledger(repository):
            status = settlement.inspect_settlement(entry, now_ns=as_of_ns)
            if status == SettlementStatus.ALREADY_SETTLED:
                settled += 1
            elif status in {SettlementStatus.NOT_DUE, SettlementStatus.DUE}:
                pending += 1
        counts = Item7ProgressionCounts(
            ledger=len(_iter_repository_ledger(repository)),
            pending=pending,
            settled=settled,
        )

    contributor_ids, fused_ids = _collect_lawful_production_forecasts(
        repository=repository,
        contributor_paths=(contributor_path,),
        forecast_paths=(forecast_path,),
    )
    production_available = len(contributor_ids) + len(fused_ids)
    counts = Item7ProgressionCounts(
        raw=counts.raw,
        normalized=counts.normalized,
        tape_eligible=counts.tape_eligible,
        grid=counts.grid,
        production_forecast_available=production_available,
        forecast_bound=counts.forecast_bound
        or sum(
            1
            for binding_id, forecast_id in bindings.items()
            if binding_id and forecast_id and repository.get_forecast(forecast_id) is not None
        ),
        ledger=counts.ledger,
        pending=counts.pending,
        settled=counts.settled,
    )

    empirical = _count_production_settled_labels(repository)
    specialist_ok = _specialist_floor_met(empirical)
    calibration_ok = _calibration_floor_met(empirical)
    counts = Item7ProgressionCounts(
        raw=counts.raw,
        normalized=counts.normalized,
        tape_eligible=counts.tape_eligible,
        grid=counts.grid,
        production_forecast_available=counts.production_forecast_available,
        forecast_bound=counts.forecast_bound,
        ledger=counts.ledger,
        pending=counts.pending,
        settled=counts.settled,
        specialist_eligible=1 if specialist_ok else 0,
        calibration_eligible=1 if calibration_ok else 0,
    )

    calibration_artifact_present = load_paper_demo_calibration(calibration_path) is not None

    stage_vector = Item7StageVector(
        raw=counts.raw > 0,
        normalized=counts.normalized > 0,
        tape_eligible=counts.tape_eligible > 0,
        grid=counts.grid > 0,
        production_forecast_available=counts.production_forecast_available > 0,
        forecast_bound=counts.forecast_bound > 0,
        ledger=counts.ledger > 0,
        pending=counts.pending > 0,
        settled=counts.settled > 0,
        specialist_eligible=specialist_ok,
        calibration_eligible=calibration_ok,
    )
    first_failing = stage_vector.first_failing_stage()

    return Item7ProgressionReport(
        item7_status=ITEM7_STATUS_PARTIAL,
        stage_vector=stage_vector,
        counts=counts,
        first_failing_stage=first_failing,
        empirical_floors=empirical,
        production_contributor_ids=contributor_ids,
        production_fused_forecast_ids=fused_ids,
        calibration_artifact_present=calibration_artifact_present,
        refusal_reasons=refusal_reasons,
        notes=tuple(notes),
    )


__all__ = [
    "ITEM7_STAGE_ORDER",
    "ITEM7_STATUS_COMPLETE_FORBIDDEN",
    "ITEM7_STATUS_PARTIAL",
    "EmpiricalFloorCounters",
    "Item7ProgressionCounts",
    "Item7ProgressionReport",
    "Item7StageVector",
    "build_item7_progression_report",
    "scan_capture_stage_counts",
]
