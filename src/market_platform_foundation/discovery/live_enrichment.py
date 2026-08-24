"""Provider-neutral live enrichment for mixed discovery candidates."""

from __future__ import annotations

import math
import os
from collections.abc import Callable, Sequence
from typing import Any, Protocol

from ..clock import monotonic_wall_ns
from ..market_data.subscription_manager import SubscriptionPriority
from .mixed import MixedCandidate


CONSUMER_ID = "discover-live-screener"
DEFAULT_LIVE_CANDIDATE_CAP = 12


def discovery_live_candidate_cap() -> int:
    raw = os.getenv("IMP_DISCOVERY_LIVE_CANDIDATES", str(DEFAULT_LIVE_CANDIDATE_CAP)).strip()
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_LIVE_CANDIDATE_CAP
    return value if value > 0 else DEFAULT_LIVE_CANDIDATE_CAP


class MarketCandidateEnricher(Protocol):
    def reconcile(self, candidates: Sequence[MixedCandidate]) -> list[dict[str, Any]]: ...

    def enrich(self, candidates: Sequence[MixedCandidate]) -> dict[str, dict[str, Any]]: ...

    def health(self) -> dict[str, Any]: ...


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _unavailable_record(reason: str) -> dict[str, Any]:
    return {
        "provider": "MOOMOO",
        "status": "UNAVAILABLE",
        "as_of_ns": None,
        "freshness_ms": None,
        "last_price": None,
        "bid_price": None,
        "ask_price": None,
        "spread_pct": None,
        "volume": None,
        "quality": "UNAVAILABLE",
        "reason": reason,
    }


