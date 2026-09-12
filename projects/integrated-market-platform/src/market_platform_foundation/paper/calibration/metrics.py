"""Deterministic IMP vs comparator calibration metrics from paired fixture records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence


class CalibrationDivergenceClass(StrEnum):
    WITHIN_TOLERANCE = "WITHIN_TOLERANCE"
    EXPLAINED_DIVERGENCE = "EXPLAINED_DIVERGENCE"
    UNEXPLAINED_DIVERGENCE = "UNEXPLAINED_DIVERGENCE"
    NOT_OBSERVABLE = "NOT_OBSERVABLE"


@dataclass(frozen=True, slots=True)
class FillObservation:
    order_id: str
    filled: bool
    fill_price: float | None = None
    submit_time_ns: int | None = None
    ack_time_ns: int | None = None
    realized_pnl_minor: int | None = None
    position_qty: int | None = None
    divergence_reason: str | None = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> FillObservation:
        return cls(
            order_id=str(row.get("order_id") or ""),
            filled=bool(row.get("filled")),
            fill_price=_optional_float(row.get("fill_price")),
            submit_time_ns=_optional_int(row.get("submit_time_ns")),
            ack_time_ns=_optional_int(row.get("ack_time_ns")),
            realized_pnl_minor=_optional_int(row.get("realized_pnl_minor")),
            position_qty=_optional_int(row.get("position_qty")),
            divergence_reason=str(row.get("divergence_reason") or "") or None,
        )


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


@dataclass(frozen=True, slots=True)
class CalibrationMetricBundle:
    fill_disagreement_rate: float | None
    mean_slippage_bps: float | None
    p95_timing_error_ns: int | None
    pnl_delta_minor: int | None
    position_qty_delta: int | None
    unexplained_divergence_rate: float | None
    divergence_classes: tuple[CalibrationDivergenceClass, ...]
    pair_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "fill_disagreement_rate": self.fill_disagreement_rate,
            "mean_slippage_bps": self.mean_slippage_bps,
            "p95_timing_error_ns": self.p95_timing_error_ns,
            "pnl_delta_minor": self.pnl_delta_minor,
            "position_qty_delta": self.position_qty_delta,
            "unexplained_divergence_rate": self.unexplained_divergence_rate,
            "divergence_classes": [item.value for item in self.divergence_classes],
            "pair_count": self.pair_count,
        }


def _index_by_order_id(rows: Sequence[FillObservation]) -> dict[str, FillObservation]:
    indexed: dict[str, FillObservation] = {}
    for row in rows:
        if row.order_id:
            indexed[row.order_id] = row
    return indexed


def compute_calibration_metrics(
    *,
    imp_fills: Sequence[FillObservation] | Sequence[Mapping[str, Any]],
    comparator_fills: Sequence[FillObservation] | Sequence[Mapping[str, Any]],
    reference_prices: Mapping[str, float] | None = None,
) -> CalibrationMetricBundle:
    imp = [
        item if isinstance(item, FillObservation) else FillObservation.from_mapping(item)
        for item in imp_fills
    ]
    comp = [
        item if isinstance(item, FillObservation) else FillObservation.from_mapping(item)
        for item in comparator_fills
    ]
    imp_by_id = _index_by_order_id(imp)
    comp_by_id = _index_by_order_id(comp)
    shared_ids = sorted(set(imp_by_id) & set(comp_by_id))
    if not shared_ids:
        return CalibrationMetricBundle(
            fill_disagreement_rate=None,
            mean_slippage_bps=None,
            p95_timing_error_ns=None,
            pnl_delta_minor=None,
            position_qty_delta=None,
            unexplained_divergence_rate=None,
            divergence_classes=(CalibrationDivergenceClass.NOT_OBSERVABLE,),
            pair_count=0,
        )

    disagreements = 0
    slippage_samples: list[float] = []
    timing_errors: list[int] = []
    pnl_delta = 0
    position_delta = 0
    unexplained = 0
    classes: list[CalibrationDivergenceClass] = []
    refs = dict(reference_prices or {})

    for order_id in shared_ids:
        imp_row = imp_by_id[order_id]
        comp_row = comp_by_id[order_id]
        if imp_row.filled != comp_row.filled:
            disagreements += 1
            if imp_row.divergence_reason or comp_row.divergence_reason:
                classes.append(CalibrationDivergenceClass.EXPLAINED_DIVERGENCE)
            else:
                unexplained += 1
                classes.append(CalibrationDivergenceClass.UNEXPLAINED_DIVERGENCE)
        else:
            classes.append(CalibrationDivergenceClass.WITHIN_TOLERANCE)

        if imp_row.filled and comp_row.filled:
            if imp_row.fill_price is not None and comp_row.fill_price is not None:
                ref = refs.get(order_id) or comp_row.fill_price
                if ref:
                    slippage_samples.append(
                        abs(imp_row.fill_price - comp_row.fill_price) / ref * 10_000.0
                    )
        if imp_row.ack_time_ns is not None and comp_row.ack_time_ns is not None:
            timing_errors.append(abs(imp_row.ack_time_ns - comp_row.ack_time_ns))

        if imp_row.realized_pnl_minor is not None and comp_row.realized_pnl_minor is not None:
            pnl_delta += imp_row.realized_pnl_minor - comp_row.realized_pnl_minor
        if imp_row.position_qty is not None and comp_row.position_qty is not None:
            position_delta += imp_row.position_qty - comp_row.position_qty

    pair_count = len(shared_ids)
    fill_rate = disagreements / pair_count if pair_count else None
    mean_slippage = (
        sum(slippage_samples) / len(slippage_samples) if slippage_samples else None
    )
    p95_timing = None
    if timing_errors:
        ordered = sorted(timing_errors)
        index = max(0, int(round(0.95 * (len(ordered) - 1))))
        p95_timing = ordered[index]
    unexplained_rate = unexplained / pair_count if pair_count else None

    return CalibrationMetricBundle(
        fill_disagreement_rate=fill_rate,
        mean_slippage_bps=mean_slippage,
        p95_timing_error_ns=p95_timing,
        pnl_delta_minor=pnl_delta,
        position_qty_delta=position_delta,
        unexplained_divergence_rate=unexplained_rate,
        divergence_classes=tuple(classes),
        pair_count=pair_count,
    )


__all__ = [
    "CalibrationDivergenceClass",
    "CalibrationMetricBundle",
    "FillObservation",
    "compute_calibration_metrics",
]
