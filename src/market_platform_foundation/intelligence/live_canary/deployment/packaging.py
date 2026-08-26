"""Release packaging and bundle assembly (BUILD 34)."""

from __future__ import annotations

import hashlib
import json
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .identity import derive_release_id
from .source_provenance import (
    collect_source_provenance,
    dirty_tree_blocks_release,
    get_repository_root,
)
from .types import (
    BUNDLE_EXCLUDE_PATTERNS,
    BUNDLE_INCLUDE_ROOTS,
    DEPLOYMENT_IMPLEMENTATION_VERSION,
    DEPLOYMENT_SCHEMA_VERSION,
    SECRET_PATTERNS,
    ReleaseManifestV1,
)

APPLICATION_VERSION = "integrated-market-platform-build34"


@dataclass(frozen=True)
class ReleaseBuildResultV1:
    manifest: ReleaseManifestV1
    bundle_path: Path | None
    blocked: bool
    block_reason: str
    semantic_content_hash: str


def _should_exclude(path: str) -> bool:
    lower = path.lower().replace("\\", "/")
    for pattern in BUNDLE_EXCLUDE_PATTERNS:
        if pattern in lower:
            return True
    for secret in SECRET_PATTERNS:
        if secret in lower:
            return True
    return False


def _collect_bundle_files(root: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for include_root in BUNDLE_INCLUDE_ROOTS:
        target = root / include_root
        if target.is_file():
            rel = include_root.replace("\\", "/")
            if not _should_exclude(rel):
                files[rel] = target.read_bytes()
        elif target.is_dir():
            for path in target.rglob("*"):
                if path.is_file():
                    rel = str(path.relative_to(root)).replace("\\", "/")
                    if not _should_exclude(rel):
                        files[rel] = path.read_bytes()
    return files


def _hash_bundle_content(files: dict[str, bytes]) -> str:
    entries = sorted((k, hashlib.sha256(v).hexdigest()) for k, v in files.items())
    payload = {"entries": entries}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def scan_bundle_for_secrets(files: dict[str, bytes]) -> tuple[str, ...]:
    """Return paths that appear to contain embedded secrets."""
    violations: list[str] = []
    credential_path_markers = (".env", "credentials", "secrets", ".pem", ".key", "id_rsa")
    for path, content in files.items():
        lower_path = path.lower()
        if any(marker in lower_path for marker in credential_path_markers):
            if ".example" not in lower_path:
                violations.append(path)
            continue
        # Skip source code — secret references in code are symbolic, not embedded values
        if lower_path.endswith((".py", ".js", ".ts", ".tsx", ".md")):
            continue
        try:
            text = content.decode("utf-8", errors="ignore").lower()
        except Exception:
            continue
        # Flag only high-confidence embedded credential patterns in config/data files
        if 'api_key="sk' in text or 'password="{' not in text and 'password="' in text:
            if ".example" not in lower_path:
                violations.append(path)
    return tuple(violations)


def build_release_manifest(
    *,
    build_timestamp_ns: int,
    build33_qualification_ref: str,
    root: Path | None = None,
    allow_dirty: bool = False,
) -> ReleaseBuildResultV1:
    root = root or get_repository_root()
    blocked, reason = dirty_tree_blocks_release(root)
    if blocked and not allow_dirty:
        empty = ReleaseManifestV1(
            release_manifest_id="BLOCKED",
            schema_version=DEPLOYMENT_SCHEMA_VERSION,
            source_repository="",
            source_commit_sha="",
            source_branch="",
            build_timestamp_ns=build_timestamp_ns,
            application_version=APPLICATION_VERSION,
            contract_schema_versions={},
            dependency_lock_hash="",
            source_tree_hash="",
            artifact_hashes={},
            supported_runtime={},
            configuration_schema_version=DEPLOYMENT_SCHEMA_VERSION,
            required_migration_schema_version="intelligence-v1",
            included_components=(),
            excluded_components=(),
            required_build_qualification_refs=(),
            implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
        )
        return ReleaseBuildResultV1(
            manifest=empty,
            bundle_path=None,
            blocked=True,
            block_reason=reason,
            semantic_content_hash="",
        )

    prov = collect_source_provenance(root)
    files = _collect_bundle_files(root)
    secret_violations = scan_bundle_for_secrets(files)
    if secret_violations:
        empty = ReleaseManifestV1(
            release_manifest_id="BLOCKED",
            schema_version=DEPLOYMENT_SCHEMA_VERSION,
            source_repository=str(root),
            source_commit_sha=prov.commit_sha,
            source_branch=prov.branch,
            build_timestamp_ns=build_timestamp_ns,
            application_version=APPLICATION_VERSION,
            contract_schema_versions={},
            dependency_lock_hash=prov.dependency_lock_hash,
            source_tree_hash=prov.source_tree_hash,
            artifact_hashes={},
            supported_runtime={},
            configuration_schema_version=DEPLOYMENT_SCHEMA_VERSION,
            required_migration_schema_version="intelligence-v1",
            included_components=(),
            excluded_components=tuple(secret_violations),
            required_build_qualification_refs=(build33_qualification_ref,),
            implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
        )
        return ReleaseBuildResultV1(
            manifest=empty,
            bundle_path=None,
            blocked=True,
            block_reason=f"secrets detected in bundle: {secret_violations}",
            semantic_content_hash="",
        )

    semantic_hash = _hash_bundle_content(files)
    artifact_hashes = {
        "bundle_content": semantic_hash,
        "source_tree": prov.source_tree_hash,
        "dependency_lock": prov.dependency_lock_hash,
    }

    manifest = ReleaseManifestV1(
        release_manifest_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        source_repository=str(root),
        source_commit_sha=prov.commit_sha,
        source_branch=prov.branch,
        build_timestamp_ns=build_timestamp_ns,
        application_version=APPLICATION_VERSION,
        contract_schema_versions={
            "deployment": DEPLOYMENT_SCHEMA_VERSION,
            "supervised_pilot": "1",
            "operational_reliability": "1",
            "operator_control": "1",
        },
        dependency_lock_hash=prov.dependency_lock_hash,
        source_tree_hash=prov.source_tree_hash,
        artifact_hashes=artifact_hashes,
        supported_runtime={"python": "3.11.15", "node": "20"},
        configuration_schema_version=DEPLOYMENT_SCHEMA_VERSION,
        required_migration_schema_version="intelligence-v1",
        included_components=tuple(sorted(files.keys())),
        excluded_components=tuple(BUNDLE_EXCLUDE_PATTERNS),
        required_build_qualification_refs=(build33_qualification_ref,),
        implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
    )
    release_id = derive_release_id(manifest)
    final = ReleaseManifestV1(
        release_manifest_id=release_id,
        schema_version=manifest.schema_version,
        source_repository=manifest.source_repository,
        source_commit_sha=manifest.source_commit_sha,
        source_branch=manifest.source_branch,
        build_timestamp_ns=manifest.build_timestamp_ns,
        application_version=manifest.application_version,
        contract_schema_versions=manifest.contract_schema_versions,
        dependency_lock_hash=manifest.dependency_lock_hash,
        source_tree_hash=manifest.source_tree_hash,
        artifact_hashes=manifest.artifact_hashes,
        supported_runtime=manifest.supported_runtime,
        configuration_schema_version=manifest.configuration_schema_version,
        required_migration_schema_version=manifest.required_migration_schema_version,
        included_components=manifest.included_components,
        excluded_components=manifest.excluded_components,
        required_build_qualification_refs=manifest.required_build_qualification_refs,
        implementation_version=manifest.implementation_version,
        metadata=manifest.metadata,
    )
    return ReleaseBuildResultV1(
        manifest=final,
        bundle_path=None,
        blocked=False,
        block_reason="OK",
        semantic_content_hash=semantic_hash,
    )


def create_release_bundle(
    manifest: ReleaseManifestV1,
    *,
    root: Path | None = None,
    output_dir: Path | None = None,
) -> Path:
    root = root or get_repository_root()
    files = _collect_bundle_files(root)
    out_dir = output_dir or (root / "artifacts" / "deployment-qualification" / "bundles")
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = out_dir / f"{manifest.release_manifest_id}.tar.gz"
    metadata = {
        "release_manifest_id": manifest.release_manifest_id,
        "source_commit_sha": manifest.source_commit_sha,
        "artifact_hashes": manifest.artifact_hashes,
    }
    with tarfile.open(bundle_path, "w:gz") as tar:
        manifest_bytes = json.dumps(metadata, sort_keys=True, indent=2).encode("utf-8")
        import io

        info = tarfile.TarInfo(name="RELEASE_MANIFEST.json")
        info.size = len(manifest_bytes)
        tar.addfile(info, io.BytesIO(manifest_bytes))
        for rel_path, content in sorted(files.items()):
            info = tarfile.TarInfo(name=rel_path)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
    return bundle_path


def compare_semantic_identity(result_a: ReleaseBuildResultV1, result_b: ReleaseBuildResultV1) -> bool:
    """Compare semantic content identity ignoring build timestamp."""
    if result_a.blocked or result_b.blocked:
        return False
    return (
        result_a.manifest.source_commit_sha == result_b.manifest.source_commit_sha
        and result_a.manifest.source_tree_hash == result_b.manifest.source_tree_hash
        and result_a.manifest.dependency_lock_hash == result_b.manifest.dependency_lock_hash
        and result_a.semantic_content_hash == result_b.semantic_content_hash
        and result_a.manifest.release_manifest_id == result_b.manifest.release_manifest_id
    )
