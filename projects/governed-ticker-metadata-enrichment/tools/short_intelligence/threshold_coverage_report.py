"""Generate machine-readable U.S. threshold coverage report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import write_canonical_json
from market_platform_foundation.cboe_regsho.transport import CboeTransport
from market_platform_foundation.nyse_regsho.transport import NyseTransport
from market_platform_foundation.short_intelligence.redaction import evidence_contains_secrets, redact_mapping


def main() -> int:
    parser = argparse.ArgumentParser(description="U.S. threshold coverage report")
    parser.add_argument("--output", default="evidence/short_intelligence/threshold-coverage-report.json")
    args = parser.parse_args()
    tested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    nyse = NyseTransport()
    cboe = CboeTransport()
    nyse_markets: list[str] = []
    nyse_error = ""
    cboe_latest = ""
    cboe_holidays: list[str] = []
    cboe_error = ""
    try:
        nyse_markets = list(nyse.discover_markets())
    except OSError as exc:
        nyse_error = type(exc).__name__
    try:
        cboe_latest = cboe.fetch_latest_date()
        cboe_holidays = list(cboe.fetch_holidays()[:5])
    except OSError as exc:
        cboe_error = type(exc).__name__
    report = {
        "capability": "US_THRESHOLD_STATUS",
        "tested_at": tested_at,
        "sources": {
            "nasdaq": {
                "implemented": True,
                "live_tested": False,
                "endpoint": "https://www.nasdaqtrader.com/dynamic/SymDir/regsho/nasdaqth{yyyymmdd}.txt",
                "coverage": "NASDAQ_LISTED",
            },
            "nyse_group": {
                "implemented": True,
                "live_tested": bool(nyse_markets),
                "markets_discovered": nyse_markets,
                "endpoint": "https://www.nyse.com/api/regulatory/threshold-securities/download",
                "error": nyse_error,
            },
            "finra_otc": {
                "implemented": True,
                "live_tested": False,
                "dataset": "otcMarket/thresholdList",
                "flags": ["regShoThresholdFlag", "rule4320Flag", "thresholdListFlag"],
            },
            "cboe": {
                "implemented": True,
                "live_tested": bool(cboe_latest),
                "coverage": "CBOE_BZX_LISTED_ONLY",
                "latest_date": cboe_latest,
                "holiday_sample": cboe_holidays,
                "file_endpoint": (
                    "https://cdn.cboe.com/resources/us/equities/market-statistics/"
                    "reg-sho-threshold/bzx_equities_reg_sho_threshold_{yyyymmdd}.txt"
                ),
                "api_endpoint": "https://www-api.cboe.com/us/equities/market_statistics/reg_sho_threshold/",
                "error": cboe_error,
            },
        },
        "listing_coverage": {
            "NASDAQ": "IMPLEMENTED",
            "NYSE": "IMPLEMENTED",
            "NYSE_AMERICAN": "IMPLEMENTED",
            "NYSE_ARCA": "IMPLEMENTED",
            "OTC": "IMPLEMENTED",
            "CBOE_BZX": "IMPLEMENTED",
            "NYSE_NATIONAL": "NOT_APPLICABLE_NO_PUBLIC_THRESHOLD_PUBLISHER_FOUND",
            "NYSE_TEXAS": "NOT_APPLICABLE_NO_PUBLIC_THRESHOLD_PUBLISHER_FOUND",
            "IEX": "NOT_APPLICABLE_NO_INDEPENDENT_THRESHOLD_LIST",
            "MEMX": "NOT_APPLICABLE_NO_INDEPENDENT_THRESHOLD_LIST",
        },
        "pit": {
            "availability_clock": "file_creation_time_or_first_observed_time",
            "amendments_preserved": True,
        },
        "revisions": {"finra_otc": "bitemporal record_version on content_hash change"},
        "known_gaps": [
            "Borrow/cost-to-borrow/locate remain unimplemented",
            "NYSE National and NYSE Texas have no separate public threshold publisher discovered",
            "Independent listing exchanges without separate threshold lists rely on primary listing authority routing",
        ],
        "coverage_assessment": "MATERIAL_COVERAGE",
    }
    report = redact_mapping(report)
    encoded = json.dumps(report).encode("utf-8")
    if evidence_contains_secrets(encoded):
        raise SystemExit("SECRET_LEAK_BLOCKED")
    out = Path(args.output)
    if not out.is_absolute():
        out = ROOT / out
    write_canonical_json(out, report)
    print(json.dumps({"output": str(out), "nyse_markets": nyse_markets, "cboe_latest": cboe_latest}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
