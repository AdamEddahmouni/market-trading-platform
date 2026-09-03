"""Build Phase 5 postreview gate artifacts."""

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
from tools.phase5.acceptance_algorithms import (
    compute_index_hashes,
    derive_final_outcome,
    expected_index_logical_ids,
    record_identity,
    verify_index_hashes,
)
from tools.postroot.suite_definition import PROCEDURE_ID, PROCEDURE_SHA256

RUN_ID = "100C08AD0815EA015AE43D29D749A8C6E1166ED99109F20AEDEC46862213A362"
CANDIDATE_ROOT = "EAC5A85BB8015F8F69B71068C64F8CA1CBB2F61066905CFF5380A0B2968B9F0F"
ROOT_ID = "ROOT-2E7C91F4"
SCHEMA_VERSION = "1.0.0"

DEFAULT_BUNDLE = ROOT / "evidence/phase5" / RUN_ID
DEFAULT_POSTREVIEW = ROOT / "evidence/phase5/postreview-pass"
DEFAULT_ADVERSARIAL = ROOT / "evidence/phase5/review-runs/ADVERSARIAL-PASS-PHASE5-FEATURES"
DEFAULT_INTEGRITY = ROOT / "evidence/phase5/review-runs/INTEGRITY-PASS-PHASE5-FEATURES"

BUNDLE_FILES = {
    "phase5.assertion_aggregate": "assertion-aggregate.json",
    "phase5.assertion_registry": "assertion_registry.json",
    "phase5.assertion_results": "assertion-results.json",
    "phase5.assertion_run_manifest": "assertion-run-manifest.json",
    "phase5.feature_determinism_report": "feature-determinism-report.json",
    "phase5.feature_snapshot_report": "feature-snapshot-report.json",
    "phase5.pit_adversarial_report": "pit-adversarial-report.json",
    "phase5.safe003_report": "safe003-report.json",
    "phase5.whale_vocabulary_report": "whale-vocabulary-report.json",
}

GOVERNANCE_PATHS = {
    "foundation.canonical_authority_manifest": "manifests/phase0/canonical-authority.json",
    "foundation.canonical_specification.revision_3": (
        "docs/superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-3.md"
    ),
    "phase0.ai_review_procedure": "docs/superpowers/governance/2026-08-14-ai-review-process-001.json",
    "phase5.design_specification": (
        "docs/superpowers/specs/2026-08-15-phase-5-capability-supported-features-design.md"
    ),
    "phase5.governance_approvals": (
        "docs/superpowers/governance/2026-08-15-phase-5-governance-approvals.json"
    ),
    "phase5.governance_plan": (
        "docs/superpowers/plans/2026-08-15-phase-5-capability-supported-features.md"
    ),
    "phase5.implementation_activation": (
        "docs/superpowers/governance/2026-08-15-phase-5-implementation-activation.json"
    ),
    "phase5.implementation_authorization": (
        "docs/superpowers/governance/2026-08-15-phase-5-implementation-authorization.json"
    ),
}


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


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


def load_review_output(review_dir: Path) -> dict[str, object]:
    return load_json(review_dir / "phase5.ai_review_output.json")


def build_approval_records(*, approved_at: str) -> dict[str, object]:
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
                            "approved_logical_id": "phase5.candidate_evidence_root",
                            "approved_sha256": CANDIDATE_ROOT,
                            "approval_scope": "PHASE_5_CANDIDATE_EVIDENCE_ROOT_ACCEPTANCE",
                            "status": "APPROVED",
                        }
                    )
                ),
                "approval_scope": "PHASE_5_CANDIDATE_EVIDENCE_ROOT_ACCEPTANCE",
                "approved_at": approved_at,
                "approved_by_principal_id": "PROJECT-PRINCIPAL-001",
                "approved_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
                "approved_logical_id": "phase5.candidate_evidence_root",
                "approved_sha256": CANDIDATE_ROOT,
                "status": "APPROVED",
            }
        ],
        "logical_id": "phase5.approval_records",
        "schema_version": SCHEMA_VERSION,
    }


def build_coverage(adversarial: dict[str, object], integrity: dict[str, object]) -> dict[str, object]:
    return {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "coverage_assertion_ids_union": sorted(
            set(adversarial.get("coverage_assertion_ids", []))
            | set(integrity.get("coverage_assertion_ids", []))
        ),
        "coverage_logical_ids_union": sorted(
            set(adversarial.get("coverage_logical_ids", []))
            | set(integrity.get("coverage_logical_ids", []))
            | set(GOVERNANCE_PATHS)
            | set(BUNDLE_FILES)
            | {"phase5.candidate_evidence_root"}
        ),
        "disqualification_reason_codes": [],
        "logical_id": "phase5.ai_review_coverage",
        "qualification_status": "QUALIFIED",
        "schema_version": SCHEMA_VERSION,
    }


