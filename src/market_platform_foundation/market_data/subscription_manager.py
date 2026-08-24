"""Reference-counted live subscription manager with priority and quota."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class SubscriptionPriority(IntEnum):
    ACTIVE_EXECUTION_CONTEXT = 0
    ACTIVE_WORKSPACE = 1
    PINNED_WATCHLIST = 2
    BACKGROUND_RESEARCH = 3
    BACKGROUND_EXPLORE = BACKGROUND_RESEARCH


CAPABILITY_TO_MOOMOO: dict[str, str] = {
    "BASIC_QUOTE": "US_EQUITY_L1",
    "US_EQUITY_L1": "US_EQUITY_L1",
    "TRADES": "US_EQUITY_TICKS",
    "US_EQUITY_TICKS": "US_EQUITY_TICKS",
    "ORDER_BOOK": "US_EQUITY_DEPTH",
    "US_EQUITY_DEPTH": "US_EQUITY_DEPTH",
}


@dataclass(frozen=True, slots=True)
class SubscriptionKey:
    instrument_id: str
    capability: str

    def normalized(self) -> SubscriptionKey:
        cap = CAPABILITY_TO_MOOMOO.get(self.capability, self.capability)
        return SubscriptionKey(instrument_id=self.instrument_id.upper(), capability=cap)


@dataclass(frozen=True, slots=True)
class ConsumerHandle:
    consumer_id: str
    priority: int


@dataclass
class SubscriptionResult:
    accepted: bool
    key: SubscriptionKey
    reason: str | None = None
    provider_subscription_active: bool = False
    ref_count: int = 0


@dataclass
class LiveSubscriptionManager:
    max_quota: int = 100
    refs: dict[str, dict[str, ConsumerHandle]] = field(default_factory=dict)
    active_keys: set[str] = field(default_factory=set)

    def _key_str(self, key: SubscriptionKey) -> str:
        normalized = key.normalized()
        return f"{normalized.instrument_id}:{normalized.capability}"

    def acquire(
        self,
        *,
        instrument_id: str,
        capability: str,
        consumer_id: str,
        priority: int = SubscriptionPriority.ACTIVE_WORKSPACE,
    ) -> SubscriptionResult:
        key = SubscriptionKey(instrument_id=instrument_id, capability=capability).normalized()
        key_str = self._key_str(key)
        consumers = self.refs.setdefault(key_str, {})
        if consumer_id in consumers:
            return SubscriptionResult(
                accepted=True,
                key=key,
                provider_subscription_active=key_str in self.active_keys,
                ref_count=len(consumers),
            )
        if key_str not in self.active_keys and len(self.active_keys) >= self.max_quota:
            return SubscriptionResult(
                accepted=False,
                key=key,
                reason="QUOTA_EXHAUSTED",
                provider_subscription_active=False,
                ref_count=len(consumers),
            )
        consumers[consumer_id] = ConsumerHandle(consumer_id=consumer_id, priority=int(priority))
        if key_str not in self.active_keys:
            self.active_keys.add(key_str)
        return SubscriptionResult(
            accepted=True,
            key=key,
            provider_subscription_active=True,
            ref_count=len(consumers),
        )

    def release(self, *, instrument_id: str, capability: str, consumer_id: str) -> SubscriptionResult:
        key = SubscriptionKey(instrument_id=instrument_id, capability=capability).normalized()
        key_str = self._key_str(key)
        consumers = self.refs.get(key_str, {})
        consumers.pop(consumer_id, None)
        if not consumers:
            self.refs.pop(key_str, None)
            self.active_keys.discard(key_str)
        return SubscriptionResult(
            accepted=True,
            key=key,
            provider_subscription_active=key_str in self.active_keys,
            ref_count=len(consumers),
        )

    def active_subscriptions(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key_str in sorted(self.active_keys):
            instrument, capability = key_str.split(":", 1)
            consumers = self.refs.get(key_str, {})
            rows.append(
                {
                    "capability": capability,
                    "consumer_count": len(consumers),
                    "consumers": sorted(consumers.keys()),
                    "instrument_id": instrument,
                    "provider_subscription_active": True,
                }
            )
        return rows

    def quota_report(self) -> dict[str, Any]:
        return {
            "active_count": len(self.active_keys),
            "imp_calculated_usage": len(self.active_keys),
            "max_quota": self.max_quota,
            "provider_quota": self.max_quota,
            "remaining": max(0, self.max_quota - len(self.active_keys)),
            "reconciliation": "IMP_USAGE_VS_CONFIGURED_OR_PROVIDER_QUOTA",
        }

    def restore_after_reconnect(self, required_keys: list[SubscriptionKey] | None = None) -> list[str]:
        """Return key strings that need provider re-subscribe after reconnect."""

        keys = required_keys or [SubscriptionKey(*item.split(":", 1)) for item in self.active_keys]
        return [self._key_str(key) for key in keys]
