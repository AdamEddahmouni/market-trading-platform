"""FINRA client-id load and annual-rotation health. The secret itself is never inspected."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ..short_intelligence.contracts import CredentialHealthState

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV_PATH = REPOSITORY_ROOT / ".env"
DEFAULT_SECRET_TTL_DAYS = 365
DUE_DAYS = 30
URGENT_DAYS = 7


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_local_env(path: Path | None = None) -> None:
    """Populate process env from local .env without overwriting existing values."""
    for key, value in _parse_env_file(path or DEFAULT_ENV_PATH).items():
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True, slots=True)
class FinraCredentials:
    client_id: str
    client_secret: str
    secret_rotated_at: str
    secret_expires_at: str

    def present(self) -> bool:
        return bool(self.client_id and self.client_secret)


def load_finra_credentials(*, env_path: Path | None = None) -> FinraCredentials:
    load_local_env(env_path)
    return FinraCredentials(
        client_id=os.environ.get("FINRA_CLIENT_ID", "").strip(),
        client_secret=os.environ.get("FINRA_CLIENT_SECRET", "").strip(),
        secret_rotated_at=os.environ.get("FINRA_SECRET_ROTATED_AT", "").strip(),
        secret_expires_at=os.environ.get("FINRA_SECRET_EXPIRES_AT", "").strip(),
    )


def _parse_date(value: str) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def resolve_expiry(credentials: FinraCredentials) -> date | None:
    explicit = _parse_date(credentials.secret_expires_at)
    if explicit is not None:
        return explicit
    rotated = _parse_date(credentials.secret_rotated_at)
    if rotated is None:
        return None
    return rotated + timedelta(days=DEFAULT_SECRET_TTL_DAYS)


def credential_health(
    credentials: FinraCredentials,
    *,
    today: date | None = None,
    auth_failed: bool = False,
) -> CredentialHealthState:
    if auth_failed:
        return CredentialHealthState.AUTH_FAILED
    expiry = resolve_expiry(credentials)
    if expiry is None:
        return CredentialHealthState.UNKNOWN
    current = today or datetime.now(timezone.utc).date()
    remaining = (expiry - current).days
    if remaining < 0:
        return CredentialHealthState.EXPIRED
    if remaining <= URGENT_DAYS:
        return CredentialHealthState.ROTATION_URGENT
    if remaining <= DUE_DAYS:
        return CredentialHealthState.ROTATION_DUE
    return CredentialHealthState.HEALTHY


def rotation_alert(state: CredentialHealthState, *, days_remaining: int | None) -> str:
    if state == CredentialHealthState.EXPIRED:
        return "FINRA credential expired"
    if state == CredentialHealthState.ROTATION_URGENT:
        return "FINRA credential expires in 7 days"
    if state == CredentialHealthState.ROTATION_DUE:
        return "FINRA credential expires in 30 days"
    if days_remaining is not None and days_remaining <= DUE_DAYS:
        return f"FINRA credential expires in {days_remaining} days"
    return ""
