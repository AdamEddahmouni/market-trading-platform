"""Attach IntelligenceRepository + production ObservationIngressRouter to ReplayStore."""

from __future__ import annotations

from ..intelligence.observation_ingress.production_wire import (
    build_production_observation_ingress_router,
)
from ..intelligence.persistence import InMemoryIntelligenceRepository
from .store import ReplayStore


def bind_ui_api_intelligence(store: ReplayStore) -> ReplayStore:
    """Wire canonical persistence and ingress used by news observational admit paths."""

    if store.strategy_repository is None:
        store.strategy_repository = InMemoryIntelligenceRepository()
    if getattr(store, "observation_ingress_router", None) is None:
        store.observation_ingress_router = build_production_observation_ingress_router(
            store.strategy_repository
        )
    return store


__all__ = ["bind_ui_api_intelligence"]
