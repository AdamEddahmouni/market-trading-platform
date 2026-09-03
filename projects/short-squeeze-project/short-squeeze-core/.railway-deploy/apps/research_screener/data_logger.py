"""Ephemeral data logging for research and learning.

Every screener snapshot and refresh cycle is written to a timestamped JSONL file
inside ``data/screener_logs/``. The format is one JSON object per line, making it
easy to parse and replay later.

This module makes no guarantees about write durability, and log files are never
used by the evaluation engine. They exist purely for post-hoc analysis and learning.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _log_dir() -> Path:
    from .paths import repository_root

    return repository_root() / "data" / "screener_logs"


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _session_id() -> str:
    return os.environ.get(
        "SQUEEZE_LOG_SESSION",
        datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S"),
    )


_log_lock = threading.Lock()
_log_enabled = os.environ.get("SQUEEZE_DATA_LOG", "true").lower() not in (
    "false", "0", "no", "off",
)

# --- Rotation configuration (env-controllable) --------------------------------

#: Maximum number of log files in the directory before rotation triggers.
#: When exceeded, the oldest files are archived to a .tar.gz.
_ROTATE_MAX_FILES = int(os.environ.get("SQUEEZE_LOG_MAX_FILES", "200"))

#: Maximum total size (MB) of the log directory before rotation triggers.
_ROTATE_MAX_DIR_MB = int(os.environ.get("SQUEEZE_LOG_MAX_DIR_SIZE_MB", "500"))

#: Subdirectory within the log directory where archives are stored.
_ARCHIVE_SUBDIR = "archive"

#: Throttle: check rotation every N writes (avoids directory scan on every call).
_ROTATE_CHECK_INTERVAL = 20

#: Write counter for throttling rotation checks.
_rotate_write_count = 0


# --- Rotation helpers ---------------------------------------------------------


def rotate_logs() -> dict[str, Any]:
    """Public entry point for manual log rotation.

    Archives the oldest log files to a compressed .tar.gz if the directory
    exceeds the configured thresholds (``SQUEEZE_LOG_MAX_FILES`` or
    ``SQUEEZE_LOG_MAX_DIR_SIZE_MB``).  Returns a summary dict.

    Called automatically every ``_ROTATE_CHECK_INTERVAL`` writes, but can
    also be invoked manually (e.g. from an admin endpoint or cron job).
    """
    with _log_lock:
        return _rotate_logs()


def _rotate_logs() -> dict[str, Any]:
    """Archive the oldest log files to a compressed .tar.gz.

    Identifies files that push the directory over the configured thresholds
    (file count or total size), creates a timestamped archive in the archive
    subdirectory, and removes the originals.

    Returns a summary dict suitable for logging and debugging.

    Must be called while ``_log_lock`` is held.
    """
    import gzip
    import tarfile

    directory = _log_dir()
    if not directory.exists():
        return {"rotated": 0, "reason": "Directory does not exist."}

    current_session = _session_id()

    # Gather all regular files (exclude archive dir and current session)
    archive_dir = directory / _ARCHIVE_SUBDIR
    files: list[tuple[float, Path, int]] = []  # (mtime, path, size)
    total_size = 0
    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        if entry.parent == archive_dir:
            continue
        # Never rotate files belonging to the current session
        if current_session in entry.name:
            continue
        stat = entry.stat()
        files.append((stat.st_mtime, entry, stat.st_size))
        total_size += stat.st_size

    # Check thresholds
    max_bytes = _ROTATE_MAX_DIR_MB * 1024 * 1024
    exceeded_files = len(files) > _ROTATE_MAX_FILES
    exceeded_size = total_size > max_bytes
    if not exceeded_files and not exceeded_size:
        return {
            "rotated": 0,
            "file_count": len(files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "thresholds_ok": True,
        }

    # Sort oldest-first
    files.sort(key=lambda t: t[0])
    keep_target = int(_ROTATE_MAX_FILES * 0.75)
    keep_target_bytes = int(max_bytes * 0.75)

    # Select files to archive: walk oldest-first, stop when both thresholds
    # would be satisfied by the remaining files.
    to_archive: list[tuple[float, Path, int]] = []
    remaining_count = len(files)
    remaining_size = total_size
    for item in files:
        remaining_count -= 1
        remaining_size -= item[2]
        to_archive.append(item)
        # Stop when we'd be under both limits
        if remaining_count <= keep_target and remaining_size <= keep_target_bytes:
            break

    if not to_archive:
        return {"rotated": 0, "reason": "Nothing to archive after threshold check."}

    # Create archive
    archive_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    archive_name = f"log_archive_{_session_id()}_{ts}.tar.gz"
    archive_path = archive_dir / archive_name

    try:
        with gzip.open(archive_path, "wb") as gz:
            with tarfile.open(fileobj=gz, mode="w|") as tar:
                for _mtime, filepath, _size in to_archive:
                    tar.add(filepath, arcname=filepath.name)
    except Exception as exc:
        return {"rotated": 0, "error": f"Archive creation failed: {exc}"}

    # Remove original files
    removed = 0
    removed_size = 0
    for _mtime, filepath, _size in to_archive:
        try:
            removed_size += filepath.stat().st_size
            filepath.unlink()
            removed += 1
        except Exception:
            pass

    return {
        "rotated": removed,
        "archived_size_mb": round(removed_size / (1024 * 1024), 2),
        "archive_path": str(archive_path),
        "archive_name": archive_name,
        "remaining_files": len(files) - removed,
        "trigger": (
            "file_count" if exceeded_files else "dir_size"
        ),
        "at": _now_iso(),
    }


def _maybe_rotate_logs() -> None:
    """Check rotation thresholds periodically and archive if exceeded.

    Throttled to run only every ``_ROTATE_CHECK_INTERVAL`` writes to avoid
    a directory scan on every single log call.  On the check interval, if
    either the file count or total directory size exceeds the configured
    limits, the oldest files are archived and removed.
    """
    global _rotate_write_count
    _rotate_write_count += 1
    if _rotate_write_count % _ROTATE_CHECK_INTERVAL != 0:
        return
    with _log_lock:
        try:
            result = _rotate_logs()
            if result.get("rotated", 0) > 0:
                # Write a brief rotation notice to a dedicated file (not to any
                # specific session file, since those may have just been archived).
                directory = _log_dir()
                directory.mkdir(parents=True, exist_ok=True)
                notice_path = directory / "rotation_events.jsonl"
                with open(notice_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(result, default=str) + "\n")
        except Exception as exc:
            # Rotation failure must never crash the application. Logging here
            # would be circular, so we write a one-liner to stderr.
            import sys
            print(
                f"[squeeze] Log rotation check failed: {exc}",
                file=sys.stderr,
            )


def log_screener_snapshot(rows: list[dict[str, Any]], *, label: str = "snapshot") -> None:
    """Append one screener snapshot to the session log file."""
    if not _log_enabled or not rows:
        return
    directory = _log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"screener_{_session_id()}.jsonl"
    payload = {
        "type": "screener_snapshot",
        "label": label,
        "at": _now_iso(),
        "row_count": len(rows),
        "rows": [
            {
                "symbol": row.get("symbol"),
                "pressure": row.get("pressure"),
                "ignition": row.get("ignition"),
                "classification": (
                    (row.get("methodologies") or [{}])[0].get("classification")
                    if row.get("methodologies") else None
                ),
                "price": (row.get("fields", {}).get("last") or {}).get("value"),
                "percentage_change": (row.get("fields", {}).get("percentage_change") or {}).get("value"),
                "relative_volume": (row.get("fields", {}).get("relative_volume") or {}).get("value"),
                "short_float": (row.get("fields", {}).get("short_float") or {}).get("value"),
                "borrow_fee": (row.get("fields", {}).get("borrow_fee") or {}).get("value"),
                "news_count": (row.get("fields", {}).get("news_count") or {}).get("value"),
                "sentiment": (row.get("fields", {}).get("sentiment") or {}).get("value"),
                "market_data_mode": row.get("market_data_mode"),
                "freshness": row.get("freshness"),
            }
            for row in rows
        ],
    }
    with _log_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    _maybe_rotate_logs()


def log_refresh_event(summary: dict[str, Any]) -> None:
    """Log a refresh-cycle summary event."""
    if not _log_enabled:
        return
    directory = _log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"events_{_session_id()}.jsonl"
    payload = {
        "type": "refresh_cycle",
        "at": _now_iso(),
        "refreshed": summary.get("refreshed", 0),
        "total": summary.get("total", 0),
        "errors": summary.get("errors", []),
        "providers": summary.get("providers", {}),
    }
    with _log_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    _maybe_rotate_logs()


def log_provider_status(health: dict[str, Any]) -> None:
    """Log provider health check results."""
    if not _log_enabled:
        return
    directory = _log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"health_{_session_id()}.jsonl"
    payload = {
        "type": "provider_health",
        "at": _now_iso(),
        "providers": health.get("providers", []),
        "frozen_available": health.get("frozen_research_available"),
        "auto_refresh": health.get("auto_refresh"),
        "market_data_mode": health.get("market_data_mode"),
    }
    with _log_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    _maybe_rotate_logs()


def log_provider_raw(
    provider: str,
    data_type: str,
    raw_data: Any,
    *,
    context: str = "",
    success: bool = True,
    enrichment_details: dict[str, Any] | None = None,
    error: str | None = None,
) -> None:
    """Log a raw provider data capture with full provenance.

    This is the single entry point for capturing EVERY piece of external data
    the screener fetches — Finviz screener exports, NewsAPI/Finnhub headlines,
    Finnhub prices, SEC filings, enrichment mappings, etc.

    Each call writes one JSON line to ``raw_provider_{session_id}.jsonl``.
    The archive is meant to be replayable: every record carries a timestamp,
    provider name, data type, success flag, and the complete raw payload.
    """
    if not _log_enabled:
        return
    directory = _log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"raw_provider_{_session_id()}.jsonl"
    payload = {
        "type": "provider_raw",
        "at": _now_iso(),
        "provider": provider,
        "data_type": data_type,
        "context": context,
        "success": success,
        "raw_data": raw_data,
        "enrichment": enrichment_details,
        "error": error,
    }
    with _log_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    _maybe_rotate_logs()


def log_enrichment_event(
    provider: str,
    target: str,
    *,
    matched_count: int = 0,
    total_rows: int = 0,
    frozen_keys: list[str] | None = None,
) -> None:
    """Log a frozen-to-live enrichment pass.

    Records which provider enriched how many fields across how many rows,
    plus the specific frozen keys that received live data.
    """
    if not _log_enabled:
        return
    directory = _log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"raw_provider_{_session_id()}.jsonl"
    payload = {
        "type": "enrichment_event",
        "at": _now_iso(),
        "provider": provider,
        "target": target,
        "matched_count": matched_count,
        "total_rows": total_rows,
        "frozen_keys_enriched": frozen_keys or [],
    }
    with _log_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")
    _maybe_rotate_logs()


def log_full_snapshot(
    mode: str,
    rows: list[dict[str, Any]],
    *,
    provider_status: dict[str, Any] | None = None,
) -> None:
    """Log a complete point-in-time snapshot with all provider data.

    Unlike ``log_screener_snapshot`` which only captures summary fields,
    this records every field from every row so the snapshot can be replayed.
    """
    if not _log_enabled or not rows:
        return
    directory = _log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"full_snapshot_{_session_id()}.jsonl"
    payload = {
        "type": "full_snapshot",
        "at": _now_iso(),
        "mode": mode,
        "row_count": len(rows),
        "provider_status": provider_status,
        "rows": rows,
    }
    with _log_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, default=str) + "\n")


def resolve_archive_path(name: str) -> Path | None:
    """Resolve a safe path to an archive file within the archive directory.

    Validates that *name* does not contain path-traversal characters and
    resolves to a real file inside the archive directory.  Returns the
    resolved ``Path`` on success, ``None`` if the name is invalid or the
    file does not exist.

    This is the single entry point for archive path resolution — route
    handlers should use this instead of building paths from private internals.
    """
    if not name or ".." in name or "/" in name or "\\" in name:
        return None
    if not name.endswith(".tar.gz"):
        return None

    archive_dir = (_log_dir() / _ARCHIVE_SUBDIR).resolve()
    candidate = (archive_dir / name).resolve()

    # Ensure the resolved path is inside the archive directory
    if archive_dir not in candidate.parents:
        return None

    return candidate if candidate.is_file() else None


def list_archives() -> dict[str, Any]:
    """List all archived .tar.gz log files.

    Returns each archive's name, path, size in bytes, and the modification
    timestamp (ISO), plus a total count.
    """
    directory = _log_dir()
    archive_dir = directory / _ARCHIVE_SUBDIR
    archives: list[dict[str, Any]] = []
    total_size = 0

    if archive_dir.exists():
        for entry in archive_dir.iterdir():
            if not entry.is_file() or not entry.name.endswith(".tar.gz"):
                continue
            stat = entry.stat()
            total_size += stat.st_size
            archives.append({
                "name": entry.name,
                "path": str(entry),
                "size_bytes": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=UTC
                ).isoformat().replace("+00:00", "Z"),
            })

    archives.sort(key=lambda a: a["name"], reverse=True)
    return {
        "available": len(archives) > 0,
        "count": len(archives),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "archive_directory": str(archive_dir),
        "archives": archives,
        "generated_at": _now_iso(),
    }


def log_status(*, tail_lines: int = 20) -> dict[str, Any]:
    """Return a live summary of the current logging state.

    Returns the session ID, whether logging is enabled, the log directory path,
    and for each log file on disk: its name, size, line count, and the last
    *tail_lines* lines for real-time tailing.

    This endpoint is read by the integration team to verify that data is being
    captured without needing to SSH into the server or restart anything.
    """
    directory = _log_dir()
    session = _session_id()

    _MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB — skip anything larger
    files: list[dict[str, Any]] = []
    if directory.exists():
        for entry in sorted(directory.iterdir(), key=lambda p: p.name):
            if not entry.is_file():
                continue
            stat = entry.stat()
            if stat.st_size > _MAX_FILE_BYTES:
                files.append({
                    "name": entry.name,
                    "path": str(entry),
                    "size_bytes": stat.st_size,
                    "line_count": -1,
                    "modified_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=UTC
                    ).isoformat().replace("+00:00", "Z"),
                    "tail_lines_requested": tail_lines,
                    "tail": [],
                    "skipped": True,
                    "skip_reason": f"File exceeds {_MAX_FILE_BYTES // (1024 * 1024)} MB limit.",
                })
                continue
            try:
                lines = entry.read_text(encoding="utf-8").splitlines()
                line_count = len(lines)
                tail = lines[-min(tail_lines, line_count):] if line_count > 0 else []
                # Try to parse the last few entries as JSON for readability
                tail_parsed: list[Any] = []
                for line in tail:
                    try:
                        tail_parsed.append(json.loads(line))
                    except ValueError:
                        tail_parsed.append(line)
            except Exception:
                line_count = -1
                tail_parsed = []

            files.append({
                "name": entry.name,
                "path": str(entry),
                "size_bytes": stat.st_size,
                "line_count": line_count,
                "modified_at": datetime.fromtimestamp(
                    stat.st_mtime, tz=UTC
                ).isoformat().replace("+00:00", "Z"),
                "tail_lines_requested": tail_lines,
                "tail": tail_parsed,
            })

    return {
        "logging_enabled": _log_enabled,
        "session_id": session,
        "log_directory": str(directory),
        "file_count": len(files),
        "files": files,
        "generated_at": _now_iso(),
        "rotation": {
            "configured_thresholds": {
                "max_files": _ROTATE_MAX_FILES,
                "max_dir_size_mb": _ROTATE_MAX_DIR_MB,
            },
            "current": {
                "file_count": len(files),
                "total_size_mb": round(
                    sum(f.get("size_bytes", 0) for f in files) / (1024 * 1024),
                    2,
                ),
                "usage_pct_files": round(len(files) / max(_ROTATE_MAX_FILES, 1) * 100, 1),
            },
            "archive_directory": str(directory / _ARCHIVE_SUBDIR),
            "check_interval_writes": _ROTATE_CHECK_INTERVAL,
            "rotation_enabled": _log_enabled,
        },
    }


def _parse_iso_ts(value: str) -> datetime | None:
    """Parse an ISO timestamp string into a UTC datetime. Returns None on failure."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except (ValueError, TypeError):
        return None


