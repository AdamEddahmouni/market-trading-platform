"""UI-002 expanded research UI acceptance assertion registry and evaluator."""

from __future__ import annotations

from pathlib import Path

from .canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json

MANDATORY_IDS = ("UI-RES-001", "UI-RES-002", "UI-RES-003", "SAFE-003")

_ROLES = {
    "UI-RES-001": (["ARCHITECTURE_LEAD"], ["PROJECT_OWNER"], ["INDEPENDENT_REVIEWER"]),
    "UI-RES-002": (["ARCHITECTURE_LEAD"], ["PROJECT_OWNER"], ["INDEPENDENT_REVIEWER"]),
    "UI-RES-003": (["ARCHITECTURE_LEAD"], ["PROJECT_OWNER"], ["INDEPENDENT_REVIEWER"]),
    "SAFE-003": (["RELEASE_OWNER"], ["SECURITY_OWNER"], ["INDEPENDENT_REVIEWER"]),
}


def build_registry(path: Path) -> dict[str, object]:
    raw = load_json_strict(path)
    if not isinstance(raw, dict) or raw.get("registry_version") != "1.0.0":
        raise ValueError("unsupported ui2 assertion registry")
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


def aggregate_status(results: list[dict[str, object]]) -> str:
    if any(row.get("status") != "PASS" for row in results):
        return "FAIL"
    return "PASS"


def evaluate_run(manifest_path: Path, evidence_dir: Path) -> list[dict[str, object]]:
    manifest = load_json_strict(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("manifest invalid")
    run_id = str(manifest.get("run_id", ""))
    observations = manifest.get("assertion_observations", {})
    if not isinstance(observations, dict):
        raise ValueError("observations invalid")
    results: list[dict[str, object]] = []
    for assertion_id in MANDATORY_IDS:
        obs = observations.get(assertion_id, {})
        if not isinstance(obs, dict):
            obs = {}
        status = str(obs.get("status", "FAIL"))
        results.append(
            {
                "assertion_id": assertion_id,
                "evaluated_at": manifest.get("evaluated_at"),
                "reason_codes": obs.get("reason_codes", []),
                "run_id": run_id,
                "status": status,
            }
        )
    validate_result_membership(run_id, results)
    write_canonical_json(evidence_dir / "assertion-results.json", {"results": results, "run_id": run_id})
    return results
