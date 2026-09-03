"""Walk-forward harness for Order Flow OF12 baseline gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ...donor_patterns.order_book_lane import best_bid_ask
from ...research.walk_forward import build_walk_forward_folds, verify_fold_pit
from ..impact import compute_impact_dynamics
from ..liquidity import compute_liquidity_dynamics, compute_trajectory_resiliency
from ..lob_baseline import compute_lob_baseline_forecast, compute_m1_cvd_baseline
from ..ofi import OFI_METHOD_MULTILEVEL_CS, compute_ofi
from ..queue import build_queue_snapshot, estimate_queue_position, parse_mbo_orders
from ..execution_forecast import compute_execution_forecast
from ..contracts import MboOrderSide
from .gates import evaluate_of12_s1_gate, evaluate_of_q9_gate

_FIXTURE_ROOT = Path(__file__).resolve().parents[4] / "tests" / "fixtures"

DEFAULT_ES_LOB_BASELINE_FIXTURE = _FIXTURE_ROOT / "order_flow" / "es_lob_baseline_slice.json"
DEFAULT_ES_LOB_MBO_UPGRADE_FIXTURE = _FIXTURE_ROOT / "order_flow" / "es_lob_mbo_upgrade_slice.json"
DEFAULT_NVDA_LOB_BASELINE_FIXTURE = _FIXTURE_ROOT / "order_flow" / "nvda_lob_baseline_slice.json"

AGGREGATE_RULE = (
    "aggregate_status is PASS only when every gate_summary entry has gate_status PASS"
)


def _load_fixture_dict(path: Path, *, error_code: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(error_code)
    return payload


def load_es_lob_baseline_dataset(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_ES_LOB_BASELINE_FIXTURE
    return _load_fixture_dict(fixture_path, error_code="ES_LOB_BASELINE_FIXTURE_INVALID")


def load_es_lob_mbo_upgrade_dataset(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_ES_LOB_MBO_UPGRADE_FIXTURE
    return _load_fixture_dict(fixture_path, error_code="ES_LOB_MBO_UPGRADE_FIXTURE_INVALID")


def load_nvda_lob_baseline_dataset(path: Path | None = None) -> dict[str, Any]:
    fixture_path = path or DEFAULT_NVDA_LOB_BASELINE_FIXTURE
    return _load_fixture_dict(fixture_path, error_code="NVDA_LOB_BASELINE_FIXTURE_INVALID")


def _mid_from_snapshot(snapshot: dict[str, Any]) -> float | None:
    bbo = best_bid_ask(snapshot)
    if bbo is None:
        return None
    return (float(bbo["bid_price"]) + float(bbo["ask_price"])) / 2.0


def _transition_context(
    snapshots: list[dict[str, Any]],
    index: int,
    *,
    level_count: int,
    trajectory_resiliency: float,
    bars_by_time: dict[str, dict[str, Any]],
    mbo_by_time: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if index <= 0 or index >= len(snapshots):
        return None
    prev_snapshot = snapshots[index - 1]
    snapshot = snapshots[index]
    if not isinstance(prev_snapshot, dict) or not isinstance(snapshot, dict):
        return None

    ofi_result = compute_ofi(
        prev_snapshot,
        snapshot,
        method=OFI_METHOD_MULTILEVEL_CS,
        level_count=level_count,
    )
    liquidity = compute_liquidity_dynamics(
        prev_snapshot,
        snapshot,
        level_count=level_count,
        trajectory_resiliency=trajectory_resiliency,
    )
    event_time = str(snapshot.get("event_time", ""))
    prev_time = str(prev_snapshot.get("event_time", ""))
    curr_bar = bars_by_time.get(event_time)
    prev_bar = bars_by_time.get(prev_time)
    bar_delta = float(curr_bar["delta"]) if curr_bar and curr_bar.get("delta") is not None else None
    prev_bar_delta = float(prev_bar["delta"]) if prev_bar and prev_bar.get("delta") is not None else None
    impact = compute_impact_dynamics(
        prev_snapshot,
        snapshot,
        bar_delta=bar_delta,
        prev_bar_delta=prev_bar_delta,
        level_count=level_count,
        trajectory_resiliency=trajectory_resiliency,
    )

    queue_ahead_fraction: float | None = None
    mbo_snapshot = mbo_by_time.get(event_time)
    if mbo_snapshot is not None:
        orders = parse_mbo_orders(mbo_snapshot.get("orders", []))
        queue_snapshot = build_queue_snapshot(orders, event_time=event_time)
        if queue_snapshot is not None:
            bbo = best_bid_ask(snapshot)
            if bbo is not None:
                hypothetical_size = 10.0
                estimate = estimate_queue_position(
                    queue_snapshot,
                    side=MboOrderSide.BID,
                    price=float(bbo["bid_price"]),
                    hypothetical_size=hypothetical_size,
                )
                total = estimate.size_ahead + hypothetical_size
                if total > 0:
                    queue_ahead_fraction = estimate.size_ahead / total

    labeled_forward = snapshot.get("mid_delta_forward")
    if labeled_forward is None:
        prev_mid = _mid_from_snapshot(prev_snapshot)
        curr_mid = _mid_from_snapshot(snapshot)
        if prev_mid is None or curr_mid is None:
            return None
        labeled_forward = curr_mid - prev_mid

    return {
        "snapshot": snapshot,
        "ofi_value": ofi_result.value,
        "book_state_valid": ofi_result.book_state_valid,
        "fragility_score": liquidity.fragility_score,
        "resiliency_score": liquidity.resiliency_score,
        "absorption_score": impact.absorption_score,
        "bar_delta": bar_delta,
        "cvd_slope": (
            bar_delta - prev_bar_delta
            if bar_delta is not None and prev_bar_delta is not None
            else None
        ),
        "queue_ahead_fraction": queue_ahead_fraction,
        "mid_delta_forward": float(labeled_forward),
        "observation_index": index,
    }


def run_of12_baseline_walk_forward_harness(
    dataset: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fixture = dataset or load_es_lob_baseline_dataset()
    snapshots = fixture.get("snapshots", [])
    if not isinstance(snapshots, list) or len(snapshots) < 4:
        return {
            "available": False,
            "reason": "INSUFFICIENT_SNAPSHOTS",
            "gate_milestones": ["OF12-S1"],
        }

    level_count = int(fixture.get("level_count", 10))
    valid_snapshots = [
        row for row in snapshots if isinstance(row, dict) and row.get("event_time")
    ]
    trajectory_resiliency = compute_trajectory_resiliency(valid_snapshots, level_count=level_count)
    bars_by_time: dict[str, dict[str, Any]] = {}
    for bar in fixture.get("bars", []) if isinstance(fixture.get("bars"), list) else []:
        if isinstance(bar, dict) and bar.get("date"):
            bars_by_time[str(bar["date"])] = bar

    mbo_by_time: dict[str, dict[str, Any]] = {}
    for row in fixture.get("mbo_snapshots", []) if isinstance(fixture.get("mbo_snapshots"), list) else []:
        if isinstance(row, dict) and row.get("event_time"):
            mbo_by_time[str(row["event_time"])] = row

    obs_times = list(range(1, len(valid_snapshots)))
    folds = build_walk_forward_folds(obs_times, min_train=2, test_size=1)
    pit_rows = [{"observation_time": index, "prediction_cutoff": index} for index in obs_times]
    pit_status, pit_reasons = verify_fold_pit(folds, pit_rows)

    m1_probs: list[float] = []
    m8_probs: list[float] = []
    realized_up: list[bool] = []

    for fold in folds:
        test_index = int(fold["test_end_cutoff"])
        context = _transition_context(
            valid_snapshots,
            test_index,
            level_count=level_count,
            trajectory_resiliency=trajectory_resiliency,
            bars_by_time=bars_by_time,
            mbo_by_time=mbo_by_time,
        )
        if context is None:
            continue
        m1 = compute_m1_cvd_baseline(
            context["snapshot"],
            bar_delta=context["bar_delta"],
            cvd_slope=context["cvd_slope"],
            book_state_valid=context["book_state_valid"],
        )
        m8 = compute_lob_baseline_forecast(
            context["snapshot"],
            ofi_value=context["ofi_value"],
            book_state_valid=context["book_state_valid"],
            fragility_score=context["fragility_score"],
            resiliency_score=context["resiliency_score"],
            absorption_score=context["absorption_score"],
            bar_delta=context["bar_delta"],
            cvd_slope=context["cvd_slope"],
            queue_ahead_fraction=context["queue_ahead_fraction"],
        )
        forward = float(context["mid_delta_forward"])
        m1_probs.append(m1.mid_up_probability)
        m8_probs.append(m8.mid_up_probability)
        realized_up.append(forward > 0.0)

    of12_s1 = evaluate_of12_s1_gate(m1_probs, m8_probs, realized_up)
    return {
        "available": True,
        "symbol": str(fixture.get("symbol", "UNKNOWN")),
        "fold_count": len(folds),
        "pit_status": pit_status,
        "pit_reasons": pit_reasons,
        "of12_s1_evaluation": of12_s1,
        "sample_size": len(realized_up),
        "research_only": True,
    }


def run_of12_mbo_upgrade_harness(dataset: dict[str, Any] | None = None) -> dict[str, Any]:
    fixture = dataset or load_es_lob_mbo_upgrade_dataset()
    snapshot = fixture.get("snapshot")
    mbo_snapshot = fixture.get("mbo_snapshot")
    if not isinstance(snapshot, dict):
        return {"available": False, "reason": "MISSING_SNAPSHOT"}

    order_qty = float(fixture.get("order_qty", 10.0))
    l2_execution = compute_execution_forecast(
        snapshot,
        order_qty=order_qty,
        book_state_valid=True,
        fragility_score=float(fixture.get("fragility_score", 0.1)),
        mbo_queue_snapshot=None,
    )
    queue_snapshot = None
    if isinstance(mbo_snapshot, dict):
        orders = parse_mbo_orders(mbo_snapshot.get("orders", []))
        queue_snapshot = build_queue_snapshot(
            orders,
            event_time=str(mbo_snapshot.get("event_time", "")),
        )

    mbo_execution = compute_execution_forecast(
        snapshot,
        order_qty=order_qty,
        book_state_valid=True,
        fragility_score=float(fixture.get("fragility_score", 0.1)),
        mbo_queue_snapshot=queue_snapshot,
    )
    of_q9 = evaluate_of_q9_gate(
        l2_execution.passive_fill_probability,
        mbo_execution.passive_fill_probability,
        l2_queue_model=l2_execution.queue_model_version,
        mbo_queue_model=mbo_execution.queue_model_version,
    )
    return {
        "available": True,
        "symbol": str(fixture.get("symbol", "ES")),
        "of_q9_evaluation": of_q9,
        "research_only": True,
    }


def _fixture_ref(*, role: str, relative_path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[4]
    rel = relative_path.relative_to(repo_root).as_posix()
    return {
        "role": role,
        "repository_relative_path": rel,
        "admission_id": payload.get("admission_id"),
        "admitted_fixture_id": payload.get("admitted_fixture_id"),
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


def run_of12_baseline_gate_validation(
    *,
    es_dataset: dict[str, Any] | None = None,
    mbo_dataset: dict[str, Any] | None = None,
    es_fixture_path: Path | None = None,
    mbo_fixture_path: Path | None = None,
) -> dict[str, Any]:
    es_path = es_fixture_path or DEFAULT_ES_LOB_BASELINE_FIXTURE
    mbo_path = mbo_fixture_path or DEFAULT_ES_LOB_MBO_UPGRADE_FIXTURE
    es_fixture = es_dataset or load_es_lob_baseline_dataset(es_path)
    mbo_fixture = mbo_dataset or load_es_lob_mbo_upgrade_dataset(mbo_path)

    walk_forward = run_of12_baseline_walk_forward_harness(es_fixture)
    of12_s1 = walk_forward.get("of12_s1_evaluation") or {
        "available": False,
        "gate_milestone": "OF12-S1",
        "gate_status": "INSUFFICIENT_SAMPLE",
        "reason": walk_forward.get("reason", "WALK_FORWARD_UNAVAILABLE"),
    }

    mbo_harness = run_of12_mbo_upgrade_harness(mbo_fixture)
    of_q9 = mbo_harness.get("of_q9_evaluation") or {
        "available": False,
        "gate_milestone": "OF-Q9",
        "gate_status": "INSUFFICIENT_SAMPLE",
        "reason": mbo_harness.get("reason", "MBO_UPGRADE_UNAVAILABLE"),
    }

    gate_summary = [
        {
            "gate_milestone": of12_s1.get("gate_milestone", "OF12-S1"),
            "gate_status": of12_s1.get("gate_status", "INSUFFICIENT_SAMPLE"),
        },
        {
            "gate_milestone": of_q9.get("gate_milestone", "OF-Q9"),
            "gate_status": of_q9.get("gate_status", "INSUFFICIENT_SAMPLE"),
        },
    ]
    aggregate_status = _aggregate_gate_status(gate_summary)

    return {
        "artifact_type": "OF12_BASELINE_GATE_VALIDATION_REPORT",
        "aggregate_status": aggregate_status,
        "aggregate_rule": AGGREGATE_RULE,
        "gate_summary": gate_summary,
        "of12_s1_evaluation": of12_s1,
        "of_q9_evaluation": of_q9,
        "walk_forward": {
            "fold_count": walk_forward.get("fold_count"),
            "pit_status": walk_forward.get("pit_status"),
            "pit_reasons": walk_forward.get("pit_reasons"),
            "sample_size": walk_forward.get("sample_size"),
        },
        "fixture_refs": [
            _fixture_ref(role="es_lob_baseline", relative_path=es_path, payload=es_fixture),
            _fixture_ref(role="es_lob_mbo_upgrade", relative_path=mbo_path, payload=mbo_fixture),
        ],
        "research_only": True,
        "experimental": True,
    }


__all__ = [
    "DEFAULT_ES_LOB_BASELINE_FIXTURE",
    "DEFAULT_ES_LOB_MBO_UPGRADE_FIXTURE",
    "DEFAULT_NVDA_LOB_BASELINE_FIXTURE",
    "load_es_lob_baseline_dataset",
    "load_es_lob_mbo_upgrade_dataset",
    "load_nvda_lob_baseline_dataset",
    "run_of12_baseline_gate_validation",
    "run_of12_baseline_walk_forward_harness",
    "run_of12_mbo_upgrade_harness",
]
