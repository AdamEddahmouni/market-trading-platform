"""Bounded live probe for NYSE / FINRA OTC / Cboe threshold sources."""
from __future__ import annotations

import json
import os
import re
import ssl
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

ctx = ssl.create_default_context()
UA = "IntegratedMarketPlatform research contact@example.com"


def fetch(url: str, *, headers: dict[str, str] | None = None, timeout: float = 20.0) -> tuple[int, dict[str, str], bytes]:
    req = Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urlopen(req, timeout=timeout, context=ctx) as response:
        raw_headers = {str(k): str(v) for k, v in response.headers.items()}
        return int(getattr(response, "status", 200)), raw_headers, response.read()


def probe_nyse() -> None:
    print("=== NYSE ===")
    # discover markets from page JSON if embedded
    status, _, html = fetch("https://www.nyse.com/regulation/threshold-securities")
    print("page status", status, "bytes", len(html))
    text = html.decode("utf-8", errors="replace")
    for pattern in (
        r"/api/regulatory/threshold-securities[^\"'\s<>]*",
        r"selectedDate[^\"'\s<>]*",
        r"market[^\"'\s<>]{0,40}",
    ):
        matches = re.findall(pattern, text)
        if matches:
            print("matches", pattern, matches[:10])
    markets = json.loads(fetch("https://www.nyse.com/api/regulatory/threshold-securities/markets")[2].decode())
    print("markets", markets)
    for date in ("2026-08-19", "2026-08-18", "2026-08-15"):
        for market in markets:
            encoded = market.replace(" ", "%20")
            url = f"https://www.nyse.com/api/regulatory/threshold-securities/download?selectedDate={date}&market={encoded}"
            status, headers, body = fetch(url)
            lines = body.decode().splitlines()
            print("OK", date, market, status, "lines", len(lines), "bytes", len(body))
            print("head", lines[:3])
            if len(lines) > 2:
                print("sample row", lines[1])
    # try markets metadata endpoints
    for path in (
        "/api/regulatory/threshold-securities/markets",
        "/api/regulatory/threshold-securities/dates",
        "/api/regulatory/threshold-securities",
    ):
        try:
            status, _, body = fetch("https://www.nyse.com" + path)
            print("meta", path, status, body[:500])
        except Exception as exc:
            print("meta ERR", path, exc)


def probe_finra() -> None:
    print("=== FINRA OTC thresholdList ===")
    from market_platform_foundation.finra.auth import FinraTokenManager
    from market_platform_foundation.finra.client_config import load_finra_credentials
    from market_platform_foundation.finra.query import query_dataset
    from market_platform_foundation.finra.transport import FinraTransport

    creds = load_finra_credentials()
    manager = FinraTokenManager(creds)
    transport = FinraTransport(manager, min_interval_s=0.0)
    meta = transport.get("/metadata/group/otcMarket/name/thresholdList")
    print("metadata status", meta.status, "records", len(meta.records))
    print(json.dumps(meta.records[:3], indent=2)[:2000])
    response = query_dataset(
        transport,
        group="otcMarket",
        dataset="thresholdList",
        limit=5,
    )
    print("sample count", len(response.records), "request_id", response.request_id)
    if response.records:
        print(json.dumps(response.records[0], indent=2))


def probe_cboe() -> None:
    print("=== CBOE ===")
    page_url = "https://www.cboe.com/markets/us/equities/market-statistics/reg-sho-threshold/"
    status, _, html = fetch(page_url)
    text = html.decode("utf-8", errors="replace")
    print("page", page_url, status, len(text))
    candidates: list[str] = []
    for m in re.findall(r"https?://[^\"'\s<>]+", text):
        if any(k in m.lower() for k in ("threshold", "reg-sho", "reg_sho", "regsho", "download", ".csv", ".txt", "api")):
            candidates.append(m.replace("\\", ""))
    for m in re.findall(r"/[^\"'\s<>]+\.(?:csv|txt|json)", text, flags=re.I):
        if "threshold" in m.lower() or "reg" in m.lower():
            candidates.append("https://www.cboe.com" + m)
    for m in re.findall(r"__NEXT_DATA__[^>]*>(\{.*?\})</script>", text, flags=re.S):
        print("next_data len", len(m))
        try:
            payload = json.loads(m)
            blob = json.dumps(payload)
            for token in re.findall(r"[^\"'\s<>]+\.(?:csv|txt|json)", blob, flags=re.I):
                if "threshold" in token.lower() or "reg" in token.lower():
                    candidates.append(token)
        except json.JSONDecodeError:
            pass
    for url in dict.fromkeys(candidates):
        if not url.startswith("http"):
            continue
        try:
            status, headers, body = fetch(url)
            print("OK", url, status, headers.get("content-type"), len(body))
            print(body[:400])
        except Exception as exc:
            print("ERR", url, exc)
    # legacy / documented patterns
    for url in (
        "https://cdn.cboe.com/resources/regulatory/reg_sho_threshold/reg_sho_threshold.csv",
        "https://cdn.cboe.com/resources/regulatory/reg_sho_threshold/reg_sho_threshold.txt",
        "https://markets.cboe.com/us/equities/market_statistics/reg_sho_threshold/download/",
        "https://www.cboe.com/us/equities/market_statistics/reg_sho_threshold/download/",
    ):
        try:
            status, headers, body = fetch(url)
            print("OK legacy", url, status, headers.get("content-type"), len(body))
            print(body[:400])
        except Exception as exc:
            print("ERR legacy", url, exc)


if __name__ == "__main__":
    probe_nyse()
    if os.environ.get("SKIP_FINRA") != "1":
        try:
            probe_finra()
        except Exception as exc:
            print("FINRA probe failed:", exc)
    probe_cboe()
