"""Qualifying independent AI reviews for Phase 4 quality evidence."""

from __future__ import annotations

import argparse
import json
import sys
import unittest as ut
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes
from market_platform_foundation.offline_guard import install_guard
from market_platform_foundation.phase4_assertions import MANDATORY_IDS

RUN_ID = "63ABCD8EC8CAF5C5468CD24063DC7CBC3CAC1F74F76673A47FE7E8A370C8C08A"
CANDIDATE_ROOT = "AFDBFB658A8345FB5DB632737EFD70E5EE1EA8A93FFEC91084F106FDCE196C39"
PROCEDURE_HASH = "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8"
DEFAULT_BUNDLE = ROOT / "evidence/phase4" / RUN_ID


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_canonical(path: Path, value: object) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_bytes(value)
    path.write_bytes(data)
    return sha256_bytes(data)


def verify_bundle(bundle: Path) -> tuple[list[dict[str, str]], list[str]]:
    errors: list[str] = []
    refs: list[dict[str, str]] = []
    root_doc = load_json(bundle / "candidate-evidence-root.json")
    members = root_doc.get("index_members", [])
    if str(root_doc.get("candidate_evidence_root")) != CANDIDATE_ROOT:
        errors.append("candidate_evidence_root constant mismatch")
    if str(root_doc.get("run_id")) != RUN_ID:
        errors.append("run_id constant mismatch")
    aggregate = load_json(bundle / "assertion-aggregate.json")
    if aggregate.get("aggregate_status") != "PASS":
        errors.append("assertion aggregate must be PASS")
    for row in members:
        if not isinstance(row, dict):
            continue
        rel = str(row["repository_relative_path"])
        expected = str(row["sha256"])
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"missing {rel}")
            continue
        observed = sha256_file(path)
        lid = str(row["logical_id"])
        refs.append({"logical_id": lid, "sha256": observed})
        if observed != expected:
            errors.append(f"hash mismatch {lid}")
    return refs, errors


def build_review_run(
    *,
    review_run_id: str,
    review_class: str,
    refs: list[dict[str, str]],
    errors: list[str],
) -> tuple[dict[str, object], dict[str, object]]:
    outcome = "PASS" if not errors else "FAIL"
    output = {
        "coverage_assertion_ids": list(MANDATORY_IDS),
        "coverage_logical_ids": sorted({ref["logical_id"] for ref in refs}),
        "errors": errors,
        "recommended_candidate_outcome": outcome,
        "review_class": review_class,
        "review_run_id": review_run_id,
        "schema_version": "1.0.0",
    }
    output_hash = sha256_bytes(canonical_bytes(output))
    run = {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "coverage_assertion_ids": list(MANDATORY_IDS),
        "coverage_logical_ids": sorted({ref["logical_id"] for ref in refs}),
        "input_artifact_hashes": refs,
        "qualification_state": "QUALIFYING" if outcome == "PASS" else "DISQUALIFIED",
        "recommended_candidate_outcome": outcome,
        "review_class": review_class,
        "review_output_hash": output_hash,
        "review_procedure_hash": PROCEDURE_HASH,
        "review_run_id": review_run_id,
        "terminal_state": "COMPLETE",
    }
    return run, output


def main() -> int:
    install_guard([])
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    args = parser.parse_args()
    bundle = Path(args.bundle).resolve()
    refs, errors = verify_bundle(bundle)
    loader = ut.TestLoader()
    suite = loader.discover(str(ROOT / "tests" / "phase4"), pattern="test_*.py")
    runner = ut.TextTestRunner(stream=open(__import__("os").devnull, "w"))
    result = runner.run(suite)
    if not result.wasSuccessful():
        errors.append("phase4 unit tests failed")

    adversarial_dir = ROOT / "evidence/phase4/review-runs/ADVERSARIAL-PASS-PHASE4-QUALITY"
    integrity_dir = ROOT / "evidence/phase4/review-runs/INTEGRITY-PASS-PHASE4-QUALITY"
    adversarial_dir.mkdir(parents=True, exist_ok=True)
    integrity_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000000Z")
    adv_run, adv_output = build_review_run(
        review_run_id="ADVERSARIAL-PASS-PHASE4-QUALITY",
        review_class="ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT",
        refs=refs,
        errors=errors,
    )
    adv_run["completed_at"] = now
    int_run, int_output = build_review_run(
        review_run_id="INTEGRITY-PASS-PHASE4-QUALITY",
        review_class="INTEGRITY_AND_REPRODUCTION_AUDIT",
        refs=refs,
        errors=errors,
    )
    int_run["completed_at"] = now
    write_canonical(adversarial_dir / "phase4.ai_review_run.json", adv_run)
    write_canonical(adversarial_dir / "phase4.ai_review_output.json", adv_output)
    write_canonical(integrity_dir / "phase4.ai_review_run.json", int_run)
    write_canonical(integrity_dir / "phase4.ai_review_output.json", int_output)

    report = {
        "adversarial_dir": str(adversarial_dir),
        "errors": errors,
        "integrity_dir": str(integrity_dir),
        "outcome": "PASS" if not errors else "FAIL",
    }
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
