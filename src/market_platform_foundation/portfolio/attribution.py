"""Durable strategy-to-realized-P&L attribution sidecar.

This module intentionally operates on explicit virtual-slice fills.  It never
reads a broker position and never mutates the authoritative portfolio ledger.
The same broker fill may therefore be represented in multiple strategy slices
with different allocated quantities while the broker remains netted.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Mapping

from ..canonical import canonical_bytes, sha256_bytes
from ..intelligence.contracts.common import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractReference,
    contract_reference_from_dict,
    contract_reference_to_dict,
    dataclass_field_names,
    normalize_unique_refs,
    validate_id,
    validate_schema_version,
    validate_timestamp_ns,
)
from .ledger import apply_fill, build_ledger_state


class AttributionValidationError(ValueError):
    """An attribution record is malformed or outside its declared scope."""


class AttributionOutcomeKind(StrEnum):
    """Separate labels for predictive and trading outcomes."""

    PREDICTION = "PREDICTION"
    TRADING = "TRADING"


@dataclass(frozen=True, slots=True)
class AttributionFillV1:
    """One explicitly allocated execution fill for a virtual strategy slice."""

    fill_id: str
    fill_time_ns: int
    direction: str
    quantity: int
    price_minor: int
    execution_ref: ContractReference | None = None
    commission_minor: int = 0
    fees_minor: int = 0

    def __post_init__(self) -> None:
        validate_id(self.fill_id, field_name="fill_id")
        validate_timestamp_ns(self.fill_time_ns, field_name="fill_time_ns")
        direction = str(self.direction).strip().upper()
        if direction not in {"LONG", "SHORT"}:
            raise AttributionValidationError("ATTRIBUTION_FILL_DIRECTION_INVALID")
        object.__setattr__(self, "direction", direction)
        for field_name in ("quantity", "price_minor", "commission_minor", "fees_minor"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise AttributionValidationError(f"ATTRIBUTION_{field_name.upper()}_INTEGER_REQUIRED")
            if value < 0 or (field_name == "quantity" and value == 0):
                raise AttributionValidationError(f"ATTRIBUTION_{field_name.upper()}_INVALID")
        if self.execution_ref is not None and not isinstance(self.execution_ref, ContractReference):
            object.__setattr__(
                self,
                "execution_ref",
                contract_reference_from_dict(self.execution_ref),
            )

    @property
    def signed_quantity(self) -> int:
        return self.quantity if self.direction == "LONG" else -self.quantity

    @property
    def fill_ref(self) -> ContractReference:
        return ContractReference(kind="fill", id=self.fill_id)


@dataclass(frozen=True, slots=True)
class TradingOutcomeV1:
    """Deterministic realized result of one virtual slice's explicit fills."""

    outcome_kind: AttributionOutcomeKind
    realized_pnl_minor: int
    ending_position_quantity: int
    ending_cost_basis_minor: int
    total_commission_minor: int
    total_fees_minor: int

    def __post_init__(self) -> None:
        if not isinstance(self.outcome_kind, AttributionOutcomeKind):
            object.__setattr__(
                self,
                "outcome_kind",
                AttributionOutcomeKind(str(self.outcome_kind)),
            )


