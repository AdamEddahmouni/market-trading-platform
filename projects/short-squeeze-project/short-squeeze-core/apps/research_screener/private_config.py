"""Private credential loader.

Private files are loaded only when the production entry point passes an explicit path.
Importing this module or constructing an application session never reads credentials.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ProviderCredentials:
    values: dict[str, str]
    path: Path | None = None


def load_provider_credentials(path: Path | None = None) -> ProviderCredentials:
    if path is None:
        return ProviderCredentials({})
    path = path.resolve()
    if not path.is_file():
        return ProviderCredentials({}, path)
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and value:
            result[key] = value
    return ProviderCredentials(result, path)


# -- credential status probes (never reveal values) --


def credential_status(credentials: ProviderCredentials | None = None) -> dict[str, str]:
    env = (credentials or ProviderCredentials({})).values
    result: dict[str, str] = {}
    for key in (
        "FINVIZ_API_KEY",
        "NEWSAPI_KEY",
        "FINNHUB_KEY",
        "SCHWAB_APP_KEY",
        "SCHWAB_APP_SECRET",
        "SCHWAB_CALLBACK_URL",
    ):
        result[key] = "CONFIGURED" if env.get(key) else "NOT_CONFIGURED"
    return result


def private_env_path_info(
    credentials: ProviderCredentials | None = None,
) -> dict[str, Any]:
    credentials = credentials or ProviderCredentials({})
    path = credentials.path
    return {
        "path": str(path) if path else None,
        "exists": bool(path and path.is_file()),
        "git_ignored": ".private/ is listed in .gitignore",
        "providers_found": len(credentials.values),
    }


__all__ = [
    "credential_status",
    "load_provider_credentials",
    "private_env_path_info",
    "ProviderCredentials",
]
