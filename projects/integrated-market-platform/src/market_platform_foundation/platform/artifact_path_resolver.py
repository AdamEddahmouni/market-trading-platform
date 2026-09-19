"""Safe resolution of paths embedded in historical manifests and run records.

Historical manifests may contain host-absolute paths from the machine that
produced them. Resolvers must not rewrite those artifacts; they classify
unavailability honestly and avoid platform-mismatched ``Path`` operations that
raise ``OSError`` (for example Linux CI stat on Windows ``C:\\`` paths).
"""

from __future__ import annotations

import re
import sys
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

ITEM9_COLLECTOR_LOG_ENV = "IMP_ITEM9_COLLECTOR_LOG_PATH"
DEFAULT_ITEM9_COLLECTOR_LOG_REL = "artifacts/ftep-v1-002/item9-prospective-collector.log"
_MAX_COLLECTOR_LOG_BYTES = 512_000
# Operator-facing freshness only. Does not rewrite evidence or imply collection liveness.
COLLECTOR_LOG_STALE_AFTER_SECONDS = 24 * 60 * 60

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
_RECEIPT_FILE_EPOCH = re.compile(
    r"item9-prospective-\d{8}-epoch-[0-9a-f]+-aapl-(\d{6})",
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


def _collector_log_freshness(
    *,
    mtime_ns: int,
    now_ns: int,
    stale_after_seconds: int,
) -> str:
    if now_ns < mtime_ns:
        return "UNKNOWN"
    age_seconds = (now_ns - mtime_ns) / 1_000_000_000
    if age_seconds > stale_after_seconds:
        return "STALE"
    return "FRESH"


def read_item9_collector_log_text(
    imp_root: Path,
    env: Mapping[str, str],
    *,
    max_bytes: int = _MAX_COLLECTOR_LOG_BYTES,
    now_ns: int | None = None,
    stale_after_seconds: int = COLLECTOR_LOG_STALE_AFTER_SECONDS,
) -> tuple[str | None, dict[str, object]]:
    """Read collector log text for expected-cycle gap analysis when configured."""

    resolution = resolve_item9_collector_log_path(imp_root, env)
    meta: dict[str, object] = {
        "log_path": resolution.raw,
        "availability": resolution.availability.value,
        "reason_code": resolution.reason_code,
        "truncated": False,
        "freshness": "NOT_OBSERVED",
    }
    if resolution.resolved_path is None:
        return None, meta

    path = resolution.resolved_path
    try:
        stat_result = path.stat()
    except OSError as exc:
        meta["reason_code"] = f"STAT_ERROR:{exc.__class__.__name__}"
        meta["availability"] = StoredPathAvailability.UNAVAILABLE.value
        return None, meta

    size = stat_result.st_size
    mtime_ns = int(getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1_000_000_000)))
    observed_ns = now_ns if now_ns is not None else time.time_ns()
    meta["byte_size"] = size
    meta["mtime_ns"] = mtime_ns
    meta["age_seconds"] = max(0.0, (observed_ns - mtime_ns) / 1_000_000_000)
    meta["freshness"] = _collector_log_freshness(
        mtime_ns=mtime_ns,
        now_ns=observed_ns,
        stale_after_seconds=stale_after_seconds,
    )
    try:
        if size <= max_bytes:
            text = path.read_text(encoding="utf-8", errors="replace")
            meta["truncated"] = False
        else:
            with path.open("rb") as handle:
                handle.seek(max(0, size - max_bytes))
                chunk = handle.read()
            text = chunk.decode("utf-8", errors="replace")
            # Byte-tail reads are not record-aligned; drop the leading partial line.
            newline = text.find("\n")
            if newline >= 0:
                text = text[newline + 1 :]
            else:
                text = ""
            meta["truncated"] = True
            meta["max_bytes"] = max_bytes
            meta["bytes_omitted"] = size - max_bytes
    except OSError as exc:
        meta["reason_code"] = f"READ_ERROR:{exc.__class__.__name__}"
        meta["availability"] = StoredPathAvailability.UNAVAILABLE.value
        return None, meta
    return text, meta


def epochs_from_item9_receipt_filenames(names: Iterable[str]) -> set[str]:
    """Extract HHMMSS epoch tokens from receipt basenames (read-only)."""

    epochs: set[str] = set()
    for name in names:
        match = _RECEIPT_FILE_EPOCH.search(Path(str(name)).name)
        if match:
            epochs.add(match.group(1))
    return epochs


