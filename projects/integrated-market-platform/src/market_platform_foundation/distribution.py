"""Deterministic standard-library-only Phase 0 distribution builder."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

from .canonical import canonical_bytes, load_json_strict, sha256_bytes

_TOP_FILES = (
    ".gitattributes",
    ".gitignore",
    "README.md",
    "phase0-dependency-lock.json",
)
_TREES = (
    "docs/architecture",
    "docs/research",
    "docs/roadmap",
    "docs/superpowers",
    "manifests/phase0",
    "src/market_platform_foundation",
    "tests/phase0",
    "tools/phase0",
)
_EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "build",
    "data",
    "dist",
    "node_modules",
}
_MAX_FILE_BYTES = 10 * 1024 * 1024
_SENSITIVE_NAME_EXCEPTIONS = {
    "src/market_platform_foundation/credential_audit.py",
    "src/market_platform_foundation/finviz/credential_manager.py",
    "tests/phase0/test_credential_audit.py",
}


def validate_lock(path: Path) -> dict[str, object]:
    value = load_json_strict(path)
    if not isinstance(value, dict):
        raise ValueError("dependency lock must be an object")
    if value.get("implementation") != "CPython" or value.get("major_minor") != "3.11":
        raise ValueError("only CPython 3.11 is authorized")
    third_party = value.get("third_party")
    if not isinstance(third_party, list):
        raise ValueError("third_party must be a list")
    prohibited = value.get("prohibited_patterns", [])
    authorized = {str(item) for item in third_party}
    matches = [
        str(item)
        for item in third_party
        if any(p in str(item) for p in prohibited)
    ]
    groups = value.get("distribution_groups", {})
    if isinstance(groups, dict):
        for group_name, group in groups.items():
            if not isinstance(group, dict):
                continue
            group_packages = group.get("third_party") or []
            if not isinstance(group_packages, list):
                raise ValueError(f"distribution group {group_name} third_party must be a list")
            for package in group_packages:
                package_name = str(package)
                if package_name not in authorized:
                    matches.append(f"unauthorized:{package_name}")
                if any(pattern in package_name for pattern in prohibited):
                    matches.append(package_name)
    return {
        "prohibited_matches": sorted(set(matches)),
        "third_party_count": len(third_party),
    }


def _is_reparse(path: Path) -> bool:
    return path.is_symlink() or bool(getattr(os.lstat(path), "st_file_attributes", 0) & 0x400)


def _selected_files(root: Path) -> list[Path]:
    root = root.resolve()
    selected: list[Path] = []
    for name in _TOP_FILES:
        path = root / name
        if path.is_file():
            selected.append(path)
    for relative_tree in _TREES:
        tree = root / relative_tree
        if not tree.exists():
            continue
        for path in tree.rglob("*"):
            relative = path.relative_to(root)
            if any(part in _EXCLUDED_PARTS or part.startswith(".venv") for part in relative.parts):
                continue
            if _is_reparse(path):
                raise ValueError(f"reparse or symlink path rejected: {relative.as_posix()}")
            if not path.is_file():
                continue
            relative_name = relative.as_posix()
            sensitive_name = (
                path.name.startswith(".env")
                or "credential" in path.name.lower()
                or "secret" in path.name.lower()
            )
            if sensitive_name and relative_name not in _SENSITIVE_NAME_EXCEPTIONS:
                raise ValueError("sensitive path rejected by distribution policy")
            if path.suffix.lower() in {".log", ".pyc", ".pyo"}:
                continue
            if path.stat().st_size >= _MAX_FILE_BYTES:
                raise ValueError("large file rejected by distribution policy")
            resolved = path.resolve()
            if root != resolved and root not in resolved.parents:
                raise ValueError("distribution path escapes repository root")
            selected.append(path)
    return sorted(set(selected), key=lambda path: path.relative_to(root).as_posix())


def build_distribution(root: Path, output_dir: Path) -> dict[str, object]:
    root = root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    files = _selected_files(root)
    rows = [
        {
            "byte_length": path.stat().st_size,
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_bytes(path.read_bytes()),
        }
        for path in files
    ]
    manifest = {"files": rows, "format": "phase0-source-manifest-v1"}
    manifest_bytes = canonical_bytes(manifest)
    manifest_path = output_dir / "source-manifest.json"
    manifest_path.write_bytes(manifest_bytes)
    archive_path = output_dir / "market-platform-phase0-offline.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for path in files:
            relative = path.relative_to(root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, path.read_bytes())
    archive_bytes = archive_path.read_bytes()
    return {
        "archive_path": archive_path.name,
        "archive_sha256": sha256_bytes(archive_bytes),
        "file_count": len(rows),
        "manifest_path": manifest_path.name,
        "manifest_sha256": sha256_bytes(manifest_bytes),
    }
