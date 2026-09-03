"""Capability state is multi-dimensional; never flatten to a single boolean."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class MarketCapability(StrEnum):
    US_EQUITY_SNAPSHOT = "US_EQUITY_SNAPSHOT"
    US_EQUITY_L1 = "US_EQUITY_L1"
    US_EQUITY_TICKS = "US_EQUITY_TICKS"
    US_EQUITY_DEPTH = "US_EQUITY_DEPTH"
    US_EQUITY_BARS = "US_EQUITY_BARS"
    US_EQUITY_EXTENDED_HOURS = "US_EQUITY_EXTENDED_HOURS"
    US_EQUITY_OVERNIGHT = "US_EQUITY_OVERNIGHT"
    US_OPTIONS_QUOTE = "US_OPTIONS_QUOTE"
    US_FUTURES_QUOTE = "US_FUTURES_QUOTE"
    CRYPTO_SPOT_QUOTE = "CRYPTO_SPOT_QUOTE"
    CRYPTO_SPOT_TICKS = "CRYPTO_SPOT_TICKS"
    CRYPTO_SPOT_DEPTH = "CRYPTO_SPOT_DEPTH"


@dataclass(frozen=True, slots=True)
class CapabilityState:
    capability: MarketCapability
    provider_supports: bool
    account_entitled: bool
    adapter_implemented: bool
    runtime_tested: bool
    data_currently_fresh: bool
    evidence_class: str = "UNTESTED"
    reason_code: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_entitled": self.account_entitled,
            "adapter_implemented": self.adapter_implemented,
            "capability": self.capability.value,
            "data_currently_fresh": self.data_currently_fresh,
            "evidence_class": self.evidence_class,
            "notes": self.notes,
            "provider_supports": self.provider_supports,
            "reason_code": self.reason_code,
            "runtime_tested": self.runtime_tested,
        }


def merge_capability(state: CapabilityState, **updates: Any) -> CapabilityState:
    payload = state.to_dict()
    payload.update(updates)
    payload["capability"] = MarketCapability(payload["capability"])
    return CapabilityState(**payload)
