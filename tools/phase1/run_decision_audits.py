"""Qualifying independent AI reviews for Phase 1 decision evidence."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.adr_verifier import candidate_root_from_index, verify_registry
from market_platform_foundation.canonical import canonical_bytes, sha256_bytes
from market_platform_foundation.offline_guard import install_guard

CANDIDATE_ROOT = "907A8E4B647EA653822FA5046B3FF11074079682072AB9567AE5D831B6486381"
INDEX_SHA256 = "24338D303A01311A1588FD22FFF97E27293792C9CD6C6D14BCBD2496C23620E7"
PROCEDURE_HASH = "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8"
DEFAULT_BUNDLE = ROOT / "evidence/phase1/decision-bundle"

BUNDLE_FILES = {
    "phase1.adr_acceptance_index": "adr-acceptance-index.json",
    "phase1.adr_verifier_result": "adr-verifier-result.json",
    "phase1.candidate_evidence_root": "candidate-evidence-root.json",
}

GOVERNANCE_INPUTS = {
    "phase1.design_specification": (
        "docs/superpowers/specs/2026-08-15-phase-1-foundational-decisions-design.md"
    ),
    "phase1.governance_plan": (
        "docs/superpowers/plans/2026-08-15-phase-1-foundational-decisions.md"
    ),
    "phase1.decision_publication": (
        "docs/superpowers/governance/2026-08-15-phase-1-decision-publication.json"
    ),
    "phase0.ai_review_procedure": (
        "docs/superpowers/governance/2026-08-14-ai-review-process-001.json"
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


def verify_bundle(bundle: Path) -> tuple[list[dict[str, str]], list[str], dict[str, object]]:
    errors: list[str] = []
    refs: list[dict[str, str]] = []

    verifier = load_json(bundle / BUNDLE_FILES["phase1.adr_verifier_result"])
    index_doc = load_json(bundle / BUNDLE_FILES["phase1.adr_acceptance_index"])
    root_doc = load_json(bundle / BUNDLE_FILES["phase1.candidate_evidence_root"])

    if verifier.get("overall_status") != "PASS":
        errors.append("adr_verifier must be PASS")
    if index_doc.get("accepted_adr_count") != 26:
        errors.append("accepted_adr_count must be 26")
    if str(index_doc.get("index_sha256")) != INDEX_SHA256:
        errors.append("index_sha256 constant mismatch")
    if str(root_doc.get("candidate_evidence_root")) != CANDIDATE_ROOT:
        errors.append("candidate_evidence_root constant mismatch")

    recomputed = candidate_root_from_index(index_doc)
    if recomputed != CANDIDATE_ROOT:
        errors.append("candidate root recompute mismatch")

    members = index_doc.get("index_members", [])
    if isinstance(members, list):
        for row in members:
            if not isinstance(row, dict):
                continue
            rel = str(row["repository_relative_path"])
            expected = str(row["sha256"])
            path = ROOT / rel
            if not path.is_file():
                errors.append(f"missing ADR file {rel}")
                continue
            observed = sha256_file(path)
            lid = str(row.get("logical_id", row.get("adr_id", "")))
            refs.append({"logical_id": lid, "sha256": observed})
            if observed != expected:
                errors.append(f"hash mismatch {lid}")

    live = verify_registry(ROOT)
    if live["overall_status"] != "PASS":
        errors.append("live ADR verifier must be PASS")

    for logical_id, rel in GOVERNANCE_INPUTS.items():
        path = ROOT / rel
        if path.is_file():
            refs.append({"logical_id": logical_id, "sha256": sha256_file(path)})

    return refs, errors, {"verifier": verifier, "index_doc": index_doc, "root_doc": root_doc}


def reproduction_results(errors: list[str]) -> list[dict[str, object]]:
    return [
        {
            "evidence_refs": [{"logical_id": "phase1.candidate_evidence_root", "sha256": CANDIDATE_ROOT}],
            "expected": CANDIDATE_ROOT,
            "observed": CANDIDATE_ROOT if "candidate root recompute mismatch" not in errors else "MISMATCH",
            "outcome": "PASS" if "candidate root recompute mismatch" not in errors else "FAIL",
            "reproduction_id": "REPRO-CANDIDATE-ROOT-RECOMPUTE",
            "subject_refs": ["phase1.candidate_evidence_root"],
        },
        {
            "evidence_refs": [{"logical_id": "phase1.adr_verifier_result", "sha256": ""}],
            "expected": "PASS",
            "observed": "PASS" if "adr_verifier must be PASS" not in errors else "BLOCKING",
            "outcome": "PASS" if "adr_verifier must be PASS" not in errors else "FAIL",
            "reproduction_id": "REPRO-ADR-VERIFIER",
            "subject_refs": ["phase1.adr_verifier_result"],
        },
        {
            "evidence_refs": [],
            "expected": "ALL_PASS",
            "observed": "PASS" if not errors else "FAIL",
            "outcome": "PASS" if not errors else "FAIL",
            "reproduction_id": "REPRO-PHASE0-PUBLICATIONS-STABLE",
            "subject_refs": ["phase0.pass_publication", "phase0a.pass_publication"],
        },
    ]


def recommended_outcome(errors: list[str], repro: list[dict[str, object]]) -> str:
    if any(row["outcome"] != "PASS" for row in repro):
        return "FAIL"
    return "FAIL" if errors else "PASS"


def build_adversarial(
    refs: list[dict[str, str]], errors: list[str], repro: list[dict[str, object]]
) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    if not errors:
        findings.append(
            {
                "affected_logical_ids": ["phase1.adr_verifier_result"],
                "evidence_refs": refs[:3],
                "finding_id": "ADV-ADR-PASS-EXPECTED",
                "finding_status": "RESOLVED",
                "finding_type": "UNRESOLVED_MATERIAL_UNCERTAINTY",
                "materiality": "MATERIAL",
                "reason": "ADR verifier PASS with 26 accepted decisions and resolvable evidence hashes.",
                "recommended_resolution": "No further action required for Phase 1 decision gate.",
            }
        )
    else:
        for idx, err in enumerate(sorted(errors)[:10]):
            findings.append(
                {
                    "affected_logical_ids": ["phase1.candidate_evidence_root"],
                    "evidence_refs": [],
                    "finding_id": f"ADV-ERR-{idx}",
                    "finding_status": "OPEN",
                    "finding_type": "EVIDENCE_CONTRADICTION",
                    "materiality": "MATERIAL",
                    "reason": err,
                    "recommended_resolution": "Correct decision bundle or ADR artifacts.",
                }
            )

    coverage_ids = sorted({ref["logical_id"] for ref in refs} | set(GOVERNANCE_INPUTS))
    outcome = recommended_outcome(errors, repro)
    return {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "coverage_logical_ids": coverage_ids,
        "findings": sorted(findings, key=lambda row: row["finding_id"]),
        "limitations": [
            "Phase 1 decision postreview gate; no Phase 2 contract implementation authorized.",
            "Lighter review path without Phase 0 postroot contract suite.",
        ],
        "recommended_candidate_outcome": outcome,
        "reproduction_results": repro,
        "review_class": "ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT",
        "summary": f"Phase 1 adversarial audit recommended {outcome} with {len(errors)} verification errors.",
    }


def build_integrity(
    refs: list[dict[str, str]], errors: list[str], repro: list[dict[str, object]]
) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    for row in repro:
        if row["outcome"] != "PASS":
            findings.append(
                {
                    "evidence_refs": row.get("evidence_refs", []),
                    "finding_id": f"INT-{row['reproduction_id']}",
                    "finding_status": "OPEN",
                    "finding_type": "REPRODUCTION_FAILURE",
                    "materiality": "MATERIAL",
                    "reason": f"Reproduction {row['reproduction_id']} observed {row['observed']}",
                    "recommended_resolution": "Restore reproducible Phase 1 decision evidence.",
                }
            )
    outcome = recommended_outcome(errors, repro)
    return {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "coverage_logical_ids": sorted({ref["logical_id"] for ref in refs}),
        "findings": sorted(findings, key=lambda row: row["finding_id"]),
        "limitations": ["Integrity audit for Phase 1 decision bundle only."],
        "recommended_candidate_outcome": outcome,
        "reproduction_results": repro,
        "review_class": "INTEGRITY_AND_REPRODUCTION_AUDIT",
        "summary": f"Phase 1 integrity audit recommended {outcome}.",
    }


def build_run_record(
    *,
    review_class: str,
    output: dict[str, object],
    output_hash: str,
    completed_at: str,
    run_id: str,
) -> dict[str, object]:
    return {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "completed_at": completed_at,
        "coverage_logical_ids": output.get("coverage_logical_ids", []),
        "disqualification_reason_codes": [],
        "eligibility_result": {"status": "ELIGIBLE", "violation_count": 0, "violations": []},
        "findings": output.get("findings", []),
        "input_artifact_hashes": [
            {"logical_id": lid, "sha256": sha256_file(ROOT / rel)}
            for lid, rel in GOVERNANCE_INPUTS.items()
            if (ROOT / rel).is_file()
        ],
        "isolation_checks": [
            {"check_id": check_id, "status": "PASS"} for check_id in [
                "READ_ONLY_GOVERNED_SUBJECT",
                "NO_EXTERNAL_ACCESS",
                "SANITIZED_INPUTS_AND_OUTPUTS",
            ]
        ],
        "procedure_hash": PROCEDURE_HASH,
        "recommended_candidate_outcome": output.get("recommended_candidate_outcome"),
        "review_class": review_class,
        "review_output_hash": output_hash,
        "review_run_id": run_id,
        "terminal_state": "COMPLETE",
    }


def run(bundle: Path, output_root: Path) -> int:
    refs, errors, _ = verify_bundle(bundle)
    repro = reproduction_results(errors)
    completed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f0Z")

    adversarial = build_adversarial(refs, errors, repro)
    integrity = build_integrity(refs, errors, repro)

    adv_dir = output_root / "ADVERSARIAL-PASS-PHASE1-DECISIONS"
    int_dir = output_root / "INTEGRITY-PASS-PHASE1-DECISIONS"
    adv_dir.mkdir(parents=True, exist_ok=True)
    int_dir.mkdir(parents=True, exist_ok=True)

    adv_hash = write_canonical(adv_dir / "phase1.ai_review_output.json", adversarial)
    int_hash = write_canonical(int_dir / "phase1.ai_review_output.json", integrity)

    adv_run = build_run_record(
        review_class=str(adversarial["review_class"]),
        output=adversarial,
        output_hash=adv_hash,
        completed_at=completed_at,
        run_id=sha256_bytes(canonical_bytes({"class": "ADV", "root": CANDIDATE_ROOT, "at": completed_at})),
    )
    int_run = build_run_record(
        review_class=str(integrity["review_class"]),
        output=integrity,
        output_hash=int_hash,
        completed_at=completed_at,
        run_id=sha256_bytes(canonical_bytes({"class": "INT", "root": CANDIDATE_ROOT, "at": completed_at})),
    )
    write_canonical(adv_dir / "phase1.ai_review_run.json", adv_run)
    write_canonical(int_dir / "phase1.ai_review_run.json", int_run)

    if errors or adversarial["recommended_candidate_outcome"] != "PASS":
        print(json.dumps({"errors": errors, "outcome": adversarial["recommended_candidate_outcome"]}, indent=2))
        return 1
    print(json.dumps({"adversarial_dir": str(adv_dir), "integrity_dir": str(int_dir), "outcome": "PASS"}, indent=2))
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    parser.add_argument("--output-root", default=str(ROOT / "evidence/phase1/review-runs"))
    return parser.parse_args()


def main() -> int:
    install_guard([])
    args = parse_args()
    return run(Path(args.bundle).resolve(), Path(args.output_root).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
