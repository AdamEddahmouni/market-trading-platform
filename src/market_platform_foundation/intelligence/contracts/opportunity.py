"""OpportunityV1 — economically interesting candidate, not an order."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    IntelligenceScope,
    OpportunitySide,
    QualitySummary,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    normalize_unique_refs,
    quality_summary_from_dict,
    quality_summary_to_dict,
    reject_unknown_keys,
    scope_from_dict,
    scope_to_dict,
    validate_finite,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)


@dataclass(frozen=True, slots=True)
class OpportunityV1:
    """Candidate setup derived from forecasts/hypotheses.

    What: screened economic interest with edge estimates — no execution fields.
    Not: broker order, trade proposal, or risk authorization.
    Producers: opportunity ranking layer (future BUILD).
    Consumers: trade-proposal and risk decision layers.
    Immutable after construction.
    """

    opportunity_id: str
    schema_version: str
    scope: IntelligenceScope
    created_at_ns: int
    quality: QualitySummary
    opportunity_type: str | None = None
    side: OpportunitySide | None = None
    valid_until_ns: int | None = None
    source_forecast_refs: tuple[ContractReference, ...] = ()
    source_hypothesis_refs: tuple[ContractReference, ...] = ()
    expected_return: float | None = None
    expected_net_edge: float | None = None
    uncertainty: dict[str, Any] = field(default_factory=dict)
    reason_summary: str | None = None
    lineage_refs: tuple[ContractReference, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_id(self.opportunity_id, field_name="opportunity_id")
        validate_schema_version(self.schema_version)
        validate_timestamp_ns(self.created_at_ns, field_name="created_at_ns")
        if self.valid_until_ns is not None:
            validate_timestamp_ns(self.valid_until_ns, field_name="valid_until_ns")
        if self.side is not None and not isinstance(self.side, OpportunitySide):
            object.__setattr__(self, "side", OpportunitySide(str(self.side)))
        if self.expected_return is not None:
            validate_finite(self.expected_return, field_name="expected_return")
        if self.expected_net_edge is not None:
            validate_finite(self.expected_net_edge, field_name="expected_net_edge")
        object.__setattr__(self, "source_forecast_refs", normalize_unique_refs(self.source_forecast_refs))
        object.__setattr__(self, "source_hypothesis_refs", normalize_unique_refs(self.source_hypothesis_refs))
        object.__setattr__(self, "lineage_refs", normalize_unique_refs(self.lineage_refs))
        if not isinstance(self.uncertainty, dict):
            raise ValueError("OPPORTUNITY_UNCERTAINTY_INVALID")
        if not isinstance(self.metadata, dict):
            raise ValueError("OPPORTUNITY_METADATA_INVALID")
        _reject_execution_fields(self.metadata)


_OPPORTUNITY_ALLOWED = dataclass_field_names(OpportunityV1)

_FORBIDDEN_EXECUTION_KEYS = frozenset(
    {
        "order_id",
        "quantity",
        "size",
        "broker_order",
        "execution_authority",
        "authorized",
        "submit_order",
        "side_buy_sell",
    }
)


def _reject_execution_fields(metadata: dict[str, Any]) -> None:
    for key in metadata:
        if key in _FORBIDDEN_EXECUTION_KEYS:
            raise ValueError("OPPORTUNITY_EXECUTION_FIELD_FORBIDDEN")


def opportunity_v1_to_dict(record: OpportunityV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "opportunity_id": record.opportunity_id,
        "schema_version": record.schema_version,
        "scope": scope_to_dict(record.scope),
        "created_at_ns": record.created_at_ns,
        "quality": quality_summary_to_dict(record.quality),
    }
    if record.opportunity_type is not None:
        body["opportunity_type"] = record.opportunity_type
    if record.side is not None:
        body["side"] = record.side.value
    if record.valid_until_ns is not None:
        body["valid_until_ns"] = record.valid_until_ns
    if record.source_forecast_refs:
        body["source_forecast_refs"] = [
            contract_reference_to_dict(ref) for ref in record.source_forecast_refs
        ]
    if record.source_hypothesis_refs:
        body["source_hypothesis_refs"] = [
            contract_reference_to_dict(ref) for ref in record.source_hypothesis_refs
        ]
    if record.expected_return is not None:
        body["expected_return"] = record.expected_return
    if record.expected_net_edge is not None:
        body["expected_net_edge"] = record.expected_net_edge
    if record.uncertainty:
        body["uncertainty"] = dict(record.uncertainty)
    if record.reason_summary is not None:
        body["reason_summary"] = record.reason_summary
    if record.lineage_refs:
        body["lineage_refs"] = [contract_reference_to_dict(ref) for ref in record.lineage_refs]
    if record.metadata:
        body["metadata"] = dict(record.metadata)
    return body


def opportunity_v1_from_dict(payload: dict[str, Any]) -> OpportunityV1:
    reject_unknown_keys(payload, _OPPORTUNITY_ALLOWED)
    return OpportunityV1(
        opportunity_id=str(payload["opportunity_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        scope=scope_from_dict(payload["scope"]),
        created_at_ns=int(payload["created_at_ns"]),
        quality=quality_summary_from_dict(payload["quality"]),
        opportunity_type=payload.get("opportunity_type"),
        side=OpportunitySide(payload["side"]) if payload.get("side") is not None else None,
        valid_until_ns=payload.get("valid_until_ns"),
        source_forecast_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("source_forecast_refs") or [])
        ),
        source_hypothesis_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("source_hypothesis_refs") or [])
        ),
        expected_return=payload.get("expected_return"),
        expected_net_edge=payload.get("expected_net_edge"),
        uncertainty=dict(payload.get("uncertainty") or {}),
        reason_summary=payload.get("reason_summary"),
        lineage_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("lineage_refs") or [])
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = ["OpportunityV1", "opportunity_v1_from_dict", "opportunity_v1_to_dict"]
