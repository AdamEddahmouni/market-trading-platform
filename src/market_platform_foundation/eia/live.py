"""Live EIA transport wiring from environment."""

from __future__ import annotations

import os
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def load_api_key() -> str:
    key = os.environ.get("EIA_API_KEY", "").strip()
    if not key:
        env_path = _REPOSITORY_ROOT / ".env"
        if env_path.is_file():
            with env_path.open(encoding="utf-8") as handle:
                for line in handle:
                    if line.strip().startswith("EIA_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    return key


def api_key_present() -> bool:
    return bool(load_api_key())


def live_enabled() -> bool:
    return os.environ.get("IMP_EIA_LIVE") == "1" and api_key_present()


__all__ = ["api_key_present", "live_enabled", "load_api_key"]
