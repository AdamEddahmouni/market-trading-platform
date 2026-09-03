"""Pure, deterministic resolver from IBKR documented evidence to Batch 03 semantics.

Given an :class:`IbkrHistoricalSemanticEvidence` (documented facts only), this maps
to the existing ``local_bar_intake`` enum vocabulary. It reuses existing enum values
and never invents new ones, never accesses the network / Gateway / account data, and
never reads bar (OHLCV) values or infers semantics from them. Where official evidence
is silent, the corresponding field resolves to ``UNKNOWN`` -- honestly, not forced.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ..local_bar_intake.semantics import (
    BarSession,
    CorporateActionHandling,
    PriceAdjustmentSemantics,
    TimestampSemantics,
    VolumeAdjustmentSemantics,
)
from .evidence import (
    FILTERED_FEED_DISCLOSURE,
    IbkrHistoricalSemanticEvidence,
    TimestampBoundaryDoc,
    VolumeUnitResolution,
)

# This batch only resolves TRADES semantics; other whatToShow values are out of scope.
SUPPORTED_WHAT_TO_SHOW = "TRADES"


class ResolvedIbkrSemantics(BaseModel):
    """Deterministic resolution outcome. Field order is stable for canonical output."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    price_adjustment_semantics: PriceAdjustmentSemantics
    volume_adjustment_semantics: VolumeAdjustmentSemantics
    corporate_action_handling: CorporateActionHandling
    timestamp_semantics: TimestampSemantics
    event_timezone: str = Field(min_length=1)
    session_coverage: BarSession
    volume_unit_code: VolumeUnitResolution
    filtered_feed_disclosure: str = Field(min_length=1)
    unresolved_fields: tuple[str, ...] = ()


def _resolve_price(evidence: IbkrHistoricalSemanticEvidence) -> PriceAdjustmentSemantics:
    if evidence.trades_split_adjusted and evidence.trades_dividend_adjusted:
        return PriceAdjustmentSemantics.SPLIT_AND_DIVIDEND_ADJUSTED
    if evidence.trades_split_adjusted and not evidence.trades_dividend_adjusted:
        return PriceAdjustmentSemantics.SPLIT_ADJUSTED
    if not evidence.trades_split_adjusted and not evidence.trades_dividend_adjusted:
        return PriceAdjustmentSemantics.RAW_UNADJUSTED
    # Dividend-adjusted-but-not-split is not a documented IBKR TRADES behavior.
    raise ValueError("dividend-adjusted without split adjustment is not representable")


def _resolve_corporate_action(
    evidence: IbkrHistoricalSemanticEvidence,
) -> CorporateActionHandling:
    if evidence.trades_split_adjusted or evidence.trades_dividend_adjusted:
        return CorporateActionHandling.ADJUSTMENTS_APPLIED
    return CorporateActionHandling.RAW_NO_ADJUSTMENT


def _resolve_volume(
    evidence: IbkrHistoricalSemanticEvidence,
) -> VolumeAdjustmentSemantics:
    if not evidence.volume_corporate_action_documented:
        return VolumeAdjustmentSemantics.UNKNOWN
    if evidence.volume_split_adjusted:
        return VolumeAdjustmentSemantics.SPLIT_ADJUSTED
    return VolumeAdjustmentSemantics.RAW_UNADJUSTED


def _resolve_timestamp(
    evidence: IbkrHistoricalSemanticEvidence,
) -> TimestampSemantics:
    if evidence.bar_timestamp_boundary is TimestampBoundaryDoc.START:
        return TimestampSemantics.START
    if evidence.bar_timestamp_boundary is TimestampBoundaryDoc.END:
        return TimestampSemantics.END
    return TimestampSemantics.UNKNOWN


def _resolve_timezone(evidence: IbkrHistoricalSemanticEvidence) -> str:
    if evidence.epoch_seconds_gmt:
        # formatDate=2 yields an absolute epoch instant in GMT; UTC is unambiguous.
        return "UTC"
    raise ValueError("event timezone is only resolvable from epoch-seconds evidence")


def _resolve_session(evidence: IbkrHistoricalSemanticEvidence) -> BarSession:
    if evidence.use_rth == 0:
        return BarSession.EXTENDED
    if evidence.use_rth == 1:
        return BarSession.REGULAR
    return BarSession.UNKNOWN


def resolve_ibkr_semantics(
    evidence: IbkrHistoricalSemanticEvidence,
) -> ResolvedIbkrSemantics:
    """Map documented IBKR evidence to Batch 03 semantic values, deterministically.

    Raises ``ValueError`` only for structurally impossible inputs (e.g. a non-TRADES
    request or dividend-without-split); silence in official docs never raises -- it
    yields ``UNKNOWN``.
    """
    if evidence.what_to_show != SUPPORTED_WHAT_TO_SHOW:
        raise ValueError(f"unsupported whatToShow: {evidence.what_to_show!r}")

    price = _resolve_price(evidence)
    volume = _resolve_volume(evidence)
    handling = _resolve_corporate_action(evidence)
    timestamp = _resolve_timestamp(evidence)
    timezone = _resolve_timezone(evidence)
    session = _resolve_session(evidence)

    unresolved: list[str] = []
    if price is PriceAdjustmentSemantics.UNKNOWN:
        unresolved.append("price_adjustment_semantics")
    if volume is VolumeAdjustmentSemantics.UNKNOWN:
        unresolved.append("volume_adjustment_semantics")
    if handling is CorporateActionHandling.UNKNOWN:
        unresolved.append("corporate_action_handling")
    if timestamp is TimestampSemantics.UNKNOWN:
        unresolved.append("timestamp_semantics")
    if session is BarSession.UNKNOWN:
        unresolved.append("session_coverage")
    if evidence.volume_unit is VolumeUnitResolution.HISTORICAL_VOLUME_UNIT_UNRESOLVED:
        unresolved.append("volume_unit")

    return ResolvedIbkrSemantics(
        price_adjustment_semantics=price,
        volume_adjustment_semantics=volume,
        corporate_action_handling=handling,
        timestamp_semantics=timestamp,
        event_timezone=timezone,
        session_coverage=session,
        volume_unit_code=evidence.volume_unit,
        filtered_feed_disclosure=FILTERED_FEED_DISCLOSURE,
        unresolved_fields=tuple(unresolved),
    )


__all__ = [
    "SUPPORTED_WHAT_TO_SHOW",
    "ResolvedIbkrSemantics",
    "resolve_ibkr_semantics",
]
