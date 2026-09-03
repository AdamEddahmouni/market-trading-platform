"""Sanitized offline/live Cboe public options statistics capability probe."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cboe_options.daily import parse_daily_statistics_html  # noqa: E402
from market_platform_foundation.cboe_options.health import capability_report  # noqa: E402
from market_platform_foundation.cboe_options.historical import (  # noqa: E402
    characterize_historical_volume_download,
    parse_totalpc_archive_csv,
)
from market_platform_foundation.cboe_options.intraday import parse_intraday_statistics_html  # noqa: E402
from market_platform_foundation.cboe_options.live import live_enabled, transport_from_env  # noqa: E402
from market_platform_foundation.cboe_options.market_volume import parse_market_volume_csv  # noqa: E402
from market_platform_foundation.cboe_options.reference import parse_reference_csv  # noqa: E402
from market_platform_foundation.cboe_options.symbol_data import parse_symbol_data_csv  # noqa: E402
from market_platform_foundation.cboe_options.contracts import CboeExchangeCode  # noqa: E402
from market_platform_foundation.cboe_options.transport import CboeOptionsTransport  # noqa: E402

OUTPUT = ROOT / "evidence" / "cboe_options" / "capability-report.json"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _live_characterization() -> dict[str, object]:
    transport = transport_from_env()
    retrieved = _now()
    report: dict[str, object] = {"retrieved_time": retrieved, "request_count": 0}

    daily_html = transport.fetch_text(transport.daily_statistics_url())
    daily = parse_daily_statistics_html(
        daily_html,
        retrieved_time=retrieved,
        ingested_time=retrieved,
    )
    report["daily_statistics"] = {
        "trade_date": daily.trade_date,
        "last_updated": daily.last_updated,
        "observation_count": len(daily.observations),
        "coverage_scope": "CBOE_EXCHANGES",
    }

    market_csv = transport.fetch_text(transport.market_volume_url())
    market = parse_market_volume_csv(
        market_csv,
        retrieved_time=retrieved,
        ingested_time=retrieved,
    )
    report["market_volume"] = {
        "trade_date": market.trade_date,
        "observation_count": len(market.observations),
        "delay_policy": "DELAYED_DATA_MINIMUM_20_MINUTES",
        "publisher": "CBOE",
        "market_coverage": "US_OPTIONS_MARKET",
    }

    intraday_html = transport.fetch_text(transport.intraday_statistics_url())
    intraday = parse_intraday_statistics_html(
        intraday_html,
        retrieved_time=retrieved,
        ingested_time=retrieved,
    )
    report["intraday_exchange_statistics"] = {
        "trade_date": intraday.trade_date,
        "timezone": intraday.timezone,
        "cumulative_buckets": len(intraday.cumulative),
        "interval_buckets": len(intraday.intervals),
    }

    symbol_csv = transport.fetch_text(transport.symbol_data_url("cone"))
    symbol = parse_symbol_data_csv(
        symbol_csv,
        exchange=CboeExchangeCode.C1,
        retrieved_time=retrieved,
        ingested_time=retrieved,
    )
    report["symbol_data"] = {
        "exchange": symbol.exchange.value,
        "snapshot_count": len(symbol.snapshots),
        "scope": "EXCHANGE_SPECIFIC",
    }

    ref_url = transport.reference_file_url("cone", "all_series")
    ref_body, ref_headers = transport.fetch_with_headers(ref_url)
    reference = parse_reference_csv(
        ref_body.decode("utf-8", errors="replace"),
        exchange=CboeExchangeCode.C1,
        reference_category="all_series",
        source_url=ref_url,
        retrieved_time=retrieved,
        ingested_time=retrieved,
        http_last_modified=transport.last_modified(ref_headers),
    )
    report["reference_data"] = {
        "row_count": reference.observation.row_count,
        "content_hash_prefix": reference.observation.content_hash[:12],
        "headers": list(reference.observation.headers[:6]),
    }

    archive_body = transport.fetch_bytes(transport.historical_pc_archive_url())
    archive_text = archive_body.decode("utf-8", errors="replace")
    archive = parse_totalpc_archive_csv(
        archive_text,
        retrieved_time=retrieved,
        ingested_time=retrieved,
    )
    report["historical_volume"] = {
        "archive_rows": len(archive.observations),
        "characterization": characterize_historical_volume_download(),
    }

    report["request_count"] = transport.request_count
    return report


def main() -> int:
    live = live_enabled()
    report = capability_report(live=live)
    if live:
        report["live_characterization"] = _live_characterization()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "live": live, "source": report.get("source")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
