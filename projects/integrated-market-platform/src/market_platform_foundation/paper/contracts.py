"""Canonical paper execution and instrument contracts."""

from __future__ import annotations

import uuid
from decimal import Decimal
import math
from typing import Any, Mapping

from ..canonical import canonical_bytes, sha256_bytes
from ..xa01.enums import InstrumentKind, Tradability
from ..xa01.tradability import NON_EXECUTABLE_KINDS

# DEPRECATED (G1 / CON-01): this tuple is a backward-compatibility view over
# the single canonical asset-class vocabulary owned by XA-01
# (``xa01.enums.XaAssetClass``). New code must import asset classes from
# ``xa01.enums``; this view exists only for persisted Paper records and legacy
# callers and will be removed once every caller migrates. It intentionally
# retains the paper-local PREDICTION_MARKET value, which has no XA-01 class.
ASSET_CLASSES: tuple[str, ...] = (
    "EQUITY",
    "OPTION",
    "FUTURE",
    "CRYPTO",
    "PREDICTION_MARKET",
)

ORDER_SIDES: tuple[str, ...] = ("BUY", "SELL")
ORDER_TYPES: tuple[str, ...] = ("MARKET", "LIMIT")

ORDER_LIFECYCLE_STATES: tuple[str, ...] = (
    "CREATED",
    "RISK_ACCEPTED",
    "RISK_REJECTED",
    "SUBMITTED",
    "WORKING",
    "ACTIVATED",
    "PARTIALLY_FILLED",
    "REPLACE_PENDING",
    "REPLACED",
    "FILLED",
    "CANCEL_PENDING",
    "CANCELLED",
    "REJECTED",
    "EXPIRED",
)

ORDER_LIFECYCLE_TERMINAL_STATES: tuple[str, ...] = (
    "FILLED",
    "CANCELLED",
    "REJECTED",
    "EXPIRED",
    "RISK_REJECTED",
)

VALID_ORDER_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "CREATED": ("RISK_ACCEPTED", "RISK_REJECTED", "REJECTED", "ACTIVATED", "SUBMITTED"),
    "RISK_ACCEPTED": ("SUBMITTED", "ACTIVATED", "WORKING"),
    "SUBMITTED": ("ACTIVATED", "WORKING", "REJECTED", "CANCEL_PENDING"),
    "WORKING": ("PARTIALLY_FILLED", "FILLED", "CANCEL_PENDING", "REJECTED", "EXPIRED", "REPLACE_PENDING"),
    "ACTIVATED": ("PARTIALLY_FILLED", "FILLED", "REJECTED", "CANCEL_PENDING", "REPLACE_PENDING"),
    "PARTIALLY_FILLED": ("FILLED", "CANCEL_PENDING", "REPLACE_PENDING"),
    "REPLACE_PENDING": ("REPLACED",),
    "REPLACED": ("PARTIALLY_FILLED", "FILLED", "CANCEL_PENDING", "REJECTED", "EXPIRED", "REPLACE_PENDING"),
    "CANCEL_PENDING": ("CANCELLED",),
}


def build_instrument_ref(
    *,
    instrument_id: str,
    asset_class: str = "EQUITY",
    venue: str = "US_EQUITY",
    symbol: str,
    currency: str = "USD",
    tick_size: str = "0.01",
    lot_size: int = 1,
    contract_multiplier: str = "1",
    expiration: str | None = None,
    strike: str | None = None,
    option_right: str | None = None,
    settlement_type: str | None = None,
    underlying: str | None = None,
    instrument_kind: str | None = None,
    tradability: str | None = None,
) -> dict[str, Any]:
    """Build a runtime instrument reference (display/simulation, not identity).

    The reference is NOT the canonical identity authority (XA-01 owns that).
    ``instrument_kind`` and ``tradability`` are carried through so the order
    boundary can fail closed: an explicit continuous/synthetic/reference
    identity can never become an order target (see build_user_order_intent).
    """
    if asset_class not in ASSET_CLASSES:
        raise ValueError("INSTRUMENT_ASSET_CLASS_INVALID")
    body: dict[str, Any] = {
        "asset_class": asset_class,
        "contract_multiplier": contract_multiplier,
        "currency": currency,
        "instrument_id": instrument_id,
        "lot_size": lot_size,
        "symbol": symbol,
        "tick_size": tick_size,
        "venue": venue,
    }
    if instrument_kind is not None:
        if instrument_kind not in {kind.value for kind in InstrumentKind}:
            raise ValueError("INSTRUMENT_KIND_INVALID")
        body["instrument_kind"] = instrument_kind
    if tradability is not None:
        if tradability not in {item.value for item in Tradability}:
            raise ValueError("INSTRUMENT_TRADABILITY_INVALID")
        body["tradability"] = tradability
    for key, value in (
        ("expiration", expiration),
        ("option_right", option_right),
        ("settlement_type", settlement_type),
        ("strike", strike),
        ("underlying", underlying),
    ):
        if value is not None:
            body[key] = value
    return body


