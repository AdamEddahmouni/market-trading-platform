#!/usr/bin/env python3
"""START LOCAL — full local deployment, zero cloud.

The single authoritative entry point for running the Short Squeeze Research
Screener entirely on your local machine.

Usage
-----
    python start_local.py                           (port 8787, opens browser)
    python start_local.py --port 9090               (custom port)
    python start_local.py --profile                 (auto-start IB Gateway via Docker)
    python start_local.py --no-browser              (headless)
    python start_local.py --private-path /path/to/providers.env
    python start_local.py --check                   (print status and exit)
    python start_local.py --doctor                  (print credential report and exit)
    python start_local.py --clear-cache             (remove port cache and exit)
    python start_local.py --profile --detect-only   (detect port and exit)

``--profile``
    Starts an IB Gateway Docker container before launching the server, so the
    entire local setup is truly one command. Requires Docker Desktop and IBKR
    credentials set in your environment or ``.private/providers.env``:

    .. code-block:: ini

        IBKR_USER_ID=your_username
        IBKR_PASSWORD=your_password
        IBKR_TRADE_MODE=paper             # or "live"
        IBKR_DOCKER_IMAGE=ghcr.io/gnzsnz/ib-gateway:stable   # default

    The container is stopped when the screener exits.

What it does
------------
  1. Loads private provider credentials from ``.private/providers.env``
  2. (Optional) Starts IB Gateway via Docker for market-data access
  3. Probes local IBKR Gateway for market-data readiness
  4. Starts the HTTP server on ``127.0.0.1`` (localhost only — never exposed)
  5. Opens your browser to ``http://127.0.0.1:<port>/``

No cloud services, no Railway — just your machine and your providers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ── Ensure we are in the repository root ──────────────────────────────
import os as _os
_repo = Path(__file__).resolve().parent
_os.chdir(_repo)
sys.path.insert(0, str(_repo))

# ── Parse our own flags before delegating ─────────────────────────────
_parser = argparse.ArgumentParser(
    prog="start_local",
    description="Short Squeeze Research Screener — local deployment",
    add_help=False,  # we pass remaining args to __main__
)
_parser.add_argument(
    "--profile",
    action="store_true",
    help="auto-start IB Gateway via Docker before launching",
)
_parser.add_argument(
    "--private-path",
    type=Path,
    default=None,
    dest="private_path",
    help="explicit path to private provider configuration file",
)
_parser.add_argument(
    "--clear-cache",
    action="store_true",
    dest="clear_cache",
    help="remove the IB Gateway port detection cache (~/.short-squeeze/) and exit",
)
_parser.add_argument(
    "--doctor",
    action="store_true",
    help="print credential/provider status report and exit",
)
_parser.add_argument(
    "--detect-only",
    action="store_true",
    dest="detect_only",
    help="(with --profile) detect the Gateway API port and exit without starting the container",
)
_parser.add_argument(
    "--docker-image",
    default=None,
    help="Docker image for IB Gateway (default: $IBKR_DOCKER_IMAGE or ghcr.io/gnzsnz/ib-gateway:stable)",
)
_parser.add_argument(
    "--docker-image-tag",
    default=None,
    help="override the tag on the default gateway image (e.g. --docker-image-tag nightly)",
)
_parser.add_argument(
    "--docker-paper-port",
    type=int,
    default=4002,
    help="host port (exposed) for paper-trading gateway (default: 4002)",
)
_parser.add_argument(
    "--docker-live-port",
    type=int,
    default=4001,
    help="host port (exposed) for live-trading gateway (default: 4001)",
)
_parser.add_argument(
    "--docker-container-paper-port",
    type=int,
    default=None,
    help="container-internal API port for paper trading (default: auto-detect from image)",
)
_parser.add_argument(
    "--docker-container-live-port",
    type=int,
    default=None,
    help="container-internal API port for live trading (default: auto-detect from image)",
)
_parser.add_argument(
    "--docker-image-env",
    action="append",
    default=[],
    dest="docker_image_env",
    metavar="KEY=VALUE",
    help="extra environment variable for the Gateway container (may be repeated)",
)

# Partition: consume our flags; pass everything else through to __main__.
_own, _passthru = _parser.parse_known_args()

# If --private-path was passed, translate it to --provider-config for __main__
if _own.private_path is not None:
    _passthru = ["--provider-config", str(_own.private_path)] + _passthru

# ══════════════════════════════════════════════════════════════════════
#  Standalone actions (exit before loading app)
# ══════════════════════════════════════════════════════════════════════

# --clear-cache: delete the port detection cache file
if _own.clear_cache:
    _cp = Path.home() / ".short-squeeze" / "ib-gateway-port.json"
    if _cp.is_file():
        _cp.unlink()
        print(f"  Removed port cache: {_cp}")
    else:
        print("  Port cache does not exist.")
    sys.exit(0)

# --doctor: delegate to the config doctor subcommand
if _own.doctor:
    from apps.research_screener.config import main as _doctor_main  # noqa: E402
    sys.exit(_doctor_main(["doctor"]))

# ── Load private credentials into environment ────────────────────────
from apps.research_screener.credentials import load_private_env  # noqa: E402

print("  Private credentials loaded:")
_private_creds = load_private_env(verbose=True)


# ══════════════════════════════════════════════════════════════════════
#  Docker IB Gateway lifecycle  (delegated to ibkr_gateway module)
# ══════════════════════════════════════════════════════════════════════

from apps.research_screener.ibkr_gateway import (  # noqa: E402
    ContainerStartError,
    DEFAULT_CONTAINER_PORTS,
    detect_container_api_port,
    ensure_ibkr_docker,
    read_port_cache,
    resolve_gateway_image,
)


def _profile_up() -> None:
    """Resolve config, start the Gateway container, and return the host port."""
    trade_mode = _private_creds.get("IBKR_TRADE_MODE", "paper").lower()
    image = resolve_gateway_image(
        explicit_image=_own.docker_image,
        private_image=_private_creds.get("IBKR_DOCKER_IMAGE"),
        tag_override=_own.docker_image_tag,
    )
    print(f"  Resolved gateway image: {image}")
    host_port = _own.docker_paper_port if trade_mode == "paper" else _own.docker_live_port
    explicit_port = (
        _own.docker_container_paper_port
        if trade_mode == "paper"
        else _own.docker_container_live_port
    )

    if _own.detect_only:
        # Detect-only mode: just print the port and exit
        container_port = explicit_port
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
                else:
                    container_port = DEFAULT_CONTAINER_PORTS[trade_mode]
                    print(f"  Could not detect API port; using default {container_port}.")
        print(f"\n  API port: {container_port}  (host port: {host_port})")
        sys.exit(0)

    try:
        ensure_ibkr_docker(
            image=image,
            trade_mode=trade_mode,
            host_port=host_port,
            container_port=explicit_port,
            user_id=_private_creds.get("IBKR_USER_ID", ""),
            password=_private_creds.get("IBKR_PASSWORD", ""),
            extra_env=_own.docker_image_env,
        )
    except ContainerStartError as exc:
        print(f"  ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if _own.profile:
    _profile_up()


# ── Delegate to the canonical launcher ───────────────────────────────
from apps.research_screener.__main__ import main as _launch  # noqa: E402

if __name__ == "__main__":
    sys.exit(_launch(_passthru))
