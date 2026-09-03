"""Index file-backed observational captures. Ticks stay on disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .paths import capture_scan_roots
from .repository import (
    CAPTURE_AVAILABLE,
    CAPTURE_CORRUPT,
    CAPTURE_INCOMPATIBLE,
    CAPTURE_MISSING,
    LocalStateRepository,
)


def _status_for_manifest(path: Path) -> tuple[str, dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return CAPTURE_CORRUPT, {}
    if not isinstance(raw, dict):
        return CAPTURE_CORRUPT, {}
    events_name = raw.get("events_path") or f"{raw.get('capture_id', path.stem)}.jsonl"
    events_path = path.parent / str(events_name)
    rotation = raw.get("rotation_files") or [str(events_name)]
    missing = [name for name in rotation if not (path.parent / str(name)).is_file()]
    if missing and not events_path.is_file():
        return CAPTURE_MISSING, raw
    versions = raw.get("schema_versions") or []
    if versions and any(int(version) > 1 for version in versions if str(version).isdigit()):
        return CAPTURE_INCOMPATIBLE, raw
    return CAPTURE_AVAILABLE, raw


def refresh_capture_catalog(repo: LocalStateRepository) -> list[dict[str, Any]]:
    seen: set[str] = set()
    indexed: list[dict[str, Any]] = []
    for root in capture_scan_roots():
        if not root.is_dir():
            continue
        for manifest in sorted(root.glob("*.manifest.json")):
            status, raw = _status_for_manifest(manifest)
            capture_id = str(raw.get("capture_id") or manifest.stem.replace(".manifest", ""))
            if capture_id in seen:
                continue
            seen.add(capture_id)
            events_name = raw.get("events_path")
            events_path = str((manifest.parent / str(events_name)).resolve()) if events_name else None
            bytes_on_disk = 0
            if events_path and Path(events_path).is_file():
                bytes_on_disk = Path(events_path).stat().st_size
            row = {
                "bytes_on_disk": bytes_on_disk,
                "capture_id": capture_id,
                "end_time_ns": raw.get("end_time_ns"),
                "events_path": events_path,
                "instruments": raw.get("instruments") or [],
                "manifest_path": str(manifest.resolve()),
                "provider": raw.get("provider") or "moomoo",
                "quality_summary": raw.get("quality_summary") or {},
                "start_time_ns": raw.get("start_time_ns"),
                "status": status,
            }
            repo.upsert_capture(row)
            indexed.append(row)
    return indexed
