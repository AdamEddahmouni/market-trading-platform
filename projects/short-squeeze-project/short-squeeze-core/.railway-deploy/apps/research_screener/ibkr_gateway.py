"""Reusable IB Gateway Docker container lifecycle.

Provides port auto-detection (ExposedPorts + CMD/ENTRYPOINT), a user-level
port cache, Docker availability checks, and the full pull/run/wait/stop
lifecycle for the IBKR Gateway container.

Both ``start_local.py`` and future programmatic launchers import from this
module instead of duplicating the lifecycle code.

Usage
-----
    from apps.research_screener.ibkr_gateway import ensure_ibkr_docker

    port = ensure_ibkr_docker(
        image="ghcr.io/gnzsnz/ib-gateway:stable",
        trade_mode="paper",
        host_port=4002,
        container_port=None,          # auto-detect
        user_id=creds["IBKR_USER_ID"],
        password=creds["IBKR_PASSWORD"],
        extra_env=["VNC_PASSWORD=secret"],
    )
    # → port 4002 is now listening on the host
"""

from __future__ import annotations

import atexit
import json
import socket
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

__all__ = [
    "CONTAINER_NAME",
    "DEFAULT_BASE_IMAGE",
    "API_PORT_CANDIDATES",
    "DEFAULT_CONTAINER_PORTS",
    "ContainerStartError",
    "resolve_gateway_image",
    "preferred_port",
    "ports_from_exposed",
    "ports_from_cmd",
    "detect_container_api_port",
    "read_port_cache",
    "write_port_cache",
    "docker_available",
    "container_running",
    "container_exists",
    "wait_for_gateway",
    "ensure_ibkr_docker",
]

# ── Constants ─────────────────────────────────────────────────────────

CONTAINER_NAME = "short-squeeze-ib-gateway"
"""Name assigned to the Gateway Docker container."""

DEFAULT_BASE_IMAGE = "ghcr.io/gnzsnz/ib-gateway"
"""Default image repository (tag appended at resolution time)."""

# Ports known to serve the IBKR API across popular Docker images.
API_PORT_CANDIDATES = frozenset({4001, 4002, 4003, 4004, 7496, 7497, 8888})
VNC_PORT_CANDIDATES = frozenset({5900, 5901})
DEFAULT_CONTAINER_PORTS: dict[str, int] = {"paper": 4004, "live": 4003}

CACHE_FILE = "ib-gateway-port.json"
"""Filename inside ``~/.short-squeeze/`` that caches the detected port."""


class ContainerStartError(RuntimeError):
    """Raised when the Gateway container fails to start or become ready."""


# ── Image resolution ──────────────────────────────────────────────────

def resolve_gateway_image(
    *,
    explicit_image: str | None = None,
    private_image: str | None = None,
    tag_override: str | None = None,
) -> str:
    """Resolve the full Gateway image reference with precedence.

    Precedence (highest → lowest):

    1. ``explicit_image`` (``--docker-image`` CLI flag)
    2. ``private_image`` (``IBKR_DOCKER_IMAGE`` from private file)
    3. ``tag_override`` + default base
    4. ``:stable`` on the default base
    """
    image = explicit_image or private_image
    if image is None:
        tag = tag_override or "stable"
        image = DEFAULT_BASE_IMAGE + ":" + tag
    return image


# ── Port detection ────────────────────────────────────────────────────

def preferred_port(ports: set[int], trade_mode: str) -> int | None:
    """Return the best port from *ports* for the given *trade_mode*.

    Preference order:
      paper → 4004, 4002, then lowest remaining
      live  → 4003, 4001, then lowest remaining
    """
    if trade_mode == "paper":
        for pref in (4004, 4002):
            if pref in ports:
                return pref
    else:
        for pref in (4003, 4001):
            if pref in ports:
                return pref
    return min(ports) if ports else None


def ports_from_exposed(exposed: dict[str, object]) -> set[int]:
    """Parse an ``ExposedPorts`` dict into a set of integer TCP ports.

    Keys look like ``"4003/tcp": {}``.  VNC ports are excluded.
    """
    ports: set[int] = set()
    for key in exposed:
        port_str, _, proto = key.partition("/")
        if proto and proto != "tcp":
            continue
        try:
            port = int(port_str)
        except ValueError:
            continue
        if port in VNC_PORT_CANDIDATES:
            continue
        if port in API_PORT_CANDIDATES:
            ports.add(port)
    return ports


