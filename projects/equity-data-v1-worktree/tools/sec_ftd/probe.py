"""SEC FTD capability probe. Bounded live discovery + optional parse."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import write_canonical_json
from market_platform_foundation.sec_ftd.discovery import discover_archives, latest_discovered_period
from market_platform_foundation.sec_ftd.health import health_from_runtime
from market_platform_foundation.sec_ftd.live import transport_from_env
from market_platform_foundation.sec_ftd.parser import EXPECTED_HEADER, parse_archive_bytes
from market_platform_foundation.sec_ftd.transport import FtdTransport
from market_platform_foundation.short_intelligence.identity import SymbolMap


def main() -> int:
    parser = argparse.ArgumentParser(description="SEC FTD capability probe")
    parser.add_argument("--output", default="evidence/sec_ftd/capability-report.json")
    parser.add_argument("--symbol", default="BIYA")
    parser.add_argument("--period", default="")
    args = parser.parse_args()

    transport = transport_from_env()
    ftd_transport = FtdTransport(transport)
    observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    discovered = discover_archives(transport)
    latest = discovered[0] if discovered else None
    period_key = args.period or (latest.period.period_key if latest else "")
    sample_rows: list[dict[str, object]] = []
    biya_rows: list[dict[str, object]] = []
    content_hash = ""
    record_count = 0
    if period_key:
        from market_platform_foundation.sec_ftd.periods import parse_period_key

        period = parse_period_key(period_key, url_path=latest.period.url_path if latest else "")
        capture = ftd_transport.fetch_archive(period, retrieved_time=observed, first_observed_time=observed)
        parsed = parse_archive_bytes(capture.content_bytes, period_key=period.period_key)
        content_hash = parsed.content_hash
        record_count = parsed.record_count
        symbol = args.symbol.upper()
        for row in parsed.rows:
            if row.symbol == symbol:
                biya_rows.append(
                    {
                        "settlement_date": row.settlement_date,
                        "cusip": row.cusip,
                        "ftd_balance_quantity": row.ftd_balance_quantity,
                        "previous_day_price_raw": row.previous_day_price_raw,
                    }
                )
        sample_rows = [
            {
                "settlement_date": row.settlement_date,
                "cusip": row.cusip,
                "symbol": row.symbol,
                "ftd_balance_quantity": row.ftd_balance_quantity,
            }
            for row in parsed.rows[:3]
        ]
    health = health_from_runtime(
        transport,
        latest_period_discovered=latest.period.period_key if latest else "",
        latest_period_captured=period_key,
        last_successful_retrieval=observed if period_key else "",
        latest_hash=content_hash,
        parser_health="OK" if record_count else "UNTESTED",
    )
    report = {
        "source": "sec_fails_to_deliver",
        "tested_at": observed,
        "coverage": {
            "start": "2004-02",
            "latest_observed_period": latest.period.period_key if latest else "",
            "modern_half_month_start": "2009-07",
        },
        "source_files": {
            "index_url": "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data",
            "latest_period": period_key,
            "content_hash": content_hash,
            "record_count": record_count,
        },
        "schema": {
            "columns": list(EXPECTED_HEADER),
            "delimiter": "pipe",
            "archive_format": "zip",
        },
        "publication": {
            "cadence": "twice_monthly",
            "first_half": "end_of_month_approx",
            "second_half": "mid_next_month_approx",
            "guaranteed_date": False,
        },
        "pit": {
            "economic_date": "settlement_date",
            "availability_clock": "first_observed_time_for_live_captures",
            "historical_backfill": "PUBLICATION_TIME_UNCERTAIN",
        },
        "live_probe": {
            "reachable": health.reachable,
            "discovered_period_count": len(discovered),
            "request_count": health.request_count,
        },
        "biya": {
            "symbol": args.symbol.upper(),
            "rows": biya_rows,
            "status": "FOUND" if biya_rows else ("PERIOD_NOT_PROBED" if not period_key else "NOT_FOUND"),
        },
        "quality": {
            "outage_is_not_zero": True,
            "balance_not_flow": True,
        },
        "limitations": [
            "FTD balance is outstanding stock, not daily fail volume",
            "FTD does not prove naked shorting",
            "SEC price is lagged context only",
            "Publication time is uncertain for historical backfills",
            "Pre-2008-09-16 files omit balances below 10,000 shares",
            "Live capture is not admitted",
        ],
        "sample_rows": sample_rows,
        "user_agent_configured": bool(os.environ.get("SEC_USER_AGENT", "").strip()),
    }
    out = Path(args.output)
    if not out.is_absolute():
        out = ROOT / out
    write_canonical_json(out, report)
    print(json.dumps({"output": str(out), "latest": period_key, "biya_rows": len(biya_rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
