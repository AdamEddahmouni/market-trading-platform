"""Deterministic provider-aware query planning without network side effects."""

from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Any, Callable

from ..canonical import canonical_bytes, sha256_bytes
from .identity import InstrumentIdentity
from .registry import ProviderDescriptor, ProviderRegistry


@dataclass(frozen=True, slots=True)
class ProviderPolicy:
    enabled: bool = True
    allowed_license_classes: tuple[str, ...] = ("RESEARCH_ONLY",)
    max_retries: int = 2
    base_backoff_ns: int = 1_000_000
    cache_ttl_ns: int = 1_000_000_000
    serve_stale: bool = False
    rate_budget: int = 100
    circuit_failure_limit: int = 3
    priority: int | None = None
    rate_window_ns: int = 1_000_000_000

    def __post_init__(self) -> None:
        if self.max_retries < 0 or self.base_backoff_ns < 0:
            raise ValueError("RETRY_POLICY_INVALID")
        if self.cache_ttl_ns < 0 or self.rate_budget <= 0:
            raise ValueError("RATE_OR_CACHE_POLICY_INVALID")
        if not self.allowed_license_classes:
            raise ValueError("LICENSE_POLICY_INVALID")
        if self.circuit_failure_limit <= 0 or self.rate_window_ns <= 0:
            raise ValueError("CIRCUIT_OR_RATE_WINDOW_INVALID")
        if self.priority is not None and self.priority < 0:
            raise ValueError("PROVIDER_PRIORITY_INVALID")


@dataclass(frozen=True, slots=True)
class QueryRequest:
    capability_id: str
    instrument: InstrumentIdentity
    as_of_time_ns: int | None
    freshness_max_age_ns: int | None
    license_purpose: str
    fanout: bool = False
    max_candidates: int = 1
    mode: str = "research"
    source_instance_id: str | None = None
    account_id: str | None = None
    provider_id: str | None = None

    def __post_init__(self) -> None:
        if self.as_of_time_ns is not None and self.as_of_time_ns < 0:
            raise ValueError("AS_OF_TIME_INVALID")
        if self.freshness_max_age_ns is not None and self.freshness_max_age_ns < 0:
            raise ValueError("FRESHNESS_INVALID")
        if not self.license_purpose.strip() or self.max_candidates < 1:
            raise ValueError("QUERY_REQUEST_INVALID")
        if self.mode not in {"research", "historical", "replay", "demo", "paper", "live"}:
            raise ValueError("QUERY_MODE_INVALID")
        if self.mode == "live" and self.as_of_time_ns is not None:
            raise ValueError("LIVE_AS_OF_UNSUPPORTED")


@dataclass(frozen=True, slots=True)
class QueryPlan:
    selected_provider_ids: tuple[str, ...]
    fallback_provider_ids: tuple[str, ...]
    fanout: bool
    cache_key: str
    diagnostics: tuple[str, ...]
    retry_max_retries: int = 0
    retry_backoff_ns: int = 0
    cache_ttl_ns: int = 0
    serve_stale: bool = False
    cache_status: str = "MISS"
    selection_mode: str = "single_best"


