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

What it does
------------
  1. Reads provider credentials ONLY from environment variables
     (``FINVIZ_API_KEY``, ``NEWSAPI_KEY``, ``FINNHUB_KEY``, ``IBKR_*``, etc.)
  2. Does NOT load any local file — ``.private/providers.env`` is suppressed
  3. Never probes a local IB Gateway unless ``IBKR_ENABLED=true`` and
     ``IBKR_HOST`` / ``IBKR_PORT`` / ``IBKR_CLIENT_ID`` are set (remote gateway)
  4. Uses ``FROZEN_DEMO`` research data packaged in the deployment image
  5. Starts the HTTP server on ``0.0.0.0:<PORT>`` (all interfaces)
  6. No browser — this is headless by design

Safe for Railway, Fly.io, Render, or any container platform.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# ── Ensure we are in the repository root ──────────────────────────────
_repo = Path(__file__).resolve().parent
os.chdir(_repo)
if str(_repo) not in sys.path:
    sys.path.insert(0, str(_repo))

# ── Set cloud mode ───────────────────────────────────────────────────
# Cloud mode reads credentials exclusively from environment variables.
# The auto-detected .private/providers.env is suppressed by passing an
# explicit --provider-config pointing to an empty temp file. This is more
# portable than os.devnull ('nul' on Windows), whose is_file() behavior
# varies across Python and Windows versions.
os.environ.setdefault("SQUEEZE_APP_MODE", "CLOUD_PROVIDER_MODE")

# ── Delegate to canonical launcher with explicit cloud args ──────────
from apps.research_screener.__main__ import main as _launch

if __name__ == "__main__":
    # Create an empty temp file to suppress .private/providers.env auto-detect.
    _suppress = tempfile.NamedTemporaryFile(
        prefix="cloud-no-private-", suffix=".env", delete=False,
    )
    _suppress.close()

    _cli_args = [
        "--mode", "CLOUD_PROVIDER_MODE",
        "--no-browser",
        "--provider-config", _suppress.name,
    ] + sys.argv[1:]

    try:
        sys.exit(_launch(_cli_args))
    finally:
        os.unlink(_suppress.name)
