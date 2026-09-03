"""Fail-closed governance verification, aggregation, and candidate rooting."""

from __future__ import annotations

from pathlib import Path

from .assertions import MANDATORY_IDS, validate_result_membership
from .canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json
from .errors import IntegrityError

_CANDIDATE_EXCLUSIONS = {
    "phase0.acceptance_index",
    "phase0.ai_review_coverage",
    "phase0.ai_review_runs",
    "phase0.approval_records",
    "phase0.candidate_evidence_root",
    "phase0.final_acceptance_result",
}


def aggregate_status(statuses: list[str]) -> str:
    if any(status == "FAIL" for status in statuses):
        return "FAIL"
    if any(status == "BLOCKED" for status in statuses):
        return "BLOCKED"
    if statuses and all(status == "PASS" for status in statuses):
        return "PASS"
    return "BLOCKED"


def candidate_tuple_array(rows: list[dict[str, object]]) -> list[list[object]]:
    selected: list[list[object]] = []
    seen: set[str] = set()
    for row in rows:
        logical_id = str(row["logical_id"])
        if logical_id in _CANDIDATE_EXCLUSIONS:
            continue
        if logical_id in seen:
            raise IntegrityError(f"duplicate candidate member: {logical_id}")
        seen.add(logical_id)
        selected.append(
            [
                logical_id,
                str(row["member_sha256"]),
                int(row["byte_length"]),
                str(row["media_type"]),
            ]
        )
    return sorted(selected, key=lambda row: tuple(str(item) for item in row))


def candidate_root(rows: list[dict[str, object]]) -> str:
    return sha256_bytes(canonical_bytes(candidate_tuple_array(rows)))


def verify_member(path: Path, expected_sha256: str) -> None:
    if not path.is_file():
        raise IntegrityError("candidate member is missing")
    if sha256_bytes(path.read_bytes()) != expected_sha256:
        raise IntegrityError("candidate member hash mismatch")


def verify_result_set(run_id: str, results: list[dict[str, object]]) -> dict[str, object]:
    reasons: list[str] = []
    ids = [str(row.get("assertion_id")) for row in results]
    if set(ids) != set(MANDATORY_IDS) or len(ids) != len(MANDATORY_IDS):
        reasons.append("MISSING_MANDATORY_RESULT")
    if any(row.get("run_id") != run_id for row in results):
        reasons.append("MIXED_RUN_ID")
    for row in results:
        result_id = row.get("assertion_result_id")
        without_id = dict(row)
        without_id.pop("assertion_result_id", None)
        if result_id != sha256_bytes(canonical_bytes(without_id)):
            reasons.append("ASSERTION_RESULT_ID_MISMATCH")
            break
    return {
        "reason_codes": sorted(set(reasons)),
        "status": "BLOCKED" if reasons else "PASS",
    }


def _member_row(logical_id: str, path: Path) -> dict[str, object]:
    return {
        "byte_length": path.stat().st_size,
        "logical_id": logical_id,
        "media_type": "application/json",
        "member_sha256": sha256_bytes(path.read_bytes()),
    }


def verify_evaluation(evaluation_dir: Path, output_dir: Path) -> dict[str, object]:
    run_manifest_path = evaluation_dir / "assertion-run-manifest.json"
    results_path = evaluation_dir / "assertion-results.json"
    index_path = evaluation_dir / "preapproval-artifact-index.json"
    run_manifest = load_json_strict(run_manifest_path)
    result_bundle = load_json_strict(results_path)
    artifact_index = load_json_strict(index_path)
    if not isinstance(run_manifest, dict) or not isinstance(result_bundle, dict) or not isinstance(artifact_index, dict):
        raise IntegrityError("evaluation inputs must be objects")
    run_id = str(run_manifest["run_id"])
    without_run_id = dict(run_manifest)
    without_run_id.pop("run_id")
    if sha256_bytes(canonical_bytes(without_run_id)) != run_id:
        raise IntegrityError("run manifest ID mismatch")
    results = result_bundle.get("results")
    if not isinstance(results, list):
        raise IntegrityError("assertion results must be a list")
    membership = verify_result_set(run_id, results)
    selected = run_manifest.get("selected_evidence", [])
    if not isinstance(selected, list):
        raise IntegrityError("selected evidence must be a list")
    for row in selected:
        if not isinstance(row, dict):
            raise IntegrityError("selected evidence row must be an object")
        verify_member(evaluation_dir / str(row["path"]), str(row["sha256"]))
    aggregate = aggregate_status([str(row.get("status")) for row in results])
    if membership["status"] != "PASS":
        aggregate = "BLOCKED"
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregate_path = output_dir / "assertion-aggregate.json"
    write_canonical_json(
        aggregate_path,
        {
            "aggregate_status": aggregate,
            "logical_id": "phase0.assertion_aggregate",
            "mandatory_ids": list(MANDATORY_IDS),
            "run_id": run_id,
        },
    )
    verifier_path = output_dir / "governance-verifier.json"
    write_canonical_json(
        verifier_path,
        {
            "logical_id": "phase0.governance_verifier",
            "reason_codes": membership["reason_codes"],
            "run_id": run_id,
            "status": membership["status"],
        },
    )
    rows = artifact_index.get("artifacts")
    if not isinstance(rows, list):
        raise IntegrityError("preapproval artifact index is invalid")
    normalized: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise IntegrityError("preapproval index row is invalid")
        path = evaluation_dir / str(row["path"])
        verify_member(path, str(row.get("member_sha256", row.get("sha256"))))
        normalized.append(
            {
                "byte_length": int(row["byte_length"]),
                "logical_id": str(row["logical_id"]),
                "media_type": str(row["media_type"]),
                "member_sha256": str(row.get("member_sha256", row.get("sha256"))),
            }
        )
    normalized.extend(
        [
            _member_row("phase0.assertion_aggregate", aggregate_path),
            _member_row("phase0.governance_verifier", verifier_path),
        ]
    )
    tuple_array = candidate_tuple_array(normalized)
    root = candidate_root(normalized)
    write_canonical_json(
        output_dir / "candidate-evidence-root.json",
        {
            "assertion_aggregate_status": aggregate,
            "candidate_evidence_root": root,
            "logical_id": "phase0.candidate_evidence_root",
            "member_count": len(tuple_array),
            "ordered_member_tuples": tuple_array,
            "run_id": run_id,
        },
    )
    return {
        "aggregate_status": aggregate,
        "candidate_evidence_root": root,
        "member_count": len(tuple_array),
        "run_id": run_id,
    }
