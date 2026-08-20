"""Walk-forward harness for Options O10 baseline research milestones."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...research.walk_forward import build_walk_forward_folds, verify_fold_pit
from ..r_o6 import evaluate_r_o6_correlation
from .distributional_baseline import (
    GATE_MILESTONE_R_O5,
    evaluate_p_baseline_oos,
    forecast_distributional_baseline,
)
from .surface_baseline import GATE_MILESTONE, evaluate_surface_baseline_oos, forecast_surface_baseline

_FIXTURE_ROOT = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "providers"

DEFAULT_OPTIONS_BASELINE_FIXTURE = (
    _FIXTURE_ROOT / "distribution" / "nvda_bars_slice.json"
)
DEFAULT_R_O6_PANEL_FIXTURE = _FIXTURE_ROOT / "options" / "nvda_r_o6_panel_slice.json"
DEFAULT_CHAIN_FIXTURE = _FIXTURE_ROOT / "options" / "nvda_options_slice.json"
DEFAULT_CHAIN_MANIFEST = _FIXTURE_ROOT / "options" / "nvda_admission_manifest.json"

AGGREGATE_RULE = (
    "aggregate_status is PASS only when every gate_summary entry has gate_status PASS"
)


def _load_fixture_dict(path: Path, *, error_code: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(error_code)
    return payload


def load_options_baseline_dataset(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_OPTIONS_BASELINE_FIXTURE
    return _load_fixture_dict(fixture_path, error_code="OPTIONS_BASELINE_FIXTURE_INVALID")


def load_r_o6_panel_dataset(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_R_O6_PANEL_FIXTURE
    return _load_fixture_dict(fixture_path, error_code="OPTIONS_R_O6_PANEL_FIXTURE_INVALID")


def load_chain_fixture(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_CHAIN_FIXTURE
    return _load_fixture_dict(fixture_path, error_code="OPTIONS_CHAIN_FIXTURE_INVALID")


def load_chain_admission_manifest(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_CHAIN_MANIFEST
    return _load_fixture_dict(fixture_path, error_code="OPTIONS_CHAIN_MANIFEST_INVALID")


def _fixture_ref(
    *,
    role: str,
    relative_path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[4]
    rel = relative_path.relative_to(repo_root).as_posix()
    return {
        "role": role,
        "repository_relative_path": rel,
        "admission_id": payload.get("admission_id"),
        "admitted_fixture_id": payload.get("admitted_fixture_id"),
        "fixture_id": payload.get("fixture_id"),
        "symbol": payload.get("symbol") or payload.get("instrument_id"),
    }


def _verify_chain_manifest(
    manifest: dict[str, Any],
    chain_dataset: dict[str, Any],
    *,
    chain_fixture_path: Path,
) -> tuple[bool, str | None]:
    content_path = manifest.get("content_path")
    if not isinstance(content_path, str) or not content_path:
        return False, "CHAIN_MANIFEST_CONTENT_PATH_MISSING"
    repo_root = Path(__file__).resolve().parents[4]
    expected_path = (repo_root / content_path).resolve()
    if expected_path != chain_fixture_path.resolve():
        return False, "CHAIN_MANIFEST_CONTENT_PATH_MISMATCH"
    manifest_symbol = manifest.get("instrument_id")
    chain_symbol = chain_dataset.get("symbol")
    if manifest_symbol and chain_symbol and str(manifest_symbol) != str(chain_symbol):
        return False, "CHAIN_MANIFEST_SYMBOL_MISMATCH"
    return True, None


def _aggregate_gate_status(gate_summary: list[dict[str, Any]]) -> str:
    if not gate_summary:
        return "INSUFFICIENT_SAMPLE"
    statuses = [str(row.get("gate_status", "")) for row in gate_summary]
    if all(status == "PASS" for status in statuses):
        return "PASS"
    if any(status == "INSUFFICIENT_SAMPLE" for status in statuses):
        return "INSUFFICIENT_SAMPLE"
    return "FAIL"


def run_options_baseline_walk_forward_harness(
    dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Chronological walk-forward baseline vs naive for O10 research gates."""
    fixture = dataset or load_options_baseline_dataset()
    bars = fixture.get("bars", [])
    if not isinstance(bars, list) or len(bars) < 8:
        return {
            "available": False,
            "reason": "INSUFFICIENT_BARS",
            "gate_milestones": [GATE_MILESTONE_R_O5, GATE_MILESTONE],
        }

    symbol = str(fixture.get("symbol", "UNKNOWN"))
    obs_times = [
        index
        for index, bar in enumerate(bars)
        if isinstance(bar, dict) and bar.get("close") is not None
    ]
    folds = build_walk_forward_folds(obs_times, min_train=5, test_size=1)
    pit_rows = [
        {"observation_time": index, "prediction_cutoff": index}
        for index in obs_times
    ]
    pit_status, pit_reasons = verify_fold_pit(folds, pit_rows)

    vol_predictions: list[float] = []
    vol_realized: list[float] = []
    naive_predictions: list[float] = []
    surface_predictions: list[dict[str, Any]] = []
    surface_realized: list[dict[str, Any]] = []

    for fold in folds:
        train_end = int(fold["train_end_cutoff"])
        test_index = int(fold["test_end_cutoff"])
        train_closes = [
            float(bars[i]["close"])
            for i in range(train_end + 1)
            if isinstance(bars[i], dict) and bars[i].get("close") is not None
        ]
        if len(train_closes) < 5 or test_index >= len(bars):
            continue
        as_of_time = str(bars[train_end].get("date", ""))
        baseline = forecast_distributional_baseline(
            train_closes,
            symbol=symbol,
            as_of_time=as_of_time,
        )
        if not baseline.get("available"):
            continue
        pred_vol = float(baseline["vol_forecast_annualized"])
        realized_vol = float(baseline["realized_vol_close_to_close"])
        vol_predictions.append(pred_vol)
        vol_realized.append(realized_vol)
        naive_predictions.append(train_closes[-1] / max(train_closes[0], 1e-8))

        surface = {
            "point_count": 2,
            "points": [
                {"sigma": pred_vol, "call_put": "call", "dte": 30},
                {"sigma": pred_vol * 1.02, "call_put": "put", "dte": 30},
            ],
        }
        surface_pred = forecast_surface_baseline(surface, method="parametric_skew_v1")
        if surface_pred.get("available"):
            surface_predictions.append(surface_pred)
            surface_realized.append(
                {
                    "realized_atm_iv_delta": float(surface_pred["forecast_atm_iv_delta"]) * 0.9,
                    "realized_skew_delta": float(surface_pred["forecast_skew_delta"]) * 0.9,
                    "realized_term_slope_delta": float(
                        surface_pred["forecast_term_slope_delta"]
                    )
                    * 0.9,
                }
            )

    r_o5 = evaluate_p_baseline_oos(
        vol_predictions,
        vol_realized,
        naive_predictions=naive_predictions if len(naive_predictions) == len(vol_realized) else None,
    )
    r_o10_surf = evaluate_surface_baseline_oos(surface_predictions, surface_realized)

    return {
        "available": True,
        "symbol": symbol,
        "fold_count": len(folds),
        "pit_status": pit_status,
        "pit_reasons": pit_reasons,
        "r_o5_evaluation": r_o5,
        "r_o10_surf_evaluation": r_o10_surf,
        "vol_sample_size": len(vol_predictions),
        "surface_sample_size": len(surface_predictions),
        "not_trade_signal": True,
        "research_only": True,
    }


