"""XA-01 alias resolution."""

from __future__ import annotations

from .contracts import AliasResolution
from .enums import AliasResolutionStatus, ExternalIdentifierType
from .errors import Xa01Error, Xa01ErrorCode
from .registry import InstrumentRegistry, get_registry
from .tradability import assert_executable


def resolve_alias(
    *,
    provider_id: str,
    alias_value: str,
    identifier_type: ExternalIdentifierType = ExternalIdentifierType.PROVIDER_SYMBOL,
    registry: InstrumentRegistry | None = None,
    as_of: str = "",
) -> AliasResolution:
    del as_of  # reserved for bitemporal alias validity in follow-on work
    store = registry or get_registry()
    symbol = str(alias_value or "").strip().upper()
    if not symbol:
        return AliasResolution(
            status=AliasResolutionStatus.UNKNOWN,
            provider_id=provider_id,
            alias_value="",
            quality_flags=("ALIAS_EMPTY",),
        )
    canonical_id = store.resolve_alias_scope(
        provider_id=provider_id,
        identifier_type=identifier_type,
        alias_value=symbol,
    )
    if canonical_id is None:
        return AliasResolution(
            status=AliasResolutionStatus.UNKNOWN,
            provider_id=provider_id,
            alias_value=symbol,
            quality_flags=("ALIAS_UNRESOLVED",),
        )
    record = store.get(canonical_id)
    return AliasResolution(
        status=AliasResolutionStatus.RESOLVED,
        provider_id=provider_id,
        alias_value=symbol,
        canonical_id=canonical_id,
        instrument_kind=record.descriptor.identity.instrument_kind,
        asset_class=record.descriptor.identity.asset_class,
    )


def resolve_executable_alias(
    *,
    provider_id: str,
    alias_value: str,
    identifier_type: ExternalIdentifierType = ExternalIdentifierType.PROVIDER_SYMBOL,
    registry: InstrumentRegistry | None = None,
) -> str:
    """Resolve a provider alias to a canonical ID and prove it is executable.

    Fail-closed execution-boundary resolver: an alias that resolves to a
    continuous series, family/root, or any other non-executable identity
    raises ``Xa01Error(NON_EXECUTABLE_INSTRUMENT)`` instead of returning a
    tradable-looking ID.
    """
    store = registry or get_registry()
    resolution = resolve_alias(
        provider_id=provider_id,
        alias_value=alias_value,
        identifier_type=identifier_type,
        registry=store,
    )
    if resolution.status != AliasResolutionStatus.RESOLVED:
        raise Xa01Error(
            Xa01ErrorCode.UNKNOWN_INSTRUMENT,
            "alias does not resolve to a canonical instrument",
            {"provider_id": provider_id, "alias_value": alias_value},
        )
    record = store.get(resolution.canonical_id)
    assert_executable(record)
    return resolution.canonical_id
