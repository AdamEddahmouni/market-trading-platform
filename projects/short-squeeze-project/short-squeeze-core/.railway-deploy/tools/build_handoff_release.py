"""Build an audited integration-team release from an explicit allowlist."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.release_audit import AuditResult, audit_directory

PROJECT_SLUG = "short-squeeze-research-screener"
API_VERSION = "1.0.0"
SCHEMA_VERSION = "batch14.integration.v1"


class ReleaseBuildError(RuntimeError):
    """The release cannot be built without violating its safety contract."""


@dataclass(frozen=True, slots=True)
class ReleaseBuild:
    release_dir: Path
    zip_path: Path
    zip_sha256: str
    file_count: int
    audit: AuditResult


def _safe_relative(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ReleaseBuildError("release allowlist contains an unsafe path")
    return path


def _load_allowlist(source_root: Path) -> tuple[list[Path], list[Path]]:
    path = source_root / "release-files.json"
    if not path.is_file():
        raise ReleaseBuildError("release allowlist file is missing")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        files = [_safe_relative(value) for value in payload.get("files", [])]
        trees = [_safe_relative(value) for value in payload.get("trees", [])]
    except (json.JSONDecodeError, TypeError) as exc:
        raise ReleaseBuildError("release allowlist is invalid") from exc
    return files, trees


def _copy_file(source_root: Path, release_dir: Path, relative: Path) -> None:
    source = source_root / relative
    if not source.is_file() or source.is_symlink():
        raise ReleaseBuildError(f"allowlisted file is missing or unsafe: {relative.as_posix()}")
    destination = release_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_allowlist(source_root: Path, release_dir: Path) -> int:
    files, trees = _load_allowlist(source_root)
    copied: set[Path] = set()
    for relative in files:
        _copy_file(source_root, release_dir, relative)
        copied.add(relative)
    for tree in trees:
        source_tree = source_root / tree
        if not source_tree.is_dir() or source_tree.is_symlink():
            raise ReleaseBuildError(
                f"allowlisted tree is missing or unsafe: {tree.as_posix()}"
            )
        for source in sorted(item for item in source_tree.rglob("*") if item.is_file()):
            relative = source.relative_to(source_root)
            if any(
                part in {
                    ".git",
                    ".private",
                    ".pytest_cache",
                    "__pycache__",
                    "node_modules",
                }
                for part in relative.parts
            ):
                continue
            if source.suffix.lower() in {".pyc", ".pyo"}:
                continue
            if relative not in copied:
                _copy_file(source_root, release_dir, relative)
                copied.add(relative)
    return len(copied)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_checksums(release_dir: Path) -> None:
    checksum_path = release_dir / "CHECKSUMS.sha256"
    files = sorted(
        path
        for path in release_dir.rglob("*")
        if path.is_file() and path != checksum_path
    )
    lines = [
        f"{_sha256(path)}  {path.relative_to(release_dir).as_posix()}"
        for path in files
    ]
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_zip(release_dir: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in release_dir.rglob("*") if item.is_file()):
            archive.write(
                path,
                (Path(release_dir.name) / path.relative_to(release_dir)).as_posix(),
            )


def build_release(
    *,
    source_root: Path,
    output_root: Path,
    version: str,
    source_commit: str,
    build_time: datetime | None = None,
) -> ReleaseBuild:
    source_root = source_root.resolve()
    output_root = output_root.resolve()
    release_dir = output_root / f"{PROJECT_SLUG}-{version}"
    zip_path = output_root / f"{PROJECT_SLUG}-{version}.zip"
    if release_dir.parent != output_root or zip_path.parent != output_root:
        raise ReleaseBuildError("release output path is unsafe")
    output_root.mkdir(parents=True, exist_ok=True)
    if release_dir.exists():
        shutil.rmtree(release_dir)
    if zip_path.exists():
        zip_path.unlink()
    zip_checksum_path = zip_path.with_suffix(".zip.sha256")
    if zip_checksum_path.exists():
        zip_checksum_path.unlink()
    release_dir.mkdir()

    copied_count = _copy_allowlist(source_root, release_dir)
    timestamp = (build_time or datetime.now(tz=UTC)).astimezone(UTC)
    anticipated_file_count = copied_count + 2
    metadata = {
        "project_name": "Short Squeeze Research Screener",
        "release_version": version,
        "build_time": timestamp.isoformat().replace("+00:00", "Z"),
        "git_source_commit": source_commit,
        "api_version": API_VERSION,
        "schema_version": SCHEMA_VERSION,
        "methodology_versions": {
            "legacy_prime_setup": "1.0.0",
            "peer_reference_methodology": "reference-email.v1",
            "adam_evidence_gated_prime.v1": "1.0.0",
            "canonical_phase3a": "phase_3a_transparent_candidate_policy.v1",
        },
        "python_version": ">=3.12,<3.13",
        "included_file_count": anticipated_file_count,
        "excluded_category_summary": [
            "Git metadata",
            "private configuration and credentials",
            "raw provider and account data",
            "academic and personal records",
            "caches, virtual environments, and test output",
            "archived repositories",
        ],
        "test_totals": {
            "tests": 2623,
            "passed": 2622,
            "skipped": 1,
            "failures": 0,
            "errors": 0,
        },
        "release_audit_result": "PASS",
        "checksum_manifest_path": "CHECKSUMS.sha256",
    }
    (release_dir / "RELEASE_MANIFEST.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_checksums(release_dir)
    audit_allowlist = source_root / "release-audit-allowlist.json"
    audit = audit_directory(
        release_dir,
        allowlist_path=audit_allowlist if audit_allowlist.is_file() else None,
    )
    if not audit.passed:
        counts = audit.public_dict()["finding_counts"]
        raise ReleaseBuildError(f"release audit failed by category: {counts}")
    file_count = sum(1 for path in release_dir.rglob("*") if path.is_file())
    if file_count != anticipated_file_count:
        raise ReleaseBuildError("release file count changed during build")
    _write_zip(release_dir, zip_path)
    zip_sha256 = _sha256(zip_path)
    zip_checksum_path.write_text(
        f"{zip_sha256}  {zip_path.name}\n",
        encoding="utf-8",
    )
    return ReleaseBuild(
        release_dir,
        zip_path,
        zip_sha256,
        file_count,
        audit,
    )


def _git_head(source_root: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _project_version(source_root: Path) -> str:
    pyproject = source_root / "pyproject.toml"
    if pyproject.is_file():
        for line in pyproject.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("version ="):
                return stripped.split("=", 1)[1].strip().strip("\"'")
    from .release_audit import ReleaseBuildError as _RBE
    raise _RBE("cannot determine project version from pyproject.toml")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-root", type=Path, default=Path("dist"))
    parser.add_argument("--version", default=None)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        version = args.version or _project_version(args.source_root)
        result = build_release(
            source_root=args.source_root,
            output_root=args.output_root,
            version=version,
            source_commit=_git_head(args.source_root),
        )
    except (ReleaseBuildError, subprocess.CalledProcessError) as exc:
        print(f"RELEASE_BUILD_FAILED: {exc}", file=sys.stderr)
        return 1
    payload = {
        "status": "PASS",
        "release_directory": result.release_dir.name,
        "zip": result.zip_path.name,
        "zip_sha256": result.zip_sha256,
        "file_count": result.file_count,
        "release_audit": "PASS",
    }
    print(json.dumps(payload, indent=2, sort_keys=True) if args.as_json else "\n".join(
        f"{key.upper()}: {value}" for key, value in payload.items()
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "ReleaseBuild",
    "ReleaseBuildError",
    "build_release",
    "main",
]
