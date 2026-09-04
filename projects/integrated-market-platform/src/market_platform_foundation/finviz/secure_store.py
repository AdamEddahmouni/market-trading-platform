"""Private-file secure storage for Finviz credentials.

Phase 0 source invariants prohibit native-OS access (ctypes / Windows
Credential Manager) inside ``src/market_platform_foundation``. Tokens
and login credentials are stored as files under the gitignored
``.private/`` directory (or ``IMP_FINVIZ_SECRET_DIR``), consistent with
the documented ``IMP_PROVIDER_ENV=.private/providers.env`` posture.
Best-effort restrictive permissions are applied on POSIX; on Windows
the file ACLs are left to the owner. The public interface
(read/write/clear token and login credentials) is unchanged so the
credential manager and tests keep working.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import REPO_ROOT

TOKEN_FILENAME = "finviz-token.txt"
LOGIN_FILENAME = "finviz-login.json"
META_FILENAME = "finviz-auth-meta.json"


@dataclass
class FinvizCredentialMetadata:
    finviz_credential_generation: int = 0
    last_validated: str | None = None
    last_rotation: str | None = None
    source: str = "NONE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FinvizCredentialMetadata:
        return cls(
            finviz_credential_generation=int(data.get("finviz_credential_generation") or 0),
            last_validated=data.get("last_validated"),
            last_rotation=data.get("last_rotation"),
            source=str(data.get("source") or "NONE"),
        )


def _secret_dir() -> Path:
    override = os.environ.get("IMP_FINVIZ_SECRET_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT / ".private"


def _meta_path() -> Path:
    override = os.environ.get("IMP_FINVIZ_AUTH_META")
    if override:
        return Path(override).expanduser().resolve()
    return _secret_dir() / META_FILENAME


def _token_path() -> Path:
    return _secret_dir() / TOKEN_FILENAME


def _login_path() -> Path:
    return _secret_dir() / LOGIN_FILENAME


def _restrict_permissions(path: Path) -> None:
    """Best-effort owner-only permissions; ignore platforms that lack chmod."""

    try:
        if sys.platform != "win32":
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8")
    _restrict_permissions(temp)
    os.replace(temp, path)
    _restrict_permissions(path)


def load_metadata() -> FinvizCredentialMetadata:
    path = _meta_path()
    if not path.is_file():
        return FinvizCredentialMetadata()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return FinvizCredentialMetadata.from_dict(data)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return FinvizCredentialMetadata()


def save_metadata(metadata: FinvizCredentialMetadata) -> None:
    _atomic_write_text(_meta_path(), json.dumps(metadata.to_dict(), indent=2))


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def read_secure_token() -> str | None:
    path = _token_path()
    if not path.is_file():
        return None
    try:
        token = path.read_text(encoding="utf-8").strip()
        return token or None
    except OSError:
        return None


def write_secure_token(token: str) -> bool:
    if not token:
        return False
    try:
        _atomic_write_text(_token_path(), token + "\n")
        return True
    except OSError:
        return False


def clear_secure_token() -> bool:
    try:
        path = _token_path()
        if path.is_file():
            path.unlink()
        return True
    except OSError:
        return False


def read_login_credentials() -> tuple[str | None, str | None]:
    path = _login_path()
    if not path.is_file():
        return None, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        username = str(data.get("username") or "")
        password = str(data.get("password") or "")
        return (username or None, password or None)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None, None


def write_login_credentials(username: str, password: str) -> bool:
    if not username or not password:
        return False
    try:
        _atomic_write_text(
            _login_path(),
            json.dumps({"username": username, "password": password}, indent=2),
        )
        return True
    except OSError:
        return False


def clear_login_credentials() -> None:
    try:
        path = _login_path()
        if path.is_file():
            path.unlink()
    except OSError:
        pass


def record_credential_activation(*, source: str, rotated: bool) -> FinvizCredentialMetadata:
    metadata = load_metadata()
    now = _utc_iso()
    if rotated:
        metadata.finviz_credential_generation += 1
        metadata.last_rotation = now
    metadata.last_validated = now
    metadata.source = source
    save_metadata(metadata)
    return metadata
