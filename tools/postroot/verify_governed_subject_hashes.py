"""Verify governed-subject identity hashes for principal validation."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

RUN_ID = "DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66"
BUNDLE = ROOT / "evidence" / "phase0" / RUN_ID

# Handoff identity table (assertion run manifest = subject_manifest_hash binding).
EXPECTED = {
    "candidate_evidence_root": "78FA6A96D4193F53018ECFA7DFFAFFEBA3DA398A4E0116056C7C3BDDE8D2C482",
    "candidate_root_manifest_file": "5574FF6FF83226423D3A17E27426730178AA0E8CE03A87C15622233DDEAC24D1",
    "subject_manifest_hash": "EE5DA97EA0823541C83E20B8123C29A4C538B76F5C52AD58823CBD3EC6D1B17B",
    "registry": "36CBBCFF1A3E3663DE4A652CB7E00983FFDA5031F255F6BBEB9BCC90A2A7EA16",
    "postroot_suite": "84431668E9F5103362D1A6275B235D8003A0BD600CAF694A4B0A4999C70F330F",
    "suite_approval": "2173396E4B977689CE20AC9602B47D25709294EE7D8E8CE3C070093E9B15B23F",
    "ai_review_procedure": "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8",
    "gov_002_eligibility": "5686F548A495E9DC215474083EBC6775C921D5B7AD8E6DB98EF132DDC27C4EE4",
    "governance_plan": "EE22C688167F5016D7ED1953BB1DAE516BC6AB343655A7D96535C6605D37E904",
    "bundle_member_assertion_run_manifest": "66074C7AA5D52B0D782D9604456D3E01487B7E6B69A9B95377C7954D188EA154",
}

WORKSPACE_PATHS = {
    "registry": ROOT / "manifests/phase0/registry.json",
    "postroot_suite": ROOT
    / "docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json",
    "suite_approval": ROOT
    / "docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite-approval.json",
    "ai_review_procedure": ROOT / "docs/superpowers/governance/2026-08-14-ai-review-process-001.json",
    "gov_002_eligibility": ROOT
    / "docs/superpowers/governance/2026-08-14-gov-002-preapproval-reviewer-eligibility.json",
    "governance_plan": ROOT
    / "docs/superpowers/plans/2026-08-13-phase-0-governance-and-no-live-safety.md",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def check(label: str, actual: str, expected: str) -> bool:
    match = actual.upper() == expected.upper()
    print(f"{'PASS' if match else 'FAIL'} {label}: {actual}")
    return match


def main() -> int:
    all_ok = True
    print("=== Governed subject identity hash verification ===")

    root_doc = json.loads((BUNDLE / "candidate-evidence-root.json").read_text())
    if not check("candidate_evidence_root (document)", root_doc["candidate_evidence_root"], EXPECTED["candidate_evidence_root"]):
        all_ok = False

    if not check(
        "candidate_root_manifest_file",
        sha256_file(BUNDLE / "candidate-evidence-root.json"),
        EXPECTED["candidate_root_manifest_file"],
    ):
        all_ok = False

    run_manifest = json.loads((BUNDLE / "assertion-run-manifest.json").read_text())
    if not check(
        "subject_manifest_hash (assertion-run-manifest binding)",
        run_manifest["subject_manifest_hash"],
        EXPECTED["subject_manifest_hash"],
    ):
        all_ok = False

    if not check(
        "bundle_member_assertion_run_manifest",
        sha256_file(BUNDLE / "assertion-run-manifest.json"),
        EXPECTED["bundle_member_assertion_run_manifest"],
    ):
        all_ok = False

    for key in ("registry", "postroot_suite", "suite_approval", "ai_review_procedure", "gov_002_eligibility", "governance_plan"):
        if not check(key, sha256_file(WORKSPACE_PATHS[key]), EXPECTED[key]):
            all_ok = False

    member_map = {row[0]: row[1] for row in root_doc["ordered_member_tuples"]}
    for logical_id, expected in (
        ("phase0.governance_plan", EXPECTED["governance_plan"]),
        ("phase0.ai_review_procedure", EXPECTED["ai_review_procedure"]),
        ("phase0.gov_002_preapproval_reviewer_eligibility", EXPECTED["gov_002_eligibility"]),
    ):
        actual = member_map.get(logical_id, "")
        if not check(f"bundle_member_{logical_id}", actual, expected):
            all_ok = False

    agg = json.loads((BUNDLE / "assertion-aggregate.json").read_text())
    print(f"  assertion_aggregate.aggregate_status: {agg.get('aggregate_status')}")

    print(f"=== Overall: {'ALL PASS' if all_ok else 'FAILURES DETECTED'} ===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
