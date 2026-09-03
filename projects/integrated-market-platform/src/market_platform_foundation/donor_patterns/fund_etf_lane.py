"""Fund/ETF flow and cross-asset context lane patterns — synthetic fixture semantics."""

from __future__ import annotations


def flow_proxy_ratio(net_flow: float, baseline: float) -> float:
    if baseline <= 0:
        return 0.0
    return round(net_flow / baseline, 4)


def correlation_regime(correlation: float, *, high: float = 0.65, low: float = 0.45) -> str:
    if correlation >= high:
        return "risk_on"
    if correlation <= low:
        return "risk_off"
    return "neutral"


def flow_direction_label(
    flow_proxy_ratio_value: float,
    *,
    inflow_threshold: float = 1.15,
    outflow_threshold: float = 0.85,
) -> str:
    if flow_proxy_ratio_value >= inflow_threshold:
        return "supports_long"
    if flow_proxy_ratio_value <= outflow_threshold:
        return "supports_short"
    return "neutral"
