"""Register UI API ReplayStore and admit FTEP prospective ingress into the same cockpit plane."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping

from ..intelligence.paper_forward_bridge.ftep_prospective_catalyst_ingress import (
    ProspectiveCatalystIngressResult,
)
from ..news.observational_admit import admit_prospective_catalyst_ingress_result
from ..news.observational_opportunity import observational_news_opportunity_id
from .live_intelligence import bind_ui_api_intelligence
from .store import TRACKED_ASSISTANT_AUDIT_ROOT, ReplayStore

_registered_cockpit_store: ReplayStore | None = None


def register_cockpit_replay_store(store: ReplayStore) -> ReplayStore:
    """Bind the in-process UI API store for FTEP / ops admit convergence."""

    global _registered_cockpit_store
    _registered_cockpit_store = store
    return store


def get_registered_cockpit_replay_store() -> ReplayStore | None:
    return _registered_cockpit_store


def reset_registered_cockpit_replay_store_for_tests() -> None:
    global _registered_cockpit_store
    _registered_cockpit_store = None


def resolve_imp_collection_root(repository_root: Path) -> Path:
    """Monorepo collection root that ``ReplayStore.load()`` expects."""

    from ..intelligence.paper_forward_bridge.ftep_catalyst_watch import (
        operator_primary_imp_root_for_evidence,
    )

    imp_root = operator_primary_imp_root_for_evidence(repository_root)
    project = imp_root if imp_root is not None else repository_root
    if (project / "phase0-dependency-lock.json").is_file():
        return project.parent
    return repository_root


def load_cockpit_replay_store(*, collection_root: Path) -> ReplayStore:
    store = ReplayStore(
        collection_root=collection_root,
        assistant_audit_root=TRACKED_ASSISTANT_AUDIT_ROOT,
    )
    store.load()
    bind_ui_api_intelligence(store)
    if os.environ.get("IMP_LIVE_OBSERVATIONAL") == "1":
        store.data_mode = "LIVE_OBSERVATIONAL"
        store.mode = "LIVE"
    register_cockpit_replay_store(store)
    return store


def admit_prospective_catalyst_ingress_into_cockpit(
    ingress: ProspectiveCatalystIngressResult | Mapping[str, Any],
    *,
    collection_root: Path,
) -> dict[str, Any]:
    """Admit #207 prospective rows through the production ingress router (unattended wire)."""

    store = get_registered_cockpit_replay_store()
    if store is None:
        store = load_cockpit_replay_store(collection_root=collection_root)
    bind_ui_api_intelligence(store)
    router = getattr(store, "observation_ingress_router", None)
    if router is None:
        return {
            "admitted_count": 0,
            "opportunity_count": 0,
            "skipped_count": 0,
            "reason": "COCKPIT_INGRESS_ROUTER_UNAVAILABLE",
        }
    if isinstance(ingress, ProspectiveCatalystIngressResult):
        if not ingress.ready:
            return {
                "admitted_count": 0,
                "opportunity_count": 0,
                "skipped_count": 0,
                "reason": str(ingress.reason or ingress.classification or "INGRESS_NOT_READY"),
            }
    outcomes = admit_prospective_catalyst_ingress_result(ingress, router=router, store=store)
    repository = getattr(store, "strategy_repository", None)
    getter = getattr(repository, "get_opportunity", None)
    admitted = 0
    opportunity_ids: list[str] = []
    skipped = 0
    for outcome in outcomes:
        if not outcome.accepted or outcome.event is None:
            skipped += 1
            continue
        admitted += 1
        if callable(getter):
            opp_id = observational_news_opportunity_id(outcome.event.event_id)
            if getter(opp_id) is not None:
                opportunity_ids.append(opp_id)
    return {
        "admitted_count": admitted,
        "opportunity_count": len(opportunity_ids),
        "skipped_count": skipped,
        "opportunity_ids": opportunity_ids,
        "live_authority": False,
        "auto_fetch": False,
        "news_event_build09": "INACTIVE",
    }


__all__ = [
    "admit_prospective_catalyst_ingress_into_cockpit",
    "get_registered_cockpit_replay_store",
    "load_cockpit_replay_store",
    "register_cockpit_replay_store",
    "reset_registered_cockpit_replay_store_for_tests",
    "resolve_imp_collection_root",
]
