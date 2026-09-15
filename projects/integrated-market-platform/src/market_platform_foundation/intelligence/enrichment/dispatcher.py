"""Optional outbound dispatch boundary — no provider network logic in IMP core."""

from __future__ import annotations

import os
from typing import Any, Protocol, runtime_checkable

from .contracts import EnrichmentRequestV1

ENRICHMENT_DISPATCHER_ENV = "IMP_INTELLIGENCE_ENRICHMENT_DISPATCHER"


@runtime_checkable
class EnrichmentDispatcher(Protocol):
    """External worker bridge (Grok runner, queue publisher, etc.)."""

    def dispatch(self, request: EnrichmentRequestV1) -> None: ...


class NoOpEnrichmentDispatcher:
    """Default: core product works with no Grok connection."""

    def dispatch(self, request: EnrichmentRequestV1) -> None:
        return None


class RecordingEnrichmentDispatcher:
    """Test/diagnostic dispatcher that records payloads without network I/O."""

    def __init__(self) -> None:
        self.dispatched: list[dict[str, Any]] = []

    def dispatch(self, request: EnrichmentRequestV1) -> None:
        from .contracts import enrichment_request_v1_to_dict

        self.dispatched.append(enrichment_request_v1_to_dict(request))


def resolve_enrichment_dispatcher() -> EnrichmentDispatcher:
    """Provider-neutral dispatcher; default NOOP (no external routing)."""

    raw = (os.environ.get(ENRICHMENT_DISPATCHER_ENV) or "").strip().lower()
    if raw in {"", "noop", "disabled", "off"}:
        return NoOpEnrichmentDispatcher()
    if raw in {"recording", "record"}:
        return RecordingEnrichmentDispatcher()
    raise ValueError("ENRICHMENT_DISPATCHER_UNSUPPORTED")


def flush_outbox_to_dispatcher(
    outbox: Any,
    dispatcher: EnrichmentDispatcher,
    *,
    now_ns: int | None = None,
) -> int:
    """Warm-path drain via worker claim/dispatch (does not block opportunity surface)."""

    from .schedule_clock import resolve_outbox_schedule_now_ns
    from .worker import EnrichmentOutboxWorker

    worker = EnrichmentOutboxWorker(outbox, dispatcher)
    return worker.drain(now_ns=resolve_outbox_schedule_now_ns(outbox, now_ns))


__all__ = [
    "ENRICHMENT_DISPATCHER_ENV",
    "EnrichmentDispatcher",
    "NoOpEnrichmentDispatcher",
    "RecordingEnrichmentDispatcher",
    "flush_outbox_to_dispatcher",
    "resolve_enrichment_dispatcher",
]
