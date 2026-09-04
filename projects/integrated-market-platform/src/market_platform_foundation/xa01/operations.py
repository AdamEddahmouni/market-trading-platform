"""XA-01 operator capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .contracts import record_to_dict
from .enums import AnalyticalDomain, ExternalIdentifierType
from .registry import get_registry
from .resolver import resolve_alias


CAPABILITY_IDS = frozenset(
    {
        "XA01.OP.STATUS",
        "XA01.OP.RESOLVE",
        "XA01.OP.SHOW_INSTRUMENT",
        "XA01.OP.LIST_DOMAINS",
        "XA01.OP.VALIDATE_REGISTRY",
    }
)


@dataclass(frozen=True, slots=True)
class OperationResult:
    outcome_code: str
    capability_id: str
    verification: Mapping[str, Any]


def execute(capability_id: str, arguments: Mapping[str, Any] | None = None) -> OperationResult:
    if capability_id not in CAPABILITY_IDS:
        return OperationResult("INVALID", capability_id, {"error": "unknown capability"})
    args = dict(arguments or {})
    registry = get_registry()
    if capability_id == "XA01.OP.STATUS":
        return OperationResult(
            "OK",
            capability_id,
            {
                "instrument_count": len(registry.list_ids()),
                "schema_version": 1,
            },
        )
    if capability_id == "XA01.OP.LIST_DOMAINS":
        return OperationResult(
            "OK",
            capability_id,
            {"domains": [item.value for item in AnalyticalDomain]},
        )
    if capability_id == "XA01.OP.VALIDATE_REGISTRY":
        findings = registry.validate_registry()
        return OperationResult(
            "OK" if not findings else "INVALID",
            capability_id,
            {"findings": findings, "instrument_count": len(registry.list_ids())},
        )
    if capability_id == "XA01.OP.RESOLVE":
        result = resolve_alias(
            provider_id=str(args.get("provider_id", "")),
            alias_value=str(args.get("alias_value", "")),
            identifier_type=ExternalIdentifierType(
                str(args.get("identifier_type", ExternalIdentifierType.PROVIDER_SYMBOL.value))
            ),
            registry=registry,
            as_of=str(args.get("as_of", "")),
        )
        return OperationResult(
            "OK" if result.status.value == "RESOLVED" else "INVALID",
            capability_id,
            {
                "status": result.status.value,
                "canonical_id": result.canonical_id,
                "provider_id": result.provider_id,
                "alias_value": result.alias_value,
                "quality_flags": list(result.quality_flags),
            },
        )
    if capability_id == "XA01.OP.SHOW_INSTRUMENT":
        canonical_id = str(args.get("canonical_id", ""))
        record = registry.get(canonical_id)
        return OperationResult("OK", capability_id, record_to_dict(record))
    return OperationResult("INVALID", capability_id, {"error": "unhandled capability"})