def _scan_full_snapshots(
    session: str | None = None,
) -> list[tuple[datetime, Path, dict[str, Any]]]:
    """Scan all ``full_snapshot_*.jsonl`` files and return every snapshot entry.

    Returns a flat list of ``(parsed_at, file_path, entry)`` tuples sorted by
    timestamp ascending.  If *session* is given, only files matching that
    session ID are scanned.
    """
    directory = _log_dir()
    if not directory.exists():
        return []

    results: list[tuple[datetime, Path, dict[str, Any]]] = []
    pattern = f"full_snapshot_{session or '*'}.jsonl"
    for path in sorted(directory.glob(pattern)):
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if entry.get("type") != "full_snapshot":
                    continue
                at_raw = entry.get("at", "")
                parsed = _parse_iso_ts(at_raw)
                if parsed is None:
                    continue
                results.append((parsed, path, entry))
        except Exception:
            continue

    results.sort(key=lambda t: t[0])
    return results


def log_replay(*, at: str | None = None, session: str | None = None) -> dict[str, Any]:
    """Reconstruct the frozen screener view at a past point in time.

    Scans ``full_snapshot_*.jsonl`` archives and returns the complete snapshot
    whose timestamp is closest to (but not after) *at*.  If *at* is None,
    the most recent snapshot is returned.

    The returned dict includes replay metadata (requested time, actual snapshot
    time, delta, source file) alongside the full snapshot payload.
    """
    snapshots = _scan_full_snapshots(session=session)

    if not snapshots:
        return {
            "available": False,
            "reason": (
                "No full_snapshot entries found in the log directory. "
                "Load the frozen screener page at least once to generate snapshots, "
                "then retry."
            ),
            "replay_at": at or "NOT_SPECIFIED",
            "snapshot_at": None,
            "delta_seconds": None,
        }

    snapshot_is_after_target = False
    if at is None:
        # Return the most recent snapshot
        matched_at, matched_path, entry = snapshots[-1]
    else:
        target = _parse_iso_ts(at)
        if target is None:
            return {
                "available": False,
                "reason": f"Could not parse timestamp {at!r}. Use ISO format, e.g. 2026-07-26T15:30:00Z.",
                "replay_at": at,
                "snapshot_at": None,
                "delta_seconds": None,
            }

        # Find the closest snapshot at or before the target
        best: tuple[datetime, Path, dict[str, Any]] | None = None
        for parsed_at, path, entry in snapshots:
            if parsed_at <= target:
                best = (parsed_at, path, entry)
            else:
                break

        if best is None:
            # All snapshots are after the target — return the earliest with a flag
            matched_at, matched_path, entry = snapshots[0]
            snapshot_is_after_target = True
        else:
            matched_at, matched_path, entry = best

    target_dt = _parse_iso_ts(at) if at else None
    delta = (target_dt - matched_at).total_seconds() if target_dt else None

    return {
        "available": True,
        "replay_at": at or "NOT_SPECIFIED (latest)",
        "snapshot_at": matched_at.isoformat().replace("+00:00", "Z"),
        "delta_seconds": round(delta, 1) if delta is not None else None,
        "exact_match": delta is not None and abs(delta) < 1.0,
        "snapshot_is_after_target": snapshot_is_after_target,
        "source_file": str(matched_path.name),
        "snapshot": entry,
    }


