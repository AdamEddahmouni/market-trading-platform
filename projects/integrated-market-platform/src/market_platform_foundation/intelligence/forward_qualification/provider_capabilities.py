"""Provider capability inventory for forward qualification (BUILD 26)."""

from __future__ import annotations

import os
from typing import Any

from market_platform_foundation.market_data.connectivity import opend_reachable
from market_platform_foundation.market_data.live_config import (
    moomoo_host,
    moomoo_live_enabled,
    moomoo_port,
)

from .types import ProviderCapabilityEntryV1, ProviderRuntimeStatus


def _finviz_elite_configured() -> bool:
    token = os.environ.get("FINVIZ_ELITE_TOKEN") or os.environ.get("IMP_FINVIZ_ELITE_TOKEN")
    return bool(token and token.strip())


def _ibkr_configured() -> bool:
    return os.environ.get("IMP_IBKR_ENABLED", "").strip().lower() in {"1", "true", "yes"}


def probe_moomoo_capabilities() -> list[ProviderCapabilityEntryV1]:
    configured = moomoo_live_enabled()
    reachable = opend_reachable(host=moomoo_host(), port=moomoo_port())
    if not configured:
        runtime = ProviderRuntimeStatus.NOT_CONFIGURED
        eligible = False
        notes = "IMP_MOOMOO_LIVE not enabled"
    elif reachable:
        runtime = ProviderRuntimeStatus.CONNECTED_LIVE
        eligible = True
        notes = f"OpenD reachable at {moomoo_host()}:{moomoo_port()}"
    else:
        runtime = ProviderRuntimeStatus.CONFIGURED_NOT_AVAILABLE
        eligible = False
        notes = f"OpenD not reachable at {moomoo_host()}:{moomoo_port()}"

    base = {
        "provider_id": "MOOMOO",
        "market": "US",
        "instrument_class": "EQUITY",
        "delivery_mode": "REAL_TIME" if runtime == ProviderRuntimeStatus.CONNECTED_LIVE else "UNAVAILABLE",
        "streaming": runtime == ProviderRuntimeStatus.CONNECTED_LIVE,
        "timestamp_semantics": "provider_event_time_plus_local_receive",
        "available_time_semantics": "BUILD_02_PIT",
        "entitlement_status": "PROBE_REQUIRED" if configured else "NOT_CONFIGURED",
        "runtime_availability": runtime,
        "qualification_eligible": eligible,
        "notes": notes,
    }
    return [
        ProviderCapabilityEntryV1(capability="US_EQUITY_L1", **base),
        ProviderCapabilityEntryV1(capability="US_EQUITY_TICKS", **base),
        ProviderCapabilityEntryV1(capability="US_EQUITY_BARS", **base),
    ]


def probe_ibkr_capabilities() -> list[ProviderCapabilityEntryV1]:
    configured = _ibkr_configured()
    runtime = (
        ProviderRuntimeStatus.CONFIGURED_NOT_AVAILABLE
        if configured
        else ProviderRuntimeStatus.NOT_CONFIGURED
    )
    return [
        ProviderCapabilityEntryV1(
            provider_id="IBKR",
            capability="US_EQUITY_L1",
            market="US",
            instrument_class="EQUITY",
            delivery_mode="DELAYED_OR_LIVE",
            streaming=False,
            timestamp_semantics="provider_event_time",
            available_time_semantics="BUILD_02_PIT",
            entitlement_status="GATEWAY_REQUIRED",
            runtime_availability=runtime,
            qualification_eligible=False,
            notes="Observational only; no order submission in BUILD 26",
        )
    ]


def probe_finviz_capabilities() -> list[ProviderCapabilityEntryV1]:
    elite = _finviz_elite_configured()
    runtime = (
        ProviderRuntimeStatus.CONNECTED_POLLING
        if elite
        else ProviderRuntimeStatus.NOT_CONFIGURED
    )
    return [
        ProviderCapabilityEntryV1(
            provider_id="FINVIZ_ELITE",
            capability="SCREENER_CONTEXT",
            market="US",
            instrument_class="EQUITY",
            delivery_mode="POLLING",
            streaming=False,
            timestamp_semantics="fetch_time",
            available_time_semantics="fetch_time",
            entitlement_status="ELITE" if elite else "FINVIZ_ELITE_NOT_CONFIGURED",
            runtime_availability=runtime,
            qualification_eligible=False,
            notes="Discovery/context only; not primary forward market data",
        )
    ]


def probe_all_provider_capabilities() -> tuple[ProviderCapabilityEntryV1, ...]:
    entries: list[ProviderCapabilityEntryV1] = []
    entries.extend(probe_moomoo_capabilities())
    entries.extend(probe_ibkr_capabilities())
    entries.extend(probe_finviz_capabilities())
    entries.append(
        ProviderCapabilityEntryV1(
            provider_id="INTERNAL",
            capability="FIXTURE_REPLAY",
            market="US",
            instrument_class="EQUITY",
            delivery_mode="REPLAY",
            streaming=False,
            timestamp_semantics="fixture_event_time",
            available_time_semantics="BUILD_02_PIT",
            entitlement_status="ALWAYS_AVAILABLE",
            runtime_availability=ProviderRuntimeStatus.CONNECTED_REPLAY_ONLY,
            qualification_eligible=True,
            notes="Deterministic fixture qualification path",
        )
    )
    return tuple(entries)


def provider_capability_matrix() -> dict[str, Any]:
    entries = probe_all_provider_capabilities()
    return {
        "schema_version": "1",
        "providers": [entry.to_dict() for entry in entries],
        "qualification_eligible_providers": sorted(
            {entry.provider_id for entry in entries if entry.qualification_eligible}
        ),
    }
