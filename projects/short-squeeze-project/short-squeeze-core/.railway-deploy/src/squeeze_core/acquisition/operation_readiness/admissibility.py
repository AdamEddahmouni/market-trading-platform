"""Deterministic operation-specific admissibility.

Maps (operation dependency + resolved IBKR semantics + coverage/alignment facts) to a
single admissibility status and reason codes. Conservative by construction: UNKNOWN
semantics block (never collapse to FAIL), missing evidence blocks (never treated as
zero), and a boundary-straddling bar blocks alignment (never pick START or END).
Nothing here reads OHLCV, infers a volume unit from magnitude, or reads an outcome.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..ibkr_semantics.resolver import ResolvedIbkrSemantics
from ..local_bar_intake.semantics import (
    PriceAdjustmentSemantics,
    TimestampSemantics,
    VolumeAdjustmentSemantics,
)
from .dependencies import DETECTION_CONTEXT_PRESENT_DOMAINS
from .models import (
    AdmissibilityStatus,
    OperationAdmissibility,
    OperationDependency,
    OperationKind,
    ReasonCode,
    SemanticDependency,
)


@dataclass(frozen=True)
class AdmissibilityContext:
    """Resolved-semantics + coverage facts the admissibility function reasons over.

    Every field is a *documented* fact from Batch 06 resolution or frozen provenance
    coverage; none is inferred from bar magnitudes.
    """

    present_domains: frozenset[str]
    price_split_adjusted: bool
    price_dividend_adjusted: bool
    volume_adjustment_known: bool
    volume_unit_resolved: bool
    timestamp_boundary_known: bool
    provider_filtered: bool
    session_completeness_evidenced: bool
    market_bars_present: bool
    final_bar_definitely_completed: bool
    final_bar_straddles_boundary: bool


def context_from_resolved(
    resolved: ResolvedIbkrSemantics,
    *,
    market_bars_present: bool,
    final_bar_definitely_completed: bool,
    final_bar_straddles_boundary: bool,
    session_completeness_evidenced: bool = False,
    present_domains: frozenset[str] = DETECTION_CONTEXT_PRESENT_DOMAINS,
) -> AdmissibilityContext:
    return AdmissibilityContext(
        present_domains=present_domains,
        price_split_adjusted=resolved.price_adjustment_semantics
        in (
            PriceAdjustmentSemantics.SPLIT_ADJUSTED,
            PriceAdjustmentSemantics.SPLIT_AND_DIVIDEND_ADJUSTED,
        ),
        price_dividend_adjusted=resolved.price_adjustment_semantics
        is PriceAdjustmentSemantics.SPLIT_AND_DIVIDEND_ADJUSTED,
        volume_adjustment_known=resolved.volume_adjustment_semantics
        is not VolumeAdjustmentSemantics.UNKNOWN,
        volume_unit_resolved="volume_unit" not in resolved.unresolved_fields,
        timestamp_boundary_known=resolved.timestamp_semantics
        is not TimestampSemantics.UNKNOWN,
        provider_filtered=bool(resolved.filtered_feed_disclosure),
        session_completeness_evidenced=session_completeness_evidenced,
        market_bars_present=market_bars_present,
        final_bar_definitely_completed=final_bar_definitely_completed,
        final_bar_straddles_boundary=final_bar_straddles_boundary,
    )


def _volume_reasons(sem: SemanticDependency, ctx: AdmissibilityContext) -> list[ReasonCode]:
    reasons: list[ReasonCode] = []
    if sem.volume_unit and not ctx.volume_unit_resolved:
        reasons.append(ReasonCode.VOLUME_UNIT_UNRESOLVED)
    if sem.volume_corporate_action and not ctx.volume_adjustment_known:
        reasons.append(ReasonCode.VOLUME_CORPORATE_ACTION_UNKNOWN)
    if sem.volume_filter_stationarity and ctx.provider_filtered:
        reasons.append(ReasonCode.VOLUME_FILTER_STATIONARITY_UNPROVEN)
    return reasons


def assess_operation(
    dep: OperationDependency, ctx: AdmissibilityContext
) -> OperationAdmissibility:
    """Assess whether the detection-context bars admissibly support ``dep``.

    Deterministic precedence: not-applicable -> missing required (non-bar) domain ->
    alignment straddle -> volume semantics -> absolute-price semantics -> session
    completeness -> availability/ratio admissibility.
    """
    sem = dep.semantic_dependency

    # (1) The bars do not feed this operation at all.
    if not dep.touches_detection_context_bars:
        return OperationAdmissibility(
            operation=dep.operation,
            kind=dep.kind,
            status=AdmissibilityStatus.NOT_APPLICABLE,
            reason_codes=(ReasonCode.OPERATION_INDEPENDENT_OF_THIS_EVIDENCE,),
        )

    reasons: list[ReasonCode] = []
    if ctx.market_bars_present:
        reasons.append(ReasonCode.MARKET_BARS_PRESENT)

    # (2) A required non-bar domain is absent from this evidence set.
    missing_domains = tuple(
        d for d in dep.required_domains if d not in ctx.present_domains
    )
    volume_reasons = _volume_reasons(sem, ctx)

    if missing_domains:
        return OperationAdmissibility(
            operation=dep.operation,
            kind=dep.kind,
            status=AdmissibilityStatus.BLOCKED_MISSING_EVIDENCE,
            reason_codes=tuple(reasons + [ReasonCode.REQUIRED_DOMAIN_ABSENT] + volume_reasons),
            constraints=(f"required domain(s) absent: {', '.join(missing_domains)}",),
        )

    # (3) Timestamp alignment straddle (only if the operation depends on the boundary).
    if sem.timestamp_boundary and ctx.final_bar_straddles_boundary:
        return OperationAdmissibility(
            operation=dep.operation,
            kind=dep.kind,
            status=AdmissibilityStatus.BLOCKED_ALIGNMENT,
            reason_codes=tuple(reasons + [ReasonCode.TIMESTAMP_ALIGNMENT_STRADDLE]),
        )

    # (4) Volume-dependent operations: any unresolved volume field blocks.
    if volume_reasons:
        return OperationAdmissibility(
            operation=dep.operation,
            kind=dep.kind,
            status=AdmissibilityStatus.BLOCKED_MISSING_SEMANTICS,
            reason_codes=tuple(reasons + volume_reasons),
        )

    # (5) Absolute price-level operations: not invariant to an unconfirmed corp action.
    if sem.price_adjustment_absolute:
        return OperationAdmissibility(
            operation=dep.operation,
            kind=dep.kind,
            status=AdmissibilityStatus.BLOCKED_MISSING_SEMANTICS,
            reason_codes=tuple(
                reasons + [ReasonCode.PRICE_ABSOLUTE_LEVEL_CORPORATE_ACTION_UNCONFIRMED]
            ),
            constraints=(
                "absolute price level is not invariant to a split; no corporate-action "
                "evidence confirms none occurred between the boundary and retrieval",
            ),
        )

    # (6) Session completeness required but not evidenced by observed coverage.
    if sem.session_completeness and not ctx.session_completeness_evidenced:
        return OperationAdmissibility(
            operation=dep.operation,
            kind=dep.kind,
            status=AdmissibilityStatus.BLOCKED_MISSING_EVIDENCE,
            reason_codes=tuple(reasons + [ReasonCode.SESSION_COMPLETENESS_UNEVIDENCED]),
        )

    # (7) Pure availability operations.
    if dep.kind is OperationKind.MARKET_BAR_AVAILABILITY:
        if sem.timestamp_boundary:
            if ctx.final_bar_definitely_completed:
                return OperationAdmissibility(
                    operation=dep.operation,
                    kind=dep.kind,
                    status=AdmissibilityStatus.ADMISSIBLE,
                    reason_codes=tuple(reasons + [ReasonCode.FINAL_BAR_DEFINITELY_COMPLETED]),
                )
            return OperationAdmissibility(
                operation=dep.operation,
                kind=dep.kind,
                status=AdmissibilityStatus.BLOCKED_ALIGNMENT,
                reason_codes=tuple(reasons + [ReasonCode.TIMESTAMP_BOUNDARY_UNKNOWN]),
            )
        return OperationAdmissibility(
            operation=dep.operation,
            kind=dep.kind,
            status=AdmissibilityStatus.ADMISSIBLE,
            reason_codes=tuple(reasons),
        )

    # (8) Price-ratio operations: split-invariant, dividend not applied.
    if dep.kind is OperationKind.PRICE_ONLY_RATIO:
        ratio_reasons = reasons + [ReasonCode.PRICE_RATIO_SPLIT_INVARIANT]
        if not ctx.price_dividend_adjusted:
            ratio_reasons.append(ReasonCode.DIVIDEND_ADJUSTMENT_NOT_APPLIED)
        return OperationAdmissibility(
            operation=dep.operation,
            kind=dep.kind,
            status=AdmissibilityStatus.ADMISSIBLE_WITH_CONSTRAINTS,
            reason_codes=tuple(ratio_reasons),
            constraints=(
                "both boundary bars must be definitely-completed under timestamp "
                "uncertainty",
                "no ex-dividend instant is assumed inside the window (prices are not "
                "dividend-adjusted)",
            ),
        )

    # Fallback (should not be reached for declared operations).
    return OperationAdmissibility(
        operation=dep.operation,
        kind=dep.kind,
        status=AdmissibilityStatus.BLOCKED_CONFLICT,
        reason_codes=tuple(reasons),
    )


__all__ = ["AdmissibilityContext", "context_from_resolved", "assess_operation"]
