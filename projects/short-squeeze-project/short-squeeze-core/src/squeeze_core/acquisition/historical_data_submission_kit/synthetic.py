"""The kit's self-contained synthetic-valid example bundle.

Unmistakably fictional provider, symbol, and venue; fixed instants (never
wall-clock); six contiguous valid 5-minute UTC bars. Distinct from the Batch 03
fixture bundle so the operator kit stands alone. No real market data, no
credentials, no case association, no outcome work.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from ..local_bar_intake.models import ColumnMappingProfile, IntakeManifest
from ..local_bar_intake.semantics import (
    ArtifactFormat,
    BarInterval,
    BarSession,
    CorporateActionHandling,
    DataTimeBasis,
    DuplicatePolicy,
    IntendedUse,
    PriceAdjustmentSemantics,
    SessionCoveragePolicy,
    SortExpectation,
    ThousandsSeparatorPolicy,
    TimestampSemantics,
    ValueAuthenticity,
    VolumeAdjustmentSemantics,
)


BUNDLE_ID = "demo-zzq1-5m-2026-07-15"
PROFILE_ID = "demo-historical-ohlcv-csv.v1"

# Fixed instants; retrieval/export are distinct from event time.
_RETRIEVAL_TIME = datetime(2026, 7, 16, 10, 0, 0, tzinfo=UTC)
_EXPORT_TIME = datetime(2026, 7, 16, 9, 45, 0, tzinfo=UTC)
_COVERAGE_START = datetime(2026, 7, 15, 14, 30, 0, tzinfo=UTC)
_COVERAGE_END = datetime(2026, 7, 15, 15, 0, 0, tzinfo=UTC)

# Six contiguous 5-minute UTC bars for fictional symbol ZZQ1. LF endings, explicit
# header, no thousands separators, valid OHLC relationships, nonnegative volume.
RAW_CSV = (
    "timestamp,symbol,venue,open,high,low,close,volume,trades,vwap,currency\n"
    "2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,20.40,19.90,20.25,3000,30,20.12,USD\n"
    "2026-07-15T14:35:00,ZZQ1,DEMO_VENUE_X,20.25,20.55,20.15,20.50,3200,33,20.36,USD\n"
    "2026-07-15T14:40:00,ZZQ1,DEMO_VENUE_X,20.50,20.75,20.35,20.40,2800,28,20.53,USD\n"
    "2026-07-15T14:45:00,ZZQ1,DEMO_VENUE_X,20.40,20.90,20.30,20.85,3500,35,20.61,USD\n"
    "2026-07-15T14:50:00,ZZQ1,DEMO_VENUE_X,20.85,21.10,20.70,20.95,4100,40,20.92,USD\n"
    "2026-07-15T14:55:00,ZZQ1,DEMO_VENUE_X,20.95,21.00,20.55,20.60,2600,26,20.78,USD\n"
).encode("utf-8")


def build_column_mapping_profile() -> ColumnMappingProfile:
    return ColumnMappingProfile(
        profile_id=PROFILE_ID,
        delimiter=",",
        encoding="utf-8",
        has_header=True,
        timestamp_column="timestamp",
        symbol_column="symbol",
        venue_column="venue",
        open_column="open",
        high_column="high",
        low_column="low",
        close_column="close",
        volume_column="volume",
        trade_count_column="trades",
        vwap_column="vwap",
        currency_column="currency",
        decimal_separator=".",
        thousands_separator_policy=ThousandsSeparatorPolicy.DISALLOW,
        null_tokens=("", "NA", "null"),
        sort_expectation=SortExpectation.STABLE_SORT_BY_EVENT_START,
        duplicate_policy=DuplicatePolicy.COLLAPSE_IDENTICAL_REJECT_CONFLICTING,
    )


def build_valid_manifest() -> IntakeManifest:
    return IntakeManifest(
        bundle_id=BUNDLE_ID,
        provider_name="DEMO_FIXTURE_FEED",
        provider_product_or_export_name="Fictional Intraday Bars Export (kit example)",
        user_entitlement_assertion=(
            "SYNTHETIC KIT EXAMPLE -- contains no real vendor data; entitlement not "
            "applicable. Replace with your own entitlement statement for a real export."
        ),
        license_or_terms_reference="synthetic-kit-example-no-license",
        retrieval_time=_RETRIEVAL_TIME,
        export_time=_EXPORT_TIME,
        artifact_relative_path="raw/synthetic-bars.csv",
        artifact_sha256=hashlib.sha256(RAW_CSV).hexdigest(),
        artifact_byte_length=len(RAW_CSV),
        artifact_media_type="text/csv",
        artifact_format=ArtifactFormat.CSV,
        provider_symbol="ZZQ1",
        canonical_symbol="ZZQ1",
        market_or_venue="DEMO_VENUE_X",
        bar_interval=BarInterval.FIVE_MINUTES,
        event_timezone="UTC",
        timestamp_semantics=TimestampSemantics.START,
        session_coverage=BarSession.REGULAR,
        session_coverage_policy=SessionCoveragePolicy.REQUIRE_CONTINUOUS,
        price_adjustment_semantics=PriceAdjustmentSemantics.RAW_UNADJUSTED,
        volume_adjustment_semantics=VolumeAdjustmentSemantics.RAW_UNADJUSTED,
        corporate_action_handling=CorporateActionHandling.RAW_NO_ADJUSTMENT,
        data_time_basis=DataTimeBasis.HISTORICAL,
        value_authenticity=ValueAuthenticity.SYNTHETIC_FIXTURE,
        intended_use=IntendedUse.INFRASTRUCTURE_FIXTURE,
        expected_start_time=_COVERAGE_START,
        expected_end_time=_COVERAGE_END,
        column_mapping_profile_id=PROFILE_ID,
        notes="Synthetic kit example bundle. Not a real security or historical claim.",
    )


__all__ = [
    "BUNDLE_ID",
    "PROFILE_ID",
    "RAW_CSV",
    "build_column_mapping_profile",
    "build_valid_manifest",
]
