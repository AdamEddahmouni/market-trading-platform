"""Centralized Finviz Elite request manager — rate limit, cache, auth recovery."""

from __future__ import annotations

import hashlib
import http.client
import threading
import time
import urllib.error
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from .auth_classification import FinvizFailureKind
from .config import MIN_REQUEST_INTERVAL_S
from .credential_manager import get_finviz_credential_manager
from .http_client import HttpResponse, is_network_error, urllib_get
from .redaction import FinvizHTTPError, redact_payload, redact_text, sanitize_url


class RequestPriority(IntEnum):
    OPERATOR = 0
    DISCOVERY_REFRESH = 1
    NEWS_CATALYST = 2
    ACTIVE_SYMBOL = 3
    OPTIONS_CONTEXT = 4
    GROUP_SECTOR = 5
    SLOW_FUNDAMENTAL = 6


@dataclass
class _CacheEntry:
    body: str
    status_code: int
    stored_at: float
    ttl_s: float


@dataclass
class FinvizRequestMetrics:
    request_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    rate_limit_waits: int = 0
    http_429_count: int = 0
    auth_failures: int = 0
    auth_recoveries: int = 0
    last_latency_ms: float | None = None


class FinvizRequestManager:
    """Single-flight Finviz HTTP access with credential recovery integration."""

    def __init__(self, *, min_interval_s: float = MIN_REQUEST_INTERVAL_S) -> None:
        self._min_interval_s = min_interval_s
        self._lock = threading.Lock()
        self._last_request_at = 0.0
        self._cache: dict[str, _CacheEntry] = {}
        self._inflight: dict[str, threading.Event] = {}
        self.metrics = FinvizRequestMetrics()
        self._headers = {
            "User-Agent": "Mozilla/5.0 (IMP integrated-market-platform)",
            "Accept": "text/csv,application/csv,text/plain,*/*",
        }
        self._credential_manager = get_finviz_credential_manager()
        self._credential_manager.set_http_getter(self._raw_get)

    def _cache_key(self, url: str, params: dict[str, Any]) -> str:
        canonical = redact_payload(dict(params))
        raw = f"{url}|{sorted(canonical.items())}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _wait_rate_limit(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_request_at
        if elapsed < self._min_interval_s:
            self.metrics.rate_limit_waits += 1
            time.sleep(self._min_interval_s - elapsed)
        self._last_request_at = time.monotonic()

    def _raw_get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        timeout: float = 15.0,
        headers: dict[str, str] | None = None,
    ) -> HttpResponse:
        return urllib_get(
            url,
            params=params or {},
            timeout=timeout,
            headers={**self._headers, **(headers or {})},
        )

    def _execute_request(
        self,
        url: str,
        params: dict[str, Any],
        *,
        timeout_s: float,
        api_key: str,
    ) -> tuple[int, str, str]:
        try:
            response = self._raw_get(url, params=params, timeout=timeout_s)
        except (urllib.error.URLError, http.client.HTTPException, OSError) as exc:
            if not is_network_error(exc):
                raise
            raise FinvizHTTPError(
                f"network_error: {exc.__class__.__name__}",
                url=sanitize_url(url, secret=api_key),
                secret=api_key,
            ) from exc
        body = response.text or ""
        content_type = str(response.headers.get("content-type", ""))
        return response.status_code, body, content_type

    def _handle_response_classification(
        self,
        classification,
        *,
        retried_auth: bool,
    ) -> bool:
        if classification.kind == FinvizFailureKind.RATE_LIMITED:
            self._credential_manager.mark_rate_limited()
            return False
        if classification.kind == FinvizFailureKind.PROVIDER_ERROR:
            self._credential_manager.mark_provider_unavailable()
            return False
        if classification.kind == FinvizFailureKind.AUTH_OK:
            return False
        if not self._credential_manager.should_attempt_recovery(classification):
            self._credential_manager.mark_auth_failure(classification.kind)
            return False
        if retried_auth:
            self._credential_manager.mark_auth_failure(classification.kind)
            return False
        recovered = self._credential_manager.attempt_recovery()
        if recovered:
            self.metrics.auth_recoveries += 1
            return True
        return False

    def get(
        self,
        url: str,
        *,
        params: dict[str, Any],
        priority: RequestPriority = RequestPriority.DISCOVERY_REFRESH,
        cache_ttl_s: float | None = None,
        timeout_s: float = 15.0,
        api_key: str | None = None,
    ) -> tuple[int, str, dict[str, Any]]:
        del priority
        token = api_key or self._credential_manager.get_token()
        if token and "auth" not in params:
            params = dict(params)
            params["auth"] = token
        key = self._cache_key(url, params)
        if cache_ttl_s is not None:
            cached = self._cache.get(key)
            if cached is not None and (time.monotonic() - cached.stored_at) < cached.ttl_s:
                self.metrics.cache_hits += 1
                return cached.status_code, cached.body, {"cached": True, "cache_hit": True}

        with self._lock:
            if cache_ttl_s is not None:
                cached = self._cache.get(key)
                if cached is not None and (time.monotonic() - cached.stored_at) < cached.ttl_s:
                    self.metrics.cache_hits += 1
                    return cached.status_code, cached.body, {"cached": True, "cache_hit": True}

            inflight = self._inflight.get(key)
            if inflight is not None:
                inflight.wait(timeout=timeout_s + self._min_interval_s)
                cached = self._cache.get(key)
                if cached is not None:
                    self.metrics.cache_hits += 1
                    return cached.status_code, cached.body, {"cached": True, "coalesced": True}

            event = threading.Event()
            self._inflight[key] = event
            try:
                self.metrics.cache_misses += 1
                retried_auth = False
                retried_429 = False
                active_token = ""
                status = 0
                body = ""
                while True:
                    self._wait_rate_limit()
                    active_token = self._credential_manager.get_token() or ""
                    request_params = dict(params)
                    if active_token:
                        request_params["auth"] = active_token
                    started = time.perf_counter()
                    status, body, content_type = self._execute_request(
                        url,
                        request_params,
                        timeout_s=timeout_s,
                        api_key=active_token,
                    )
                    self.metrics.last_latency_ms = (time.perf_counter() - started) * 1000.0
                    self.metrics.request_count += 1

                    if status == 429:
                        self.metrics.http_429_count += 1
                        self._credential_manager.mark_rate_limited()
                        if not retried_429:
                            retried_429 = True
                            time.sleep(self._min_interval_s)
                            continue
                        break

                    classification = self._credential_manager.classify_response(
                        status_code=status,
                        body=body,
                        content_type=content_type,
                    )
                    if classification.kind != FinvizFailureKind.AUTH_OK:
                        if status in (401, 403) or classification.triggers_recovery:
                            self.metrics.auth_failures += 1
                        if self._handle_response_classification(
                            classification,
                            retried_auth=retried_auth,
                        ):
                            retried_auth = True
                            key = self._cache_key(url, request_params)
                            continue
                    break

                if cache_ttl_s is not None and status == 200:
                    self._cache[key] = _CacheEntry(
                        body=body,
                        status_code=status,
                        stored_at=time.monotonic(),
                        ttl_s=cache_ttl_s,
                    )
                meta = {
                    "cached": False,
                    "cache_hit": False,
                    "status_code": status,
                    "latency_ms": self.metrics.last_latency_ms,
                    "url": sanitize_url(url, secret=active_token),
                }
                if active_token and body:
                    body = redact_text(body, active_token)
                return status, body, meta
            finally:
                event.set()
                self._inflight.pop(key, None)

    def clear_cache(self) -> None:
        self._cache.clear()


_MANAGER: FinvizRequestManager | None = None
_MANAGER_LOCK = threading.Lock()


def get_finviz_request_manager() -> FinvizRequestManager:
    global _MANAGER
    with _MANAGER_LOCK:
        if _MANAGER is None:
            _MANAGER = FinvizRequestManager()
        return _MANAGER


def reset_finviz_request_manager() -> None:
    global _MANAGER
    with _MANAGER_LOCK:
        _MANAGER = None
