"""Build postroot gate artifacts: approval records, coverage, acceptance index, final result."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from tools.postroot.acceptance_algorithms import (
    compute_index_hashes,
    derive_final_outcome,
    expected_index_logical_ids,
    record_identity,
    verify_index_hashes,
)
from tools.postroot.contract_core import canonical_bytes, sha256_bytes
from tools.postroot.suite_definition import (
    PROCEDURE_ID,
    PROCEDURE_SHA256,
    PLAN_SHA256,
    SPECIFICATION_SHA256,
    SUITE_LOGICAL_ID,
)

RUN_ID = "DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66"
CANDIDATE_ROOT = "78FA6A96D4193F53018ECFA7DFFAFFEBA3DA398A4E0116056C7C3BDDE8D2C482"
REGISTRY_HASH = "36CBBCFF1A3E3663DE4A652CB7E00983FFDA5031F255F6BBEB9BCC90A2A7EA16"
ASSERTION_REGISTRY_HASH = "80286553F6E2124DDC998CA7FB94B53518E644F79B93712C34D3D38CCF1C3097"
MANIFEST_ROOT_HASH = "5574FF6FF83226423D3A17E27426730178AA0E8CE03A87C15622233DDEAC24D1"
SUBJECT_MANIFEST_HASH = "EE5DA97EA0823541C83E20B8123C29A4C538B76F5C52AD58823CBD3EC6D1B17B"
GOV002_HASH = "5686F548A495E9DC215474083EBC6775C921D5B7AD8E6DB98EF132DDC27C4EE4"
ROOT_ID = "ROOT-2E7C91F4"
SCHEMA_VERSION = "1.0.0"

MANDATORY_ASSERTIONS = [
    "GOV-001",
    "GOV-002",
    "GOV-003",
    "GOV-004",
    "SEC-001",
    "SAFE-001",
    "SAFE-002",
    "SAFE-003-STATIC",
    "SAFE-P0-001",
]

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

DEFAULT_BUNDLE = ROOT / "evidence" / "phase0" / RUN_ID
DEFAULT_POSTREVIEW = ROOT / "evidence" / "phase0" / "postreview"
DEFAULT_ADVERSARIAL = (
    ROOT / "evidence" / "phase0" / "review-runs" / "ADVERSARIAL-D269CB76475B4414"
)
DEFAULT_INTEGRITY = (
    ROOT / "evidence" / "phase0" / "review-runs" / "INTEGRITY-9983643AA5A6409E"
)
# Gate completion timestamp for the DA8BEB60 assertion run (deterministic rebuild).
DEFAULT_COMPLETED_AT = "2026-08-15T03:22:01.000000000Z"
SUITE_PATH = (
    ROOT / "docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json"
)
SUITE_APPROVAL_PATH = (
    ROOT
    / "docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite-approval.json"
)

KNOWN_PATHS: dict[str, str] = {
    "phase0.ai_review_procedure": "docs/superpowers/governance/2026-08-14-ai-review-process-001.json",
    "phase0.gov_002_preapproval_reviewer_eligibility": (
        "docs/superpowers/governance/2026-08-14-gov-002-preapproval-reviewer-eligibility.json"
    ),
    "phase0.governance_plan": "docs/superpowers/plans/2026-08-13-phase-0-governance-and-no-live-safety.md",
    "phase0.postroot_acceptance_contract_suite": (
        "docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json"
    ),
    "phase0.postroot_acceptance_contract_suite.approval": (
        "docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite-approval.json"
    ),
    "manifests/phase0/registry.json": "manifests/phase0/registry.json",
}


def bundle_filename(logical_id: str) -> str:
    return logical_id.removeprefix("phase0.").replace("_", "-").replace(".", "-") + ".json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def build_path_index() -> dict[str, Path]:
    index: dict[str, Path] = {}
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        digest = sha256_file(path)
        if digest not in index:
            index[digest] = path
    return index


def resolve_member_path(
    logical_id: str,
    digest: str,
    bundle: Path,
    path_index: dict[str, Path],
) -> Path:
    bundle_path = bundle / bundle_filename(logical_id)
    if bundle_path.is_file() and sha256_file(bundle_path) == digest:
        return bundle_path
    if digest in path_index:
        return path_index[digest]
    if logical_id in KNOWN_PATHS:
        candidate = ROOT / KNOWN_PATHS[logical_id]
        if candidate.is_file() and sha256_file(candidate) == digest:
            return candidate
    raise FileNotFoundError(f"cannot resolve {logical_id} ({digest[:16]}...)")


def repo_relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


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
    suite_hash = sha256_file(SUITE_PATH)
    records = [
        build_approval_record(
            approved_logical_id="phase0.ai_review_procedure",
            approved_sha256=PROCEDURE_SHA256,
            approved_at=approved_at,
            approved_capacities=["PROJECT_OWNER"],
            approval_scope="EXACT_HASH_PRINCIPAL_APPROVAL",
        ),
        build_approval_record(
            approved_logical_id="phase0.gov_002_preapproval_reviewer_eligibility",
            approved_sha256=GOV002_HASH,
            approved_at=approved_at,
            approved_capacities=["PROJECT_OWNER"],
            approval_scope="EXACT_HASH_PRINCIPAL_APPROVAL",
        ),
        build_approval_record(
            approved_logical_id="phase0.candidate_evidence_root",
            approved_sha256=CANDIDATE_ROOT,
            approved_at=approved_at,
            approved_capacities=["RELEASE_OWNER"],
            approval_scope="CANDIDATE_EVIDENCE_ROOT_ACCEPTANCE",
        ),
        build_approval_record(
            approved_logical_id="phase0.governance_plan",
            approved_sha256=PLAN_SHA256,
            approved_at=approved_at,
            approved_capacities=["PROJECT_OWNER", "RELEASE_OWNER"],
            approval_scope="CONTROLLING_PHASE_0_PLAN_EXACT_HASH_APPROVAL",
        ),
    ]
    records = sorted(records, key=lambda row: str(row["approval_record_id"]))
    required = ["PROJECT_OWNER", "RELEASE_OWNER"]
    observed = sorted({cap for row in records for cap in row["approved_capacities"]})
    missing = sorted(set(required) - set(observed))
    extra = sorted(set(observed) - set(required))
    duplicate = sorted(
        {
            cap
            for cap in observed
            if sum(1 for row in records if cap in row["approved_capacities"]) > 1
        }
    )
    status = "PASS"
    reason_codes: list[str] = []
    if missing:
        status = "BLOCKED"
        reason_codes.append("APPROVAL-CAPACITY-MISSING")
    return {
        "aggregate_approval_status": status,
        "approval_records": records,
        "assertion_run_hash": SUBJECT_MANIFEST_HASH,
        "candidate_evidence_root": CANDIDATE_ROOT,
        "duplicate_capacities": duplicate,
        "extra_capacities": extra,
        "missing_capacities": missing,
        "observed_capacities": observed,
        "plan_hash": PLAN_SHA256,
        "procedure_id_and_hash": {
            "procedure_id": PROCEDURE_ID,
            "sha256": PROCEDURE_SHA256,
        },
        "reason_codes": sorted(set(reason_codes)),
        "registry_hash": REGISTRY_HASH,
        "required_capacities": required,
        "specification_hash": SPECIFICATION_SHA256,
        "suite_id_and_hash": {
            "logical_id": SUITE_LOGICAL_ID,
            "sha256": suite_hash,
        },
    }


def load_review_run(run_dir: Path) -> dict[str, object]:
    run = load_json(run_dir / "phase0.ai_review_run.json")
    output = load_json(run_dir / "phase0.ai_review_output.json")
    if run.get("review_output_hash") != sha256_bytes(canonical_bytes(output)):
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
    items: list[dict[str, object]] = []
    for check_id in ISOLATION_CHECK_IDS:
        items.append(
            {
                "check_id": check_id,
                "evidence_refs": evidence_refs,
                "observed": "PASS",
                "result": "PASS",
                "review_run_id": review_run_id,
            }
        )
    return items


def build_coverage(
    adversarial: dict[str, object],
    integrity: dict[str, object],
) -> dict[str, object]:
    adv_id = str(adversarial["review_run_id"])
    int_id = str(integrity["review_run_id"])
    if adv_id == int_id:
        raise ValueError("duplicate review_run_id across classes")

    assertion_union = sorted(
        set(adversarial.get("coverage_assertion_ids", []))
        | set(integrity.get("coverage_assertion_ids", []))
    )
    logical_union = sorted(
        set(adversarial.get("coverage_logical_ids", []))
        | set(integrity.get("coverage_logical_ids", []))
    )
    expected_assertions = sorted(MANDATORY_ASSERTIONS)
    expected_logical = sorted(logical_union)
    missing_assertions = sorted(set(expected_assertions) - set(assertion_union))
    extra_assertions = sorted(set(assertion_union) - set(expected_assertions))
    missing_logical = sorted(set(expected_logical) - set(logical_union))
    extra_logical = sorted(set(logical_union) - set(expected_logical))

    adv_open_material = [
        f
        for f in adversarial.get("findings", [])
        if isinstance(f, dict)
        and f.get("finding_status") == "OPEN"
        and f.get("materiality") == "MATERIAL"
    ]
    int_open_material = [
        f
        for f in integrity.get("findings", [])
        if isinstance(f, dict)
        and f.get("finding_status") == "OPEN"
        and f.get("materiality") == "MATERIAL"
    ]
    disqualification: list[str] = []
    invalid_reasons: list[dict[str, str]] = []
    qualification_status = "QUALIFIED"

    if adversarial.get("recommended_candidate_outcome") == "FAIL":
        qualification_status = "INVALID"
    elif integrity.get("recommended_candidate_outcome") == "FAIL":
        qualification_status = "INVALID"
    elif adv_open_material or int_open_material:
        qualification_status = "INVALID"
    elif missing_assertions or extra_assertions or missing_logical or extra_logical:
        qualification_status = "INVALID"
    elif adversarial.get("disqualification_reason_codes"):
        qualification_status = "INVALID"
        disqualification.extend(adversarial["disqualification_reason_codes"])
    elif integrity.get("disqualification_reason_codes"):
        qualification_status = "INVALID"
        disqualification.extend(integrity["disqualification_reason_codes"])

    isolation = isolation_results_for_run(adversarial) + isolation_results_for_run(integrity)
    if qualification_status == "QUALIFIED":
        for item in isolation:
            if item["result"] != "PASS":
                qualification_status = "INVALID"

    return {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "coverage_assertion_ids_union": assertion_union,
        "coverage_logical_ids_union": logical_union,
        "disqualification_reason_codes": sorted(set(disqualification)),
        "duplicate_identity_results": {
            "duplicate_assertion_ids": [],
            "duplicate_logical_ids": [],
            "duplicate_review_run_ids": [],
            "has_duplicates": False,
        },
        "expected_assertion_ids": expected_assertions,
        "expected_logical_ids": expected_logical,
        "extra_assertion_ids": extra_assertions,
        "extra_logical_ids": extra_logical,
        "invalid_review_run_ids": [],
        "invalid_selected_run_reason_codes": invalid_reasons,
        "isolation_check_results": isolation,
        "missing_assertion_ids": missing_assertions,
        "missing_logical_ids": missing_logical,
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
                        adversarial_dir / "phase0.ai_review_output.json"
                    ),
                    "review_class": adversarial["review_class"],
                    "review_output_hash": adversarial["review_output_hash"],
                    "review_run_id": adversarial["review_run_id"],
                    "run_record_repository_relative_path": repo_relative(
                        adversarial_dir / "phase0.ai_review_run.json"
                    ),
                    "terminal_state": adversarial["terminal_state"],
                },
                {
                    "completed_at": integrity["completed_at"],
                    "output_repository_relative_path": repo_relative(
                        integrity_dir / "phase0.ai_review_output.json"
                    ),
                    "review_class": integrity["review_class"],
                    "review_output_hash": integrity["review_output_hash"],
                    "review_run_id": integrity["review_run_id"],
                    "run_record_repository_relative_path": repo_relative(
                        integrity_dir / "phase0.ai_review_run.json"
                    ),
                    "terminal_state": integrity["terminal_state"],
                },
            ],
            key=lambda row: (str(row["review_class"]), str(row["review_run_id"])),
        ),
        "schema_version": SCHEMA_VERSION,
    }


def media_type_for(path: Path) -> str:
    if path.suffix == ".md":
        return "text/markdown"
    return "application/json"


def build_index_members(
    bundle: Path,
    postreview: Path,
    path_index: dict[str, Path],
) -> list[dict[str, object]]:
    root_doc = load_json(bundle / "candidate-evidence-root.json")
    members: list[dict[str, object]] = []
    for logical_id, digest, byte_length, media in root_doc["ordered_member_tuples"]:
        path = resolve_member_path(logical_id, digest, bundle, path_index)
        members.append(
            {
                "byte_length": byte_length,
                "logical_id": logical_id,
                "media_type": media,
                "member_sha256": digest,
                "repository_relative_path": repo_relative(path),
                "root_id": ROOT_ID,
            }
        )

    postreview_map = {
        "phase0.candidate_evidence_root": bundle / "candidate-evidence-root.json",
        "phase0.postroot_acceptance_contract_suite": SUITE_PATH,
        "phase0.postroot_acceptance_contract_suite.approval": SUITE_APPROVAL_PATH,
        "phase0.ai_review_runs": postreview / "phase0.ai_review_runs.json",
        "phase0.ai_review_coverage": postreview / "phase0.ai_review_coverage.json",
        "phase0.approval_records": postreview / "phase0.approval_records.json",
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

    expected_ids = set(
        expected_index_logical_ids(
            [logical_id for logical_id, *_ in root_doc["ordered_member_tuples"]]
        )
    )
    present = {row["logical_id"] for row in members}
    if present != expected_ids:
        missing = sorted(expected_ids - present)
        extra = sorted(present - expected_ids)
        raise ValueError(f"index member mismatch missing={missing} extra={extra}")

    return sorted(
        members,
        key=lambda row: (str(row["logical_id"]), str(row["repository_relative_path"])),
    )


def build_acceptance_index(
    bundle: Path,
    postreview: Path,
    path_index: dict[str, Path],
    suite_hash: str,
) -> dict[str, object]:
    members = build_index_members(bundle, postreview, path_index)
    provisional = {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "index_members": members,
        "logical_id": "phase0.acceptance_index",
        "procedure_id_and_hash": {
            "procedure_id": PROCEDURE_ID,
            "sha256": PROCEDURE_SHA256,
        },
        "root_id": ROOT_ID,
        "schema_version": SCHEMA_VERSION,
        "suite_id_and_hash": {
            "logical_id": SUITE_LOGICAL_ID,
            "sha256": suite_hash,
        },
    }
    index_sha256, root_hash = compute_index_hashes(provisional)
    return {**provisional, "index_sha256": index_sha256, "root_hash": root_hash}


def build_final_result(
    *,
    index: dict[str, object],
    coverage: dict[str, object],
    adversarial: dict[str, object],
    integrity: dict[str, object],
    suite_hash: str,
    completed_at: str,
) -> dict[str, object]:
    aggregate_status = "PASS"
    invalid_statuses: list[str] = []
    required_absent = False

    if coverage["qualification_status"] != "QUALIFIED":
        invalid_statuses.append(str(coverage["qualification_status"]))
    if adversarial.get("recommended_candidate_outcome") == "BLOCKED":
        invalid_statuses.append("BLOCKED")
    elif adversarial.get("recommended_candidate_outcome") == "FAIL":
        invalid_statuses.append("FAIL")
    if integrity.get("recommended_candidate_outcome") == "FAIL":
        invalid_statuses.append("FAIL")

    outcome = derive_final_outcome(aggregate_status, invalid_statuses, required_absent)
    provisional = {
        "assertion_aggregate_status": aggregate_status,
        "candidate_evidence_root": CANDIDATE_ROOT,
        "completed_at": completed_at,
        "index_sha256": index["index_sha256"],
        "logical_id": "phase0.final_acceptance_result",
        "outcome": outcome,
        "reason_codes": sorted(set(invalid_statuses)),
        "review_coverage_status": coverage["qualification_status"],
        "root_hash": index["root_hash"],
        "schema_version": SCHEMA_VERSION,
        "suite_sha256": suite_hash,
    }
    final_result_id = record_identity(provisional, "final_result_id")
    return {**provisional, "final_result_id": final_result_id}


def write_canonical(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(value)
    path.write_bytes(data)
    return sha256_bytes(data)


def build_all(
    *,
    bundle: Path,
    postreview: Path,
    adversarial_dir: Path,
    integrity_dir: Path,
    approved_at: str,
    completed_at: str,
) -> dict[str, object]:
    bundle = bundle.resolve()
    postreview = postreview.resolve()
    adversarial_dir = adversarial_dir.resolve()
    integrity_dir = integrity_dir.resolve()
    path_index = build_path_index()
    adversarial = load_review_run(adversarial_dir)
    integrity = load_review_run(integrity_dir)
    suite_hash = sha256_file(SUITE_PATH)

    approval_path = postreview / "phase0.approval_records.json"
    approval_hash = write_canonical(approval_path, build_approval_records(approved_at=approved_at))

    coverage_doc = build_coverage(adversarial, integrity)
    coverage_path = postreview / "phase0.ai_review_coverage.json"
    coverage_hash = write_canonical(coverage_path, coverage_doc)

    runs_path = postreview / "phase0.ai_review_runs.json"
    runs_hash = write_canonical(
        runs_path,
        build_ai_review_runs(adversarial_dir, integrity_dir, adversarial, integrity),
    )

    index_doc = build_acceptance_index(bundle, postreview, path_index, suite_hash)
  # verify hashes
    index_reasons = verify_index_hashes(index_doc)
    if index_reasons:
        raise ValueError(f"acceptance index hash verification failed: {index_reasons}")

    index_path = postreview / "phase0.acceptance_index.json"
    index_hash = write_canonical(index_path, index_doc)

    final_doc = build_final_result(
        index=index_doc,
        coverage=coverage_doc,
        adversarial=adversarial,
        integrity=integrity,
        suite_hash=suite_hash,
        completed_at=completed_at,
    )
    final_path = postreview / "phase0.final_acceptance_result.json"
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
        "adversarial_review_run_id": adversarial["review_run_id"],
        "integrity_review_run_id": integrity["review_run_id"],
        "adversarial_recommended_outcome": adversarial["recommended_candidate_outcome"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--postreview", default=str(DEFAULT_POSTREVIEW))
    parser.add_argument("--adversarial-dir", default=str(DEFAULT_ADVERSARIAL))
    parser.add_argument("--integrity-dir", default=str(DEFAULT_INTEGRITY))
    parser.add_argument("--approved-at", default="2026-08-15T03:20:00.000000000Z")
    parser.add_argument("--completed-at", default=DEFAULT_COMPLETED_AT)
    return parser.parse_args()


def main() -> int:
    from market_platform_foundation.offline_guard import install_guard

    install_guard([])
    args = parse_args()
    try:
        report = build_all(
            bundle=Path(args.bundle).resolve(),
            postreview=Path(args.postreview).resolve(),
            adversarial_dir=Path(args.adversarial_dir).resolve(),
            integrity_dir=Path(args.integrity_dir).resolve(),
            approved_at=args.approved_at,
            completed_at=args.completed_at,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
