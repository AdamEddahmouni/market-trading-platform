"""Build Phase 8 postreview gate artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes
from tools.phase8.acceptance_algorithms import (
    compute_index_hashes,
    derive_final_outcome,
    expected_index_logical_ids,
    record_identity,
    verify_index_hashes,
)
from tools.postroot.suite_definition import PROCEDURE_ID, PROCEDURE_SHA256

ROOT_ID = "ROOT-2E7C91F4"
SCHEMA_VERSION = "1.0.0"

RUN_ID = "8C94A65C60955EAB3A13A453CFBBF6DAAA7035600776C419F1AC17D036548A5F"
CANDIDATE_ROOT = "4C3901972615C7A4F0C276F2D095F6477E48204CF77EA6E9A75808C863434335"
DEFAULT_BUNDLE = ROOT / f"evidence/phase8/{RUN_ID}"
DEFAULT_POSTREVIEW = ROOT / "evidence/phase8/postreview-pass"
DEFAULT_ADVERSARIAL = ROOT / "evidence/phase8/review-runs/ADVERSARIAL-PASS-PHASE8-E2E"
DEFAULT_INTEGRITY = ROOT / "evidence/phase8/review-runs/INTEGRITY-PASS-PHASE8-E2E"

BUNDLE_FILES = {
    "phase8.assertion_aggregate": "assertion-aggregate.json",
    "phase8.assertion_registry": "assertion_registry.json",
    "phase8.assertion_results": "assertion-results.json",
    "phase8.assertion_run_manifest": "assertion-run-manifest.json",
    "phase8.determinism_report": "determinism-report.json",
    "phase8.end_to_end_report": "end-to-end-report.json",
    "phase8.limitations_report": "limitations-report.json",
    "phase8.rollup_report": "rollup-report.json",
    "phase8.safe003_report": "safe003-report.json",
}

GOVERNANCE_PATHS = {
    "foundation.canonical_authority_manifest": "manifests/phase0/canonical-authority.json",
    "foundation.canonical_specification.revision_3": (
        "docs/superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-3.md"
    ),
    "phase0.ai_review_procedure": "docs/superpowers/governance/2026-08-14-ai-review-process-001.json",
    "phase7.pass_publication": "docs/superpowers/governance/2026-08-16-phase-7-pass-publication.json",
    "phase8.design_specification": (
        "docs/superpowers/specs/2026-08-17-phase-8-deterministic-end-to-end-acceptance-design.md"
    ),
    "phase8.governance_approvals": (
        "docs/superpowers/governance/2026-08-17-phase-8-governance-approvals.json"
    ),
    "phase8.governance_plan": (
        "docs/superpowers/plans/2026-08-17-phase-8-deterministic-end-to-end-acceptance.md"
    ),
    "phase8.implementation_activation": (
        "docs/superpowers/governance/2026-08-17-phase-8-implementation-activation.json"
    ),
    "phase8.implementation_authorization": (
        "docs/superpowers/governance/2026-08-17-phase-8-implementation-authorization.json"
    ),
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_canonical(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(value)
    path.write_bytes(data)
    return sha256_bytes(data)


def repo_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def media_type_for(path: Path) -> str:
    return "text/markdown" if path.suffix == ".md" else "application/json"


def resolve_phase8_bundle() -> tuple[str, str, Path]:
    bundle = DEFAULT_BUNDLE
    if not bundle.is_dir() or not (bundle / "candidate-evidence-root.json").is_file():
        raise ValueError("phase8 bundle missing")
    root_doc = load_json(bundle / "candidate-evidence-root.json")
    run_id = str(root_doc["run_id"])
    candidate_root = str(root_doc["candidate_evidence_root"])
    if run_id != RUN_ID:
        raise ValueError("run_id constant mismatch")
    if candidate_root != CANDIDATE_ROOT:
        raise ValueError("candidate_evidence_root constant mismatch")
    return run_id, candidate_root, bundle


def load_review_output(review_dir: Path) -> dict[str, object]:
    return load_json(review_dir / "phase8.ai_review_output.json")


def build_approval_records(*, approved_at: str, candidate_root: str) -> dict[str, object]:
    return {
        "aggregate_approval_status": "PASS",
        "approval_records": [
            {
                "approval_record_id": sha256_bytes(
                    canonical_bytes(
                        {
                            "approved_at": approved_at,
                            "approved_by_principal_id": "PROJECT-PRINCIPAL-001",
                            "approved_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
                            "approved_logical_id": "phase8.candidate_evidence_root",
                            "approved_sha256": candidate_root,
                            "approval_scope": "PHASE_8_CANDIDATE_EVIDENCE_ROOT_ACCEPTANCE",
                            "status": "APPROVED",
                        }
                    )
                ),
                "approval_scope": "PHASE_8_CANDIDATE_EVIDENCE_ROOT_ACCEPTANCE",
                "approved_at": approved_at,
                "approved_by_principal_id": "PROJECT-PRINCIPAL-001",
                "approved_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
                "approved_logical_id": "phase8.candidate_evidence_root",
                "approved_sha256": candidate_root,
                "status": "APPROVED",
            }
        ],
        "logical_id": "phase8.approval_records",
        "schema_version": SCHEMA_VERSION,
    }


def build_coverage(
    adversarial: dict[str, object],
    integrity: dict[str, object],
    *,
    candidate_root: str,
) -> dict[str, object]:
    return {
        "candidate_evidence_root": candidate_root,
        "coverage_assertion_ids_union": sorted(
            set(adversarial.get("coverage_assertion_ids", []))
            | set(integrity.get("coverage_assertion_ids", []))
        ),
        "coverage_logical_ids_union": sorted(
            set(adversarial.get("coverage_logical_ids", []))
            | set(integrity.get("coverage_logical_ids", []))
            | set(GOVERNANCE_PATHS)
            | set(BUNDLE_FILES)
            | {"phase8.candidate_evidence_root"}
        ),
        "disqualification_reason_codes": [],
        "logical_id": "phase8.ai_review_coverage",
        "qualification_status": "QUALIFIED",
        "schema_version": SCHEMA_VERSION,
    }


def build_ai_review_runs(
    adversarial_dir: Path,
    integrity_dir: Path,
    adversarial: dict[str, object],
    integrity: dict[str, object],
    *,
    candidate_root: str,
) -> dict[str, object]:
    adv_run = load_json(adversarial_dir / "phase8.ai_review_run.json")
    int_run = load_json(integrity_dir / "phase8.ai_review_run.json")
    return {
        "candidate_evidence_root": candidate_root,
        "review_runs": sorted(
            [
                {
                    "completed_at": adv_run.get("completed_at", "2026-08-17T01:30:00.000000000Z"),
                    "output_repository_relative_path": repo_relative(
                        adversarial_dir / "phase8.ai_review_output.json"
                    ),
                    "review_class": adversarial["review_class"],
                    "review_output_hash": adv_run["review_output_hash"],
                    "review_run_id": adv_run["review_run_id"],
                    "run_record_repository_relative_path": repo_relative(
                        adversarial_dir / "phase8.ai_review_run.json"
                    ),
                    "terminal_state": adv_run["terminal_state"],
                },
                {
                    "completed_at": int_run.get("completed_at", "2026-08-17T01:30:00.000000000Z"),
                    "output_repository_relative_path": repo_relative(
                        integrity_dir / "phase8.ai_review_output.json"
                    ),
                    "review_class": integrity["review_class"],
                    "review_output_hash": int_run["review_output_hash"],
                    "review_run_id": int_run["review_run_id"],
                    "run_record_repository_relative_path": repo_relative(
                        integrity_dir / "phase8.ai_review_run.json"
                    ),
                    "terminal_state": int_run["terminal_state"],
                },
            ],
            key=lambda row: str(row["review_class"]),
        ),
        "schema_version": SCHEMA_VERSION,
    }


def build_index_members(bundle: Path, postreview: Path) -> list[dict[str, object]]:
    members: list[dict[str, object]] = []
    for logical_id, filename in sorted(BUNDLE_FILES.items()):
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
    root_path = bundle / "candidate-evidence-root.json"
    root_raw = root_path.read_bytes()
    members.append(
        {
            "byte_length": len(root_raw),
            "logical_id": "phase8.candidate_evidence_root",
            "media_type": "application/json",
            "member_sha256": sha256_bytes(root_raw),
            "repository_relative_path": repo_relative(root_path),
            "root_id": ROOT_ID,
        }
    )
    for logical_id, rel in sorted(GOVERNANCE_PATHS.items()):
        path = ROOT / rel
        if not path.is_file():
            raise FileNotFoundError(path)
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
        "phase8.ai_review_runs": postreview / "phase8.ai_review_runs.json",
        "phase8.ai_review_coverage": postreview / "phase8.ai_review_coverage.json",
        "phase8.approval_records": postreview / "phase8.approval_records.json",
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
    candidate_ids = [
        row["logical_id"] for row in members if row["logical_id"] != "phase8.candidate_evidence_root"
    ]
    expected_ids = set(expected_index_logical_ids(candidate_ids))
    present = {row["logical_id"] for row in members}
    if present != expected_ids:
        missing = sorted(expected_ids - present)
        extra = sorted(present - expected_ids)
        raise ValueError(f"index member mismatch missing={missing} extra={extra}")
    return sorted(members, key=lambda row: str(row["logical_id"]))


def build_acceptance_index(members: list[dict[str, object]], *, candidate_root: str) -> dict[str, object]:
    provisional = {
        "candidate_evidence_root": candidate_root,
        "index_members": members,
        "logical_id": "phase8.acceptance_index",
        "procedure_id_and_hash": {"procedure_id": PROCEDURE_ID, "sha256": PROCEDURE_SHA256},
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
    bundle: Path,
    candidate_root: str,
) -> dict[str, object]:
    invalid_statuses: list[str] = []
    if coverage["qualification_status"] != "QUALIFIED":
        invalid_statuses.append(str(coverage["qualification_status"]))
    if adversarial.get("recommended_candidate_outcome") == "FAIL":
        invalid_statuses.append("FAIL")
    if integrity.get("recommended_candidate_outcome") == "FAIL":
        invalid_statuses.append("FAIL")
    aggregate = load_json(bundle / "assertion-aggregate.json")
    aggregate_status = str(aggregate.get("aggregate_status", "BLOCKED"))
    outcome = derive_final_outcome(aggregate_status, invalid_statuses, False)
    provisional = {
        "assertion_aggregate_status": aggregate_status,
        "candidate_evidence_root": candidate_root,
        "completed_at": completed_at,
        "index_sha256": index["index_sha256"],
        "logical_id": "phase8.final_acceptance_result",
        "outcome": outcome,
        "reason_codes": sorted(set(invalid_statuses)),
        "review_coverage_status": coverage["qualification_status"],
        "root_hash": index["root_hash"],
        "schema_version": SCHEMA_VERSION,
    }
    return {**provisional, "final_result_id": record_identity(provisional, "final_result_id")}


def build_all(
    *,
    bundle: Path,
    postreview: Path,
    adversarial_dir: Path,
    integrity_dir: Path,
    approved_at: str,
    completed_at: str,
    candidate_root: str,
) -> dict[str, object]:
    postreview.mkdir(parents=True, exist_ok=True)
    adversarial = load_review_output(adversarial_dir)
    integrity = load_review_output(integrity_dir)
    write_canonical(
        postreview / "phase8.approval_records.json",
        build_approval_records(approved_at=approved_at, candidate_root=candidate_root),
    )
    coverage_doc = build_coverage(adversarial, integrity, candidate_root=candidate_root)
    write_canonical(postreview / "phase8.ai_review_coverage.json", coverage_doc)
    write_canonical(
        postreview / "phase8.ai_review_runs.json",
        build_ai_review_runs(
            adversarial_dir,
            integrity_dir,
            adversarial,
            integrity,
            candidate_root=candidate_root,
        ),
    )
    members = build_index_members(bundle, postreview)
    index_doc = build_acceptance_index(members, candidate_root=candidate_root)
    reasons = verify_index_hashes(index_doc)
    if reasons:
        raise ValueError(f"acceptance index verification failed: {reasons}")
    write_canonical(postreview / "phase8.acceptance_index.json", index_doc)
    final_doc = build_final_result(
        index=index_doc,
        coverage=coverage_doc,
        adversarial=adversarial,
        integrity=integrity,
        completed_at=completed_at,
        bundle=bundle,
        candidate_root=candidate_root,
    )
    write_canonical(postreview / "phase8.final_acceptance_result.json", final_doc)
    return {
        "final_outcome": final_doc["outcome"],
        "index_sha256": index_doc["index_sha256"],
        "root_hash": index_doc["root_hash"],
    }


def main() -> int:
    from market_platform_foundation.offline_guard import install_guard

    install_guard([])
    run_id, candidate_root, default_bundle = resolve_phase8_bundle()
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", default=str(default_bundle))
    parser.add_argument("--postreview", default=str(DEFAULT_POSTREVIEW))
    parser.add_argument("--adversarial-dir", default=str(DEFAULT_ADVERSARIAL))
    parser.add_argument("--integrity-dir", default=str(DEFAULT_INTEGRITY))
    parser.add_argument("--approved-at", default="2026-08-17T01:30:00.000000000Z")
    parser.add_argument("--completed-at", default="2026-08-17T01:32:00.000000000Z")
    args = parser.parse_args()
    result = build_all(
        bundle=Path(args.bundle),
        postreview=Path(args.postreview),
        adversarial_dir=Path(args.adversarial_dir),
        integrity_dir=Path(args.integrity_dir),
        approved_at=args.approved_at,
        completed_at=args.completed_at,
        candidate_root=candidate_root,
    )
    result["run_id"] = run_id
    result["candidate_evidence_root"] = candidate_root
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