def log_replay_from_raw(
    *, at: str | None = None, session: str | None = None
) -> dict[str, Any]:
    """Reconstruct what raw provider data was available at a past point in time.

    Scans ``raw_provider_*.jsonl`` files and, for each symbol+provider
    combination, finds the most recent data entry at or before *at*.  Returns a
    per-symbol summary of what Finviz, NEWS, Finnhub, and SEC data would have
    been available for enrichment at that moment.

    Unlike ``log_replay`` which returns the exact displayed snapshot, this
    reconstructs the raw data pool — useful when checking whether a missing
    value was a provider failure or genuinely unavailable data.

    If *at* is None, uses the current time.
    """
    directory = _log_dir()
    if not directory.exists():
        return {"available": False, "reason": "Log directory not found."}

    target_dt = _parse_iso_ts(at) if at else datetime.now(tz=UTC)
    if target_dt is None:
        return {
            "available": False,
            "reason": f"Invalid timestamp {at!r}. Use ISO format.",
        }

    # Collect all matching provider_raw entries (not enrichment events — those
    # don't carry raw data and belong in a separate timeline).
    pattern = f"raw_provider_{session or '*'}.jsonl"
    entries: list[tuple[datetime, dict[str, Any]]] = []
    enrichment: list[dict[str, Any]] = []
    for path in sorted(directory.glob(pattern)):
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                entry_type = entry.get("type", "")
                if entry_type == "enrichment_event":
                    entry_at = _parse_iso_ts(entry.get("at", ""))
                    if entry_at is not None and entry_at <= target_dt:
                        enrichment.append(entry)
                    continue
                if entry_type != "provider_raw":
                    continue
                entry_at = _parse_iso_ts(entry.get("at", ""))
                if entry_at is None or entry_at > target_dt:
                    continue
                entries.append((entry_at, entry))
        except Exception:
            continue

    # Entries are sorted ascending — last write for each key automatically wins.
    entries.sort(key=lambda t: t[0])

    if not entries:
        return {
            "available": True,
            "replay_at": at or _now_iso(),
            "entry_count": 0,
            "enrichment_event_count": len(enrichment),
            "reason": (
                "No raw_provider entries found at or before the requested time."
            ),
            "by_symbol": {},
        }

    # Group by (context, provider, data_type) — last-write-wins (already sorted)
    latest: dict[str, dict[str, Any]] = {}
    for _entry_at, entry in entries:
        ctx = entry.get("context", "all") or "ALL_SYMBOLS"
        prov = entry.get("provider", "?")
        dtype = entry.get("data_type", "?")
        key = f"{ctx}|{prov}|{dtype}"
        latest[key] = {
            "at": entry.get("at"),
            "context": ctx,
            "provider": prov,
            "data_type": dtype,
            "success": entry.get("success"),
            "raw_data": entry.get("raw_data"),
            "error": entry.get("error"),
        }

    # Organise by symbol
    by_symbol: dict[str, dict[str, Any]] = {}
    for _key, val in latest.items():
        ctx = val["context"]
        symbol = "ALL_SYMBOLS" if ctx == "all" or not ctx else ctx
        if symbol not in by_symbol:
            by_symbol[symbol] = {"providers": []}
        by_symbol[symbol]["providers"].append(val)

    return {
        "available": True,
        "replay_at": at or _now_iso(),
        "replay_as_of": target_dt.isoformat().replace("+00:00", "Z"),
        "total_entries_scanned": len(entries),
        "unique_latest_entries": len(latest),
        "enrichment_event_count": len(enrichment),
        "symbol_count": len(by_symbol),
        "by_symbol": by_symbol,
    }


def log_replay_timeline(*, session: str | None = None) -> dict[str, Any]:
    """Return a timeline of all available snapshot timestamps.

    Useful for the integration team to pick a point in time for replay.
    Returns timestamps sorted ascending with the source file and mode.
    """
    snapshots = _scan_full_snapshots(session=session)

    points: list[dict[str, Any]] = []
    seen: set[str] = set()
    for parsed_at, path, entry in snapshots:
        ts = parsed_at.isoformat().replace("+00:00", "Z")
        if ts not in seen:
            seen.add(ts)
            points.append({
                "at": ts,
                "mode": entry.get("mode", "UNKNOWN"),
                "row_count": entry.get("row_count", 0),
                "source_file": str(path.name),
            })

    return {
        "point_count": len(points),
        "session_filter": session,
        "points": points,
        "generated_at": _now_iso(),
    }


__all__ = [
    "list_archives",
    "log_enrichment_event",
    "log_full_snapshot",
    "log_provider_raw",
    "log_provider_status",
    "log_refresh_event",
    "log_replay",
    "log_replay_from_raw",
    "log_replay_timeline",
    "log_screener_snapshot",
    "log_status",
    "resolve_archive_path",
    "rotate_logs",
]
