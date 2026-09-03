"""Live FRED transport wiring from environment."""

from __future__ import annotations

import os
from pathlib import Path

from .transport import FredHttpTransport

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
from .v1_client import FredV1Client
from .v2_client import FredV2Client


def load_api_key() -> str:
    key = os.environ.get("FRED_API_KEY", "").strip()
    if not key:
        env_path = _REPOSITORY_ROOT / ".env"
        if env_path.is_file():
            with env_path.open(encoding="utf-8") as handle:
                for line in handle:
                    if line.strip().startswith("FRED_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    return key


def api_key_present() -> bool:
    return bool(load_api_key())


def live_enabled() -> bool:
    return os.environ.get("IMP_FRED_LIVE") == "1" and api_key_present()


def transport_from_env() -> tuple[FredV1Client, FredV2Client]:
    key = load_api_key()
    if not key:
        raise RuntimeError("FRED_API_KEY unavailable")
    transport = FredHttpTransport()
    return FredV1Client(api_key=key, transport=transport), FredV2Client(api_key=key, transport=transport)


__all__ = ["api_key_present", "live_enabled", "load_api_key", "transport_from_env"]
