"""Broker-neutral paper execution contract (Platformization P4, frozen in 4A).

Canonical broker-facing payloads, status mapping onto the IMP order lifecycle,
broker-fill normalization into the shared portfolio projection shape, and the
ADR-PROV-001 envelope builder. Provider-native wire details never leak past
this boundary; adapters (e.g. ``TradierPaperExecutionProvider``) map onto these
models only.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..contracts.envelope import validate_envelope
from .contracts import SymbolMapping
from .envelope import build_provider_metadata

BROKER_EXECUTION_SCHEMA = "1.0.0"
BROKER_NORMALIZATION_VERSION = "providers/broker_execution/1.0.0"

# Canonical, adapter-independent broker statuses. The broker wire vocabulary is
# mapped into these by each adapter; the wire mapping is recorded in
# docs/providers/TRADIER_PAPER.md as it is verified in 4A.
BROKER_STATUSES: tuple[str, ...] = (
    "accepted",
    "working",
    "partially_filled",
    "filled",
    "rejected",
    "cancelled",
    "expired",
    "ambiguous",
)

AMBIGUOUS_BROKER_STATUS = "ambiguous"

# Canonical broker status -> IMP ORDER_LIFECYCLE_STATES.
BROKER_STATUS_TO_IMP: dict[str, str] = {
    "accepted": "ACTIVATED",
    "working": "WORKING",
    "partially_filled": "PARTIALLY_FILLED",
    "filled": "FILLED",
    "rejected": "REJECTED",
    "cancelled": "CANCELLED",
    "expired": "EXPIRED",
}

BROKER_ALLOCATION_MODEL = "tradier-paper/1.0.0"


def map_broker_status(status: str) -> str:
    """Map a canonical broker status to an IMP lifecycle state, failing closed.

    ``ambiguous`` and any unknown status have no IMP mapping and therefore must
    never advance the IMP lifecycle (P4-MAP-001).
    """
    if status == AMBIGUOUS_BROKER_STATUS or status not in BROKER_STATUS_TO_IMP:
        raise ValueError(f"BROKER_STATUS_UNMAPPED: {status}")
    return BROKER_STATUS_TO_IMP[status]


def is_ambiguous_broker_status(status: str) -> bool:
    return status == AMBIGUOUS_BROKER_STATUS


@dataclass(frozen=True)
class BrokerPaperOrderRequest:
    """Normalized outbound broker submission derived from a canonical intent."""

    broker_symbol: str
    client_order_id: str
    idempotency_key: str
    instrument_id: str
    intent_id: str
    order_type: str
    quantity: int
    requested_time_ns: int
    side: str
    limit_price_minor: int | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "broker_symbol": self.broker_symbol,
            "client_order_id": self.client_order_id,
            "idempotency_key": self.idempotency_key,
            "instrument_id": self.instrument_id,
            "intent_id": self.intent_id,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "requested_time_ns": self.requested_time_ns,
            "side": self.side,
        }
        if self.limit_price_minor is not None:
            body["limit_price_minor"] = self.limit_price_minor
        return body


@dataclass(frozen=True)
class BrokerFillEvent:
    """One broker execution within an order."""

    broker_fill_id: str
    broker_order_id: str
    event_time_ns: int
    price_minor: int
    quantity: int
    receive_time_ns: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "broker_fill_id": self.broker_fill_id,
            "broker_order_id": self.broker_order_id,
            "event_time_ns": self.event_time_ns,
            "price_minor": self.price_minor,
            "quantity": self.quantity,
            "receive_time_ns": self.receive_time_ns,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any], *, broker_order_id: str) -> BrokerFillEvent:
        return cls(
            broker_fill_id=str(record["broker_fill_id"]),
            broker_order_id=broker_order_id,
            event_time_ns=int(record.get("event_time_ns", 0)),
            price_minor=int(record["price_minor"]),
            quantity=int(record["quantity"]),
            receive_time_ns=int(record.get("receive_time_ns", record.get("event_time_ns", 0))),
        )


@dataclass(frozen=True)
class BrokerOrderStatusEvent:
    """Broker-side order lifecycle push/poll record."""

    broker_order_id: str
    broker_status_raw: str
    event_time_ns: int
    receive_time_ns: int
    status: str
    avg_fill_price_minor: int | None = None
    filled_quantity: int = 0
    fills: tuple[BrokerFillEvent, ...] = ()

    @property
    def ambiguous(self) -> bool:
        return is_ambiguous_broker_status(self.status)

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "broker_order_id": self.broker_order_id,
            "broker_status_raw": self.broker_status_raw,
            "event_time_ns": self.event_time_ns,
            "receive_time_ns": self.receive_time_ns,
            "status": self.status,
        }
        if self.avg_fill_price_minor is not None:
            body["avg_fill_price_minor"] = self.avg_fill_price_minor
        if self.filled_quantity:
            body["filled_quantity"] = self.filled_quantity
        if self.fills:
            body["fills"] = [fill.to_dict() for fill in self.fills]
        return body

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> BrokerOrderStatusEvent:
        """Build from a normalized fixture/provider record (canonical status)."""
        broker_order_id = str(record["broker_order_id"])
        raw_status = str(record.get("status_raw", record.get("status", "")))
        status = str(record.get("status", ""))
        fills = tuple(
            BrokerFillEvent.from_record(fill, broker_order_id=broker_order_id)
            for fill in record.get("fills", [])
        )
        return cls(
            broker_order_id=broker_order_id,
            broker_status_raw=raw_status,
            event_time_ns=int(record.get("event_time_ns", 0)),
            receive_time_ns=int(record.get("receive_time_ns", record.get("event_time_ns", 0))),
            status=status,
            avg_fill_price_minor=(
                int(record["avg_fill_price_minor"])
                if record.get("avg_fill_price_minor") is not None
                else None
            ),
            filled_quantity=int(record.get("filled_quantity", 0)),
            fills=fills,
        )


def build_broker_order_request(
    intent: dict[str, Any],
    *,
    broker_symbol: str,
) -> BrokerPaperOrderRequest:
    """Normalize a canonical order intent into an outbound broker request.

    ``broker_symbol`` must already be resolved by the adapter's symbol mapping
    (unmapped instruments fail closed before this call).
    """
    return BrokerPaperOrderRequest(
        broker_symbol=broker_symbol,
        client_order_id=str(intent["client_order_id"]),
        idempotency_key=str(intent["idempotency_key"]),
        instrument_id=str(intent["instrument_id"]),
        intent_id=str(intent["intent_id"]),
        order_type=str(intent.get("order_type", "MARKET")),
        quantity=int(intent["desired_quantity"]),
        requested_time_ns=int(intent["created_time"]),
        side=str(intent["side"]),
        limit_price_minor=(
            int(intent["limit_price_minor"]) if intent.get("limit_price_minor") is not None else None
        ),
    )


def build_canonical_order_id(*, intent: dict[str, Any], decision: dict[str, Any]) -> str:
    """Deterministic pre-network IMP order id (mirrors the simulator's pattern).

    The broker order id is only known after submission, so the IMP order is
    identified by this content-derived id for the full lifecycle; the broker
    order id is carried separately (``broker_order_id``) for provenance.
    """
    body = {
        "allocation_model": BROKER_ALLOCATION_MODEL,
        "created_time": int(intent["created_time"]),
        "direction": intent["direction"],
        "intent_id": intent["intent_id"],
        "instrument_id": intent["instrument_id"],
        "quantity": int(decision["approved_quantity"]),
        "risk_decision": decision["decision"],
        "source_capability": "BROKER_PAPER",
    }
    return sha256_bytes(canonical_bytes(body))


def build_broker_order(
    *,
    intent: dict[str, Any],
    decision: dict[str, Any],
    state: str,
    order_id: str,
    broker_order_id: str | None = None,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    """Canonical IMP order dict for the ledger (state + broker provenance)."""
    order: dict[str, Any] = {
        "allocation_model": BROKER_ALLOCATION_MODEL,
        "broker_order_id": broker_order_id,
        "created_time": int(intent["created_time"]),
        "direction": intent["direction"],
        "instrument_id": intent["instrument_id"],
        "intent_id": intent["intent_id"],
        "order_id": order_id,
        "quantity": int(decision["approved_quantity"]),
        "risk_decision": decision["decision"],
        "source_capability": "BROKER_PAPER",
        "state": state,
    }
    if reason_codes:
        order["reason_codes"] = sorted(set(reason_codes))
    return order


def normalize_broker_fill(
    fill_event: BrokerFillEvent,
    *,
    order_id: str,
    instrument_id: str,
    direction: str,
) -> dict[str, Any]:
    """Normalize a broker fill into the shared ledger fill shape (apply_fill)."""
    if direction not in {"long", "short"}:
        raise ValueError("BROKER_FILL_DIRECTION_INVALID")
    body = {
        "broker_fill_id": fill_event.broker_fill_id,
        "direction": direction,
        "fill_price_minor": int(fill_event.price_minor),
        "fill_quantity": int(fill_event.quantity),
        "fill_time": int(fill_event.event_time_ns),
        "instrument_id": instrument_id,
        "order_id": order_id,
        "source_capability": "BROKER_PAPER",
    }
    return {
        **body,
        "fill_id": sha256_bytes(canonical_bytes(body)),
    }


def broker_execution_envelope_id(payload: dict[str, Any]) -> str:
    return sha256_bytes(canonical_bytes(payload))


def build_broker_execution_envelope(
    *,
    broker_event_type: str,
    instrument_id: str,
    symbol_mapping: SymbolMapping,
    provider_id: str,
    entitlement: str,
    event_time_ns: int,
    receive_time_ns: int,
    available_time_ns: int,
    raw_source_reference: str,
    source_record_id: str,
    payload: dict[str, Any],
    ingest_run_id: str,
    quality_state: str = "GOOD",
) -> dict[str, Any]:
    """Serialize one broker event as a canonical IMP envelope (ADR-PROV-001).

    Reuses ``build_provider_metadata`` + ``validate_envelope`` verbatim
    (audit F2). ``available_time`` defaults to local receipt for live pushes
    per PLATFORM-DATA-001.
    """
    provider_metadata = build_provider_metadata(
        provider_id=provider_id,
        entitlement=entitlement,
        event_time_ns=event_time_ns,
        receive_time_ns=receive_time_ns,
        symbol_mapping=symbol_mapping,
        quality_state=quality_state,
        raw_source_reference=raw_source_reference,
    )
    normalized_event_id = broker_execution_envelope_id(payload)
    envelope: dict[str, Any] = {
        "available_time": available_time_ns,
        "broker_event_type": broker_event_type,
        "channel_id": symbol_mapping.provider_symbol,
        "event_time": event_time_ns,
        "event_type": "BROKER_EXECUTION_EVENT",
        "historical_ingested_time": None,
        "ingest_run_id": ingest_run_id,
        "instrument_id": instrument_id,
        "live_received_time": receive_time_ns,
        "normalization_version": BROKER_NORMALIZATION_VERSION,
        "normalized_event_id": normalized_event_id,
        "operation": "UPSERT",
        "payload": payload,
        "provider_metadata": provider_metadata,
        "publisher_id": provider_id,
        "quality_observation_refs": [],
        "raw_reference": raw_source_reference,
        "schema_version": BROKER_EXECUTION_SCHEMA,
        "source_instance_id": provider_id,
        "source_publish_time": event_time_ns,
        "source_record_id": source_record_id,
        "source_revision_id": str(payload.get("source_revision_id", "1")),
        "source_sequence": None,
        "supersedes_event_id": None,
        "venue_id": symbol_mapping.venue_id,
    }
    timestamp_states = {
        "event_time": "REQUIRED",
        "source_publish_time": "REQUIRED",
        "live_received_time": "REQUIRED",
        "historical_ingested_time": "FORBIDDEN",
        "available_time": "REQUIRED",
    }
    reasons = validate_envelope(envelope, timestamp_states=timestamp_states, acquisition_mode="live")
    if reasons:
        raise ValueError(f"BROKER_ENVELOPE_INVALID:{','.join(reasons)}")
    return envelope


def ensure_broker_fill_ids(status_event: BrokerOrderStatusEvent) -> BrokerOrderStatusEvent:
    """Backfill deterministic fill ids for records that do not carry one."""
    if not status_event.fills:
        return status_event
    if all(fill.broker_fill_id for fill in status_event.fills):
        return status_event
    rebuilt: list[BrokerFillEvent] = []
    for index, fill in enumerate(status_event.fills):
        if fill.broker_fill_id:
            rebuilt.append(fill)
            continue
        body = {
            "broker_order_id": fill.broker_order_id,
            "index": index,
            "price_minor": fill.price_minor,
            "quantity": fill.quantity,
        }
        rebuilt.append(
            BrokerFillEvent(
                broker_fill_id=sha256_bytes(canonical_bytes(body)),
                broker_order_id=fill.broker_order_id,
                event_time_ns=fill.event_time_ns,
                price_minor=fill.price_minor,
                quantity=fill.quantity,
                receive_time_ns=fill.receive_time_ns,
            )
        )
    return BrokerOrderStatusEvent(
        broker_order_id=status_event.broker_order_id,
        broker_status_raw=status_event.broker_status_raw,
        event_time_ns=status_event.event_time_ns,
        receive_time_ns=status_event.receive_time_ns,
        status=status_event.status,
        avg_fill_price_minor=status_event.avg_fill_price_minor,
        filled_quantity=status_event.filled_quantity,
        fills=tuple(rebuilt),
    )


def new_ingest_run_id() -> str:
    return f"ingest-{uuid.uuid4().hex}"


__all__ = [
    "AMBIGUOUS_BROKER_STATUS",
    "BROKER_ALLOCATION_MODEL",
    "BROKER_EXECUTION_SCHEMA",
    "BROKER_NORMALIZATION_VERSION",
    "BROKER_STATUSES",
    "BROKER_STATUS_TO_IMP",
    "BrokerFillEvent",
    "BrokerOrderStatusEvent",
    "BrokerPaperOrderRequest",
    "build_broker_execution_envelope",
    "build_broker_order",
    "build_broker_order_request",
    "build_canonical_order_id",
    "broker_execution_envelope_id",
    "ensure_broker_fill_ids",
    "is_ambiguous_broker_status",
    "map_broker_status",
    "new_ingest_run_id",
    "normalize_broker_fill",
]
