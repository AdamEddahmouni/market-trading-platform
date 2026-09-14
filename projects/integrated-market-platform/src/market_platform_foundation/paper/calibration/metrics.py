"""Deterministic IMP vs comparator calibration metrics from paired records.

Reports N, unpaired coverage, distributions, median, and percentiles. A rate
with pair_count=0 is NOT_OBSERVABLE (None), not 0%. Small N is never hidden.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Sequence

from ...execution.simulator import SIMULATOR_VERSION


class CalibrationDivergenceClass(StrEnum):
    WITHIN_TOLERANCE = "WITHIN_TOLERANCE"
    EXPLAINED_DIVERGENCE = "EXPLAINED_DIVERGENCE"
    UNEXPLAINED_DIVERGENCE = "UNEXPLAINED_DIVERGENCE"
    NOT_OBSERVABLE = "NOT_OBSERVABLE"


class SampleHonesty(StrEnum):
    NOT_OBSERVABLE = "NOT_OBSERVABLE"
    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    SAMPLE_MET_NARROW = "SAMPLE_MET_NARROW"
    SAMPLE_MET_DECLARED_SCOPE = "SAMPLE_MET_DECLARED_SCOPE"


@dataclass(frozen=True, slots=True)
class FillObservation:
    order_id: str
    filled: bool
    fill_price: float | None = None
    submit_time_ns: int | None = None
    ack_time_ns: int | None = None
    fill_time_ns: int | None = None
    realized_pnl_minor: int | None = None
    position_qty: int | None = None
    divergence_reason: str | None = None
    correlation_id: str | None = None
    fill_qty: int | None = None
    approved_qty: int | None = None
    fill_count: int | None = None
    rejected: bool = False
    cancelled: bool = False
    paper_account_id: str = ""
    instrument_id: str = ""
    asset_class: str = ""
    commission_minor: int | None = None
    fees_minor: int | None = None

    @classmethod
    def from_mapping(cls, row: Mapping[str, Any]) -> FillObservation:
        return cls(
            order_id=str(row.get("order_id") or ""),
            filled=bool(row.get("filled")),
            fill_price=_optional_float(row.get("fill_price")),
            submit_time_ns=_optional_int(row.get("submit_time_ns")),
            ack_time_ns=_optional_int(row.get("ack_time_ns")),
            fill_time_ns=_optional_int(row.get("fill_time_ns")),
            realized_pnl_minor=_optional_int(row.get("realized_pnl_minor")),
            position_qty=_optional_int(row.get("position_qty")),
            divergence_reason=str(row.get("divergence_reason") or "") or None,
            correlation_id=str(row.get("correlation_id") or "") or None,
            fill_qty=_optional_int(row.get("fill_qty")),
            approved_qty=_optional_int(row.get("approved_qty")),
            fill_count=_optional_int(row.get("fill_count")),
            rejected=bool(row.get("rejected")),
            cancelled=bool(row.get("cancelled")),
            paper_account_id=str(row.get("paper_account_id") or ""),
            instrument_id=str(row.get("instrument_id") or ""),
            asset_class=str(row.get("asset_class") or ""),
            commission_minor=_optional_int(row.get("commission_minor"))
            if "commission_minor" in row
            else None,
            fees_minor=_optional_int(row.get("fees_minor")) if "fees_minor" in row else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "filled": self.filled,
            "fill_price": self.fill_price,
            "submit_time_ns": self.submit_time_ns,
            "ack_time_ns": self.ack_time_ns,
            "fill_time_ns": self.fill_time_ns,
            "realized_pnl_minor": self.realized_pnl_minor,
            "position_qty": self.position_qty,
            "divergence_reason": self.divergence_reason,
            "correlation_id": self.correlation_id,
            "fill_qty": self.fill_qty,
            "approved_qty": self.approved_qty,
            "fill_count": self.fill_count,
            "rejected": self.rejected,
            "cancelled": self.cancelled,
            "paper_account_id": self.paper_account_id,
            "instrument_id": self.instrument_id,
            "asset_class": self.asset_class,
            "commission_minor": self.commission_minor,
            "fees_minor": self.fees_minor,
        }


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _percentile(samples: Sequence[float] | Sequence[int], p: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(float(item) for item in samples)
    index = max(0, int(round((p / 100.0) * (len(ordered) - 1))))
    return ordered[index]


def distribution_summary(samples: Sequence[float] | Sequence[int]) -> dict[str, float | int | None]:
    values = [float(item) for item in samples]
    n = len(values)
    if not values:
        return {
            "n": 0,
            "mean": None,
            "median": None,
            "p50": None,
            "p95": None,
            "min": None,
            "max": None,
        }
    return {
        "n": n,
        "mean": sum(values) / n,
        "median": _percentile(values, 50.0),
        "p50": _percentile(values, 50.0),
        "p95": _percentile(values, 95.0),
        "min": min(values),
        "max": max(values),
    }


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _honesty(*, pair_count: int, minimum_n: int | None) -> SampleHonesty:
    if pair_count <= 0:
        return SampleHonesty.NOT_OBSERVABLE
    if minimum_n is None or pair_count < minimum_n:
        return SampleHonesty.INSUFFICIENT_SAMPLE
    return SampleHonesty.SAMPLE_MET_NARROW


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


@dataclass(frozen=True, slots=True)
class CalibrationMetricReport:
    """Expanded metric dictionary. Never hides small N. Not a calibration pass."""

    pair_count: int
    unpaired_imp_count: int
    unpaired_comparator_count: int
    sample_honesty: SampleHonesty
    simulator_version: str
    fill_disagreement_rate: float | None
    fill_qty_agreement_rate: float | None
    price_error: dict[str, float | int | None]
    slippage_bps: dict[str, float | int | None]
    latency_error_ns: dict[str, float | int | None]
    partial_completion_disagreement_rate: float | None
    reject_disagreement_rate: float | None
    cancel_disagreement_rate: float | None
    pnl_delta_minor: int | None
    position_qty_delta: int | None
    unexplained_divergence_rate: float | None
    divergence_classes: tuple[CalibrationDivergenceClass, ...]
    cost_friction_honesty: SampleHonesty = SampleHonesty.NOT_OBSERVABLE
    cost_friction_delta_minor: int | None = None
    calibrated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_count": self.pair_count,
            "unpaired_imp_count": self.unpaired_imp_count,
            "unpaired_comparator_count": self.unpaired_comparator_count,
            "sample_honesty": self.sample_honesty.value,
            "simulator_version": self.simulator_version,
            "fill_disagreement_rate": self.fill_disagreement_rate,
            "fill_qty_agreement_rate": self.fill_qty_agreement_rate,
            "price_error": dict(self.price_error),
            "slippage_bps": dict(self.slippage_bps),
            "latency_error_ns": dict(self.latency_error_ns),
            "partial_completion_disagreement_rate": self.partial_completion_disagreement_rate,
            "reject_disagreement_rate": self.reject_disagreement_rate,
            "cancel_disagreement_rate": self.cancel_disagreement_rate,
            "pnl_delta_minor": self.pnl_delta_minor,
            "position_qty_delta": self.position_qty_delta,
            "unexplained_divergence_rate": self.unexplained_divergence_rate,
            "divergence_classes": [item.value for item in self.divergence_classes],
            "cost_friction_honesty": self.cost_friction_honesty.value,
            "cost_friction_delta_minor": self.cost_friction_delta_minor,
            "calibrated": False,
        }

    def as_bundle(self) -> CalibrationMetricBundle:
        p95 = self.latency_error_ns.get("p95")
        mean_slippage = self.slippage_bps.get("mean")
        return CalibrationMetricBundle(
            fill_disagreement_rate=self.fill_disagreement_rate,
            mean_slippage_bps=float(mean_slippage) if mean_slippage is not None else None,
            p95_timing_error_ns=int(p95) if p95 is not None else None,
            pnl_delta_minor=self.pnl_delta_minor,
            position_qty_delta=self.position_qty_delta,
            unexplained_divergence_rate=self.unexplained_divergence_rate,
            divergence_classes=self.divergence_classes,
            pair_count=self.pair_count,
        )


def _index_by_order_id(rows: Sequence[FillObservation]) -> dict[str, FillObservation]:
    indexed: dict[str, FillObservation] = {}
    for row in rows:
        key = row.correlation_id or row.order_id
        if key:
            indexed[key] = row
    return indexed


def _as_observations(
    rows: Sequence[FillObservation] | Sequence[Mapping[str, Any]],
) -> list[FillObservation]:
    return [
        item if isinstance(item, FillObservation) else FillObservation.from_mapping(item)
        for item in rows
    ]


def compute_calibration_metric_report(
    *,
    imp_fills: Sequence[FillObservation] | Sequence[Mapping[str, Any]],
    comparator_fills: Sequence[FillObservation] | Sequence[Mapping[str, Any]],
    reference_prices: Mapping[str, float] | None = None,
    unpaired_imp_count: int = 0,
    unpaired_comparator_count: int = 0,
    minimum_n: int | None = None,
    simulator_version: str = SIMULATOR_VERSION,
) -> CalibrationMetricReport:
    imp = _as_observations(imp_fills)
    comp = _as_observations(comparator_fills)
    imp_by_id = _index_by_order_id(imp)
    comp_by_id = _index_by_order_id(comp)
    shared_ids = sorted(set(imp_by_id) & set(comp_by_id))
    empty_dist = distribution_summary(())
    if not shared_ids:
        return CalibrationMetricReport(
            pair_count=0,
            unpaired_imp_count=unpaired_imp_count or len(imp),
            unpaired_comparator_count=unpaired_comparator_count or len(comp),
            sample_honesty=SampleHonesty.NOT_OBSERVABLE,
            simulator_version=simulator_version,
            fill_disagreement_rate=None,
            fill_qty_agreement_rate=None,
            price_error=empty_dist,
            slippage_bps=empty_dist,
            latency_error_ns=empty_dist,
            partial_completion_disagreement_rate=None,
            reject_disagreement_rate=None,
            cancel_disagreement_rate=None,
            pnl_delta_minor=None,
            position_qty_delta=None,
            unexplained_divergence_rate=None,
            divergence_classes=(CalibrationDivergenceClass.NOT_OBSERVABLE,),
            cost_friction_honesty=SampleHonesty.NOT_OBSERVABLE,
            cost_friction_delta_minor=None,
            calibrated=False,
        )

    disagreements = 0
    qty_agreements = 0
    qty_compared = 0
    slippage_samples: list[float] = []
    price_errors: list[float] = []
    timing_errors: list[int] = []
    partial_disagreements = 0
    partial_compared = 0
    reject_disagreements = 0
    cancel_disagreements = 0
    pnl_delta = 0
    pnl_compared = 0
    position_delta = 0
    position_compared = 0
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

        if imp_row.fill_qty is not None and comp_row.fill_qty is not None:
            qty_compared += 1
            if imp_row.fill_qty == comp_row.fill_qty:
                qty_agreements += 1

        if imp_row.filled and comp_row.filled:
            if imp_row.fill_price is not None and comp_row.fill_price is not None:
                price_errors.append(imp_row.fill_price - comp_row.fill_price)
                ref = refs.get(order_id) or comp_row.fill_price
                if ref:
                    slippage_samples.append(
                        abs(imp_row.fill_price - comp_row.fill_price) / ref * 10_000.0
                    )

        latency_imp = imp_row.ack_time_ns
        latency_comp = comp_row.ack_time_ns
        if latency_imp is not None and latency_comp is not None:
            timing_errors.append(abs(latency_imp - latency_comp))

        imp_ratio = _completion_ratio(imp_row)
        comp_ratio = _completion_ratio(comp_row)
        if imp_ratio is not None and comp_ratio is not None:
            partial_compared += 1
            if imp_ratio != comp_ratio:
                partial_disagreements += 1

        if imp_row.rejected != comp_row.rejected:
            reject_disagreements += 1
        if imp_row.cancelled != comp_row.cancelled:
            cancel_disagreements += 1

        if imp_row.realized_pnl_minor is not None and comp_row.realized_pnl_minor is not None:
            pnl_delta += imp_row.realized_pnl_minor - comp_row.realized_pnl_minor
            pnl_compared += 1
        if imp_row.position_qty is not None and comp_row.position_qty is not None:
            position_delta += imp_row.position_qty - comp_row.position_qty
            position_compared += 1

    pair_count = len(shared_ids)
    cost_observable = True
    cost_delta = 0
    for order_id in shared_ids:
        imp_row = imp_by_id[order_id]
        comp_row = comp_by_id[order_id]
        if (
            imp_row.commission_minor is None
            or imp_row.fees_minor is None
            or comp_row.commission_minor is None
            or comp_row.fees_minor is None
        ):
            cost_observable = False
            break
        cost_delta += (imp_row.commission_minor + imp_row.fees_minor) - (
            comp_row.commission_minor + comp_row.fees_minor
        )
    return CalibrationMetricReport(
        pair_count=pair_count,
        unpaired_imp_count=unpaired_imp_count,
        unpaired_comparator_count=unpaired_comparator_count,
        sample_honesty=_honesty(pair_count=pair_count, minimum_n=minimum_n),
        simulator_version=simulator_version,
        fill_disagreement_rate=_rate(disagreements, pair_count),
        fill_qty_agreement_rate=_rate(qty_agreements, qty_compared),
        price_error=distribution_summary(price_errors),
        slippage_bps=distribution_summary(slippage_samples),
        latency_error_ns=distribution_summary(timing_errors),
        partial_completion_disagreement_rate=_rate(partial_disagreements, partial_compared),
        reject_disagreement_rate=_rate(reject_disagreements, pair_count),
        cancel_disagreement_rate=_rate(cancel_disagreements, pair_count),
        pnl_delta_minor=pnl_delta if pnl_compared else None,
        position_qty_delta=position_delta if position_compared else None,
        unexplained_divergence_rate=_rate(unexplained, pair_count),
        divergence_classes=tuple(classes),
        cost_friction_honesty=(
            _honesty(pair_count=pair_count, minimum_n=minimum_n)
            if cost_observable
            else SampleHonesty.NOT_OBSERVABLE
        ),
        cost_friction_delta_minor=cost_delta if cost_observable else None,
        calibrated=False,
    )


def _completion_ratio(row: FillObservation) -> float | None:
    if row.approved_qty is None or row.approved_qty <= 0:
        return None
    filled = row.fill_qty if row.fill_qty is not None else (row.approved_qty if row.filled else 0)
    return filled / row.approved_qty


def compute_calibration_metrics(
    *,
    imp_fills: Sequence[FillObservation] | Sequence[Mapping[str, Any]],
    comparator_fills: Sequence[FillObservation] | Sequence[Mapping[str, Any]],
    reference_prices: Mapping[str, float] | None = None,
) -> CalibrationMetricBundle:
    report = compute_calibration_metric_report(
        imp_fills=imp_fills,
        comparator_fills=comparator_fills,
        reference_prices=reference_prices,
    )
    return report.as_bundle()


__all__ = [
    "CalibrationDivergenceClass",
    "CalibrationMetricBundle",
    "CalibrationMetricReport",
    "FillObservation",
    "SampleHonesty",
    "compute_calibration_metric_report",
    "compute_calibration_metrics",
    "distribution_summary",
]
