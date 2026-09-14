"""Optional outbound dispatch boundary — no provider network logic in IMP core."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .contracts import EnrichmentRequestV1


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


def flush_outbox_to_dispatcher(
    outbox: Any,
    dispatcher: EnrichmentDispatcher,
) -> int:
    """Warm-path drain: dispatch pending rows without blocking opportunity surface."""

    pending = outbox.list_pending()
    for request in pending:
        dispatcher.dispatch(request)
        if hasattr(outbox, "mark_dispatched"):
            outbox.mark_dispatched(request.request_id)
    return len(pending)


__all__ = [
    "EnrichmentDispatcher",
    "NoOpEnrichmentDispatcher",
    "RecordingEnrichmentDispatcher",
    "flush_outbox_to_dispatcher",
]
