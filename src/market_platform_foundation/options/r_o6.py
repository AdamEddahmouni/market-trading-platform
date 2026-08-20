"""R-O6 research gate — P vs Q edge correlation with delta-hedged returns (O10)."""

from __future__ import annotations

from typing import Any, Literal

from .delta_hedged import delta_hedged_research_snapshot
from .edge import compare_physical_vs_risk_neutral

R_O6_VERSION = "r_o6_research_v1"
MIN_PANEL_SIZE = 3
SPEARMAN_PASS_THRESHOLD = 0.0

_EDGE_COMPONENTS = (
    "volatility_edge",
    "directional_edge",
    "skew_edge",
)


def compose_r_o6_research_snapshot(
    physical_p: dict[str, Any] | None,
    risk_neutral_q: dict[str, Any] | None,
    *,
    spot_path: list[float] | None = None,
    strike: float | None = None,
    rate: float = 0.05,
    call_put: Literal["call", "put"] = "call",
    maturity_days: int = 30,
) -> dict[str, Any]:
    """Compose O4 P vs Q edge with O10 delta-hedged path for R-O6 validation."""
    p_vs_q_edge = compare_physical_vs_risk_neutral(physical_p, risk_neutral_q)
    if not p_vs_q_edge.get("available"):
        return {
            "available": False,
            "reason": p_vs_q_edge.get("reason", "P_VS_Q_UNAVAILABLE"),
            "r_o6_version": R_O6_VERSION,
            "gate_milestone": "R-O6",
        }

    delta_hedged = delta_hedged_research_snapshot(
        physical_p,
        risk_neutral_q,
        spot_path=spot_path,
        strike=strike,
        rate=rate,
        call_put=call_put,
        maturity_days=maturity_days,
    )
    if not delta_hedged.get("available"):
        return {
            "available": False,
            "reason": delta_hedged.get("reason", "DELTA_HEDGED_UNAVAILABLE"),
            "r_o6_version": R_O6_VERSION,
            "gate_milestone": "R-O6",
            "p_vs_q_edge": p_vs_q_edge,
        }

    components = p_vs_q_edge.get("components", {})
    return {
        "available": True,
        "r_o6_version": R_O6_VERSION,
        "gate_milestone": "R-O6",
        "target_id": "T-DH",
        "not_trade_signal": True,
        "research_only": True,
        "p_vs_q_edge": p_vs_q_edge,
        "delta_hedged": delta_hedged,
        "volatility_edge": components.get("volatility_edge"),
        "directional_edge": components.get("directional_edge"),
        "skew_edge": components.get("skew_edge"),
        "cumulative_delta_hedged_return_pct": delta_hedged.get(
            "cumulative_delta_hedged_return_pct"
        ),
        "interpretation": (
            "R-O6 research snapshot: P vs Q edge components paired with realized "
            "delta-hedged return path — correlation validation gate only"
        ),
    }


def _rank_values(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(indexed):
        start = index
        value = indexed[index][1]
        while index < len(indexed) and indexed[index][1] == value:
            index += 1
        avg_rank = (start + index - 1) / 2.0 + 1.0
        for position in range(start, index):
            ranks[indexed[position][0]] = avg_rank
    return ranks


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = sum((x - mean_x) ** 2 for x in xs)
    den_y = sum((y - mean_y) ** 2 for y in ys)
    if den_x <= 0 or den_y <= 0:
        return None
    return num / (den_x**0.5 * den_y**0.5)


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    return _pearson(_rank_values(xs), _rank_values(ys))


def _component_pairs(
    panel_rows: list[dict[str, Any]],
    component: str,
    outcome_key: str = "cumulative_delta_hedged_return_pct",
) -> tuple[list[float], list[float]]:
    xs: list[float] = []
    ys: list[float] = []
    for row in panel_rows:
        if not isinstance(row, dict):
            continue
        x_raw = row.get(component)
        y_raw = row.get(outcome_key)
        if isinstance(x_raw, (int, float)) and isinstance(y_raw, (int, float)):
            xs.append(float(x_raw))
            ys.append(float(y_raw))
    return xs, ys


def evaluate_r_o6_correlation(
    panel_rows: list[dict[str, Any]],
    *,
    min_panel_size: int = MIN_PANEL_SIZE,
    spearman_pass_threshold: float = SPEARMAN_PASS_THRESHOLD,
) -> dict[str, Any]:
    """Panel study: correlate P vs Q edge components with delta-hedged returns."""
    if len(panel_rows) < min_panel_size:
        return {
            "available": False,
            "gate_milestone": "R-O6",
            "gate_status": "INSUFFICIENT_SAMPLE",
            "r_o6_version": R_O6_VERSION,
            "sample_size": len(panel_rows),
            "min_panel_size": min_panel_size,
        }

    component_results: dict[str, Any] = {}
    for component in _EDGE_COMPONENTS:
        xs, ys = _component_pairs(panel_rows, component)
        pearson = _pearson(xs, ys)
        spearman = _spearman(xs, ys)
        component_results[component] = {
            "sample_size": len(xs),
            "pearson": round(pearson, 6) if pearson is not None else None,
            "spearman": round(spearman, 6) if spearman is not None else None,
        }

    primary = component_results.get("volatility_edge", {})
    primary_spearman = primary.get("spearman")
    primary_sample = int(primary.get("sample_size", 0))
    if primary_sample < min_panel_size or primary_spearman is None:
        gate_status = "INSUFFICIENT_SAMPLE"
    elif primary_spearman > spearman_pass_threshold:
        gate_status = "PASS"
    else:
        gate_status = "FAIL"

    return {
        "available": True,
        "gate_milestone": "R-O6",
        "gate_status": gate_status,
        "r_o6_version": R_O6_VERSION,
        "sample_size": len(panel_rows),
        "primary_component": "volatility_edge",
        "pearson": primary.get("pearson"),
        "spearman": primary_spearman,
        "component_correlations": component_results,
        "not_trade_signal": True,
        "research_only": True,
        "interpretation": (
            "R-O6 gate: volatility_edge rank correlation with delta-hedged returns; "
            "fixture-scope validation only"
        ),
    }


__all__ = [
    "MIN_PANEL_SIZE",
    "R_O6_VERSION",
    "SPEARMAN_PASS_THRESHOLD",
    "compose_r_o6_research_snapshot",
    "evaluate_r_o6_correlation",
]