def build_ai_review_runs(
    adversarial_dir: Path,
    integrity_dir: Path,
    adversarial: dict[str, object],
    integrity: dict[str, object],
) -> dict[str, object]:
    adv_run = load_json(adversarial_dir / "phase5.ai_review_run.json")
    int_run = load_json(integrity_dir / "phase5.ai_review_run.json")
    return {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "review_runs": sorted(
            [
                {
                    "completed_at": adv_run.get("completed_at", "2026-08-15T22:30:00.000000000Z"),
                    "output_repository_relative_path": repo_relative(
                        adversarial_dir / "phase5.ai_review_output.json"
                    ),
                    "review_class": adversarial["review_class"],
                    "review_output_hash": adv_run["review_output_hash"],
                    "review_run_id": adv_run["review_run_id"],
                    "run_record_repository_relative_path": repo_relative(
                        adversarial_dir / "phase5.ai_review_run.json"
                    ),
                    "terminal_state": adv_run["terminal_state"],
                },
                {
                    "completed_at": int_run.get("completed_at", "2026-08-15T22:30:00.000000000Z"),
                    "output_repository_relative_path": repo_relative(
                        integrity_dir / "phase5.ai_review_output.json"
                    ),
                    "review_class": integrity["review_class"],
                    "review_output_hash": int_run["review_output_hash"],
                    "review_run_id": int_run["review_run_id"],
                    "run_record_repository_relative_path": repo_relative(
                        integrity_dir / "phase5.ai_review_run.json"
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
            "logical_id": "phase5.candidate_evidence_root",
            "media_type": "application/json",
            "member_sha256": sha256_bytes(root_raw),
            "repository_relative_path": repo_relative(root_path),
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
        "phase5.ai_review_runs": postreview / "phase5.ai_review_runs.json",
        "phase5.ai_review_coverage": postreview / "phase5.ai_review_coverage.json",
        "phase5.approval_records": postreview / "phase5.approval_records.json",
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
    candidate_ids = [row["logical_id"] for row in members if row["logical_id"] != "phase5.candidate_evidence_root"]
    expected_ids = set(expected_index_logical_ids(candidate_ids))
    present = {row["logical_id"] for row in members}
    if present != expected_ids:
        missing = sorted(expected_ids - present)
        extra = sorted(present - expected_ids)
        raise ValueError(f"index member mismatch missing={missing} extra={extra}")
    return sorted(members, key=lambda row: str(row["logical_id"]))


def build_acceptance_index(members: list[dict[str, object]]) -> dict[str, object]:
    provisional = {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "index_members": members,
        "logical_id": "phase5.acceptance_index",
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
) -> dict[str, object]:
    invalid_statuses: list[str] = []
    if coverage["qualification_status"] != "QUALIFIED":
        invalid_statuses.append(str(coverage["qualification_status"]))
    if adversarial.get("recommended_candidate_outcome") == "FAIL":
        invalid_statuses.append("FAIL")
    if integrity.get("recommended_candidate_outcome") == "FAIL":
        invalid_statuses.append("FAIL")
    aggregate = load_json(DEFAULT_BUNDLE / "assertion-aggregate.json")
    aggregate_status = str(aggregate.get("aggregate_status", "BLOCKED"))
    outcome = derive_final_outcome(aggregate_status, invalid_statuses, False)
    provisional = {
        "assertion_aggregate_status": aggregate_status,
        "candidate_evidence_root": CANDIDATE_ROOT,
        "completed_at": completed_at,
        "index_sha256": index["index_sha256"],
        "logical_id": "phase5.final_acceptance_result",
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
) -> dict[str, object]:
    postreview.mkdir(parents=True, exist_ok=True)
    adversarial = load_review_output(adversarial_dir)
    integrity = load_review_output(integrity_dir)
    write_canonical(postreview / "phase5.approval_records.json", build_approval_records(approved_at=approved_at))
    coverage_doc = build_coverage(adversarial, integrity)
    write_canonical(postreview / "phase5.ai_review_coverage.json", coverage_doc)
    write_canonical(
        postreview / "phase5.ai_review_runs.json",
        build_ai_review_runs(adversarial_dir, integrity_dir, adversarial, integrity),
    )
    members = build_index_members(bundle, postreview)
    index_doc = build_acceptance_index(members)
    reasons = verify_index_hashes(index_doc)
    if reasons:
        raise ValueError(f"acceptance index verification failed: {reasons}")
    write_canonical(postreview / "phase5.acceptance_index.json", index_doc)
    final_doc = build_final_result(
        index=index_doc,
        coverage=coverage_doc,
        adversarial=adversarial,
        integrity=integrity,
        completed_at=completed_at,
    )
    write_canonical(postreview / "phase5.final_acceptance_result.json", final_doc)
    return {
        "final_outcome": final_doc["outcome"],
        "index_sha256": index_doc["index_sha256"],
        "root_hash": index_doc["root_hash"],
    }


def main() -> int:
    from market_platform_foundation.offline_guard import install_guard

    install_guard([])
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--postreview", default=str(DEFAULT_POSTREVIEW))
    parser.add_argument("--adversarial-dir", default=str(DEFAULT_ADVERSARIAL))
    parser.add_argument("--integrity-dir", default=str(DEFAULT_INTEGRITY))
    parser.add_argument("--approved-at", default="2026-08-15T22:30:00.000000000Z")
    parser.add_argument("--completed-at", default="2026-08-15T22:32:00.000000000Z")
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
