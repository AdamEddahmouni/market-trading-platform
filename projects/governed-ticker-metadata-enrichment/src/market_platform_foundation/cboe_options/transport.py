"""Official Cboe public options statistics HTTP transport."""

from __future__ import annotations

import email.utils
import threading
import time
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT_S = 30.0
DEFAULT_MIN_INTERVAL_S = 1.0
MAX_RETRIES = 3
USER_AGENT = "IntegratedMarketPlatform research contact@example.com"
REFERER = "https://www.cboe.com/"

DAILY_STATISTICS_URL = "https://www.cboe.com/us/options/market_statistics/daily/"
MARKET_VOLUME_URL = (
    "https://www.cboe.com/us/options/market_share/market/csv/"
    "?bias=Volume&auctions=0&oddLots=n&subdollars=n"
)
INTRADAY_STATISTICS_URL = "https://www.cboe.com/us/options/market_statistics/market/"
HISTORICAL_PC_ARCHIVE_URL = (
    "https://cdn.cboe.com/resources/options/volume_and_call_put_ratios/totalpc.csv"
)
HISTORICAL_VOLUME_FORM_URL = "https://www.cboe.com/us/options/market_statistics/historical_data/"

CDN_REFERENCE_BASE = "https://cdn.cboe.com/data/us/options/market_statistics/symbol_reference"
SYMBOL_DATA_CSV_BASE = "https://www.cboe.com/us/options/market_statistics/symbol_data/csv/"

Requester = Callable[[str, dict[str, str], float], tuple[bytes, dict[str, str]]]


class CboeOptionsTransport:
    _global_lock = threading.Lock()
    _last_request = 0.0

    def __init__(
        self,
        *,
        requester: Requester | None = None,
        min_interval_s: float = DEFAULT_MIN_INTERVAL_S,
        sleeper: Callable[[float], None] | None = None,
        user_agent: str = USER_AGENT,
        referer: str = REFERER,
    ) -> None:
        self._requester = requester or _stdlib_requester
        self.min_interval_s = min_interval_s
        self._sleeper = sleeper or time.sleep
        self.user_agent = user_agent
        self.referer = referer
        self.request_count = 0
        self.error_count = 0
        self.last_status = "idle"
        self.last_response_headers: dict[str, str] = {}
        self.last_success_monotonic: float | None = None

    def fetch_bytes(self, url: str, *, timeout: float = DEFAULT_TIMEOUT_S) -> bytes:
        body, _headers = self._fetch(url, timeout=timeout)
        return body

    def fetch_text(self, url: str, *, timeout: float = DEFAULT_TIMEOUT_S) -> str:
        body = self.fetch_bytes(url, timeout=timeout)
        return body.decode("utf-8", errors="replace")

    def fetch_with_headers(
        self, url: str, *, timeout: float = DEFAULT_TIMEOUT_S
    ) -> tuple[bytes, dict[str, str]]:
        return self._fetch(url, timeout=timeout)

    @staticmethod
    def last_modified(headers: dict[str, str]) -> str:
        raw = headers.get("last-modified") or headers.get("Last-Modified") or ""
        if not raw:
            return ""
        parsed = email.utils.parsedate_to_datetime(raw)
        return parsed.isoformat()

    @staticmethod
    def daily_statistics_url() -> str:
        return DAILY_STATISTICS_URL

    @staticmethod
    def market_volume_url() -> str:
        return MARKET_VOLUME_URL

    @staticmethod
    def intraday_statistics_url(exchange_mkt: str = "cone") -> str:
        if exchange_mkt.lower() in {"cone", "c1", ""}:
            return INTRADAY_STATISTICS_URL
        return f"{INTRADAY_STATISTICS_URL}?mkt={exchange_mkt.lower()}"

    @staticmethod
    def symbol_data_url(exchange_mkt: str) -> str:
        mapping = {"c1": "cone", "bzx": "opt", "c2": "ctwo", "edgx": "exo"}
        mkt = mapping.get(exchange_mkt.lower(), exchange_mkt.lower())
        return f"{SYMBOL_DATA_CSV_BASE}?mkt={mkt}"

    @staticmethod
    def reference_file_url(exchange_prefix: str, category: str) -> str:
        slug_map = {
            "all_series": "all-series",
            "underlying": "underlying",
            "market_maker_registered": "market-maker-registered",
            "constituent_series": "constituent",
        }
        prefix = {"c1": "cone", "bzx": "opt", "c2": "ctwo", "edgx": "exo"}.get(
            exchange_prefix.lower(),
            exchange_prefix.lower(),
        )
        slug = slug_map.get(category.strip().lower(), category.strip().lower().replace(" ", "-"))
        return f"{CDN_REFERENCE_BASE}/{prefix}-{slug}.csv"

    @staticmethod
    def historical_pc_archive_url() -> str:
        return HISTORICAL_PC_ARCHIVE_URL

    @staticmethod
    def historical_volume_form_url() -> str:
        return HISTORICAL_VOLUME_FORM_URL

    def _fetch(self, url: str, *, timeout: float) -> tuple[bytes, dict[str, str]]:
        last_error: BaseException | None = None
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/json,text/csv,text/plain,*/*",
            "Referer": self.referer,
        }
        for attempt in range(MAX_RETRIES):
            self._throttle()
            try:
                body, response_headers = self._requester(url, headers, timeout)
                self.request_count += 1
                self.last_status = "ok"
                self.last_response_headers = {
                    str(key).lower(): str(value) for key, value in response_headers.items()
                }
                self.last_success_monotonic = time.monotonic()
                return body, self.last_response_headers
            except HTTPError as exc:
                last_error = exc
                self.error_count += 1
                self.last_status = f"http_{exc.code}"
                if exc.code == 404:
                    raise OSError("CBOE_OPTIONS_SOURCE_MISSING") from exc
                if exc.code == 403:
                    raise OSError("CBOE_OPTIONS_SOURCE_FORBIDDEN") from exc
                if exc.code >= 500 and attempt + 1 < MAX_RETRIES:
                    self._sleeper(0.2 * (2**attempt))
                    continue
                raise OSError("SOURCE_UNAVAILABLE") from exc
            except (URLError, TimeoutError, OSError) as exc:
                last_error = exc
                self.error_count += 1
                self.last_status = "network_error"
                if attempt + 1 < MAX_RETRIES:
                    self._sleeper(0.2 * (2**attempt))
                    continue
                raise OSError("SOURCE_UNAVAILABLE") from exc
        raise OSError("SOURCE_UNAVAILABLE") from last_error

    def _throttle(self) -> None:
        with self._global_lock:
            elapsed = time.monotonic() - CboeOptionsTransport._last_request
            wait = self.min_interval_s - elapsed
            if wait > 0:
                self._sleeper(wait)
            CboeOptionsTransport._last_request = time.monotonic()


def _stdlib_requester(url: str, headers: dict[str, str], timeout: float) -> tuple[bytes, dict[str, str]]:
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        body = response.read()
        response_headers = {str(key): str(value) for key, value in response.headers.items()}
    return body, response_headers


__all__ = [
    "CDN_REFERENCE_BASE",
    "SYMBOL_DATA_CSV_BASE",
    "CboeOptionsTransport",
    "DAILY_STATISTICS_URL",
    "HISTORICAL_PC_ARCHIVE_URL",
    "HISTORICAL_VOLUME_FORM_URL",
    "INTRADAY_STATISTICS_URL",
    "MARKET_VOLUME_URL",
    "USER_AGENT",
]
