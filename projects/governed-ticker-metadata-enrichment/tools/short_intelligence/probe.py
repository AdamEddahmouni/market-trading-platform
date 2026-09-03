"""Bounded live/fixture capability probe. Never prints credentials or tokens."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import write_canonical_json
from market_platform_foundation.finra.auth import FinraAuthError, FinraTokenManager
from market_platform_foundation.finra.client_config import (
    credential_health,
    load_finra_credentials,
    resolve_expiry,
    rotation_alert,
)
from market_platform_foundation.finra.health import health_from_runtime
from market_platform_foundation.finra.live import probe_short_interest, probe_short_sale_volume
from market_platform_foundation.finra.query import query_reg_sho_daily, query_short_interest
from market_platform_foundation.finra.transport import FinraTransport
from market_platform_foundation.short_intelligence.store import ShortIntelligenceStore
from market_platform_foundation.nasdaq_regsho.live import fetch_threshold_observations
from market_platform_foundation.nasdaq_regsho.transport import NasdaqTransport
from market_platform_foundation.short_intelligence.identity import SymbolMap
from market_platform_foundation.short_intelligence.redaction import evidence_contains_secrets, redact_mapping


def main() -> int:
    parser = argparse.ArgumentParser(description="Short intelligence capability probe")
    parser.add_argument("--output", default="evidence/short_intelligence/capability-report.json")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--threshold-date", default="2026-07-28")
    args = parser.parse_args()

    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mapping = SymbolMap.from_path(ROOT / "tests" / "fixtures" / "short_intelligence" / "symbol_map.json")
    credentials = load_finra_credentials()
    auth_failed = False
    oauth_success = False
    token_reuse_success = False
    interest_count = 0
    volume_count = 0
    transport = None
    tokens = None
    finra_error = ""
    token_expires_in: float | None = None
    token_type = ""
    short_interest_schema: list[str] = []
    short_sale_schema: list[str] = []
    pit_observed = False
    last_request_id = ""
    if credentials.present():
        try:
            tokens = FinraTokenManager(credentials)
            first = tokens.get_token()
            second = tokens.get_token()
            oauth_success = bool(first) and tokens.refresh_count >= 1
            token_reuse_success = first == second and tokens.refresh_count == 1
            if tokens._cache is not None:
                token_expires_in = tokens._cache.expires_in_s
                token_type = tokens._cache.token_type
            transport = FinraTransport(tokens)
            interest = probe_short_interest(transport, mapping, args.symbol)
            volume = probe_short_sale_volume(transport, mapping, args.symbol)
            interest_count = len(interest)
            volume_count = len(volume)
            si_response = query_short_interest(transport, symbol=args.symbol, limit=1)
            vol_response = query_reg_sho_daily(transport, symbol=args.symbol, limit=1)
            if si_response.records:
                short_interest_schema = sorted(si_response.records[0].keys())
            if vol_response.records:
                short_sale_schema = sorted(vol_response.records[0].keys())
            last_request_id = transport.last_request_id
            pit_rows = probe_short_interest(transport, mapping, args.symbol, settlement_date="2026-07-15")
            if pit_rows and pit_rows[0].clocks.get("available_time"):
                store = ShortIntelligenceStore()
                store.add_short_interest(pit_rows[0])
                available = pit_rows[0].clocks["available_time"]
                before = f"{available[:10]}T00:00:00Z"
                pit_observed = (
                    store.short_interest_as_of(pit_rows[0].instrument_id, before) is None
                    and store.short_interest_as_of(pit_rows[0].instrument_id, available) is not None
                )
        except (FinraAuthError, OSError) as exc:
            auth_failed = "AUTH" in str(exc)
            finra_error = type(exc).__name__
    nasdaq_count = 0
    nasdaq_hash = ""
    nasdaq_error = ""
    nasdaq_transport = NasdaqTransport()
    try:
        rows = fetch_threshold_observations(
            nasdaq_transport, mapping, args.threshold_date, requested_symbols=(args.symbol, "BIYA")
        )
        nasdaq_count = len(rows)
        nasdaq_hash = rows[0].content_hash if rows else ""
    except OSError:
        nasdaq_error = "SOURCE_UNAVAILABLE"

    expiry = resolve_expiry(credentials)
    rotation = credential_health(credentials, auth_failed=auth_failed)
    remaining = None if expiry is None else (expiry - datetime.now(timezone.utc).date()).days
    health = health_from_runtime(
        credentials=credentials,
        tokens=tokens,
        transport=transport,
        last_dataset_publication_observed="",
        auth_failed=auth_failed,
    )
    si_runtime = oauth_success and interest_count > 0
    vol_runtime = oauth_success and volume_count > 0
    report = {
        "source_family": "short_intelligence",
        "tested_at": observed,
        "last_finra_success_time": observed if oauth_success else "",
        "token_refresh_tested": token_reuse_success,
        "consolidated_short_interest_runtime_tested": si_runtime,
        "regsho_daily_runtime_tested": vol_runtime,
        "finra": {
            "auth": {
                "oauth_success": oauth_success,
                "token_type": token_type or "Bearer",
                "expires_in": token_expires_in,
                "refresh_margin_seconds": 120,
                "token_refresh_success": token_reuse_success,
                "token_cached_in_memory_only": True,
                "credential_present": credentials.present(),
                "error": finra_error,
            },
            "consolidated_short_interest": {
                "supported": True,
                "credential_entitled": True,
                "implemented": True,
                "runtime_tested": si_runtime,
                "sample_row_count": interest_count,
                "fresh": "publication-dependent",
                "observed_schema_fields": short_interest_schema,
                "pit_blocks_before_publication": pit_observed,
                "last_request_id": last_request_id,
            },
            "reg_sho_daily_short_sale_volume": {
                "supported": True,
                "implemented": True,
                "runtime_tested": vol_runtime,
                "retention": "rolling_12_month_api",
                "sample_row_count": volume_count,
                "observed_schema_fields": short_sale_schema,
                "ratio_field": "finra_reported_short_sale_ratio",
                "semantic_note": "short_sale_volume_is_not_short_interest",
            },
        },
        "nasdaq": {
            "threshold_list": {
                "supported": True,
                "implemented": True,
                "runtime_tested": bool(nasdaq_hash),
                "coverage": "NASDAQ_LISTED_ONLY",
                "sample_row_count": nasdaq_count,
                "content_hash": nasdaq_hash,
                "error": nasdaq_error,
            }
        },
        "clocks": {
            "short_interest_available_time": "official publication date 16:40 America/New_York",
            "threshold_available_time": "file creation timestamp",
        },
        "coverage": {"nasdaq_threshold_not_all_us": True, "reg_sho_daily_api_window_months": 12},
        "quality": {
            "reachable_is_not_new_publication": True,
            "outage_is_not_zero": True,
        },
        "limitations": [
            "Individual Public credential is not a commercial license",
            "Live observation is not an admitted dataset",
            "Short interest is not short-sale volume is not threshold status is not borrow",
            "Nasdaq list is not all US Reg SHO threshold securities",
            "API short-sale history is a rolling window",
        ],
        "credential_health": {
            "state": rotation.value,
            "alert": rotation_alert(rotation, days_remaining=remaining),
            "expires_on_configured": bool(expiry),
        },
        "finra_health": {
            "oauth_healthy": health.oauth_healthy,
            "api_reachable": health.api_reachable,
            "last_status": health.last_status,
            "license_constraint": health.license_constraint,
        },
        "nasdaq_health": {
            "reachable": nasdaq_transport.last_status == "ok",
            "last_status": nasdaq_transport.last_status,
        },
    }
    report = redact_mapping(report)
    encoded = json.dumps(report).encode("utf-8")
    if evidence_contains_secrets(encoded):
        raise SystemExit("SECRET_LEAK_BLOCKED")
    out = Path(args.output)
    if not out.is_absolute():
        out = ROOT / out
    write_canonical_json(out, report)
    print(
        json.dumps(
            {
                "output": str(out),
                "oauth_success": oauth_success,
                "finra_rows": interest_count + volume_count,
                "nasdaq_rows": nasdaq_count,
                "credential_present": credentials.present(),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
