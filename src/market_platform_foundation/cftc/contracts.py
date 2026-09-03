"""Provider-neutral institutional positioning contracts for CFTC COT evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CotReportFamily(StrEnum):
    """CFTC COT report taxonomy — families are not interchangeable."""

    TFF = "TFF"
    DISAGGREGATED = "DISAGGREGATED"
    LEGACY = "LEGACY"
    SUPPLEMENTAL_CIT = "SUPPLEMENTAL_CIT"


class CotPositionScope(StrEnum):
    """Futures-only vs combined futures+options — never aggregate both."""

    FUTURES_ONLY = "FUTURES_ONLY"
    FUTURES_AND_OPTIONS_COMBINED = "FUTURES_AND_OPTIONS_COMBINED"


class CotParticipantCategory(StrEnum):
    """Regulatory participant classifications — preserve CFTC terminology."""

    # TFF
    DEALER_INTERMEDIARY = "DEALER_INTERMEDIARY"
    ASSET_MANAGER_INSTITUTIONAL = "ASSET_MANAGER_INSTITUTIONAL"
    LEVERAGED_FUNDS = "LEVERAGED_FUNDS"
    OTHER_REPORTABLES = "OTHER_REPORTABLES"
    NON_REPORTABLES = "NON_REPORTABLES"

    # Disaggregated
    PRODUCER_MERCHANT = "PRODUCER_MERCHANT"
    SWAP_DEALER = "SWAP_DEALER"
    MANAGED_MONEY = "MANAGED_MONEY"
    OTHER_REPORTABLE = "OTHER_REPORTABLE"
    NON_REPORTABLE = "NON_REPORTABLE"

    # Legacy
    COMMERCIAL = "COMMERCIAL"
    NON_COMMERCIAL = "NON_COMMERCIAL"
    NON_REPORTABLE_LEGACY = "NON_REPORTABLE_LEGACY"

    # Supplemental CIT
    COMMODITY_INDEX_TRADER = "COMMODITY_INDEX_TRADER"


@dataclass(frozen=True, slots=True)
class InstitutionalPositioningObservation:
    """Canonical COT positioning row — contract-family level, not expiration."""

    market_id: str
    contract_family_id: str
    cftc_contract_market_code: str
    cftc_commodity_code: str
    market_and_exchange_names: str

    report_family: CotReportFamily
    position_scope: CotPositionScope
    participant_category: CotParticipantCategory

    position_date: str
    publication_time: str
    available_time: str
    observed_time: str

    open_interest: int | None = None
    long_positions: int | None = None
    short_positions: int | None = None
    spreading_positions: int | None = None
    trader_count_long: int | None = None
    trader_count_short: int | None = None
    trader_count_spreading: int | None = None

    source: str = "cftc_cot"
    source_dataset: str = ""
    source_row_id: str = ""
    content_hash: str = ""

    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""
    lifecycle: str = "OBSERVED"
    predictive: bool = False


@dataclass(frozen=True, slots=True)
class InstitutionalPositioningState:
    """Higher-timeframe positioning context for Futures / Market Context lanes."""

    contract_family_id: str
    report_family: CotReportFamily
    position_scope: CotPositionScope
    latest_report_date: str
    publication_time: str
    report_age_days: int | None

    leveraged_or_managed_net: int | None = None
    asset_manager_or_producer_net: int | None = None
    dealer_or_swap_net: int | None = None

    net_percentile_52w: float | None = None
    net_percentile_104w: float | None = None
    weekly_net_change: int | None = None

    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = ""
    predictive: bool = False


def observation_to_dict(obs: InstitutionalPositioningObservation) -> dict[str, Any]:
    return {
        "market_id": obs.market_id,
        "contract_family_id": obs.contract_family_id,
        "cftc_contract_market_code": obs.cftc_contract_market_code,
        "cftc_commodity_code": obs.cftc_commodity_code,
        "market_and_exchange_names": obs.market_and_exchange_names,
        "report_family": obs.report_family.value,
        "position_scope": obs.position_scope.value,
        "participant_category": obs.participant_category.value,
        "position_date": obs.position_date,
        "publication_time": obs.publication_time,
        "available_time": obs.available_time,
        "observed_time": obs.observed_time,
        "open_interest": obs.open_interest,
        "long_positions": obs.long_positions,
        "short_positions": obs.short_positions,
        "spreading_positions": obs.spreading_positions,
        "trader_count_long": obs.trader_count_long,
        "trader_count_short": obs.trader_count_short,
        "trader_count_spreading": obs.trader_count_spreading,
        "source": obs.source,
        "source_dataset": obs.source_dataset,
        "source_row_id": obs.source_row_id,
        "content_hash": obs.content_hash,
        "quality_flags": list(obs.quality_flags),
        "provenance_ref": obs.provenance_ref,
        "lifecycle": obs.lifecycle,
        "predictive": obs.predictive,
    }


def positioning_state_to_dict(state: InstitutionalPositioningState) -> dict[str, Any]:
    return {
        "contract_family_id": state.contract_family_id,
        "report_family": state.report_family.value,
        "position_scope": state.position_scope.value,
        "latest_report_date": state.latest_report_date,
        "publication_time": state.publication_time,
        "report_age_days": state.report_age_days,
        "leveraged_or_managed_net": state.leveraged_or_managed_net,
        "asset_manager_or_producer_net": state.asset_manager_or_producer_net,
        "dealer_or_swap_net": state.dealer_or_swap_net,
        "net_percentile_52w": state.net_percentile_52w,
        "net_percentile_104w": state.net_percentile_104w,
        "weekly_net_change": state.weekly_net_change,
        "quality_flags": list(state.quality_flags),
        "provenance_ref": state.provenance_ref,
        "predictive": state.predictive,
    }


__all__ = [
    "CotParticipantCategory",
    "CotPositionScope",
    "CotReportFamily",
    "InstitutionalPositioningObservation",
    "InstitutionalPositioningState",
    "observation_to_dict",
    "positioning_state_to_dict",
]
