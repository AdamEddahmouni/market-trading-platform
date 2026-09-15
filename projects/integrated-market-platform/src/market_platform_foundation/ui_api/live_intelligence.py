"""Bind IntelligenceRepository + production ingress onto the UI API ReplayStore."""

from __future__ import annotations

from ..intelligence.observation_ingress.production_wire import (
    build_production_observation_ingress_router,
)
from ..intelligence.persistence import InMemoryIntelligenceRepository
from .store import ReplayStore


def bind_ui_api_intelligence(store: ReplayStore) -> ReplayStore:
    """Attach observational ranked-read persistence to the UI API process.

    Necessary for EventV1 ``put_event`` in this process. Not sufficient for a
    live ranked book: P12 showed today's ``UNAVAILABLE`` was the
    ``_is_live`` request-path gate *before* ``build_ranked_rows``. Moomoo quotes
    remain ``ObservationalStateStore``, not EventV1. Does not fetch providers,
    start enrichment, or enable Live execution.
    """

    if store.strategy_repository is None:
        store.strategy_repository = InMemoryIntelligenceRepository()
    if getattr(store, "observation_ingress_router", None) is None:
        store.observation_ingress_router = build_production_observation_ingress_router(
            store.strategy_repository
        )
    return store


__all__ = ["bind_ui_api_intelligence"]
