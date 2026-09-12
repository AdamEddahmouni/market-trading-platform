"""Market Data Capability Contract — canonical access states and validation.

Aligned to ``docs/architecture/MARKET_DATA_CAPABILITY_CONTRACT.md``. This module
does not duplicate ``ProviderRegistry`` metadata; it validates governed snapshot
records and promotion semantics for Wave B capability-matrix tooling.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, Sequence

CAPABILITY_MATRIX_SCHEMA_VERSION = "1.0.0"
CAPABILITY_MATRIX_LOGICAL_ID = "providers.capability_matrix_snapshot"

_SECRET_KEY_PATTERN = re.compile(
    r"(api[_-]?key|token|secret|password|totp)", re.IGNORECASE
)
_SECRET_VALUE_PATTERN = re.compile(
    r"(sk-[a-zA-Z0-9]{10,}|AKIA[0-9A-Z]{16}|[A-Za-z0-9+/]{32,}={0,2})"
)


class CapabilityAccessState(StrEnum):
    """Governed provider access ladder (catalog → blocked)."""

    CATALOGED = "CATALOGED"
    CONFIGURED = "CONFIGURED"
    ENTITLED = "ENTITLED"
    REACHABLE = "REACHABLE"
    SAMPLE_VERIFIED = "SAMPLE_VERIFIED"
    ROLE_VALIDATED = "ROLE_VALIDATED"
    CAMPAIGN_BOUND = "CAMPAIGN_BOUND"
    PROMOTED = "PROMOTED"
    BLOCKED = "BLOCKED"


_ACCESS_STATE_ORDER: tuple[CapabilityAccessState, ...] = tuple(CapabilityAccessState)


class CampaignRole(StrEnum):
    AUTHORITY = "AUTHORITY"
    CHALLENGER = "CHALLENGER"
    CONTEXT_ONLY = "CONTEXT_ONLY"
    COMPARATOR_ONLY = "COMPARATOR_ONLY"
    PROHIBITED = "PROHIBITED"
    UNASSIGNED = "UNASSIGNED"


class CapabilitySupportLevel(StrEnum):
    """Whether the platform knows a capability exists for the provider."""

    KNOWN_SUPPORTED = "KNOWN_SUPPORTED"
    KNOWN_UNSUPPORTED = "KNOWN_UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class CapabilityDimensionState(StrEnum):
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNSUPPORTED = "UNSUPPORTED"
    NOT_CONNECTED = "NOT_CONNECTED"
    STALE = "STALE"
    VERIFIED = "VERIFIED"
    CATALOGED = "CATALOGED"
    BLOCKED = "BLOCKED"


class CapabilityContractError(ValueError):
    """Raised when a capability record violates contract rules."""


@dataclass(frozen=True, slots=True)
class CapabilityDimension:
    dimension: str
    state: CapabilityDimensionState
    observed_at: str | None = None
    evidence_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "dimension": self.dimension,
            "state": self.state.value,
            "evidence_refs": list(self.evidence_refs),
        }
        if self.observed_at is not None:
            payload["observed_at"] = self.observed_at
        return payload


@dataclass(frozen=True, slots=True)
class ProviderCapabilityEntry:
    capability_id: str
    support_level: CapabilitySupportLevel
    access_state: CapabilityAccessState | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "capability_id": self.capability_id,
            "support_level": self.support_level.value,
        }
        if self.access_state is not None:
            payload["access_state"] = self.access_state.value
        if self.notes:
            payload["notes"] = self.notes
        return payload


@dataclass(frozen=True, slots=True)
class ProviderCapabilityRecord:
    provider_id: str
    access_state: CapabilityAccessState
    campaign_role: CampaignRole
    support_level: CapabilitySupportLevel
    capabilities: tuple[ProviderCapabilityEntry, ...]
    display_name: str = ""
    capability_contract_id: str | None = None
    observed_at: str | None = None
    verification_evidence: tuple[str, ...] = ()
    dimensions: tuple[CapabilityDimension, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "access_state": self.access_state.value,
            "campaign_role": self.campaign_role.value,
            "capabilities": [row.to_dict() for row in self.capabilities],
            "provider_id": self.provider_id,
            "support_level": self.support_level.value,
        }
        if self.display_name:
            payload["display_name"] = self.display_name
        if self.capability_contract_id:
            payload["capability_contract_id"] = self.capability_contract_id
        if self.observed_at:
            payload["observed_at"] = self.observed_at
        if self.verification_evidence:
            payload["verification_evidence"] = list(self.verification_evidence)
        if self.dimensions:
            payload["dimensions"] = [row.to_dict() for row in self.dimensions]
        if self.notes:
            payload["notes"] = self.notes
        return payload


@dataclass(frozen=True, slots=True)
class CapabilityMatrixSnapshot:
    observed_at: str
    sources: tuple[dict[str, str], ...]
    providers: tuple[ProviderCapabilityRecord, ...]
    schema_version: str = CAPABILITY_MATRIX_SCHEMA_VERSION
    logical_id: str = CAPABILITY_MATRIX_LOGICAL_ID
    secrets_included: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "logical_id": self.logical_id,
            "observed_at": self.observed_at,
            "providers": [row.to_dict() for row in self.providers],
            "schema_version": self.schema_version,
            "secrets_included": self.secrets_included,
            "sources": [dict(item) for item in self.sources],
        }


def access_state_at_least(
    state: CapabilityAccessState, minimum: CapabilityAccessState
) -> bool:
    try:
        return _ACCESS_STATE_ORDER.index(state) >= _ACCESS_STATE_ORDER.index(minimum)
    except ValueError:
        return False


def validate_provider_record(record: ProviderCapabilityRecord) -> None:
    if not record.provider_id.strip():
        raise CapabilityContractError("PROVIDER_ID_REQUIRED")
    if record.access_state == CapabilityAccessState.PROMOTED and not record.verification_evidence:
        raise CapabilityContractError("PROMOTED_REQUIRES_VERIFICATION_EVIDENCE")
    if record.access_state == CapabilityAccessState.BLOCKED:
        return
    for entry in record.capabilities:
        if entry.support_level == CapabilitySupportLevel.KNOWN_UNSUPPORTED:
            if entry.access_state not in (
                None,
                CapabilityAccessState.CATALOGED,
                CapabilityAccessState.BLOCKED,
            ):
                raise CapabilityContractError("UNSUPPORTED_CAPABILITY_ACCESS_STATE_INVALID")
        if (
            entry.support_level == CapabilitySupportLevel.UNKNOWN
            and entry.access_state == CapabilityAccessState.PROMOTED
        ):
            raise CapabilityContractError("UNKNOWN_SUPPORT_CANNOT_BE_PROMOTED")


def validate_snapshot(snapshot: CapabilityMatrixSnapshot) -> None:
    if snapshot.schema_version != CAPABILITY_MATRIX_SCHEMA_VERSION:
        raise CapabilityContractError("SCHEMA_VERSION_UNSUPPORTED")
    if snapshot.logical_id != CAPABILITY_MATRIX_LOGICAL_ID:
        raise CapabilityContractError("LOGICAL_ID_INVALID")
    if snapshot.secrets_included:
        raise CapabilityContractError("SECRETS_MUST_NOT_BE_INCLUDED")
    if not snapshot.observed_at.strip():
        raise CapabilityContractError("OBSERVED_AT_REQUIRED")
    for record in snapshot.providers:
        validate_provider_record(record)


def redact_secrets_text(text: str) -> str:
    """Replace likely secret material in free text (snapshot hygiene only)."""

    redacted = text
    for match in _SECRET_VALUE_PATTERN.finditer(redacted):
        redacted = redacted.replace(match.group(0), "[REDACTED]")
    return redacted


def redact_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Deep-copy a JSON-like mapping with secret keys and values redacted."""

    def _walk(item: Any, parent_key: str = "") -> Any:
        if isinstance(item, dict):
            result: dict[str, Any] = {}
            for key, val in item.items():
                key_str = str(key)
                if _SECRET_KEY_PATTERN.search(key_str):
                    result[key_str] = "[REDACTED]"
                else:
                    result[key_str] = _walk(val, parent_key=key_str)
            return result
        if isinstance(item, list):
            return [_walk(row) for row in item]
        if isinstance(item, str):
            if _SECRET_KEY_PATTERN.search(parent_key):
                return "[REDACTED]"
            return redact_secrets_text(item)
        return item

    return _walk(dict(value))