@dataclass(frozen=True, slots=True)
class StrategyAttributionV1:
    """Immutable lineage and P&L sidecar for one virtual strategy allocation."""

    attribution_id: str
    schema_version: str
    account_id: str
    mode: str
    instrument_id: str
    allocation_ref: ContractReference
    strategy_match_ref: ContractReference
    strategy_id: str
    strategy_identity_hash: str
    allocation_quantity: int
    allocation_direction: str
    allocation_time_ns: int
    point_in_time_ns: int
    fills: tuple[AttributionFillV1, ...] = ()
    intent_ref: ContractReference | None = None
    opportunity_ref: ContractReference | None = None
    cluster_thesis_ref: ContractReference | None = None
    execution_refs: tuple[ContractReference, ...] = ()
    fill_refs: tuple[ContractReference, ...] = ()
    forecast_refs: tuple[ContractReference, ...] = ()
    prediction_outcome_refs: tuple[ContractReference, ...] = ()
    materialization_semantics: str = "CUMULATIVE"
    coverage_algorithm_version: str = "fill-set-coverage-v1"
    initial_position_quantity: int = 0
    initial_cost_basis_minor: int = 0
    created_at_ns: int = 0

    def __post_init__(self) -> None:
        validate_id(self.attribution_id, field_name="attribution_id")
        validate_schema_version(self.schema_version)
        validate_id(self.account_id, field_name="account_id")
        validate_id(self.instrument_id, field_name="instrument_id")
        validate_id(self.strategy_id, field_name="strategy_id")
        validate_id(self.strategy_identity_hash, field_name="strategy_identity_hash")
        for field_name in ("allocation_ref", "strategy_match_ref"):
            ref = getattr(self, field_name)
            if not isinstance(ref, ContractReference):
                ref = contract_reference_from_dict(ref)
                object.__setattr__(self, field_name, ref)
        if self.allocation_ref.kind not in {
            "allocation",
            "allocation_decision",
            "intent",
            "trade_proposal",
        }:
            raise AttributionValidationError("ATTRIBUTION_ALLOCATION_REF_KIND_INVALID")
        if self.strategy_match_ref.kind != "strategy_match":
            raise AttributionValidationError("ATTRIBUTION_STRATEGY_MATCH_REF_KIND_INVALID")
        for field_name, allowed_kinds in (
            ("intent_ref", {"intent", "trade_proposal", "capital_allocation_intent"}),
            ("opportunity_ref", {"opportunity"}),
            ("cluster_thesis_ref", {"cluster", "thesis", "thesis_cluster"}),
        ):
            ref = getattr(self, field_name)
            if ref is not None:
                if not isinstance(ref, ContractReference):
                    ref = contract_reference_from_dict(ref)
                    object.__setattr__(self, field_name, ref)
                if ref.kind not in allowed_kinds:
                    raise AttributionValidationError(
                        f"ATTRIBUTION_{field_name.upper()}_KIND_INVALID"
                    )
        mode = _normalize_mode(self.mode)
        if not mode:
            raise AttributionValidationError("ATTRIBUTION_MODE_REQUIRED")
        object.__setattr__(self, "mode", mode)
        semantics = str(self.materialization_semantics).strip().upper()
        if semantics != "CUMULATIVE":
            raise AttributionValidationError("ATTRIBUTION_MATERIALIZATION_SEMANTICS_INVALID")
        object.__setattr__(self, "materialization_semantics", semantics)
        coverage_version = str(self.coverage_algorithm_version).strip()
        if not coverage_version:
            raise AttributionValidationError("ATTRIBUTION_COVERAGE_ALGORITHM_VERSION_REQUIRED")
        object.__setattr__(self, "coverage_algorithm_version", coverage_version)
        direction = str(self.allocation_direction).strip().upper()
        if direction not in {"LONG", "SHORT"}:
            raise AttributionValidationError("ATTRIBUTION_ALLOCATION_DIRECTION_INVALID")
        object.__setattr__(self, "allocation_direction", direction)
        if not isinstance(self.allocation_quantity, int) or isinstance(self.allocation_quantity, bool):
            raise AttributionValidationError("ATTRIBUTION_ALLOCATION_QUANTITY_INTEGER_REQUIRED")
        if self.allocation_quantity <= 0:
            raise AttributionValidationError("ATTRIBUTION_ALLOCATION_QUANTITY_INVALID")
        for field_name in ("initial_position_quantity", "initial_cost_basis_minor"):
            value = getattr(self, field_name)
            if not isinstance(value, int) or isinstance(value, bool):
                raise AttributionValidationError(f"ATTRIBUTION_{field_name.upper()}_INTEGER_REQUIRED")
        if self.initial_position_quantity == 0 and self.initial_cost_basis_minor != 0:
            raise AttributionValidationError("ATTRIBUTION_FLAT_POSITION_COST_BASIS_INVALID")
        if self.initial_position_quantity > 0 and self.initial_cost_basis_minor < 0:
            raise AttributionValidationError("ATTRIBUTION_LONG_COST_BASIS_INVALID")
        if self.initial_position_quantity < 0 and self.initial_cost_basis_minor > 0:
            raise AttributionValidationError("ATTRIBUTION_SHORT_COST_BASIS_INVALID")
        validate_timestamp_ns(self.allocation_time_ns, field_name="allocation_time_ns")
        validate_timestamp_ns(self.point_in_time_ns, field_name="point_in_time_ns")
        validate_timestamp_ns(self.created_at_ns, field_name="created_at_ns")
        if self.point_in_time_ns < self.allocation_time_ns:
            raise AttributionValidationError("ATTRIBUTION_PIT_BEFORE_ALLOCATION")
        normalized_fills = tuple(
            fill if isinstance(fill, AttributionFillV1) else attribution_fill_v1_from_dict(fill)
            for fill in self.fills
        )
        if len({fill.fill_id for fill in normalized_fills}) != len(normalized_fills):
            raise AttributionValidationError("ATTRIBUTION_DUPLICATE_FILL_ID")
        normalized_fills = tuple(sorted(normalized_fills, key=lambda fill: (fill.fill_time_ns, fill.fill_id)))
        object.__setattr__(self, "fills", normalized_fills)
        for fill in normalized_fills:
            if fill.fill_time_ns < self.point_in_time_ns:
                raise AttributionValidationError("ATTRIBUTION_FILL_BEFORE_POINT_IN_TIME")
        for field_name in ("execution_refs", "fill_refs", "forecast_refs", "prediction_outcome_refs"):
            refs = tuple(
                ref if isinstance(ref, ContractReference) else contract_reference_from_dict(ref)
                for ref in getattr(self, field_name)
            )
            object.__setattr__(
                self,
                field_name,
                tuple(sorted(normalize_unique_refs(refs), key=_ref_sort_key)),
            )
        derived_fill_refs = tuple(sorted((fill.fill_ref for fill in normalized_fills), key=_ref_sort_key))
        if self.fill_refs and self.fill_refs != derived_fill_refs:
            raise AttributionValidationError("ATTRIBUTION_FILL_REFS_MISMATCH")
        object.__setattr__(self, "fill_refs", derived_fill_refs)
        derived_execution_refs = tuple(
            sorted(
                normalize_unique_refs(
                    tuple(self.execution_refs)
                    + tuple(fill.execution_ref for fill in normalized_fills if fill.execution_ref)
                ),
                key=_ref_sort_key,
            )
        )
        object.__setattr__(self, "execution_refs", derived_execution_refs)
        if any(ref.kind != "forecast" for ref in self.forecast_refs):
            raise AttributionValidationError("ATTRIBUTION_FORECAST_REF_KIND_INVALID")
        if any(ref.kind != "outcome" for ref in self.prediction_outcome_refs):
            raise AttributionValidationError("ATTRIBUTION_PREDICTION_OUTCOME_REF_KIND_INVALID")

    @classmethod
    def create(cls, **kwargs: Any) -> "StrategyAttributionV1":
        """Construct a record with a deterministic id when one is not supplied."""
        attribution_id = kwargs.pop("attribution_id", None)
        record = cls(
            attribution_id=attribution_id or "ATR-PENDING",
            **kwargs,
        )
        if attribution_id is None:
            object.__setattr__(record, "attribution_id", f"ATR-{record.identity_hash}")
        return record

    @property
    def identity_hash(self) -> str:
        body = attribution_v1_to_dict(self, include_identity=False)
        body.pop("attribution_id", None)
        return sha256_bytes(canonical_bytes(body))

    @property
    def trading_outcome(self) -> TradingOutcomeV1:
        return compute_slice_realized_pnl(
            self.fills,
            initial_position_quantity=self.initial_position_quantity,
            initial_cost_basis_minor=self.initial_cost_basis_minor,
        )

    @property
    def prediction_outcome_ref(self) -> ContractReference | None:
        """Convenience accessor; predictive outcomes remain separate from P&L."""
        return self.prediction_outcome_refs[0] if self.prediction_outcome_refs else None

    @property
    def trading_outcome_kind(self) -> AttributionOutcomeKind:
        return AttributionOutcomeKind.TRADING

    @property
    def prediction_outcome_kind(self) -> AttributionOutcomeKind:
        return AttributionOutcomeKind.PREDICTION

    @property
    def realized_fill_refs(self) -> tuple[ContractReference, ...]:
        return self.fill_refs

