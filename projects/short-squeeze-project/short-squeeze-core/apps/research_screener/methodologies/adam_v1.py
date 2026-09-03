from __future__ import annotations

from collections.abc import Callable

from .enums import Classification, CoverageCategory
from .evidence import EvidenceInput
from .models import MethodologyResult
from .normalization import inverse_linear, linear

ADAM_POLICY_ID = "adam_evidence_gated_prime.v1"
ADAM_LABEL = "ADAM EVIDENCE-GATED PRIME v1"
MIN_DIMENSION_WEIGHT = 65

PRESSURE: dict[str, tuple[int, Callable[[float], float]]] = {
    "published_short_interest_pct": (30, lambda x: linear(x, 5, 30)),
    "days_to_cover": (25, lambda x: linear(x, 1, 7)),
    "cost_to_borrow": (20, lambda x: linear(x, 2, 50)),
    "borrow_availability_pct_float": (15, lambda x: inverse_linear(x, 0.1, 10)),
    "float_shares": (10, lambda x: inverse_linear(x, 10_000_000, 50_000_000)),
}
IGNITION: dict[str, tuple[int, Callable[[float], float]]] = {
    "current_percentage_change": (35, lambda x: linear(x, 0, 20)),
    "relative_volume": (30, lambda x: linear(x, 1, 10)),
    "completed_bar_acceleration": (20, lambda x: linear(x, 0, 5)),
    "catalyst_age_hours": (15, lambda x: 100.0 if x <= 24 else 50.0 if x <= 72 else 0.0),
}
UNITS = {
    "published_short_interest_pct": "PERCENT",
    "days_to_cover": "DAYS",
    "cost_to_borrow": "PERCENT_ANNUALIZED",
    "borrow_availability_pct_float": "PERCENT_OF_FLOAT",
    "float_shares": "SHARES",
    "current_percentage_change": "PERCENT",
    "relative_volume": "RATIO",
    "completed_bar_acceleration": "PERCENTAGE_POINTS",
    "catalyst_age_hours": "HOURS",
}


def _eligible(item: EvidenceInput | None, key: str) -> bool:
    return bool(item and item.eligible_for(UNITS[key]))


def _dimension(
    policy: dict[str, tuple[int, Callable[[float], float]]],
    inputs: dict[str, EvidenceInput],
    *,
    critical: bool,
) -> tuple[float | None, int, list[dict], list[str], list[str]]:
    contribution = 0.0
    supported_weight = 0
    components: list[dict] = []
    missing: list[str] = []
    display_only: list[str] = []
    for key, (weight, normalize) in policy.items():
        item = inputs.get(key)
        if not _eligible(item, key):
            missing.append(key)
            if item is not None and item.display_available:
                display_only.append(key)
            components.append({
                "component": key, "weight": weight, "normalized": None,
                "eligible": False, "evidence": None if item is None else item.as_dict(),
            })
            continue
        normalized = normalize(float(item.value))
        supported_weight += weight
        contribution += weight * normalized
        components.append({
            "component": key, "weight": weight, "normalized": normalized,
            "eligible": True, "evidence": item.as_dict(),
        })
    score = None
    if supported_weight >= MIN_DIMENSION_WEIGHT and critical:
        score = round(contribution / supported_weight, 1)
    return score, supported_weight, components, missing, display_only


