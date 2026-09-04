"""Discover Cboe Reg SHO threshold data endpoints."""
from __future__ import annotations

import json
import re
import ssl
from urllib.request import Request, urlopen

ctx = ssl.create_default_context()
UA = "IntegratedMarketPlatform research contact@example.com"
page = "https://www.cboe.com/markets/us/equities/market-statistics/reg-sho-threshold/"
req = Request(page, headers={"User-Agent": UA})
with urlopen(req, timeout=30, context=ctx) as r:
    html = r.read().decode("utf-8", errors="replace")

print("len", len(html))
# Next.js flight data
for pat in (
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    r'self\.__next_f\.push\(\[1,"(.*?)"\]\)',
):
    for m in re.findall(pat, html, flags=re.S):
        print("match", pat[:40], "len", len(m))
        if m.startswith("{"):
            data = json.loads(m)
            blob = json.dumps(data)
            for token in sorted(set(re.findall(r"[^\"\\]+(?:threshold|reg[-_]?sho|regsho)[^\"\\]*", blob, re.I))):
                print(" token", token[:120])
            for token in sorted(set(re.findall(r"https?://[^\"\\]+", blob))):
                if any(k in token.lower() for k in ("api", "download", "csv", "txt", "data")):
                    print(" url", token)

# search all script chunks
for m in re.findall(r"/_next/static/chunks/[^\"']+\.js", html):
    if "chunk" in m:
        pass
chunks = sorted(set(re.findall(r"/_next/static/chunks/[^\"']+\.js", html)))
print("chunks", len(chunks))
for chunk in chunks[:8]:
    url = "https://www.cboe.com" + chunk
    req = Request(url, headers={"User-Agent": UA})
    with urlopen(req, timeout=30, context=ctx) as r:
        js = r.read().decode("utf-8", errors="replace")
    hits = sorted(set(re.findall(r"[^\"']*(?:threshold|reg[-_]?sho|regsho)[^\"']*", js, re.I)))
    if hits:
        print("chunk", chunk, "hits", len(hits))
        for h in hits[:15]:
            print(" ", h[:150])