def _assert_instrument_executable(instrument: Mapping[str, Any]) -> None:
    """Fail closed: reject order intents targeting reference/synthetic identities.

    An instrument reference that explicitly carries a non-executable
    instrument kind (family/root, continuous series, economic commodity,
    reference bond/sovereign, currency, FX pair, benchmark, spot reference) or
    a non-TRADABLE tradability value cannot become an order target. Legacy
    equity refs (which carry neither field) are unaffected.
    """
    kind_raw = instrument.get("instrument_kind")
    tradability_raw = instrument.get("tradability")
    if kind_raw is not None:
        try:
            kind = InstrumentKind(str(kind_raw))
        except ValueError:
            raise ValueError("INSTRUMENT_KIND_INVALID") from None
        if kind in NON_EXECUTABLE_KINDS:
            raise ValueError(
                f"INSTRUMENT_NOT_EXECUTABLE:{kind.value}"
            )
    if tradability_raw is not None:
        if str(tradability_raw) != Tradability.TRADABLE.value:
            raise ValueError(
                f"INSTRUMENT_NOT_EXECUTABLE:{str(tradability_raw)}"
            )


def direction_from_side(side: str) -> str:
    if side == "BUY":
        return "long"
    if side == "SELL":
        return "short"
    raise ValueError("ORDER_SIDE_INVALID")


RESEARCH_CANDIDATE_ID_PREFIX = "CAND-"


def _validate_research_candidate_id(research_candidate_id: str) -> None:
    """Fail closed: a provenance id must be a well-formed ``CAND-<uuid>``.

    Unrecognized / malformed ids are rejected at intent build rather than
    silently dropped, so provenance is never silently lost (``DEC-MAN-001``).
    """
    if not research_candidate_id.startswith(RESEARCH_CANDIDATE_ID_PREFIX):
        raise ValueError("RESEARCH_CANDIDATE_ID_INVALID")
    tail = research_candidate_id[len(RESEARCH_CANDIDATE_ID_PREFIX):]
    try:
        uuid.UUID(tail)
    except (ValueError, AttributeError):
        raise ValueError("RESEARCH_CANDIDATE_ID_INVALID") from None


def _lineage_ref_to_dict(value: Any) -> dict[str, Any]:
    """Serialize a backend lineage reference without coupling Paper to a domain type."""
    if isinstance(value, Mapping):
        kind = value.get("kind")
        identifier = value.get("id")
        schema_version = value.get("schema_version", "1")
    else:
        kind = getattr(value, "kind", None)
        identifier = getattr(value, "id", None)
        schema_version = getattr(value, "schema_version", "1")
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError("PAPER_LINEAGE_REFERENCE_KIND_REQUIRED")
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError("PAPER_LINEAGE_REFERENCE_ID_REQUIRED")
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise ValueError("PAPER_LINEAGE_REFERENCE_SCHEMA_INVALID")
    return {
        "kind": kind,
        "id": identifier,
        "schema_version": schema_version,
    }


