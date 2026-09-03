"""Provider-neutral threshold coverage routing and aggregated state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import (
    ThresholdAuthority,
    ThresholdCoverageState,
    ThresholdCoverageStatus,
    ThresholdStatusObservation,
)
from .features import threshold_duration
from .identity import SymbolMap
from .store import ShortIntelligenceStore

AUTHORITY_ALIASES = {
    "NASDAQ": ThresholdAuthority.NASDAQ,
    "NYSE": ThresholdAuthority.NYSE_GROUP,
    "NYSE_GROUP": ThresholdAuthority.NYSE_GROUP,
    "NYSE_AMERICAN": ThresholdAuthority.NYSE_GROUP,
    "NYSE ARCA": ThresholdAuthority.NYSE_GROUP,
    "NYSE_ARCA": ThresholdAuthority.NYSE_GROUP,
    "OTC": ThresholdAuthority.FINRA_OTC,
    "FINRA_OTC": ThresholdAuthority.FINRA_OTC,
    "CBOE": ThresholdAuthority.CBOE_BZX,
    "CBOE_BZX": ThresholdAuthority.CBOE_BZX,
    "BZX": ThresholdAuthority.CBOE_BZX,
}

SOURCE_SRO_TO_AUTHORITY = {
    "NASDAQ": ThresholdAuthority.NASDAQ,
    "NYSE_GROUP": ThresholdAuthority.NYSE_GROUP,
    "FINRA_OTC": ThresholdAuthority.FINRA_OTC,
    "CBOE_BZX": ThresholdAuthority.CBOE_BZX,
}


@dataclass(frozen=True, slots=True)
class ThresholdSourceHealth:
    authority: ThresholdAuthority
    last_successful_retrieval: str
    last_list_date_observed: str
    expected_latest_date: str
    publication_pending: bool
    parse_health: str
    coverage_state: ThresholdCoverageStatus
    source_version: str


def resolve_listing_authority(symbol_map: SymbolMap, symbol: str, *, as_of: str) -> ThresholdCoverageState:
    resolved = symbol_map.resolve(symbol, as_of=as_of)
    if "IDENTITY_UNRESOLVED" in resolved.quality_flags or not resolved.listing_authority:
        return ThresholdCoverageState(
            authority=ThresholdAuthority.NASDAQ,
            status=ThresholdCoverageStatus.IDENTITY_UNRESOLVED,
            listing_market="",
            note="listing authority unknown at as_of",
        )
    authority = AUTHORITY_ALIASES.get(resolved.listing_authority.strip().upper())
    if authority is None:
        return ThresholdCoverageState(
            authority=ThresholdAuthority.NASDAQ,
            status=ThresholdCoverageStatus.HISTORICAL_COVERAGE_UNKNOWN,
            listing_market=resolved.listing_authority,
            note="unsupported listing authority mapping",
        )
    return ThresholdCoverageState(
        authority=authority,
        status=ThresholdCoverageStatus.NOT_APPLICABLE,
        listing_market=resolved.listing_authority,
        note="routing only; source availability determined separately",
    )


def relevant_authority_for_symbol(symbol_map: SymbolMap, symbol: str, *, as_of: str) -> ThresholdAuthority | None:
    state = resolve_listing_authority(symbol_map, symbol, as_of=as_of)
    if state.status == ThresholdCoverageStatus.IDENTITY_UNRESOLVED:
        return None
    if state.status == ThresholdCoverageStatus.HISTORICAL_COVERAGE_UNKNOWN:
        return None
    return state.authority


def nyse_market_for_authority(listing_authority: str) -> str:
    normalized = listing_authority.strip().upper()
    if normalized in {"NYSE_AMERICAN", "AMEX"}:
        return "NYSE American"
    if normalized in {"NYSE_ARCA", "ARCA"}:
        return "NYSE Arca"
    return "NYSE"


def threshold_observations_for_authority(
    store: ShortIntelligenceStore,
    instrument_id: str,
    as_of: str,
    authority: ThresholdAuthority,
) -> tuple[ThresholdStatusObservation, ...]:
    rows = store.threshold_as_of(instrument_id, as_of)
    wanted = {
        ThresholdAuthority.NASDAQ: {"NASDAQ"},
        ThresholdAuthority.NYSE_GROUP: {"NYSE_GROUP"},
        ThresholdAuthority.FINRA_OTC: {"FINRA_OTC"},
        ThresholdAuthority.CBOE_BZX: {"CBOE_BZX"},
    }[authority]
    return tuple(row for row in rows if row.source_sro in wanted)


def threshold_coverage_as_of(
    store: ShortIntelligenceStore,
    symbol_map: SymbolMap,
    *,
    instrument_id: str,
    provider_symbol: str,
    as_of: str,
    trade_date: str,
    source_outage: dict[ThresholdAuthority, bool] | None = None,
    holiday: bool = False,
) -> ThresholdCoverageState:
    routing = resolve_listing_authority(symbol_map, provider_symbol, as_of=trade_date)
    authority = routing.authority
    if routing.status == ThresholdCoverageStatus.IDENTITY_UNRESOLVED:
        return ThresholdCoverageState(
            authority=authority,
            status=ThresholdCoverageStatus.IDENTITY_UNRESOLVED,
            listing_market=routing.listing_market,
        )
    if routing.status == ThresholdCoverageStatus.HISTORICAL_COVERAGE_UNKNOWN:
        return ThresholdCoverageState(
            authority=authority,
            status=ThresholdCoverageStatus.HISTORICAL_COVERAGE_UNKNOWN,
            listing_market=routing.listing_market,
        )
    if holiday:
        return ThresholdCoverageState(
            authority=authority,
            status=ThresholdCoverageStatus.NOT_APPLICABLE,
            listing_market=routing.listing_market,
            note="non-settlement day; no list expected",
        )
    if source_outage and source_outage.get(authority):
        return ThresholdCoverageState(
            authority=authority,
            status=ThresholdCoverageStatus.SOURCE_UNAVAILABLE,
            listing_market=routing.listing_market,
        )
    rows = threshold_observations_for_authority(store, instrument_id, as_of, authority)
    dated = [row for row in rows if row.trade_date == trade_date[:10]]
    if not dated:
        return ThresholdCoverageState(
            authority=authority,
            status=ThresholdCoverageStatus.UNKNOWN,
            listing_market=routing.listing_market,
            note="relevant source not yet observed for trade_date",
        )
    latest = max(dated, key=lambda row: (row.clocks.get("available_time", ""), row.record_version))
    absent = "SOURCE_COVERAGE_CONFIRMED_ABSENT" in latest.quality_flags
    if absent and not latest.currently_threshold:
        return ThresholdCoverageState(
            authority=authority,
            status=ThresholdCoverageStatus.COVERED,
            listing_market=routing.listing_market,
            source_market=latest.source_market,
            note="confirmed non-membership for source",
        )
    return ThresholdCoverageState(
        authority=authority,
        status=ThresholdCoverageStatus.COVERED,
        listing_market=routing.listing_market,
        source_market=latest.source_market,
    )


def threshold_state_as_of(
    store: ShortIntelligenceStore,
    symbol_map: SymbolMap,
    *,
    instrument_id: str,
    provider_symbol: str,
    as_of: str,
    source_outage: dict[ThresholdAuthority, bool] | None = None,
    holiday: bool = False,
) -> dict[str, Any]:
    routing = resolve_listing_authority(symbol_map, provider_symbol, as_of=as_of)
    authority = routing.authority
    if routing.status in {
        ThresholdCoverageStatus.IDENTITY_UNRESOLVED,
        ThresholdCoverageStatus.HISTORICAL_COVERAGE_UNKNOWN,
    }:
        return {
            "status": "UNKNOWN",
            "authority": authority.value,
            "listing_market": routing.listing_market,
            "coverage_status": routing.status.value,
            "currently_threshold": None,
            "available_time": "",
            "quality_flags": list(routing.status.value),
        }
    if source_outage and source_outage.get(authority):
        return {
            "status": "SOURCE_UNAVAILABLE",
            "authority": authority.value,
            "listing_market": routing.listing_market,
            "coverage_status": ThresholdCoverageStatus.SOURCE_UNAVAILABLE.value,
            "currently_threshold": None,
            "available_time": "",
            "quality_flags": ["SOURCE_UNAVAILABLE"],
        }
    if holiday:
        return {
            "status": "NOT_APPLICABLE",
            "authority": authority.value,
            "listing_market": routing.listing_market,
            "coverage_status": ThresholdCoverageStatus.NOT_APPLICABLE.value,
            "currently_threshold": None,
            "available_time": "",
            "quality_flags": ["NON_SETTLEMENT_DAY"],
        }
    rows = threshold_observations_for_authority(store, instrument_id, as_of, authority)
    if not rows:
        return {
            "status": "UNKNOWN",
            "authority": authority.value,
            "listing_market": routing.listing_market,
            "coverage_status": ThresholdCoverageStatus.UNKNOWN.value,
            "currently_threshold": None,
            "available_time": "",
            "quality_flags": ["THRESHOLD_UNKNOWN"],
        }
    latest = rows[-1]
    duration = threshold_duration(rows)
    return {
        "status": "AVAILABLE",
        "authority": authority.value,
        "listing_market": routing.listing_market,
        "source_market": latest.source_market,
        "trade_date": latest.trade_date,
        "currently_threshold": latest.currently_threshold,
        "coverage_status": ThresholdCoverageStatus.COVERED.value,
        "available_time": latest.clocks.get("available_time", ""),
        "reg_sho_threshold_flag": latest.reg_sho_threshold_flag,
        "rule_4320_flag": latest.rule_4320_flag,
        "threshold_list_flag": latest.threshold_list_flag,
        "consecutive_observed_threshold_days": duration.get("consecutive_observed_threshold_days"),
        "days_since_entered": duration.get("days_since_entered"),
        "days_since_exited": duration.get("days_since_exited"),
        "quality_flags": list(latest.quality_flags),
        "provenance": latest.source_sro,
        "record_version": latest.record_version,
    }


def cross_source_reconciliation(
    store: ShortIntelligenceStore,
    instrument_id: str,
    as_of: str,
) -> dict[str, Any]:
    threshold_rows = store.threshold_as_of(instrument_id, as_of)
    latest_by_source: dict[str, ThresholdStatusObservation] = {}
    for row in threshold_rows:
        latest_by_source[row.source_sro] = row
    ftd = store.latest_ftd(instrument_id, as_of)
    si = store.short_interest_as_of(instrument_id, as_of)
    flow = store.short_sale_as_of(instrument_id, as_of)
    return {
        "instrument_id": instrument_id,
        "as_of": as_of,
        "threshold_by_source": {
            source: {
                "currently_threshold": row.currently_threshold,
                "trade_date": row.trade_date,
                "available_time": row.clocks.get("available_time", ""),
                "authority": source,
            }
            for source, row in latest_by_source.items()
        },
        "ftd_balance_as_known": {
            "status": "AVAILABLE" if ftd else "UNKNOWN",
            "quantity": ftd.ftd_balance_quantity if ftd else None,
            "available_time": ftd.clocks.get("available_time", "") if ftd else "",
        },
        "short_interest_as_known": {
            "status": "AVAILABLE" if si else "UNKNOWN",
            "quantity": si.current_short_position_quantity if si else None,
            "available_time": si.clocks.get("available_time", "") if si else "",
        },
        "short_sale_flow_as_known": {
            "status": "AVAILABLE" if flow else "UNKNOWN",
            "row_count": len(flow),
            "latest_available_time": flow[-1].clocks.get("available_time", "") if flow else "",
        },
    }


def aggregate_threshold_health(
    *,
    source_health: dict[ThresholdAuthority, ThresholdSourceHealth],
    listing_authority_known: bool,
) -> str:
    if not listing_authority_known:
        return "UNKNOWN_LISTING_AUTHORITY"
    states = [item.coverage_state for item in source_health.values()]
    if any(state == ThresholdCoverageStatus.SOURCE_UNAVAILABLE for state in states):
        return "PARTIAL_COVERAGE"
    if states and all(state == ThresholdCoverageStatus.COVERED for state in states):
        return "RELEVANT_SOURCE_HEALTHY"
    return "PARTIAL_COVERAGE"
