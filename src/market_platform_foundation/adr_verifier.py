"""Fail-closed ADR registry verification for Phase 1 decision completion."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from .errors import IntegrityError

ACCEPTED_STATUSES = frozenset({"ACCEPTED", "ACCEPTED_EXACT_HASH"})


def _repo_root(start: Path | None = None) -> Path:
    if start is None:
        return Path(__file__).resolve().parents[2]
    return start


def load_registry(root: Path | None = None) -> dict[str, Any]:
    path = _repo_root(root) / "manifests/phase1/adr-registry.json"
    doc = load_json_strict(path)
    if not isinstance(doc, dict):
        raise IntegrityError("ADR registry must be an object")
    rows = doc.get("rows")
    if not isinstance(rows, list) or not rows:
        raise IntegrityError("ADR registry rows are missing")
    return doc


def _evidence_ok(evidence: object) -> bool:
    if not isinstance(evidence, list) or not evidence:
        return False
    for row in evidence:
        if not isinstance(row, dict):
            return False
        if not str(row.get("logical_id", "")).strip():
            return False
        if not str(row.get("sha256", "")).strip():
            return False
    return True


def verify_adr_row(root: Path, row: dict[str, Any]) -> dict[str, Any]:
    adr_id = str(row["adr_id"])
    decision_path = root / str(row["decision_path"])
    blocking = bool(row.get("blocking", False))
    reasons: list[str] = []

    if not decision_path.is_file():
        reasons.append("MISSING_DECISION_FILE")
        return {
            "adr_id": adr_id,
            "blocking": blocking,
            "decision_path": str(row["decision_path"]),
            "decision_sha256": None,
            "reason_codes": reasons,
            "status": "BLOCKING" if blocking else "SPEC-RESOLVED_PENDING_RECORD",
        }

    decision_sha256 = sha256_bytes(decision_path.read_bytes())
    doc = load_json_strict(decision_path)
    if not isinstance(doc, dict):
        reasons.append("INVALID_DECISION_DOCUMENT")
        return {
            "adr_id": adr_id,
            "blocking": blocking,
            "decision_path": str(row["decision_path"]),
            "decision_sha256": decision_sha256,
            "reason_codes": reasons,
            "status": "BLOCKING",
        }

    status = str(doc.get("status", ""))
    if status not in ACCEPTED_STATUSES:
        reasons.append("NOT_ACCEPTED")
    if not _evidence_ok(doc.get("conformance_evidence")):
        reasons.append("MISSING_CONFORMANCE_EVIDENCE")

    if reasons:
        return {
            "adr_id": adr_id,
            "blocking": blocking,
            "decision_path": str(row["decision_path"]),
            "decision_sha256": decision_sha256,
            "reason_codes": sorted(set(reasons)),
            "status": "BLOCKING",
        }

    return {
        "adr_id": adr_id,
        "blocking": blocking,
        "decision_path": str(row["decision_path"]),
        "decision_sha256": decision_sha256,
        "reason_codes": [],
        "status": "ACCEPTED",
    }


def verify_registry(root: Path | None = None) -> dict[str, Any]:
    repo = _repo_root(root)
    registry = load_registry(repo)
    rows = registry["rows"]
    results = [verify_adr_row(repo, row) for row in rows if isinstance(row, dict)]
    blocking_rows = [row for row in results if row["status"] == "BLOCKING"]
    accepted_rows = [row for row in results if row["status"] == "ACCEPTED"]
    overall = "PASS" if not blocking_rows else "BLOCKING"
    return {
        "accepted_count": len(accepted_rows),
        "blocking_count": len(blocking_rows),
        "logical_id": "phase1.adr_verifier_result",
        "overall_status": overall,
        "registry_logical_id": str(registry.get("logical_id", "phase1.adr_registry")),
        "results": sorted(results, key=lambda row: str(row["adr_id"])),
        "total_count": len(results),
    }


def write_verifier_result(output_dir: Path, root: Path | None = None) -> dict[str, Any]:
    result = verify_registry(root)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_canonical_json(output_dir / "adr-verifier-result.json", result)
    return result


def build_acceptance_index(root: Path | None = None) -> dict[str, Any]:
    repo = _repo_root(root)
    result = verify_registry(repo)
    members: list[dict[str, str]] = []
    for row in result["results"]:
        if row["status"] != "ACCEPTED":
            continue
        path = repo / str(row["decision_path"])
        members.append(
            {
                "adr_id": str(row["adr_id"]),
                "logical_id": f"phase1.{str(row['adr_id']).lower().replace('-', '_')}",
                "repository_relative_path": str(row["decision_path"]),
                "sha256": str(row["decision_sha256"]),
            }
        )
    members = sorted(members, key=lambda row: row["adr_id"])
    index_sha256 = sha256_bytes(canonical_bytes(members))
    return {
        "accepted_adr_count": len(members),
        "index_members": members,
        "index_sha256": index_sha256,
        "logical_id": "phase1.adr_acceptance_index",
    }


def candidate_root_from_index(index_doc: dict[str, Any]) -> str:
    members = index_doc.get("index_members")
    if not isinstance(members, list):
        raise IntegrityError("acceptance index members are missing")
    tuples = [
        [str(row["adr_id"]), str(row["sha256"]), str(row["repository_relative_path"])]
        for row in members
        if isinstance(row, dict)
    ]
    tuples = sorted(tuples, key=lambda row: row[0])
    return sha256_bytes(canonical_bytes(tuples))
