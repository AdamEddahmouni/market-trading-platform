"""Finviz Elite capability probe — sanitized evidence output."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.finviz.config import finviz_api_key, finviz_evidence_root, finviz_live_enabled
from market_platform_foundation.finviz.fields import classify_options_columns, classify_screener_columns
from market_platform_foundation.finviz.news import FinvizNewsClient
from market_platform_foundation.finviz.options import FinvizOptionsClient
from market_platform_foundation.finviz.request_manager import get_finviz_request_manager, redact_payload
from market_platform_foundation.finviz.screener import FinvizScreenerClient

PROBE_VERSION = "1.0.0"


def _utc_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _capability_row(
    name: str,
    *,
    documented: bool,
    account_accessible: bool,
    verified: bool,
    endpoint: str,
    notes: str,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "documented": documented,
        "account_accessible": account_accessible,
        "verified": verified,
        "endpoint_export": endpoint,
        "response_fields": fields or [],
        "notes": notes,
    }


def run_probe(*, symbol: str = "AAPL", force: bool = False) -> dict[str, Any]:
    manager = get_finviz_request_manager()
    screener = FinvizScreenerClient()
    news = FinvizNewsClient()
    options = FinvizOptionsClient()
    configured = screener.configured
    capabilities: list[dict[str, Any]] = []

    screener_result = screener.fetch_export(filter_expr="sh_float_u50", force=force)
    screener_ok = bool(screener_result.get("success"))
    columns = list(screener_result.get("columns") or [])
    capabilities.append(
        _capability_row(
            "Screener",
            documented=True,
            account_accessible=configured,
            verified=screener_ok,
            endpoint="elite.finviz.com/export/screener",
            notes=str(screener_result.get("error") or "OK"),
            fields=columns,
        )
    )

    news_result = news.fetch_news(force=force)
    news_ok = bool(news_result.get("success"))
    news_fields = list((news_result.get("items") or [{}])[0].keys()) if news_ok else []
    capabilities.append(
        _capability_row(
            "News",
            documented=True,
            account_accessible=configured,
            verified=news_ok,
            endpoint="elite.finviz.com/news_export.ashx",
            notes=str(news_result.get("error") or f"count={len(news_result.get('items') or [])}"),
            fields=news_fields,
        )
    )

    options_result = options.fetch_chain(symbol, force=force)
    options_ok = bool(options_result.get("success"))
    opt_columns = list(options_result.get("columns") or [])
    capabilities.append(
        _capability_row(
            "Options Chain",
            documented=True,
            account_accessible=configured,
            verified=options_ok,
            endpoint="elite.finviz.com/export/options",
            notes=str(options_result.get("error") or options_result.get("capability")),
            fields=opt_columns,
        )
    )

    capabilities.extend(
        [
            _capability_row(
                "Groups",
                documented=True,
                account_accessible=False,
                verified=False,
                endpoint="UI_ONLY",
                notes="Groups/sector breadth not exposed via documented Elite export in this adapter",
            ),
            _capability_row(
                "Portfolio",
                documented=True,
                account_accessible=False,
                verified=False,
                endpoint="UI_ONLY",
                notes="Portfolio export not probed in P3.3",
            ),
            _capability_row(
                "ETF Holdings",
                documented=True,
                account_accessible=False,
                verified=False,
                endpoint="UNKNOWN",
                notes="Full ETF holdings require further endpoint characterization",
            ),
            _capability_row(
                "Correlations",
                documented=True,
                account_accessible=False,
                verified=False,
                endpoint="UI_ONLY",
                notes="Correlation data UI-only per current probe",
            ),
            _capability_row(
                "Alerts",
                documented=True,
                account_accessible=False,
                verified=False,
                endpoint="UI_ONLY",
                notes="Alerts not API-accessible in current probe",
            ),
        ]
    )

    report = {
        "probe_version": PROBE_VERSION,
        "probed_at": _utc_iso(),
        "configured": configured,
        "finviz_live_enabled": finviz_live_enabled(),
        "rate_limit_observations": {
            "min_interval_s": manager._min_interval_s,
            "request_count": manager.metrics.request_count,
            "cache_hits": manager.metrics.cache_hits,
            "cache_misses": manager.metrics.cache_misses,
            "rate_limit_waits": manager.metrics.rate_limit_waits,
            "http_429_count": manager.metrics.http_429_count,
            "auth_failures": manager.metrics.auth_failures,
        },
        "capabilities": capabilities,
        "field_inventory": {
            "screener": classify_screener_columns(columns),
            "options": classify_options_columns(opt_columns),
        },
        "auth_present": bool(finviz_api_key()),
    }
    return redact_payload(report)


def main() -> int:
    parser = argparse.ArgumentParser(description="Finviz Elite capability probe")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    report = run_probe(symbol=args.symbol, force=args.force)
    out = args.output or (finviz_evidence_root() / "capability-report.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, sort_keys=True, indent=2), encoding="utf-8")
    print(json.dumps({"written": str(out), "configured": report.get("configured")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
