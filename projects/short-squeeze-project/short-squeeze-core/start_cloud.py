#!/usr/bin/env python3
"""START CLOUD — full cloud deployment, zero local deps.

The single authoritative entry point for running the Short Squeeze Research
Screener in a cloud environment (Railway, Docker, any container platform).

Usage
-----
    python start_cloud.py                           (PORT from env or 8787)
    python start_cloud.py --port 9090
    python start_cloud.py --check
    python start_cloud.py --verbose
    python start_cloud.py --load-local-providers    (local dev: preload .private/providers.env)

What it does
------------
  1. Reads provider credentials from environment variables
     (``FINVIZ_API_KEY``, ``NEWSAPI_KEY``, ``FINNHUB_KEY``, ``IBKR_*``, etc.)
  2. By default does NOT load ``.private/providers.env`` (platform secrets only)
  3. ``--load-local-providers`` preloads the repository private provider file into
     ``os.environ`` for local CLOUD_PROVIDER_MODE soak tests
  4. Never probes a local IB Gateway unless ``IBKR_ENABLED=true`` and
     ``IBKR_HOST`` / ``IBKR_PORT`` / ``IBKR_CLIENT_ID`` are set (remote gateway)
  5. Uses ``FROZEN_DEMO`` research data packaged in the deployment image
  6. Starts the HTTP server on ``0.0.0.0:<PORT>`` (all interfaces)
  7. No browser — this is headless by design

Safe for Railway, Fly.io, Render, or any container platform.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

# ── Repository root (file-based; never rely on CWD) ────────────────────
_repo = Path(__file__).resolve().parent

from apps.research_screener.credentials import (  # noqa: E402
    default_private_path,
    load_private_env,
)
from apps.research_screener.__main__ import main as _launch  # noqa: E402


def _prepare_cloud_environment() -> None:
    """Entry-point side effects: repo-root cwd and cloud mode.

    Kept out of module scope so importing :mod:`start_cloud` (e.g. from tests)
    never mutates the process environment or working directory.
    """
    os.chdir(_repo)
    if str(_repo) not in sys.path:
        sys.path.insert(0, str(_repo))
    os.environ.setdefault("SQUEEZE_APP_MODE", "CLOUD_PROVIDER_MODE")


def _boolean_env(name: str, default: str) -> None:
    if not os.environ.get(name):
        os.environ[name] = default


def _preload_local_providers() -> Path | None:
    """Load private provider credentials into os.environ for local cloud soak."""
    path = default_private_path()
    if path is None or not path.is_file():
        print("  start_cloud: --load-local-providers set but no private provider file found")
        return None
    loaded = load_private_env(path, verbose=True)
    if not loaded:
        print(f"  start_cloud: no keys loaded from {path}")
        return None
    _boolean_env("FINVIZ_ENABLED", "true")
    _boolean_env("NEWSAPI_ENABLED", "true")
    _boolean_env("FINNHUB_ENABLED", "true")
    _boolean_env("SEC_ENABLED", "true")
    os.environ.setdefault("IBKR_ENABLED", "false")
    os.environ.setdefault("FINVIZ_AUTO_REFRESH", "true")
    print(f"  start_cloud: loaded local providers from {path}")
    return path


def _build_cli_args(argv: list[str]) -> tuple[list[str], bool]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--load-local-providers", action="store_true")
    known, remaining = parser.parse_known_args(argv)
    load_local = bool(known.load_local_providers) or os.environ.get(
        "SQUEEZE_CLOUD_LOAD_LOCAL_PROVIDERS", ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    return remaining, load_local


if __name__ == "__main__":
    _prepare_cloud_environment()
    remaining_argv, load_local = _build_cli_args(sys.argv[1:])
    private_path: Path | None = None
    suppress_path: str | None = None

    if load_local:
        private_path = _preload_local_providers()
    else:
        _suppress = tempfile.NamedTemporaryFile(
            prefix="cloud-no-private-", suffix=".env", delete=False,
        )
        _suppress.close()
        suppress_path = _suppress.name

    _cli_args = ["--mode", "CLOUD_PROVIDER_MODE", "--no-browser"]
    if suppress_path is not None:
        _cli_args.extend(["--provider-config", suppress_path])
    elif private_path is not None:
        _cli_args.extend(["--provider-config", str(private_path)])
    _cli_args.extend(remaining_argv)

    try:
        sys.exit(_launch(_cli_args))
    finally:
        if suppress_path is not None:
            os.unlink(suppress_path)
