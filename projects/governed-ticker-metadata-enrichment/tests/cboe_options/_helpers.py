"""Shared fixture helpers for Cboe options statistics tests."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "cboe_options"

RETRIEVED_TIME = "2026-08-19T17:35:00-05:00"
INGESTED_TIME = "2026-08-19T17:36:00-05:00"


def load_json(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def load_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def daily_html(payload: dict) -> str:
    """Minimal HTML wrapper mimicking Cboe daily statistics embedded JSON."""
    embedded = json.dumps(payload, separators=(",", ":"))
    return (
        "<!DOCTYPE html><html><body>"
        f'"putCallRatios":{json.dumps(payload["putCallRatios"])},'
        f'"volumeAndOpenInterest":{json.dumps(payload["volumeAndOpenInterest"])},'
        f'"tradeDate":"{payload["tradeDate"]}",'
        f'"lastUpdated":"{payload.get("lastUpdated", payload["tradeDate"] + "T17:30:00-05:00")}"'
        f'<script id="__NEXT_DATA__" type="application/json">{embedded}</script>'
        "</body></html>"
    )


def intraday_html(payload: dict) -> str:
    """HTML wrapper for intraday cumulative statistics rows."""
    rows = payload["buckets"]
    trade_date = payload["tradeDate"]
    embedded = json.dumps({"timeBuckets": rows, "tradeDate": trade_date}, separators=(",", ":"))
    return (
        "<!DOCTYPE html><html><body>"
        f'"tradeDate":"{trade_date}",'
        f'"timeBuckets":{json.dumps(rows)},'
        f'<script id="__NEXT_DATA__" type="application/json">{embedded}</script>'
        "</body></html>"
    )


def parse_daily_fixture(name: str = "daily_stats_embedded.json"):
    from market_platform_foundation.cboe_options.daily import parse_daily_statistics_html

    payload = load_json(name)
    return parse_daily_statistics_html(
        daily_html(payload),
        retrieved_time=RETRIEVED_TIME,
        ingested_time=payload.get("availableTime", INGESTED_TIME),
    )
