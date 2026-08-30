"""XA-04 operator capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from market_platform_foundation.xa01.registry import get_registry as get_xa01_registry, reset_registry_for_tests as reset_xa01
from market_platform_foundation.xa02.registry import get_registry as get_xa02_registry, reset_registry_for_tests as reset_xa02
from market_platform_foundation.xa03.registry import get_registry as get_xa03_registry, reset_registry_for_tests as reset_xa03

from .audit import audit_matrix
from .memory import InMemoryCrossAssetCatalogRepository
from .repository import CrossAssetCatalogRepository

CAPABILITY_IDS = frozenset(
    {
        "XA04.OP.STATUS",
        "XA04.OP.VALIDATE",
        "XA04.OP.SHOW_RECORD",
        "XA04.OP.LIST_CATALOG",
    }
)

_DEFAULT_REPOSITORY: CrossAssetCatalogRepository | None = None


@dataclass(frozen=True, slots=True)
class OperationResult:
    outcome_code: str
    capability_id: str
    verification: Mapping[str, Any]


def get_repository() -> CrossAssetCatalogRepository:
    global _DEFAULT_REPOSITORY
    if _DEFAULT_REPOSITORY is None:
        _DEFAULT_REPOSITORY = InMemoryCrossAssetCatalogRepository()
    return _DEFAULT_REPOSITORY


def configure_repository(repository: CrossAssetCatalogRepository) -> None:
    global _DEFAULT_REPOSITORY
    _DEFAULT_REPOSITORY = repository


def reset_repository_for_tests() -> None:
    global _DEFAULT_REPOSITORY
    _DEFAULT_REPOSITORY = InMemoryCrossAssetCatalogRepository()
    reset_xa01()
    reset_xa02()
    reset_xa03()


def _catalog_counts(repository: CrossAssetCatalogRepository) -> dict[str, int]:
    health = repository.check_health()
    counts = dict(health.get("collection_counts", {}))
    if not counts:
        counts = {
            "xa_instruments": len(repository.list_instrument_ids()),
        }
    return counts


def execute(capability_id: str, arguments: Mapping[str, Any] | None = None) -> OperationResult:
    if capability_id not in CAPABILITY_IDS:
        return OperationResult("INVALID", capability_id, {"error": "unknown capability"})
    args = dict(arguments or {})
    repository = get_repository()
    if capability_id == "XA04.OP.STATUS":
        health = repository.check_health()
        return OperationResult(
            "OK",
            capability_id,
            {
                "schema_version": 1,
                "backend": health.get("backend"),
                "available": health.get("available"),
                "collection_counts": _catalog_counts(repository),
                "audit_rows": len(audit_matrix()),
                "paid_mongodb_required": False,
            },
        )
    if capability_id == "XA04.OP.VALIDATE":
        findings: list[dict[str, str]] = []
        xa01 = get_xa01_registry()
        xa02 = get_xa02_registry()
        xa03 = get_xa03_registry()
        findings.extend({"code": item["code"], "vertical": "xa01"} for item in xa01.validate_registry())
        if not xa02.status()["catalog_bootstrapped"]:
            xa02.bootstrap_catalog()
        if not xa03.status()["catalog_bootstrapped"]:
            xa03.bootstrap_catalog()
        findings.extend({"code": item["code"], "vertical": "fred_rates"} for item in xa02.validate_registry())
        findings.extend({"code": item["code"], "vertical": "cftc_positioning"} for item in xa03.validate_registry())
        health = repository.check_health()
        return OperationResult(
            "OK" if not findings else "INVALID",
            capability_id,
            {
                "findings": findings,
                "repository_health": health,
                "collection_counts": _catalog_counts(repository),
            },
        )
    if capability_id == "XA04.OP.SHOW_RECORD":
        record_kind = str(args.get("record_kind", ""))
        record_id = str(args.get("record_id", ""))
        if record_kind == "instrument":
            record = repository.get_instrument(record_id)
            payload = {"record_kind": record_kind, "record": record}
        elif record_kind == "scalar_observation":
            record = repository.get_scalar_observation(record_id)
            payload = {"record_kind": record_kind, "record": record}
        elif record_kind == "admission_envelope":
            record = repository.get_admission_envelope(record_id)
            payload = {"record_kind": record_kind, "record": record}
        elif record_kind == "cross_asset_relationship":
            record = repository.get_cross_asset_relationship(record_id)
            payload = {"record_kind": record_kind, "record": record}
        else:
            return OperationResult("INVALID", capability_id, {"error": "unknown record_kind"})
        if record is None:
            return OperationResult("INVALID", capability_id, {"error": "record_not_found", **payload})
        return OperationResult("OK", capability_id, payload)
    if capability_id == "XA04.OP.LIST_CATALOG":
        return OperationResult(
            "OK",
            capability_id,
            {
                "instrument_ids": repository.list_instrument_ids(),
                "audit_matrix": audit_matrix(),
                "collection_counts": _catalog_counts(repository),
            },
        )
    return OperationResult("INVALID", capability_id, {"error": "unhandled capability"})
