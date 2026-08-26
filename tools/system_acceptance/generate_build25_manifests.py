"""Generate BUILD 25 release-candidate manifests and file hashes."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from market_platform_foundation.intelligence.system_acceptance import (
    build_acceptance_spec,
    contract_inventory_hash,
    run_acceptance,
    system_acceptance_report_v1_to_dict,
    system_acceptance_spec_v1_to_dict,
)

EXCLUDE_PREFIXES = (
    ".git/",
    ".venv/",
    "node_modules/",
    "__pycache__/",
    ".pytest_cache/",
    ".private/",
    ".local/",
    ".cursor/",
    "data/",
)

SCIENTIFIC_GLOBS = (
    "src/market_platform_foundation/intelligence/**",
    "tests/intelligence/**",
    "docs/engineering/SYSTEM_ACCEPTANCE_BUILD25.md",
    "artifacts/system-acceptance/**",
    "tools/system_acceptance/**",
)


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip())


def git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def build24_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "origin/cloud/build-24-controlled-adaptation"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


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
    for prefix in EXCLUDE_PREFIXES:
        if normalized.startswith(prefix) or f"/{prefix}" in f"/{normalized}/":
            return True
    return False


def is_scientific_file(relative: str) -> bool:
    normalized = relative.replace("\\", "/")
    prefixes = (
        "src/market_platform_foundation/intelligence/",
        "tests/intelligence/",
        "docs/engineering/SYSTEM_ACCEPTANCE_BUILD25.md",
        "artifacts/system-acceptance/",
        "tools/system_acceptance/",
    )
    return any(normalized.startswith(p) for p in prefixes)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    root = repo_root()
    candidate_head = git_head(root)
    source_head = build24_head(root)
    spec = build_acceptance_spec(source_build_head=source_head)
    report = run_acceptance(source_head=source_head, candidate_head=candidate_head)

    out_dir = root / "artifacts" / "system-acceptance"
    out_dir.mkdir(parents=True, exist_ok=True)

    files: list[dict[str, object]] = []
    for relative in sorted(list_tracked_files(root)):
        if should_exclude(relative) or not is_scientific_file(relative):
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

    hash_manifest_path = out_dir / "BUILD25_FILE_HASHES.json"
    hash_manifest = {
        "schema_version": "1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": "sha256",
        "file_count": len(files),
        "excluded_categories": list(EXCLUDE_PREFIXES),
        "files": files,
    }
    hash_manifest_path.write_text(json.dumps(hash_manifest, indent=2) + "\n", encoding="utf-8")

    rc_manifest_path = out_dir / "BUILD25_RC_MANIFEST.json"
    rc_manifest = {
        "schema_version": "1",
        "build_frontier": "BUILD_25_SYSTEM_ACCEPTANCE_FREEZE",
        "branch": "cloud/build-25-system-acceptance-freeze",
        "source_build_24_head": source_head,
        "candidate_head": candidate_head,
        "python_version": platform.python_version(),
        "acceptance_spec_id": spec.acceptance_spec_id,
        "acceptance_report_id": report.acceptance_report_id,
        "acceptance_disposition": report.overall_disposition.value,
        "contract_inventory_hash": contract_inventory_hash(),
        "file_hash_manifest": "artifacts/system-acceptance/BUILD25_FILE_HASHES.json",
        "known_limitations_ref": "artifacts/system-acceptance/BUILD25_KNOWN_LIMITATIONS.md",
        "acceptance_spec": system_acceptance_spec_v1_to_dict(spec),
        "acceptance_report": system_acceptance_report_v1_to_dict(report),
    }
    rc_manifest_path.write_text(json.dumps(rc_manifest, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {hash_manifest_path} ({len(files)} files)")
    print(f"Wrote {rc_manifest_path}")
    print(f"Disposition: {report.overall_disposition.value}")
    return 0 if not report.blocking_failures else 1


if __name__ == "__main__":
    sys.exit(main())