def compute_slice_realized_pnl(
    fills: Iterable[AttributionFillV1 | Mapping[str, Any]],
    *,
    initial_position_quantity: int = 0,
    initial_cost_basis_minor: int = 0,
) -> TradingOutcomeV1:
    """Compute P&L from explicit slice fills, including reversal semantics."""
    normalized = tuple(
        fill if isinstance(fill, AttributionFillV1) else attribution_fill_v1_from_dict(dict(fill))
        for fill in fills
    )
    if len({fill.fill_id for fill in normalized}) != len(normalized):
        raise AttributionValidationError("ATTRIBUTION_DUPLICATE_FILL_ID")
    position = int(initial_position_quantity)
    basis = int(initial_cost_basis_minor)
    if position == 0 and basis != 0:
        raise AttributionValidationError("ATTRIBUTION_FLAT_POSITION_COST_BASIS_INVALID")
    if position > 0 and basis < 0:
        raise AttributionValidationError("ATTRIBUTION_LONG_COST_BASIS_INVALID")
    if position < 0 and basis > 0:
        raise AttributionValidationError("ATTRIBUTION_SHORT_COST_BASIS_INVALID")
    state = build_ledger_state(initial_cash_minor=0)
    state["position_shares"] = position
    state["position_cost_basis_minor"] = basis
    for fill in sorted(normalized, key=lambda item: (item.fill_time_ns, item.fill_id)):
        state = apply_fill(
            state,
            fill={
                "fill_id": fill.fill_id,
                "fill_quantity": fill.quantity,
                "fill_price_minor": fill.price_minor,
                "direction": fill.direction.lower(),
                "commission_minor": fill.commission_minor,
                "fees_minor": fill.fees_minor,
            },
            policy={
                "commission_minor_per_share": 0,
                "fee_minor_per_order": 0,
            },
        )
    return TradingOutcomeV1(
        outcome_kind=AttributionOutcomeKind.TRADING,
        realized_pnl_minor=int(state["realized_pnl_minor"]),
        ending_position_quantity=int(state["position_shares"]),
        ending_cost_basis_minor=int(state["position_cost_basis_minor"]),
        total_commission_minor=int(state["total_commission_minor"]),
        total_fees_minor=int(state["total_fees_minor"]),
    )


