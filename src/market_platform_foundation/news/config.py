"""Configuration for read-only NewsAPI and Finnhub access."""

from __future__ import annotations

import os
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
NEWSAPI_URL = "https://newsapi.org/v2/everything"
FINNHUB_URL = "https://finnhub.io/api/v1/company-news"
PLACEHOLDERS = frozenset({"", "CHANGEME", "EXAMPLE", "PLACEHOLDER", "NOT_A_SECRET"})


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return values
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _runtime_values() -> dict[str, str]:
    values = _read_env_file(REPO_ROOT / ".env")
    provider_path = os.environ.get("IMP_PROVIDER_ENV", "").strip()
    if provider_path:
        values.update(_read_env_file(Path(provider_path).expanduser()))
    else:
        values.update(_read_env_file(REPO_ROOT / ".private" / "providers.env"))
    values.update({str(key): str(value) for key, value in os.environ.items()})
    return values


def _configured(name: str) -> str | None:
    value = _runtime_values().get(name, "").strip()
    return value if value.upper() not in PLACEHOLDERS else None


def newsapi_api_key() -> str | None:
    return _configured("NEWSAPI_API_KEY") or _configured("NEWSAPI_KEY")


def finnhub_api_key() -> str | None:
    return _configured("FINNHUB_API_KEY")


def _gate_enabled(name: str) -> bool:
    return _runtime_values().get(name, "").strip().lower() in {"1", "true", "yes"}


def newsapi_live_enabled() -> bool:
    return _gate_enabled("IMP_NEWSAPI_LIVE")


def finnhub_live_enabled() -> bool:
    return _gate_enabled("IMP_FINNHUB_LIVE")


__all__ = [
    "FINNHUB_URL",
    "NEWSAPI_URL",
    "finnhub_api_key",
    "finnhub_live_enabled",
    "newsapi_api_key",
    "newsapi_live_enabled",
]
