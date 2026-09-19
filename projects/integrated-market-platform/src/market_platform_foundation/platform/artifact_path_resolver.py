"""Safe resolution of paths embedded in historical manifests and run records.

Historical manifests may contain host-absolute paths from the machine that
produced them. Resolvers must not rewrite those artifacts; they classify
unavailability honestly and avoid platform-mismatched ``Path`` operations that
raise ``OSError`` (for example Linux CI stat on Windows ``C:\\`` paths).
"""

from __future__ import annotations

import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

ITEM9_COLLECTOR_LOG_ENV = "IMP_ITEM9_COLLECTOR_LOG_PATH"
DEFAULT_ITEM9_COLLECTOR_LOG_REL = "artifacts/ftep-v1-002/item9-prospective-collector.log"
_MAX_COLLECTOR_LOG_BYTES = 512_000

_START_ITEM9_EPOCH = re.compile(
    r"START\s+(item9-prospective-\d{8}-epoch-[0-9a-f]+-aapl-(\d{6}))",
    re.IGNORECASE,
)
_END_ITEM9_EPOCH = re.compile(
    r"END\s+(item9-prospective-\d{8}-epoch-[0-9a-f]+-aapl-(\d{6}))",
    re.IGNORECASE,
)
_RECEIPT_ITEM9_EPOCH = re.compile(
    r"receipt\s+(item9-prospective-\d{8}-epoch-[0-9a-f]+-aapl-(\d{6}))",
    re.IGNORECASE,
)


