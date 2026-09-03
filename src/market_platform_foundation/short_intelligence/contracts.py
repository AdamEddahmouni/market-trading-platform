"""Canonical short-intelligence observations. These families are not interchangeable."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ObservationFamily(StrEnum):
    SHORT_INTEREST = "SHORT_INTEREST"
    SHORT_SALE_VOLUME = "SHORT_SALE_VOLUME"
    THRESHOLD_STATUS = "THRESHOLD_STATUS"
    FAILS_TO_DELIVER = "FAILS_TO_DELIVER"


class AvailabilityState(StrEnum):
    AVAILABLE = "AVAILABLE"
    NOT_YET_PUBLISHED = "NOT_YET_PUBLISHED"
    NO_RECORD = "NO_RECORD"
    EMPTY_RESULT = "EMPTY_RESULT"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    AUTH_UNAVAILABLE = "AUTH_UNAVAILABLE"
    AUTH_FAILED = "AUTH_FAILED"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    OUTSIDE_DATASET_HISTORY = "OUTSIDE_DATASET_HISTORY"
    COVERAGE_UNAVAILABLE = "COVERAGE_UNAVAILABLE"


class CredentialHealthState(StrEnum):
    HEALTHY = "HEALTHY"
    ROTATION_DUE = "ROTATION_DUE"
    ROTATION_URGENT = "ROTATION_URGENT"
    EXPIRED = "EXPIRED"
    AUTH_FAILED = "AUTH_FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ShortInterestObservation:
    """Outstanding reported short position snapshot. Not trading flow."""

    observation_family: ObservationFamily
    instrument_id: str
    provider_symbol: str
    settlement_date: str
    publication_date: str
    current_short_position_quantity: int | None
    previous_short_position_quantity: int | None
    short_position_delta: int | None
    short_position_pct_change: float | None
    average_daily_volume_quantity: int | None
    days_to_cover_provider: float | None
    market_class_code: str
    stock_split_flag: str | None
    revision_flag: str | None
    issue_name: str
    provider: str
    source_dataset: str
    record_version: int
    clocks: dict[str, str]
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    raw_payload_hash: str = ""
    finra_request_id: str = ""
    lifecycle: str = "CAPTURED"

    def __post_init__(self) -> None:
        if self.observation_family != ObservationFamily.SHORT_INTEREST:
            raise ValueError("SHORT_INTEREST_FAMILY_REQUIRED")


@dataclass(frozen=True, slots=True)
class ShortSaleVolumeObservation:
    """FINRA-reported short-marked trade volume (flow). Not short interest."""

    observation_family: ObservationFamily
    instrument_id: str
    provider_symbol: str
    trade_report_date: str
    reporting_facility_code: str
    market_code: str
    short_sale_volume: int | None
    short_exempt_volume: int | None
    finra_reported_total_volume: int | None
    finra_reported_short_sale_ratio: float | None
    provider: str
    source_dataset: str
    clocks: dict[str, str]
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    raw_payload_hash: str = ""
    finra_request_id: str = ""
    lifecycle: str = "CAPTURED"

    def __post_init__(self) -> None:
        if self.observation_family != ObservationFamily.SHORT_SALE_VOLUME:
            raise ValueError("SHORT_SALE_VOLUME_FAMILY_REQUIRED")


class ThresholdAuthority(StrEnum):
    NASDAQ = "NASDAQ"
    NYSE_GROUP = "NYSE_GROUP"
    FINRA_OTC = "FINRA_OTC"
    CBOE_BZX = "CBOE_BZX"


class ThresholdCoverageStatus(StrEnum):
    COVERED = "COVERED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    NOT_YET_PUBLISHED = "NOT_YET_PUBLISHED"
    HISTORICAL_COVERAGE_UNKNOWN = "HISTORICAL_COVERAGE_UNKNOWN"
    IDENTITY_UNRESOLVED = "IDENTITY_UNRESOLVED"
    NOT_THRESHOLD = "NOT_THRESHOLD"
    THRESHOLD = "THRESHOLD"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ThresholdCoverageState:
    authority: ThresholdAuthority
    status: ThresholdCoverageStatus
    listing_market: str = ""
    source_market: str = ""
    note: str = ""


@dataclass(frozen=True, slots=True)
class ThresholdStatusObservation:
    """Reg SHO threshold membership/status. Not short interest and not FTD quantity."""

    observation_family: ObservationFamily
    instrument_id: str
    provider_symbol: str
    trade_date: str
    currently_threshold: bool
    source_sro: str
    listing_coverage: str
    market_category: str
    security_name: str
    rule_3210_flag: str | None
    file_creation_time: str
    content_hash: str
    parser_version: str
    clocks: dict[str, str]
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    lifecycle: str = "CAPTURED"
    reg_sho_threshold_flag: str | None = None
    rule_4320_flag: str | None = None
    threshold_list_flag: str | None = None
    source_market: str = ""
    source_file_or_request_id: str = ""
    record_version: int = 1

    def __post_init__(self) -> None:
        if self.observation_family != ObservationFamily.THRESHOLD_STATUS:
            raise ValueError("THRESHOLD_STATUS_FAMILY_REQUIRED")


@dataclass(frozen=True, slots=True)
class FailsToDeliverObservation:
    """SEC-published aggregate net FTD balance outstanding. Not flow, not short interest."""

    observation_family: ObservationFamily
    instrument_id: str
    raw_symbol: str
    cusip: str
    settlement_date: str
    ftd_balance_quantity: int
    previous_day_price: float | None
    approx_ftd_notional_sec_price: float | None
    issuer_description: str
    source: str
    source_file_id: str
    source_period: str
    content_hash: str
    parser_version: str
    clocks: dict[str, str]
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    raw_payload_hash: str = ""
    lifecycle: str = "CAPTURED"

    def __post_init__(self) -> None:
        if self.observation_family != ObservationFamily.FAILS_TO_DELIVER:
            raise ValueError("FAILS_TO_DELIVER_FAMILY_REQUIRED")


@dataclass(frozen=True, slots=True)
class ShortPressureState:
    """Coarse structural context. Missing families remain UNKNOWN. Not a squeeze score."""

    instrument_id: str
    as_of: str
    structural_short_crowding: str
    short_interest_direction: str
    days_to_cover: str | float | None
    recent_short_sale_flow: str
    short_flow_persistence: str
    threshold_status: str
    threshold_duration: int | None
    fails_to_deliver: str
    ftd_balance_quantity: int | None
    borrow_state: str
    cost_to_borrow: str
    locate_state: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance: tuple[str, ...] = field(default_factory=tuple)


def observation_to_dict(row: object) -> dict[str, Any]:
    if hasattr(row, "__dict__"):
        payload = dict(row.__dict__)
    else:
        payload = {key: getattr(row, key) for key in getattr(row, "__slots__", ())}
    payload["observation_family"] = str(payload.get("observation_family", ""))
    payload["quality_flags"] = list(payload.get("quality_flags") or ())
    return payload


__all__ = [
    "AvailabilityState",
    "CredentialHealthState",
    "FailsToDeliverObservation",
    "ObservationFamily",
    "ShortInterestObservation",
    "ShortPressureState",
    "ShortSaleVolumeObservation",
    "ThresholdAuthority",
    "ThresholdCoverageState",
    "ThresholdCoverageStatus",
    "ThresholdStatusObservation",
    "observation_to_dict",
]
