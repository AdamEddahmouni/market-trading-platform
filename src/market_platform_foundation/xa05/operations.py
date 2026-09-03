"""XA-05 operator capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from market_platform_foundation.xa04.memory import InMemoryCrossAssetCatalogRepository
from market_platform_foundation.xa04.operations import get_repository, reset_repository_for_tests
from market_platform_foundation.xa04.repository import CrossAssetCatalogRepository

from .audit import audit_matrix
from .contracts import state_to_dict
from .engine import CrossAssetStateEngine, StateConstructionConfig
from .queries import compare_states

CAPABILITY_IDS = frozenset(
    {
        "XA05.OP.STATUS",
        "XA05.OP.VALIDATE",
        "XA05.OP.CONSTRUCT_STATE",
        "XA05.OP.SHOW_STATE",
        "XA05.OP.COMPARE_STATES",
    }
)


@dataclass(frozen=True, slots=True)
class OperationResult:
    outcome_code: str
    capability_id: str
    verification: Mapping[str, Any]


def build_engine(repository: CrossAssetCatalogRepository | None = None) -> CrossAssetStateEngine:
    return CrossAssetStateEngine(repository or get_repository())


def execute(capability_id: str, arguments: Mapping[str, Any] | None = None) -> OperationResult:
    if capability_id not in CAPABILITY_IDS:
        return OperationResult("INVALID", capability_id, {"error": "unknown capability"})
    args = dict(arguments or {})
    if capability_id == "XA05.OP.STATUS":
        return OperationResult(
            "OK",
            capability_id,
            {
                "schema_version": 1,
                "engine_profile": "imp-xa05-state-engine-v1",
                "persistence_mode": "EPHEMERAL_RECONSTRUCTABLE",
                "audit_rows": len(audit_matrix()),
                "paid_infrastructure_required": False,
                "analytical_authority_granted": False,
            },
        )
    if capability_id == "XA05.OP.VALIDATE":
        config = StateConstructionConfig()
        try:
            config.validate()
        except ValueError as exc:
            return OperationResult("INVALID", capability_id, {"error": str(exc)})
        return OperationResult(
            "OK",
            capability_id,
            {
                "classifier_versions": config.classifier_versions(),
                "audit_matrix": audit_matrix(),
            },
        )
    engine = build_engine()
    if capability_id == "XA05.OP.CONSTRUCT_STATE":
        decision_time = str(args.get("decision_time", ""))
        construction_time = str(args.get("construction_time", decision_time))
        config = StateConstructionConfig(
            yield_curve_classifier_version=str(
                args.get("yield_curve_classifier_version", "imp-xa05-yield-curve-v1")
            ),
            policy_rate_classifier_version=str(
                args.get("policy_rate_classifier_version", "imp-xa05-policy-rate-v1")
            ),
            positioning_classifier_version=str(
                args.get("positioning_classifier_version", "imp-xa05-positioning-v1")
            ),
            freshness_classifier_version=str(
                args.get("freshness_classifier_version", "imp-xa05-freshness-v1")
            ),
        )
        state = engine.construct_state(
            decision_time=decision_time,
            construction_time=construction_time,
            config=config,
        )
        return OperationResult("OK", capability_id, state_to_dict(state))
    if capability_id == "XA05.OP.SHOW_STATE":
        cached = args.get("state")
        if isinstance(cached, Mapping):
            return OperationResult("OK", capability_id, dict(cached))
        decision_time = str(args.get("decision_time", ""))
        construction_time = str(args.get("construction_time", decision_time))
        state = engine.construct_state(
            decision_time=decision_time,
            construction_time=construction_time,
        )
        return OperationResult("OK", capability_id, state_to_dict(state))
    if capability_id == "XA05.OP.COMPARE_STATES":
        earlier_time = str(args.get("earlier_decision_time", ""))
        later_time = str(args.get("later_decision_time", ""))
        earlier = engine.construct_state(decision_time=earlier_time, construction_time=earlier_time)
        later = engine.construct_state(decision_time=later_time, construction_time=later_time)
        return OperationResult(
            "OK",
            capability_id,
            compare_states(earlier, later),
        )
    return OperationResult("INVALID", capability_id, {"error": "unhandled capability"})


def reset_engine_for_tests() -> None:
    reset_repository_for_tests()
    from market_platform_foundation.xa04 import operations as xa04_operations

    xa04_operations._DEFAULT_REPOSITORY = InMemoryCrossAssetCatalogRepository()
