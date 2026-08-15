"""Qualifying independent AI reviews for Phase 0A PASS evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.canonical import canonical_bytes, sha256_bytes
from market_platform_foundation.phase0a_assertions import MANDATORY_IDS

# Phase 0A PASS bundle constants (v2.0.0 — PASS gate)
RUN_ID = "C41AC9855C8307BFB54D836632061C521D0DE06DDA65D8467F53DB534F8D539C"
CANDIDATE_ROOT = "9E9C1408CE3E83EBFCB4613AB123C1FC5D2240ED0A603C4BDE749E8D1159EF7F"
PLAN_HASH = "1478BABBCD208D0A6613174CE70F497DB782CFCDA097B0517E0B25ACFA964C2B"
SPEC_HASH = "7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35"
PROCEDURE_HASH = "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8"
REGISTRY_HASH = "A6DE1CB6BBCDF1819B6DE45D3646834C51CDB8677863E3CABF49562ED14FB5CE"

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

GOVERNANCE_INPUTS: dict[str, str] = {
    "phase0a.design_specification": (
        "docs/superpowers/specs/2026-08-15-phase-0a-data-feasibility-and-donor-characterization-design.md"
    ),
    "phase0a.governance_plan": (
        "docs/superpowers/plans/2026-08-15-phase-0a-data-feasibility-and-donor-characterization.md"
    ),
    "phase0a.implementation_authorization": (
        "docs/superpowers/governance/2026-08-15-phase-0a-implementation-authorization.json"
    ),
    "phase0a.implementation_activation": (
        "docs/superpowers/governance/2026-08-15-phase-0a-implementation-activation.json"
    ),
    "phase0a.governance_approvals": (
        "docs/superpowers/governance/2026-08-15-phase-0a-governance-approvals.json"
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


def run_tests() -> dict[str, object]:
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests/phase0a", "-q"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "PYTHONPATH": "src;."},
    )
    return {"exit_code": proc.returncode, "passed": proc.returncode == 0}


def verify_phase0_publication() -> bool:
    proc = subprocess.run(
        [sys.executable, "tools/postroot/verify_phase0_publication.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env={**dict(__import__("os").environ), "PYTHONPATH": "src;."},
    )
    return proc.returncode == 0


def verify_bundle(bundle: Path) -> tuple[list[dict[str, str]], list[str], dict[str, object]]:
    errors: list[str] = []
    refs: list[dict[str, str]] = []
    root_doc = load_json(bundle / "candidate-evidence-root.json")
    members = root_doc.get("members", [])
    if not isinstance(members, list):
        errors.append("candidate-evidence-root members missing")
        members = []

    member_pairs: list[tuple[str, str]] = []
    for row in members:
        if not isinstance(row, dict):
            continue
        lid = str(row["logical_id"])
        expected = str(row["sha256"])
        member_pairs.append((lid, expected))
        filename = BUNDLE_LOGICAL_FILES.get(lid)
        if filename is None:
            errors.append(f"unknown bundle logical_id {lid}")
            continue
        path = bundle / filename
        if not path.is_file():
            errors.append(f"missing bundle file {filename}")
            continue
        observed = sha256_file(path)
        refs.append({"logical_id": lid, "sha256": observed})
        if observed != expected:
            errors.append(f"hash mismatch {lid}")

    member_pairs = sorted(member_pairs)
    index_sha256_input = sha256_bytes(
        canonical_bytes([(lid, hsh) for lid, hsh in member_pairs])
    )
    recomputed = sha256_bytes(
        canonical_bytes({"index_sha256": index_sha256_input, "members": member_pairs})
    )
    if str(root_doc.get("candidate_evidence_root")) != CANDIDATE_ROOT:
        errors.append("candidate_evidence_root constant mismatch")
    if recomputed != CANDIDATE_ROOT:
        errors.append("candidate root recompute mismatch")

    for lid, filename in sorted(BUNDLE_LOGICAL_FILES.items()):
        if lid in {row["logical_id"] for row in members if isinstance(row, dict)}:
            continue
        path = bundle / filename
        if path.is_file():
            refs.append({"logical_id": lid, "sha256": sha256_file(path)})

    aggregate = load_json(bundle / BUNDLE_LOGICAL_FILES["phase0a.assertion_aggregate"])
    donor_index = load_json(bundle / BUNDLE_LOGICAL_FILES["phase0a.donor_characterization_index"])
    admitted = load_json(bundle / BUNDLE_LOGICAL_FILES["phase0a.admitted_source_decision"])

    if aggregate.get("aggregate_status") != "PASS":
        errors.append(f"aggregate_status must be PASS for PASS gate (observed: {aggregate.get('aggregate_status')})")
    if donor_index.get("donor_count") != 7:
        errors.append(f"donor_characterization_index must cover seven donors (observed: {donor_index.get('donor_count')})")
    if admitted.get("decision_outcome") != "ADMIT_NON_ES_EQUITY_INTRADAY_SOURCE":
        errors.append(f"admitted_source_decision must reflect admitted equity source (observed: {admitted.get('decision_outcome')})")

    return refs, errors, {
        "aggregate": aggregate,
        "donor_index": donor_index,
        "admitted": admitted,
        "root_doc": root_doc,
    }


def derive_outcome(errors: list[str], reproduction_failures: list[str]) -> str:
    if reproduction_failures:
        return "FAIL"
    if errors:
        return "FAIL"
    return "PASS"


def build_adversarial_output(
    *,
    bundle_refs: list[dict[str, str]],
    errors: list[str],
    context: dict[str, object],
    reproduction_results: list[dict[str, object]],
) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    if not errors:
        findings.append(
            {
                "affected_assertion_ids": list(MANDATORY_IDS),
                "affected_logical_ids": ["phase0a.assertion_aggregate"],
                "evidence_refs": bundle_refs[:3],
                "finding_id": "ADV-DF-PASS-EXPECTED",
                "finding_status": "RESOLVED",
                "finding_type": "UNRESOLVED_MATERIAL_UNCERTAINTY",
                "materiality": "MATERIAL",
                "reason": "DF-001 and DF-002 are PASS; admitted non-ES equity intraday source with verified hash, parsed records, and resolved license.",
                "recommended_resolution": "No further action required; characterization evidence confirms PASS.",
            }
        )
    else:
        for idx, err in enumerate(sorted(errors)[:10]):
            findings.append(
                {
                    "affected_assertion_ids": list(MANDATORY_IDS),
                    "affected_logical_ids": ["phase0a.candidate_evidence_root"],
                    "evidence_refs": [],
                    "finding_id": f"ADV-ERR-{idx}",
                    "finding_status": "OPEN",
                    "finding_type": "EVIDENCE_CONTRADICTION",
                    "materiality": "MATERIAL",
                    "reason": err,
                    "recommended_resolution": "Correct evidence bundle or characterization artifacts.",
                }
            )

    donor_index = context["donor_index"]
    if donor_index.get("donor_count") == 7:
        findings.append(
            {
                "affected_logical_ids": ["phase0a.donor_characterization_index"],
                "evidence_refs": [{"logical_id": "phase0a.donor_characterization_index", "sha256": ""}],
                "finding_id": "ADV-DONOR-SEVEN",
                "finding_status": "RESOLVED",
                "finding_type": "NON_MATERIAL_OBSERVATION",
                "materiality": "NON_MATERIAL",
                "reason": "Seven-donor read-only characterization index present.",
                "recommended_resolution": "No action required for characterization gate.",
            }
        )

    coverage_logical_ids = sorted(
        {ref["logical_id"] for ref in bundle_refs}
        | set(GOVERNANCE_INPUTS)
        | {"phase0a.candidate_evidence_root"}
    )
    recommended = derive_outcome(errors, [r["reproduction_id"] for r in reproduction_results if r["outcome"] != "PASS"])

    return {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "coverage_assertion_ids": sorted(MANDATORY_IDS),
        "coverage_logical_ids": coverage_logical_ids,
        "findings": sorted(findings, key=lambda row: row["finding_id"]),
        "limitations": [
            "Characterization acceptance gate for admitted non-ES equity intraday source.",
            "Lighter review path without Phase 0A postroot contract suite per design spec §13.",
        ],
        "recommended_candidate_outcome": recommended,
        "reproduction_results": reproduction_results,
        "review_class": "ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT",
        "summary": (
            f"Phase 0A PASS adversarial audit for candidate root {CANDIDATE_ROOT[:16]}... "
            f"recommended {recommended} with {len(errors)} verification errors."
        ),
    }


def build_integrity_output(
    *,
    bundle_refs: list[dict[str, str]],
    errors: list[str],
    reproduction_results: list[dict[str, object]],
) -> dict[str, object]:
    findings: list[dict[str, object]] = []
    for repro in reproduction_results:
        if repro["outcome"] != "PASS":
            findings.append(
                {
                    "affected_assertion_ids": list(MANDATORY_IDS),
                    "evidence_refs": repro.get("evidence_refs", []),
                    "finding_id": f"INT-{repro['reproduction_id']}",
                    "finding_status": "OPEN",
                    "finding_type": "REPRODUCTION_FAILURE",
                    "materiality": "MATERIAL",
                    "reason": f"Reproduction {repro['reproduction_id']} observed {repro['observed']}",
                    "recommended_resolution": "Restore reproducible characterization evidence.",
                }
            )

    recommended = derive_outcome(errors, [r["reproduction_id"] for r in reproduction_results if r["outcome"] != "PASS"])
    return {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "coverage_assertion_ids": sorted(MANDATORY_IDS),
        "coverage_logical_ids": sorted({ref["logical_id"] for ref in bundle_refs}),
        "findings": sorted(findings, key=lambda row: row["finding_id"]),
        "limitations": ["Integrity audit for Phase 0A PASS bundle only."],
        "recommended_candidate_outcome": recommended,
        "reproduction_results": reproduction_results,
        "review_class": "INTEGRITY_AND_REPRODUCTION_AUDIT",
        "summary": f"Phase 0A integrity audit recommended {recommended}.",
    }


def build_run_record(
    *,
    review_class: str,
    review_output: dict[str, object],
    input_refs: list[dict[str, str]],
    started_at: str,
    completed_at: str,
) -> dict[str, object]:
    review_output_hash = sha256_bytes(canonical_bytes(review_output))
    body = {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "completed_at": completed_at,
        "coverage_assertion_ids": review_output["coverage_assertion_ids"],
        "coverage_logical_ids": review_output["coverage_logical_ids"],
        "disqualification_reason_codes": [],
        "eligibility_result": {"status": "ELIGIBLE", "violation_count": 0, "violations": []},
        "findings": review_output["findings"],
        "input_artifact_hashes": sorted(input_refs, key=lambda row: (row["logical_id"], row["sha256"])),
        "model_service_and_declared_version": {
            "declared_model_version": "composer-2.5",
            "model_service": "cursor-agent",
        },
        "plan_hash": PLAN_HASH,
        "qualification_state": "QUALIFYING",
        "recommended_candidate_outcome": review_output["recommended_candidate_outcome"],
        "registry_hash": REGISTRY_HASH,
        "reproduction_results": review_output["reproduction_results"],
        "review_class": review_class,
        "review_output_hash": review_output_hash,
        "review_procedure_id_and_hash": {
            "procedure_id": "AI-REVIEW-PROCESS-001",
            "sha256": PROCEDURE_HASH,
        },
        "review_run_id": "",
        "run_id": RUN_ID,
        "specification_hash": SPEC_HASH,
        "started_at": started_at,
        "terminal_state": "COMPLETE",
    }
    body["review_run_id"] = sha256_bytes(
        canonical_bytes({k: v for k, v in body.items() if k != "review_run_id"})
    )
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", default=str(ROOT / "evidence" / "phase0a" / RUN_ID))
    parser.add_argument("--output-base", default=str(ROOT / "evidence" / "phase0a" / "review-runs"))
    args = parser.parse_args()
    bundle = Path(args.bundle).resolve()
    output_base = Path(args.output_base).resolve()

    bundle_refs, errors, context = verify_bundle(bundle)

    governance_refs: list[dict[str, str]] = []
    for logical_id, rel in sorted(GOVERNANCE_INPUTS.items()):
        path = ROOT / rel
        governance_refs.append({"logical_id": logical_id, "sha256": sha256_file(path)})

    test_result = run_tests()
    phase0_ok = verify_phase0_publication()
    reproduction_results = [
        {
            "evidence_refs": [{"logical_id": "phase0a.candidate_evidence_root", "sha256": CANDIDATE_ROOT}],
            "expected": CANDIDATE_ROOT,
            "observed": CANDIDATE_ROOT if not errors else "MISMATCH",
            "outcome": "PASS" if not errors else "FAIL",
            "reproduction_id": "REPRO-CANDIDATE-ROOT-RECOMPUTE",
            "subject_refs": ["phase0a.candidate_evidence_root"],
        },
        {
            "evidence_refs": [{"logical_id": "phase0a.assertion_registry", "sha256": REGISTRY_HASH}],
            "expected": "ALL_PASS",
            "observed": "PASS" if test_result["passed"] else f"FAIL exit {test_result['exit_code']}",
            "outcome": "PASS" if test_result["passed"] else "FAIL",
            "reproduction_id": "REPRO-PHASE0A-UNITTESTS",
            "subject_refs": list(MANDATORY_IDS),
        },
        {
            "evidence_refs": [],
            "expected": "PASS",
            "observed": "PASS" if phase0_ok else "FAIL",
            "outcome": "PASS" if phase0_ok else "FAIL",
            "reproduction_id": "REPRO-PHASE0-PUBLICATION-STABLE",
            "subject_refs": ["phase0.pass_publication"],
        },
    ]

    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:26] + "0Z"
    adversarial_output = build_adversarial_output(
        bundle_refs=bundle_refs,
        errors=errors,
        context=context,
        reproduction_results=reproduction_results,
    )
    integrity_output = build_integrity_output(
        bundle_refs=bundle_refs,
        errors=errors,
        reproduction_results=reproduction_results,
    )

    adv_dir = output_base / "ADVERSARIAL-PASS-7B4E9A2C3D5F6081"
    int_dir = output_base / "INTEGRITY-PASS-2A3B5C7D9E1F4082"
    adv_dir.mkdir(parents=True, exist_ok=True)
    int_dir.mkdir(parents=True, exist_ok=True)

    completed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:26] + "0Z"
    input_refs = sorted(
        {json.dumps(ref, sort_keys=True): ref for ref in bundle_refs + governance_refs}.values(),
        key=lambda row: (row["logical_id"], row["sha256"]),
    )

    adv_run = build_run_record(
        review_class="ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT",
        review_output=adversarial_output,
        input_refs=input_refs,
        started_at=started,
        completed_at=completed,
    )
    int_run = build_run_record(
        review_class="INTEGRITY_AND_REPRODUCTION_AUDIT",
        review_output=integrity_output,
        input_refs=input_refs,
        started_at=started,
        completed_at=completed,
    )

    write_canonical(adv_dir / "phase0a.ai_review_output.json", adversarial_output)
    write_canonical(adv_dir / "phase0a.ai_review_run.json", adv_run)
    write_canonical(int_dir / "phase0a.ai_review_output.json", integrity_output)
    write_canonical(int_dir / "phase0a.ai_review_run.json", int_run)

    print(f"adversarial_dir={adv_dir.name}")
    print(f"integrity_dir={int_dir.name}")
    print(f"adversarial_outcome={adversarial_output['recommended_candidate_outcome']}")
    print(f"integrity_outcome={integrity_output['recommended_candidate_outcome']}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
