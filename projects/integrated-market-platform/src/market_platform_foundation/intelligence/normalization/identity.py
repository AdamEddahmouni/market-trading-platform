"""Deterministic event identity for BUILD 03 normalization."""

from __future__ import annotations

from ...canonical import canonical_bytes, sha256_bytes
from ...contracts.identity import normalized_event_id


def derive_event_id_from_provider(
    *,
    provider_id: str,
    venue_id: str,
    source_record_id: str,
    event_family: str,
    source_revision_id: str = "1",
    channel_id: str = "",
    publisher_id: str | None = None,
    source_instance_id: str | None = None,
    subrecord_discriminator: str = "",
) -> str:
    """Prefer stable provider-native identity for canonical event_id."""
    return normalized_event_id(
        provider_id=provider_id,
        venue_id=venue_id or "GLOBAL",
        publisher_id=publisher_id or provider_id,
        channel_id=channel_id or source_record_id,
        source_instance_id=source_instance_id or provider_id,
        source_record_id=source_record_id,
        source_revision_id=source_revision_id,
        event_family=event_family,
        subrecord_discriminator=subrecord_discriminator,
    )


def derive_event_id_composite(
    *,
    provider_id: str,
    identity_fields: dict[str, object],
    event_family: str,
) -> str:
    """Deterministic fallback when no native immutable provider ID exists."""
    digest = sha256_bytes(canonical_bytes({"provider_id": provider_id, "event_family": event_family, **identity_fields}))
    return derive_event_id_from_provider(
        provider_id=provider_id,
        venue_id="GLOBAL",
        source_record_id=digest[:32],
        event_family=event_family,
        channel_id=str(identity_fields.get("channel_id", "")),
    )


def hash_raw_payload(raw: object) -> str:
    return sha256_bytes(canonical_bytes(raw))


__all__ = [
    "derive_event_id_composite",
    "derive_event_id_from_provider",
    "hash_raw_payload",
]