class QueryPlanner:
    def __init__(
        self,
        registry: ProviderRegistry,
        policies: dict[str, ProviderPolicy],
        clock_ns: Callable[[], int] | None = None,
        max_cache_entries: int = 256,
    ) -> None:
        self._registry = registry
        self._policies = policies
        self._clock_ns = clock_ns or (lambda: 0)
        self._failures: dict[str, int] = {}
        self._requests: dict[str, deque[int]] = {}
        self._cache: dict[str, tuple[int, object, bool]] = {}
        if max_cache_entries <= 0:
            raise ValueError("CACHE_BOUND_INVALID")
        self._max_cache_entries = max_cache_entries

    def plan(self, request: QueryRequest) -> QueryPlan:
        eligible: list[ProviderDescriptor] = []
        diagnostics: list[str] = []
        descriptors = self._registry.providers_for(request.capability_id)
        for descriptor in descriptors:
            if request.provider_id is not None and descriptor.provider_id != request.provider_id:
                diagnostics.append(f"PROVIDER_NOT_REQUESTED:{descriptor.provider_id}")
                continue
            policy = self._policies.get(descriptor.provider_id, ProviderPolicy())
            capability = next(
                item for item in descriptor.capabilities if item.capability_id == request.capability_id
            )
            if not policy.enabled:
                diagnostics.append(f"DISABLED:{descriptor.provider_id}")
                continue
            if descriptor.health_state not in {"HEALTHY", "DEGRADED"}:
                diagnostics.append(f"UNHEALTHY:{descriptor.provider_id}")
                continue
            if self._failures.get(descriptor.provider_id, 0) >= policy.circuit_failure_limit:
                diagnostics.append(f"CIRCUIT_OPEN:{descriptor.provider_id}")
                continue
            if request.license_purpose not in policy.allowed_license_classes:
                diagnostics.append(f"LICENSE_REJECTED:{descriptor.provider_id}")
                continue
            if capability.license_class not in policy.allowed_license_classes:
                diagnostics.append(f"LICENSE_UNAVAILABLE:{descriptor.provider_id}")
                continue
            if request.as_of_time_ns is not None and not capability.supports_pit:
                diagnostics.append(f"PIT_UNSUPPORTED:{descriptor.provider_id}")
                continue
            if (
                request.freshness_max_age_ns is not None
                and capability.freshness_sla_ns is not None
                and capability.freshness_sla_ns > request.freshness_max_age_ns
            ):
                diagnostics.append(f"FRESHNESS_UNAVAILABLE:{descriptor.provider_id}")
                continue
            now_ns = self._clock_ns()
            requests = self._requests.setdefault(descriptor.provider_id, deque())
            while requests and requests[0] <= now_ns - policy.rate_window_ns:
                requests.popleft()
            if len(requests) >= policy.rate_budget:
                diagnostics.append(f"RATE_BUDGET_EXHAUSTED:{descriptor.provider_id}")
                continue
            eligible.append(descriptor)

        selected_count = request.max_candidates if request.fanout else 1
        eligible.sort(
            key=lambda item: (
                self._policies.get(item.provider_id, ProviderPolicy()).priority
                if self._policies.get(item.provider_id, ProviderPolicy()).priority is not None
                else item.priority,
                item.provider_id,
            )
        )
        selected = tuple(item.provider_id for item in eligible[:selected_count])
        fallback_start = selected_count if request.fanout else 1
        fallback = tuple(item.provider_id for item in eligible[fallback_start:])
        if not eligible:
            diagnostics.append("NO_ELIGIBLE_PROVIDER")
        cache_payload = {
            "as_of_time_ns": request.as_of_time_ns,
            "capability_id": request.capability_id,
            "freshness_max_age_ns": request.freshness_max_age_ns,
            "instrument": request.instrument.qualified_id(),
            "license_purpose": request.license_purpose,
            "mode": request.mode,
            "source_instance_id": request.source_instance_id,
            "account_id": request.account_id,
            "provider_id": request.provider_id,
            "eligible_provider_ids": [item.provider_id for item in eligible],
            "fanout": request.fanout,
            "max_candidates": request.max_candidates,
        }
        cache_key = f"query-{sha256_bytes(canonical_bytes(cache_payload))[:24]}"
        policy = self._policies.get(selected[0], ProviderPolicy()) if selected else ProviderPolicy()
        cache_status = self._cache_status(cache_key)
        return QueryPlan(
            selected,
            fallback,
            request.fanout,
            cache_key,
            tuple(sorted(diagnostics)),
            policy.max_retries,
            policy.base_backoff_ns,
            policy.cache_ttl_ns,
            policy.serve_stale,
            cache_status,
            "fanout" if request.fanout else "single_best",
        )

    def record_result(self, provider_id: str, success: bool) -> None:
        if success:
            self._failures[provider_id] = 0
        else:
            self._failures[provider_id] = self._failures.get(provider_id, 0) + 1
        self._requests.setdefault(provider_id, deque()).append(self._clock_ns())

    def cache_put(
        self,
        cache_key: str,
        value: object,
        *,
        now_ns: int | None = None,
        ttl_ns: int = 0,
        serve_stale: bool = False,
    ) -> None:
        if not cache_key or now_ns is None:
            now_ns = self._clock_ns()
        if cache_key not in self._cache and len(self._cache) >= self._max_cache_entries:
            oldest_key = min(self._cache, key=lambda key: self._cache[key][0])
            del self._cache[oldest_key]
        self._cache[cache_key] = (now_ns + max(0, ttl_ns), value, serve_stale)

    def cache_get(self, cache_key: str, *, now_ns: int | None = None) -> object | None:
        entry = self._cache.get(cache_key)
        if entry is None:
            return None
        now = self._clock_ns() if now_ns is None else now_ns
        expires, value, serve_stale = entry
        if now <= expires or serve_stale:
            return value
        del self._cache[cache_key]
        return None

    def _cache_status(self, cache_key: str) -> str:
        return "FRESH" if cache_key in self._cache else "MISS"


__all__ = ["ProviderPolicy", "QueryPlan", "QueryPlanner", "QueryRequest"]