def validate_attribution_scope(
    record: StrategyAttributionV1,
    *,
    account_id: str,
    mode: str,
    as_of_ns: int,
) -> None:
    """Enforce account, mode, and PIT isolation before a durable join."""
    if not isinstance(record, StrategyAttributionV1):
        raise AttributionValidationError("ATTRIBUTION_RECORD_INVALID")
    if str(account_id) != record.account_id:
        raise AttributionValidationError("ATTRIBUTION_ACCOUNT_SCOPE_MISMATCH")
    if _normalize_mode(mode) != record.mode:
        raise AttributionValidationError("ATTRIBUTION_MODE_SCOPE_MISMATCH")
    validate_timestamp_ns(as_of_ns, field_name="as_of_ns")
    if record.point_in_time_ns > as_of_ns:
        raise AttributionValidationError("ATTRIBUTION_AFTER_POINT_IN_TIME")
    if any(fill.fill_time_ns > as_of_ns for fill in record.fills):
        raise AttributionValidationError("ATTRIBUTION_FILL_AFTER_POINT_IN_TIME")


_ATTRIBUTION_ALLOWED = dataclass_field_names(StrategyAttributionV1) | {
    "identity_hash",
    "prediction_outcome_kind",
    "trading_outcome_kind",
}
_FILL_ALLOWED = dataclass_field_names(AttributionFillV1)


def attribution_fill_v1_to_dict(fill: AttributionFillV1) -> dict[str, Any]:
    body: dict[str, Any] = {
        "fill_id": fill.fill_id,
        "fill_time_ns": fill.fill_time_ns,
        "direction": fill.direction,
        "quantity": fill.quantity,
        "price_minor": fill.price_minor,
        "commission_minor": fill.commission_minor,
        "fees_minor": fill.fees_minor,
    }
    if fill.execution_ref is not None:
        body["execution_ref"] = contract_reference_to_dict(fill.execution_ref)
    return body


