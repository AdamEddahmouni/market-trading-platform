"""Canonical, immutable Phase 0 evidence publication."""

from __future__ import annotations

import uuid
from pathlib import Path

from .analysis import analyze_tree
from .assertions import build_registry
from .authority import resolve_canonical_authority
from .canonical import canonical_bytes, load_json_strict, sha256_bytes
from .credential_audit import audit_path_inventory
from .distribution import validate_lock
from .registry import registry_snapshot

_FINALIZED: set[Path] = set()


def _record(
    logical_id: str,
    content: object,
    metadata: dict[str, object] | None,
) -> dict[str, object]:
    content_sha256 = sha256_bytes(canonical_bytes(content))
    supplied = dict(metadata or {})
    return {
        "artifact_type": "PHASE0_EVIDENCE_RECORD",
        "content": content,
        "content_sha256": content_sha256,
        "exclusions": supplied.pop("exclusions", []),
        "inputs": supplied.pop("inputs", []),
        "logical_id": logical_id,
        "media_type": "application/json",
        "procedure_versions": supplied.pop("procedure_versions", {}),
        "sanitization": supplied.pop(
            "sanitization",
            {
                "absolute_paths_included": False,
                "account_identifiers_included": False,
                "credential_values_included": False,
                "environment_values_included": False,
                "remote_urls_included": False,
            },
        ),
        "scope": supplied.pop("scope", "PHASE_0_STEPS_9_THROUGH_13"),
        "source_manifest_sha256": supplied.pop("source_manifest_sha256", "UNBOUND"),
        "status": supplied.pop("status", "FINALIZED"),
        **supplied,
    }


def finalize_artifact(
    path: Path,
    logical_id: str,
    content: object,
    metadata: dict[str, object] | None = None,
) -> str:
    target = path.resolve()
    if path.exists() or target in _FINALIZED:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(_record(logical_id, content, metadata))
    staging = path.parent / f".staging-{uuid.uuid4().hex}"
    try:
        staging.write_bytes(data)
        if path.exists():
            raise FileExistsError(path)
        staging.replace(path)
    finally:
        if staging.exists():
            staging.unlink()
    _FINALIZED.add(target)
    return sha256_bytes(data)


def _filename(logical_id: str) -> str:
    name = logical_id.removeprefix("phase0.").replace("_", "-").replace(".", "-")
    return name + ".json"


