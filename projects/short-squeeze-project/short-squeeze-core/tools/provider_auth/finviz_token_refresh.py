"""Manual Finviz Elite export-token refresh command.

This operational module is inert on import and is not part of canonical research runtime.
"""

from __future__ import annotations

import csv
import io
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Callable, Protocol


LOGIN_URL = "https://finviz.com/login_submit.ashx"
TOKEN_PAGE_URL = "https://elite.finviz.com/api_explanation"
EXPORT_URL = "https://elite.finviz.com/export/screener"
EXPORT_VERSION = "152"
EXPORT_FILTER = "sh_float_u20,sh_price_u20"
EXPORT_COLUMNS = (
    "1,25,26,30,31,84,42,43,49,50,52,53,55,59,56,60,61,64,65,66,57,81,86,87"
)
TOKEN_PATTERN = re.compile(
    r"[?&]auth=([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-"
    r"[a-f0-9]{4}-[a-f0-9]{12})",
    re.IGNORECASE,
)
USER_TOKEN_PATTERN = re.compile(
    r"userToken.{0,256}?([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-"
    r"[a-f0-9]{4}-[a-f0-9]{12})",
    re.IGNORECASE | re.DOTALL,
)
TOKEN_VALUE_PATTERN = re.compile(
    r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-"
    r"[a-f0-9]{4}-[a-f0-9]{12}$",
    re.IGNORECASE,
)
MANUAL_AUTH_MARKERS = (
    "captcha",
    "two-factor",
    "two factor",
    "multi-factor",
    "multifactor",
    "verification code",
    "security challenge",
)


class RefreshStatus(StrEnum):
    REFRESHED = "REFRESHED"
    MANUAL_AUTH_REQUIRED = "MANUAL_AUTH_REQUIRED"
    INVALID_EXPORT = "INVALID_EXPORT"
    CONFIG_MISSING = "CONFIG_MISSING"
    AUTH_FAILED = "AUTH_FAILED"
    TOKEN_NOT_FOUND = "TOKEN_NOT_FOUND"
    NETWORK_ERROR = "NETWORK_ERROR"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"


@dataclass(frozen=True, slots=True)
class ExportValidation:
    valid: bool
    http_status: int
    content_type: str
    row_count: int = 0
    columns: tuple[str, ...] = ()
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class RefreshResult:
    status: RefreshStatus
    http_status: int | None = None
    content_type: str | None = None
    row_count: int = 0
    columns: tuple[str, ...] = ()
    latency_ms: int | None = None
    retrieved_at: str | None = None
    backup_created: bool = False
    old_token_present: bool = False


class ResponseLike(Protocol):
    text: str
    status_code: int
    url: object
    headers: dict[str, str]


def validate_export_response(response: ResponseLike) -> ExportValidation:
    status = int(response.status_code)
    content_type = str(response.headers.get("content-type", "")).split(";", 1)[0].strip()
    text = response.text or ""
    lowered = text[:10_000].lower()
    if _requires_manual_auth(lowered):
        return ExportValidation(
            False, status, content_type, error_code="MANUAL_AUTH_REQUIRED",
        )
    if "text/html" in content_type or "<html" in lowered:
        error = "LOGIN_PAGE" if _looks_like_login(lowered) else "HTML_RESPONSE"
        return ExportValidation(False, status, content_type, error_code=error)
    if status != 200:
        return ExportValidation(False, status, content_type, error_code="HTTP_ERROR")
    try:
        reader = csv.DictReader(io.StringIO(text))
        columns = tuple(reader.fieldnames or ())
        if "Ticker" not in columns:
            return ExportValidation(False, status, content_type, error_code="NOT_CSV")
        rows = sum(1 for row in reader if (row.get("Ticker") or "").strip())
    except (csv.Error, TypeError):
        return ExportValidation(False, status, content_type, error_code="NOT_CSV")
    if rows < 1:
        return ExportValidation(
            False, status, content_type, columns=columns, error_code="EMPTY_EXPORT",
        )
    return ExportValidation(True, status, content_type, rows, columns)


def persist_private_token(
    path: Path, token: str, *, timestamp: str | None = None,
) -> Path:
    if not TOKEN_VALUE_PATTERN.fullmatch(token):
        raise ValueError("Finviz export token has an unsupported format")
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError("Private provider file is missing")
    original = path.read_text(encoding="utf-8")
    stamp = timestamp or datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{path.name}.pre-finviz-{stamp}.bak"
    shutil.copy2(path, backup)

    lines = original.splitlines(keepends=True)
    replacement = f"FINVIZ_API_KEY={token}\n"
    updated = False
    for index, line in enumerate(lines):
        if line.lstrip().startswith("FINVIZ_API_KEY="):
            lines[index] = replacement
            updated = True
            break
    if not updated:
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += "\n"
        lines.append(replacement)

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.writelines(lines)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        temp_name = None
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
    return backup