def attribution_fill_v1_from_dict(payload: Mapping[str, Any]) -> AttributionFillV1:
    unknown = sorted(set(payload) - _FILL_ALLOWED)
    if unknown:
        raise AttributionValidationError(f"UNKNOWN_FIELDS:{','.join(unknown)}")
    return AttributionFillV1(
        fill_id=str(payload["fill_id"]),
        execution_ref=(
            contract_reference_from_dict(payload["execution_ref"])
            if payload.get("execution_ref") is not None
            else None
        ),
        fill_time_ns=int(payload["fill_time_ns"]),
        direction=str(payload["direction"]),
        quantity=int(payload["quantity"]),
        price_minor=int(payload["price_minor"]),
        commission_minor=int(payload.get("commission_minor", 0)),
        fees_minor=int(payload.get("fees_minor", 0)),
    )


def attribution_v1_to_dict(
    record: StrategyAttributionV1,
    *,
    include_identity: bool = True,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "attribution_id": record.attribution_id,
        "schema_version": record.schema_version,
        "account_id": record.account_id,
        "mode": record.mode,
        "instrument_id": record.instrument_id,
        "allocation_ref": contract_reference_to_dict(record.allocation_ref),
        "strategy_match_ref": contract_reference_to_dict(record.strategy_match_ref),
        "strategy_id": record.strategy_id,
        "strategy_identity_hash": record.strategy_identity_hash,
        "allocation_quantity": record.allocation_quantity,
        "allocation_direction": record.allocation_direction,
        "allocation_time_ns": record.allocation_time_ns,
        "point_in_time_ns": record.point_in_time_ns,
        "fills": [attribution_fill_v1_to_dict(fill) for fill in record.fills],
        "execution_refs": [contract_reference_to_dict(ref) for ref in record.execution_refs],
        "fill_refs": [contract_reference_to_dict(ref) for ref in record.fill_refs],
        "forecast_refs": [contract_reference_to_dict(ref) for ref in record.forecast_refs],
        "prediction_outcome_refs": [
            contract_reference_to_dict(ref) for ref in record.prediction_outcome_refs
        ],
        "materialization_semantics": record.materialization_semantics,
        "coverage_algorithm_version": record.coverage_algorithm_version,
        "prediction_outcome_kind": record.prediction_outcome_kind.value,
        "trading_outcome_kind": record.trading_outcome_kind.value,
        "initial_position_quantity": record.initial_position_quantity,
        "initial_cost_basis_minor": record.initial_cost_basis_minor,
        "created_at_ns": record.created_at_ns,
    }
    for field_name in ("intent_ref", "opportunity_ref", "cluster_thesis_ref"):
        ref = getattr(record, field_name)
        if ref is not None:
            body[field_name] = contract_reference_to_dict(ref)
    if include_identity:
        body["identity_hash"] = record.identity_hash
    return body


