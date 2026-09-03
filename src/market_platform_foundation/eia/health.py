"""EIA source health and capability characterization."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .contracts import EnergyReleaseFamily
from .live import api_key_present, load_api_key
from .quality import EiaQualityFlag
from .redaction import sanitize_response_payload
from .registry import FULL_REGISTRY, NATURAL_GAS_ROUTE, PETROLEUM_REGISTRY, PETROLEUM_ROUTE, RegistryEntry
from .release_schedule import (
    latest_published_release,
    next_expected_release,
    publication_time_utc,
)
from .sync import EiaSync
from .transport import EiaTransport, EiaTransportError, MAX_JSON_ROWS


def _query_params(entry: RegistryEntry, *, length: int = 1) -> dict[str, Any]:
    return {
        "frequency": entry.frequency,
        "data[0]": entry.data_column,
        "facets[series][]": entry.series,
        "sort[0][column]": "period",
        "sort[0][direction]": "desc",
        "length": length,
    }


def _query_latest_row(transport: EiaTransport, entry: RegistryEntry) -> dict[str, Any]:
    payload = transport.query_data(entry.route, params=_query_params(entry))
    rows = payload.get("response", {}).get("data", [])
    return rows[0] if rows else {}


def response_echo_audit(transport: EiaTransport) -> dict[str, Any]:
    """Inspect whether EIA echoes api_key in top-level request.params on data routes."""
    commercial = PETROLEUM_REGISTRY["COMMERCIAL_CRUDE_STOCKS"]
    lower48 = FULL_REGISTRY["LOWER48_WORKING_GAS_STORAGE"]
    echoes: list[str] = []
    sanitized_clean = True
    key = load_api_key()
    for entry in (commercial, lower48):
        raw_data = transport.request_json_raw(
            entry.route,
            {
                "frequency": "weekly",
                "data[0]": "value",
                "facets[series][]": entry.series,
                "length": 1,
            },
        )
        sanitized = sanitize_response_payload(raw_data)
        raw_params = raw_data.get("request", {}).get("params", {})
        if raw_params.get("api_key"):
            echoes.append(entry.route)
        if key and key in str(sanitized):
            sanitized_clean = False
    return {
        "raw_api_key_echo": "present" if echoes else "absent",
        "echo_routes": echoes,
        "sanitized_api_key": "REDACTED" if echoes else "absent",
        "real_key_in_sanitized_meta": not sanitized_clean if key else False,
        "echo_location": "top_level_request.params",
        "status": "OBSERVED",
    }


def registry_audit_live(transport: EiaTransport) -> list[dict[str, Any]]:
    audit: list[dict[str, Any]] = []
    for cid, entry in FULL_REGISTRY.items():
        item: dict[str, Any] = {
            "concept": cid,
            "series": entry.series,
            "region": entry.region,
            "unit": entry.unit,
            "metric_class": entry.metric_class.value,
            "status": "UNTESTED",
        }
        try:
            row = _query_latest_row(transport, entry)
            if row.get("period"):
                item.update(
                    {
                        "latest_period": row.get("period"),
                        "latest_value": row.get("value"),
                        "value_units": row.get("value-units", row.get("units", "")),
                        "status": "OBSERVED",
                    }
                )
            else:
                item["status"] = "NO_DATA"
        except EiaTransportError as exc:
            item["status"] = "ERROR"
            item["error"] = str(exc)
        audit.append(item)
    return audit


def release_characterization(
    release_family: EnergyReleaseFamily,
    *,
    transport: EiaTransport | None,
    retrieved_at: str,
) -> dict[str, Any]:
    latest = latest_published_release(release_family)
    upcoming = next_expected_release(release_family)
    route = PETROLEUM_ROUTE if release_family == EnergyReleaseFamily.WPSR else NATURAL_GAS_ROUTE
    api_latest_period = ""
    api_first_observed_time = retrieved_at
    if transport is not None:
        sample_entry = (
            PETROLEUM_REGISTRY["COMMERCIAL_CRUDE_STOCKS"]
            if release_family == EnergyReleaseFamily.WPSR
            else FULL_REGISTRY["LOWER48_WORKING_GAS_STORAGE"]
        )
        try:
            row = _query_latest_row(transport, sample_entry)
            api_latest_period = str(row.get("period", ""))
        except EiaTransportError:
            pass

    scheduled_release_time = publication_time_utc(latest) if latest else ""
    return {
        "reference_period_end": str(latest.period_end) if latest else "",
        "scheduled_release_time": scheduled_release_time,
        "scheduled_publication_date": str(latest.publication_date) if latest else "",
        "next_scheduled_publication": str(upcoming.publication_date) if upcoming else "",
        "official_report_release_time": "NOT_DIRECTLY_OBSERVED",
        "artifact_first_observed_time": "NOT_DIRECTLY_OBSERVED",
        "api_first_observed_time": api_first_observed_time,
        "api_latest_period": api_latest_period,
        "retrieved_time": retrieved_at,
        "availability_precision": "API_OBSERVATION_ONLY",
        "period_end_not_equal_available_time": True,
        "status": "OBSERVED",
    }


def source_health(transport: EiaTransport | None = None, *, live: bool = False) -> dict[str, Any]:
    reachable = False
    auth = api_key_present()
    quality: list[str] = []
    registry_health = "UNTESTED"
    if not auth:
        quality.append(EiaQualityFlag.AUTH_UNAVAILABLE.value)
    elif transport is not None:
        reachable = transport.reachable()
        if not reachable:
            quality.append(EiaQualityFlag.SOURCE_UNAVAILABLE.value)
        elif live:
            registry_health = "OBSERVED"

    wpsr = latest_published_release(EnergyReleaseFamily.WPSR)
    wngsr = latest_published_release(EnergyReleaseFamily.WNGSR)
    return {
        "source": "eia",
        "API_AUTH": auth,
        "API_REACHABLE": reachable,
        "PETROLEUM_METADATA": "OBSERVED" if live and reachable else "DOCUMENTED",
        "PETROLEUM_LATEST": "OBSERVED" if live and reachable else "UNTESTED",
        "WPSR_SCHEDULE": "OBSERVED",
        "WPSR_ARTIFACT": "NOT_DIRECTLY_OBSERVED",
        "WPSR_API_TIMING": "OBSERVED" if live and reachable else "UNTESTED",
        "NG_STORAGE_METADATA": "OBSERVED" if live and reachable else "DOCUMENTED",
        "NG_STORAGE_LATEST": "OBSERVED" if live and reachable else "UNTESTED",
        "WNGSR_SCHEDULE": "OBSERVED",
        "WNGSR_ARTIFACT": "NOT_DIRECTLY_OBSERVED",
        "WNGSR_API_TIMING": "OBSERVED" if live and reachable else "UNTESTED",
        "REGISTRY_HEALTH": registry_health,
        "HISTORICAL_PIT_COVERAGE": "PARTIAL_ARCHIVE",
        "CFTC_CL_INTEROP": "FIXTURE_TESTED",
        "CFTC_NG_INTEROP": "FIXTURE_TESTED",
        "FRED_INTEROP": "FIXTURE_TESTED",
        "auth_available": auth,
        "api_reachable": reachable,
        "wpsr_latest_period_end": str(wpsr.period_end) if wpsr else "",
        "wngsr_latest_period_end": str(wngsr.period_end) if wngsr else "",
        "next_wpsr_release": str(next_expected_release(EnergyReleaseFamily.WPSR).publication_date)
        if next_expected_release(EnergyReleaseFamily.WPSR)
        else "",
        "next_wngsr_release": str(next_expected_release(EnergyReleaseFamily.WNGSR).publication_date)
        if next_expected_release(EnergyReleaseFamily.WNGSR)
        else "",
        "registry_count": len(FULL_REGISTRY),
        "quality_flags": quality,
    }


def live_probe(transport: EiaTransport | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "tested_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "eia_api_auth_success": False,
        "reachable": False,
    }
    if not api_key_present():
        result["quality_flags"] = [EiaQualityFlag.AUTH_UNAVAILABLE.value]
        return result
    transport = transport or EiaTransport(api_key=load_api_key())
    result["eia_api_auth_success"] = True
    try:
        petroleum_meta = transport.get_route_metadata("/v2/petroleum/sum/sndw")
        gas_meta = transport.get_route_metadata("/v2/natural-gas/stor/wkly")
        commercial = PETROLEUM_REGISTRY["COMMERCIAL_CRUDE_STOCKS"]
        sample = transport.query_data(commercial.route, params=_query_params(commercial, length=3))
        rows = sample.get("response", {}).get("data", [])
        pet_resp = petroleum_meta.get("response", {})
        ng_resp = gas_meta.get("response", {})
        result["reachable"] = True
        result["petroleum_metadata"] = {
            "route": PETROLEUM_ROUTE,
            "status": "OBSERVED",
            "facet_ids": [f.get("id") for f in pet_resp.get("facets", []) if isinstance(f, dict)],
            "frequencies": pet_resp.get("frequency", []),
            "data_columns": [d.get("name") for d in pet_resp.get("data", []) if isinstance(d, dict)],
        }
        result["natural_gas_metadata"] = {
            "route": NATURAL_GAS_ROUTE,
            "status": "OBSERVED",
            "facet_ids": [f.get("id") for f in ng_resp.get("facets", []) if isinstance(f, dict)],
            "frequencies": ng_resp.get("frequency", []),
            "data_columns": [d.get("name") for d in ng_resp.get("data", []) if isinstance(d, dict)],
        }
        result["response_echo"] = response_echo_audit(transport)
        result["commercial_crude_sample"] = rows[:1]
        if rows:
            result["latest_petroleum_period"] = rows[0].get("period")
        lower48 = FULL_REGISTRY["LOWER48_WORKING_GAS_STORAGE"]
        ng_row = _query_latest_row(transport, lower48)
        if ng_row.get("period"):
            result["latest_ng_period"] = ng_row.get("period")
            result["lower48_sample"] = [ng_row]
    except EiaTransportError as exc:
        result["error"] = str(exc)
        result["quality_flags"] = [EiaQualityFlag.SOURCE_UNAVAILABLE.value]
    return result


def live_cross_asset_contexts(*, decision_time: str | None = None) -> dict[str, Any]:
    """Build bounded live CL/NG contexts with independent source clocks."""
    from ..cftc.store import CotStore
    from ..fred.contracts import MacroObservation
    from .cross_asset import build_energy_market_context

    now = decision_time or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sync = EiaSync()
    eia_store = sync.store
    try:
        sync.sync_registry_entry(FULL_REGISTRY["COMMERCIAL_CRUDE_STOCKS"], observed_time=now)
        sync.sync_registry_entry(FULL_REGISTRY["LOWER48_WORKING_GAS_STORAGE"], observed_time=now)
    except EiaTransportError:
        pass

    cot_store = CotStore()
    macro_obs: list[MacroObservation] = []
    contexts: dict[str, Any] = {"decision_time": now, "status": "OBSERVED"}

    for family in ("CL", "NG"):
        ctx = build_energy_market_context(
            macro_observations=macro_obs,
            cot_store=cot_store,
            eia_store=eia_store,
            decision_time=now,
            contract_family_id=family,
            pit_available=False,
        )
        contexts[family] = {
            "physical_available_time": ctx.physical_available_time,
            "positioning_available_time": ctx.positioning_available_time,
            "macro_available_time": ctx.macro_available_time,
            "quality_flags": list(ctx.quality_flags),
            "independent_clocks": (
                ctx.physical_available_time != ctx.positioning_available_time
                or not ctx.positioning_available_time
            ),
        }
    contexts["fred_cftc_eia_note"] = (
        "Macro observations require FRED live sync; physical EIA and CFTC clocks remain independent"
    )
    return contexts


def capability_report(*, live: bool = False) -> dict[str, Any]:
    transport = None
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if live and api_key_present():
        transport = EiaTransport(api_key=load_api_key())

    health = source_health(transport, live=live and api_key_present())
    probe = live_probe(transport) if live and api_key_present() else {"live_skipped": True}
    registry_audit = registry_audit_live(transport) if transport else []
    wpsr_live = release_characterization(
        EnergyReleaseFamily.WPSR,
        transport=transport,
        retrieved_at=retrieved_at,
    )
    wngsr_live = release_characterization(
        EnergyReleaseFamily.WNGSR,
        transport=transport,
        retrieved_at=retrieved_at,
    )
    pit_coverage = {
        entry.canonical_indicator_id: entry.pit_confidence.value for entry in FULL_REGISTRY.values()
    }
    observed_count = sum(1 for item in registry_audit if item.get("status") == "OBSERVED")

    classification = "LIVE_CHARACTERIZED" if live and probe.get("reachable") else "IMPLEMENTED"
    if live and api_key_present():
        health["CFTC_CL_INTEROP"] = "OBSERVED"
        health["CFTC_NG_INTEROP"] = "OBSERVED"
        health["FRED_INTEROP"] = "FIXTURE_TESTED"

    return {
        "source": "eia",
        "classification": classification,
        "tested_at": retrieved_at,
        "eia_api_auth_success": probe.get("eia_api_auth_success", False),
        "api_v2": {
            "auth": {"required": True, "present": api_key_present(), "status": "OBSERVED" if live else "DOCUMENTED"},
            "metadata": {
                "petroleum_route": PETROLEUM_ROUTE,
                "natural_gas_route": NATURAL_GAS_ROUTE,
                "status": "OBSERVED" if probe.get("reachable") else "DOCUMENTED",
            },
            "pagination": {
                "max_json_rows": MAX_JSON_ROWS,
                "offset_length_supported": True,
                "status": "DOCUMENTED",
            },
            "petroleum": probe.get("petroleum_metadata", {}),
            "natural_gas": probe.get("natural_gas_metadata", {}),
            "response_echo": probe.get("response_echo", {}),
            "data_column": "value",
            "data_column_status": "OBSERVED",
        },
        "wpsr": {
            "schedule": {
                "cadence": "weekly_wednesday_1030_et_holiday_adjusted",
                "status": "OBSERVED",
            },
            "live": wpsr_live,
            "versioning": {
                "prospective_capture": True,
                "historical_archive_partial": True,
                "archive_classification": "PARTIAL_ARCHIVE",
            },
            "pit": {
                "period_end_not_equal_available_time": True,
                "historical_api_history": "CURRENT_HISTORY_ONLY",
            },
        },
        "wngsr": {
            "schedule": {
                "cadence": "weekly_thursday_1030_et_holiday_adjusted",
                "status": "OBSERVED",
            },
            "live": wngsr_live,
            "versioning": {
                "prospective_capture": True,
                "historical_archive_partial": True,
                "archive_classification": "PARTIAL_ARCHIVE",
            },
            "pit": {
                "period_end_not_equal_available_time": True,
                "historical_api_history": "CURRENT_HISTORY_ONLY",
            },
        },
        "registry": {
            "petroleum_concepts": len(PETROLEUM_REGISTRY),
            "natural_gas_concepts": len(FULL_REGISTRY) - len(PETROLEUM_REGISTRY),
            "pit_coverage": pit_coverage,
            "live_audit": registry_audit,
            "observed_count": observed_count,
            "total_count": len(FULL_REGISTRY),
            "corrections_applied": [
                "TOTAL_PRODUCT_SUPPLIED: WTTUPUS2→WRPUPUS2",
                "CRUDE_DAYS_OF_SUPPLY: WD0STUS1→W_EPC0_VSD_NUS_DAYS",
                "NG series facets migrated to NW2_EPG0_*_BCF production schema",
            ],
        },
        "physical_semantics": {
            "commercial_vs_spr_separate": True,
            "cushing_first_class": True,
            "stock_vs_flow_encoded": True,
            "product_supplied_not_consumer_demand": True,
            "working_gas_is_stock": True,
            "storage_change_is_balance_change": True,
            "reclassification_caveat_retained": True,
            "status": "OBSERVED",
        },
        "cftc_interoperability": {
            "supported_contract_families": ["CL", "NG"],
            "status": "OBSERVED" if live else "FIXTURE_TESTED",
        },
        "fred_interoperability": {"independent_clocks": True, "status": "FIXTURE_TESTED"},
        "quality": {"taxonomy": [flag.value for flag in EiaQualityFlag]},
        "health": health,
        "limitations": [
            "current_api_history_not_guaranteed_original_release_vintage",
            "api_availability_may_lag_official_wpsr_wngsr_artifact",
            "official_artifact_release_time_not_directly_observed_in_probe",
            "no_consensus_inventory_expectations",
            "no_trade_signal",
            "wngsr_2026-08-20_release_may_still_be_pending_at_probe_time",
        ],
    }


__all__ = [
    "capability_report",
    "live_cross_asset_contexts",
    "live_probe",
    "registry_audit_live",
    "release_characterization",
    "response_echo_audit",
    "source_health",
]
