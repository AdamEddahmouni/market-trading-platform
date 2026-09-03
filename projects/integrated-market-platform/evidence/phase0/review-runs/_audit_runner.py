"""Read-only adversarial audit runner — writes deliverables outside candidate bundle."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
BUNDLE = REPO / "evidence" / "phase0" / "DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66"
RUN_ID = "DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66"
CANDIDATE_ROOT = "78FA6A96D4193F53018ECFA7DFFAFFEBA3DA398A4E0116056C7C3BDDE8D2C482"
REGISTRY_HASH = "80286553F6E2124DDC998CA7FB94B53518E644F79B93712C34D3D38CCF1C3097"
PLAN_HASH = "EE22C688167F5016D7ED1953BB1DAE516BC6AB343655A7D96535C6605D37E904"
SPEC_HASH = "7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35"
PROCEDURE_HASH = "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8"

PRIMARY_INPUTS = {
    "phase0.ai_review_procedure": (
        REPO / "docs/superpowers/governance/2026-08-14-ai-review-process-001.json",
        PROCEDURE_HASH,
    ),
    "phase0.candidate_evidence_root": (
        BUNDLE / "candidate-evidence-root.json",
        "5574FF6FF83226423D3A17E27426730178AA0E8CE03A87C15622233DDEAC24D1",
    ),
    "phase0.assertion_run_manifest": (
        BUNDLE / "assertion-run-manifest.json",
        "66074C7AA5D52B0D782D9604456D3E01487B7E6B69A9B95377C7954D188EA154",
    ),
    "phase0.assertion_registry": (
        BUNDLE / "assertion-registry.json",
        REGISTRY_HASH,
    ),
    "phase0.gov_002_preapproval_reviewer_eligibility": (
        REPO / "docs/superpowers/governance/2026-08-14-gov-002-preapproval-reviewer-eligibility.json",
        "5686F548A495E9DC215474083EBC6775C921D5B7AD8E6DB98EF132DDC27C4EE4",
    ),
    "phase0.governance_plan": (
        REPO / "docs/superpowers/plans/2026-08-13-phase-0-governance-and-no-live-safety.md",
        PLAN_HASH,
    ),
}

EXCLUDED_LOGICAL_IDS = {
    "phase0.postroot_acceptance_contract_suite",
    "phase0.postroot_acceptance_contract_suite.approval",
    "phase0.ai_review_runs",
    "phase0.ai_review_coverage",
    "phase0.acceptance_index",
    "phase0.final_acceptance_result",
    "phase0.approval_records",
    "phase0.candidate_evidence_root",
}

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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def bundle_filename(logical_id: str) -> str:
    return logical_id.removeprefix("phase0.").replace("_", "-").replace(".", "-") + ".json"


def build_path_index() -> dict[str, Path]:
    """Map sha256 -> path for repo files (excluding .git)."""
    index: dict[str, Path] = {}
    for path in REPO.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        digest = sha256_file(path)
        if digest not in index:
            index[digest] = path
    return index


def verify_primary_inputs() -> tuple[list[dict], list[str]]:
    refs: list[dict] = []
    errors: list[str] = []
    for logical_id, (path, expected) in sorted(PRIMARY_INPUTS.items()):
        if not path.is_file():
            errors.append(f"missing primary input {logical_id}")
            continue
        observed = sha256_file(path)
        refs.append({"logical_id": logical_id, "sha256": observed})
        if observed != expected:
            errors.append(
                f"hash mismatch {logical_id}: expected {expected}, observed {observed}"
            )
    return refs, errors


def verify_bundle_members(root_doc: dict, path_index: dict[str, Path]) -> tuple[list[str], list[dict]]:
    errors: list[str] = []
    member_refs: list[dict] = []
    tuples = root_doc.get("ordered_member_tuples", [])
    seen_ids: set[str] = set()
    for entry in tuples:
        logical_id, expected_hash, expected_len, _media = entry
        if logical_id in EXCLUDED_LOGICAL_IDS:
            errors.append(f"excluded logical_id present in tuples: {logical_id}")
        if logical_id in seen_ids:
            errors.append(f"duplicate logical_id in tuples: {logical_id}")
        seen_ids.add(logical_id)
        # Prefer bundle file
        bundle_path = BUNDLE / bundle_filename(logical_id)
        if bundle_path.is_file():
            path = bundle_path
        elif expected_hash in path_index:
            path = path_index[expected_hash]
        else:
            errors.append(f"member not found: {logical_id}")
            continue
        raw = path.read_bytes()
        observed_hash = sha256_bytes(raw)
        observed_len = len(raw)
        member_refs.append({"logical_id": logical_id, "sha256": observed_hash})
        if observed_hash != expected_hash:
            errors.append(
                f"member hash mismatch {logical_id}: expected {expected_hash}, observed {observed_hash}"
            )
        if observed_len != expected_len:
            errors.append(
                f"member length mismatch {logical_id}: expected {expected_len}, observed {observed_len}"
            )
    for excluded in EXCLUDED_LOGICAL_IDS:
        if excluded in seen_ids:
            errors.append(f"excluded id in tuple array: {excluded}")
    if len(tuples) != 40:
        errors.append(f"member_count expected 40, observed {len(tuples)}")
    if root_doc.get("member_count") != 40:
        errors.append("member_count field not 40")
    if root_doc.get("candidate_evidence_root") != CANDIDATE_ROOT:
        errors.append("candidate_evidence_root value mismatch in manifest")
    return errors, member_refs


def recompute_candidate_root(tuples: list) -> str:
    # Candidate-root hashing follows foundation canonical_bytes (UTF-8 JSON + trailing LF).
    payload = (
        json.dumps(tuples, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    return sha256_bytes(payload)


def cross_check_assertions(
    manifest: dict, results_doc: dict, aggregate_doc: dict
) -> list[dict]:
    findings: list[dict] = []
    observations = manifest.get("assertion_observations", {})
    results = {r["assertion_id"]: r for r in results_doc.get("results", [])}
    for aid in MANDATORY_ASSERTIONS:
        if aid not in observations:
            findings.append(
                _finding(
                    f"ADV-MISSING-OBS-{aid}",
                    "MISSING_REQUIRED_EVIDENCE",
                    "OPEN",
                    "MATERIAL",
                    f"assertion-run-manifest lacks observation for {aid}",
                    "Supply observation or correct manifest",
                    [aid],
                    ["phase0.assertion_run_manifest"],
                )
            )
        if aid not in results:
            findings.append(
                _finding(
                    f"ADV-MISSING-RESULT-{aid}",
                    "MISSING_REQUIRED_EVIDENCE",
                    "OPEN",
                    "MATERIAL",
                    f"assertion-results lacks result for {aid}",
                    "Supply result or correct bundle",
                    [aid],
                    ["phase0.assertion_results"],
                )
            )
            continue
        obs = observations[aid]
        res = results[aid]
        if res.get("status") != obs.get("status"):
            findings.append(
                _finding(
                    f"ADV-CONTRA-STATUS-{aid}",
                    "EVIDENCE_CONTRADICTION",
                    "OPEN",
                    "MATERIAL",
                    f"status mismatch for {aid}: manifest {obs.get('status')} vs results {res.get('status')}",
                    "Reconcile assertion observations and results",
                    [aid],
                    ["phase0.assertion_run_manifest", "phase0.assertion_results"],
                )
            )
        ov = res.get("observed_values", {})
        for key, val in obs.items():
            if key in ("status", "reason_codes"):
                continue
            if key in ov and ov[key] != val:
                findings.append(
                    _finding(
                        f"ADV-CONTRA-OBS-{aid}-{key}",
                        "EVIDENCE_CONTRADICTION",
                        "OPEN",
                        "MATERIAL",
                        f"observed_values.{key} mismatch for {aid}",
                        "Reconcile observation fields",
                        [aid],
                        ["phase0.assertion_run_manifest", "phase0.assertion_results"],
                    )
                )
    agg_status = aggregate_doc.get("aggregate_status")
    statuses = [r.get("status") for r in results_doc.get("results", [])]
    expected_agg = "PASS"
    if any(s == "FAIL" for s in statuses):
        expected_agg = "FAIL"
    elif any(s == "BLOCKED" for s in statuses):
        expected_agg = "BLOCKED"
    elif not all(s == "PASS" for s in statuses):
        expected_agg = "BLOCKED"
    if agg_status != expected_agg:
        findings.append(
            _finding(
                "ADV-AGG-STATUS",
                "EVIDENCE_CONTRADICTION",
                "OPEN",
                "MATERIAL",
                f"aggregate_status {agg_status} contradicts recomputed {expected_agg}",
                "Correct assertion-aggregate",
                MANDATORY_ASSERTIONS,
                ["phase0.assertion_aggregate", "phase0.assertion_results"],
            )
        )
    return findings


def verify_assertion_result_ids(results_doc: dict, run_id: str) -> list[dict]:
    findings: list[dict] = []
    for row in results_doc.get("results", []):
        aid = row.get("assertion_id", "UNKNOWN")
        result_id = row.get("assertion_result_id")
        without_id = dict(row)
        without_id.pop("assertion_result_id", None)
        expected = sha256_bytes(
            (
                json.dumps(without_id, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode("utf-8")
        )
        if result_id != expected:
            findings.append(
                _finding(
                    f"ADV-RESULT-ID-{aid}",
                    "INVALID_APPROVAL_REVIEW_HASH_IDENTITY_OR_INDEX",
                    "OPEN",
                    "MATERIAL",
                    f"assertion_result_id mismatch for {aid}",
                    "Regenerate assertion result with correct identity hash",
                    [aid],
                    ["phase0.assertion_results"],
                )
            )
        if row.get("run_id") != run_id:
            findings.append(
                _finding(
                    f"ADV-MIXED-RUN-{aid}",
                    "EVIDENCE_CONTRADICTION",
                    "OPEN",
                    "MATERIAL",
                    f"result run_id does not match manifest run_id for {aid}",
                    "Align run_id across assertion results",
                    [aid],
                    ["phase0.assertion_results", "phase0.assertion_run_manifest"],
                )
            )
    return findings


def _approval_records_path() -> Path:
    return REPO / "evidence" / "phase0" / "postreview" / "phase0.approval_records.json"


def _has_exact_hash_approval(logical_id: str, expected_sha256: str) -> bool:
    path = _approval_records_path()
    if not path.is_file():
        return False
    bundle = load_json(path)
    for record in bundle.get("approval_records", []):
        if (
            record.get("status") == "APPROVED"
            and record.get("approved_logical_id") == logical_id
            and record.get("approved_sha256") == expected_sha256
        ):
            return True
    return False


def adversarial_gov_checks() -> list[dict]:
    findings: list[dict] = []
    procedure = load_json(PRIMARY_INPUTS["phase0.ai_review_procedure"][0])
    gov002 = load_json(PRIMARY_INPUTS["phase0.gov_002_preapproval_reviewer_eligibility"][0])
    manifest = load_json(BUNDLE / "assertion-run-manifest.json")

    proc_effectivity = procedure.get("effectivity", {}).get("current_effectivity")
    proc_hash = PROCEDURE_HASH
    gov_hash = PRIMARY_INPUTS["phase0.gov_002_preapproval_reviewer_eligibility"][1]
    proc_approved = _has_exact_hash_approval("phase0.ai_review_procedure", proc_hash)
    gov_approved = _has_exact_hash_approval(
        "phase0.gov_002_preapproval_reviewer_eligibility", gov_hash
    )

    if proc_effectivity == "PENDING_EXACT_HASH_PRINCIPAL_APPROVAL" and not proc_approved:
        findings.append(
            _finding(
                "ADV-GOV002-PROC-EFFECTIVITY",
                "UNRESOLVED_MATERIAL_UNCERTAINTY",
                "OPEN",
                "MATERIAL",
                "AI-REVIEW-PROCESS-001 declares PENDING_EXACT_HASH_PRINCIPAL_APPROVAL while GOV-002 observation reports PASS with zero eligibility violations; external conversational approval is asserted but not recorded in phase0.approval_records.",
                "Record formal exact-hash approval evidence or downgrade GOV-002 until effectivity is demonstrable.",
                ["GOV-002"],
                ["phase0.ai_review_procedure", "phase0.gov_002_preapproval_reviewer_eligibility"],
            )
        )
    elif proc_effectivity == "PENDING_EXACT_HASH_PRINCIPAL_APPROVAL" and proc_approved:
        findings.append(
            _finding(
                "ADV-GOV002-PROC-EFFECTIVITY",
                "UNRESOLVED_MATERIAL_UNCERTAINTY",
                "RESOLVED",
                "MATERIAL",
                "AI-REVIEW-PROCESS-001 artifact still declares pending effectivity, but phase0.approval_records now binds the exact procedure hash with PROJECT-PRINCIPAL-001 approval.",
                "No further action required; effectivity is established by formal approval records.",
                ["GOV-002"],
                ["phase0.ai_review_procedure", "phase0.approval_records"],
            )
        )

    gov_effectivity = gov002.get("effectivity", {}).get("current_effectivity")
    gov_blocked = gov002.get("governance_effect", {}).get("gov002_current_status", "")
    if (
        gov_effectivity == "PENDING_EXACT_HASH_PRINCIPAL_APPROVAL"
        and "BLOCKED" in gov_blocked
        and manifest.get("assertion_observations", {}).get("GOV-002", {}).get("status") == "PASS"
        and not gov_approved
    ):
        findings.append(
            _finding(
                "ADV-GOV002-ELIG-EFFECTIVITY",
                "UNRESOLVED_MATERIAL_UNCERTAINTY",
                "OPEN",
                "MATERIAL",
                "Preapproval eligibility artifact declares GOV-002 BLOCKED pending effective exact-hash approval, yet assertion observation marks GOV-002 PASS.",
                "Clarify whether documentary ELIGIBLE with pending effectivity satisfies GOV-002 predicate or reassess assertion.",
                ["GOV-002"],
                ["phase0.gov_002_preapproval_reviewer_eligibility", "phase0.assertion_run_manifest"],
            )
        )
    elif (
        gov_effectivity == "PENDING_EXACT_HASH_PRINCIPAL_APPROVAL"
        and "BLOCKED" in gov_blocked
        and manifest.get("assertion_observations", {}).get("GOV-002", {}).get("status") == "PASS"
        and gov_approved
    ):
        findings.append(
            _finding(
                "ADV-GOV002-ELIG-EFFECTIVITY",
                "UNRESOLVED_MATERIAL_UNCERTAINTY",
                "RESOLVED",
                "MATERIAL",
                "Eligibility artifact still records pending effectivity text, but formal phase0.approval_records binds the exact eligibility hash; documentary ELIGIBLE with external exact-hash approval satisfies the GOV-002 predicate.",
                "No further action required.",
                ["GOV-002"],
                ["phase0.gov_002_preapproval_reviewer_eligibility", "phase0.approval_records"],
            )
        )

    internal_lid = gov002.get("logical_id")
    if internal_lid != "phase0.gov_002_preapproval_reviewer_eligibility":
        findings.append(
            _finding(
                "ADV-GOV002-LOGICAL-ID",
                "NON_MATERIAL_OBSERVATION",
                "NOT_APPLICABLE",
                "NON_MATERIAL",
                f"Member logical_id phase0.gov_002_preapproval_reviewer_eligibility file contains internal logical_id {internal_lid}.",
                "Align internal logical_id with candidate-root member identity if schema requires.",
                ["GOV-002"],
                ["phase0.gov_002_preapproval_reviewer_eligibility"],
            )
        )

    inv = load_json(BUNDLE / "canonical-inventory.json")
    ca = inv.get("content", {}).get("canonical_authority", {})
    if ca.get("phase0_status") == "BLOCKED_PENDING_POSTROOT_ACCEPTANCE":
        findings.append(
            _finding(
                "ADV-PHASE0-STATUS-BLOCKED",
                "NON_MATERIAL_OBSERVATION",
                "NOT_APPLICABLE",
                "NON_MATERIAL",
                "Canonical inventory records phase0_status BLOCKED_PENDING_POSTROOT_ACCEPTANCE while aggregate assertion status is PASS; consistent with documented postroot gate but worth principal acknowledgment.",
                "No action required for preapproval bundle; final gate remains separate.",
                ["GOV-001"],
                ["phase0.canonical_inventory"],
            )
        )

    return findings


def _finding(
    finding_id: str,
    finding_type: str,
    finding_status: str,
    materiality: str,
    reason: str,
    resolution: str,
    assertion_ids: list[str],
    logical_ids: list[str],
) -> dict:
    refs = []
    for lid in sorted(set(logical_ids)):
        h = None
        if lid in PRIMARY_INPUTS:
            h = sha256_file(PRIMARY_INPUTS[lid][0])
        elif (BUNDLE / bundle_filename(lid)).is_file():
            h = sha256_file(BUNDLE / bundle_filename(lid))
        if h:
            refs.append({"logical_id": lid, "sha256": h})
    return {
        "affected_assertion_ids": sorted(set(assertion_ids)),
        "affected_logical_ids": sorted(set(logical_ids)),
        "evidence_refs": sorted(refs, key=lambda x: (x["logical_id"], x["sha256"])),
        "finding_id": finding_id,
        "finding_status": finding_status,
        "finding_type": finding_type,
        "materiality": materiality,
        "reason": reason,
        "recommended_resolution": resolution,
    }


def run_tests() -> dict:
    env = {**dict(__import__("os").environ), "PYTHONPATH": f"src;.{__import__('os').pathsep}src"}
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests/phase0", "-v"],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=env,
    )
    return {
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-4000:] if proc.stdout else "",
        "stderr_tail": proc.stderr[-2000:] if proc.stderr else "",
        "passed": proc.returncode == 0,
    }


def derive_outcome(findings: list[dict], repro: list[dict]) -> str:
    for r in repro:
        if r.get("outcome") == "FAIL":
            return "FAIL"
    for f in findings:
        if f["finding_status"] == "OPEN" and f["materiality"] == "MATERIAL":
            if f["finding_type"] in (
                "EVIDENCE_CONTRADICTION",
                "INVALID_APPROVAL_REVIEW_HASH_IDENTITY_OR_INDEX",
            ):
                return "FAIL"
    for f in findings:
        if f["finding_status"] == "OPEN" and f["materiality"] == "MATERIAL":
            return "BLOCKED"
    for r in repro:
        if r.get("outcome") == "BLOCKED":
            return "BLOCKED"
    return "PASS"


def main() -> None:
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:26] + "0Z"
    out_dir = Path(__file__).resolve().parent / f"ADVERSARIAL-{uuid.uuid4().hex[:16].upper()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    disqualification: list[str] = []
    input_refs, primary_errors = verify_primary_inputs()
    if primary_errors:
        disqualification.append("DISQ-HASH-OR-IDENTITY-MISMATCH")

    root_doc = load_json(BUNDLE / "candidate-evidence-root.json")
    path_index = build_path_index()
    bundle_errors, member_refs = verify_bundle_members(root_doc, path_index)
    if bundle_errors:
        # Hash errors in bundle are disqualifying for review
        if any("hash mismatch" in e or "length mismatch" in e for e in bundle_errors):
            disqualification.append("DISQ-HASH-OR-IDENTITY-MISMATCH")

    tuples = root_doc["ordered_member_tuples"]
    recomputed_root = recompute_candidate_root(tuples)
    reproduction_results: list[dict] = [
        {
            "evidence_refs": [{"logical_id": "phase0.candidate_evidence_root", "sha256": sha256_file(BUNDLE / "candidate-evidence-root.json")}],
            "expected": CANDIDATE_ROOT,
            "observed": recomputed_root,
            "outcome": "PASS" if recomputed_root == CANDIDATE_ROOT else "FAIL",
            "reproduction_id": "REPRO-CANDIDATE-ROOT-RECOMPUTE",
            "subject_refs": ["phase0.candidate_evidence_root"],
        }
    ]

    manifest = load_json(BUNDLE / "assertion-run-manifest.json")
    results_doc = load_json(BUNDLE / "assertion-results.json")
    aggregate_doc = load_json(BUNDLE / "assertion-aggregate.json")

    findings = cross_check_assertions(manifest, results_doc, aggregate_doc)
    findings.extend(verify_assertion_result_ids(results_doc, RUN_ID))
    findings.extend(adversarial_gov_checks())

    if bundle_errors:
        for i, err in enumerate(sorted(bundle_errors)[:20]):
            findings.append(
                _finding(
                    f"ADV-BUNDLE-ERR-{i}",
                    "EVIDENCE_CONTRADICTION" if "mismatch" in err else "MISSING_REQUIRED_EVIDENCE",
                    "OPEN",
                    "MATERIAL",
                    err,
                    "Correct candidate bundle member",
                    [],
                    ["phase0.candidate_evidence_root"],
                )
            )

    test_result = run_tests()
    reproduction_results.append(
        {
            "evidence_refs": [{"logical_id": "phase0.assertion_registry", "sha256": REGISTRY_HASH}],
            "expected": "ALL_PASS",
            "observed": "PASS" if test_result["passed"] else f"FAIL exit {test_result['exit_code']}",
            "outcome": "PASS" if test_result["passed"] else "FAIL",
            "reproduction_id": "REPRO-PHASE0-UNITTESTS",
            "subject_refs": MANDATORY_ASSERTIONS,
        }
    )

    findings = sorted(findings, key=lambda f: f["finding_id"])
    recommended = derive_outcome(findings, reproduction_results)

    coverage_assertion_ids = sorted(MANDATORY_ASSERTIONS)
    coverage_logical_ids = sorted(
        {lid for lid, *_ in tuples}
        | {r["logical_id"] for r in input_refs}
        | {r["logical_id"] for r in member_refs}
    )

    limitations: list[str] = []
    if test_result["passed"]:
        limitations.append(
            "Phase 0 unit tests executed against current workspace tree; evidence bundle frozen at subject_git_commit 55b09254b1720753f1f6bad2c5ac41ea9656bbac."
        )
    limitations.append(
        "Peer INTEGRITY_AND_REPRODUCTION_AUDIT and postroot acceptance artifacts were not inputs to this review class."
    )
    limitations.sort()

    summary = (
        f"Adversarial requirements and conformance audit of candidate root {CANDIDATE_ROOT[:16]}... "
        f"completed with {len([f for f in findings if f['finding_status']=='OPEN'])} open findings; "
        f"recommended outcome {recommended}. "
        f"Primary input hash verification {'passed' if not primary_errors else 'failed'}. "
        f"Bundle member verification {'passed' if not bundle_errors else f'reported {len(bundle_errors)} issues'}."
    )

    review_output = {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "coverage_assertion_ids": coverage_assertion_ids,
        "coverage_logical_ids": coverage_logical_ids,
        "findings": findings,
        "limitations": limitations,
        "recommended_candidate_outcome": recommended,
        "reproduction_results": sorted(reproduction_results, key=lambda r: r["reproduction_id"]),
        "review_class": "ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT",
        "summary": summary,
    }

    review_output_hash = sha256_bytes(canonical_bytes(review_output))

    eligibility = {
        "status": "ELIGIBLE" if not disqualification else "INELIGIBLE",
        "violation_count": len(disqualification),
        "violations": sorted(
            [
                {
                    "evidence_refs": input_refs[:1] if input_refs else [],
                    "reason_code": code,
                    "rule_ref": code,
                }
                for code in disqualification
            ],
            key=lambda v: (v["reason_code"], v["rule_ref"]),
        ),
    }

    all_input_hashes = sorted(
        {json.dumps(r, sort_keys=True): r for r in (input_refs + member_refs)}.values(),
        key=lambda x: (x["logical_id"], x["sha256"]),
    )

    completed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:26] + "0Z"

    terminal_state = "DISQUALIFIED" if disqualification else "COMPLETE"
    qualification_state = "QUALIFYING" if terminal_state == "COMPLETE" and not disqualification else "NON_QUALIFYING"

    run_record: dict[str, Any] = {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "canonical_configuration_hash": manifest.get("canonical_configuration_sha256", "0" * 64),
        "completed_at": completed,
        "coverage_assertion_ids": coverage_assertion_ids,
        "coverage_logical_ids": coverage_logical_ids,
        "disqualification_reason_codes": sorted(set(disqualification)),
        "eligibility_result": eligibility,
        "findings": findings,
        "input_artifact_hashes": all_input_hashes,
        "model_service_and_declared_version": {
            "declared_model_version": "claude-4.6-opus-high-thinking",
            "model_service": "cursor-agent",
        },
        "plan_hash": PLAN_HASH,
        "qualification_state": qualification_state,
        "recommended_candidate_outcome": recommended,
        "registry_hash": REGISTRY_HASH,
        "reproduction_results": review_output["reproduction_results"],
        "review_class": "ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT",
        "review_output_hash": review_output_hash,
        "review_procedure_id_and_hash": {
            "procedure_id": "AI-REVIEW-PROCESS-001",
            "sha256": PROCEDURE_HASH,
        },
        "review_run_id": "",
        "run_id": RUN_ID,
        "runtime_and_tool_versions": sorted(
            [
                {
                    "component_id": "cpython",
                    "declared_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
                    "runtime_context": "local-read-only-audit",
                },
                {
                    "component_id": "market_platform_foundation",
                    "declared_version": "frozen-subject-55b09254",
                    "runtime_context": "src/market_platform_foundation",
                },
            ],
            key=lambda x: (x["component_id"], x["declared_version"], x["runtime_context"]),
        ),
        "specification_hash": SPEC_HASH,
        "started_at": started,
        "terminal_state": terminal_state,
    }

    review_run_id = sha256_bytes(
        canonical_bytes({k: v for k, v in run_record.items() if k != "review_run_id"})
    )
    run_record["review_run_id"] = review_run_id

    (out_dir / "phase0.ai_review_output.json").write_bytes(canonical_bytes(review_output))
    (out_dir / "phase0.ai_review_run.json").write_bytes(canonical_bytes(run_record))

    report = {
        "terminal_state": terminal_state,
        "recommended_candidate_outcome": recommended,
        "finding_count": len(findings),
        "open_finding_count": len([f for f in findings if f["finding_status"] == "OPEN"]),
        "review_run_id": review_run_id,
        "review_output_hash": review_output_hash,
        "output_dir": str(out_dir),
        "primary_errors": primary_errors,
        "bundle_errors": bundle_errors,
        "disqualification": disqualification,
        "tests_passed": test_result["passed"],
    }
    (out_dir / "_audit_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
