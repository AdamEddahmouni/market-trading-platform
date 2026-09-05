"""Generate SHA-256 file hash manifest for cloud handoff verification."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


EXCLUDE_PREFIXES = (
    ".git/",
    ".venv/",
    "node_modules/",
    "__pycache__/",
    ".pytest_cache/",
    ".private/",
    ".local/",
    "data/",
)


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip())


def list_tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return [p.decode("utf-8") for p in result.stdout.split(b"\0") if p]


def should_exclude(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    if normalized.startswith("."):
        for prefix in EXCLUDE_PREFIXES:
            if normalized.startswith(prefix.lstrip("/")) or f"/{prefix}" in f"/{normalized}/":
                return True
    for prefix in EXCLUDE_PREFIXES:
        if normalized.startswith(prefix) or f"/{prefix}" in f"/{normalized}/":
            return True
    return False


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    root = repo_root()
    files: list[dict[str, object]] = []

    for relative in sorted(list_tracked_files(root)):
        if should_exclude(relative):
            continue
        path = root / relative
        if not path.is_file():
            continue
        files.append(
            {
                "path": relative.replace("\\", "/"),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository_root": str(root),
        "algorithm": "sha256",
        "file_count": len(files),
        "files": files,
    }

    out_path = root / "artifacts" / "cloud-handoff" / "CLOUD_FILE_HASHES.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(files)} file hashes to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
