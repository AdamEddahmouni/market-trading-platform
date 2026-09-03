"""HTTP transport for official CFTC Public Reporting SODA API."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .datasets import CotDataset

CFTC_SODA_BASE = "https://publicreporting.cftc.gov/resource"
DEFAULT_USER_AGENT = "integrated-market-platform-cot/1.0 (+https://www.cftc.gov/MarketReports/CommitmentsofTraders/)"


class CotTransportError(Exception):
    """CFTC source unavailable or malformed response."""


class CotTransport:
    """Bounded public API client — no credentials required for low-volume use."""

    def __init__(
        self,
        *,
        base_url: str = CFTC_SODA_BASE,
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval_seconds: float = 0.25,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.user_agent = user_agent
        self.min_interval_seconds = min_interval_seconds
        self.timeout_seconds = timeout_seconds
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)

    def _request_json(self, url: str) -> list[dict[str, Any]]:
        self._throttle()
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise CotTransportError(f"SOURCE_UNAVAILABLE: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise CotTransportError(f"SOURCE_UNAVAILABLE: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise CotTransportError("SOURCE_UNAVAILABLE: invalid JSON") from exc
        finally:
            self._last_request_at = time.monotonic()

        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            return [payload]
        raise CotTransportError("SOURCE_UNAVAILABLE: unexpected payload shape")

    def query_dataset(
        self,
        dataset: CotDataset,
        *,
        where: str = "",
        select: str = "",
        order: str = "",
        limit: int = 1000,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"$limit": str(limit), "$offset": str(offset)}
        if where:
            params["$where"] = where
        if select:
            params["$select"] = select
        if order:
            params["$order"] = order
        query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = f"{self.base_url}/{dataset.value}.json?{query}"
        return self._request_json(url)

    def query_product_hierarchy(
        self,
        *,
        where: str = "",
        limit: int = 1000,
        order: str = "",
    ) -> list[dict[str, Any]]:
        return self.query_dataset(
            CotDataset.PRODUCT_HIERARCHY,
            where=where,
            limit=limit,
            order=order,
        )

    def reachable(self) -> bool:
        try:
            rows = self.query_dataset(CotDataset.TFF_FUTURES_ONLY, limit=1)
            return isinstance(rows, list)
        except CotTransportError:
            return False


__all__ = ["CFTC_SODA_BASE", "CotTransport", "CotTransportError", "DEFAULT_USER_AGENT"]