class StoredPathAvailability(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    FOREIGN_PLATFORM = "FOREIGN_PLATFORM"
    NOT_OBSERVED = "NOT_OBSERVED"
    INVALID = "INVALID"


@dataclass(frozen=True, slots=True)
class StoredPathResolution:
    raw: str
    availability: StoredPathAvailability
    resolved_path: Path | None
    reason_code: str | None = None


def looks_like_windows_absolute_path(path_str: str) -> bool:
    if len(path_str) >= 2 and path_str[0].isalpha() and path_str[1] == ":":
        return True
    return path_str.startswith("\\\\")


def looks_like_posix_absolute_path(path_str: str) -> bool:
    return path_str.startswith("/")


def _path_is_readable_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _path_is_readable_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def classify_stored_path(raw: str | None, *, platform: str | None = None) -> StoredPathResolution:
    platform_name = platform or sys.platform
    if raw is None:
        return StoredPathResolution("", StoredPathAvailability.NOT_OBSERVED, None, "PATH_NOT_PROVIDED")
    text = str(raw).strip()
    if not text:
        return StoredPathResolution(text, StoredPathAvailability.NOT_OBSERVED, None, "PATH_EMPTY")
    if platform_name != "win32" and looks_like_windows_absolute_path(text):
        return StoredPathResolution(
            text,
            StoredPathAvailability.FOREIGN_PLATFORM,
            None,
            "WINDOWS_ABSOLUTE_ON_NON_WINDOWS",
        )
    if platform_name == "win32" and looks_like_posix_absolute_path(text) and not text.startswith("//"):
        return StoredPathResolution(
            text,
            StoredPathAvailability.FOREIGN_PLATFORM,
            None,
            "POSIX_ABSOLUTE_ON_WINDOWS",
        )
    return StoredPathResolution(text, StoredPathAvailability.UNAVAILABLE, None, "NOT_YET_RESOLVED")


def resolve_stored_file_path(
    raw: str | None,
    *,
    repository_root: Path | None = None,
) -> StoredPathResolution:
    classified = classify_stored_path(raw)
    if classified.availability in {
        StoredPathAvailability.NOT_OBSERVED,
        StoredPathAvailability.FOREIGN_PLATFORM,
        StoredPathAvailability.INVALID,
    }:
        return classified

    text = classified.raw
    candidates: list[Path] = [Path(text)]
    if repository_root is not None and not looks_like_windows_absolute_path(text) and not looks_like_posix_absolute_path(text):
        candidates.append(repository_root / text)

    for candidate in candidates:
        if _path_is_readable_file(candidate):
            return StoredPathResolution(
                text,
                StoredPathAvailability.AVAILABLE,
                candidate,
                None,
            )

    return StoredPathResolution(text, StoredPathAvailability.UNAVAILABLE, None, "FILE_NOT_FOUND")


def resolve_stored_file_parent(
    raw: str | None,
    *,
    repository_root: Path | None = None,
) -> StoredPathResolution:
    file_resolution = resolve_stored_file_path(raw, repository_root=repository_root)
    if file_resolution.resolved_path is None:
        return file_resolution
    return StoredPathResolution(
        file_resolution.raw,
        StoredPathAvailability.AVAILABLE,
        file_resolution.resolved_path.parent,
        None,
    )


def portable_stored_path(path: Path, *, repository_root: Path) -> str:
    """Repository-relative POSIX path for new manifest writes."""

    try:
        return path.resolve().relative_to(repository_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def monorepo_root_from_imp(repository_root: Path) -> Path:
    current = repository_root.resolve()
    for _ in range(10):
        if (current / ".git").exists():
            return current
        if current.parent == current:
            break
        current = current.parent
    return repository_root.resolve()


def resolve_v3_baseline_run_dir(
    repository_root: Path,
    *,
    run_id: str,
    manifest_path: str | None,
) -> Path | None:
    parent = resolve_stored_file_parent(manifest_path, repository_root=repository_root)
    if parent.resolved_path is not None:
        return parent.resolved_path

    local = (
        repository_root
        / "artifacts"
        / "historical-research-harness"
        / "baseline-pack-v3"
        / "runs"
        / run_id
    )
    if _path_is_readable_dir(local):
        return local

    monorepo_root = monorepo_root_from_imp(repository_root)
    sibling = (
        monorepo_root
        / ".worktrees"
        / "opend-fill-economics-v3"
        / "projects"
        / "integrated-market-platform"
        / "artifacts"
        / "historical-research-harness"
        / "baseline-pack-v3"
        / "runs"
        / run_id
    )
    if _path_is_readable_dir(sibling):
        return sibling
    return None


def resolve_item9_collector_log_path(
    imp_root: Path,
    env: Mapping[str, str],
) -> StoredPathResolution:
    """Resolve operator-captured Item 9 collector log (read-only; does not create paths)."""

    imp_root = imp_root.resolve()
    override = (env.get(ITEM9_COLLECTOR_LOG_ENV) or "").strip()
    if override:
        return resolve_stored_file_path(override, repository_root=imp_root)

    default = imp_root / DEFAULT_ITEM9_COLLECTOR_LOG_REL
    if _path_is_readable_file(default):
        return StoredPathResolution(
            DEFAULT_ITEM9_COLLECTOR_LOG_REL,
            StoredPathAvailability.AVAILABLE,
            default,
            None,
        )
    return StoredPathResolution(
        DEFAULT_ITEM9_COLLECTOR_LOG_REL,
        StoredPathAvailability.NOT_OBSERVED,
        None,
        "COLLECTOR_LOG_NOT_CONFIGURED",
    )


def read_item9_collector_log_text(
    imp_root: Path,
    env: Mapping[str, str],
    *,
    max_bytes: int = _MAX_COLLECTOR_LOG_BYTES,
) -> tuple[str | None, dict[str, object]]:
    """Read collector log text for expected-cycle gap analysis when configured."""

    resolution = resolve_item9_collector_log_path(imp_root, env)
    meta: dict[str, object] = {
        "log_path": resolution.raw,
        "availability": resolution.availability.value,
        "reason_code": resolution.reason_code,
    }
    if resolution.resolved_path is None:
        return None, meta

    path = resolution.resolved_path
    try:
        size = path.stat().st_size
    except OSError as exc:
        meta["reason_code"] = f"STAT_ERROR:{exc.__class__.__name__}"
        return None, meta

    meta["byte_size"] = size
    try:
        if size <= max_bytes:
            text = path.read_text(encoding="utf-8", errors="replace")
        else:
            with path.open("rb") as handle:
                handle.seek(max(0, size - max_bytes))
                text = handle.read().decode("utf-8", errors="replace")
            meta["truncated"] = True
            meta["max_bytes"] = max_bytes
    except OSError as exc:
        meta["reason_code"] = f"READ_ERROR:{exc.__class__.__name__}"
        return None, meta
    return text, meta


def analyze_item9_collect_log_gaps(log_text: str) -> dict[str, object]:
    """Compare START/END epochs in collector logs against receipt filenames (read-only)."""

    started: dict[str, str] = {}
    ended: dict[str, str] = {}
    receipt_epochs: set[str] = set()
    for line in log_text.splitlines():
        receipt_match = _RECEIPT_ITEM9_EPOCH.search(line)
        if receipt_match:
            receipt_epochs.add(receipt_match.group(2))
            continue
        start_match = _START_ITEM9_EPOCH.search(line)
        if start_match:
            started[start_match.group(2)] = start_match.group(1)
            continue
        end_match = _END_ITEM9_EPOCH.search(line)
        if end_match:
            ended[end_match.group(2)] = end_match.group(1)

    missing_receipt_epochs: list[dict[str, str]] = []
    for epoch, experiment_id in sorted(started.items()):
        if epoch in receipt_epochs:
            continue
        failure_class = (
            "COLLECTOR_HUNG_OR_PROVIDER_UNAVAILABLE"
            if epoch not in ended
            else "PROVIDER_UNAVAILABLE_OR_PARTIAL_RECEIPT"
        )
        missing_receipt_epochs.append(
            {
                "epoch": epoch,
                "experiment_id": experiment_id,
                "failure_class": failure_class,
                "receipt_status": "NOT_OBSERVED",
            }
        )

    hung_without_end = [epoch for epoch in started if epoch not in ended]
    return {
        "started_epoch_count": len(started),
        "ended_epoch_count": len(ended),
        "hung_epochs_without_end": hung_without_end,
        "missing_receipt_epochs": missing_receipt_epochs,
    }


def analyze_item9_receipt_directory(receipt_dir: Path) -> dict[str, object]:
    """Inventory prospective receipts; does not mutate or backfill gaps."""

    if not receipt_dir.is_dir():
        return {
            "receipt_dir": str(receipt_dir),
            "availability": StoredPathAvailability.UNAVAILABLE.value,
            "reason_code": "RECEIPT_DIR_MISSING",
            "receipt_files": [],
        }

    files = sorted(path.name for path in receipt_dir.glob("item9-prospective-*.json") if path.is_file())
    return {
        "receipt_dir": str(receipt_dir),
        "availability": StoredPathAvailability.AVAILABLE.value,
        "receipt_file_count": len(files),
        "receipt_files": files,
    }


__all__ = [
    "DEFAULT_ITEM9_COLLECTOR_LOG_REL",
    "ITEM9_COLLECTOR_LOG_ENV",
    "StoredPathAvailability",
    "StoredPathResolution",
    "analyze_item9_collect_log_gaps",
    "analyze_item9_receipt_directory",
    "classify_stored_path",
    "looks_like_posix_absolute_path",
    "looks_like_windows_absolute_path",
    "monorepo_root_from_imp",
    "portable_stored_path",
    "read_item9_collector_log_text",
    "resolve_item9_collector_log_path",
    "resolve_stored_file_parent",
    "resolve_stored_file_path",
    "resolve_v3_baseline_run_dir",
]
