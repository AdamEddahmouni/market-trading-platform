"""BUILD 26 linkage integrity (BUILD 27)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from market_platform_foundation.git_ref import read_git_head, read_remote_ref, repo_root

from .spec import BUILD26_BRANCH


@dataclass(frozen=True)
class Build26IntegrityResult:
    status: str
    build26_head: str
    manifest_present: bool
    details: dict[str, object]


def verify_build26_integrity(expected_head: str | None = None) -> Build26IntegrityResult:
    head = (
        expected_head
        or read_remote_ref("origin", BUILD26_BRANCH)
        or read_git_head(start=repo_root())
        or ""
    )
    root = repo_root()
    manifest_path = root / "artifacts" / "forward-qualification" / "BUILD26_RUN_MANIFEST.json"
    manifest_present = manifest_path.is_file()
    details: dict[str, object] = {}
    if manifest_present:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        details["manifest_source_head"] = manifest.get("source_head")
        details["qualification_spec_id"] = manifest.get("qualification_spec_id")
    status = "PASS" if head and manifest_present else "FAIL"
    return Build26IntegrityResult(
        status=status,
        build26_head=head,
        manifest_present=manifest_present,
        details=details,
    )
