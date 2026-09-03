"""Wall-clock nanoseconds that never stall within a process (shared infrastructure).

``time.time_ns()`` (the wall clock) can freeze for whole ticks in virtualized
environments or return coarse-grained values. That previously produced
identical session ids for back-to-back ledger opens, duplicate event
timestamps, identity-hash collisions in the audit store, and a busy-wait
deadline that never expired. ``monotonic_wall_ns()`` returns the wall clock
when it advances and ``last + 1`` when it does not, so successive calls within
one process are strictly increasing while still tracking wall time whenever it
moves.

This is the single guarded source of wall-clock nanoseconds for every
identity/time-sensitive call site in the project: identity hashes, event
timestamps, point-in-time defaults, staleness checks, and deadlines. Sites that
only write informational metadata (``observed``/``tested_at`` strings) are
deliberately left on the raw clock — see ``docs/engineering/CLOCK.md``.

Cross-process uniqueness is a separate concern: identity bodies that need it
carry an explicit ``uuid4`` nonce (e.g. paper session ids). This module removes
the in-process tie problem at the source.
"""

from __future__ import annotations

import time

_last_wall_ns: int = 0


def monotonic_wall_ns() -> int:
    """Strictly increasing wall-clock nanoseconds within this process.

    If the underlying wall clock has not advanced since the previous call
    (frozen or coarse tick), return the previous value plus one so callers
    never observe duplicate timestamps while the clock is stalled.
    """
    global _last_wall_ns
    now = time.time_ns()
    if now <= _last_wall_ns:
        now = _last_wall_ns + 1
    _last_wall_ns = now
    return now


def reset_clock_for_tests() -> None:
    """Reset the per-process clock guard (test isolation only)."""
    global _last_wall_ns
    _last_wall_ns = 0


__all__ = ["monotonic_wall_ns", "reset_clock_for_tests"]
