"""XA-01 alias resolution."""

from __future__ import annotations

from .contracts import AliasResolution
from .enums import AliasResolutionStatus, ExternalIdentifierType
from .registry import InstrumentRegistry, get_registry


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
