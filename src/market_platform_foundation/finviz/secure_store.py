"""OS-backed secure storage for Finviz credentials (Windows Credential Manager)."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import REPO_ROOT

CREDENTIAL_TARGET = "IMP/FINVIZ_ELITE_API_TOKEN"
LOGIN_USERNAME_TARGET = "IMP/FINVIZ_ELITE_USERNAME"
LOGIN_PASSWORD_TARGET = "IMP/FINVIZ_ELITE_PASSWORD"
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


def _meta_path() -> Path:
    override = os.environ.get("IMP_FINVIZ_AUTH_META")
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT / ".private" / META_FILENAME


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
    path = _meta_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(metadata.to_dict(), indent=2), encoding="utf-8")
    os.replace(temp, path)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _windows_cred_available() -> bool:
    return sys.platform == "win32"


def read_windows_credential(target: str) -> str | None:
    if not _windows_cred_available():
        return None
    try:
        import ctypes
        from ctypes import wintypes

        advapi32 = ctypes.windll.advapi32
        pcred = ctypes.c_void_p()
        if not advapi32.CredReadW(target, 1, 0, ctypes.byref(pcred)):
            return None
        try:
            class CREDENTIAL(ctypes.Structure):
                _fields_ = [
                    ("Flags", wintypes.DWORD),
                    ("Type", wintypes.DWORD),
                    ("TargetName", wintypes.LPWSTR),
                    ("Comment", wintypes.LPWSTR),
                    ("LastWritten", wintypes.FILETIME),
                    ("CredentialBlobSize", wintypes.DWORD),
                    ("CredentialBlob", ctypes.POINTER(ctypes.c_char)),
                    ("Persist", wintypes.DWORD),
                    ("AttributeCount", wintypes.DWORD),
                    ("Attributes", ctypes.c_void_p),
                    ("TargetAlias", wintypes.LPWSTR),
                    ("UserName", wintypes.LPWSTR),
                ]

            cred = ctypes.cast(pcred, ctypes.POINTER(CREDENTIAL)).contents
            blob = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize)
            return blob.decode("utf-16-le")
        finally:
            advapi32.CredFree(pcred)
    except (AttributeError, OSError, UnicodeDecodeError):
        return None


def write_windows_credential(target: str, secret: str) -> bool:
    if not _windows_cred_available() or not secret:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        advapi32 = ctypes.windll.advapi32
        encoded = secret.encode("utf-16-le")
        blob = (ctypes.c_char * len(encoded)).from_buffer_copy(encoded)

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [
                ("Flags", wintypes.DWORD),
                ("Type", wintypes.DWORD),
                ("TargetName", wintypes.LPWSTR),
                ("Comment", wintypes.LPWSTR),
                ("LastWritten", wintypes.FILETIME),
                ("CredentialBlobSize", wintypes.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_char)),
                ("Persist", wintypes.DWORD),
                ("AttributeCount", wintypes.DWORD),
                ("Attributes", ctypes.c_void_p),
                ("TargetAlias", wintypes.LPWSTR),
                ("UserName", wintypes.LPWSTR),
            ]

        cred = CREDENTIAL()
        cred.Flags = 0
        cred.Type = 1  # CRED_TYPE_GENERIC
        cred.TargetName = target
        cred.CredentialBlobSize = len(encoded)
        cred.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_char))
        cred.Persist = 2  # CRED_PERSIST_LOCAL_MACHINE
        cred.UserName = "IMP"
        return bool(advapi32.CredWriteW(ctypes.byref(cred), 0))
    except (AttributeError, OSError):
        return False


def delete_windows_credential(target: str) -> bool:
    if not _windows_cred_available():
        return False
    try:
        import ctypes

        return bool(ctypes.windll.advapi32.CredDeleteW(target, 1, 0))
    except (AttributeError, OSError):
        return False


def read_secure_token() -> str | None:
    return read_windows_credential(CREDENTIAL_TARGET)


def write_secure_token(token: str) -> bool:
    return write_windows_credential(CREDENTIAL_TARGET, token)


def clear_secure_token() -> bool:
    return delete_windows_credential(CREDENTIAL_TARGET)


def read_login_credentials() -> tuple[str | None, str | None]:
    return (
        read_windows_credential(LOGIN_USERNAME_TARGET),
        read_windows_credential(LOGIN_PASSWORD_TARGET),
    )


def write_login_credentials(username: str, password: str) -> bool:
    user_ok = write_windows_credential(LOGIN_USERNAME_TARGET, username)
    pass_ok = write_windows_credential(LOGIN_PASSWORD_TARGET, password)
    return user_ok and pass_ok


def clear_login_credentials() -> None:
    delete_windows_credential(LOGIN_USERNAME_TARGET)
    delete_windows_credential(LOGIN_PASSWORD_TARGET)


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
