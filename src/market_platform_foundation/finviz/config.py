"""Finviz Elite configuration — constants and non-secret paths."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

FINVIZ_EXPORT_URL = "https://elite.finviz.com/export/screener"
FINVIZ_NEWS_URL = "https://elite.finviz.com/news_export.ashx"
FINVIZ_OPTIONS_URL = "https://elite.finviz.com/export/options"
FINVIZ_EXPORT_VERSION = "152"
DEFAULT_SCREENER_COLUMNS = "1,25,26,30,31,84,42,43,49,50,52,53,55,59,56,60,61,64,65,66,57,81,86,87"

MIN_REQUEST_INTERVAL_S = 5.0
SCREENER_CACHE_TTL_S = 120.0
NEWS_CACHE_TTL_S = 180.0
OPTIONS_CACHE_TTL_S = 300.0
SYMBOL_CACHE_TTL_S = 300.0
FUNDAMENTAL_CACHE_TTL_S = 3600.0

REDACT_KEYS = (
    "auth",
    "token",
    "api_token",
    "password",
    "passwd",
    "secret",
    "key",
    "login",
    "pwd",
    "cookie",
    "set-cookie",
    "session",
    "sessionid",
    "authorization",
)


def finviz_live_enabled() -> bool:
    return os.environ.get("IMP_FINVIZ_LIVE", "").strip().lower() in ("1", "true", "yes")


def provider_env_path() -> Path | None:
    override = os.environ.get("IMP_PROVIDER_ENV")
    if override:
        path = Path(override).expanduser()
        return path if path.is_file() else None
    candidates = [
        REPO_ROOT / ".private" / "providers.env",
        REPO_ROOT.parent / "short-squeeze-project" / "short-squeeze-core" / ".private" / "providers.env",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, _, value = text.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        return {}
    return values


def finviz_api_key() -> str | None:
    from .credential_manager import get_finviz_credential_manager

    return get_finviz_credential_manager().get_token()


def finviz_evidence_root() -> Path:
    override = os.environ.get("IMP_FINVIZ_EVIDENCE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT / "evidence" / "market_data" / "finviz"


def finviz_capture_root() -> Path:
    override = os.environ.get("IMP_FINVIZ_CAPTURE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT / "data" / "captures" / "finviz"
