"""Parse normalized cross-lane evidence into evaluator snapshots."""

from __future__ import annotations

from typing import Any

from .contracts import HorizonModelSnapshot, MagnitudeEstimateSnapshot
from .evaluator import CrossLaneSnapshot, FuelHistorySnapshot


def cross_lane_from_dict(payload: dict[str, Any] | None) -> CrossLaneSnapshot:
    if not payload:
        return CrossLaneSnapshot()
    return CrossLaneSnapshot(
        order_flow_cvd_slope=_optional_float(payload.get("order_flow_cvd_slope")),
        order_flow_aggressive_buy=_optional_bool(payload.get("order_flow_aggressive_buy")),
        order_flow_aggressive_sell=_optional_bool(payload.get("order_flow_aggressive_sell")),
        order_flow_available=bool(payload.get("order_flow_available")),
        options_call_demand_anomaly=_optional_bool(payload.get("options_call_demand_anomaly")),
        options_gamma_amplification=_optional_bool(payload.get("options_gamma_amplification")),
        options_hedging_pressure=_optional_float(payload.get("options_hedging_pressure")),
        options_flow_reversal=_optional_bool(payload.get("options_flow_reversal")),
        options_gamma_decay=_optional_bool(payload.get("options_gamma_decay")),
        options_available=bool(payload.get("options_available")),
        borrow_normalization_score=_optional_float(payload.get("borrow_normalization_score")),
        attention_acceleration=_optional_float(payload.get("attention_acceleration")),
        attention_available=bool(payload.get("attention_available")),
        catalyst_strength=_optional_float(payload.get("catalyst_strength")),
        catalyst_available=bool(payload.get("catalyst_available")),
        thesis_invalidation_score=_optional_float(payload.get("thesis_invalidation_score")),
        lending_fee_rate=_optional_float(payload.get("lending_fee_rate")),
        lending_shares_available=_optional_int(payload.get("lending_shares_available")),
        lending_utilization_rate=_optional_float(payload.get("lending_utilization_rate")),
        lending_shares_on_loan=_optional_int(payload.get("lending_shares_on_loan")),
        lending_available=bool(payload.get("lending_available")),
        borrow_utilization_velocity=_optional_float(payload.get("borrow_utilization_velocity")),
    )


def fuel_history_from_dict(payload: dict[str, Any] | None) -> FuelHistorySnapshot:
    if not payload:
        return FuelHistorySnapshot()
    return FuelHistorySnapshot(
        previous_remaining_fuel=_optional_float(payload.get("previous_remaining_fuel")),
        previous_cvd_slope=_optional_float(payload.get("previous_cvd_slope")),
        previous_reflexivity=_optional_float(payload.get("previous_reflexivity")),
    )


def cross_lane_snapshot_to_dict(snapshot: CrossLaneSnapshot) -> dict[str, Any]:
    return {
        "order_flow_cvd_slope": snapshot.order_flow_cvd_slope,
        "order_flow_aggressive_buy": snapshot.order_flow_aggressive_buy,
        "order_flow_aggressive_sell": snapshot.order_flow_aggressive_sell,
        "order_flow_available": snapshot.order_flow_available,
        "options_call_demand_anomaly": snapshot.options_call_demand_anomaly,
        "options_gamma_amplification": snapshot.options_gamma_amplification,
        "options_hedging_pressure": snapshot.options_hedging_pressure,
        "options_flow_reversal": snapshot.options_flow_reversal,
        "options_gamma_decay": snapshot.options_gamma_decay,
        "options_available": snapshot.options_available,
        "borrow_normalization_score": snapshot.borrow_normalization_score,
        "attention_acceleration": snapshot.attention_acceleration,
        "attention_available": snapshot.attention_available,
        "catalyst_strength": snapshot.catalyst_strength,
        "catalyst_available": snapshot.catalyst_available,
        "thesis_invalidation_score": snapshot.thesis_invalidation_score,
        "lending_fee_rate": snapshot.lending_fee_rate,
        "lending_shares_available": snapshot.lending_shares_available,
        "lending_utilization_rate": snapshot.lending_utilization_rate,
        "lending_shares_on_loan": snapshot.lending_shares_on_loan,
        "lending_available": snapshot.lending_available,
        "borrow_utilization_velocity": snapshot.borrow_utilization_velocity,
    }


def fuel_history_to_dict(history: FuelHistorySnapshot) -> dict[str, Any]:
    return {
        "previous_remaining_fuel": history.previous_remaining_fuel,
        "previous_cvd_slope": history.previous_cvd_slope,
        "previous_reflexivity": history.previous_reflexivity,
    }


def horizon_model_from_dict(payload: dict[str, Any] | None) -> HorizonModelSnapshot | None:
    if not payload:
        return None
    magnitude_payload = payload.get("magnitude")
    magnitude = None
    if isinstance(magnitude_payload, dict):
        magnitude = MagnitudeEstimateSnapshot(
            expected_move_pct=_optional_float(magnitude_payload.get("expected_move_pct")),
            upside_tail_pct=_optional_float(magnitude_payload.get("upside_tail_pct")),
            status=str(magnitude_payload.get("status", "UNAVAILABLE")),
            method=str(magnitude_payload.get("method", "")),
            model_version=str(magnitude_payload.get("model_version", "")),
        )
    hazard_raw = payload.get("hazard_by_horizon")
    hazard_by_horizon: tuple[tuple[int, float], ...] = ()
    if isinstance(hazard_raw, dict):
        hazard_by_horizon = tuple(
            (int(days), float(value))
            for days, value in sorted(hazard_raw.items(), key=lambda row: int(row[0]))
            if value is not None
        )
    elif isinstance(hazard_raw, list):
        parsed: list[tuple[int, float]] = []
        for item in hazard_raw:
            if isinstance(item, dict) and item.get("horizon_days") is not None:
                value = item.get("value")
                if value is not None:
                    parsed.append((int(item["horizon_days"]), float(value)))
        hazard_by_horizon = tuple(parsed)
    return HorizonModelSnapshot(
        model_version=str(payload.get("model_version", "")),
        status=str(payload.get("status", "RESEARCH_ONLY")),
        pit_verified=bool(payload.get("pit_verified")),
        occurrence_probability=_optional_float(payload.get("occurrence_probability")),
        hazard_by_horizon=hazard_by_horizon,
        magnitude=magnitude,
    )


def horizon_model_to_dict(snapshot: HorizonModelSnapshot) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model_version": snapshot.model_version,
        "status": snapshot.status,
        "pit_verified": snapshot.pit_verified,
        "occurrence_probability": snapshot.occurrence_probability,
        "hazard_by_horizon": {
            str(days): value for days, value in snapshot.hazard_by_horizon
        },
    }
    if snapshot.magnitude is not None:
        payload["magnitude"] = {
            "expected_move_pct": snapshot.magnitude.expected_move_pct,
            "upside_tail_pct": snapshot.magnitude.upside_tail_pct,
            "status": snapshot.magnitude.status,
            "method": snapshot.magnitude.method,
            "model_version": snapshot.magnitude.model_version,
        }
    return payload


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
