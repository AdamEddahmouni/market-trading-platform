"""Production operator runtime: durable outbox, worker gate, dispatcher resolution."""

from __future__ import annotations

import os
from typing import Any

from ...local_state.paths import persistence_enabled
from ...local_state.startup import open_enrichment_outbox
from .dispatcher import EnrichmentDispatcher, resolve_enrichment_dispatcher
from .outbox import EnrichmentOutbox
from .sqlite_outbox import SqliteEnrichmentOutbox
from .worker import EnrichmentOutboxWorker

ENRICHMENT_WORKER_ENV = "IMP_INTELLIGENCE_ENRICHMENT_WORKER"
ENRICHMENT_POLL_INTERVAL_ENV = "IMP_INTELLIGENCE_ENRICHMENT_POLL_SEC"
DEFAULT_ENRICHMENT_POLL_SEC = 1.0


def _env_truthy(name: str) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def enrichment_worker_enabled() -> bool:
    return _env_truthy(ENRICHMENT_WORKER_ENV)


def enrichment_poll_interval_sec() -> float:
    raw = os.environ.get(ENRICHMENT_POLL_INTERVAL_ENV)
    if raw is None:
        return DEFAULT_ENRICHMENT_POLL_SEC
    try:
        parsed = float(raw.strip())
    except ValueError:
        return DEFAULT_ENRICHMENT_POLL_SEC
    return max(0.25, parsed)


def open_sqlite_enrichment_outbox(*, force: bool = False) -> SqliteEnrichmentOutbox | None:
    """Canonical durable outbox backed by the operator local_state database."""

    return open_enrichment_outbox(force=force)


def resolve_warm_path_enrichment_outbox() -> EnrichmentOutbox | None:
    """Durable enqueue plane when persistence is enabled; independent of worker gate."""

    if not persistence_enabled():
        return None
    return open_sqlite_enrichment_outbox()


def build_enrichment_worker(
    outbox: Any,
    *,
    worker_id: str = "enrichment-worker",
    dispatcher: EnrichmentDispatcher | None = None,
) -> EnrichmentOutboxWorker:
    resolved = dispatcher if dispatcher is not None else resolve_enrichment_dispatcher()
    return EnrichmentOutboxWorker(outbox, resolved, worker_id=worker_id)


def worker_status_snapshot(outbox: EnrichmentOutbox | None) -> dict[str, Any]:
    pending = outbox.list_pending() if outbox is not None else ()
    return {
        "worker_enabled": enrichment_worker_enabled(),
        "persistence_enabled": persistence_enabled(),
        "outbox_attached": outbox is not None,
        "pending_request_count": len(pending),
        "poll_interval_sec": enrichment_poll_interval_sec(),
        "dispatcher": resolve_enrichment_dispatcher().__class__.__name__,
    }


__all__ = [
    "DEFAULT_ENRICHMENT_POLL_SEC",
    "ENRICHMENT_POLL_INTERVAL_ENV",
    "ENRICHMENT_WORKER_ENV",
    "build_enrichment_worker",
    "enrichment_poll_interval_sec",
    "enrichment_worker_enabled",
    "open_sqlite_enrichment_outbox",
    "resolve_warm_path_enrichment_outbox",
    "worker_status_snapshot",
]
