"""XA-02 operator capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .catalog import catalog_rows
from .contracts import observation_to_dict, relationship_to_dict
from .fixtures import admit_fixture
from .registry import get_registry


CAPABILITY_IDS = frozenset(
    {
        "XA02.OP.STATUS",
        "XA02.OP.VALIDATE",
        "XA02.OP.SHOW_INDICATOR",
        "XA02.OP.LIST_RELATIONSHIPS",
        "XA02.OP.ADMIT_FIXTURE",
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
    if capability_id == "XA02.OP.STATUS":
        status = registry.status()
        return OperationResult(
            "OK",
            capability_id,
            {
                **status,
                "schema_version": 1,
                "source_classification": "FIXTURE_OR_ADMITTED",
            },
        )
    if capability_id == "XA02.OP.VALIDATE":
        if not registry.status()["catalog_bootstrapped"]:
            registry.bootstrap_catalog()
        findings = registry.validate_registry()
        return OperationResult(
            "OK" if not findings else "INVALID",
            capability_id,
            {"findings": findings, **registry.status()},
        )
    if capability_id == "XA02.OP.SHOW_INDICATOR":
        canonical_indicator_id = str(args.get("canonical_indicator_id", ""))
        summary = registry.indicator_summary(canonical_indicator_id)
        observations = registry.list_observations_for_indicator(canonical_indicator_id)
        relationships = registry.list_relationships_for_indicator(canonical_indicator_id)
        return OperationResult(
            "OK",
            capability_id,
            {
                "canonical_indicator_id": summary.canonical_indicator_id,
                "provider_series_id": summary.provider_series_id,
                "title": summary.title,
                "units": summary.units,
                "observation_count": summary.observation_count,
                "relationship_count": summary.relationship_count,
                "revision_classifications": [item.value for item in summary.revision_classifications],
                "observations": [observation_to_dict(item) for item in observations],
                "relationships": [relationship_to_dict(item) for item in relationships],
            },
        )
    if capability_id == "XA02.OP.LIST_RELATIONSHIPS":
        if not registry.status()["catalog_bootstrapped"]:
            registry.bootstrap_catalog()
        canonical_indicator_id = str(args.get("canonical_indicator_id", ""))
        target_xa_canonical_id = str(args.get("target_xa_canonical_id", ""))
        if canonical_indicator_id:
            relationships = registry.list_relationships_for_indicator(canonical_indicator_id)
        elif target_xa_canonical_id:
            relationships = registry.list_relationships_for_target(target_xa_canonical_id)
        else:
            relationships = registry.list_all_relationships()
        return OperationResult(
            "OK",
            capability_id,
            {
                "relationships": [relationship_to_dict(item) for item in relationships],
                "catalog": catalog_rows(),
            },
        )
    if capability_id == "XA02.OP.ADMIT_FIXTURE":
        fixture_name = str(args.get("fixture_name", "rates_reference_vertical.json"))
        result = admit_fixture(fixture_name=fixture_name, registry=registry)
        return OperationResult("OK", capability_id, result)
    return OperationResult("INVALID", capability_id, {"error": "unhandled capability"})
