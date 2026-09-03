"""Independent NOAA/NWS/CPC source health and capability characterization."""

from __future__ import annotations

import os
from typing import Any

from .ndfd import NDFD_DECODE_STATUS, NDFD_PERIOD_OF_RECORD_START
from .quality import WeatherQualityFlag
from .store import WeatherStore


def source_health(*, store: WeatherStore | None = None, live: bool = False) -> dict[str, Any]:
    store = store or WeatherStore()
    observed = "OBSERVED" if live else "UNTESTED"
    return {
        "source_family": "noaa_nws_cpc",
        "NWS_API_REACHABLE": observed,
        "POINT_MAPPING_HEALTH": observed,
        "GRID_FORECAST_HEALTH": observed,
        "HOURLY_FORECAST_HEALTH": observed,
        "GRID_DATA_HEALTH": observed,
        "OBSERVATION_HEALTH": observed,
        "CPC_REALIZED_DEGREE_DAYS": "FIXTURE_TESTED",
        "CPC_7DAY_FORECAST": "FIXTURE_TESTED",
        "CPC_FORECAST_ARCHIVE": "DOCUMENTED",
        "CPC_CLIMATOLOGY": "FIXTURE_TESTED",
        "CPC_610_OUTLOOK": "CHARACTERIZED_DEFERRED",
        "CPC_814_OUTLOOK": "CHARACTERIZED_DEFERRED",
        "NDFD_ARCHIVE_REACHABLE": observed,
        "NDFD_PERIOD_OF_RECORD": NDFD_PERIOD_OF_RECORD_START,
        "NDFD_DECODE_CAPABILITY": "DEFERRED",
        "ENERGY_MARKET_CONTEXT": "FIXTURE_TESTED",
        "forecast_count": len(store.forecasts),
        "realization_count": len(store.realizations),
        "reference_count": len(store.references),
        "quality_flags": [WeatherQualityFlag.ARCHIVE_AVAILABLE_DECODE_DEFERRED.value],
    }


def capability_report(*, live: bool = False, store: WeatherStore | None = None) -> dict[str, Any]:
    health = source_health(store=store, live=live)
    cdo_available = bool(os.environ.get("NOAA_CDO_TOKEN", "").strip())
    return {
        "source_family": "noaa_nws_cpc",
        "classification": "LIVE_CHARACTERIZED" if live else "IMPLEMENTED_OFFLINE",
        "credential_access": {
            "nws_auth": "PUBLIC_USER_AGENT_REQUIRED",
            "nws_user_agent_override": "IMP_NWS_USER_AGENT",
            "cpc_access": "PUBLIC",
            "ndfd_access": "PUBLIC",
            "cdo_live_validation": "AVAILABLE" if cdo_available else "DEFERRED_TOKEN_UNAVAILABLE",
        },
        "nws_api": {
            "current_forecast": {"status": health["GRID_FORECAST_HEALTH"]},
            "hourly": {"status": health["HOURLY_FORECAST_HEALTH"]},
            "grid": {"status": health["GRID_DATA_HEALTH"]},
            "observations": {"status": health["OBSERVATION_HEALTH"]},
            "mapping_revalidation": True,
            "historical_forecast_truth": False,
        },
        "cpc_degree_days": {
            "realized": {"status": health["CPC_REALIZED_DEGREE_DAYS"], "archive_start": "1981"},
            "forecast_7day": {"status": health["CPC_7DAY_FORECAST"], "target_days": 7},
            "forecast_archive": {"status": health["CPC_FORECAST_ARCHIVE"], "start": "2014-01-01", "known_directory_gaps": 52},
            "climatology": {"status": health["CPC_CLIMATOLOGY"], "normal_period": "1981-2010"},
            "weightings": {"population_vintage": "2010_CENSUS", "utility_gas_vintage": "2010_ACS", "kept_separate": True},
            "regions": ["STATE", "CENSUS_DIVISION", "CLIMATE_DIVISION", "CONUS"],
        },
        "forecast_vintage": {
            "pit": {"issue_available_target_separate": True},
            "revisions": {"distinct_issues_are_vintages": True, "same_issue_correction_is_knowledge_version": True},
            "realizations": {"separate_evidence_family": True, "forecast_error_gated": True},
        },
        "ndfd_archive": {
            "period_of_record_start": NDFD_PERIOD_OF_RECORD_START,
            "cloud_access_start": "2020-04-16",
            "decode_capability": NDFD_DECODE_STATUS,
            "bulk_download": False,
        },
        "medium_range": {
            "six_to_ten_day": "CHARACTERIZED",
            "eight_to_fourteen_day": "CHARACTERIZED",
            "semantics": "TERCILE_PROBABILITIES_NOT_TEMPERATURE_MAGNITUDES",
            "implementation": "CHARACTERIZED_PROSPECTIVE_DEFERRED",
        },
        "energy_interoperability": {
            "natural_gas_priority": True,
            "fred_clock_independent": True,
            "cftc_clock_independent": True,
            "eia_clock_independent": True,
            "weather_clock_independent": True,
            "composite_score": False,
        },
        "quality": {"health": health, "taxonomy": [flag.value for flag in WeatherQualityFlag]},
        "limitations": [
            "degree_days_are_demand_proxies",
            "historical_archive_availability_can_be_inferred",
            "realized_annual_files_are_mutable",
            "1981_2010_normals_and_2010_weights_are_stale",
            "ndfd_grib2_decode_deferred",
            "nws_observations_can_be_delayed",
            "no_market_consensus",
        ],
    }


__all__ = ["capability_report", "source_health"]
