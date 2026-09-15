"""Independent worker boundary: claim → dispatch → delivery state transitions."""

from __future__ import annotations

from typing import Any

from .delivery import DEFAULT_RETRY_POLICY, EnrichmentRetryPolicy
from .dispatcher import EnrichmentDispatcher


class EnrichmentOutboxWorker:
    def __init__(
        self,
        outbox: Any,
        dispatcher: EnrichmentDispatcher,
        *,
        worker_id: str = "enrichment-worker",
        policy: EnrichmentRetryPolicy = DEFAULT_RETRY_POLICY,
    ) -> None:
        self._outbox = outbox
        self._dispatcher = dispatcher
        self._worker_id = worker_id
        self._policy = policy

    def run_once(self, *, now_ns: int | None = None) -> bool:
        from .schedule_clock import resolve_outbox_schedule_now_ns

        clock_ns = resolve_outbox_schedule_now_ns(self._outbox, now_ns)
        if hasattr(self._outbox, "sweep_expired"):
            self._outbox.sweep_expired(clock_ns)
        if hasattr(self._outbox, "release_expired_claims"):
            self._outbox.release_expired_claims(clock_ns)
        request = None
        if hasattr(self._outbox, "claim_next"):
            request = self._outbox.claim_next(
                self._worker_id,
                now_ns=clock_ns,
                lease_duration_ns=self._policy.claim_lease_ns,
            )
        if request is None:
            return False
        try:
            self._dispatcher.dispatch(request)
            self._outbox.mark_dispatched(request.request_id, at_ns=clock_ns)
        except Exception as exc:  # noqa: BLE001 — bounded retry boundary
            if hasattr(self._outbox, "record_dispatch_failure"):
                self._outbox.record_dispatch_failure(
                    request.request_id,
                    str(exc),
                    now_ns=clock_ns,
                    policy=self._policy,
                )
            else:
                raise
        return True

    def drain(self, *, max_iterations: int = 256, now_ns: int | None = None) -> int:
        from .schedule_clock import resolve_outbox_schedule_now_ns

        clock_ns = resolve_outbox_schedule_now_ns(self._outbox, now_ns)
        processed = 0
        for _ in range(max_iterations):
            if not self.run_once(now_ns=clock_ns):
                break
            processed += 1
        return processed


__all__ = ["EnrichmentOutboxWorker"]
