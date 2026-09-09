"""G7 — observational lane runtime: canonical store → existing analytics.

Wires ObservationalStateStore into order-flow, book-feature, options, and
futures lanes without redesigning formulas. All derived outputs carry
instrument identity, provider provenance, source/received times, freshness,
and formula/method versions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..order_flow.cvd import compute_cvd_state
from ..order_flow.contracts import cvd_state_to_dict
from ..order_flow.ofi import (
    OFI_METHOD_MULTILEVEL_PRICE_ALIGNED,
    compute_ofi,
    usable_ofi_value,
)
from ..providers.runtime_capability import EntitlementState, ProviderHealth
from ..xa01.enums import InstrumentKind
from .depth_admission import DepthAdmissionContext
from .live_config import depth_freshness_policy
from .observational_state import ObservationalStateStore, QuoteSnapshot


@dataclass(frozen=True, slots=True)
class LaneProvenance:
    instrument_id: str
    provider: str
    source_time_ns: int | None
    received_time_ns: int | None
    quality: str
    admission: str
    freshness_state: str
    formula_method: str | None = None
    formula_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "admission": self.admission,
            "formula_method": self.formula_method,
            "formula_version": self.formula_version,
            "freshness_state": self.freshness_state,
            "instrument_id": self.instrument_id,
            "provider": self.provider,
            "received_time_ns": self.received_time_ns,
            "source_time_ns": self.source_time_ns,
        }


@dataclass
class ObservationalLaneRuntime:
    """Derives lane outputs from the canonical observational store."""

    store: ObservationalStateStore
    _prev_book_snapshots: dict[str, dict[str, Any]] = field(default_factory=dict)
    _depth_context: DepthAdmissionContext = field(default_factory=DepthAdmissionContext)
    _as_of_time_ns: int | None = None

    def build_l1_payload(self, instrument_id: str) -> dict[str, Any] | None:
        quote = self.store.quote_for(instrument_id)
        if quote is None:
            return None
        freshness = _quote_freshness_state(quote)
        return {
            "available": True,
            "instrument_id": quote.instrument_id,
            "provenance": _quote_provenance(quote, freshness).to_dict(),
            "quote": quote.to_dict(),
        }

    def build_cvd_payload(
        self,
        instrument_id: str,
        *,
        previous_anchor: str | None = None,
    ) -> dict[str, Any]:
        symbol = instrument_id.upper()
        trades = self.store.trades_for(symbol)
        if not trades:
            return {
                "available": False,
                "instrument_id": symbol,
                "reason": "INSUFFICIENT_TRADE_CLASSIFICATION",
                "state": "UNAVAILABLE",
            }
        bars: list[dict[str, object]] = []
        provider = ""
        for trade in trades:
            side = str(trade.get("aggressor_side") or "").upper()
            if side == "UNKNOWN":
                continue
            signed = 0.0
            if side == "SELL":
                signed = -abs(float(trade["quantity"]))
            elif side == "BUY":
                signed = abs(float(trade["quantity"]))
            provenance = str(trade.get("aggressor_provenance") or "")
            quality = "tick" if provenance in {"PROVIDER_NATIVE", "EXCHANGE_NATIVE"} else "neutral"
            bars.append(
                {
                    "bar_time": str(trade.get("event_time_ns", "")),
                    "delta": signed,
                    "volume": abs(float(trade["quantity"])),
                    "quality": quality,
                    "aggressor_provenance": provenance,
                }
            )
            provider = str(trade.get("provider") or provider)
        if not bars:
            return {
                "available": False,
                "instrument_id": symbol,
                "reason": "INSUFFICIENT_TRADE_CLASSIFICATION",
                "state": "UNAVAILABLE",
            }
        cvd = compute_cvd_state(bars, previous_anchor=previous_anchor)
        if cvd is None:
            return {
                "available": False,
                "instrument_id": symbol,
                "reason": "CVD_COMPUTATION_FAILED",
                "state": "UNAVAILABLE",
            }
        last_trade = trades[-1]
        return {
            "available": True,
            "cvd": cvd_state_to_dict(cvd),
            "instrument_id": symbol,
            "provenance": LaneProvenance(
                instrument_id=symbol,
                provider=provider,
                source_time_ns=int(last_trade.get("event_time_ns") or 0) or None,
                received_time_ns=int(last_trade.get("available_time_ns") or 0) or None,
                quality=str(last_trade.get("quality") or "PASS"),
                admission=str(last_trade.get("admission") or "PASS"),
                freshness_state="FRESH",
                formula_method="cvd_session_v1",
                formula_version="1",
            ).to_dict(),
            "trade_count": len(trades),
        }

    def configure_depth_context(
        self,
        *,
        as_of_time_ns: int | None = None,
        entitlement: EntitlementState = EntitlementState.UNKNOWN,
        provider_health: ProviderHealth = ProviderHealth.UNKNOWN,
        provider_connected: bool = True,
        generation: int = 0,
    ) -> None:
        self._as_of_time_ns = as_of_time_ns
        self._depth_context = DepthAdmissionContext(
            entitlement=entitlement,
            provider_health=provider_health,
            provider_connected=provider_connected,
            generation=generation,
        )

    def build_ofi_payload(self, instrument_id: str) -> dict[str, Any]:
        symbol = instrument_id.upper()
        book = self.store.book_for(symbol)
        if book is None:
            return {
                "available": False,
                "instrument_id": symbol,
                "reason": "NO_CANONICAL_BOOK",
                "state": "UNAVAILABLE",
            }
        stale_block = self._depth_stale_block(symbol, book)
        if stale_block is not None:
            return stale_block
        if not book.get("book_state_valid"):
            return {
                "available": False,
                "book_state_valid": False,
                "book_status": book.get("book_status"),
                "instrument_id": symbol,
                "reason": "INVALID_BOOK",
                "sequence_status": book.get("sequence_status"),
                "state": "UNAVAILABLE",
            }
        prev = self._prev_book_snapshots.get(symbol)
        curr = _book_as_snapshot(book)
        curr_received = book.get("received_ns")
        if prev is None:
            self._prev_book_snapshots[symbol] = {**curr, "_received_ns": curr_received}
            return {
                "available": False,
                "instrument_id": symbol,
                "reason": "AWAITING_SECOND_SNAPSHOT",
                "sequence_status": book.get("sequence_status"),
                "state": "DEGRADED",
            }
        prev_received = prev.get("_received_ns")
        if prev_received == curr_received:
            return {
                "available": False,
                "instrument_id": symbol,
                "reason": "AWAITING_SECOND_SNAPSHOT",
                "sequence_status": book.get("sequence_status"),
                "state": "DEGRADED",
            }
        ofi_result = compute_ofi(
            {k: v for k, v in prev.items() if not k.startswith("_")},
            curr,
            method=OFI_METHOD_MULTILEVEL_PRICE_ALIGNED,
        )
        self._prev_book_snapshots[symbol] = {**curr, "_received_ns": curr_received}
        freshness = _book_freshness_state(book)
        value = usable_ofi_value(ofi_result)
        return {
            "available": value is not None,
            "book_state_valid": ofi_result.book_state_valid,
            "instrument_id": symbol,
            "ofi_method": ofi_result.ofi_method,
            "ofi_version": ofi_result.ofi_version,
            "ofi_value": value,
            "provenance": LaneProvenance(
                instrument_id=symbol,
                provider=str(book.get("provider") or ""),
                source_time_ns=book.get("event_time_ns"),
                received_time_ns=book.get("received_ns"),
                quality=str(book.get("quality") or "PASS"),
                admission=str(book.get("admission") or "PASS"),
                freshness_state=freshness,
                formula_method=ofi_result.ofi_method,
                formula_version=ofi_result.ofi_version,
            ).to_dict(),
            "sequence_status": book.get("sequence_status"),
            "state": "READY" if value is not None else "UNAVAILABLE",
        }

    def build_book_features_payload(self, instrument_id: str) -> dict[str, Any]:
        symbol = instrument_id.upper()
        book = self.store.book_for(symbol)
        if book is None:
            return {
                "available": False,
                "instrument_id": symbol,
                "reason": "NO_CANONICAL_BOOK",
                "state": "UNAVAILABLE",
            }
        stale_block = self._depth_stale_block(symbol, book)
        if stale_block is not None:
            return stale_block
        features = book.get("book_features")
        if not book.get("book_state_valid"):
            return {
                "available": False,
                "book_features": features,
                "book_state_valid": False,
                "book_status": book.get("book_status"),
                "instrument_id": symbol,
                "reason": "INVALID_BOOK",
                "sequence_status": book.get("sequence_status"),
                "state": "UNAVAILABLE",
            }
        freshness = _book_freshness_state(book)
        return {
            "available": features is not None,
            "book_features": features,
            "book_state_valid": True,
            "instrument_id": symbol,
            "provenance": LaneProvenance(
                instrument_id=symbol,
                provider=str(book.get("provider") or ""),
                source_time_ns=book.get("event_time_ns"),
                received_time_ns=book.get("received_ns"),
                quality=str(book.get("quality") or "PASS"),
                admission=str(book.get("admission") or "PASS"),
                freshness_state=freshness,
                formula_method="book_features_v1",
                formula_version="1",
            ).to_dict(),
            "sequence_status": book.get("sequence_status"),
            "state": "READY" if features is not None else "DEGRADED",
        }

    def build_options_observation_payload(
        self,
        *,
        instrument_id: str,
        instrument_kind: str,
        underlying_id: str | None = None,
        chain_status: str = "available",
        delayed: bool = False,
        stale: bool = False,
        multiplier: float | None = None,
        provider: str = "",
        source_time_ns: int | None = None,
    ) -> dict[str, Any]:
        if instrument_kind != InstrumentKind.OPTION_CONTRACT.value:
            return {
                "available": False,
                "instrument_id": instrument_id,
                "reason": "OPTION_CONTRACT_REQUIRED",
                "state": "UNSUPPORTED_INSTRUMENT",
            }
        if underlying_id and instrument_id.upper() == underlying_id.upper():
            return {
                "available": False,
                "instrument_id": instrument_id,
                "reason": "UNDERLYING_ONLY_AMBIGUOUS",
                "state": "UNSUPPORTED_INSTRUMENT",
            }
        if chain_status == "missing":
            return {
                "available": False,
                "instrument_id": instrument_id,
                "reason": "CHAIN_MISSING",
                "state": "UNAVAILABLE",
            }
        if stale:
            return {
                "available": False,
                "instrument_id": instrument_id,
                "reason": "STALE_CHAIN",
                "state": "STALE",
            }
        timeliness = "DELAYED" if delayed else "REAL_TIME"
        state = "DEGRADED" if delayed else "READY"
        return {
            "analytics_authority": "NON_AUTHORITATIVE",
            "available": True,
            "instrument_id": instrument_id.upper(),
            "instrument_kind": instrument_kind,
            "multiplier": multiplier,
            "provenance": {
                "instrument_id": instrument_id.upper(),
                "provider": provider,
                "source_time_ns": source_time_ns,
                "timeliness": timeliness,
            },
            "state": state,
        }

    def build_futures_observation_payload(
        self,
        *,
        instrument_id: str,
        instrument_kind: str,
        price: float | None,
        multiplier: float | None,
        provider: str = "",
        source_time_ns: int | None = None,
    ) -> dict[str, Any]:
        if instrument_kind in {
            InstrumentKind.FUTURE_FAMILY.value,
            InstrumentKind.CONTINUOUS_SERIES.value,
        }:
            return {
                "available": False,
                "instrument_id": instrument_id,
                "reason": "SPECIFIC_FUTURE_CONTRACT_REQUIRED",
                "state": "UNSUPPORTED_INSTRUMENT",
            }
        if instrument_kind != InstrumentKind.FUTURE_CONTRACT.value:
            return {
                "available": False,
                "instrument_id": instrument_id,
                "reason": "FUTURE_CONTRACT_REQUIRED",
                "state": "UNSUPPORTED_INSTRUMENT",
            }
        if multiplier is None:
            return {
                "available": False,
                "instrument_id": instrument_id,
                "reason": "MULTIPLIER_REQUIRED",
                "state": "UNAVAILABLE",
            }
        if price is None:
            return {
                "available": False,
                "instrument_id": instrument_id,
                "reason": "NO_QUOTE",
                "state": "UNAVAILABLE",
            }
        return {
            "analytics_authority": "NON_AUTHORITATIVE",
            "available": True,
            "instrument_id": instrument_id.upper(),
            "instrument_kind": instrument_kind,
            "multiplier": multiplier,
            "notional_per_point": multiplier,
            "price": price,
            "provenance": {
                "instrument_id": instrument_id.upper(),
                "provider": provider,
                "source_time_ns": source_time_ns,
            },
            "state": "READY",
        }

    def build_evidence_bundle(self, instrument_id: str) -> dict[str, Any]:
        """Combined lane outputs with deterministic evidence hash."""
        symbol = instrument_id.upper()
        bundle = {
            "book_features": self.build_book_features_payload(symbol),
            "cvd": self.build_cvd_payload(symbol),
            "instrument_id": symbol,
            "l1": self.build_l1_payload(symbol),
            "ofi": self.build_ofi_payload(symbol),
        }
        bundle["evidence_hash"] = sha256_bytes(canonical_bytes(bundle))[:32]
        return bundle

    def reset_generation(self, instrument_id: str) -> None:
        """Clear per-instrument lane carry state after book generation reset."""
        key = instrument_id.upper()
        self._prev_book_snapshots.pop(key, None)

    def _depth_stale_block(self, symbol: str, book: dict[str, Any]) -> dict[str, Any] | None:
        as_of = self._as_of_time_ns
        if as_of is None:
            return None
        provider = str(book.get("provider") or "")
        admissibility = self.store.depth_admissibility_for(
            symbol,
            as_of_time_ns=as_of,
            provider_id=provider,
            context=self._depth_context,
            policy=depth_freshness_policy(provider),
        )
        if admissibility.admissible:
            return None
        return {
            "available": False,
            "book_state_valid": book.get("book_state_valid", False),
            "depth_admissibility": admissibility.to_dict(),
            "instrument_id": symbol,
            "reason": admissibility.reason_code,
            "state": admissibility.status.value,
        }


def _book_as_snapshot(book: dict[str, Any]) -> dict[str, Any]:
    return {
        "asks": list(book.get("asks") or []),
        "bids": list(book.get("bids") or []),
        "book_sequence": book.get("book_sequence"),
        "book_state_valid": book.get("book_state_valid"),
    }


def _book_freshness_state(book: dict[str, Any]) -> str:
    explicit = book.get("freshness_status")
    if explicit:
        return str(explicit)
    status = str(book.get("book_status") or "")
    if status == "STALE":
        return "STALE"
    if not book.get("book_state_valid"):
        return "INVALID"
    return "FRESH"


def _quote_freshness_state(quote: QuoteSnapshot) -> str:
    if quote.quality == "STALE":
        return "STALE"
    if quote.quality == "DEGRADED":
        return "DEGRADED"
    return "FRESH"


def _quote_provenance(quote: QuoteSnapshot, freshness: str) -> LaneProvenance:
    return LaneProvenance(
        instrument_id=quote.instrument_id,
        provider=quote.provider,
        source_time_ns=quote.event_time_ns,
        received_time_ns=quote.received_ns,
        quality=quote.quality,
        admission=quote.admission,
        freshness_state=freshness,
    )


__all__ = [
    "LaneProvenance",
    "ObservationalLaneRuntime",
]
