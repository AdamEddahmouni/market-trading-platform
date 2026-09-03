"""NYSE Group official Reg SHO threshold transport. Public, no credential."""

from __future__ import annotations

import json
import threading
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MARKETS_URL = "https://www.nyse.com/api/regulatory/threshold-securities/markets"
DOWNLOAD_URL_TEMPLATE = (
    "https://www.nyse.com/api/regulatory/threshold-securities/download"
    "?selectedDate={selected_date}&market={market}"
)
DEFAULT_TIMEOUT_S = 15.0
DEFAULT_MIN_INTERVAL_S = 1.0
MAX_RETRIES = 3
USER_AGENT = "IntegratedMarketPlatform research contact@example.com"

Requester = Callable[[str, dict[str, str], float], bytes]


class NyseTransport:
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
        self.last_markets: tuple[str, ...] = ()
        self.last_success_monotonic: float | None = None

    def discover_markets(self, *, timeout: float = DEFAULT_TIMEOUT_S) -> tuple[str, ...]:
        body = self._fetch(MARKETS_URL, timeout=timeout)
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, list):
            raise OSError("NYSE_MARKETS_INVALID")
        markets = tuple(str(item) for item in payload if str(item).strip())
        self.last_markets = markets
        return markets

    def fetch_threshold_file(
        self,
        trade_date: str,
        *,
        market: str,
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> bytes:
        selected = trade_date[:10]
        encoded_market = market.replace(" ", "%20")
        url = DOWNLOAD_URL_TEMPLATE.format(selected_date=selected, market=encoded_market)
        return self._fetch(url, timeout=timeout)

    def _fetch(self, url: str, *, timeout: float) -> bytes:
        last_error: BaseException | None = None
        for attempt in range(MAX_RETRIES):
            self._throttle()
            try:
                body = self._requester(url, {"User-Agent": self.user_agent, "Accept": "*/*"}, timeout)
                self.request_count += 1
                self.last_status = "ok"
                self.last_success_monotonic = time.monotonic()
                return body
            except HTTPError as exc:
                last_error = exc
                self.error_count += 1
                self.last_status = f"http_{exc.code}"
                if exc.code == 400:
                    raise OSError("NYSE_THRESHOLD_BAD_REQUEST") from exc
                if exc.code == 404:
                    raise OSError("NYSE_THRESHOLD_FILE_MISSING") from exc
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
            elapsed = time.monotonic() - NyseTransport._last_request
            wait = self.min_interval_s - elapsed
            if wait > 0:
                self._sleeper(wait)
            NyseTransport._last_request = time.monotonic()


def _stdlib_requester(url: str, headers: dict[str, str], timeout: float) -> bytes:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return response.read()
