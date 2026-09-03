"""Deterministic IBKR historical-bar semantic resolver (Batch 06).

Synthetic evidence fixtures only: no network, no Gateway, no account data, no real
bars. Verifies that documented facts map to the existing Batch 03 vocabulary and that
official silence yields UNKNOWN rather than a fabricated value.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from squeeze_core.acquisition.ibkr_semantics import (
    OFFICIAL_TRADES_EVIDENCE,
    IbkrHistoricalSemanticEvidence,
    TimestampBoundaryDoc,
    VolumeUnitResolution,
    resolve_ibkr_semantics,
)
from squeeze_core.acquisition.local_bar_intake.semantics import (
    BarSession,
    CorporateActionHandling,
    PriceAdjustmentSemantics,
    TimestampSemantics,
    VolumeAdjustmentSemantics,
)
from squeeze_core.serialization.canonical_json import canonical_json_bytes


def _evidence(**overrides) -> IbkrHistoricalSemanticEvidence:
    base = OFFICIAL_TRADES_EVIDENCE.model_dump(mode="python")
    base.update(overrides)
    return IbkrHistoricalSemanticEvidence(**base)


def test_official_trades_price_is_split_adjusted():
    resolved = resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE)
    assert resolved.price_adjustment_semantics is PriceAdjustmentSemantics.SPLIT_ADJUSTED


def test_trades_never_maps_to_raw_unadjusted():
    resolved = resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE)
    assert resolved.price_adjustment_semantics is not PriceAdjustmentSemantics.RAW_UNADJUSTED


def test_trades_never_maps_to_dividend_adjusted():
    resolved = resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE)
    assert (
        resolved.price_adjustment_semantics
        is not PriceAdjustmentSemantics.SPLIT_AND_DIVIDEND_ADJUSTED
    )


def test_corporate_action_is_adjustments_applied():
    resolved = resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE)
    assert resolved.corporate_action_handling is CorporateActionHandling.ADJUSTMENTS_APPLIED


def test_volume_adjustment_unknown_when_undocumented():
    resolved = resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE)
    assert resolved.volume_adjustment_semantics is VolumeAdjustmentSemantics.UNKNOWN


def test_volume_adjustment_split_when_documented():
    resolved = resolve_ibkr_semantics(
        _evidence(volume_corporate_action_documented=True, volume_split_adjusted=True)
    )
    assert resolved.volume_adjustment_semantics is VolumeAdjustmentSemantics.SPLIT_ADJUSTED


def test_volume_adjustment_raw_when_documented_unadjusted():
    resolved = resolve_ibkr_semantics(
        _evidence(volume_corporate_action_documented=True, volume_split_adjusted=False)
    )
    assert resolved.volume_adjustment_semantics is VolumeAdjustmentSemantics.RAW_UNADJUSTED


def test_timestamp_semantics_unknown_when_boundary_absent():
    resolved = resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE)
    assert resolved.timestamp_semantics is TimestampSemantics.UNKNOWN


@pytest.mark.parametrize(
    "boundary,expected",
    [
        (TimestampBoundaryDoc.START, TimestampSemantics.START),
        (TimestampBoundaryDoc.END, TimestampSemantics.END),
    ],
)
def test_timestamp_semantics_resolved_when_documented(boundary, expected):
    resolved = resolve_ibkr_semantics(_evidence(bar_timestamp_boundary=boundary))
    assert resolved.timestamp_semantics is expected


def test_event_timezone_utc_from_epoch_seconds():
    resolved = resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE)
    assert resolved.event_timezone == "UTC"


def test_event_timezone_requires_epoch_evidence():
    with pytest.raises(ValueError):
        resolve_ibkr_semantics(_evidence(epoch_seconds_gmt=False))


def test_use_rth_zero_maps_to_extended():
    resolved = resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE)
    assert resolved.session_coverage is BarSession.EXTENDED


def test_use_rth_one_maps_to_regular():
    resolved = resolve_ibkr_semantics(_evidence(use_rth=1))
    assert resolved.session_coverage is BarSession.REGULAR


def test_volume_unit_unresolved_recorded():
    resolved = resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE)
    assert (
        resolved.volume_unit_code
        is VolumeUnitResolution.HISTORICAL_VOLUME_UNIT_UNRESOLVED
    )
    assert "volume_unit" in resolved.unresolved_fields


def test_filtered_feed_disclosure_preserved():
    resolved = resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE)
    assert "filtered" in resolved.filtered_feed_disclosure.lower()
    assert "lower volume" in resolved.filtered_feed_disclosure.lower()


def test_unresolved_fields_are_exactly_volume_timestamp_unit():
    resolved = resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE)
    assert set(resolved.unresolved_fields) == {
        "volume_adjustment_semantics",
        "timestamp_semantics",
        "volume_unit",
    }


def test_non_trades_request_rejected():
    with pytest.raises(ValueError):
        resolve_ibkr_semantics(_evidence(what_to_show="MIDPOINT"))


def test_dividend_without_split_not_representable():
    with pytest.raises(ValueError):
        resolve_ibkr_semantics(
            _evidence(trades_split_adjusted=False, trades_dividend_adjusted=True)
        )


def test_resolution_is_deterministic():
    a = canonical_json_bytes(resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE))
    b = canonical_json_bytes(resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE))
    assert a == b


def test_resolver_does_not_read_ohlcv_or_network():
    # The evidence model has no OHLCV/network field; resolution depends only on
    # documented request/adjustment flags. Guard against silent field creep.
    field_names = set(IbkrHistoricalSemanticEvidence.model_fields)
    forbidden = {"open", "high", "low", "close", "volume", "bars", "url", "host", "port"}
    assert field_names.isdisjoint(forbidden)


def test_evidence_is_frozen():
    with pytest.raises(ValidationError):
        OFFICIAL_TRADES_EVIDENCE.what_to_show = "MIDPOINT"  # type: ignore[misc]
