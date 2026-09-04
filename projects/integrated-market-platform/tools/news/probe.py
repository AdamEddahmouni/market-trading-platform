"""Bounded live news-provider probe with sanitized output."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.news.aggregator import NewsAggregator  # noqa: E402
from market_platform_foundation.news.config import (  # noqa: E402
    finnhub_api_key,
    finnhub_live_enabled,
    newsapi_api_key,
    newsapi_live_enabled,
)


def run_probe(symbol: str) -> dict[str, object]:
    result = NewsAggregator().fetch_news(symbol)
    source_status = dict(result.get("source_status") or {})
    return {
        "symbol": symbol.upper(),
        "success": bool(result.get("success")),
        "item_count": len(result.get("items") or []),
        "source_status": source_status,
        "errors": dict(result.get("errors") or {}),
        "credential_presence": {
            "newsapi": bool(newsapi_api_key()),
            "finnhub": bool(finnhub_api_key()),
        },
        "live_gates": {
            "newsapi": newsapi_live_enabled(),
            "finnhub": finnhub_live_enabled(),
        },
        "secrets_included": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe read-only news providers")
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".local/news/capability-report.json"),
    )
    args = parser.parse_args(argv)
    report = run_probe(args.symbol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"written": str(args.output), "success": report["success"]}, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
