"""Frozen connection, pacing, and timeout policy for the collection tool."""

from __future__ import annotations

# Localhost only -- the tool never connects anywhere else.
HOST = "127.0.0.1"

# Probe order: common IB Gateway paper then live socket ports. The successful port is
# recorded as observed configuration, never as an account-mode determination.
# Paper/live native Gateway ports first, then common Docker image mappings.
PORT_PROBE_ORDER: tuple[int, ...] = (4002, 4001, 4004, 4003)

# Deterministic, high, nonzero client ID reserved for this project, with a fixed
# fallback sequence. Never 0.
CLIENT_ID_PRIMARY = 27185
CLIENT_ID_FALLBACKS: tuple[int, ...] = (27186, 27187, 27188)
CLIENT_ID_SEQUENCE: tuple[int, ...] = (CLIENT_ID_PRIMARY, *CLIENT_ID_FALLBACKS)

# Timeouts (seconds).
CONNECTION_TIMEOUT_S = 15
CONNECTION_PING_TIMEOUT_S = 5
RECONNECT_ATTEMPTS = 3
RECONNECT_BACKOFF_S = 2
CONTRACT_DETAILS_TIMEOUT_S = 30
HISTORICAL_TIMEOUT_S = 60

# Pacing (seconds).
INTER_REQUEST_DELAY_S = 2
IDENTICAL_REQUEST_MIN_INTERVAL_S = 15
RETRY_BACKOFF_S = 20
MAX_TRANSIENT_RETRIES = 1


def assert_localhost(host: str) -> None:
    """Guard: refuse any non-localhost host."""
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError(f"refusing non-localhost connection to {host!r}")


__all__ = [
    "HOST",
    "PORT_PROBE_ORDER",
    "CLIENT_ID_PRIMARY",
    "CLIENT_ID_FALLBACKS",
    "CLIENT_ID_SEQUENCE",
    "CONNECTION_TIMEOUT_S",
    "CONNECTION_PING_TIMEOUT_S",
    "RECONNECT_ATTEMPTS",
    "RECONNECT_BACKOFF_S",
    "CONTRACT_DETAILS_TIMEOUT_S",
    "HISTORICAL_TIMEOUT_S",
    "INTER_REQUEST_DELAY_S",
    "IDENTICAL_REQUEST_MIN_INTERVAL_S",
    "RETRY_BACKOFF_S",
    "MAX_TRANSIENT_RETRIES",
    "assert_localhost",
]
