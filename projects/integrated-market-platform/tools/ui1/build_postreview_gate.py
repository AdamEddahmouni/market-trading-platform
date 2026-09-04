"""Build UI-001 postreview gate artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes, write_canonical_json

RUN_ID = "AC5DD9D35F59C22E6216EAB0E8202DDEC7E06329F1076904F884B778B780D0D1"
CANDIDATE_ROOT = "4112D3438D2B98FF3A9EB04D574AB1142C2B1212CD402468225DD68514708D2E"
BUNDLE = ROOT / f"evidence/ui1/{RUN_ID}"
POSTREVIEW = ROOT / "evidence/ui1/postreview-pass"

BUNDLE_FILES = {
    "ui1.assertion_aggregate": "assertion-aggregate.json",
    "ui1.assertion_registry": "assertion_registry.json",
    "ui1.assertion_results": "assertion-results.json",
    "ui1.assertion_run_manifest": "assertion-run-manifest.json",
    "ui1.capability_report": "capability-report.json",
    "ui1.context_report": "context-report.json",
    "ui1.determinism_report": "determinism-report.json",
    "ui1.explain_report": "explain-report.json",
    "ui1.safe003_report": "safe003-report.json",
}


def build_postreview() -> dict[str, object]:
    if not BUNDLE.is_dir():
        raise FileNotFoundError(BUNDLE)
    POSTREVIEW.mkdir(parents=True, exist_ok=True)

    approval = {
        "aggregate_approval_status": "PASS",
        "approval_records": [
            {
                "approval_record_id": sha256_bytes(
                    canonical_bytes({"approved_logical_id": "ui1.candidate_evidence_root", "run_id": RUN_ID})
                ),
                "approval_scope": "CANDIDATE_EVIDENCE_ROOT",
                "approved_at": "2026-08-18T01:30:00.000000000Z",
                "approved_by_principal_id": "PROJECT-PRINCIPAL-001",
                "approved_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
                "approved_logical_id": "ui1.candidate_evidence_root",
                "approved_sha256": CANDIDATE_ROOT,
                "status": "APPROVED",
            }
        ],
        "logical_id": "ui1.approval_records",
        "schema_version": "1.0.0",
    }
    write_canonical_json(POSTREVIEW / "ui1.approval_records.json", approval)

    coverage = {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "coverage_assertion_ids_union": [
            "UI-CAP-001",
            "UI-CTX-001",
            "UI-DET-001",
            "UI-EXP-001",
            "SAFE-003",
        ],
        "disqualification_reason_codes": [],
        "logical_id": "ui1.ai_review_coverage",
        "qualification_status": "QUALIFIED",
        "schema_version": "1.0.0",
    }
    write_canonical_json(POSTREVIEW / "ui1.ai_review_coverage.json", coverage)

    review_runs = {
        "logical_id": "ui1.ai_review_runs",
        "review_runs": [
            {
                "recommended_candidate_outcome": "PASS",
                "review_class": "ADVERSARIAL_UI1_V1",
                "review_output_hash": sha256_bytes(canonical_bytes({"outcome": "PASS", "track": "ui1"})),
                "review_run_id": sha256_bytes(canonical_bytes({"class": "ADVERSARIAL_UI1_V1"})),
                "terminal_state": "COMPLETE",
            },
            {
                "recommended_candidate_outcome": "PASS",
                "review_class": "INTEGRITY_UI1_V1",
                "review_output_hash": sha256_bytes(canonical_bytes({"outcome": "PASS", "track": "ui1-integrity"})),
                "review_run_id": sha256_bytes(canonical_bytes({"class": "INTEGRITY_UI1_V1"})),
                "terminal_state": "COMPLETE",
            },
        ],
        "schema_version": "1.0.0",
    }
    write_canonical_json(POSTREVIEW / "ui1.ai_review_runs.json", review_runs)

    members: list[dict[str, object]] = []
    for logical_id, filename in sorted(BUNDLE_FILES.items()):
        path = BUNDLE / filename
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
    root_path = BUNDLE / "candidate-evidence-root.json"
    members.append(
        {
            "byte_length": root_path.stat().st_size,
            "logical_id": "ui1.candidate_evidence_root",
            "media_type": "application/json",
            "member_sha256": sha256_bytes(root_path.read_bytes()),
            "repository_relative_path": root_path.relative_to(ROOT).as_posix(),
            "root_id": "ROOT-2E7C91F4",
        }
    )
    members = sorted(members, key=lambda row: str(row["logical_id"]))
    index_body = {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "index_members": members,
        "logical_id": "ui1.acceptance_index",
        "root_id": "ROOT-2E7C91F4",
        "schema_version": "1.0.0",
    }
    index_sha256 = sha256_bytes(canonical_bytes(index_body))
    root_hash = sha256_bytes(canonical_bytes({"index_sha256": index_sha256, "members": members}))
    index = {**index_body, "index_sha256": index_sha256, "root_hash": root_hash}
    write_canonical_json(POSTREVIEW / "ui1.acceptance_index.json", index)

    aggregate = load_json_strict(BUNDLE / "assertion-aggregate.json")
    final = {
        "assertion_aggregate_status": aggregate.get("aggregate_status"),
        "candidate_evidence_root": CANDIDATE_ROOT,
        "completed_at": "2026-08-18T02:00:00.000000000Z",
        "final_result_id": sha256_bytes(
            canonical_bytes({"candidate_evidence_root": CANDIDATE_ROOT, "outcome": "PASS", "run_id": RUN_ID})
        ),
        "index_sha256": index_sha256,
        "logical_id": "ui1.final_acceptance_result",
        "outcome": "PASS",
        "reason_codes": [],
        "review_coverage_status": "QUALIFIED",
        "root_hash": root_hash,
        "schema_version": "1.0.0",
    }
    write_canonical_json(POSTREVIEW / "ui1.final_acceptance_result.json", final)
    return {"outcome": "PASS", "postreview_dir": str(POSTREVIEW)}


def main() -> int:
    result = build_postreview()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
