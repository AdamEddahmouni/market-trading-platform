"""Loopback service probes: port bound vs HTTP alive vs process identity."""

from __future__ import annotations

import os
import socket
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from typing import Callable, Mapping, Sequence


@dataclass(frozen=True)
class ServiceHealthSnapshot:
    port_bound: bool
    http_alive: bool | None
    process_alive: bool
    identity_owned: bool

    def as_dict(self) -> dict[str, bool | None]:
        return asdict(self)

    @property
    def process_healthy(self) -> bool:
        """Launcher-owned process is alive and still matches recorded identity."""
        return self.process_alive and self.identity_owned

    @property
    def http_ready(self) -> bool:
        if self.http_alive is None:
            return self.port_bound
        return bool(self.http_alive)


def process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, int(pid))
        if not handle:
            return False
        exit_code = ctypes.c_ulong()
        still_active = 259
        try:
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return int(exit_code.value) == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def probe_port_bound(host: str, port: int, *, timeout_seconds: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def probe_http_alive(url: str, *, timeout_seconds: float = 1.0) -> bool:
    request = urllib.request.Request(url, headers={"User-Agent": "imp-service-health/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return 200 <= int(response.status) < 500
    except (OSError, urllib.error.URLError, ValueError):
        return False


def identity_owned(
    pid: int,
    identity: Sequence[str],
    *,
    command_line: Callable[[int], str | None],
    identity_matches: Callable[[str | None, Sequence[str]], bool],
) -> bool:
    if not process_alive(pid):
        return False
    return identity_matches(command_line(pid), identity)


def evaluate_service_health(
    *,
    pid: int,
    host: str,
    port: int,
    http_url: str | None,
    identity: Sequence[str],
    command_line: Callable[[int], str | None],
    identity_matches: Callable[[str | None, Sequence[str]], bool],
    port_is_open: Callable[[str, int], bool] | None = None,
    http_timeout_seconds: float = 1.0,
    process_alive_fn: Callable[[int], bool] | None = None,
    http_probe: Callable[[str], bool] | None = None,
) -> ServiceHealthSnapshot:
    alive = process_alive_fn(pid) if process_alive_fn is not None else process_alive(pid)
    port_bound = port_is_open(host, port) if port_is_open is not None else probe_port_bound(host, port)
    owned = (
        identity_matches(command_line(pid), identity)
        if alive
        else False
    )
    http_alive: bool | None
    if http_url is None:
        http_alive = None
    elif not port_bound:
        http_alive = False
    elif http_probe is not None:
        http_alive = http_probe(http_url)
    else:
        http_alive = probe_http_alive(http_url, timeout_seconds=http_timeout_seconds)
    return ServiceHealthSnapshot(
        port_bound=port_bound,
        http_alive=http_alive,
        process_alive=alive,
        identity_owned=owned,
    )


_REQUIRED_PLATFORM_SERVICES = ("api", "ui", "control")


def aggregate_platform_health(services: Mapping[str, ServiceHealthSnapshot]) -> str:
    if not services:
        return "STOPPED"
    if not all(name in services for name in _REQUIRED_PLATFORM_SERVICES):
        return "PARTIAL"
    if all(services[name].process_healthy and services[name].http_ready for name in _REQUIRED_PLATFORM_SERVICES):
        return "READY"
    return "PARTIAL"
