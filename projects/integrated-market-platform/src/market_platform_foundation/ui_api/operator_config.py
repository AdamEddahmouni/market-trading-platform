"""Value-blind operator configuration metadata and private env writes."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[3]
PRIVATE_ENV = ".private/providers.env"

PROVIDER_FIELDS: tuple[tuple[str, str, tuple[tuple[str, str, bool], ...]], ...] = (
    (
        "finviz",
        "Finviz discovery",
        (("FINVIZ_API_KEY", "Elite API token", True),),
    ),
    (
        "anthropic",
        "Anthropic assistant",
        (
            ("ANTHROPIC_API_KEY", "API key", True),
            ("ANTHROPIC_MODEL", "Model", False),
            ("IMP_ASSISTANT_PROVIDER", "Provider", False),
        ),
    ),
    (
        "news",
        "News providers",
        (("NEWSAPI_API_KEY", "NewsAPI key", True), ("FINNHUB_API_KEY", "Finnhub key", True)),
    ),
    (
        "finra",
        "FINRA short intelligence",
        (("FINRA_CLIENT_ID", "Client ID", False), ("FINRA_CLIENT_SECRET", "Client secret", True)),
    ),
    ("fred", "FRED macro data", (("FRED_API_KEY", "API key", True),)),
    ("eia", "EIA energy data", (("EIA_API_KEY", "API key", True),)),
    (
        "ibkr",
        "IBKR observational",
        (
            ("IBKR_USERNAME", "Username", False),
            ("IBKR_PASSWORD", "Password", True),
            ("IBKR_TOTP_SECRET", "TOTP secret", True),
        ),
    ),
    (
        "tradier",
        "Tradier paper sandbox",
        (("IMP_TRADIER_TOKEN", "Sandbox token", True), ("IMP_TRADIER_ACCOUNT_ID", "Account ID", False)),
    ),
)

_PROVIDER_KEYS = {provider: {field[0] for field in fields} for provider, _, fields in PROVIDER_FIELDS}


def provider_env_path(*, root: Path | None = None) -> Path:
    override = os.environ.get("IMP_PROVIDER_ENV", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (root or REPO_ROOT) / PRIVATE_ENV


def _read_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip():
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_provider_values(provider: str, values: Mapping[str, str], *, path: Path | None = None) -> None:
    allowed = _PROVIDER_KEYS.get(provider)
    if allowed is None:
        raise ValueError("PROVIDER_NOT_SUPPORTED")
    unknown = set(values) - allowed
    if unknown:
        raise ValueError("PROVIDER_FIELD_NOT_ALLOWED")
    for key, value in values.items():
        if not isinstance(value, str) or "\n" in value or "\r" in value:
            raise ValueError(f"INVALID_VALUE:{key}")

    destination = (path or provider_env_path()).resolve()
    existing = destination.read_text(encoding="utf-8") if destination.is_file() else ""
    remaining = {str(key): str(value) for key, value in values.items()}
    output: list[str] = []
    for line in existing.splitlines():
        key, separator, _ = line.partition("=")
        normalized = key.strip()
        if separator and normalized in remaining:
            output.append(f"{normalized}={remaining.pop(normalized)}")
        else:
            output.append(line)
    output.extend(f"{key}={value}" for key, value in remaining.items())
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=str(destination.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(output) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def build_config_payload(
    *,
    path: Path | None = None,
    environment: Mapping[str, str] | None = None,
    environment_path: Path | None = None,
) -> dict[str, Any]:
    values = _read_values((path or provider_env_path()).resolve())
    if environment_path is not None:
        values.update(_read_values(environment_path.resolve()))
    values.update({str(key): str(value) for key, value in (environment or {}).items() if str(value).strip()})
    providers: list[dict[str, Any]] = []
    for provider, label, fields in PROVIDER_FIELDS:
        providers.append(
            {
                "provider": provider,
                "label": label,
                "fields": [
                    {
                        "key": key,
                        "label": field_label,
                        "sensitive": sensitive,
                        "configured": bool(values.get(key, "").strip()),
                    }
                    for key, field_label, sensitive in fields
                ],
            }
        )
    return {
        "schema_version": "operator-config/1.0",
        "providers": providers,
        "secrets_included": False,
    }
