"""Execution eligibility admission at the order boundary (G3 / BL-0203).

The actual preview/submit path performs canonical identity admission instead
of trusting UI validation: a symbol that resolves in the XA-01 registry is
admitted only if its canonical kind/tradability is executable, and the
instrument ref carries the canonical id, kind, tradability, and contract
multiplier. Registered non-executable identities (futures family, continuous
series, economic commodities, reference-only bonds/benchmarks) fail closed.

Operator fixture registration: the interactive operator path historically
uses raw fixture symbols (e.g. ``BIYA``) that are not registered in XA-01.
``ensure_operator_fixture_registered`` registers the known operator fixture
instruments canonically through G1 (idempotent, so registration survives any
registry reset), so the standard operator path resolves through canonical
metadata.

The former legacy equity-default bridge is CLOSED: an unregistered symbol is
genuinely unknown and fails closed (``UNKNOWN_INSTRUMENT``) instead of being
silently invented as an executable equity. This makes it impossible for a
known non-executable alias (future family root, continuous series, reference
identity) to masquerade as an equity through symbol shape, and removes any
need for symbol heuristics (G3 §33/§34, Invariant E). Owner: IMP execution
core; the operator fixture allowlist is pinned by tests.
"""

from __future__ import annotations

from typing import Any

from ..xa01.enums import ExternalIdentifierType, InstrumentKind
from ..xa01.errors import Xa01Error
from ..xa01.registry import get_registry
from ..xa01.resolver import resolve_alias
from .contracts import build_instrument_ref

EXECUTION_PROVIDER_SCOPE = "INTERNAL"
UNKNOWN_INSTRUMENT = "UNKNOWN_INSTRUMENT"
UNSUPPORTED_INSTRUMENT_KIND = "UNSUPPORTED_INSTRUMENT_KIND"
NON_EXECUTABLE_INSTRUMENT = "NON_EXECUTABLE_INSTRUMENT"

# Operator fixtures that are admitted through canonical G1 registration so
# the legacy bridge is never the primary path for the standard operator
# workflow. Keep in sync with the fixtures the interactive paper path uses.
OPERATOR_FIXTURE_SYMBOLS: frozenset[str] = frozenset({"BIYA", "AAPL"})


