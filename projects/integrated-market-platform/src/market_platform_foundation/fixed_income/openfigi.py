"""Optional OpenFIGI identifier enrichment for one selected bond (Screener S16).

OpenFIGI's ``/v3/mapping`` maps a CUSIP to Financial Instrument Global
Identifiers (FIGI) with the instrument's market sector and security type. It
works without a key at 25 requests per minute (an ``OPENFIGI_API_KEY`` raises
the limit). IMP calls it only for the security a user opens in Quick Preview —
never per visible row and never for the catalog — and only when the operator
opts in with ``IMP_OPENFIGI_LIVE=1``. The FIGI is identity metadata, not a
price or a rating.
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict, deque
from typing import Any, Callable, Mapping

from .http import FixedIncomeSourceError, failure_code, http_post_json

URL = "https://api.openfigi.com/v3/mapping"
SOURCE = "OPENFIGI"
LIVE_FLAG = "IMP_OPENFIGI_LIVE"
REQUESTS_PER_MINUTE = 20  # below the documented 25/min keyless limit
CACHE_ENTRIES = 512

Poster = Callable[..., Any]


class OpenFigi:
    def __init__(self, *, env: Mapping[str, str] = os.environ, post: Poster = http_post_json,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._env, self._post, self._clock = env, post, clock
        self._lock = threading.Lock()
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._recent: deque[float] = deque()
        self.requests = 0

    def enabled(self) -> bool:
        return self._env.get(LIVE_FLAG) == "1"

    def lookup(self, cusip: str) -> dict[str, Any]:
        if not self.enabled():
            return {"state": "NOT_CONFIGURED", "reason": f"{LIVE_FLAG}_NOT_SET", "items": []}
        with self._lock:
            if cusip in self._cache:
                self._cache.move_to_end(cusip)
                return self._cache[cusip]
            now = self._clock()
            while self._recent and now - self._recent[0] > 60:
                self._recent.popleft()
            if len(self._recent) >= REQUESTS_PER_MINUTE:
                return {"state": "UNAVAILABLE", "reason": "OPENFIGI_RATE_LIMITED", "items": []}
            self._recent.append(now)
            self.requests += 1
        headers = {"X-OPENFIGI-APIKEY": self._env["OPENFIGI_API_KEY"]} if self._env.get("OPENFIGI_API_KEY") else None
        try:
            payload = self._post(URL, [{"idType": "ID_CUSIP", "idValue": cusip}], 10.0, headers)
            if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
                raise FixedIncomeSourceError("MALFORMED_RESPONSE")
            rows = payload[0].get("data") or []
            items = [{"figi": row.get("figi"), "composite_figi": row.get("compositeFIGI"),
                      "share_class_figi": row.get("shareClassFIGI"), "name": row.get("name"),
                      "ticker": row.get("ticker"), "market_sector": row.get("marketSector"),
                      "security_type": row.get("securityType"), "security_type2": row.get("securityType2")}
                     for row in rows if isinstance(row, dict) and row.get("figi")]
            result = {"state": "OBSERVED" if items else "UNAVAILABLE",
                      "reason": None if items else "NO_FIGI_MATCH", "items": items[:5]}
        except Exception as exc:  # noqa: BLE001 — stable code only
            return {"state": "UNAVAILABLE", "reason": failure_code(exc), "items": []}
        with self._lock:
            self._cache[cusip] = result
            while len(self._cache) > CACHE_ENTRIES:
                self._cache.popitem(last=False)
        return result
