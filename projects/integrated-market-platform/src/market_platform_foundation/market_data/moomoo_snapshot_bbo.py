"""Item 7 — lawful Moomoo ``get_market_snapshot`` BBO assessment and capture mapping.

Runtime authority for SNAPSHOT_BBO (distinct from ``US_EQUITY_L1``). Never fabricates
bid/ask from ``last_price`` or trade prices.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from .capture import CAPTURE_SCHEMA_VERSION
from .normalization import PROVIDER_ID as MOOMOO_OPEND_PROVIDER_ID

SNAPSHOT_BBO_CAPABILITY = "SNAPSHOT_BBO"
ITEM7_ADAPTER_VERSION = "1.0.0"
VENDOR_API_METHOD = "OpenQuoteContext.get_market_snapshot"

OUTCOME_REAL_SNAPSHOT_BBO_VALIDATED = "REAL_SNAPSHOT_BBO_VALIDATED"
OUTCOME_DERIVED_BBO_DESIGN_REQUIRED = "DERIVED_BBO_DESIGN_REQUIRED"

DEFAULT_SYMBOL = "US.AAPL"
DEFAULT_STALE_THRESHOLD_NS = 120_000_000_000


@dataclass(frozen=True, slots=True)
class BboClocks:
    request_time_ns: int
    provider_time_ns: int | None
    receive_time_ns: int
    available_time_ns: int


@dataclass(frozen=True, slots=True)
class BboDiagnostic:
    lane: str = "ITEM7_BBO_SNAPSHOT"
    symbol: str = DEFAULT_SYMBOL
    provider_id: str = MOOMOO_OPEND_PROVIDER_ID
    capability: str = SNAPSHOT_BBO_CAPABILITY
    identity: str = f"{MOOMOO_OPEND_PROVIDER_ID}:{SNAPSHOT_BBO_CAPABILITY}"
    clocks: BboClocks | None = None
    last_price: float | None = None
    bid_price: float | None = None
    ask_price: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None
    market_status: str | None = None
    entitlement: str = "UNKNOWN"
    bbo_source: str = "VENDOR_MARKET_SNAPSHOT"
    quality_flags: tuple[str, ...] = ()
    temporal_order_valid: bool = True
    raw_hash: str | None = None
    adapter_version: str = ITEM7_ADAPTER_VERSION
    vendor_api_method: str = VENDOR_API_METHOD
    lane_outcome: str = ""
    derived_design_note: str | None = None
    probe_status: str = "OK"
    block_reason: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.clocks is not None:
            payload["clocks"] = asdict(self.clocks)
        return payload


@dataclass(frozen=True, slots=True)
class SnapshotBboCaptureMapping:
    """Result of mapping a vendor snapshot row to a prospective capture envelope."""

    envelope: dict[str, Any] | None
    diagnostic: BboDiagnostic
    refusal_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_kind": "item7_snapshot_bbo_capture_mapping_v1",
            "refusal_reason": self.refusal_reason,
            "diagnostic": self.diagnostic.to_dict(),
            "envelope_capability": (
                str(self.envelope.get("capability")) if self.envelope is not None else None
            ),
        }


def raw_row_sha256(row: Mapping[str, Any]) -> str:
    canonical = json.dumps(dict(row), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _parse_positive_price(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if price != price or price in {float("inf"), float("-inf")}:
        return None
    return price


def _parse_size(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    try:
        size = float(value)
    except (TypeError, ValueError):
        return None
    if size < 0 or size != size:
        return None
    return size


def provider_time_ns_from_row(row: Mapping[str, Any], *, receive_time_ns: int) -> int | None:
    from .provider_time import event_time_ns_from_payload

    return event_time_ns_from_payload(dict(row), received_ns=receive_time_ns)


def assess_snapshot_bbo(
    row: Mapping[str, Any],
    *,
    clocks: BboClocks,
    stale_threshold_ns: int = DEFAULT_STALE_THRESHOLD_NS,
    delayed_sec_statuses: frozenset[str] | None = None,
) -> BboDiagnostic:
    """Classify vendor snapshot BBO without deriving prices from last."""

    delayed_tokens = delayed_sec_statuses or frozenset({"DELAYED", "DELAY", "NON_REALTIME"})
    receive_ns = clocks.receive_time_ns
    provider_ns = clocks.provider_time_ns
    if provider_ns is None:
        provider_ns = provider_time_ns_from_row(row, receive_time_ns=receive_ns)

    bid = _parse_positive_price(row.get("bid_price"))
    ask = _parse_positive_price(row.get("ask_price"))
    last = _parse_positive_price(row.get("last_price"))
    bid_size = _parse_size(row.get("bid_vol"))
    ask_size = _parse_size(row.get("ask_vol"))
    market_status = str(row.get("sec_status") or row.get("market_status") or "").strip() or None

    flags: list[str] = []
    temporal_valid = (
        clocks.request_time_ns <= receive_ns <= clocks.available_time_ns
        and (provider_ns is None or clocks.request_time_ns <= provider_ns <= receive_ns)
    )
    if not temporal_valid:
        flags.append("TEMPORAL_ORDER_VIOLATION")

    if bid is None or ask is None:
        flags.append("BBO_MISSING_BID_ASK")
    elif bid > ask:
        flags.append("BBO_INVALID_SPREAD")

    if provider_ns is not None and receive_ns - provider_ns > stale_threshold_ns:
        flags.append("BBO_STALE")

    status_upper = (market_status or "").upper()
    if status_upper and any(token in status_upper for token in delayed_tokens):
        flags.append("BBO_DELAYED")

    bbo_valid = (
        bid is not None
        and ask is not None
        and bid <= ask
        and "BBO_STALE" not in flags
        and "BBO_DELAYED" not in flags
        and temporal_valid
    )
    if bbo_valid:
        flags.append("BBO_VALID")

    if bbo_valid:
        lane_outcome = OUTCOME_REAL_SNAPSHOT_BBO_VALIDATED
        derived_note = None
    elif last is not None and ("BBO_MISSING_BID_ASK" in flags or "BBO_INVALID_SPREAD" in flags):
        lane_outcome = OUTCOME_DERIVED_BBO_DESIGN_REQUIRED
        derived_note = (
            "Vendor snapshot lacks lawful top-of-book; G5/depth-derived BBO would be "
            "a separate labeled capability — not SNAPSHOT_BBO."
        )
    else:
        lane_outcome = OUTCOME_DERIVED_BBO_DESIGN_REQUIRED
        derived_note = (
            "Snapshot row does not admit REAL_SNAPSHOT_BBO_VALIDATED; depth/G5 design "
            "review required before any derived BBO."
        )

    symbol = str(row.get("code") or DEFAULT_SYMBOL).strip() or DEFAULT_SYMBOL
    return BboDiagnostic(
        symbol=symbol,
        clocks=BboClocks(
            request_time_ns=clocks.request_time_ns,
            provider_time_ns=provider_ns,
            receive_time_ns=receive_ns,
            available_time_ns=clocks.available_time_ns,
        ),
        last_price=last,
        bid_price=bid,
        ask_price=ask,
        bid_size=bid_size,
        ask_size=ask_size,
        market_status=market_status,
        entitlement="ENTITLED",
        quality_flags=tuple(dict.fromkeys(flags)),
        temporal_order_valid=temporal_valid,
        raw_hash=raw_row_sha256(row),
        lane_outcome=lane_outcome,
        derived_design_note=derived_note,
    )


def is_lawful_snapshot_bbo_validated(diagnostic: BboDiagnostic) -> bool:
    return diagnostic.lane_outcome == OUTCOME_REAL_SNAPSHOT_BBO_VALIDATED and "BBO_VALID" in diagnostic.quality_flags


def snapshot_bbo_quality_flags(record: Mapping[str, Any]) -> frozenset[str]:
    raw = record.get("quality_flags") or ()
    if isinstance(raw, str):
        return frozenset({raw})
    if isinstance(raw, (list, tuple, set)):
        return frozenset(str(item) for item in raw)
    return frozenset()


def map_validated_snapshot_bbo_to_capture_envelope(
    row: Mapping[str, Any],
    diagnostic: BboDiagnostic,
    *,
    sequence: int,
    lifecycle: str = "CAPTURED",
) -> SnapshotBboCaptureMapping:
    """Map vendor snapshot row → ``market_data.provider_envelope`` capture JSONL shape.

    Returns ``envelope=None`` when BBO is not ``REAL_SNAPSHOT_BBO_VALIDATED``. Does not
    copy ``last_price`` into bid/ask and does not coerce trade prices into BBO.
    """

    if not is_lawful_snapshot_bbo_validated(diagnostic):
        reason = diagnostic.lane_outcome or "SNAPSHOT_BBO_NOT_VALIDATED"
        return SnapshotBboCaptureMapping(envelope=None, diagnostic=diagnostic, refusal_reason=reason)

    clocks = diagnostic.clocks
    if clocks is None or clocks.provider_time_ns is None:
        return SnapshotBboCaptureMapping(
            envelope=None,
            diagnostic=diagnostic,
            refusal_reason="SNAPSHOT_BBO_MISSING_PROVIDER_CLOCK",
        )

    provider_symbol = str(row.get("code") or diagnostic.symbol).strip()
    instrument_id = provider_symbol.split(".", 1)[-1] if "." in provider_symbol else provider_symbol
    event_time_ns = clocks.provider_time_ns
    received_time_ns = clocks.receive_time_ns
    # OpenD capture PIT requires event_time <= available <= received (distinct from probe clocks).
    available_time_ns = min(clocks.available_time_ns, received_time_ns)
    if available_time_ns < event_time_ns:
        available_time_ns = event_time_ns
    if event_time_ns > available_time_ns or available_time_ns > received_time_ns:
        return SnapshotBboCaptureMapping(
            envelope=None,
            diagnostic=diagnostic,
            refusal_reason="SNAPSHOT_BBO_CAPTURE_CLOCK_ORDER_INVALID",
        )

    raw_payload = {
        "bid_price": diagnostic.bid_price,
        "ask_price": diagnostic.ask_price,
        "bid_vol": diagnostic.bid_size,
        "ask_vol": diagnostic.ask_size,
        "code": provider_symbol,
    }
    if diagnostic.last_price is not None:
        raw_payload["last_price"] = diagnostic.last_price

    envelope: dict[str, Any] = {
        "schema_version": CAPTURE_SCHEMA_VERSION,
        "provider": MOOMOO_OPEND_PROVIDER_ID,
        "capability": SNAPSHOT_BBO_CAPABILITY,
        "provider_symbol": provider_symbol,
        "instrument_id": instrument_id,
        "lifecycle": lifecycle,
        "sequence": sequence,
        "clocks": {
            "event_time_ns": event_time_ns,
            "provider_time_ns": event_time_ns,
            "available_time_ns": available_time_ns,
            "received_time_ns": received_time_ns,
            "ingested_time_ns": received_time_ns,
        },
        "quality_flags": list(diagnostic.quality_flags),
        "item7_lane_outcome": diagnostic.lane_outcome,
        "raw_payload": raw_payload,
        "vendor_api_method": VENDOR_API_METHOD,
        "adapter_version": ITEM7_ADAPTER_VERSION,
        "raw_hash": diagnostic.raw_hash,
    }
    return SnapshotBboCaptureMapping(envelope=envelope, diagnostic=diagnostic, refusal_reason=None)


def build_capture_envelope_from_vendor_snapshot(
    row: Mapping[str, Any],
    *,
    clocks: BboClocks,
    sequence: int,
    stale_threshold_ns: int = DEFAULT_STALE_THRESHOLD_NS,
) -> SnapshotBboCaptureMapping:
    """Assess vendor snapshot BBO and emit capture envelope only when lawful."""

    diagnostic = assess_snapshot_bbo(row, clocks=clocks, stale_threshold_ns=stale_threshold_ns)
    return map_validated_snapshot_bbo_to_capture_envelope(
        row,
        diagnostic,
        sequence=sequence,
    )


__all__ = [
    "BboClocks",
    "BboDiagnostic",
    "DEFAULT_SYMBOL",
    "DEFAULT_STALE_THRESHOLD_NS",
    "ITEM7_ADAPTER_VERSION",
    "MOOMOO_OPEND_PROVIDER_ID",
    "OUTCOME_DERIVED_BBO_DESIGN_REQUIRED",
    "OUTCOME_REAL_SNAPSHOT_BBO_VALIDATED",
    "SNAPSHOT_BBO_CAPABILITY",
    "SnapshotBboCaptureMapping",
    "VENDOR_API_METHOD",
    "assess_snapshot_bbo",
    "build_capture_envelope_from_vendor_snapshot",
    "is_lawful_snapshot_bbo_validated",
    "map_validated_snapshot_bbo_to_capture_envelope",
    "provider_time_ns_from_row",
    "raw_row_sha256",
    "snapshot_bbo_quality_flags",
]