class InstrumentAdmissionError(ValueError):
    """Fail-closed instrument admission error with a machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _resolution(store: Any, symbol: str):
    # Canonical ticker aliases are registered under the empty provider scope
    # (``register_equity`` etc.); provider symbols live under their provider.
    # Try the canonical ticker scope first, then the INTERNAL execution scope.
    for provider_id, identifier_type in (
        ("", ExternalIdentifierType.TICKER),
        (EXECUTION_PROVIDER_SCOPE, ExternalIdentifierType.TICKER),
        (EXECUTION_PROVIDER_SCOPE, ExternalIdentifierType.PROVIDER_SYMBOL),
    ):
        resolution = resolve_alias(
            provider_id=provider_id,
            alias_value=symbol,
            identifier_type=identifier_type,
            registry=store,
        )
        if resolution.status.value == "RESOLVED":
            return resolution
    return None


def ensure_operator_fixture_registered(*, registry: Any = None) -> None:
    """Canonically register the operator fixture instruments through G1.

    Idempotent: ``register_equity`` is safe to call repeatedly (descriptor
    identity matching), so this can run on every admission without side
    effects. This keeps the standard operator path (BIYA/AAPL) on canonical
    identity metadata instead of the legacy equity-default bridge.
    """
    from ..xa01.compatibility import register_equity

    store = registry or get_registry()
    for symbol in sorted(OPERATOR_FIXTURE_SYMBOLS):
        register_equity(symbol=symbol, registry=store)


def admit_order_instrument(
    symbol: str,
    *,
    registry: Any = None,
) -> dict[str, Any]:
    """Admit an order-target symbol and build its runtime instrument ref.

    Returns the instrument ref used by preview/submit. Registered identities
    are strictly admitted (canonical id + kind + tradability + multiplier);
    the operator fixtures are registered canonically on first use so they
    resolve through G1; only symbols that are neither registered nor an
    operator fixture fall through to the governed legacy equity-default
    bridge (removal condition in the module docstring).
    """
    normalized = str(symbol or "").strip().upper()
    if not normalized:
        raise InstrumentAdmissionError(UNKNOWN_INSTRUMENT, "empty instrument symbol")

    store = registry or get_registry()
    if normalized in OPERATOR_FIXTURE_SYMBOLS:
        ensure_operator_fixture_registered(registry=store)
    resolution = _resolution(store, normalized)
    if resolution is not None:
        try:
            record = store.get(resolution.canonical_id)
        except Xa01Error:
            raise InstrumentAdmissionError(UNKNOWN_INSTRUMENT, "unresolved canonical instrument") from None
        kind = record.descriptor.identity.instrument_kind
        tradability = record.descriptor.tradability
        # Non-executable kinds must never cross the boundary (G3 Invariant E).
        if kind in {
            InstrumentKind.FUTURE_FAMILY,
            InstrumentKind.CONTINUOUS_SERIES,
            InstrumentKind.COMMODITY_ECONOMIC,
            InstrumentKind.COMMODITY_SPOT,
            InstrumentKind.INDEX_BENCHMARK,
            InstrumentKind.CURRENCY_UNIT,
            InstrumentKind.FX_PAIR,
            InstrumentKind.SOVEREIGN_SECURITY,
            InstrumentKind.BOND,
        }:
            raise InstrumentAdmissionError(
                UNSUPPORTED_INSTRUMENT_KIND,
                f"instrument kind is not executable: {kind.value}",
            )
        if str(tradability.value) != "TRADABLE":
            raise InstrumentAdmissionError(
                NON_EXECUTABLE_INSTRUMENT,
                f"instrument tradability is not TRADABLE: {tradability.value}",
            )
        denomination = record.descriptor.denomination
        # G4: derivative contracts must carry explicit canonical multiplier
        # economics; missing multiplier fails closed instead of silently
        # acquiring equity-style multiplier=1 semantics.
        multiplier = getattr(denomination, "contract_multiplier", None)
        if multiplier is None or not str(multiplier).strip():
            if kind in {InstrumentKind.OPTION_CONTRACT, InstrumentKind.FUTURE_CONTRACT}:
                raise InstrumentAdmissionError(
                    UNSUPPORTED_INSTRUMENT_KIND,
                    f"{kind.value} has no canonical contract multiplier",
                )
            multiplier = "1"
        return build_instrument_ref(
            instrument_id=resolution.canonical_id,
            symbol=normalized,
            asset_class=record.descriptor.identity.asset_class.value,
            venue=str(record.descriptor.venue_id or "US_EQUITY"),
            currency=str(getattr(denomination, "currency", "USD") or "USD"),
            contract_multiplier=str(multiplier),
            instrument_kind=kind.value,
            tradability=tradability.value,
        )

    # Compatibility bridge — CLOSED. Operator fixtures are registered
    # canonically above (G1), so an unregistered symbol is genuinely unknown
    # and must fail closed rather than being silently invented as an
    # executable equity (G3 §33/§34, Invariant E). No symbol heuristics.
    raise InstrumentAdmissionError(
        UNKNOWN_INSTRUMENT,
        f"unresolved instrument symbol (legacy bridge closed): {normalized}",
    )


def assert_executable_or_registered(symbol: str, *, registry: Any = None) -> None:
    """Fail-closed check for known non-executable identities (no ref building).

    Raises ``InstrumentAdmissionError`` when the symbol resolves to a
    non-executable canonical identity; unregistered symbols pass (legacy
    bridge). Used by tests and guard call sites that only need the verdict.
    """
    admit_order_instrument(symbol, registry=registry)


__all__ = [
    "EXECUTION_PROVIDER_SCOPE",
    "NON_EXECUTABLE_INSTRUMENT",
    "OPERATOR_FIXTURE_SYMBOLS",
    "UNKNOWN_INSTRUMENT",
    "UNSUPPORTED_INSTRUMENT_KIND",
    "InstrumentAdmissionError",
    "admit_order_instrument",
    "assert_executable_or_registered",
    "ensure_operator_fixture_registered",
]