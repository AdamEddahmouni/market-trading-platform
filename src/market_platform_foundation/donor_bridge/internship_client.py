"""Read-only filesystem client for internship agent demo state."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_STATE_RELATIVE = (
    "internship-project-main",
    "internship-project-main",
    "news_momentum_agent",
    "state",
)


def _workspace_root() -> Path:
    # donor_bridge -> market_platform_foundation -> src -> integrated-market-platform -> workspace
    return Path(__file__).resolve().parents[4]


def default_state_dir() -> Path:
    override = os.environ.get("INTERNSHIP_STATE_DIR", "").strip()
    if override:
        return Path(override)
    return _workspace_root().joinpath(*DEFAULT_STATE_RELATIVE)


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def is_available(*, state_dir: Path | None = None) -> bool:
    root = state_dir or default_state_dir()
    health = _read_json(root / "health.json")
    if isinstance(health, dict) and health.get("demo_mode"):
        return True
    return (root / "demo.lock").is_file() and (root / "trade_log.json").is_file()


def load_health(*, state_dir: Path | None = None) -> dict[str, Any] | None:
    root = state_dir or default_state_dir()
    payload = _read_json(root / "health.json")
    return payload if isinstance(payload, dict) else None


def load_trade_log(*, state_dir: Path | None = None) -> list[dict[str, Any]]:
    root = state_dir or default_state_dir()
    payload = _read_json(root / "trade_log.json")
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]


def load_watchlist(*, state_dir: Path | None = None) -> list[dict[str, Any]]:
    root = state_dir or default_state_dir()
    payload = _read_json(root / "watchlist.json")
    if not isinstance(payload, dict):
        return []
    items = payload.get("items", [])
    if not isinstance(items, list):
        return []
    return [row for row in items if isinstance(row, dict)]


def load_pending_reviews(*, state_dir: Path | None = None) -> list[dict[str, Any]]:
    root = state_dir or default_state_dir()
    payload = _read_json(root / "pending_reviews.json")
    if not isinstance(payload, list):
        return []
    return [row for row in payload if isinstance(row, dict)]