def refresh_finviz_token(
    path: Path,
    session_factory: Callable[[], object],
    *,
    emit: Callable[[str], None] = print,
) -> RefreshResult:
    values = _load_private_values(path)
    username = values.get("FINVIZ_USERNAME", "")
    password = values.get("FINVIZ_PASSWORD", "")
    old_token_present = bool(values.get("FINVIZ_API_KEY"))
    if not username or not password:
        emit("FINVIZ_AUTH_SESSION: CONFIG_MISSING")
        return RefreshResult(
            RefreshStatus.CONFIG_MISSING, old_token_present=old_token_present,
        )

    started = time.perf_counter()
    try:
        session: Any = session_factory()
        login = session.post(
            LOGIN_URL,
            data={"email": username, "password": password},
            impersonate="chrome",
            timeout=15,
            allow_redirects=True,
        )
        login_text = (login.text or "")[:10_000].lower()
        if _requires_manual_auth(login_text):
            emit("FINVIZ_AUTH_SESSION: MANUAL_AUTH_REQUIRED")
            return RefreshResult(
                RefreshStatus.MANUAL_AUTH_REQUIRED,
                http_status=int(login.status_code),
                old_token_present=old_token_present,
            )
        if int(login.status_code) != 200 or "elite.finviz.com" not in str(login.url).lower():
            emit("FINVIZ_AUTH_SESSION: FAILED")
            return RefreshResult(
                RefreshStatus.AUTH_FAILED,
                http_status=int(login.status_code),
                old_token_present=old_token_present,
            )
        emit("FINVIZ_AUTH_SESSION: SUCCESS")

        token_page = session.get(
            TOKEN_PAGE_URL, impersonate="chrome", timeout=15,
        )
        page_text = token_page.text or ""
        if _requires_manual_auth(page_text[:10_000].lower()):
            emit("FINVIZ_EXPORT_TOKEN: MANUAL_AUTH_REQUIRED")
            return RefreshResult(
                RefreshStatus.MANUAL_AUTH_REQUIRED,
                http_status=int(token_page.status_code),
                old_token_present=old_token_present,
            )
        match = TOKEN_PATTERN.search(page_text) or USER_TOKEN_PATTERN.search(page_text)
        if int(token_page.status_code) != 200 or match is None:
            emit("FINVIZ_EXPORT_TOKEN: NOT_FOUND")
            return RefreshResult(
                RefreshStatus.TOKEN_NOT_FOUND,
                http_status=int(token_page.status_code),
                old_token_present=old_token_present,
            )
        token = match.group(1)
        validation_response = session.get(
            EXPORT_URL,
            params={
                "v": EXPORT_VERSION,
                "f": EXPORT_FILTER,
                "c": EXPORT_COLUMNS,
                "auth": token,
            },
            impersonate="chrome",
            timeout=15,
        )
        validation = validate_export_response(validation_response)
        latency_ms = round((time.perf_counter() - started) * 1000)
        if not validation.valid:
            if validation.error_code == "MANUAL_AUTH_REQUIRED":
                emit("FINVIZ_EXPORT_VALIDATION: MANUAL_AUTH_REQUIRED")
                status = RefreshStatus.MANUAL_AUTH_REQUIRED
            else:
                emit(f"FINVIZ_EXPORT_VALIDATION: REJECTED_{validation.error_code}")
                status = RefreshStatus.INVALID_EXPORT
            return RefreshResult(
                status,
                http_status=validation.http_status,
                content_type=validation.content_type,
                latency_ms=latency_ms,
                old_token_present=old_token_present,
            )

        persist_private_token(path, token)
        retrieved_at = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
        emit("FINVIZ_EXPORT_TOKEN: REFRESHED")
        emit(f"FINVIZ_EXPORT_VALIDATION: HTTP {validation.http_status}")
        emit(f"FINVIZ_ROWS: {validation.row_count}")
        return RefreshResult(
            RefreshStatus.REFRESHED,
            http_status=validation.http_status,
            content_type=validation.content_type,
            row_count=validation.row_count,
            columns=validation.columns,
            latency_ms=latency_ms,
            retrieved_at=retrieved_at,
            backup_created=True,
            old_token_present=old_token_present,
        )
    except Exception:
        emit("FINVIZ_AUTH_SESSION: NETWORK_OR_PROVIDER_ERROR")
        return RefreshResult(
            RefreshStatus.NETWORK_ERROR,
            latency_ms=round((time.perf_counter() - started) * 1000),
            old_token_present=old_token_present,
        )


def _load_private_values(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        values[key.strip()] = value.strip()
    return values


def _requires_manual_auth(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in MANUAL_AUTH_MARKERS)


def _looks_like_login(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in ("login", "log in", "sign in", "password"))


def _curl_session_factory() -> object:
    from curl_cffi import requests as curl_requests

    return curl_requests.Session()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Refresh the user-owned Finviz Elite export token (sanitized output).",
    )
    parser.add_argument(
        "--providers-env",
        type=Path,
        default=Path(".private/providers.env"),
        help="Git-ignored private provider configuration file.",
    )
    args = parser.parse_args()
    try:
        import curl_cffi  # noqa: F401
    except ImportError:
        print("FINVIZ_AUTH_SESSION: DEPENDENCY_MISSING")
        return 4
    result = refresh_finviz_token(args.providers_env, _curl_session_factory)
    return 0 if result.status == RefreshStatus.REFRESHED else 2


if __name__ == "__main__":
    raise SystemExit(main())