def attribution_v1_from_dict(payload: Mapping[str, Any]) -> StrategyAttributionV1:
    unknown = sorted(set(payload) - _ATTRIBUTION_ALLOWED)
    if unknown:
        raise AttributionValidationError(f"UNKNOWN_FIELDS:{','.join(unknown)}")
    if (
        payload.get("prediction_outcome_kind", AttributionOutcomeKind.PREDICTION.value)
        != AttributionOutcomeKind.PREDICTION.value
    ):
        raise AttributionValidationError("ATTRIBUTION_PREDICTION_OUTCOME_KIND_INVALID")
    if (
        payload.get("trading_outcome_kind", AttributionOutcomeKind.TRADING.value)
        != AttributionOutcomeKind.TRADING.value
    ):
        raise AttributionValidationError("ATTRIBUTION_TRADING_OUTCOME_KIND_INVALID")
    record = StrategyAttributionV1(
        attribution_id=str(payload["attribution_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        account_id=str(payload["account_id"]),
        mode=str(payload["mode"]),
        instrument_id=str(payload["instrument_id"]),
        allocation_ref=contract_reference_from_dict(payload["allocation_ref"]),
        strategy_match_ref=contract_reference_from_dict(payload["strategy_match_ref"]),
        strategy_id=str(payload["strategy_id"]),
        strategy_identity_hash=str(payload["strategy_identity_hash"]),
        allocation_quantity=int(payload["allocation_quantity"]),
        allocation_direction=str(payload["allocation_direction"]),
        allocation_time_ns=int(payload["allocation_time_ns"]),
        point_in_time_ns=int(payload["point_in_time_ns"]),
        fills=tuple(attribution_fill_v1_from_dict(item) for item in (payload.get("fills") or ())),
        intent_ref=(
            contract_reference_from_dict(payload["intent_ref"])
            if payload.get("intent_ref") is not None
            else None
        ),
        opportunity_ref=(
            contract_reference_from_dict(payload["opportunity_ref"])
            if payload.get("opportunity_ref") is not None
            else None
        ),
        cluster_thesis_ref=(
            contract_reference_from_dict(payload["cluster_thesis_ref"])
            if payload.get("cluster_thesis_ref") is not None
            else None
        ),
        execution_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("execution_refs") or ())
        ),
        fill_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("fill_refs") or ())
        ),
        forecast_refs=tuple(
            contract_reference_from_dict(item) for item in (payload.get("forecast_refs") or ())
        ),
        prediction_outcome_refs=tuple(
            contract_reference_from_dict(item)
            for item in (payload.get("prediction_outcome_refs") or ())
        ),
        materialization_semantics=str(
            payload.get("materialization_semantics", "CUMULATIVE")
        ),
        coverage_algorithm_version=str(
            payload.get("coverage_algorithm_version", "fill-set-coverage-v1")
        ),
        initial_position_quantity=int(payload.get("initial_position_quantity", 0)),
        initial_cost_basis_minor=int(payload.get("initial_cost_basis_minor", 0)),
        created_at_ns=int(payload.get("created_at_ns", payload["allocation_time_ns"])),
    )
    serialized_identity_hash = payload.get("identity_hash")
    if serialized_identity_hash is not None and serialized_identity_hash != record.identity_hash:
        raise AttributionValidationError("ATTRIBUTION_IDENTITY_HASH_MISMATCH")
    return record


def attribution_v1_canonical_bytes(record: StrategyAttributionV1) -> bytes:
    return canonical_bytes(attribution_v1_to_dict(record))


def strategy_attribution_identity_hash(record: StrategyAttributionV1) -> str:
    return record.identity_hash


def strategy_attribution_v1_from_dict(payload: Mapping[str, Any]) -> StrategyAttributionV1:
    return attribution_v1_from_dict(payload)


def strategy_attribution_v1_to_dict(record: StrategyAttributionV1) -> dict[str, Any]:
    return attribution_v1_to_dict(record)


def strategy_attribution_canonical_bytes(record: StrategyAttributionV1) -> bytes:
    return attribution_v1_canonical_bytes(record)


def _normalize_mode(value: str) -> str:
    normalized = str(value).strip().upper()
    return {"LIVE": "ACTUAL_LIVE"}.get(normalized, normalized)


def _ref_sort_key(ref: ContractReference) -> tuple[str, str, str]:
    return ref.kind, ref.id, ref.schema_version


# Short aliases make the boundary convenient without introducing a second
# contract or a second serialization format.
AttributionRecordV1 = StrategyAttributionV1
AttributionFill = AttributionFillV1
StrategyAttribution = StrategyAttributionV1
VirtualAllocationSliceV1 = StrategyAttributionV1
StrategyAllocationSliceV1 = StrategyAttributionV1


__all__ = [
    "AttributionFill",
    "AttributionFillV1",
    "AttributionOutcomeKind",
    "AttributionRecordV1",
    "AttributionValidationError",
    "StrategyAttributionV1",
    "StrategyAttribution",
    "StrategyAllocationSliceV1",
    "TradingOutcomeV1",
    "VirtualAllocationSliceV1",
    "attribution_fill_v1_from_dict",
    "attribution_fill_v1_to_dict",
    "attribution_v1_canonical_bytes",
    "attribution_v1_from_dict",
    "attribution_v1_to_dict",
    "compute_slice_realized_pnl",
    "strategy_attribution_canonical_bytes",
    "strategy_attribution_identity_hash",
    "strategy_attribution_v1_from_dict",
    "strategy_attribution_v1_to_dict",
    "validate_attribution_scope",
]