def provider_record_from_dict(payload: Mapping[str, Any]) -> ProviderCapabilityRecord:
    capabilities = tuple(
        ProviderCapabilityEntry(
            capability_id=str(row["capability_id"]),
            support_level=CapabilitySupportLevel(str(row["support_level"])),
            access_state=(
                CapabilityAccessState(str(row["access_state"]))
                if row.get("access_state")
                else None
            ),
            notes=str(row.get("notes") or ""),
        )
        for row in payload.get("capabilities", ())
    )
    dimensions = tuple(
        CapabilityDimension(
            dimension=str(row["dimension"]),
            state=CapabilityDimensionState(str(row["state"])),
            observed_at=str(row["observed_at"]) if row.get("observed_at") else None,
            evidence_refs=tuple(str(ref) for ref in row.get("evidence_refs", ())),
        )
        for row in payload.get("dimensions", ())
    )
    record = ProviderCapabilityRecord(
        provider_id=str(payload["provider_id"]),
        access_state=CapabilityAccessState(str(payload["access_state"])),
        campaign_role=CampaignRole(str(payload["campaign_role"])),
        support_level=CapabilitySupportLevel(str(payload["support_level"])),
        capabilities=capabilities,
        display_name=str(payload.get("display_name") or ""),
        capability_contract_id=(
            str(payload["capability_contract_id"])
            if payload.get("capability_contract_id")
            else None
        ),
        observed_at=str(payload["observed_at"]) if payload.get("observed_at") else None,
        verification_evidence=tuple(
            str(ref) for ref in payload.get("verification_evidence", ())
        ),
        dimensions=dimensions,
        notes=str(payload.get("notes") or ""),
    )
    validate_provider_record(record)
    return record


def snapshot_from_dict(payload: Mapping[str, Any]) -> CapabilityMatrixSnapshot:
    snapshot = CapabilityMatrixSnapshot(
        observed_at=str(payload["observed_at"]),
        sources=tuple(dict(row) for row in payload.get("sources", ())),
        providers=tuple(
            provider_record_from_dict(row) for row in payload.get("providers", ())
        ),
        schema_version=str(payload.get("schema_version", CAPABILITY_MATRIX_SCHEMA_VERSION)),
        logical_id=str(payload.get("logical_id", CAPABILITY_MATRIX_LOGICAL_ID)),
        secrets_included=bool(payload.get("secrets_included", False)),
    )
    validate_snapshot(snapshot)
    return snapshot
