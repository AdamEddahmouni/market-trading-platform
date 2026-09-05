"""Bridge donor row payloads into causal squeeze intelligence."""

from __future__ import annotations

from typing import Any

from squeeze_core.intelligence.cross_lane import (
    cross_lane_from_dict,
    fuel_history_from_dict,
    horizon_model_from_dict,
)
from squeeze_core.intelligence.contracts import HorizonModelSnapshot
from squeeze_core.intelligence.evaluator import (
    AdamSnapshot,
    CrossLaneSnapshot,
    FuelHistorySnapshot,
    QualitySnapshot,
    RuleSnapshot,
    evaluate_squeeze_intelligence,
    intelligence_result_to_dict,
)
from squeeze_core.intelligence.hysteresis import apply_hysteresis


def _rules_from_detail(detail: dict[str, Any]) -> tuple[RuleSnapshot, ...]:
    rules_raw = detail.get("rules") or detail.get("phase3a", {}).get("rules") or []
    if not isinstance(rules_raw, list):
        return ()
    snapshots: list[RuleSnapshot] = []
    for rule in rules_raw:
        if not isinstance(rule, dict):
            continue
        snapshots.append(
            RuleSnapshot(
                rule_id=str(rule.get("rule_id", "")),
                category=str(rule.get("category", "")),
                outcome=str(rule.get("outcome", "UNKNOWN")),
                reason=str(rule.get("reason", "")),
            )
        )
    return tuple(snapshots)


def _adam_from_row(row: dict[str, Any]) -> AdamSnapshot | None:
    pressure = row.get("pressure")
    ignition = row.get("ignition")
    classification = row.get("adam_classification")
    if pressure is None and ignition is None and not classification:
        return None
    coverage = row.get("methodology_coverage") or row.get("evidence_coverage")
    coverage_label = None
    if isinstance(coverage, dict):
        coverage_label = str(coverage.get("label", "")) or None
    elif isinstance(coverage, str):
        coverage_label = coverage
    return AdamSnapshot(
        pressure=float(pressure) if pressure is not None else None,
        ignition=float(ignition) if ignition is not None else None,
        classification=str(classification or "UNEVALUABLE"),
        coverage_label=coverage_label,
    )


def _quality_from_row(row: dict[str, Any], *, frozen: bool) -> QualitySnapshot:
    stale: list[str] = []
    missing: list[str] = []
    fields = row.get("fields") or {}
    if isinstance(fields, dict):
        for name, cell in fields.items():
            if not isinstance(cell, dict):
                continue
            freshness = str(cell.get("freshness", "")).upper()
            if freshness in ("STALE", "DELAYED") and cell.get("status") == "KNOWN":
                stale.append(name)
            if cell.get("status") != "KNOWN":
                missing.append(name)
    data_quality = row.get("data_quality") or {}
    if isinstance(data_quality, dict):
        for flag in data_quality.get("quality_flags") or []:
            stale.append(str(flag))
    return QualitySnapshot(
        stale_fields=tuple(dict.fromkeys(stale)),
        unavailable_capabilities=tuple(dict.fromkeys(missing)),
        provider_conflicts=bool(row.get("adam_classification") == "CONFLICTED"),
        frozen_snapshot=frozen,
    )


def build_causal_intelligence(
    row: dict[str, Any],
    *,
    rules: tuple[RuleSnapshot, ...] | None = None,
    cross_lane: CrossLaneSnapshot | dict[str, Any] | None = None,
    fuel_history: FuelHistorySnapshot | dict[str, Any] | None = None,
    horizon_model: HorizonModelSnapshot | dict[str, Any] | None = None,
    previous_state: str | None = None,
    state_since: str | None = None,
    apply_state_hysteresis: bool = True,
) -> dict[str, Any]:
    """Project a donor row into causal intelligence JSON."""
    from squeeze_core.intelligence.contracts import SqueezeState

    frozen = str(row.get("freshness", "")).upper() == "FROZEN" or str(
        row.get("mode_label", "")
    ).upper().startswith("FROZEN")
    rule_snapshots = rules if rules is not None else _rules_from_detail(row)
    adam = _adam_from_row(row)
    quality = _quality_from_row(row, frozen=frozen)
    prev = None
    if previous_state:
        try:
            prev = SqueezeState(previous_state)
        except ValueError:
            prev = None
    lane = (
        cross_lane_from_dict(cross_lane)
        if isinstance(cross_lane, dict)
        else (cross_lane or CrossLaneSnapshot())
    )
    history = (
        fuel_history_from_dict(fuel_history)
        if isinstance(fuel_history, dict)
        else (fuel_history or FuelHistorySnapshot())
    )
    model = (
        horizon_model_from_dict(horizon_model)
        if isinstance(horizon_model, dict)
        else horizon_model
    )
    result = evaluate_squeeze_intelligence(
        rules=rule_snapshots,
        adam=adam,
        cross_lane=lane,
        quality=quality,
        previous_state=prev,
        fuel_history=history,
        horizon_model=model,
    )
    payload = intelligence_result_to_dict(result)
    if apply_state_hysteresis and previous_state:
        payload = apply_hysteresis(
            payload,
            previous_state=previous_state,
            state_since=state_since or row.get("causal_state_since"),
        )
    return payload


def finalize_causal_intelligence_for_row(
    row: dict[str, Any],
    *,
    previous_state: str | None,
    state_since: str | None,
    cross_lane: CrossLaneSnapshot | dict[str, Any] | None = None,
    fuel_history: FuelHistorySnapshot | dict[str, Any] | None = None,
    horizon_model: HorizonModelSnapshot | dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    """Evaluate causal intelligence with hysteresis; return (payload, state_changed)."""
    payload = build_causal_intelligence(
        row,
        cross_lane=cross_lane,
        fuel_history=fuel_history,
        horizon_model=horizon_model,
        previous_state=previous_state,
        state_since=state_since,
        apply_state_hysteresis=True,
    )
    changed = bool(previous_state is None or payload.get("state") != previous_state)
    return payload, changed