def evaluate_adam(inputs: dict[str, EvidenceInput], *, as_of: str | None = None) -> MethodologyResult:
    conflicts = tuple(
        f"material conflict in {key}" for key, item in inputs.items() if item.conflict
    )
    pressure_critical = bool(
        inputs.get("published_short_interest_pct")
        and _eligible(inputs["published_short_interest_pct"], "published_short_interest_pct")
        and any(
            _eligible(inputs.get(key), key)
            for key in (
                "days_to_cover",
                "cost_to_borrow",
                "borrow_availability_pct_float",
                "float_shares",
            )
        )
    )
    ignition_critical = bool(
        inputs.get("current_percentage_change")
        and _eligible(inputs["current_percentage_change"], "current_percentage_change")
        and inputs.get("relative_volume")
        and _eligible(inputs["relative_volume"], "relative_volume")
    )
    pressure, pw, pc, pm, pd = _dimension(
        PRESSURE, inputs, critical=pressure_critical
    )
    ignition, iw, ic, im, idisplay = _dimension(
        IGNITION, inputs, critical=ignition_critical
    )
    weight_coverage_pct = round((pw + iw) / 2.0, 4)
    if conflicts:
        coverage = CoverageCategory.CONFLICTED
    elif not (pressure_critical and ignition_critical):
        coverage = CoverageCategory.INSUFFICIENT
    elif weight_coverage_pct >= 85 and pressure is not None and ignition is not None:
        coverage = CoverageCategory.HIGH
    elif weight_coverage_pct >= 70 and pressure is not None and ignition is not None:
        coverage = CoverageCategory.MODERATE
    elif weight_coverage_pct >= 50:
        coverage = CoverageCategory.LOW
    else:
        coverage = CoverageCategory.INSUFFICIENT

    # LOW_COVERAGE still yields a classification when both dimensions scored at
    # the Finviz floor (MIN_DIMENSION_WEIGHT=65). UNEVALUABLE is reserved for
    # insufficient/conflicted evidence or a missing dimension score.
    if conflicts:
        classification = Classification.CONFLICTED
    elif coverage is CoverageCategory.INSUFFICIENT or pressure is None or ignition is None:
        classification = Classification.UNEVALUABLE
    elif pressure >= 70 and ignition >= 70 and coverage is CoverageCategory.HIGH:
        classification = Classification.PRIME
    elif ((pressure >= 70 and ignition >= 50) or (ignition >= 70 and pressure >= 50)):
        classification = Classification.SUBPRIME
    elif pressure >= 50 or ignition >= 50:
        classification = Classification.WATCH
    else:
        classification = Classification.NOT_QUALIFIED

    used = tuple(
        key for key in (*PRESSURE, *IGNITION) if _eligible(inputs.get(key), key)
    )
    missing = tuple(dict.fromkeys([*pm, *im]))
    total_fields_required = len(PRESSURE) + len(IGNITION)
    total_fields_available = len(used)
    field_coverage_percent = (
        None
        if total_fields_required <= 0
        else round(100.0 * total_fields_available / total_fields_required, 1)
    )
    return MethodologyResult(
        methodology_id=ADAM_POLICY_ID,
        methodology_version="1.0.0",
        methodology_label=ADAM_LABEL,
        classification=str(classification),
        evaluable=classification not in (Classification.UNEVALUABLE, Classification.CONFLICTED),
        pressure=pressure,
        ignition=ignition,
        evidence_coverage={
            "category": str(coverage),
            "percent": field_coverage_percent,
            "field_coverage_percent": field_coverage_percent,
            "weight_coverage_percent": weight_coverage_pct,
            "pressure_fields_available": len(PRESSURE) - len(pm),
            "pressure_fields_required": len(PRESSURE),
            "ignition_fields_available": len(IGNITION) - len(im),
            "ignition_fields_required": len(IGNITION),
            "total_fields_available": total_fields_available,
            "total_fields_required": total_fields_required,
            "critical_domains_present": pressure_critical and ignition_critical,
            "provider_conflicts": bool(conflicts),
        },
        known_inputs=used,
        missing_inputs=missing,
        supporting_evidence=tuple(inputs[key].as_dict() for key in used),
        blocking_reasons=tuple(
            [
                *([] if pressure_critical else ["Pressure critical domains are incomplete"]),
                *([] if ignition_critical else ["Ignition critical domains are incomplete"]),
                *(
                    []
                    if pw >= MIN_DIMENSION_WEIGHT
                    else [f"Pressure supported weight {pw}% is below {MIN_DIMENSION_WEIGHT}%"]
                ),
                *(
                    []
                    if iw >= MIN_DIMENSION_WEIGHT
                    else [f"Ignition supported weight {iw}% is below {MIN_DIMENSION_WEIGHT}%"]
                ),
            ]
        ),
        conflict_reasons=conflicts,
        as_of=as_of,
        metadata={
            "pressure_supported_weight": pw,
            "ignition_supported_weight": iw,
            "pressure_components": pc,
            "ignition_components": ic,
            "display_only_inputs": sorted(set(pd + idisplay)),
            "weights_validated": False,
            "thresholds_optimal": False,
        },
    )
