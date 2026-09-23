"""Optional ambient binding for latency instrumentation (unbound path skips stamps)."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    from .collector import LatencyInstrumentationCollector

_collector_var: ContextVar[LatencyInstrumentationCollector | None] = ContextVar(
    "imp_latency_instrumentation_v1_collector",
    default=None,
)

STORE_ATTR = "latency_instrumentation_collector"


def current_latency_collector() -> LatencyInstrumentationCollector | None:
    return _collector_var.get()


def resolve_latency_collector(store: Any | None = None) -> LatencyInstrumentationCollector | None:
    bound = _collector_var.get()
    if bound is not None:
        return bound
    if store is None:
        return None
    candidate = getattr(store, STORE_ATTR, None)
    return candidate if candidate is not None else None


@contextmanager
def bind_latency_collector(collector: LatencyInstrumentationCollector | None) -> Iterator[None]:
    token: Token = _collector_var.set(collector)
    try:
        yield
    finally:
        _collector_var.reset(token)


__all__ = [
    "STORE_ATTR",
    "bind_latency_collector",
    "current_latency_collector",
    "resolve_latency_collector",
]
