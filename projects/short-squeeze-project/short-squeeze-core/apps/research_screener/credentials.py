"""Private provider credential loading.

Extracted from ``config.py`` so the application-configuration dataclasses are
not mixed with file-I/O credential loading.  Every credential path in this
codebase should flow through the functions exposed here.

Functions
---------
_read_env_file
    Low-level key-value parser (filtered by ``KNOWN_KEYS``).
default_private_path
    Auto-detect ``.private/providers.env`` relative to the repository root.
load_private_env
    Read a credentials file, populate ``os.environ``, and return the dict.
"""

from __future__ import annotations

import os
from pathlib import Path

# ── Known-key schema (moved here to break circular import with config.py) ─
PROVIDER_KEYS = ("FINVIZ_API_KEY", "NEWSAPI_KEY", "FINNHUB_KEY")
ENABLE_KEYS = (
    "FINVIZ_ENABLED",
    "NEWSAPI_ENABLED",
    "FINNHUB_ENABLED",
    "SEC_ENABLED",
    "IBKR_ENABLED",
    "SENTIMENT_ENABLED",
)
KNOWN_KEYS = frozenset(
    (
        "SQUEEZE_APP_MODE",
        "PORT",
        "LOG_LEVEL",
        "SEC_USER_AGENT",
        "SEC_CONTACT_EMAIL",
        "IBKR_HOST",
        "IBKR_PORT",
        "IBKR_CLIENT_ID",
        "SENTIMENT_PROVIDER",
        "SENTIMENT_MODEL_PATH",
        "SENTIMENT_BATCH_SIZE",
        "NEWS_PROVIDER_ORDER",
        "NEWS_CACHE_TTL_SECONDS",
        "NEWS_MAX_HEADLINES_PER_SYMBOL",
        "QUOTE_REFRESH_SECONDS",
        "SCANNER_REFRESH_SECONDS",
        "CURRENT_SCREEN_CAP",
        "FINVIZ_TOP_N",
        "SCANNER_ROW_LIMIT",
        "SYMBOLS_PER_CYCLE",
        "SYMBOLS_PER_CYCLE_MAX",
        "TARGET_LIVE_CANDIDATES",
        "FRESHNESS_CURRENT_SECONDS",
        "FRESHNESS_DELAYED_SECONDS",
        "MAX_CHART_POINTS",
        "COLLECTORS_ENABLED",
        "COLLECTOR_TICK_SECONDS",
        "COLLECTOR_MAX_SYMBOLS_PER_TICK",
        "COLLECTOR_MAX_REQUESTS_PER_MINUTE",
        "COLLECTOR_ORDER",
        "COLLECTOR_OVERRIDE_POLICY",
        "FINRA_SI_COLLECTOR_ENABLED",
        "FINRA_DAILY_VOLUME_COLLECTOR_ENABLED",
        "RSS_NEWS_ENABLED",
        "SEC_RSS_COLLECTOR_ENABLED",
        "YFINANCE_COLLECTOR_ENABLED",
        "REDDIT_COLLECTOR_ENABLED",
        "STOCKTWITS_COLLECTOR_ENABLED",
        "POLYGON_COLLECTOR_ENABLED",
        "ALPHA_VANTAGE_COLLECTOR_ENABLED",
        "COLLECTOR_CACHE_ENABLED",
        "FINRA_SI_DATA_URL",
        "FINRA_SI_FIXTURE_PATH",
        "FINRA_DAILY_VOLUME_URL_TEMPLATE",
        "POLYGON_API_KEY",
        "ALPHA_VANTAGE_API_KEY",
        "REDDIT_CLIENT_ID",
        "REDDIT_SECRET",
        "STOCKTWITS_ACCESS_TOKEN",
        *PROVIDER_KEYS,
        *ENABLE_KEYS,
    )
)

__all__ = [
    "PROVIDER_KEYS",
    "ENABLE_KEYS",
    "KNOWN_KEYS",
    "_read_env_file",
    "default_private_path",
    "load_private_env",
]


def _read_env_file(path: Path | None) -> dict[str, str]:
    """Read ``KEY=VALUE`` pairs from *path*, filtering by :data:`KNOWN_KEYS`.

    Returns an empty dict if the file does not exist.  Only keys present in
    :data:`KNOWN_KEYS` are included (public config schema); credentials-specific
    variables such as ``IBKR_USER_ID`` are intentionally excluded — use
    :func:`load_private_env` for those.
    """
    if path is None or not path.is_file():
        return {}
    result: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if key in KNOWN_KEYS and value:
            result[key] = value
    return result


def default_private_path() -> Path | None:
    """Return the default path to ``.private/providers.env``.

    Resolution order:

    1. ``SQUEEZE_PRIVATE_PATH`` environment variable (if set)
    2. Repository-relative path (``.private/providers.env`` under the
       repository root, which is two levels above this file)

    Returns ``None`` if the file does not exist under any resolution
    strategy.

    This is the single source of truth for private-file path resolution;
    all callers should use this function rather than hardcoding the path.
    """
    # 1. Env var override (CI / Docker convenience)
    env_path = os.environ.get("SQUEEZE_PRIVATE_PATH")
    if env_path:
        candidate = Path(env_path)
        return candidate if candidate.is_file() else None

    # 2. Repository-relative default
    candidate = Path(__file__).resolve().parents[2] / ".private" / "providers.env"
    return candidate if candidate.is_file() else None


def load_private_env(path: Path | None = None, *, verbose: bool = False) -> dict[str, str]:
    """Load private provider credentials into ``os.environ`` and return them.

    Reads every ``KEY=VALUE`` pair from the file at *path* and calls
    ``os.environ.setdefault()`` for each, so already-set env vars are never
    overwritten.  Unlike :func:`_read_env_file`, this does **not** filter by
    :data:`KNOWN_KEYS` — it loads everything, because callers may need custom
    variables (``IBKR_USER_ID``, ``IBKR_PASSWORD``, etc.) that live outside
    the application config schema.

    Parameters
    ----------
    path
        Full path to the ``.env`` file.  If ``None`` (default), uses
        :func:`default_private_path` to auto-detect.
    verbose
        If ``True``, prints each key name (without its value) as it is loaded.
        Values are never printed or logged.

    Returns
    -------
    dict[str, str]
        All key-value pairs that were loaded (empty dict if the file does
        not exist).  Values reflect the effective environment after loading:
        the file value for keys with no pre-existing ``os.environ`` entry,
        or the pre-existing value when a shell override was preserved by
        ``setdefault``.
    """
    if path is None:
        path = default_private_path()

    if path is None or not path.is_file():
        return {}

    loaded: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        k = key.strip()
        v = value.strip().strip("\"'")
        os.environ.setdefault(k, v)
        # Read back the effective value — if a pre-existing os.environ
        # value was preserved by setdefault(), the dict reflects the
        # shell override rather than the (ignored) file value.
        loaded[k] = os.environ[k]
        if verbose:
            print(f"    {k}")
            if os.environ[k] != v:
                print(f"      (shell override, file value ignored)")
    return loaded
