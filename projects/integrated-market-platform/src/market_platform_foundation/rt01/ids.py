"""RT-01 identity generation — distinct from run_id / attempt_id."""

from __future__ import annotations

import uuid


def new_trace_id() -> str:
    return str(uuid.uuid4())


def new_span_id() -> str:
    return str(uuid.uuid4())


def new_correlation_id() -> str:
    return str(uuid.uuid4())


__all__ = ["new_correlation_id", "new_span_id", "new_trace_id"]
