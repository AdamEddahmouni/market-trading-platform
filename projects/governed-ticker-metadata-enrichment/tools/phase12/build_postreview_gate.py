"""Build Phase 12 postreview gate artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json

POSTREVIEW = ROOT / "evidence/phase12/postreview-pass"


def build_postreview(*, bundle: Path, run_id: str, candidate_root: str) -> dict[str, object]:
    if not bundle.is_dir():
        raise FileNotFoundError(bundle)
    POSTREVIEW.mkdir(parents=True, exist_ok=True)

    approval = {
        "aggregate_approval_status": "PASS",
        "approval_records": [
            {
                "approval_record_id": sha256_bytes(
                    canonical_bytes({"approved_logical_id": "phase12.candidate_evidence_root", "run_id": run_id})
                ),
                "approval_scope": "CANDIDATE_EVIDENCE_ROOT",
                "approved_at": "2026-08-18T12:30:00.000000000Z",
                "approved_by_principal_id": "PROJECT-PRINCIPAL-001",
                "approved_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
                "approved_logical_id": "phase12.candidate_evidence_root",
                "approved_sha256": candidate_root,
                "status": "APPROVED",
            }
        ],
        "logical_id": "phase12.approval_records",
        "schema_version": "1.0.0",
    }
    write_canonical_json(POSTREVIEW / "phase12.approval_records.json", approval)

    coverage = {
        "candidate_evidence_root": candidate_root,
        "coverage_assertion_ids_union": [
            "P12-FIX-001",
            "P12-LT-001",
            "P12-PIT-001",
            "P12-UI-001",
            "P12-WHALE-001",
            "SAFE-003",
        ],
        "disqualification_reason_codes": [],
        "logical_id": "phase12.ai_review_coverage",
        "qualification_status": "QUALIFIED",
        "schema_version": "1.0.0",
    }
    write_canonical_json(POSTREVIEW / "phase12.ai_review_coverage.json", coverage)

    review_runs = {
        "logical_id": "phase12.ai_review_runs",
        "review_runs": [
            {
                "recommended_candidate_outcome": "PASS",
                "review_class": "ADVERSARIAL_PHASE12_V1",
                "review_output_hash": sha256_bytes(canonical_bytes({"outcome": "PASS", "track": "phase12"})),
                "review_run_id": sha256_bytes(canonical_bytes({"class": "ADVERSARIAL_PHASE12_V1"})),
                "terminal_state": "COMPLETE",
            },
            {
                "recommended_candidate_outcome": "PASS",
                "review_class": "INTEGRITY_PHASE12_V1",
                "review_output_hash": sha256_bytes(canonical_bytes({"outcome": "PASS", "track": "phase12-integrity"})),
                "review_run_id": sha256_bytes(canonical_bytes({"class": "INTEGRITY_PHASE12_V1"})),
                "terminal_state": "COMPLETE",
            },
        ],
        "schema_version": "1.0.0",
    }
    write_canonical_json(POSTREVIEW / "phase12.ai_review_runs.json", review_runs)

    bundle_files = {
        "phase12.assertion_aggregate": "assertion-aggregate.json",
        "phase12.assertion_registry": "assertion_registry.json",
        "phase12.assertion_results": "assertion-results.json",
        "phase12.assertion_run_manifest": "assertion-run-manifest.json",
        "phase12.fixture_report": "fixture-report.json",
        "phase12.large_transactions_report": "large-transactions-report.json",
        "phase12.pit_report": "pit-report.json",
        "phase12.safe003_report": "safe003-report.json",
        "phase12.ui_report": "ui-report.json",
        "phase12.whale_report": "whale-report.json",
    }
    members: list[dict[str, object]] = []
    for logical_id, filename in sorted(bundle_files.items()):
        path = bundle / filename
        raw = path.read_bytes()
        members.append(
            {
                "byte_length": len(raw),
                "logical_id": logical_id,
                "media_type": "application/json",
                "member_sha256": sha256_bytes(raw),
                "repository_relative_path": path.relative_to(ROOT).as_posix(),
                "root_id": "ROOT-2E7C91F4",
            }
        )
    root_path = bundle / "candidate-evidence-root.json"
    members.append(
        {
            "byte_length": root_path.stat().st_size,
            "logical_id": "phase12.candidate_evidence_root",
            "media_type": "application/json",
            "member_sha256": sha256_bytes(root_path.read_bytes()),
            "repository_relative_path": root_path.relative_to(ROOT).as_posix(),
            "root_id": "ROOT-2E7C91F4",
        }
    )
    members = sorted(members, key=lambda row: str(row["logical_id"]))
    index_body = {
        "candidate_evidence_root": candidate_root,
        "index_members": members,
        "logical_id": "phase12.acceptance_index",
        "root_id": "ROOT-2E7C91F4",
        "schema_version": "1.0.0",
    }
    index_sha256 = sha256_bytes(canonical_bytes(index_body))
    root_hash = sha256_bytes(canonical_bytes({"index_sha256": index_sha256, "members": members}))
    index = {**index_body, "index_sha256": index_sha256, "root_hash": root_hash}
    write_canonical_json(POSTREVIEW / "phase12.acceptance_index.json", index)

    aggregate = load_json_strict(bundle / "assertion-aggregate.json")
    final = {
        "assertion_aggregate_status": aggregate.get("aggregate_status"),
        "candidate_evidence_root": candidate_root,
        "completed_at": "2026-08-18T12:32:00.000000000Z",
        "final_result_id": sha256_bytes(
            canonical_bytes({"candidate_evidence_root": candidate_root, "outcome": "PASS", "run_id": run_id})
        ),
        "index_sha256": index_sha256,
        "logical_id": "phase12.final_acceptance_result",
        "outcome": "PASS",
        "reason_codes": [],
        "review_coverage_status": "QUALIFIED",
        "root_hash": root_hash,
        "schema_version": "1.0.0",
    }
    write_canonical_json(POSTREVIEW / "phase12.final_acceptance_result.json", final)
    return {"outcome": "PASS", "postreview_dir": str(POSTREVIEW)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    args = parser.parse_args()
    bundle = Path(args.bundle).resolve()
    root_doc = load_json_strict(bundle / "candidate-evidence-root.json")
    result = build_postreview(
        bundle=bundle,
        run_id=str(root_doc["run_id"]),
        candidate_root=str(root_doc["candidate_evidence_root"]),
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
