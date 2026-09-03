"""Phase 16 fund_etf_cross_asset whale family assertion registry and evaluator."""

from __future__ import annotations

from pathlib import Path

from .canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json

MANDATORY_IDS = ("P16-FIX-001", "P16-FUND-001", "P16-PIT-001", "P16-WHALE-001", "P16-UI-001", "SAFE-003")

_ROLES = {
    "P16-FIX-001": (["ARCHITECTURE_LEAD"], ["PROJECT_OWNER"], ["INDEPENDENT_REVIEWER"]),
    "P16-FUND-001": (["ARCHITECTURE_LEAD"], ["PROJECT_OWNER"], ["INDEPENDENT_REVIEWER"]),
    "P16-PIT-001": (["ARCHITECTURE_LEAD"], ["PROJECT_OWNER"], ["INDEPENDENT_REVIEWER"]),
    "P16-WHALE-001": (["ARCHITECTURE_LEAD"], ["PROJECT_OWNER"], ["INDEPENDENT_REVIEWER"]),
    "P16-UI-001": (["ARCHITECTURE_LEAD"], ["PROJECT_OWNER"], ["INDEPENDENT_REVIEWER"]),
    "SAFE-003": (["RELEASE_OWNER"], ["SECURITY_OWNER"], ["INDEPENDENT_REVIEWER"]),
}


def build_registry(path: Path) -> dict[str, object]:
    raw = load_json_strict(path)
    if not isinstance(raw, dict) or raw.get("registry_version") != "1.0.0":
        raise ValueError("unsupported phase16 assertion registry")
    predicates = raw.get("predicates")
    if not isinstance(predicates, list):
        raise ValueError("predicates must be a list")
    by_id: dict[str, dict[str, str]] = {}
    for row in predicates:
        if not isinstance(row, dict):
            raise ValueError("predicate row must be an object")
        assertion_id = str(row.get("assertion_id"))
        if assertion_id in by_id:
            raise ValueError("duplicate assertion ID")
        by_id[assertion_id] = {
            "assertion_id": assertion_id,
            "assertion_version": str(row.get("assertion_version")),
            "predicate": str(row.get("predicate")),
        }
    if set(by_id) != set(MANDATORY_IDS):
        raise ValueError("active assertion set differs from mandatory set")
    active: list[dict[str, object]] = []
    for assertion_id in MANDATORY_IDS:
        predicate = by_id[assertion_id]
        predicate_hash = sha256_bytes(canonical_bytes(predicate))
        active.append(
            {
                "assertion_id": assertion_id,
                "assertion_version": predicate["assertion_version"],
                "effective_from_registry_version": "1.0.0",
                "lifecycle": "ACTIVE",
                "predicate": predicate["predicate"],
                "predicate_hash": predicate_hash,
                "retired_by_registry_version": None,
            }
        )
    return {
        "active_keys": active,
        "mandatory_ids": list(MANDATORY_IDS),
        "mandatory_set_hash": sha256_bytes(canonical_bytes(list(MANDATORY_IDS))),
        "registry_version": "1.0.0",
        "retired_keys": [],
    }


def create_run_manifest(path: Path, inputs: dict[str, object]) -> str:
    manifest = dict(inputs)
    manifest.pop("run_id", None)
    run_id = sha256_bytes(canonical_bytes(manifest))
    manifest["run_id"] = run_id
    write_canonical_json(path, manifest)
    return run_id


def validate_result_membership(run_id: str, results: list[dict[str, object]]) -> None:
    ids = [str(result.get("assertion_id")) for result in results]
    if len(ids) != len(set(ids)) or set(ids) != set(MANDATORY_IDS):
        raise ValueError("result membership differs from mandatory assertion set")
    if any(result.get("run_id") != run_id for result in results):
        raise ValueError("mixed run IDs")


def _result_id(result_without_id: dict[str, object]) -> str:
    return sha256_bytes(canonical_bytes(result_without_id))


def evaluate_run(run_manifest_path: Path, output_dir: Path) -> list[dict[str, object]]:
    manifest = load_json_strict(run_manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("run manifest must be an object")
    run_id = str(manifest["run_id"])
    without_id = dict(manifest)
    without_id.pop("run_id")
    if sha256_bytes(canonical_bytes(without_id)) != run_id:
        raise ValueError("run ID mismatch")
    registry = manifest.get("active_keys")
    observations = manifest.get("assertion_observations", {})
    if not isinstance(registry, list) or not isinstance(observations, dict):
        raise ValueError("run manifest lacks registry or observations")
    selected = manifest.get("selected_evidence", [])
    if not isinstance(selected, list):
        raise ValueError("selected evidence must be a list")
    evidence_refs = sorted(
        str(row["logical_id"]) for row in selected if isinstance(row, dict) and "logical_id" in row
    )
    key_by_id = {str(row["assertion_id"]): row for row in registry if isinstance(row, dict)}
    results: list[dict[str, object]] = []
    for assertion_id in MANDATORY_IDS:
        key = key_by_id.get(assertion_id)
        observed = observations.get(assertion_id)
        if key is None or observed is None:
            status = "BLOCKED"
            reasons = ["MISSING_REGISTRY_KEY_OR_OBSERVATION"]
            observed_values: dict[str, object] = {}
        elif not isinstance(observed, dict):
            status = "BLOCKED"
            reasons = ["INVALID_OBSERVATION"]
            observed_values = {}
        else:
            observed_values = observed
            status = str(observed.get("status", "BLOCKED"))
            if status not in {"PASS", "FAIL", "BLOCKED"}:
                raise ValueError("invalid assertion status")
            reasons = sorted(str(item) for item in observed.get("reason_codes", []))
        owners, approvers, reviewers = _ROLES[assertion_id]
        result: dict[str, object] = {
            "approver_roles": sorted(approvers),
            "assertion_id": assertion_id,
            "assertion_version": str(key.get("assertion_version", "1.0.0")) if key else "1.0.0",
            "evaluated_at": str(manifest.get("evaluated_at", "1970-01-01T00:00:00Z")),
            "evidence_refs": evidence_refs,
            "expected_predicate": str(key.get("predicate", "")) if key else "",
            "observed_values": observed_values,
            "owner_roles": sorted(owners),
            "predicate_hash": str(key.get("predicate_hash", "")) if key else "",
            "reason_codes": reasons,
            "reviewer_roles": sorted(reviewers),
            "run_id": run_id,
            "status": status,
            "subject_manifest_hash": str(manifest["subject_manifest_hash"]),
            "supersedes_assertion_result_id": None,
            "tool_versions": sorted(str(item) for item in manifest.get("tool_versions", [])),
        }
        result["assertion_result_id"] = _result_id(result)
        results.append(result)
    validate_result_membership(run_id, results)
    write_canonical_json(
        output_dir / "assertion-results.json",
        {"results": results, "run_id": run_id},
    )
    return results


def aggregate_status(results: list[dict[str, object]]) -> str:
    statuses = {str(result["status"]) for result in results}
    if "FAIL" in statuses:
        return "FAIL"
    if "BLOCKED" in statuses:
        return "BLOCKED"
    return "PASS"
