"""Extract Cboe threshold data from RSC/Next.js payloads."""
from __future__ import annotations

import json
import re
import ssl
from urllib.request import Request, urlopen

ctx = ssl.create_default_context()
UA = "IntegratedMarketPlatform research contact@example.com"


def fetch(url: str) -> str:
    req = Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/json"})
    with urlopen(req, timeout=30, context=ctx) as r:
        return r.read().decode("utf-8", errors="replace")


def scan(text: str, label: str) -> None:
    patterns = [
        r"https?://[^\"'\\]+",
        r"/api/[^\"'\\]+",
        r"reg[-_]?sho[^\"'\\]{0,80}",
        r"threshold[^\"'\\]{0,80}",
        r"GMEU|ARCX|BMNZ|AMZE",
        r"Symbol|Company Name",
    ]
    for pat in patterns:
        hits = sorted(set(re.findall(pat, text, flags=re.I)))
        if hits:
            print(label, pat[:30], len(hits))
            for h in hits[:20]:
                print(" ", h[:160])


for date in ("2025-06-17", "2026-08-19"):
    url = f"https://www.cboe.com/markets/us/equities/market-statistics/reg-sho-threshold/{date}/"
    html = fetch(url)
    print("===", date, "len", len(html))
    for pat in ("xlsx", "xls", "download", "Excel", "cdn.cboe.com/resources", "reg_sho", "reg-sho", "threshold"):
        hits = [m for m in re.findall(rf"[^\"'<>]{{0,120}}{pat}[^\"'<>]{{0,120}}", html, re.I)]
        if hits:
            print(pat, len(hits), hits[:5])

# try likely JSON endpoints
candidates = [
    "https://www.cboe.com/api/markets/us/equities/market-statistics/reg-sho-threshold/2025-06-17",
    "https://www.cboe.com/api/markets/us/equities/reg-sho-threshold/2025-06-17",
    "https://www.cboe.com/markets/us/equities/market-statistics/reg-sho-threshold/api/2025-06-17",
    "https://www.cboe.com/markets/us/equities/market-statistics/reg-sho-threshold/download/2025-06-17",
    "https://www.cboe.com/markets/us/equities/market-statistics/reg-sho-threshold/2025-06-17/download",
    "https://www.cboe.com/markets/us/equities/market-statistics/reg-sho-threshold/2025-06-17.json",
    "https://www.cboe.com/markets/us/equities/market-statistics/reg-sho-threshold/2025-06-17.txt",
    "https://www.cboe.com/markets/us/equities/market-statistics/reg-sho-threshold/2025-06-17.xlsx",
    "https://cdn.cboe.com/resources/regulatory/reg_sho_threshold/reg_sho_threshold_20250617.xlsx",
    "https://cdn.cboe.com/resources/regulatory/reg_sho_threshold/2025-06-17.xlsx",
    "https://cdn.cboe.com/resources/regulatory/reg_sho_threshold/reg_sho_threshold_20250617.txt",
    "https://cdn.cboe.com/resources/regulatory/reg_sho_threshold/reg_sho_threshold_20250617.csv",
]
for url in candidates:
    try:
        req = Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/plain,*/*"})
        with urlopen(req, timeout=20, context=ctx) as r:
            body = r.read()
        print("OK", url, len(body), body[:200])
    except Exception as exc:
        print("ERR", url, exc)
