"""Deny-first network and process guard for every Phase 0 entry point."""

from __future__ import annotations

import os
import socket
import sys
from typing import NoReturn

from .errors import OfflineBoundaryViolation

_ACTIVE_LOG: list[dict[str, str]] | None = None
_AUDIT_INSTALLED = False
_SOCKET_PATCHED = False


def _reject(event_category: str) -> NoReturn:
    if _ACTIVE_LOG is not None:
        _ACTIVE_LOG.append(
            {
                "event_category": event_category,
                "reason_code": "PHASE0_OFFLINE_BOUNDARY_DENIAL",
            }
        )
    raise OfflineBoundaryViolation(
        f"prohibited operation denied: {event_category}"
    )


def _reject_socket(*_args: object, **_kwargs: object) -> NoReturn:
    _reject("NETWORK_API")


def _audit_hook(event: str, _args: tuple[object, ...]) -> None:
    if event in {
        "socket.__new__",
        "socket.getaddrinfo",
        "subprocess.Popen",
        "os.system",
    }:
        category = "PROCESS_API" if event in {"subprocess.Popen", "os.system"} else "NETWORK_API"
        _reject(category)


def install_guard(log: list[dict[str, str]]) -> None:
    """Install an idempotent guard and direct sanitized events to *log*."""
    global _ACTIVE_LOG, _AUDIT_INSTALLED, _SOCKET_PATCHED
    _ACTIVE_LOG = log
    if not _AUDIT_INSTALLED:
        sys.addaudithook(_audit_hook)
        _AUDIT_INSTALLED = True
    if not _SOCKET_PATCHED:
        socket.socket = _reject_socket  # type: ignore[assignment]
        socket.create_connection = _reject_socket  # type: ignore[assignment]
        socket.getaddrinfo = _reject_socket  # type: ignore[assignment]
        socket.gethostbyname = _reject_socket  # type: ignore[assignment]
        socket.gethostbyname_ex = _reject_socket  # type: ignore[assignment]
        _SOCKET_PATCHED = True


def run_denial_self_test() -> list[dict[str, str]]:
    """Exercise denials without opening a socket or creating a process."""
    log: list[dict[str, str]] = []
    install_guard(log)
    attempts = (
        lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM),
        lambda: socket.socket(socket.AF_INET6, socket.SOCK_STREAM),
        lambda: socket.getaddrinfo("localhost", 1),
        lambda: socket.gethostbyname("localhost"),
        lambda: os.system("denied"),
    )
    for attempt in attempts:
        try:
            attempt()
        except OfflineBoundaryViolation:
            pass
        else:
            raise AssertionError("offline denial did not occur")
    return log