def _quantity_facts_to_dict(value: Mapping[str, Any] | None) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("PAPER_QUANTITY_FACTS_INVALID")
    facts: dict[str, int] = {}
    allowed = {
        "allocation_desired_quantity",
        "allocation_desired_notional_minor",
        "proposal_requested_quantity",
        "proposal_requested_notional_minor",
        "risk_approved_quantity",
        "risk_approved_notional_minor",
        "submitted_quantity",
        "filled_quantity",
    }
    for key, raw in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("PAPER_QUANTITY_FACT_KEY_INVALID")
        if key not in allowed:
            raise ValueError("PAPER_QUANTITY_FACT_KEY_UNSUPPORTED")
        if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
            raise ValueError("PAPER_QUANTITY_FACT_INVALID")
        facts[key] = raw
    return facts


def build_user_order_intent(
    *,
    instrument: dict[str, Any],
    side: str,
    quantity: int,
    observation_time: int,
    order_type: str = "MARKET",
    limit_price_minor: int | None = None,
    client_order_id: str,
    idempotency_key: str,
    correlation_id: str | None = None,
    decision_source_snapshot: dict[str, Any] | None = None,
    research_candidate_id: str | None = None,
    lineage_refs: tuple[Any, ...] | list[Any] = (),
    quantity_facts: Mapping[str, Any] | None = None,
    risk_decision_id: str | None = None,
) -> dict[str, Any]:
    if side not in ORDER_SIDES:
        raise ValueError("ORDER_SIDE_INVALID")
    if order_type not in ORDER_TYPES:
        raise ValueError("ORDER_TYPE_INVALID")
    # Fail closed against adversarial numerics: NaN bypasses every ordering
    # comparison and a float/bool quantity would poison content-derived ids
    # and downstream int() coercions.
    if (
        not isinstance(quantity, int)
        or isinstance(quantity, bool)
        or quantity <= 0
    ):
        raise ValueError("ORDER_QUANTITY_INVALID")
    if limit_price_minor is not None and (
        not isinstance(limit_price_minor, int)
        or isinstance(limit_price_minor, bool)
        or not math.isfinite(limit_price_minor)
        or limit_price_minor < 0
    ):
        raise ValueError("ORDER_LIMIT_PRICE_INVALID")
    if not isinstance(observation_time, int) or isinstance(observation_time, bool):
        raise ValueError("ORDER_OBSERVATION_TIME_INVALID")
    if research_candidate_id is not None:
        _validate_research_candidate_id(research_candidate_id)
    _assert_instrument_executable(instrument)
    direction = direction_from_side(side)
    body: dict[str, Any] = {
        "action": "OPEN",
        "client_order_id": client_order_id,
        "created_time": observation_time,
        "desired_quantity": quantity,
        "direction": direction,
        "idempotency_key": idempotency_key,
        "instrument": instrument,
        "instrument_id": instrument["instrument_id"],
        "order_type": order_type,
        "side": side,
        "source": "USER_ORDER_TICKET",
    }
    if limit_price_minor is not None:
        body["limit_price_minor"] = limit_price_minor
    if correlation_id:
        body["correlation_id"] = correlation_id
    if decision_source_snapshot:
        body["decision_source_snapshot"] = decision_source_snapshot
    if research_candidate_id:
        body["research_candidate_id"] = research_candidate_id
    if risk_decision_id:
        body["risk_decision_id"] = risk_decision_id
    serialized_lineage = [_lineage_ref_to_dict(ref) for ref in lineage_refs]
    if serialized_lineage:
        body["lineage_refs"] = serialized_lineage
    facts = _quantity_facts_to_dict(quantity_facts)
    if facts:
        body["quantity_facts"] = facts
        body.update(facts)
    return {
        **body,
        "intent_id": sha256_bytes(canonical_bytes(body)),
    }


def decimal_minor_to_display(minor: int, *, scale: int = 100) -> str:
    value = Decimal(minor) / Decimal(scale)
    return format(value, "f")


# G3 semantic order-intent fields that participate in the preview binding and
# content-derived idempotency digest. Transport correlation fields
# (client_order_id, idempotency_key, correlation_id) and provenance fields
# (decision_source_snapshot, lineage_refs, quantity_facts, created_time) are
# deliberately EXCLUDED: the same financial intent must produce the same
# digest regardless of how it was correlated or retried.
SEMANTIC_INTENT_FIELDS: tuple[str, ...] = (
    "action",
    "instrument_id",
    "side",
    "desired_quantity",
    "order_type",
    "limit_price_minor",
    "currency",
    "quantity_unit",
)


