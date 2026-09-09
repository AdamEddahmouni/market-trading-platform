"""XA-01 tradability and execution-boundary safety.

G1 invariant: an identity is executable only when it is explicitly a tradable
instrument/contract form. Continuous series, synthetic aggregates, family/root
identities, economic commodities, reference spot identities, currencies, FX
pairs, benchmarks, and reference-only bonds can never become an order target.

The guard fails closed: unknown/missing tradability semantics default to
non-executable for canonical identities, and ``assert_executable`` raises
``Xa01Error(NON_EXECUTABLE_INSTRUMENT, ...)``.
"""

from __future__ import annotations

from .contracts import InstrumentRecord
from .enums import InstrumentKind, Tradability
from .errors import Xa01Error, Xa01ErrorCode

# Kinds that are inherently non-executable regardless of any flag: they are
# family/root, aggregate/synthetic, economic, or reference identities.
NON_EXECUTABLE_KINDS: frozenset[InstrumentKind] = frozenset(
    {
        InstrumentKind.COMMODITY_ECONOMIC,
        InstrumentKind.COMMODITY_SPOT,
        InstrumentKind.FUTURE_FAMILY,
        InstrumentKind.CONTINUOUS_SERIES,
        InstrumentKind.SOVEREIGN_SECURITY,
        InstrumentKind.BOND,
        InstrumentKind.CURRENCY_UNIT,
        InstrumentKind.FX_PAIR,
        InstrumentKind.INDEX_BENCHMARK,
    }
)

# Kinds that are executable contract/security forms when explicitly tradable.
EXECUTABLE_KINDS: frozenset[InstrumentKind] = frozenset(
    {
        InstrumentKind.TRADABLE_SECURITY,
        InstrumentKind.FUTURE_CONTRACT,
        InstrumentKind.OPTION_CONTRACT,
        InstrumentKind.CRYPTO_PAIR,
    }
)

# Tradability values that are never executable.
NON_EXECUTABLE_TRADABILITY: frozenset[Tradability] = frozenset(
    {
        Tradability.REFERENCE_ONLY,
        Tradability.SYNTHETIC,
        Tradability.CONTINUOUS_SERIES,
    }
)


def default_tradability(instrument_kind: InstrumentKind) -> Tradability:
    """Derive the default tradability for a kind.

    Explicit and deterministic: executable kinds default to TRADABLE; every
    other kind defaults to REFERENCE_ONLY (continuous series stays
    CONTINUOUS_SERIES so its synthetic nature is always visible).
    """
    if instrument_kind in EXECUTABLE_KINDS:
        return Tradability.TRADABLE
    if instrument_kind == InstrumentKind.CONTINUOUS_SERIES:
        return Tradability.CONTINUOUS_SERIES
    return Tradability.REFERENCE_ONLY


def is_executable(*, instrument_kind: InstrumentKind, tradability: Tradability | None = None) -> bool:
    """Deterministic answer: can this identity legally become an order target?"""
    effective = tradability if tradability is not None else default_tradability(instrument_kind)
    if effective in NON_EXECUTABLE_TRADABILITY:
        return False
    if instrument_kind in NON_EXECUTABLE_KINDS:
        return False
    return effective == Tradability.TRADABLE and instrument_kind in EXECUTABLE_KINDS


def validate_tradability(
    *,
    instrument_kind: InstrumentKind,
    tradability: Tradability,
) -> None:
    """Reject contradictory kind/tradability combinations at registration.

    A kind that is inherently non-executable must never be registered as
    TRADABLE, and a tradable kind must never be registered as a continuous
    series. Raises ``Xa01Error(TRADABILITY_CONFLICT)`` otherwise.
    """
    if tradability == Tradability.TRADABLE and instrument_kind in NON_EXECUTABLE_KINDS:
        raise Xa01Error(
            Xa01ErrorCode.TRADABILITY_CONFLICT,
            "inherently non-executable kind cannot be registered as tradable",
            {"instrument_kind": instrument_kind.value, "tradability": tradability.value},
        )
    if tradability == Tradability.CONTINUOUS_SERIES and instrument_kind != InstrumentKind.CONTINUOUS_SERIES:
        raise Xa01Error(
            Xa01ErrorCode.TRADABILITY_CONFLICT,
            "continuous-series tradability requires CONTINUOUS_SERIES kind",
            {"instrument_kind": instrument_kind.value, "tradability": tradability.value},
        )


def selector_action_for_kind(instrument_kind: InstrumentKind, *, executable: bool) -> str:
    """Product-facing selection action — distinct from execution eligibility."""
    if instrument_kind == InstrumentKind.OPTION_CONTRACT:
        return "OPEN_OPTIONS_WORKSPACE" if executable else "UNSUPPORTED_INSTRUMENT"
    if instrument_kind == InstrumentKind.FUTURE_CONTRACT:
        return "OPEN_FUTURES_WORKSPACE" if executable else "UNSUPPORTED_INSTRUMENT"
    if instrument_kind == InstrumentKind.TRADABLE_SECURITY:
        return "OPEN_EQUITY_WORKSPACE" if executable else "REFERENCE_ONLY"
    if instrument_kind == InstrumentKind.CRYPTO_PAIR:
        return "OPEN_CRYPTO_REFERENCE" if executable else "REFERENCE_ONLY"
    if instrument_kind == InstrumentKind.FUTURE_FAMILY:
        return "OPEN_FUTURE_FAMILY_REFERENCE"
    if instrument_kind == InstrumentKind.CONTINUOUS_SERIES:
        return "OPEN_CONTINUOUS_REFERENCE"
    if instrument_kind in {InstrumentKind.BOND, InstrumentKind.SOVEREIGN_SECURITY}:
        return "REFERENCE_ONLY"
    if instrument_kind in {
        InstrumentKind.COMMODITY_ECONOMIC,
        InstrumentKind.COMMODITY_SPOT,
    }:
        return "REFERENCE_ONLY"
    return "UNSUPPORTED_INSTRUMENT" if not executable else "OPEN_WORKSPACE"


def assert_executable(record: InstrumentRecord) -> None:
    """Raise unless the record's identity is an executable instrument/contract.

    Fail-closed guard used at canonical identity resolution boundaries. A
    continuous series, family/root, synthetic aggregate, or any other
    reference identity raises ``Xa01Error(NON_EXECUTABLE_INSTRUMENT)``.
    """
    identity = record.descriptor.identity
    tradability = record.descriptor.tradability
    if is_executable(instrument_kind=identity.instrument_kind, tradability=tradability):
        return
    raise Xa01Error(
        Xa01ErrorCode.NON_EXECUTABLE_INSTRUMENT,
        "identity is not executable (reference/synthetic identities cannot become order targets)",
        {
            "canonical_id": identity.canonical_id,
            "instrument_kind": identity.instrument_kind.value,
            "asset_class": identity.asset_class.value,
            "tradability": tradability.value,
        },
    )


__all__ = [
    "EXECUTABLE_KINDS",
    "NON_EXECUTABLE_KINDS",
    "NON_EXECUTABLE_TRADABILITY",
    "assert_executable",
    "default_tradability",
    "is_executable",
    "selector_action_for_kind",
    "validate_tradability",
]