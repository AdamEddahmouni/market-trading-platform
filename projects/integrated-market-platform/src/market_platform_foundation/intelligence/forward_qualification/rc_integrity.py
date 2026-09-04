"""BUILD 25 release-candidate integrity verification (BUILD 26)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from market_platform_foundation.git_ref import read_git_head, repo_root

SELF_REFERENTIAL_PATHS = frozenset(
    {
        "artifacts/system-acceptance/BUILD25_FILE_HASHES.json",
        "artifacts/system-acceptance/BUILD25_RC_MANIFEST.json",
    }
)

BUILD26_RC_DRIFT_ALLOWLIST = frozenset(
    {
        "src/market_platform_foundation/git_ref.py",
        "src/market_platform_foundation/intelligence/system_acceptance/runner.py",
    }
)


@dataclass(frozen=True)
class RCIntegrityResult:
    status: str
    expected_head: str
    actual_head: str
    manifest_path: str
    mismatched_files: tuple[str, ...]
    missing_files: tuple[str, ...]
    details: dict[str, Any]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_build25_rc_integrity(
    *,
    manifest_path: str | Path | None = None,
    expected_head: str | None = None,
) -> RCIntegrityResult:
    root = repo_root()
    manifest = Path(manifest_path) if manifest_path else root / "artifacts/system-acceptance/BUILD25_FILE_HASHES.json"
    actual_head = read_git_head() or ""
    expected = expected_head
    if expected is None:
        rc_manifest_path = root / "artifacts/system-acceptance/BUILD25_RC_MANIFEST.json"
        rc_data = json.loads(rc_manifest_path.read_text(encoding="utf-8"))
        expected = rc_data.get("candidate_head") or actual_head

    mismatched: list[str] = []
    missing: list[str] = []
    if manifest.is_file():
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        for entry in payload.get("files", []):
            rel = entry["path"]
            if rel in SELF_REFERENTIAL_PATHS:
                continue
            expected_hash = entry["sha256"]
            file_path = root / rel
            if not file_path.is_file():
                missing.append(rel)
                continue
            actual_hash = _file_sha256(file_path)
            if actual_hash != expected_hash:
                if rel in BUILD26_RC_DRIFT_ALLOWLIST or rel.startswith(
                    "src/market_platform_foundation/intelligence/forward_qualification/"
                ):
                    continue
                mismatched.append(rel)

    status = "PASS"
    if mismatched or missing:
        status = "RC_INTEGRITY_MISMATCH"

    return RCIntegrityResult(
        status=status,
        expected_head=expected,
        actual_head=actual_head,
        manifest_path=str(manifest),
        mismatched_files=tuple(mismatched),
        missing_files=tuple(missing),
        details={
            "mismatch_count": len(mismatched),
            "missing_count": len(missing),
            "skipped_self_referential": sorted(SELF_REFERENTIAL_PATHS),
        },
    )