def publish_artifacts(
    output_dir: Path,
    artifacts: list[tuple[str, object]],
    metadata: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    logical_ids = [logical_id for logical_id, _content in artifacts]
    if len(logical_ids) != len(set(logical_ids)):
        raise ValueError("duplicate logical ID")
    index: list[dict[str, object]] = []
    for logical_id, content in sorted(artifacts, key=lambda row: row[0]):
        path = output_dir / _filename(logical_id)
        digest = finalize_artifact(path, logical_id, content, metadata)
        index.append(
            {
                "byte_length": path.stat().st_size,
                "logical_id": logical_id,
                "media_type": "application/json",
                "path": path.name,
                "sha256": digest,
            }
        )
    return index


def _revision3_preservation_summary(record: dict[str, object]) -> dict[str, object]:
    comparisons = record.get("donor_comparisons")
    unauthorized_drift = record.get("unauthorized_drift")
    if not isinstance(comparisons, list) or not isinstance(unauthorized_drift, list):
        return {
            "declared_result": str(record.get("result", "BLOCKED")),
            "donor_root_ids": [],
            "internally_consistent": False,
            "observed_result": "BLOCKED",
        }
    if any(not isinstance(row, dict) for row in comparisons):
        return {
            "declared_result": str(record.get("result", "BLOCKED")),
            "donor_root_ids": [],
            "internally_consistent": False,
            "observed_result": "BLOCKED",
        }
    root_ids = sorted(str(row.get("root_id", "")) for row in comparisons)
    expected_root_ids = ["PROTO-DS340W-001", "PROTO-GRIDIQ-001"]
    if root_ids != expected_root_ids:
        observed_result = "BLOCKED"
    elif unauthorized_drift or any(row.get("result") != "PASS" for row in comparisons):
        observed_result = "FAIL"
    else:
        observed_result = "PASS"
    declared_result = str(record.get("result", "BLOCKED"))
    return {
        "comparison_results": sorted(
            str(row.get("result", "BLOCKED")) for row in comparisons
        ),
        "declared_result": declared_result,
        "donor_root_ids": root_ids,
        "internally_consistent": declared_result == observed_result,
        "observed_result": observed_result,
    }


def build_preassertion_content(
    repository_root: Path,
    build_result: dict[str, object],
    install_inventory: dict[str, object],
    denial_report: dict[str, object],
    credential_history_report: dict[str, object] | None = None,
) -> dict[str, object]:
    root = repository_root.resolve()
    authority = resolve_canonical_authority(root)
    analysis = analyze_tree(root / "src" / "market_platform_foundation")
    tracked_like_paths: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(
            part
            in {
                ".git",
                ".pytest_cache",
                ".worktrees",
                "__pycache__",
                "build",
                "dist",
                "node_modules",
            }
            or part.startswith(".venv")
            for part in relative.parts
        ):
            continue
        posix = relative.as_posix()
        if posix == ".env" or posix.startswith(".env.local"):
            continue
        tracked_like_paths.append(posix)
    tracked_like_paths.sort()
    current_audit = audit_path_inventory(tracked_like_paths, tracked=True)
    history = credential_history_report or {
        "history_revision_count": 0,
        "reason_codes": ["LOCAL_HISTORY_AUDIT_NOT_SUPPLIED"],
        "status": "BLOCKED",
        "unresolved_redacted_finding_count": 0,
    }
    documents = []
    for path in sorted((root / "docs" / "superpowers").rglob("*")):
        if path.is_file():
            documents.append(
                {
                    "byte_length": path.stat().st_size,
                    "path": path.relative_to(root).as_posix(),
                    "sha256": sha256_bytes(path.read_bytes()),
                }
            )
    preservation_path = (
        root
        / "docs"
        / "superpowers"
        / "governance"
        / "2026-08-14-phase-0-repository-preservation-difference.json"
    )
    preservation = {
        "byte_length": preservation_path.stat().st_size,
        "repository_relative_path": preservation_path.relative_to(root).as_posix(),
        "sha256": sha256_bytes(preservation_path.read_bytes()),
    }
    revision3_preservation_path = (
        root
        / "docs"
        / "superpowers"
        / "governance"
        / "2026-08-14-revision-3-donor-preservation-difference.json"
    )
    revision3_preservation = load_json_strict(revision3_preservation_path)
    if not isinstance(revision3_preservation, dict):
        raise ValueError("Revision 3 donor preservation record must be an object")
    revision3_preservation_summary = _revision3_preservation_summary(
        revision3_preservation
    )
    return {
        "phase0.canonical_inventory": {
            "canonical_authority": authority,
            "document_count": len(documents),
            "documents": documents,
            "one_canonical_specification": authority.get(
                "one_canonical_specification", False
            ),
        },
        "phase0.credential_audit": {
            "current_tree": current_audit,
            "history": history,
            "private_configuration_ignored": True,
            "public_examples_placeholder_only": True,
            "status": (
                "PASS"
                if current_audit["prohibited_count"] == 0 and history.get("status") == "PASS"
                else "BLOCKED"
            ),
        },
        "phase0.denied_network_install": install_inventory,
        "phase0.denied_network_protocol": denial_report,
        "phase0.dependency_lock_report": validate_lock(root / "phase0-dependency-lock.json"),
        "phase0.distribution_manifest": build_result,
        "phase0.entrypoint_route_report": {
            "entry_points": analysis["entry_points"],
            "prohibited_routes": analysis["prohibited_routes"],
        },
        "phase0.import_boundary_report": {
            "dynamic_load_findings": analysis["dynamic_load_findings"],
            "import_edges": analysis["import_edges"],
            "prohibited_edges": analysis["prohibited_edges"],
            "syntax_errors": analysis["syntax_errors"],
            "unresolved_internal_imports": analysis["unresolved_internal_imports"],
        },
        "phase0.local_artifact_manifest": {
            "archive_sha256": build_result.get("archive_sha256"),
            "manifest_sha256": build_result.get("manifest_sha256"),
        },
        "phase0.registry_snapshot": {"rows": registry_snapshot()},
        "phase0.repository_preservation_difference": preservation,
        "phase0.revision3_donor_preservation_difference": {
            "byte_length": revision3_preservation_path.stat().st_size,
            "repository_relative_path": revision3_preservation_path.relative_to(
                root
            ).as_posix(),
            "sha256": sha256_bytes(revision3_preservation_path.read_bytes()),
            **revision3_preservation_summary,
        },
    }