def analyze_item9_collect_log_gaps(
    log_text: str,
    *,
    truncated: bool = False,
    known_receipt_epochs: Iterable[str] | None = None,
) -> dict[str, object]:
    """Compare START/END epochs in collector logs against receipt filenames (read-only)."""

    started: dict[str, str] = {}
    ended: dict[str, str] = {}
    start_counts: dict[str, int] = {}
    end_counts: dict[str, int] = {}
    receipt_epochs: set[str] = set(known_receipt_epochs or ())
    inventory_receipt_epochs = set(receipt_epochs)

    normalized = log_text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = normalized.split("\n")

    for line in lines:
        receipt_match = _RECEIPT_ITEM9_EPOCH.search(line)
        if receipt_match:
            receipt_epochs.add(receipt_match.group(2))
            continue
        start_match = _START_ITEM9_EPOCH.search(line)
        if start_match:
            epoch = start_match.group(2)
            start_counts[epoch] = start_counts.get(epoch, 0) + 1
            if epoch not in started:
                started[epoch] = start_match.group(1)
            continue
        end_match = _END_ITEM9_EPOCH.search(line)
        if end_match:
            epoch = end_match.group(2)
            end_counts[epoch] = end_counts.get(epoch, 0) + 1
            if epoch not in ended:
                ended[epoch] = end_match.group(1)

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

    hung_without_end = sorted(epoch for epoch in started if epoch not in ended)
    ends_without_start = sorted(epoch for epoch in ended if epoch not in started)
    duplicate_start_epochs = sorted(epoch for epoch, count in start_counts.items() if count > 1)
    duplicate_end_epochs = sorted(epoch for epoch, count in end_counts.items() if count > 1)
    return {
        "started_epoch_count": len(started),
        "ended_epoch_count": len(ended),
        "start_observation_count": sum(start_counts.values()),
        "end_observation_count": sum(end_counts.values()),
        "hung_epochs_without_end": hung_without_end,
        "ends_without_start": ends_without_start,
        "duplicate_start_epochs": duplicate_start_epochs,
        "duplicate_end_epochs": duplicate_end_epochs,
        "missing_receipt_epochs": missing_receipt_epochs,
        "truncated": truncated,
        "analysis_completeness": "PARTIAL_TAIL" if truncated else "FULL",
        "inventory_receipt_epoch_count": len(inventory_receipt_epochs),
    }


def analyze_item9_receipt_directory(receipt_dir: Path | str) -> dict[str, object]:
    """Inventory prospective receipts; does not mutate or backfill gaps."""

    raw = receipt_dir if isinstance(receipt_dir, str) else str(receipt_dir)
    classified = classify_stored_path(raw)
    path = Path(receipt_dir)
    if classified.availability != StoredPathAvailability.FOREIGN_PLATFORM:
        posix = path.as_posix()
        if posix != raw:
            classified = classify_stored_path(posix)
    if classified.availability == StoredPathAvailability.FOREIGN_PLATFORM:
        return {
            "receipt_dir": raw,
            "availability": StoredPathAvailability.FOREIGN_PLATFORM.value,
            "reason_code": classified.reason_code,
            "receipt_files": [],
            "receipt_file_count": 0,
        }

    try:
        is_dir = path.is_dir()
    except OSError as exc:
        return {
            "receipt_dir": raw,
            "availability": StoredPathAvailability.UNAVAILABLE.value,
            "reason_code": f"RECEIPT_DIR_UNREADABLE:{exc.__class__.__name__}",
            "receipt_files": [],
            "receipt_file_count": 0,
        }

    if not is_dir:
        return {
            "receipt_dir": raw,
            "availability": StoredPathAvailability.UNAVAILABLE.value,
            "reason_code": "RECEIPT_DIR_MISSING",
            "receipt_files": [],
            "receipt_file_count": 0,
        }

    try:
        files = sorted(
            file_path.name
            for file_path in path.glob("item9-prospective-*.json")
            if file_path.is_file()
        )
    except OSError as exc:
        return {
            "receipt_dir": raw,
            "availability": StoredPathAvailability.UNAVAILABLE.value,
            "reason_code": f"RECEIPT_DIR_UNREADABLE:{exc.__class__.__name__}",
            "receipt_files": [],
            "receipt_file_count": 0,
        }
    return {
        "receipt_dir": raw,
        "availability": StoredPathAvailability.AVAILABLE.value,
        "receipt_file_count": len(files),
        "receipt_files": files,
        "receipt_epochs": sorted(epochs_from_item9_receipt_filenames(files)),
    }


__all__ = [
    "COLLECTOR_LOG_STALE_AFTER_SECONDS",
    "DEFAULT_ITEM9_COLLECTOR_LOG_REL",
    "ITEM9_COLLECTOR_LOG_ENV",
    "StoredPathAvailability",
    "StoredPathResolution",
    "analyze_item9_collect_log_gaps",
    "analyze_item9_receipt_directory",
    "classify_stored_path",
    "epochs_from_item9_receipt_filenames",
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