def ports_from_cmd(cmd: Sequence[str]) -> set[int]:
    """Scan a CMD or ENTRYPOINT array for ``--port`` / ``-p`` arguments.

    Looks for elements like ``--port=4004``, ``--port 4004``, ``-p 4004``
    and returns any that match known API port candidates.
    """
    ports: set[int] = set()
    tokens = list(cmd)
    for i, token in enumerate(tokens):
        if token.startswith("--port="):
            _, _, val = token.partition("=")
            try:
                p = int(val)
                if p in API_PORT_CANDIDATES:
                    ports.add(p)
            except ValueError:
                pass
        elif token in ("--port", "-p") and i + 1 < len(tokens):
            try:
                p = int(tokens[i + 1])
                if p in API_PORT_CANDIDATES:
                    ports.add(p)
            except ValueError:
                pass
    return ports


def detect_container_api_port(image: str, trade_mode: str) -> int | None:
    """Inspect a Docker image's metadata to discover the IBKR API port.

    Uses two strategies in order of reliability:

    1. **ExposedPorts** — reads ``.Config.ExposedPorts`` from ``docker image
       inspect``; the most authoritative source.

    2. **CMD / ENTRYPOINT** — parses the startup command array for
       ``--port=<N>``, ``--port <N>``, or ``-p <N>`` arguments.  Catches
       images that accept the API port as a runtime argument.

    Returns the detected port or ``None`` if neither strategy finds a match.
    """
    try:
        r = subprocess.run(
            [
                "docker", "image", "inspect", image,
                "--format", "{{json .Config}}",
            ],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return None
        config: dict[str, object] | None = json.loads(r.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError):
        return None

    if not isinstance(config, dict):
        return None

    # Strategy 1: ExposedPorts
    exposed = config.get("ExposedPorts")
    if isinstance(exposed, dict):
        ports = ports_from_exposed(exposed)
        if ports:
            result = preferred_port(ports, trade_mode)
            print(f"    (detected via ExposedPorts: {sorted(ports)})")
            return result

    # Strategy 2: CMD / ENTRYPOINT
    candidates: set[int] = set()
    cmd = config.get("Cmd")
    if isinstance(cmd, list):
        candidates |= ports_from_cmd(cmd)
    entrypoint = config.get("Entrypoint")
    if isinstance(entrypoint, list):
        candidates |= ports_from_cmd(entrypoint)

    if candidates:
        result = preferred_port(candidates, trade_mode)
        print(f"    (detected via CMD/ENTRYPOINT: {sorted(candidates)})")
        return result
    return None


# ── Port cache ────────────────────────────────────────────────────────

def _port_cache_path() -> Path:
    """Return the path to the port-detection cache JSON file.

    Resolved lazily to avoid ``Path.home()`` raising in headless environments.
    """
    return Path.home() / ".short-squeeze" / CACHE_FILE


def read_port_cache(image: str, trade_mode: str) -> int | None:
    """Return a cached container port for ``(image, trade_mode)`` or ``None``."""
    path = _port_cache_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("image") != image or data.get("trade_mode") != trade_mode:
        return None
    port = data.get("port")
    return int(port) if isinstance(port, (int, str)) else None


def write_port_cache(image: str, trade_mode: str, port: int) -> None:
    """Persist the detected port so future startups skip inspection."""
    try:
        cache_dir = Path.home() / ".short-squeeze"
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / CACHE_FILE).write_text(
            json.dumps({"image": image, "trade_mode": trade_mode, "port": port}),
            encoding="utf-8",
        )
    except OSError:
        pass  # cache is best-effort; failure should never block startup


# ── Docker checks ─────────────────────────────────────────────────────

def docker_available() -> bool:
    """Return ``True`` if ``docker`` is on ``PATH`` and the daemon is running."""
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return False