def _semantic_value(intent: Mapping[str, Any], key: str) -> Any:
    if key in intent:
        return intent.get(key)
    instrument = intent.get("instrument")
    if isinstance(instrument, Mapping) and key in instrument:
        return instrument.get(key)
    if key == "quantity_unit":
        return "SHARES"
    return None


def build_semantic_intent_digest(intent: Mapping[str, Any]) -> str:
    """Deterministic digest of the financial/semantic order intent.

    BUY 100 AAPL MARKET, BUY 101 AAPL MARKET, SELL 100 AAPL MARKET,
    BUY 100 MSFT MARKET, and BUY 100 AAPL LIMIT 200 all hash differently;
    the same semantic intent hashes identically even when transport ids or
    provenance snapshots differ. This is the digest bound into server
    preview records and used for content-derived idempotency (G3 / BL-0201,
    BL-0207).
    """
    body: dict[str, Any] = {}
    for key in SEMANTIC_INTENT_FIELDS:
        value = _semantic_value(intent, key)
        if value is None:
            continue
        if isinstance(value, int) and not isinstance(value, bool):
            body[key] = str(value)
        elif isinstance(value, (str, float)):
            upper_keys = {"side", "order_type", "action", "currency", "quantity_unit"}
            body[key] = str(value).upper() if key in upper_keys else str(value)
        else:
            body[key] = value
    return sha256_bytes(canonical_bytes(body))


# G3 preview-binding reason codes (BL-0201). Kept here so the UI and the
# domain boundary share one vocabulary.
PREVIEW_REQUIRED = "PREVIEW_REQUIRED"
PREVIEW_EXPIRED = "PREVIEW_EXPIRED"
PREVIEW_STALE = "PREVIEW_STALE"
PREVIEW_INTENT_MISMATCH = "PREVIEW_INTENT_MISMATCH"
PREVIEW_ACCOUNT_MISMATCH = "PREVIEW_ACCOUNT_MISMATCH"
PREVIEW_MODE_MISMATCH = "PREVIEW_MODE_MISMATCH"
PREVIEW_PORTFOLIO_STALE = "PREVIEW_PORTFOLIO_STALE"
PREVIEW_POLICY_STALE = "PREVIEW_POLICY_STALE"


def normalize_execution_intent(intent: dict[str, Any]) -> dict[str, Any]:
    """Extract canonical execution fields for shared simulator/risk path."""
    body: dict[str, Any] = {
        "action": intent.get("action", "OPEN"),
        "created_time": intent["created_time"],
        "desired_quantity": int(intent["desired_quantity"]),
        "direction": intent["direction"],
        "instrument_id": intent["instrument_id"],
    }
    for key in (
        "research_candidate_id",
        "signal_prediction_cutoff",
        "strategy_identity_hash",
        "order_type",
        "limit_price_minor",
        "lineage_refs",
        "quantity_facts",
        "risk_decision_id",
        "allocation_desired_quantity",
        "allocation_desired_notional_minor",
        "proposal_requested_quantity",
        "proposal_requested_notional_minor",
        "risk_approved_quantity",
        "risk_approved_notional_minor",
        "submitted_quantity",
    ):
        if key in intent:
            body[key] = intent[key]
    return {
        **body,
        "intent_id": sha256_bytes(canonical_bytes(body)),
    }


def validate_order_transition(*, prior_state: str, next_state: str) -> None:
    if prior_state in ORDER_LIFECYCLE_TERMINAL_STATES:
        raise ValueError(f"ORDER_TRANSITION_FROM_TERMINAL: {prior_state}")
    allowed = VALID_ORDER_TRANSITIONS.get(prior_state, ())
    if next_state not in allowed and prior_state != next_state:
        if next_state in ORDER_LIFECYCLE_TERMINAL_STATES and prior_state in {"CREATED", "ACTIVATED"}:
            return
        raise ValueError(f"ORDER_TRANSITION_INVALID: {prior_state} -> {next_state}")


def next_event_sequence(events: list[dict[str, Any]]) -> int:
    if not events:
        return 0
    return max(int(event.get("sequence", 0)) for event in events) + 1