class MoomooCandidateEnricher:
    """Read admitted Moomoo L1 and own only the screener consumer's references."""

    def __init__(
        self,
        runtime: Any | None,
        *,
        cap: int | None = None,
        stale_after_ms: int = 5_000,
        now_ns: Callable[[], int] = monotonic_wall_ns,
    ) -> None:
        self._runtime = runtime
        self._cap = cap if cap is not None and cap > 0 else discovery_live_candidate_cap()
        self._stale_after_ms = stale_after_ms
        self._now_ns = now_ns
        self._subscribed_symbols: set[str] = set()
        self._admission_reasons: dict[str, str] = {}

    @property
    def subscribed_symbols(self) -> set[str]:
        return set(self._subscribed_symbols)

    def _targets(self, candidates: Sequence[MixedCandidate]) -> list[str]:
        ordered = sorted(
            candidates,
            key=lambda item: (item.queue_rank if item.queue_rank is not None else 1_000_000, item.instrument_id),
        )
        near_cutoff = [
            item.instrument_id
            for item in ordered
            if item.instrument_id in self._subscribed_symbols
            and (item.queue_rank or 1_000_000) <= self._cap + 3
        ]
        targets: list[str] = near_cutoff[: self._cap]
        for item in ordered:
            if len(targets) >= self._cap:
                break
            if item.instrument_id not in targets:
                targets.append(item.instrument_id)
        return targets

    def reconcile(self, candidates: Sequence[MixedCandidate]) -> list[dict[str, Any]]:
        if self._runtime is None:
            return []
        targets = self._targets(candidates)
        for symbol in set(self._admission_reasons).difference(targets):
            self._admission_reasons.pop(symbol, None)
        outcomes: list[dict[str, Any]] = []

        for symbol in sorted(self._subscribed_symbols.difference(targets)):
            released = self._runtime.unsubscribe(
                instrument_id=symbol,
                capabilities=["BASIC_QUOTE"],
                consumer_id=CONSUMER_ID,
            )
            outcomes.extend(dict(row) for row in released)
            self._subscribed_symbols.discard(symbol)
            self._admission_reasons.pop(symbol, None)

        for symbol in targets:
            if symbol in self._subscribed_symbols:
                continue
            acquired = self._runtime.subscribe(
                instrument_id=symbol,
                capabilities=["BASIC_QUOTE"],
                consumer_id=CONSUMER_ID,
                priority=int(SubscriptionPriority.BACKGROUND_RESEARCH),
            )
            for row in acquired:
                normalized = dict(row)
                outcomes.append(normalized)
                if normalized.get("accepted"):
                    self._subscribed_symbols.add(symbol)
                    self._admission_reasons.pop(symbol, None)
                elif normalized.get("reason"):
                    self._admission_reasons[symbol] = str(normalized["reason"])
        return outcomes

    def enrich(self, candidates: Sequence[MixedCandidate]) -> dict[str, dict[str, Any]]:
        if self._runtime is None:
            return {
                candidate.instrument_id: _unavailable_record("MOOMOO_RUNTIME_UNAVAILABLE")
                for candidate in candidates
            }
        result: dict[str, dict[str, Any]] = {}
        now_ns = self._now_ns()
        for candidate in candidates:
            symbol = candidate.instrument_id
            quote = self._runtime.state.quote_for(symbol)
            if quote is None:
                reason = (
                    "AWAITING_FIRST_EVENT"
                    if symbol in self._subscribed_symbols
                    else self._admission_reasons.get(symbol, "NOT_SUBSCRIBED")
                )
                record = _unavailable_record(reason)
                record["status"] = "SNAPSHOT"
                record["provider"] = "FINVIZ_ELITE"
                record["quality"] = candidate.quality
                record["as_of_ns"] = candidate.available_time_ns
                record["last_price"] = _finite(candidate.metrics.get("price"))
                record["volume"] = _finite(candidate.metrics.get("volume"))
                result[symbol] = record
                continue

            freshness_ms = max(0, (now_ns - int(quote.received_ns)) // 1_000_000)
            status = "LIVE" if freshness_ms <= self._stale_after_ms else "STALE"
            bid = _finite(quote.bid_price)
            ask = _finite(quote.ask_price)
            last = _finite(quote.last_price)
            volume = _finite(quote.volume)
            spread_pct: float | None = None
            reason: str | None = None
            quality = str(quote.quality or "DEGRADED").upper()
            if bid is not None and ask is not None:
                midpoint = (bid + ask) / 2.0
                if ask < bid:
                    quality = "DEGRADED"
                    reason = "CROSSED_MARKET"
                elif midpoint > 0:
                    spread_pct = round(((ask - bid) / midpoint) * 100.0, 4)
                else:
                    quality = "DEGRADED"
                    reason = "INVALID_MARKET"
            if status == "STALE" and reason is None:
                reason = "STALE_QUOTE"
            result[symbol] = {
                "provider": str(quote.provider or "MOOMOO").upper(),
                "status": status,
                "as_of_ns": int(quote.available_time_ns),
                "freshness_ms": freshness_ms,
                "last_price": last,
                "bid_price": bid,
                "ask_price": ask,
                "spread_pct": spread_pct,
                "volume": volume,
                "quality": quality,
                "reason": reason,
            }
        return result

    def health(self) -> dict[str, Any]:
        if self._runtime is None:
            return {
                "provider": "MOOMOO",
                "connection": "UNAVAILABLE",
                "reason": "MOOMOO_RUNTIME_UNAVAILABLE",
                "subscribed_candidates": 0,
            }
        subscriptions = getattr(self._runtime, "subscriptions", None)
        quota = subscriptions.quota_report() if subscriptions is not None else {}
        lifecycle = getattr(self._runtime, "lifecycle", None)
        connection = "AVAILABLE"
        reason = None
        if lifecycle is not None:
            state = getattr(lifecycle, "connection_state", None)
            connection = str(getattr(state, "value", state) or "AVAILABLE").upper()
            reason = getattr(lifecycle, "last_error", None)
        return {
            "provider": "MOOMOO",
            "connection": connection,
            "reason": reason,
            "subscribed_candidates": len(self._subscribed_symbols),
            "quota": quota,
        }