def container_running(name: str = CONTAINER_NAME) -> bool:
    """Return ``True`` if a container with *name* is currently running."""
    r = subprocess.run(
        ["docker", "ps", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=10,
    )
    return name in r.stdout.strip().splitlines()


def container_exists(name: str = CONTAINER_NAME) -> bool:
    """Return ``True`` if a container with *name* exists (any state)."""
    r = subprocess.run(
        ["docker", "ps", "-a", "--filter", f"name=^{name}$", "--format", "{{.Names}}"],
        capture_output=True, text=True, timeout=10,
    )
    return name in r.stdout.strip().splitlines()


# ── Lifecycle ─────────────────────────────────────────────────────────

def wait_for_gateway(port: int, timeout: int = 120, *, name: str = CONTAINER_NAME) -> None:
    """Poll ``127.0.0.1:<port>`` until it accepts TCP connections.

    Raises :exc:`ContainerStartError` on timeout.
    """
    print(f"  Waiting for Gateway (:{port}) ...", end="", flush=True)
    deadline = time.monotonic() + timeout
    logged = 0
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                print(" READY")
                return
        except (ConnectionRefusedError, OSError):
            elapsed = int(time.monotonic() - (deadline - timeout))
            if elapsed >= logged + 10:
                print(f" {elapsed}s", end="", flush=True)
                logged = elapsed
            time.sleep(1)
    print(f" TIMEOUT after {timeout}s")
    raise ContainerStartError(
        f"Gateway did not become ready. Check logs: docker logs {name}"
    )


def ensure_ibkr_docker(
    *,
    image: str,
    trade_mode: str,
    host_port: int,
    container_port: int | None = None,
    user_id: str,
    password: str,
    extra_env: Sequence[str] = (),
    name: str = CONTAINER_NAME,
) -> int:
    """Start the IB Gateway via Docker and return *host_port*.

    Parameters
    ----------
    image
        Full Docker image reference (e.g. ``ghcr.io/gnzsnz/ib-gateway:stable``).
    trade_mode
        ``"paper"`` or ``"live"``.
    host_port
        Host-side port to expose.
    container_port
        Container-internal API port.  When ``None``, auto-detects from the image
        metadata (with a best-effort user-level cache).
    user_id
        IBKR account username (``TWS_USERID``).
    password
        IBKR account password (``TWS_PASSWORD``).
    extra_env
        Extra ``KEY=VALUE`` pairs to pass as ``-e`` to ``docker run``.
    name
        Docker container name.

    Returns
    -------
    int
        The *host_port* (now listening).

    Raises
    ------
    ContainerStartError
        If Docker is unavailable, credentials are missing, or the container
        fails to start.
    """
    if not docker_available():
        raise ContainerStartError(
            "Docker is not available.  Install Docker Desktop or "
            "start the Docker daemon."
        )

    if trade_mode not in ("paper", "live"):
        raise ContainerStartError(
            f"trade_mode must be 'paper' or 'live', got {trade_mode!r}"
        )
    if not user_id or not password:
        raise ContainerStartError(
            "IBKR_USER_ID and IBKR_PASSWORD are required"
        )

    # ── Already running? ──────────────────────────────────────────
    if container_running(name):
        print(f"  IB Gateway container '{name}' already running.")
        return host_port

    # ── Remove stale container ────────────────────────────────────
    if container_exists(name):
        print(f"  Removing stale container '{name}'...")
        subprocess.run(
            ["docker", "rm", "-f", name],
            capture_output=True, timeout=20, check=False,
        )

    # ── Pull ──────────────────────────────────────────────────────
    print(f"  Pulling {image} ...")
    subprocess.run(
        ["docker", "pull", image],
        capture_output=True, timeout=120,
    )

    # ── Auto-detect container API port ────────────────────────────
    if container_port is None:
        cached = read_port_cache(image, trade_mode)
        if cached is not None:
            container_port = cached
            print(f"  Using cached API port {container_port} for {image.split('/')[-1]}")
        else:
            detected = detect_container_api_port(image, trade_mode)
            if detected is not None:
                container_port = detected
                print(f"  Detected API port {container_port} from image {image.split('/')[-1]}")
                write_port_cache(image, trade_mode, container_port)
            else:
                container_port = DEFAULT_CONTAINER_PORTS[trade_mode]
                print(
                    f"  Could not detect API port from image; using default {container_port}."
                )

    # ── Run ───────────────────────────────────────────────────────
    cmd = [
        "docker", "run", "-d",
        "--name", name,
        "--rm",
        "-p", f"127.0.0.1:{host_port}:{container_port}",
        "-e", f"TWS_USERID={user_id}",
        "-e", f"TWS_PASSWORD={password}",
        "-e", f"TRADING_MODE={trade_mode}",
        "-e", "TWS_ACCEPT_INCOMING=accept",
        "-e", "READ_ONLY_API=yes",
    ]
    for pair in extra_env:
        cmd.extend(["-e", pair])
    cmd.append(image)

    print(f"  Starting IB Gateway ({trade_mode}) on 127.0.0.1:{host_port} ...")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    if r.returncode != 0:
        stderr = r.stderr.strip()
        raise ContainerStartError(stderr or "(no stderr)")

    container_id = r.stdout.strip()[:12]
    print(f"  Container {container_id} started.")

    # ── Wait for socket readiness ─────────────────────────────────
    wait_for_gateway(host_port, name=name)

    # Register cleanup
    def _stop() -> None:
        if container_running(name):
            print(f"\n  Stopping IB Gateway container '{name}' ...")
            subprocess.run(
                ["docker", "stop", name],
                capture_output=True, timeout=30, check=False,
            )

    atexit.register(_stop)
    return host_port
