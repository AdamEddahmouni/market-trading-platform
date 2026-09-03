"""Point-in-time opportunity context validation (BUILD 21)."""

from __future__ import annotations

from ..contracts.common import ContractReference, ContractKind
from .errors import OpportunityError
from .types import OpportunityContext


def validate_context_pit(
    context: OpportunityContext,
    *,
    opportunity_decision_time_ns: int,
) -> None:
    if context.snapshot_available_time_ns is not None:
        if context.snapshot_available_time_ns > opportunity_decision_time_ns:
            raise OpportunityError(
                "TEMPORAL_INTEGRITY_VIOLATION",
                details={"field": "snapshot_available_time_ns"},
            )
    if context.spread_available_time_ns is not None:
        if context.spread_available_time_ns > opportunity_decision_time_ns:
            raise OpportunityError(
                "TEMPORAL_INTEGRITY_VIOLATION",
                details={"field": "spread_available_time_ns"},
            )
    if context.depth_available_time_ns is not None:
        if context.depth_available_time_ns > opportunity_decision_time_ns:
            raise OpportunityError(
                "TEMPORAL_INTEGRITY_VIOLATION",
                details={"field": "depth_available_time_ns"},
            )
    if context.regime_available_time_ns is not None:
        if context.regime_available_time_ns > opportunity_decision_time_ns:
            raise OpportunityError(
                "TEMPORAL_INTEGRITY_VIOLATION",
                details={"field": "regime_available_time_ns"},
            )


def context_refs(context: OpportunityContext) -> tuple[ContractReference, ...]:
    refs: list[ContractReference] = []
    if context.snapshot_ref is not None:
        refs.append(context.snapshot_ref)
    refs.extend(context.signal_refs)
    return tuple(refs)


__all__ = ["context_refs", "validate_context_pit"]
