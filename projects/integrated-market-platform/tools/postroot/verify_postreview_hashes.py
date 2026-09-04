"""Verify postreview gate artifact hashes for principal validation."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POSTREVIEW = ROOT / "evidence/phase0/postreview"

EXPECTED = {
    "phase0.approval_records": "C8737648CDE7E13480643E94BEE5FFFAA42C04F093136D2D910AC76B5D9CF278",
    "phase0.ai_review_coverage": "423B9F92008AF930FCCE3DFD2782A74EEB6E324C7C055C428B1AC319CC133A3B",
    "phase0.ai_review_runs": "9DA52BCD39E2CC9DDDAB8AF11769314C250842E7527DD467E84E581A76852D2D",
    "phase0.acceptance_index": "33032B063BAA167981D10E28C6B69BF372B8A43703C0C28B63FD852721F36814",
    "phase0.final_acceptance_result": "ADF26F898F44E41EAA006EE9AF9AD6547AFB45CA3083ED2DAAE81DFA19A0E548",
}
INDEX_SHA_EXPECTED = "A03044C69F977A34BF19FAB405194CE36A47F8EA032A539A4DED76B522F879DB"

QUALIFYING_RUNS = {
    "ADVERSARIAL": "3B46DCFBBE324D97DE8D496EABD2C1B1DB648FF8AE8787FB04C7A492F1900651",
    "INTEGRITY": "5DE42893FB2248CB57172AFDF315D50506289F1E9EDA789C942D4EFD0FA4D4EF",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main() -> int:
    all_ok = True
    print("=== Postreview artifact hash verification ===")
    for logical_id, expected in EXPECTED.items():
        path = POSTREVIEW / f"{logical_id}.json"
        actual = sha256_file(path)
        match = actual == expected
        if not match:
            all_ok = False
        print(f"{'PASS' if match else 'FAIL'} {logical_id}: {actual}")

    idx = json.loads((POSTREVIEW / "phase0.acceptance_index.json").read_text())
    index_sha = idx.get("index_sha256", "").upper()
    idx_match = index_sha == INDEX_SHA_EXPECTED
    if not idx_match:
        all_ok = False
    print(f"{'PASS' if idx_match else 'FAIL'} acceptance_index.index_sha256: {index_sha}")

    final = json.loads((POSTREVIEW / "phase0.final_acceptance_result.json").read_text())
    print("=== Final acceptance result ===")
    for key in (
        "outcome",
        "final_result_id",
        "root_hash",
        "assertion_aggregate_status",
        "review_coverage_status",
        "reason_codes",
    ):
        print(f"  {key}: {final.get(key)}")

    approvals = json.loads((POSTREVIEW / "phase0.approval_records.json").read_text())
    print("=== Approval records cross-check ===")
    print(f"  aggregate_approval_status: {approvals.get('aggregate_approval_status')}")
    for rec in approvals.get("approval_records", []):
        lid = rec.get("approved_logical_id")
        sha = rec.get("approved_sha256", "").upper()
        scope = rec.get("approval_scope")
        caps = rec.get("approved_capacities")
        print(f"  {lid}: {sha} ({scope}) caps={caps}")

    coverage = json.loads((POSTREVIEW / "phase0.ai_review_coverage.json").read_text())
    print("=== Qualifying review runs ===")
    for cls, run_id in QUALIFYING_RUNS.items():
        in_qualifying = run_id in coverage.get("qualifying_review_run_ids", [])
        in_selected = run_id in coverage.get("selected_review_run_ids", [])
        print(f"  {cls}: {run_id} qualifying={in_qualifying} selected={in_selected}")
    print(f"  qualification_status: {coverage.get('qualification_status')}")

    print(f"=== Overall: {'ALL PASS' if all_ok else 'FAILURES DETECTED'} ===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
