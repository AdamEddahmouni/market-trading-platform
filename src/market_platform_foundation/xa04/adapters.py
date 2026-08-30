"""Adapters between XA registries and durable catalog repository (IMP-XA-04)."""

from __future__ import annotations

from market_platform_foundation.xa01.registry import InstrumentRegistry
from market_platform_foundation.xa02.registry import AdmissionRegistry
from market_platform_foundation.xa03.registry import PositioningAdmissionRegistry

from .repository import CrossAssetCatalogRepository, RepositoryPutResult


def persist_instrument_registry(
    repository: CrossAssetCatalogRepository,
    registry: InstrumentRegistry,
) -> dict[str, int]:
    inserted = 0
    already_present = 0
    for canonical_id in registry.list_ids():
        record = registry.get(canonical_id)
        result = repository.put_instrument(record)
        if result == RepositoryPutResult.INSERTED:
            inserted += 1
        else:
            already_present += 1
    return {"inserted": inserted, "already_present": already_present}


def persist_admission_registry(
    repository: CrossAssetCatalogRepository,
    registry: AdmissionRegistry,
) -> dict[str, int]:
    inserted = 0
    already_present = 0
    for relationship in registry.list_all_relationships():
        result = repository.put_cross_asset_relationship(relationship)
        if result == RepositoryPutResult.INSERTED:
            inserted += 1
        else:
            already_present += 1
    with registry._lock:  # noqa: SLF001
        observations = list(registry._observations.values())  # noqa: SLF001
    for observation in observations:
        result = repository.put_scalar_observation(observation)
        if result == RepositoryPutResult.INSERTED:
            inserted += 1
        else:
            already_present += 1
    return {"inserted": inserted, "already_present": already_present}


def persist_positioning_registry(
    repository: CrossAssetCatalogRepository,
    registry: PositioningAdmissionRegistry,
) -> dict[str, int]:
    inserted = 0
    already_present = 0
    for relationship in registry.list_all_relationships():
        result = repository.put_cross_asset_relationship(relationship)
        if result == RepositoryPutResult.INSERTED:
            inserted += 1
        else:
            already_present += 1
    with registry._lock:  # noqa: SLF001
        market_ids = sorted(registry._market_index.keys())  # noqa: SLF001
    for market_id in market_ids:
        for envelope in registry.list_observations_for_market(market_id):
            result = repository.put_admission_envelope(envelope)
            if result == RepositoryPutResult.INSERTED:
                inserted += 1
            else:
                already_present += 1
    return {"inserted": inserted, "already_present": already_present}


def persist_all_registries(
    repository: CrossAssetCatalogRepository,
    *,
    xa01_registry: InstrumentRegistry,
    xa02_registry: AdmissionRegistry,
    xa03_registry: PositioningAdmissionRegistry,
) -> dict[str, dict[str, int]]:
    return {
        "instruments": persist_instrument_registry(repository, xa01_registry),
        "fred_admission": persist_admission_registry(repository, xa02_registry),
        "cftc_admission": persist_positioning_registry(repository, xa03_registry),
    }


def hydrate_instrument_registry(
    repository: CrossAssetCatalogRepository,
    registry: InstrumentRegistry,
) -> int:
    count = 0
    for canonical_id in repository.list_instrument_ids():
        record = repository.get_instrument(canonical_id)
        if record is None:
            continue
        registry.register_descriptor(record.descriptor)
        if record.analytical_domains:
            registry.add_domains(canonical_id, record.analytical_domains)
        for alias in record.aliases:
            registry.add_alias(canonical_id, alias)
        for relationship in record.relationships:
            registry.add_relationship(relationship)
        count += 1
    return count
