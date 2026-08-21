"""Independent Cboe public options statistics health and capability reporting."""

from __future__ import annotations

from typing import Any

from .historical import characterize_historical_volume_download
from .quality import CboeOptionsQualityFlag
from .store import CboeOptionsStore
from .transport import CboeOptionsTransport


def source_health(*, store: CboeOptionsStore | None = None, live: bool = False) -> dict[str, Any]:
    store = store or CboeOptionsStore()
    observed = "OBSERVED" if live else "UNTESTED"
    return {
        "source_family": "cboe_public_options_statistics",
        "DAILY_STATISTICS": observed,
        "MARKET_VOLUME_SUMMARY": observed,
        "CBOE_INTRADAY_STATISTICS": observed,
        "SYMBOL_DATA_C1": observed,
        "SYMBOL_DATA_BZX": observed,
        "SYMBOL_DATA_C2": observed,
        "SYMBOL_DATA_EDGX": observed,
        "REFERENCE_DATA": observed,
        "HISTORICAL_VOLUME": "CHARACTERIZED",
        "NET_OPTION_PREMIUM": "CHARACTERIZED_DEFERRED",
        "VOL_SETTLEMENT_EOI": "DEFERRED_SPECIALIZED",
        "PIT_COVERAGE": "IMPLEMENTED",
        "OPTIONS_INTEROPERABILITY": "IMPLEMENTED",
        "statistic_count": len(store.statistics),
        "snapshot_count": len(store.snapshots),
        "reference_count": len(store.references),
        "quality_flags": [
            CboeOptionsQualityFlag.DIRECTION_UNKNOWN.value,
            CboeOptionsQualityFlag.OPEN_CLOSE_UNKNOWN.value,
        ],
    }


def capability_report(*, live: bool = False, store: CboeOptionsStore | None = None) -> dict[str, Any]:
    health = source_health(store=store, live=live)
    historical = characterize_historical_volume_download()
    transport = CboeOptionsTransport()
    return {
        "source": "cboe_public_options_statistics",
        "daily_statistics": {
            "status": health["DAILY_STATISTICS"],
            "url": transport.daily_statistics_url(),
            "coverage_scope": "CBOE_EXCHANGES",
            "semantics": "aggregate_put_call_volume_oi_not_signed_flow",
        },
        "market_volume": {
            "status": health["MARKET_VOLUME_SUMMARY"],
            "url": transport.market_volume_url(),
            "publisher": "CBOE",
            "market_coverage": "US_OPTIONS_MARKET",
            "delay_policy": "DELAYED_DATA_MINIMUM_20_MINUTES",
        },
        "intraday_exchange_statistics": {
            "status": health["CBOE_INTRADAY_STATISTICS"],
            "url": transport.intraday_statistics_url(),
            "timezone": "America/Chicago",
            "semantics": "cumulative_not_signed_flow",
        },
        "symbol_data": {
            "c1": {"status": health["SYMBOL_DATA_C1"], "url": transport.symbol_data_url("c1")},
            "bzx": {"status": health["SYMBOL_DATA_BZX"], "url": transport.symbol_data_url("bzx")},
            "c2": {"status": health["SYMBOL_DATA_C2"], "url": transport.symbol_data_url("c2")},
            "edgx": {"status": health["SYMBOL_DATA_EDGX"], "url": transport.symbol_data_url("edgx")},
            "scope": "EXCHANGE_SPECIFIC_NOT_OPRA",
            "quotes": "EXCHANGE_BID_ASK_NOT_NBBO",
        },
        "reference_data": {
            "status": health["REFERENCE_DATA"],
            "categories": list(("all_series", "underlying", "market_maker_registered", "constituent_series")),
            "versioning": "content_hash",
        },
        "historical_volume": {
            "status": historical.status,
            "form_url": historical.form_url,
            "archive_url": transport.historical_pc_archive_url(),
            "exchange_coverage": historical.exchange_coverage,
            "aggregation_modes": list(historical.aggregation_modes),
            "metric_modes": list(historical.metric_modes),
            "notes": list(historical.notes),
        },
        "net_option_premium": {
            "status": health["NET_OPTION_PREMIUM"],
            "decision": "CHARACTERIZED_DEFERRED_AMBIGUOUS",
        },
        "volatility_settlement_eoi": {
            "status": health["VOL_SETTLEMENT_EOI"],
            "decision": "DEFERRED_SPECIALIZED",
        },
        "pit": {
            "coverage": health["PIT_COVERAGE"],
            "reference_kind": "OPTIONS_OI",
            "daily_availability_clock": "available_time",
            "intraday_bucket_clock": "bucket_end",
        },
        "coverage": {
            "daily_statistics": "CBOE_EXCHANGES",
            "market_volume": "US_OPTIONS_MARKET",
            "symbol_data": "EXCHANGE_SPECIFIC",
        },
        "licensing": {
            "terms_reviewed": "DOCUMENTED",
            "attribution_required_or_requested": True,
            "raw_redistribution_status": "RESTRICTED_REVIEW_REQUIRED",
            "internal_research_status": "AUTHORIZED_FOR_PLATFORM_DEVELOPMENT",
            "paid_source_boundary": "DATASHOP_NOT_USED",
        },
        "options_interoperability": {
            "status": health["OPTIONS_INTEROPERABILITY"],
            "complements_option_chain_lane": True,
            "replaces_iv_greeks": False,
            "composite_score": False,
        },
        "health": health,
        "limitations": [
            "put_call_ratio_is_not_direction",
            "volume_is_not_open_interest",
            "publisher_is_not_execution_venue_for_market_share",
            "exchange_symbol_data_is_not_consolidated_opra",
            "exchange_quotes_are_not_nbbo",
            "delayed_data_is_not_real_time",
            "opening_closing_and_aggressor_direction_unknown",
            "historical_publication_time_may_be_unknown",
        ],
    }


__all__ = ["capability_report", "source_health"]
