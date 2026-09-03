"""TradeProposalV1 — requested trade intent from a governed opportunity (BUILD 22)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    normalize_unique_refs,
    reject_unknown_keys,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)


@dataclass(frozen=True, slots=True)
class TradeProposalV1:
    """Immutable requested trade intent — not risk approval and not an order."""

    proposal_id: str
    schema_version: str
    opportunity_id: str
    execution_policy_id: str
    instrument_id: str
    side: str
    requested_quantity: int
    requested_notional_minor: int
    reference_price_minor: int
    proposal_time_ns: int
    expires_at_ns: int
    execution_mode: str
    opportunity_ref: ContractReference
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.proposal_id, field_name="proposal_id")
        validate_schema_version(self.schema_version)
        validate_id(self.opportunity_id, field_name="opportunity_id")
        validate_id(self.execution_policy_id, field_name="execution_policy_id")
        validate_id(self.instrument_id, field_name="instrument_id")
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("TRADE_PROPOSAL_SIDE_INVALID")
        if self.requested_quantity <= 0:
            raise ValueError("TRADE_PROPOSAL_QUANTITY_INVALID")
        if self.requested_notional_minor <= 0:
            raise ValueError("TRADE_PROPOSAL_NOTIONAL_INVALID")
        if self.reference_price_minor <= 0:
            raise ValueError("TRADE_PROPOSAL_REFERENCE_PRICE_INVALID")
        validate_timestamp_ns(self.proposal_time_ns, field_name="proposal_time_ns")
        validate_timestamp_ns(self.expires_at_ns, field_name="expires_at_ns")
        if self.expires_at_ns < self.proposal_time_ns:
            raise ValueError("TRADE_PROPOSAL_EXPIRY_INVALID")
        if self.execution_mode != "PAPER":
            raise ValueError("TRADE_PROPOSAL_MODE_INVALID")
        object.__setattr__(self, "lineage_refs", normalize_unique_refs(self.lineage_refs))
        if not isinstance(self.metadata, dict):
            raise ValueError("TRADE_PROPOSAL_METADATA_INVALID")


_PROPOSAL_ALLOWED = dataclass_field_names(TradeProposalV1)


def trade_proposal_v1_to_dict(record: TradeProposalV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "proposal_id": record.proposal_id,
        "schema_version": record.schema_version,
        "opportunity_id": record.opportunity_id,
        "execution_policy_id": record.execution_policy_id,
        "instrument_id": record.instrument_id,
        "side": record.side,
        "requested_quantity": record.requested_quantity,
        "requested_notional_minor": record.requested_notional_minor,
        "reference_price_minor": record.reference_price_minor,
        "proposal_time_ns": record.proposal_time_ns,
        "expires_at_ns": record.expires_at_ns,
        "execution_mode": record.execution_mode,
        "opportunity_ref": contract_reference_to_dict(record.opportunity_ref),
    }
    if record.lineage_refs:
        body["lineage_refs"] = [contract_reference_to_dict(ref) for ref in record.lineage_refs]
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def trade_proposal_v1_from_dict(payload: dict[str, Any]) -> TradeProposalV1:
    reject_unknown_keys(payload, _PROPOSAL_ALLOWED)
    return TradeProposalV1(
        proposal_id=str(payload["proposal_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        opportunity_id=str(payload["opportunity_id"]),
        execution_policy_id=str(payload["execution_policy_id"]),
        instrument_id=str(payload["instrument_id"]),
        side=str(payload["side"]),
        requested_quantity=int(payload["requested_quantity"]),
        requested_notional_minor=int(payload["requested_notional_minor"]),
        reference_price_minor=int(payload["reference_price_minor"]),
        proposal_time_ns=int(payload["proposal_time_ns"]),
        expires_at_ns=int(payload["expires_at_ns"]),
        execution_mode=str(payload.get("execution_mode", "PAPER")),
        opportunity_ref=contract_reference_from_dict(payload["opportunity_ref"]),
        lineage_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("lineage_refs") or [])
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = ["TradeProposalV1", "trade_proposal_v1_from_dict", "trade_proposal_v1_to_dict"]
