"""Search Cboe JS bundles for threshold API endpoints."""
from __future__ import annotations

import re
import ssl
from urllib.request import Request, urlopen

ctx = ssl.create_default_context()
UA = "IntegratedMarketPlatform research contact@example.com"
page = "https://www.cboe.com/markets/us/equities/market-statistics/reg-sho-threshold/2025-06-17/"
req = Request(page, headers={"User-Agent": UA})
with urlopen(req, timeout=30, context=ctx) as r:
    html = r.read().decode("utf-8", errors="replace")
chunks = sorted(set(re.findall(r"/_next/static/chunks/[^\"']+\.js", html)))
print("chunks", len(chunks))
for chunk in chunks:
    url = "https://www.cboe.com" + chunk
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=30, context=ctx) as r:
        js = r.read().decode("utf-8", errors="replace")
    if not any(k in js for k in ("RegSho", "reg-sho", "regSho", "threshold")):
        continue
    print("===", chunk, "len", len(js))
    for pat in (
        r"https?://[^\"']+",
        r"/api/[^\"']+",
        r"reg[-_]?sho[^\"']{0,80}",
        r"threshold[^\"']{0,80}",
        r"fetch\([^)]+\)",
        r"\.csv[^\"']*",
        r"\.xlsx[^\"']*",
    ):
        hits = sorted(set(re.findall(pat, js, re.I)))
        if hits:
            print(pat[:20], hits[:12])
