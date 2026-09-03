"""Local workstation state directory (PLATFORM-STATE-001)."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_STATE_DIRNAME = ".local"
DB_FILENAME = "imp-state.sqlite3"


def persistence_enabled() -> bool:
    if os.environ.get("IMP_STATE_DIR"):
        return True
    return os.environ.get("IMP_PERSIST_STATE") == "1"


def state_dir(*, create: bool = False) -> Path:
    override = os.environ.get("IMP_STATE_DIR")
    path = Path(override).expanduser().resolve() if override else (REPO_ROOT / DEFAULT_STATE_DIRNAME)
    if create:
        path.mkdir(parents=True, exist_ok=True)
        (path / "captures").mkdir(parents=True, exist_ok=True)
        (path / "backups").mkdir(parents=True, exist_ok=True)
    return path


def database_path(*, create_dir: bool = False) -> Path:
    return state_dir(create=create_dir) / DB_FILENAME


def capture_scan_roots() -> list[Path]:
    roots = [
        state_dir() / "captures",
        REPO_ROOT / "evidence" / "live-captures",
        REPO_ROOT / "evidence" / "market_data" / "moomoo",
    ]
    extra = os.environ.get("IMP_CAPTURE_DIR")
    if extra:
        roots.insert(0, Path(extra).expanduser().resolve())
    return roots
