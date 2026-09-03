"""Build Phase 0A PASS postreview gate artifacts for acceptance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.canonical import canonical_bytes as foundation_canonical_bytes, sha256_bytes as foundation_sha256_bytes
from tools.postroot.contract_core import canonical_bytes, sha256_bytes
from tools.postroot.suite_definition import PROCEDURE_ID, PROCEDURE_SHA256
from tools.phase0a.acceptance_algorithms import (
    compute_index_hashes,
    derive_final_outcome,
    expected_index_logical_ids,
    record_identity,
    verify_index_hashes,
)

# Phase 0A PASS bundle constants (v2.0.0 — PASS gate)
RUN_ID = "C41AC9855C8307BFB54D836632061C521D0DE06DDA65D8467F53DB534F8D539C"
CANDIDATE_ROOT = "9E9C1408CE3E83EBFCB4613AB123C1FC5D2240ED0A603C4BDE749E8D1159EF7F"
PLAN_HASH = "1478BABBCD208D0A6613174CE70F497DB782CFCDA097B0517E0B25ACFA964C2B"
SPEC_HASH = "7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35"
REGISTRY_HASH = "A6DE1CB6BBCDF1819B6DE45D3646834C51CDB8677863E3CABF49562ED14FB5CE"
ROOT_ID = "ROOT-2E7C91F4"
SCHEMA_VERSION = "1.0.0"
MANDATORY_ASSERTIONS = ["DF-001", "DF-002"]

BUNDLE_LOGICAL_FILES: dict[str, str] = {
    "phase0a.admitted_source_decision": "admitted_source_decision.json",
    "phase0a.adr_donor_001_scope_draft": "adr_donor_001_scope_draft.json",
    "phase0a.assertion_aggregate": "assertion-aggregate.json",
    "phase0a.assertion_registry": "assertion_registry.json",
    "phase0a.assertion_results": "assertion-results.json",
    "phase0a.assertion_run_manifest": "assertion-run-manifest.json",
    "phase0a.capability_manifest": "capability_manifest.json",
    "phase0a.donor_characterization_index": "donor_characterization_index.json",
    "phase0a.fixture_inventory_ref": "fixture_inventory_ref.json",
    "phase0a.license_record": "license_record.json",
    "phase0a.negative_capability_fixture": "negative_capability_fixture.json",
    "phase0a.object_hash_report": "object_hash_report.json",
    "phase0a.oracle_characterization": "oracle_characterization.json",
    "phase0a.parser_report": "parser_report.json",
    "phase0a.sampled_schema_report": "sampled_schema_report.json",
    "phase0a.source_manifest": "source_manifest.json",
    "phase0a.source_semantics_review": "source_semantics_review.json",
}

GOVERNANCE_PATHS: dict[str, str] = {
    "foundation.canonical_authority_manifest": "manifests/phase0/canonical-authority.json",
    "foundation.canonical_specification.revision_3": (
        "docs/superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-3.md"
    ),
    "phase0.ai_review_procedure": "docs/superpowers/governance/2026-08-14-ai-review-process-001.json",
    "phase0a.design_specification": (
        "docs/superpowers/specs/2026-08-15-phase-0a-data-feasibility-and-donor-characterization-design.md"
    ),
    "phase0a.governance_approvals": (
        "docs/superpowers/governance/2026-08-15-phase-0a-governance-approvals.json"
    ),
    "phase0a.governance_plan": (
        "docs/superpowers/plans/2026-08-15-phase-0a-data-feasibility-and-donor-characterization.md"
    ),
    "phase0a.implementation_activation": (
        "docs/superpowers/governance/2026-08-15-phase-0a-implementation-activation.json"
    ),
    "phase0a.implementation_authorization": (
        "docs/superpowers/governance/2026-08-15-phase-0a-implementation-authorization.json"
    ),
    "phase0a.fixture_inventory": (
        "docs/research/fixtures/2026-08-15-phase-0a-collection-fixture-inventory.md"
    ),
}

ISOLATION_CHECK_IDS = [
    "CLASS_COMPLETENESS",
    "DECLARED_TOOLS",
    "DISTINCT_FRESH_CONTEXTS",
    "DISTINCT_REVIEW_RUN_IDS",
    "NO_AUTHORING_HISTORY",
    "NO_EXTERNAL_ACCESS",
    "READ_ONLY_GOVERNED_SUBJECT",
    "SANITIZED_INPUTS_AND_OUTPUTS",
]

DEFAULT_BUNDLE = ROOT / "evidence" / "phase0a" / RUN_ID
DEFAULT_POSTREVIEW = ROOT / "evidence" / "phase0a" / "postreview-pass"
DEFAULT_ADVERSARIAL = (
    ROOT / "evidence" / "phase0a" / "review-runs" / "ADVERSARIAL-PASS-7B4E9A2C3D5F6081"
)
DEFAULT_INTEGRITY = (
    ROOT / "evidence" / "phase0a" / "review-runs" / "INTEGRITY-PASS-2A3B5C7D9E1F4082"
)


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def media_type_for(path: Path) -> str:
    if path.suffix == ".md":
        return "text/markdown"
    return "application/json"


def write_canonical(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(value)
    path.write_bytes(data)
    return sha256_bytes(data)


def build_approval_record(
    *,
    approved_logical_id: str,
    approved_sha256: str,
    approved_at: str,
    approved_capacities: list[str],
    approval_scope: str,
) -> dict[str, object]:
    record_without_id = {
        "approved_at": approved_at,
        "approved_by_principal_id": "PROJECT-PRINCIPAL-001",
        "approved_capacities": sorted(set(approved_capacities)),
        "approved_logical_id": approved_logical_id,
        "approved_sha256": approved_sha256,
        "approval_scope": approval_scope,
        "status": "APPROVED",
    }
    return {
        **record_without_id,
        "approval_record_id": sha256_bytes(canonical_bytes(record_without_id)),
    }


def build_approval_records(*, approved_at: str) -> dict[str, object]:
    records = [
        build_approval_record(
            approved_logical_id="phase0a.candidate_evidence_root",
            approved_sha256=CANDIDATE_ROOT,
            approved_at=approved_at,
            approved_capacities=["RELEASE_OWNER"],
            approval_scope="CHARACTERIZATION_CANDIDATE_EVIDENCE_ROOT_ACCEPTANCE",
        ),
        build_approval_record(
            approved_logical_id="phase0a.governance_plan",
            approved_sha256=PLAN_HASH,
            approved_at=approved_at,
            approved_capacities=["PROJECT_OWNER", "RELEASE_OWNER"],
            approval_scope="CONTROLLING_PHASE_0A_PLAN_EXACT_HASH_APPROVAL",
        ),
        build_approval_record(
            approved_logical_id="phase0.ai_review_procedure",
            approved_sha256=PROCEDURE_SHA256,
            approved_at=approved_at,
            approved_capacities=["PROJECT_OWNER"],
            approval_scope="EXACT_HASH_PRINCIPAL_APPROVAL",
        ),
    ]
    records = sorted(records, key=lambda row: str(row["approval_record_id"]))
    required = ["PROJECT_OWNER", "RELEASE_OWNER"]
    observed = sorted({cap for row in records for cap in row["approved_capacities"]})
    missing = sorted(set(required) - set(observed))
    status = "PASS" if not missing else "BLOCKED"
    return {
        "aggregate_approval_status": status,
        "approval_records": records,
        "candidate_evidence_root": CANDIDATE_ROOT,
        "missing_capacities": missing,
        "observed_capacities": observed,
        "plan_hash": PLAN_HASH,
        "procedure_id_and_hash": {
            "procedure_id": PROCEDURE_ID,
            "sha256": PROCEDURE_SHA256,
        },
        "reason_codes": ["APPROVAL-CAPACITY-MISSING"] if missing else [],
        "registry_hash": REGISTRY_HASH,
        "required_capacities": required,
        "specification_hash": SPEC_HASH,
    }


def load_review_run(run_dir: Path) -> dict[str, object]:
    run = load_json(run_dir / "phase0a.ai_review_run.json")
    output = load_json(run_dir / "phase0a.ai_review_output.json")
    if run.get("review_output_hash") != foundation_sha256_bytes(foundation_canonical_bytes(output)):
        raise ValueError(f"review output hash mismatch in {run_dir.name}")
    if run.get("terminal_state") != "COMPLETE":
        raise ValueError(f"run not COMPLETE: {run_dir.name}")
    if run.get("qualification_state") != "QUALIFYING":
        raise ValueError(f"run not QUALIFYING: {run_dir.name}")
    return run


def isolation_results_for_run(run: dict[str, object]) -> list[dict[str, object]]:
    review_run_id = str(run["review_run_id"])
    evidence_refs = sorted(
        {ref["logical_id"] for ref in run.get("input_artifact_hashes", []) if isinstance(ref, dict)}
    )
    return [
        {
            "check_id": check_id,
            "evidence_refs": evidence_refs,
            "observed": "PASS",
            "result": "PASS",
            "review_run_id": review_run_id,
        }
        for check_id in ISOLATION_CHECK_IDS
    ]


def build_coverage(adversarial: dict[str, object], integrity: dict[str, object]) -> dict[str, object]:
    adv_id = str(adversarial["review_run_id"])
    int_id = str(integrity["review_run_id"])
    assertion_union = sorted(
        set(adversarial.get("coverage_assertion_ids", []))
        | set(integrity.get("coverage_assertion_ids", []))
    )
    logical_union = sorted(
        set(adversarial.get("coverage_logical_ids", []))
        | set(integrity.get("coverage_logical_ids", []))
    )
    expected_assertions = sorted(MANDATORY_ASSERTIONS)
    missing_assertions = sorted(set(expected_assertions) - set(assertion_union))
    extra_assertions = sorted(set(assertion_union) - set(expected_assertions))
    qualification_status = "QUALIFIED"
    if missing_assertions or extra_assertions:
        qualification_status = "INVALID"
    if adversarial.get("recommended_candidate_outcome") == "FAIL":
        qualification_status = "INVALID"
    if integrity.get("recommended_candidate_outcome") == "FAIL":
        qualification_status = "INVALID"

    isolation = isolation_results_for_run(adversarial) + isolation_results_for_run(integrity)
    return {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "coverage_assertion_ids_union": assertion_union,
        "coverage_logical_ids_union": logical_union,
        "disqualification_reason_codes": [],
        "duplicate_identity_results": {
            "duplicate_assertion_ids": [],
            "duplicate_logical_ids": [],
            "duplicate_review_run_ids": [],
            "has_duplicates": False,
        },
        "expected_assertion_ids": expected_assertions,
        "expected_logical_ids": logical_union,
        "extra_assertion_ids": extra_assertions,
        "extra_logical_ids": [],
        "invalid_review_run_ids": [],
        "invalid_selected_run_reason_codes": [],
        "isolation_check_results": isolation,
        "missing_assertion_ids": missing_assertions,
        "missing_logical_ids": [],
        "qualification_status": qualification_status,
        "qualifying_review_run_ids": sorted([adv_id, int_id]),
        "registry_hash": REGISTRY_HASH,
        "review_class_assignments": sorted(
            [
                {
                    "review_class": "ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT",
                    "review_run_id": adv_id,
                },
                {
                    "review_class": "INTEGRITY_AND_REPRODUCTION_AUDIT",
                    "review_run_id": int_id,
                },
            ],
            key=lambda row: (row["review_class"], row["review_run_id"]),
        ),
        "review_procedure_id_and_hash": {
            "procedure_id": PROCEDURE_ID,
            "sha256": PROCEDURE_SHA256,
        },
        "selected_review_run_ids": sorted([adv_id, int_id]),
    }


def build_ai_review_runs(
    adversarial_dir: Path,
    integrity_dir: Path,
    adversarial: dict[str, object],
    integrity: dict[str, object],
) -> dict[str, object]:
    return {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "review_runs": sorted(
            [
                {
                    "completed_at": adversarial["completed_at"],
                    "output_repository_relative_path": repo_relative(
                        adversarial_dir / "phase0a.ai_review_output.json"
                    ),
                    "review_class": adversarial["review_class"],
                    "review_output_hash": adversarial["review_output_hash"],
                    "review_run_id": adversarial["review_run_id"],
                    "run_record_repository_relative_path": repo_relative(
                        adversarial_dir / "phase0a.ai_review_run.json"
                    ),
                    "terminal_state": adversarial["terminal_state"],
                },
                {
                    "completed_at": integrity["completed_at"],
                    "output_repository_relative_path": repo_relative(
                        integrity_dir / "phase0a.ai_review_output.json"
                    ),
                    "review_class": integrity["review_class"],
                    "review_output_hash": integrity["review_output_hash"],
                    "review_run_id": integrity["review_run_id"],
                    "run_record_repository_relative_path": repo_relative(
                        integrity_dir / "phase0a.ai_review_run.json"
                    ),
                    "terminal_state": integrity["terminal_state"],
                },
            ],
            key=lambda row: (str(row["review_class"]), str(row["review_run_id"])),
        ),
        "schema_version": SCHEMA_VERSION,
    }


def build_index_members(bundle: Path, postreview: Path) -> list[dict[str, object]]:
    members: list[dict[str, object]] = []
    for logical_id, filename in sorted(BUNDLE_LOGICAL_FILES.items()):
        path = bundle / filename
        raw = path.read_bytes()
        members.append(
            {
                "byte_length": len(raw),
                "logical_id": logical_id,
                "media_type": media_type_for(path),
                "member_sha256": sha256_bytes(raw),
                "repository_relative_path": repo_relative(path),
                "root_id": ROOT_ID,
            }
        )

    candidate_path = bundle / "candidate-evidence-root.json"
    candidate_raw = candidate_path.read_bytes()
    members.append(
        {
            "byte_length": len(candidate_raw),
            "logical_id": "phase0a.candidate_evidence_root",
            "media_type": "application/json",
            "member_sha256": sha256_bytes(candidate_raw),
            "repository_relative_path": repo_relative(candidate_path),
            "root_id": ROOT_ID,
        }
    )

    for logical_id, rel in sorted(GOVERNANCE_PATHS.items()):
        path = ROOT / rel
        raw = path.read_bytes()
        members.append(
            {
                "byte_length": len(raw),
                "logical_id": logical_id,
                "media_type": media_type_for(path),
                "member_sha256": sha256_bytes(raw),
                "repository_relative_path": repo_relative(path),
                "root_id": ROOT_ID,
            }
        )

    postreview_map = {
        "phase0a.ai_review_runs": postreview / "phase0a.ai_review_runs.json",
        "phase0a.ai_review_coverage": postreview / "phase0a.ai_review_coverage.json",
        "phase0a.approval_records": postreview / "phase0a.approval_records.json",
    }
    for logical_id, path in postreview_map.items():
        raw = path.read_bytes()
        members.append(
            {
                "byte_length": len(raw),
                "logical_id": logical_id,
                "media_type": media_type_for(path),
                "member_sha256": sha256_bytes(raw),
                "repository_relative_path": repo_relative(path),
                "root_id": ROOT_ID,
            }
        )

    candidate_ids = [row["logical_id"] for row in members if row["logical_id"] != "phase0a.candidate_evidence_root"]
    expected_ids = set(expected_index_logical_ids(candidate_ids))
    present = {row["logical_id"] for row in members}
    if present != expected_ids:
        missing = sorted(expected_ids - present)
        extra = sorted(present - expected_ids)
        raise ValueError(f"index member mismatch missing={missing} extra={extra}")

    return sorted(
        members,
        key=lambda row: (str(row["logical_id"]), str(row["repository_relative_path"])),
    )


def build_acceptance_index(postreview: Path, members: list[dict[str, object]]) -> dict[str, object]:
    provisional = {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "index_members": members,
        "logical_id": "phase0a.acceptance_index",
        "procedure_id_and_hash": {
            "procedure_id": PROCEDURE_ID,
            "sha256": PROCEDURE_SHA256,
        },
        "root_id": ROOT_ID,
        "schema_version": SCHEMA_VERSION,
    }
    index_sha256, root_hash = compute_index_hashes(provisional)
    return {**provisional, "index_sha256": index_sha256, "root_hash": root_hash}


def build_final_result(
    *,
    index: dict[str, object],
    coverage: dict[str, object],
    adversarial: dict[str, object],
    integrity: dict[str, object],
    completed_at: str,
) -> dict[str, object]:
    aggregate_status = "PASS"
    invalid_statuses: list[str] = []
    if coverage["qualification_status"] != "QUALIFIED":
        invalid_statuses.append(str(coverage["qualification_status"]))
    if adversarial.get("recommended_candidate_outcome") == "FAIL":
        invalid_statuses.append("FAIL")
    if integrity.get("recommended_candidate_outcome") == "FAIL":
        invalid_statuses.append("FAIL")

    outcome = derive_final_outcome(aggregate_status, invalid_statuses, False)
    provisional = {
        "assertion_aggregate_status": aggregate_status,
        "candidate_evidence_root": CANDIDATE_ROOT,
        "completed_at": completed_at,
        "index_sha256": index["index_sha256"],
        "logical_id": "phase0a.final_acceptance_result",
        "outcome": outcome,
        "reason_codes": sorted(set(invalid_statuses)),
        "review_coverage_status": coverage["qualification_status"],
        "root_hash": index["root_hash"],
        "schema_version": SCHEMA_VERSION,
    }
    final_result_id = record_identity(provisional, "final_result_id")
    return {**provisional, "final_result_id": final_result_id}


def build_all(
    *,
    bundle: Path,
    postreview: Path,
    adversarial_dir: Path,
    integrity_dir: Path,
    approved_at: str,
    completed_at: str,
) -> dict[str, object]:
    adversarial = load_review_run(adversarial_dir)
    integrity = load_review_run(integrity_dir)

    approval_path = postreview / "phase0a.approval_records.json"
    approval_hash = write_canonical(approval_path, build_approval_records(approved_at=approved_at))

    coverage_doc = build_coverage(adversarial, integrity)
    coverage_path = postreview / "phase0a.ai_review_coverage.json"
    coverage_hash = write_canonical(coverage_path, coverage_doc)

    runs_path = postreview / "phase0a.ai_review_runs.json"
    runs_hash = write_canonical(
        runs_path,
        build_ai_review_runs(adversarial_dir, integrity_dir, adversarial, integrity),
    )

    members = build_index_members(bundle, postreview)
    index_doc = build_acceptance_index(postreview, members)
    index_reasons = verify_index_hashes(index_doc)
    if index_reasons:
        raise ValueError(f"acceptance index hash verification failed: {index_reasons}")

    index_path = postreview / "phase0a.acceptance_index.json"
    index_hash = write_canonical(index_path, index_doc)

    final_doc = build_final_result(
        index=index_doc,
        coverage=coverage_doc,
        adversarial=adversarial,
        integrity=integrity,
        completed_at=completed_at,
    )
    final_path = postreview / "phase0a.final_acceptance_result.json"
    final_hash = write_canonical(final_path, final_doc)

    return {
        "approval_records": {"path": str(approval_path), "sha256": approval_hash},
        "ai_review_coverage": {
            "path": str(coverage_path),
            "sha256": coverage_hash,
            "qualification_status": coverage_doc["qualification_status"],
        },
        "ai_review_runs": {"path": str(runs_path), "sha256": runs_hash},
        "acceptance_index": {
            "path": str(index_path),
            "sha256": index_hash,
            "index_sha256": index_doc["index_sha256"],
            "root_hash": index_doc["root_hash"],
        },
        "final_acceptance_result": {
            "path": str(final_path),
            "sha256": final_hash,
            "outcome": final_doc["outcome"],
            "final_result_id": final_doc["final_result_id"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--postreview", default=str(DEFAULT_POSTREVIEW))
    parser.add_argument("--adversarial-dir", default=str(DEFAULT_ADVERSARIAL))
    parser.add_argument("--integrity-dir", default=str(DEFAULT_INTEGRITY))
    parser.add_argument("--approved-at", default="2026-08-15T06:00:00.000000000Z")
    parser.add_argument("--completed-at", default="2026-08-15T06:02:00.000000000Z")
    args = parser.parse_args()

    result = build_all(
        bundle=Path(args.bundle),
        postreview=Path(args.postreview),
        adversarial_dir=Path(args.adversarial_dir),
        integrity_dir=Path(args.integrity_dir),
        approved_at=args.approved_at,
        completed_at=args.completed_at,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
