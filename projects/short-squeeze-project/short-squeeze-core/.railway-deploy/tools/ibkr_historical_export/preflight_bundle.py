"""Build a private Batch 04 intake bundle from captured IBKR CSV bytes and run the
existing offline preflight -- honestly.

This module imports the deterministic runtime's intake/preflight primitives but never
the live IBKR client. It declares provider semantics truthfully: IBKR historical
TRADES adjustment and volume-unit semantics are not verifiable from the allowed
(non-account) API surface, so they are declared ``UNKNOWN``. The Batch 03 normalizer
treats ``UNKNOWN`` adjustment as a fatal ``MISSING_ADJUSTMENT_SEMANTICS`` code, so the
honest, expected result is ``PREFLIGHT_REJECTED``. Batch 03 semantics are never changed
to force acceptance, and no case association is performed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from squeeze_core.acquisition.local_bar_intake.models import (
    ColumnMappingProfile,
    IntakeManifest,
)
from squeeze_core.acquisition.local_bar_intake.semantics import (
    ArtifactFormat,
    BarInterval,
    BarSession,
    CorporateActionHandling,
    DataTimeBasis,
    IntendedUse,
    PriceAdjustmentSemantics,
    TimestampSemantics,
    ValueAuthenticity,
    VolumeAdjustmentSemantics,
)
from squeeze_core.acquisition.historical_data_submission_kit.preflight import (
    PreflightReport,
    PreflightStatus as _RuntimePreflightStatus,
    run_preflight_from_bytes,
)

from .statuses import PreflightStatus

PROVIDER_NAME = "Interactive Brokers"
PROVIDER_PRODUCT = "TWS API Historical Bars via IB Gateway"
ENTITLEMENT_ASSERTION = (
    "Operator asserts a local IB Gateway session entitled to historical TRADES bars; "
    "adjustment and volume-unit semantics are not verifiable from the non-account API "
    "surface and are declared UNKNOWN."
)

_STATUS_MAP = {
    _RuntimePreflightStatus.READY_FOR_FUTURE_ASSOCIATION: PreflightStatus.PREFLIGHT_READY,
    _RuntimePreflightStatus.NOT_READY_QUARANTINED: PreflightStatus.PREFLIGHT_QUARANTINED,
    _RuntimePreflightStatus.NOT_READY_REJECTED: PreflightStatus.PREFLIGHT_REJECTED,
}


@dataclass(frozen=True, slots=True)
class PreflightOutcome:
    status: PreflightStatus
    report: PreflightReport
    reason_codes: tuple[str, ...]


def build_profile(bundle_id: str) -> ColumnMappingProfile:
    """Column profile matching the tool's fixed CSV layout."""
    return ColumnMappingProfile(
        profile_id=f"{bundle_id}::ibkr-csv",
        delimiter=",",
        encoding="utf-8",
        has_header=True,
        timestamp_column="timestamp_utc",
        open_column="open",
        high_column="high",
        low_column="low",
        close_column="close",
        volume_column="volume",
        trade_count_column="bar_count",
        vwap_column="wap",
        symbol_column="requested_symbol",
    )


def build_manifest(
    *,
    bundle_id: str,
    symbol: str,
    artifact_relative_path: str,
    artifact_sha256: str,
    artifact_byte_length: int,
    retrieval_time: datetime,
    export_time: datetime,
    expected_start_time: datetime,
    expected_end_time: datetime,
    profile_id: str,
) -> IntakeManifest:
    """Honest IBKR intake manifest. Adjustment/volume semantics are UNKNOWN."""
    return IntakeManifest(
        bundle_id=bundle_id,
        provider_name=PROVIDER_NAME,
        provider_product_or_export_name=PROVIDER_PRODUCT,
        user_entitlement_assertion=ENTITLEMENT_ASSERTION,
        license_or_terms_reference="IB API Non-Commercial License",
        retrieval_time=retrieval_time,
        export_time=export_time,
        artifact_relative_path=artifact_relative_path,
        artifact_sha256=artifact_sha256,
        artifact_byte_length=artifact_byte_length,
        artifact_media_type="text/csv",
        artifact_format=ArtifactFormat.CSV,
        provider_symbol=symbol,
        canonical_symbol=symbol,
        market_or_venue="SMART",
        bar_interval=BarInterval.ONE_MINUTE,
        event_timezone="UTC",
        timestamp_semantics=TimestampSemantics.START,
        session_coverage=BarSession.EXTENDED,
        price_adjustment_semantics=PriceAdjustmentSemantics.UNKNOWN,
        volume_adjustment_semantics=VolumeAdjustmentSemantics.UNKNOWN,
        corporate_action_handling=CorporateActionHandling.UNKNOWN,
        data_time_basis=DataTimeBasis.HISTORICAL,
        value_authenticity=ValueAuthenticity.VENDOR_SUPPLIED,
        intended_use=IntendedUse.HISTORICAL_EVIDENCE,
        expected_start_time=expected_start_time,
        expected_end_time=expected_end_time,
        column_mapping_profile_id=profile_id,
        notes="IBKR TWS historical TRADES bars, useRTH=0; UNKNOWN adjustment semantics.",
    )


def run_bundle_preflight(
    *,
    bundle_id: str,
    symbol: str,
    csv_bytes: bytes,
    artifact_relative_path: str,
    artifact_sha256: str,
    artifact_byte_length: int,
    retrieval_time: datetime,
    export_time: datetime,
    expected_start_time: datetime,
    expected_end_time: datetime,
) -> PreflightOutcome:
    """Build the bundle and run the existing offline preflight on the exact CSV bytes."""
    profile = build_profile(bundle_id)
    manifest = build_manifest(
        bundle_id=bundle_id,
        symbol=symbol,
        artifact_relative_path=artifact_relative_path,
        artifact_sha256=artifact_sha256,
        artifact_byte_length=artifact_byte_length,
        retrieval_time=retrieval_time,
        export_time=export_time,
        expected_start_time=expected_start_time,
        expected_end_time=expected_end_time,
        profile_id=profile.profile_id,
    )
    report = run_preflight_from_bytes(manifest, profile, csv_bytes)
    status = _STATUS_MAP[report.status]
    reason_codes = tuple(code.value for code in report.reason_codes)
    return PreflightOutcome(status=status, report=report, reason_codes=reason_codes)


__all__ = [
    "PROVIDER_NAME",
    "PROVIDER_PRODUCT",
    "ENTITLEMENT_ASSERTION",
    "PreflightOutcome",
    "build_profile",
    "build_manifest",
    "run_bundle_preflight",
]
