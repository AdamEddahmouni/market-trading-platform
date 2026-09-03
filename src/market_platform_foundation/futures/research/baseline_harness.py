"""Walk-forward harness for Futures F11 baseline gates."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ...research.distribution.ewma import ewma_volatility_forecast
from ...research.walk_forward import build_walk_forward_folds, verify_fold_pit
from ..advanced_baseline import (
    compute_family_engineered_baseline,
    compute_trend_only_baseline,
)
from ..advanced_features import build_futures_feature_vector
from ..baselines import (
    MIN_BARS_FOR_BASELINES,
    _bar_close,
    _bar_event_time,
    compute_trend_features,
)
from ..positioning import crowding_regime, filter_pit_reports
from .gates import evaluate_f11_s1_gate, evaluate_fq8_gate

_REPO_ROOT = Path(__file__).resolve().parents[4]
_FIXTURE_ROOT = _REPO_ROOT / "tests" / "fixtures"

DEFAULT_ES_F11_BASELINE_FIXTURE = _FIXTURE_ROOT / "futures" / "es_f11_baseline_slice.json"
DEFAULT_ES_F11_COT_UPGRADE_FIXTURE = _FIXTURE_ROOT / "futures" / "es_f11_cot_upgrade_slice.json"
DEFAULT_CL_F11_BASELINE_FIXTURE = _FIXTURE_ROOT / "futures" / "cl_f11_baseline_slice.json"
DEFAULT_CL_F11_COT_UPGRADE_FIXTURE = _FIXTURE_ROOT / "futures" / "cl_f11_cot_upgrade_slice.json"

AGGREGATE_RULE = (
    "aggregate_status is PASS only when every gate_summary entry has gate_status PASS"
)
MACRO_WINDOW_HOURS = 48


def _load_fixture_dict(path: Path, *, error_code: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(error_code)
    return payload


def _resolve_path(relative_or_absolute: str | Path) -> Path:
    path = Path(relative_or_absolute)
    if path.is_absolute():
        return path
    return _REPO_ROOT / path


def _parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def load_es_f11_baseline_dataset(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_ES_F11_BASELINE_FIXTURE
    return _load_fixture_dict(fixture_path, error_code="ES_F11_BASELINE_FIXTURE_INVALID")


def load_es_f11_cot_upgrade_dataset(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_ES_F11_COT_UPGRADE_FIXTURE
    return _load_fixture_dict(fixture_path, error_code="ES_F11_COT_UPGRADE_FIXTURE_INVALID")


def load_cl_f11_baseline_dataset(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_CL_F11_BASELINE_FIXTURE
    return _load_fixture_dict(fixture_path, error_code="CL_F11_BASELINE_FIXTURE_INVALID")


def load_cl_f11_cot_upgrade_dataset(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_CL_F11_COT_UPGRADE_FIXTURE
    return _load_fixture_dict(fixture_path, error_code="CL_F11_COT_UPGRADE_FIXTURE_INVALID")


def _load_nested(manifest: dict[str, Any], key: str) -> dict[str, Any]:
    rel = manifest.get(key)
    if not rel:
        return {}
    return _load_fixture_dict(_resolve_path(str(rel)), error_code=f"{key.upper()}_INVALID")


def _pit_history_rows(
    rows: list[dict[str, Any]],
    decision_time: str,
    time_keys: tuple[str, ...] = ("observation_time", "event_time", "available_time"),
) -> list[dict[str, Any]]:
    decision_dt = _parse_dt(decision_time)
    eligible: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        stamp = ""
        for key in time_keys:
            if row.get(key):
                stamp = str(row[key])
                break
        row_dt = _parse_dt(stamp)
        if decision_dt is not None and row_dt is not None and row_dt > decision_dt:
            continue
        eligible.append(row)
    return eligible


def _cot_features(reports: list[dict[str, Any]], decision_time: str) -> tuple[bool, float | None, str | None]:
    pit_reports, _flags = filter_pit_reports(reports, decision_time)
    if not pit_reports:
        return False, None, None
    latest = pit_reports[-1]
    history_nets: list[int] = []
    for report in pit_reports:
        net = report.get("net")
        if net is None:
            continue
        history_nets.append(int(net))
    current_net = latest.get("net")
    if current_net is None or not history_nets:
        return False, None, None
    sorted_nets = sorted(history_nets)
    rank = sum(1 for value in sorted_nets if value <= int(current_net))
    percentile = rank / len(sorted_nets)
    return True, percentile, crowding_regime(percentile).value


def _latest_numeric(
    rows: list[dict[str, Any]],
    field: str,
    decision_time: str,
) -> float | None:
    eligible = _pit_history_rows(rows, decision_time)
    for row in reversed(eligible):
        value = row.get(field)
        if value is not None:
            return float(value)
    return None


def _event_window_active(events: list[dict[str, Any]], decision_time: str) -> bool:
    decision_dt = _parse_dt(decision_time)
    if decision_dt is None:
        return False
    horizon = decision_dt + timedelta(hours=MACRO_WINDOW_HOURS)
    for event in events:
        if not isinstance(event, dict):
            continue
        scheduled = _parse_dt(str(event.get("scheduled_time") or ""))
        if scheduled is None:
            continue
        if decision_dt <= scheduled <= horizon:
            return True
    return False


def _stress_from_margin(history: list[dict[str, Any]], decision_time: str) -> float | None:
    eligible = _pit_history_rows(history, decision_time, ("available_time", "observation_time"))
    if not eligible:
        return None
    latest = eligible[-1]
    change = latest.get("margin_change_pct")
    if change is None:
        return 0.2
    return min(max(abs(float(change)) / 10.0, 0.0), 1.0)


def _observation_context(
    bars: list[dict[str, Any]],
    index: int,
    *,
    cot_reports: list[dict[str, Any]],
    carry_history: list[dict[str, Any]],
    slope_history: list[dict[str, Any]],
    margin_history: list[dict[str, Any]],
    macro_events: list[dict[str, Any]],
    instrument_family: str,
) -> dict[str, Any] | None:
    if index < MIN_BARS_FOR_BASELINES or index >= len(bars) - 1:
        return None
    current = bars[index]
    nxt = bars[index + 1]
    current_close = _bar_close(current)
    next_close = _bar_close(nxt)
    if current_close is None or next_close is None:
        return None
    decision_time = _bar_event_time(current)
    history = bars[: index + 1]
    closes = [value for value in (_bar_close(bar) for bar in history) if value is not None]
    vol = ewma_volatility_forecast(closes)
    features, _used = compute_trend_features(closes, vol)
    cot_ok, percentile, crowding = _cot_features(cot_reports, decision_time)
    annualized_carry = _latest_numeric(carry_history, "annualized_carry", decision_time)
    curve_slope = _latest_numeric(slope_history, "slope", decision_time)
    prior_slopes = _pit_history_rows(slope_history, decision_time)
    curve_slope_change = None
    if len(prior_slopes) >= 2:
        prev = prior_slopes[-2].get("slope")
        curr = prior_slopes[-1].get("slope")
        if prev is not None and curr is not None:
            curve_slope_change = float(curr) - float(prev)
    return {
        "observation_index": index,
        "decision_time": decision_time,
        "instrument_family": instrument_family,
        "trend_3m": features.get("trend_3m"),
        "annualized_carry": annualized_carry,
        "curve_slope": curve_slope,
        "curve_slope_change": curve_slope_change,
        "net_percentile": percentile,
        "crowding_regime": crowding,
        "stress_score": _stress_from_margin(margin_history, decision_time),
        "event_window_active": _event_window_active(macro_events, decision_time),
        "cot_available": cot_ok,
        "outright_up": next_close > current_close,
        "curve_steepen": bool(curve_slope_change is not None and curve_slope_change > 0),
    }


def _vector_from_context(context: dict[str, Any], *, omit_cot: bool = False) -> Any:
    return build_futures_feature_vector(
        instrument_family=str(context.get("instrument_family", "ES")),
        trend_3m=context.get("trend_3m"),
        annualized_carry=context.get("annualized_carry"),
        curve_slope=context.get("curve_slope"),
        curve_slope_change=context.get("curve_slope_change"),
        net_percentile=None if omit_cot else context.get("net_percentile"),
        crowding_regime=None if omit_cot else context.get("crowding_regime"),
        stress_score=context.get("stress_score"),
        event_window_active=bool(context.get("event_window_active")),
        cot_available=False if omit_cot else bool(context.get("cot_available")),
    )


def run_f11_baseline_walk_forward_harness(
    dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = dataset or load_es_f11_baseline_dataset()
    bars_payload = _load_nested(manifest, "bars_relative_path")
    cot_payload = _load_nested(manifest, "cot_relative_path")
    macro_payload = _load_nested(manifest, "macro_relative_path")
    margin_payload = _load_nested(manifest, "margin_relative_path")

    bars = [row for row in bars_payload.get("bars", []) if isinstance(row, dict)]
    if len(bars) < MIN_BARS_FOR_BASELINES + 2:
        return {
            "available": False,
            "reason": "INSUFFICIENT_BARS",
            "gate_milestones": ["F11-S1"],
        }

    cot_reports = [row for row in cot_payload.get("reports", []) if isinstance(row, dict)]
    carry_history = [row for row in bars_payload.get("carry_history", []) if isinstance(row, dict)]
    slope_history = [row for row in bars_payload.get("curve_slope_history", []) if isinstance(row, dict)]
    margin_history = [
        row for row in margin_payload.get("margin_history", []) if isinstance(row, dict)
    ]
    macro_events = [row for row in macro_payload.get("events", []) if isinstance(row, dict)]
    instrument_family = str(manifest.get("instrument_family") or bars_payload.get("symbol") or "ES")

    contexts: list[dict[str, Any]] = []
    for index in range(len(bars)):
        context = _observation_context(
            bars,
            index,
            cot_reports=cot_reports,
            carry_history=carry_history,
            slope_history=slope_history,
            margin_history=margin_history,
            macro_events=macro_events,
            instrument_family=instrument_family,
        )
        if context is not None:
            contexts.append(context)

    if len(contexts) < 3:
        return {
            "available": False,
            "reason": "INSUFFICIENT_LABELED_OBSERVATIONS",
            "gate_milestones": ["F11-S1"],
        }

    obs_times = [int(row["observation_index"]) for row in contexts]
    folds = build_walk_forward_folds(obs_times, min_train=2, test_size=1)
    pit_rows = [{"observation_time": index, "prediction_cutoff": index} for index in obs_times]
    pit_status, pit_reasons = verify_fold_pit(folds, pit_rows)
    context_by_index = {int(row["observation_index"]): row for row in contexts}

    m1_probs: list[float] = []
    m8_probs: list[float] = []
    realized_up: list[bool] = []
    latest_m8: dict[str, Any] | None = None

    for fold in folds:
        test_index = int(fold["test_end_cutoff"])
        context = context_by_index.get(test_index)
        if context is None:
            continue
        vector = _vector_from_context(context)
        m1 = compute_trend_only_baseline(vector)
        m8 = compute_family_engineered_baseline(vector)
        m1_probs.append(m1.outright_up_probability)
        m8_probs.append(m8.outright_up_probability)
        realized_up.append(bool(context["outright_up"]))
        latest_m8 = {
            "futures_model_version": m8.futures_model_version,
            "baseline_tier": m8.baseline_tier,
            "outright_up_probability": m8.outright_up_probability,
            "curve_steepen_probability": m8.curve_steepen_probability,
            "direction_bias": m8.direction_bias,
            "family": m8.family,
        }

    f11_s1 = evaluate_f11_s1_gate(m1_probs, m8_probs, realized_up)
    return {
        "available": True,
        "symbol": str(manifest.get("symbol", instrument_family)),
        "fold_count": len(folds),
        "pit_status": pit_status,
        "pit_reasons": pit_reasons,
        "f11_s1_evaluation": f11_s1,
        "sample_size": len(realized_up),
        "latest_m8_forecast": latest_m8,
        "research_only": True,
    }


def run_f11_cot_upgrade_harness(dataset: dict[str, Any] | None = None) -> dict[str, Any]:
    fixture = dataset or load_es_f11_cot_upgrade_dataset()
    cot_payload = _load_nested(fixture, "cot_relative_path")
    reports = [row for row in cot_payload.get("reports", []) if isinstance(row, dict)]
    decision_time = str(fixture.get("decision_time", "2025-06-02T14:41:07.000000000Z"))
    cot_ok, percentile, crowding = _cot_features(reports, decision_time)
    kwargs = {
        "instrument_family": str(fixture.get("instrument_family", "ES")),
        "trend_3m": float(fixture.get("trend_3m", 1.0)),
        "annualized_carry": float(fixture.get("annualized_carry", 0.04)),
        "curve_slope": float(fixture.get("curve_slope", 0.002)),
        "curve_slope_change": float(fixture.get("curve_slope_change", 0.0002)),
        "stress_score": float(fixture.get("stress_score", 0.2)),
        "event_window_active": bool(fixture.get("event_window_active", False)),
    }
    with_cot = build_futures_feature_vector(
        **kwargs,
        net_percentile=percentile,
        crowding_regime=crowding,
        cot_available=cot_ok,
    )
    without_cot = build_futures_feature_vector(
        **kwargs,
        net_percentile=None,
        crowding_regime=None,
        cot_available=False,
    )
    cot_forecast = compute_family_engineered_baseline(with_cot)
    omitted_forecast = compute_family_engineered_baseline(without_cot)
    fq8 = evaluate_fq8_gate(
        cot_forecast.outright_up_probability,
        omitted_forecast.outright_up_probability,
        cot_available=cot_ok,
    )
    return {
        "available": True,
        "symbol": str(fixture.get("symbol", "ES")),
        "fq8_evaluation": fq8,
        "research_only": True,
    }


def _fixture_ref(*, role: str, relative_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    rel = relative_path.relative_to(_REPO_ROOT).as_posix()
    return {
        "role": role,
        "repository_relative_path": rel,
        "admission_id": payload.get("admission_id"),
        "admitted_fixture_id": payload.get("admitted_fixture_id") or payload.get("admission_id"),
        "fixture_id": payload.get("fixture_id"),
        "symbol": payload.get("symbol"),
    }


def _aggregate_gate_status(gate_summary: list[dict[str, Any]]) -> str:
    if not gate_summary:
        return "INSUFFICIENT_SAMPLE"
    statuses = [str(row.get("gate_status", "")) for row in gate_summary]
    if all(status == "PASS" for status in statuses):
        return "PASS"
    if any(status == "INSUFFICIENT_SAMPLE" for status in statuses):
        return "INSUFFICIENT_SAMPLE"
    return "FAIL"


def _run_family_gate_validation(
    *,
    baseline_fixture_path: Path,
    cot_fixture_path: Path,
    baseline_dataset: dict[str, Any] | None = None,
    cot_dataset: dict[str, Any] | None = None,
    baseline_role: str,
    cot_role: str,
) -> dict[str, Any]:
    baseline_fixture = baseline_dataset or _load_fixture_dict(
        baseline_fixture_path,
        error_code=f"{baseline_role.upper()}_FIXTURE_INVALID",
    )
    cot_fixture = cot_dataset or _load_fixture_dict(
        cot_fixture_path,
        error_code=f"{cot_role.upper()}_FIXTURE_INVALID",
    )

    walk_forward = run_f11_baseline_walk_forward_harness(baseline_fixture)
    f11_s1 = walk_forward.get("f11_s1_evaluation") or {
        "available": False,
        "gate_milestone": "F11-S1",
        "gate_status": "INSUFFICIENT_SAMPLE",
        "reason": walk_forward.get("reason", "WALK_FORWARD_UNAVAILABLE"),
    }

    cot_harness = run_f11_cot_upgrade_harness(cot_fixture)
    fq8 = cot_harness.get("fq8_evaluation") or {
        "available": False,
        "gate_milestone": "FQ-8",
        "gate_status": "INSUFFICIENT_SAMPLE",
        "reason": cot_harness.get("reason", "COT_UPGRADE_UNAVAILABLE"),
    }

    gate_summary = [
        {
            "gate_milestone": f11_s1.get("gate_milestone", "F11-S1"),
            "gate_status": f11_s1.get("gate_status", "INSUFFICIENT_SAMPLE"),
        },
        {
            "gate_milestone": fq8.get("gate_milestone", "FQ-8"),
            "gate_status": fq8.get("gate_status", "INSUFFICIENT_SAMPLE"),
        },
    ]

    return {
        "aggregate_status": _aggregate_gate_status(gate_summary),
        "gate_summary": gate_summary,
        "f11_s1_evaluation": f11_s1,
        "fq8_evaluation": fq8,
        "walk_forward": {
            "fold_count": walk_forward.get("fold_count"),
            "pit_status": walk_forward.get("pit_status"),
            "pit_reasons": walk_forward.get("pit_reasons"),
            "sample_size": walk_forward.get("sample_size"),
        },
        "latest_futures_forecast": walk_forward.get("latest_m8_forecast"),
        "fixture_refs": [
            _fixture_ref(role=baseline_role, relative_path=baseline_fixture_path, payload=baseline_fixture),
            _fixture_ref(role=cot_role, relative_path=cot_fixture_path, payload=cot_fixture),
        ],
    }


def run_f11_baseline_gate_validation(
    *,
    es_dataset: dict[str, Any] | None = None,
    cot_dataset: dict[str, Any] | None = None,
    es_fixture_path: Path | None = None,
    cot_fixture_path: Path | None = None,
) -> dict[str, Any]:
    es_path = es_fixture_path or DEFAULT_ES_F11_BASELINE_FIXTURE
    cot_path = cot_fixture_path or DEFAULT_ES_F11_COT_UPGRADE_FIXTURE
    family_report = _run_family_gate_validation(
        baseline_fixture_path=es_path,
        cot_fixture_path=cot_path,
        baseline_dataset=es_dataset,
        cot_dataset=cot_dataset,
        baseline_role="es_f11_baseline",
        cot_role="es_f11_cot_upgrade",
    )

    return {
        "artifact_type": "F11_BASELINE_GATE_VALIDATION_REPORT",
        "aggregate_status": family_report["aggregate_status"],
        "aggregate_rule": AGGREGATE_RULE,
        "gate_summary": family_report["gate_summary"],
        "f11_s1_evaluation": family_report["f11_s1_evaluation"],
        "fq8_evaluation": family_report["fq8_evaluation"],
        "walk_forward": family_report["walk_forward"],
        "latest_futures_forecast": family_report["latest_futures_forecast"],
        "fixture_refs": family_report["fixture_refs"],
        "research_only": True,
        "experimental": True,
    }


def run_f11_energy_baseline_gate_validation(
    *,
    cl_dataset: dict[str, Any] | None = None,
    cot_dataset: dict[str, Any] | None = None,
    cl_fixture_path: Path | None = None,
    cot_fixture_path: Path | None = None,
) -> dict[str, Any]:
    cl_path = cl_fixture_path or DEFAULT_CL_F11_BASELINE_FIXTURE
    cot_path = cot_fixture_path or DEFAULT_CL_F11_COT_UPGRADE_FIXTURE
    family_report = _run_family_gate_validation(
        baseline_fixture_path=cl_path,
        cot_fixture_path=cot_path,
        baseline_dataset=cl_dataset,
        cot_dataset=cot_dataset,
        baseline_role="cl_f11_baseline",
        cot_role="cl_f11_cot_upgrade",
    )

    return {
        "artifact_type": "F11_ENERGY_BASELINE_GATE_VALIDATION_REPORT",
        "aggregate_status": family_report["aggregate_status"],
        "aggregate_rule": AGGREGATE_RULE,
        "gate_summary": family_report["gate_summary"],
        "f11_s1_evaluation": family_report["f11_s1_evaluation"],
        "fq8_evaluation": family_report["fq8_evaluation"],
        "walk_forward": family_report["walk_forward"],
        "latest_futures_forecast": family_report["latest_futures_forecast"],
        "fixture_refs": family_report["fixture_refs"],
        "research_only": True,
        "experimental": True,
    }


__all__ = [
    "DEFAULT_CL_F11_BASELINE_FIXTURE",
    "DEFAULT_CL_F11_COT_UPGRADE_FIXTURE",
    "DEFAULT_ES_F11_BASELINE_FIXTURE",
    "DEFAULT_ES_F11_COT_UPGRADE_FIXTURE",
    "load_cl_f11_baseline_dataset",
    "load_cl_f11_cot_upgrade_dataset",
    "load_es_f11_baseline_dataset",
    "load_es_f11_cot_upgrade_dataset",
    "run_f11_baseline_gate_validation",
    "run_f11_baseline_walk_forward_harness",
    "run_f11_cot_upgrade_harness",
    "run_f11_energy_baseline_gate_validation",
]
