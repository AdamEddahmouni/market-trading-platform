"""Shared fixtures for XA-05 strategic state tests."""

from __future__ import annotations

from market_platform_foundation.xa04.adapters import persist_all_registries
from market_platform_foundation.xa04.memory import InMemoryCrossAssetCatalogRepository
from market_platform_foundation.xa04.operations import configure_repository
from market_platform_foundation.xa04.repository import CrossAssetCatalogRepository
from market_platform_foundation.xa05.engine import CrossAssetStateEngine

from tests.xa04.test_xa04_fixtures import build_vertical_slice_state


def populate_repository(
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
    configure_repository(repo)
    return repo, state


def build_engine(
    repository: CrossAssetCatalogRepository | None = None,
) -> CrossAssetStateEngine:
    repo, _state = populate_repository(repository)
    return CrossAssetStateEngine(repo)
