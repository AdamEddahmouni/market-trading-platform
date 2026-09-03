"""RT-01 trace completeness classification."""

from __future__ import annotations

from .enums import TraceCompleteness, TraceStatus
from .span import TraceSpan


def classify_completeness(
    spans: list[TraceSpan],
    *,
    context_lost: bool = False,
    sampled_partial: bool = False,
) -> TraceCompleteness:
    if not spans:
        return TraceCompleteness.PARTIAL_CONTEXT_LOSS
    if context_lost:
        return TraceCompleteness.PARTIAL_CONTEXT_LOSS
    if sampled_partial:
        return TraceCompleteness.PARTIAL_SAMPLED
    terminal = spans[-1]
    if terminal.status == TraceStatus.ERROR:
        return TraceCompleteness.TERMINATED_BY_ERROR
    if terminal.status == TraceStatus.TERMINATED:
        return TraceCompleteness.TERMINATED_BY_DOMAIN_DECISION
    return TraceCompleteness.COMPLETE_FOR_OBSERVED_PATH


__all__ = ["classify_completeness"]
