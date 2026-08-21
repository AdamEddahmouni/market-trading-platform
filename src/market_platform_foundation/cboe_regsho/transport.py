"""Official Cboe BZX Reg SHO threshold transport."""

from __future__ import annotations

import json
import threading
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CDN_URL_TEMPLATE = (
    "https://cdn.cboe.com/resources/us/equities/market-statistics/reg-sho-threshold/"
    "bzx_equities_reg_sho_threshold_{yyyymmdd}.txt"
)
HOLIDAYS_URL = "https://www-api.cboe.com/us/equities/market_statistics/reg_sho_threshold/holidays/"
LATEST_DATE_URL = "https://www-api.cboe.com/us/equities/market_statistics/reg_sho_threshold/latest_date/"
DEFAULT_TIMEOUT_S = 15.0
DEFAULT_MIN_INTERVAL_S = 1.0
MAX_RETRIES = 3
USER_AGENT = "IntegratedMarketPlatform research contact@example.com"

Requester = Callable[[str, dict[str, str], float], bytes]


class CboeTransport:
    _global_lock = threading.Lock()
    _last_request = 0.0

    def __init__(
        self,
        *,
        requester: Requester | None = None,
        min_interval_s: float = DEFAULT_MIN_INTERVAL_S,
        sleeper: Callable[[float], None] | None = None,
        user_agent: str = USER_AGENT,
    ) -> None:
        self._requester = requester or _stdlib_requester
        self.min_interval_s = min_interval_s
        self._sleeper = sleeper or time.sleep
        self.user_agent = user_agent
        self.request_count = 0
        self.error_count = 0
        self.last_status = "idle"
        self.last_holidays: tuple[str, ...] = ()
        self.last_latest_date = ""
        self.last_success_monotonic: float | None = None

    def fetch_holidays(self, *, timeout: float = DEFAULT_TIMEOUT_S) -> tuple[str, ...]:
        body = self._fetch(HOLIDAYS_URL, timeout=timeout, accept="application/json")
        payload = json.loads(body.decode("utf-8"))
        dates = payload.get("dates") if isinstance(payload, dict) else None
        if not isinstance(dates, list):
            raise OSError("CBOE_HOLIDAYS_INVALID")
        self.last_holidays = tuple(str(item)[:10] for item in dates)
        return self.last_holidays

    def fetch_latest_date(self, *, timeout: float = DEFAULT_TIMEOUT_S) -> str:
        body = self._fetch(LATEST_DATE_URL, timeout=timeout, accept="application/json")
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict) or not payload.get("date"):
            raise OSError("CBOE_LATEST_DATE_INVALID")
        self.last_latest_date = str(payload["date"])[:10]
        return self.last_latest_date

    def fetch_threshold_file(self, trade_date: str, *, timeout: float = DEFAULT_TIMEOUT_S) -> bytes:
        compact = trade_date.replace("-", "")[:8]
        url = CDN_URL_TEMPLATE.format(yyyymmdd=compact)
        return self._fetch(url, timeout=timeout, accept="text/plain,*/*")

    def _fetch(self, url: str, *, timeout: float, accept: str = "*/*") -> bytes:
        last_error: BaseException | None = None
        headers = {
            "User-Agent": self.user_agent,
            "Accept": accept,
            "Referer": "https://www.cboe.com/",
        }
        for attempt in range(MAX_RETRIES):
            self._throttle()
            try:
                body = self._requester(url, headers, timeout)
                self.request_count += 1
                self.last_status = "ok"
                self.last_success_monotonic = time.monotonic()
                return body
            except HTTPError as exc:
                last_error = exc
                self.error_count += 1
                self.last_status = f"http_{exc.code}"
                if exc.code == 404:
                    raise OSError("CBOE_THRESHOLD_FILE_MISSING") from exc
                if exc.code == 403:
                    raise OSError("CBOE_THRESHOLD_FILE_FORBIDDEN") from exc
                if exc.code >= 500 and attempt + 1 < MAX_RETRIES:
                    self._sleeper(0.2 * (2 ** attempt))
                    continue
                raise OSError("SOURCE_UNAVAILABLE") from exc
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                self.error_count += 1
                self.last_status = "network_error"
                if attempt + 1 < MAX_RETRIES:
                    self._sleeper(0.2 * (2 ** attempt))
                    continue
                raise OSError("SOURCE_UNAVAILABLE") from exc
        raise OSError("SOURCE_UNAVAILABLE") from last_error

    def _throttle(self) -> None:
        with self._global_lock:
            elapsed = time.monotonic() - CboeTransport._last_request
            wait = self.min_interval_s - elapsed
            if wait > 0:
                self._sleeper(wait)
            CboeTransport._last_request = time.monotonic()


def _stdlib_requester(url: str, headers: dict[str, str], timeout: float) -> bytes:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return response.read()