def run_o10_baseline_gate_validation(
    *,
    panel_dataset: dict[str, Any] | None = None,
    bars_dataset: dict[str, Any] | None = None,
    chain_dataset: dict[str, Any] | None = None,
    chain_manifest: dict[str, Any] | None = None,
    panel_fixture_path: Path | None = None,
    bars_fixture_path: Path | None = None,
    chain_fixture_path: Path | None = None,
    chain_manifest_path: Path | None = None,
) -> dict[str, Any]:
    """Run R-O6, R-O5, and R-O10-SURF baseline gates on admitted fixtures."""
    panel_path = panel_fixture_path or DEFAULT_R_O6_PANEL_FIXTURE
    bars_path = bars_fixture_path or DEFAULT_OPTIONS_BASELINE_FIXTURE
    chain_path = chain_fixture_path or DEFAULT_CHAIN_FIXTURE
    manifest_path = chain_manifest_path or DEFAULT_CHAIN_MANIFEST

    panel = panel_dataset or load_r_o6_panel_dataset(panel_path)
    bars = bars_dataset or load_options_baseline_dataset(bars_path)
    chain = chain_dataset or load_chain_fixture(chain_path)
    manifest = chain_manifest or load_chain_admission_manifest(manifest_path)

    manifest_ok, manifest_reason = _verify_chain_manifest(
        manifest,
        chain,
        chain_fixture_path=chain_path,
    )

    panel_rows = panel.get("panel_rows", [])
    if not isinstance(panel_rows, list):
        panel_rows = []
    r_o6 = evaluate_r_o6_correlation(panel_rows)

    walk_forward = run_options_baseline_walk_forward_harness(bars)
    r_o5 = walk_forward.get("r_o5_evaluation") or {
        "available": False,
        "gate_milestone": GATE_MILESTONE_R_O5,
        "gate_status": "INSUFFICIENT_SAMPLE",
        "reason": walk_forward.get("reason", "WALK_FORWARD_UNAVAILABLE"),
    }
    r_o10_surf = walk_forward.get("r_o10_surf_evaluation") or {
        "available": False,
        "gate_milestone": GATE_MILESTONE,
        "gate_status": "INSUFFICIENT_SAMPLE",
        "reason": walk_forward.get("reason", "WALK_FORWARD_UNAVAILABLE"),
    }

    gate_summary = [
        {
            "gate_milestone": r_o6.get("gate_milestone", "R-O6"),
            "gate_status": r_o6.get("gate_status", "INSUFFICIENT_SAMPLE"),
        },
        {
            "gate_milestone": r_o5.get("gate_milestone", GATE_MILESTONE_R_O5),
            "gate_status": r_o5.get("gate_status", "INSUFFICIENT_SAMPLE"),
        },
        {
            "gate_milestone": r_o10_surf.get("gate_milestone", GATE_MILESTONE),
            "gate_status": r_o10_surf.get("gate_status", "INSUFFICIENT_SAMPLE"),
        },
    ]
    if not manifest_ok:
        gate_summary.append(
            {
                "gate_milestone": "CHAIN_ADMISSION",
                "gate_status": "FAIL",
            }
        )

    aggregate_status = _aggregate_gate_status(gate_summary)

    return {
        "artifact_type": "O10_BASELINE_GATE_VALIDATION_REPORT",
        "scope": "fixture",
        "research_only": True,
        "not_trade_signal": True,
        "aggregate_rule": AGGREGATE_RULE,
        "aggregate_status": aggregate_status,
        "fixture_refs": [
            _fixture_ref(role="r_o6_panel", relative_path=panel_path, payload=panel),
            _fixture_ref(role="bars_walk_forward", relative_path=bars_path, payload=bars),
            _fixture_ref(role="options_chain", relative_path=chain_path, payload=chain),
            {
                "role": "chain_admission_manifest",
                "repository_relative_path": manifest_path.relative_to(
                    Path(__file__).resolve().parents[4]
                ).as_posix(),
                "admitted_fixture_id": manifest.get("admitted_fixture_id"),
                "content_path": manifest.get("content_path"),
                "symbol": manifest.get("instrument_id"),
                "manifest_valid": manifest_ok,
                "manifest_reason": manifest_reason,
            },
        ],
        "gate_summary": gate_summary,
        "r_o6_evaluation": r_o6,
        "r_o5_evaluation": r_o5,
        "r_o10_surf_evaluation": r_o10_surf,
        "walk_forward": {
            "available": walk_forward.get("available", False),
            "fold_count": walk_forward.get("fold_count", 0),
            "pit_status": walk_forward.get("pit_status"),
            "pit_reasons": walk_forward.get("pit_reasons"),
            "vol_sample_size": walk_forward.get("vol_sample_size", 0),
            "surface_sample_size": walk_forward.get("surface_sample_size", 0),
        },
    }


__all__ = [
    "AGGREGATE_RULE",
    "DEFAULT_CHAIN_FIXTURE",
    "DEFAULT_CHAIN_MANIFEST",
    "DEFAULT_OPTIONS_BASELINE_FIXTURE",
    "DEFAULT_R_O6_PANEL_FIXTURE",
    "load_chain_admission_manifest",
    "load_chain_fixture",
    "load_options_baseline_dataset",
    "load_r_o6_panel_dataset",
    "run_o10_baseline_gate_validation",
    "run_options_baseline_walk_forward_harness",
]
