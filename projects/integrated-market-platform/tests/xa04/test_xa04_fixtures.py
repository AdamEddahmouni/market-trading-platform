"""Shared fixtures for XA-04 persistence tests."""

from __future__ import annotations

from market_platform_foundation.xa01.compatibility import register_future_family
from market_platform_foundation.xa01.registry import InstrumentRegistry, reset_registry_for_tests as reset_xa01
from market_platform_foundation.xa02.fixtures import admit_fixture as admit_xa02_fixture
from market_platform_foundation.xa02.registry import AdmissionRegistry, reset_registry_for_tests as reset_xa02
from market_platform_foundation.xa03.fixtures import admit_fixture as admit_xa03_fixture
from market_platform_foundation.xa03.registry import PositioningAdmissionRegistry, reset_registry_for_tests as reset_xa03

from market_platform_foundation.xa04.adapters import persist_all_registries
from market_platform_foundation.xa04.memory import InMemoryCrossAssetCatalogRepository
from market_platform_foundation.xa04.repository import CrossAssetCatalogRepository


def reset_all_registries() -> None:
    reset_xa01()
    reset_xa02()
    reset_xa03()


def build_vertical_slice_state(
    *,
    xa01_registry: InstrumentRegistry | None = None,
    xa02_registry: AdmissionRegistry | None = None,
    xa03_registry: PositioningAdmissionRegistry | None = None,
) -> dict[str, object]:
    reset_all_registries()
    xa01 = xa01_registry or InstrumentRegistry()
    xa02 = xa02_registry or AdmissionRegistry(xa_registry=xa01)
    xa03 = xa03_registry or PositioningAdmissionRegistry(xa_registry=xa01)
    gc_id = register_future_family(family_root="GC", registry=xa01)
    xa02.bootstrap_catalog()
    xa03.bootstrap_catalog()
    fred = admit_xa02_fixture(fixture_name="rates_reference_vertical.json", registry=xa02)
    cftc = admit_xa03_fixture(fixture_name="legacy_futures_only_gc.json", registry=xa03)
    return {
        "gc_canonical_id": gc_id,
        "fred": fred,
        "cftc": cftc,
        "xa01_registry": xa01,
        "xa02_registry": xa02,
        "xa03_registry": xa03,
    }


def populate_vertical_slice_repository(
    repository: CrossAssetCatalogRepository | None = None,
) -> tuple[CrossAssetCatalogRepository, dict[str, object]]:
    state = build_vertical_slice_state()
    repo = repository or InMemoryCrossAssetCatalogRepository()
    persist_all_registries(
        repo,
        xa01_registry=state["xa01_registry"],  # type: ignore[arg-type]
        xa02_registry=state["xa02_registry"],  # type: ignore[arg-type]
        xa03_registry=state["xa03_registry"],  # type: ignore[arg-type]
    )
    return repo, state
