"""Attach IntelligenceRepository + production ObservationIngressRouter to ReplayStore."""

from __future__ import annotations

from ..intelligence.observation_ingress.production_wire import (
    build_production_observation_ingress_router,
)
from ..intelligence.persistence.local_state_book import open_local_state_intelligence_repository
from ..local_state.paths import persistence_enabled
from .store import ReplayStore


def _is_live_observational(store: ReplayStore) -> bool:
    return store.data_mode == "LIVE_OBSERVATIONAL" or str(getattr(store, "mode", "")).upper() == "LIVE"


def _apply_durable_book_cursor(store: ReplayStore) -> None:
    """Software book cursor from persisted OpportunityV1. Never a Live receive clock."""

    if _is_live_observational(store) or not persistence_enabled():
        return
    lister = getattr(store.strategy_repository, "list_opportunities", None)
    if not callable(lister):
        return
    created = [int(row.created_at_ns) for row in lister() if getattr(row, "created_at_ns", None) is not None]
    if not created:
        return
    book_ns = max(created)
    if getattr(store, "as_of_time_ns", None) is None:
        store.as_of_time_ns = book_ns
    if getattr(store, "last_source_time_ns", None) is None:
        store.last_source_time_ns = book_ns


def bind_ui_api_intelligence(store: ReplayStore) -> ReplayStore:
    """Wire canonical persistence and ingress used by news observational admit paths.

    Ranked opportunities use the serving IntelligenceRepository: local_state SQLite
    (same family as operator acks) when persist is on; otherwise process-local
    ``INTENTIONAL_EPHEMERAL`` memory. Mongo is not this serving composition.
    Non-live persist-on reuses persisted ``created_at_ns`` as the software book
    cursor so ranked readback survives restart. Live observational as_of stays
    the receive clock (or ``UNAVAILABLE``) — never this cursor.
    """

    if store.strategy_repository is None:
        store.strategy_repository = open_local_state_intelligence_repository()
    _apply_durable_book_cursor(store)
    if getattr(store, "observation_ingress_router", None) is None:
        store.observation_ingress_router = build_production_observation_ingress_router(
            store.strategy_repository
        )
    return store


__all__ = ["bind_ui_api_intelligence"]
