"""Execution funnel reconciliation (BUILD 27)."""

from __future__ import annotations

from .types import ExecutionFunnelCountsV1


def reconcile_funnel(counts: ExecutionFunnelCountsV1) -> tuple[bool, list[str]]:
    """Verify funnel transitions reconcile without unexplained drops."""
    issues: list[str] = []
    if counts.opportunities_emitted > counts.opportunity_assessments:
        issues.append("OPPORTUNITIES_EXCEED_ASSESSMENTS")
    if counts.trade_proposals > counts.opportunities_emitted:
        issues.append("PROPOSALS_EXCEED_OPPORTUNITIES")
    total_risk = counts.risk_approvals + counts.risk_reductions + counts.risk_rejections
    if total_risk > counts.trade_proposals:
        issues.append("RISK_DECISIONS_EXCEED_PROPOSALS")
    if counts.orders_submitted > total_risk:
        issues.append("ORDERS_EXCEED_RISK_DECISIONS")
    if counts.orders_filled > counts.orders_submitted:
        issues.append("FILLS_EXCEED_ORDERS")
    return len(issues) == 0, issues


def empty_funnel() -> ExecutionFunnelCountsV1:
    return ExecutionFunnelCountsV1()
