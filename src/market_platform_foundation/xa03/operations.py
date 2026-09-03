"""XA-03 operator capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from market_platform_foundation.xa02.contracts import envelope_to_dict, relationship_to_dict
from market_platform_foundation.xa02.registry import get_registry as get_xa02_registry

from .catalog import catalog_rows, admitted_market_definitions
from .fixtures import admit_fixture
from .registry import get_registry, unified_admission_status


CAPABILITY_IDS = frozenset(
    {
        "XA03.OP.STATUS",
        "XA03.OP.VALIDATE",
        "XA03.OP.SHOW_SOURCE",
        "XA03.OP.SHOW_OBSERVATION",
        "XA03.OP.LIST_RELATIONSHIPS",
        "XA03.OP.ADMIT_FIXTURE",
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
    if capability_id == "XA03.OP.STATUS":
        return OperationResult(
            "OK",
            capability_id,
            {
                **unified_admission_status(),
                "pit_capability": True,
                "revision_capability": True,
                "validation_state": "DECLARED",
            },
        )
    if capability_id == "XA03.OP.VALIDATE":
        if not registry.status()["catalog_bootstrapped"]:
            registry.bootstrap_catalog()
        xa02_registry = get_xa02_registry()
        if not xa02_registry.status()["catalog_bootstrapped"]:
            xa02_registry.bootstrap_catalog()
        findings = registry.validate_registry()
        xa02_findings = xa02_registry.validate_registry()
        combined = [*findings, *[dict(item, vertical="fred_rates") for item in xa02_findings]]
        return OperationResult(
            "OK" if not combined else "INVALID",
            capability_id,
            {"findings": combined, **unified_admission_status()},
        )
    if capability_id == "XA03.OP.SHOW_SOURCE":
        market_report_id = str(args.get("market_report_id", ""))
        observations = registry.list_observations_for_market(market_report_id)
        relationships = registry.list_relationships_for_market(market_report_id)
        definition = next(
            (item for item in admitted_market_definitions() if item.market_report_id == market_report_id),
            None,
        )
        return OperationResult(
            "OK" if definition else "INVALID",
            capability_id,
            {
                "market_report_id": market_report_id,
                "cftc_contract_market_code": definition.cftc_contract_market_code if definition else "",
                "report_family": definition.report_family.value if definition else "",
                "position_scope": definition.position_scope.value if definition else "",
                "target_key": definition.target_key if definition else "",
                "observation_count": len(observations),
                "relationship_count": len(relationships),
                "observations": [envelope_to_dict(item) for item in observations],
                "relationships": [relationship_to_dict(item) for item in relationships],
            },
        )
    if capability_id == "XA03.OP.SHOW_OBSERVATION":
        observation_id = str(args.get("observation_id", ""))
        observation = registry.get_observation(observation_id)
        return OperationResult(
            "OK",
            capability_id,
            envelope_to_dict(observation),
        )
    if capability_id == "XA03.OP.LIST_RELATIONSHIPS":
        if not registry.status()["catalog_bootstrapped"]:
            registry.bootstrap_catalog()
        market_report_id = str(args.get("market_report_id", ""))
        target_xa_canonical_id = str(args.get("target_xa_canonical_id", ""))
        if market_report_id:
            relationships = registry.list_relationships_for_market(market_report_id)
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
    if capability_id == "XA03.OP.ADMIT_FIXTURE":
        fixture_name = str(args.get("fixture_name", "positioning_reference_vertical.json"))
        result = admit_fixture(fixture_name=fixture_name, registry=registry)
        return OperationResult("OK", capability_id, result)
    return OperationResult("INVALID", capability_id, {"error": "unhandled capability"})
