"""Read-only integrity and reproduction audit runner — writes deliverables outside candidate bundle."""
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
SUITE_HASH = "84431668E9F5103362D1A6275B235D8003A0BD600CAF694A4B0A4999C70F330F"
SUITE_APPROVAL_HASH = "2173396E4B977689CE20AC9602B47D25709294EE7D8E8CE3C070093E9B15B23F"
GOV002_HASH = "5686F548A495E9DC215474083EBC6775C921D5B7AD8E6DB98EF132DDC27C4EE4"
MANIFEST_ROOT_HASH = "5574FF6FF83226423D3A17E27426730178AA0E8CE03A87C15622233DDEAC24D1"
ASSERTION_MANIFEST_HASH = "66074C7AA5D52B0D782D9604456D3E01487B7E6B69A9B95377C7954D188EA154"
REGISTRY_MANIFEST_HASH = "36CBBCFF1A3E3663DE4A652CB7E00983FFDA5031F255F6BBEB9BCC90A2A7EA16"

SUITE_PATH = REPO / "docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json"
SUITE_APPROVAL_PATH = REPO / "docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite-approval.json"
REGISTRY_PATH = REPO / "manifests/phase0/registry.json"

PRIMARY_INPUTS = {
    "phase0.ai_review_procedure": (
        REPO / "docs/superpowers/governance/2026-08-14-ai-review-process-001.json",
        PROCEDURE_HASH,
    ),
    "phase0.candidate_evidence_root": (
        BUNDLE / "candidate-evidence-root.json",
        MANIFEST_ROOT_HASH,
    ),
    "phase0.assertion_run_manifest": (
        BUNDLE / "assertion-run-manifest.json",
        ASSERTION_MANIFEST_HASH,
    ),
    "phase0.assertion_registry": (
        BUNDLE / "assertion-registry.json",
        REGISTRY_HASH,
    ),
    "phase0.postroot_acceptance_contract_suite": (SUITE_PATH, SUITE_HASH),
    "phase0.postroot_acceptance_contract_suite.approval": (
        SUITE_APPROVAL_PATH,
        SUITE_APPROVAL_HASH,
    ),
    "phase0.gov_002_preapproval_reviewer_eligibility": (
        REPO / "docs/superpowers/governance/2026-08-14-gov-002-preapproval-reviewer-eligibility.json",
        GOV002_HASH,
    ),
    "manifests/phase0/registry.json": (REGISTRY_PATH, REGISTRY_MANIFEST_HASH),
}

POSTROOT_EXCLUDED_IDS = {
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

sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from market_platform_foundation.assertions import MANDATORY_IDS, build_registry  # noqa: E402
from market_platform_foundation.canonical import canonical_bytes, sha256_bytes  # noqa: E402
from market_platform_foundation.verifier import (  # noqa: E402
    aggregate_status,
    candidate_root,
    candidate_tuple_array,
    verify_result_set,
)
from tools.postroot.acceptance_algorithms import (  # noqa: E402
    POSTROOT_INDEX_IDS,
    compute_index_hashes,
    derive_final_outcome,
    expected_index_logical_ids,
    record_identity,
    verify_index_hashes,
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def build_path_index() -> dict[str, Path]:
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


def bundle_filename(logical_id: str) -> str:
    return logical_id.removeprefix("phase0.").replace("_", "-").replace(".", "-") + ".json"


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
        if logical_id in POSTROOT_EXCLUDED_IDS:
            errors.append(f"postroot logical_id present in tuples: {logical_id}")
        if logical_id in seen_ids:
            errors.append(f"duplicate logical_id in tuples: {logical_id}")
        seen_ids.add(logical_id)
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
    for excluded in POSTROOT_EXCLUDED_IDS:
        if excluded in seen_ids:
            errors.append(f"excluded id in tuple array: {excluded}")
    if len(tuples) != 40:
        errors.append(f"member_count expected 40, observed {len(tuples)}")
    if root_doc.get("member_count") != 40:
        errors.append("member_count field not 40")
    if root_doc.get("candidate_evidence_root") != CANDIDATE_ROOT:
        errors.append("candidate_evidence_root value mismatch in manifest")
    if root_doc.get("run_id") != RUN_ID:
        errors.append("run_id mismatch in candidate-evidence-root manifest")
    return errors, member_refs


def recompute_candidate_root_from_tuples(tuples: list) -> str:
    rows = [
        {
            "logical_id": logical_id,
            "member_sha256": digest,
            "byte_length": length,
            "media_type": media,
        }
        for logical_id, digest, length, media in tuples
    ]
    return candidate_root(rows)


def registry_content_keys(registry_doc: dict) -> list[dict]:
    content = registry_doc.get("content", registry_doc)
    return content.get("active_keys", [])


def recompute_mandatory_set_hash() -> str:
    return sha256_bytes(canonical_bytes(list(MANDATORY_IDS)))


def verify_suite_approval() -> tuple[bool, str]:
    approval = load_json(SUITE_APPROVAL_PATH)
    checks = [
        approval.get("approved_sha256") == SUITE_HASH,
        approval.get("procedure_sha256") == PROCEDURE_HASH,
        approval.get("approval_scope") == "INTEGRITY_REVIEW_COMPANION_INPUT_ONLY",
        approval.get("approved_logical_id") == "phase0.postroot_acceptance_contract_suite",
        approval.get("procedure_id") == "AI-REVIEW-PROCESS-001",
        approval.get("status") == "APPROVED",
    ]
    return all(checks), "all binding fields match" if all(checks) else "approval binding mismatch"


def run_cmd(args: list[str], cwd: Path | None = None) -> dict[str, Any]:
    env = {**dict(__import__("os").environ), "PYTHONPATH": f"src;.{__import__('os').pathsep}src"}
    proc = subprocess.run(
        args,
        cwd=cwd or REPO,
        capture_output=True,
        text=True,
        env=env,
    )
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "passed": proc.returncode == 0,
    }


def falsification_reproductions(root_doc: dict, manifest: dict, results_doc: dict) -> list[dict]:
    repros: list[dict] = []
    tuples = root_doc["ordered_member_tuples"]

    # Hash mismatch detection: tampered digest yields different root
    logical_id, digest, length, media = tuples[0]
    bad_rows = [
        {
            "logical_id": logical_id,
            "member_sha256": "F" * 64,
            "byte_length": length,
            "media_type": media,
        }
    ]
    good_rows = [
        {
            "logical_id": logical_id,
            "member_sha256": digest,
            "byte_length": length,
            "media_type": media,
        }
    ]
    bad_root = candidate_root(bad_rows)
    good_root = candidate_root(good_rows)
    repros.append(
        {
            "evidence_refs": [{"logical_id": "phase0.candidate_evidence_root", "sha256": MANIFEST_ROOT_HASH}],
            "expected": "roots_differ",
            "observed": f"bad={bad_root[:16]} good={good_root[:16]}",
            "outcome": "PASS" if bad_root != good_root else "FAIL",
            "reproduction_id": "REPRO-FALSIFY-HASH-MISMATCH",
            "subject_refs": ["phase0.candidate_evidence_root"],
        }
    )

    # Mixed run detection
    mixed_results = list(results_doc.get("results", []))
    if mixed_results:
        mixed_results[0] = {**mixed_results[0], "run_id": "B" * 64}
    mixed = verify_result_set(RUN_ID, mixed_results)
    repros.append(
        {
            "evidence_refs": [{"logical_id": "phase0.assertion_results", "sha256": sha256_file(BUNDLE / "assertion-results.json")}],
            "expected": "MIXED_RUN_ID",
            "observed": ",".join(mixed.get("reason_codes", [])),
            "outcome": "PASS" if "MIXED_RUN_ID" in mixed.get("reason_codes", []) else "FAIL",
            "reproduction_id": "REPRO-FALSIFY-MIXED-RUN",
            "subject_refs": ["phase0.assertion_results"],
        }
    )

    # Missing mandatory member
    partial = tuples[:-1]
    partial_root = recompute_candidate_root_from_tuples(partial)
    repros.append(
        {
            "evidence_refs": [{"logical_id": "phase0.candidate_evidence_root", "sha256": MANIFEST_ROOT_HASH}],
            "expected": CANDIDATE_ROOT,
            "observed": partial_root,
            "outcome": "PASS" if partial_root != CANDIDATE_ROOT else "FAIL",
            "reproduction_id": "REPRO-FALSIFY-MISSING-MEMBER",
            "subject_refs": ["phase0.candidate_evidence_root"],
        }
    )

    # Extra member changes root
    extra = tuples + [["phase0.extra_member", "A" * 64, 1, "application/json"]]
    extra_root = recompute_candidate_root_from_tuples(extra)
    repros.append(
        {
            "evidence_refs": [{"logical_id": "phase0.candidate_evidence_root", "sha256": MANIFEST_ROOT_HASH}],
            "expected": CANDIDATE_ROOT,
            "observed": extra_root,
            "outcome": "PASS" if extra_root != CANDIDATE_ROOT else "FAIL",
            "reproduction_id": "REPRO-FALSIFY-EXTRA-MEMBER",
            "subject_refs": ["phase0.candidate_evidence_root"],
        }
    )

    # Non-circularity: postroot IDs absent
    tuple_ids = {entry[0] for entry in tuples}
    overlap = sorted(tuple_ids & POSTROOT_EXCLUDED_IDS)
    repros.append(
        {
            "evidence_refs": [{"logical_id": "phase0.candidate_evidence_root", "sha256": MANIFEST_ROOT_HASH}],
            "expected": "no postroot ids in tuple",
            "observed": ",".join(overlap) if overlap else "none",
            "outcome": "PASS" if not overlap else "FAIL",
            "reproduction_id": "REPRO-FALSIFY-NON-CIRCULARITY",
            "subject_refs": sorted(POSTROOT_EXCLUDED_IDS),
        }
    )

    # Index self-hash avoidance
    index_self_rejected = False
    try:
        compute_index_hashes(
            {
                "candidate_evidence_root": CANDIDATE_ROOT,
                "index_members": [
                    {
                        "byte_length": 1,
                        "logical_id": "phase0.acceptance_index",
                        "media_type": "application/json",
                        "member_sha256": "A" * 64,
                        "repository_relative_path": "synthetic/a.json",
                        "root_id": "ROOT-TEST",
                    }
                ],
                "logical_id": "phase0.acceptance_index",
                "procedure_id_and_hash": {"logical_id": "phase0.ai_review_procedure", "sha256": PROCEDURE_HASH},
                "root_id": "ROOT-TEST",
                "schema_version": "1.0.0",
                "suite_id_and_hash": {
                    "logical_id": "phase0.postroot_acceptance_contract_suite",
                    "sha256": SUITE_HASH,
                },
            }
        )
    except ValueError as exc:
        index_self_rejected = "INDEX-SELF-MEMBERSHIP" in str(exc)
    repros.append(
        {
            "evidence_refs": [{"logical_id": "phase0.postroot_acceptance_contract_suite", "sha256": SUITE_HASH}],
            "expected": "INDEX-SELF-MEMBERSHIP",
            "observed": "rejected" if index_self_rejected else "accepted",
            "outcome": "PASS" if index_self_rejected else "FAIL",
            "reproduction_id": "REPRO-INDEX-SELF-HASH-AVOIDANCE",
            "subject_refs": ["phase0.acceptance_index"],
        }
    )

    # Root hash golden vector stability
    rows = [
        {
            "byte_length": 10,
            "logical_id": "a",
            "media_type": "application/json",
            "member_sha256": "B" * 64,
            "repository_relative_path": "synthetic/b.json",
            "root_id": "ROOT-TEST-001",
        },
        {
            "byte_length": 10,
            "logical_id": "b",
            "media_type": "application/json",
            "member_sha256": "A" * 64,
            "repository_relative_path": "synthetic/a.json",
            "root_id": "ROOT-TEST-001",
        },
    ]
    index = {
        "candidate_evidence_root": "A" * 64,
        "index_members": rows,
        "logical_id": "phase0.acceptance_index",
        "procedure_id_and_hash": {"logical_id": "phase0.ai_review_procedure", "sha256": "B" * 64},
        "root_id": "ROOT-TEST-001",
        "schema_version": "1.0.0",
        "suite_id_and_hash": {
            "logical_id": "phase0.postroot_acceptance_contract_suite",
            "sha256": "C" * 64,
        },
    }
    h1 = compute_index_hashes(index)
    h2 = compute_index_hashes({**index, "index_members": list(reversed(rows))})
    repros.append(
        {
            "evidence_refs": [{"logical_id": "phase0.postroot_acceptance_contract_suite", "sha256": SUITE_HASH}],
            "expected": "order_independent_hashes",
            "observed": "match" if h1 == h2 else "mismatch",
            "outcome": "PASS" if h1 == h2 else "FAIL",
            "reproduction_id": "REPRO-INDEX-ROOT-HASH-GOLDEN",
            "subject_refs": ["phase0.acceptance_index"],
        }
    )

    # Final result precedence: FAIL over BLOCKED over PASS
    precedence_cases = [
        ("FAIL", [], False, "FAIL"),
        ("PASS", ["INVALID"], False, "FAIL"),
        ("PASS", [], True, "BLOCKED"),
        ("PASS", [], False, "PASS"),
    ]
    observed = [derive_final_outcome(a, b, c) for a, b, c, _ in precedence_cases]
    expected = [d for _, _, _, d in precedence_cases]
    repros.append(
        {
            "evidence_refs": [{"logical_id": "phase0.postroot_acceptance_contract_suite", "sha256": SUITE_HASH}],
            "expected": ",".join(expected),
            "observed": ",".join(observed),
            "outcome": "PASS" if observed == expected else "FAIL",
            "reproduction_id": "REPRO-FINAL-RESULT-PRECEDENCE",
            "subject_refs": ["phase0.final_acceptance_result"],
        }
    )

    # Record identity omits only identity field
    record = {"approval_record_id": "X", "status": "APPROVED"}
    id_stable = record_identity(record, "approval_record_id") == record_identity(
        {**record, "approval_record_id": "Y"}, "approval_record_id"
    )
    repros.append(
        {
            "evidence_refs": [{"logical_id": "phase0.postroot_acceptance_contract_suite.approval", "sha256": SUITE_APPROVAL_HASH}],
            "expected": "identity_stable",
            "observed": "stable" if id_stable else "unstable",
            "outcome": "PASS" if id_stable else "FAIL",
            "reproduction_id": "REPRO-RECORD-IDENTITY",
            "subject_refs": ["phase0.approval_records"],
        }
    )

    # Expected index logical IDs include postroot set
    candidate_ids = [entry[0] for entry in tuples]
    index_ids = expected_index_logical_ids(candidate_ids)
    postroot_present = all(pid in index_ids for pid in POSTROOT_INDEX_IDS)
    repros.append(
        {
            "evidence_refs": [{"logical_id": "phase0.postroot_acceptance_contract_suite", "sha256": SUITE_HASH}],
            "expected": "postroot_index_ids_present",
            "observed": str(len(index_ids)),
            "outcome": "PASS" if postroot_present else "FAIL",
            "reproduction_id": "REPRO-EXPECTED-INDEX-IDS",
            "subject_refs": ["phase0.acceptance_index"],
        }
    )

    # Run manifest identity
    without_run = dict(manifest)
    without_run.pop("run_id", None)
    manifest_id_ok = sha256_bytes(canonical_bytes(without_run)) == RUN_ID
    repros.append(
        {
            "evidence_refs": [{"logical_id": "phase0.assertion_run_manifest", "sha256": ASSERTION_MANIFEST_HASH}],
            "expected": RUN_ID,
            "observed": sha256_bytes(canonical_bytes(without_run)),
            "outcome": "PASS" if manifest_id_ok else "FAIL",
            "reproduction_id": "REPRO-RUN-MANIFEST-IDENTITY",
            "subject_refs": ["phase0.assertion_run_manifest"],
        }
    )

    return repros


def _finding(
    finding_id: str,
    finding_type: str,
    finding_status: str,
    materiality: str,
    reason: str,
    resolution: str,
    assertion_ids: list[str],
    logical_ids: list[str],
    hash_lookup: dict[str, str],
) -> dict:
    refs = []
    for lid in sorted(set(logical_ids)):
        if lid in hash_lookup:
            refs.append({"logical_id": lid, "sha256": hash_lookup[lid]})
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
    out_dir = Path(__file__).resolve().parent / f"INTEGRITY-{uuid.uuid4().hex[:16].upper()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    disqualification: list[str] = []
    input_refs, primary_errors = verify_primary_inputs()
    if primary_errors:
        disqualification.append("DISQ-HASH-OR-IDENTITY-MISMATCH")

    root_doc = load_json(BUNDLE / "candidate-evidence-root.json")
    path_index = build_path_index()
    bundle_errors, member_refs = verify_bundle_members(root_doc, path_index)
    if any("hash mismatch" in e or "length mismatch" in e for e in bundle_errors):
        disqualification.append("DISQ-HASH-OR-IDENTITY-MISMATCH")

    hash_lookup = {r["logical_id"]: r["sha256"] for r in input_refs + member_refs}

    tuples = root_doc["ordered_member_tuples"]
    recomputed_root = recompute_candidate_root_from_tuples(tuples)
    manifest = load_json(BUNDLE / "assertion-run-manifest.json")
    results_doc = load_json(BUNDLE / "assertion-results.json")
    aggregate_doc = load_json(BUNDLE / "assertion-aggregate.json")
    registry_doc = load_json(BUNDLE / "assertion-registry.json")

    reproduction_results: list[dict] = [
        {
            "evidence_refs": [{"logical_id": "phase0.candidate_evidence_root", "sha256": MANIFEST_ROOT_HASH}],
            "expected": CANDIDATE_ROOT,
            "observed": recomputed_root,
            "outcome": "PASS" if recomputed_root == CANDIDATE_ROOT else "FAIL",
            "reproduction_id": "REPRO-CANDIDATE-ROOT-RECOMPUTE",
            "subject_refs": ["phase0.candidate_evidence_root"],
        }
    ]

    statuses = [r.get("status") for r in results_doc.get("results", [])]
    expected_agg = aggregate_status(statuses)
    reproduction_results.append(
        {
            "evidence_refs": [
                {"logical_id": "phase0.assertion_aggregate", "sha256": sha256_file(BUNDLE / "assertion-aggregate.json")},
                {"logical_id": "phase0.assertion_results", "sha256": sha256_file(BUNDLE / "assertion-results.json")},
            ],
            "expected": expected_agg,
            "observed": aggregate_doc.get("aggregate_status"),
            "outcome": "PASS" if aggregate_doc.get("aggregate_status") == expected_agg else "FAIL",
            "reproduction_id": "REPRO-ASSERTION-AGGREGATE",
            "subject_refs": MANDATORY_ASSERTIONS,
        }
    )

    manifest_keys = manifest.get("active_keys", [])
    registry_keys = registry_content_keys(registry_doc)
    keys_match = manifest_keys == registry_keys
    reproduction_results.append(
        {
            "evidence_refs": [
                {"logical_id": "phase0.assertion_registry", "sha256": REGISTRY_HASH},
                {"logical_id": "phase0.assertion_run_manifest", "sha256": ASSERTION_MANIFEST_HASH},
            ],
            "expected": "active_keys_equal",
            "observed": "match" if keys_match else "mismatch",
            "outcome": "PASS" if keys_match else "FAIL",
            "reproduction_id": "REPRO-ACTIVE-ASSERTION-SET-EQUALITY",
            "subject_refs": ["phase0.assertion_registry", "phase0.assertion_run_manifest"],
        }
    )

    membership = verify_result_set(RUN_ID, results_doc.get("results", []))
    reproduction_results.append(
        {
            "evidence_refs": [{"logical_id": "phase0.assertion_results", "sha256": sha256_file(BUNDLE / "assertion-results.json")}],
            "expected": "PASS",
            "observed": membership.get("status"),
            "outcome": "PASS" if membership.get("status") == "PASS" else "FAIL",
            "reproduction_id": "REPRO-SELECTED-RUN-MEMBERSHIP",
            "subject_refs": ["phase0.assertion_results", "phase0.assertion_run_manifest"],
        }
    )

    recomputed_mandatory = recompute_mandatory_set_hash()
    reproduction_results.append(
        {
            "evidence_refs": [{"logical_id": "phase0.assertion_run_manifest", "sha256": ASSERTION_MANIFEST_HASH}],
            "expected": recomputed_mandatory,
            "observed": manifest.get("mandatory_set_hash"),
            "outcome": "PASS" if manifest.get("mandatory_set_hash") == recomputed_mandatory else "FAIL",
            "reproduction_id": "REPRO-MANDATORY-SET-HASH",
            "subject_refs": ["phase0.assertion_run_manifest"],
        }
    )

    predicate_ok = True
    for key in manifest_keys:
        aid = key.get("assertion_id")
        reg_row = next((r for r in registry_keys if r.get("assertion_id") == aid), None)
        if reg_row is None or reg_row.get("predicate_hash") != key.get("predicate_hash"):
            predicate_ok = False
            break
    reproduction_results.append(
        {
            "evidence_refs": [
                {"logical_id": "phase0.assertion_registry", "sha256": REGISTRY_HASH},
                {"logical_id": "phase0.assertion_run_manifest", "sha256": ASSERTION_MANIFEST_HASH},
            ],
            "expected": "predicate_hashes_match",
            "observed": "match" if predicate_ok else "mismatch",
            "outcome": "PASS" if predicate_ok else "FAIL",
            "reproduction_id": "REPRO-PREDICATE-IDENTITY",
            "subject_refs": MANDATORY_ASSERTIONS,
        }
    )

    approval_ok, approval_obs = verify_suite_approval()
    reproduction_results.append(
        {
            "evidence_refs": [
                {"logical_id": "phase0.postroot_acceptance_contract_suite", "sha256": SUITE_HASH},
                {"logical_id": "phase0.postroot_acceptance_contract_suite.approval", "sha256": SUITE_APPROVAL_HASH},
                {"logical_id": "phase0.ai_review_procedure", "sha256": PROCEDURE_HASH},
            ],
            "expected": "INTEGRITY_REVIEW_COMPANION_INPUT_ONLY binding",
            "observed": approval_obs,
            "outcome": "PASS" if approval_ok else "FAIL",
            "reproduction_id": "REPRO-SUITE-APPROVAL-BINDING",
            "subject_refs": [
                "phase0.postroot_acceptance_contract_suite",
                "phase0.postroot_acceptance_contract_suite.approval",
            ],
        }
    )

    validate_result = run_cmd(
        [
            sys.executable,
            "tools/postroot/validate_postroot_acceptance_suite.py",
            str(SUITE_PATH),
        ]
    )
    validate_report = {}
    if validate_result["stdout"].strip():
        validate_report = json.loads(validate_result["stdout"].strip())
    reproduction_results.append(
        {
            "evidence_refs": [{"logical_id": "phase0.postroot_acceptance_contract_suite", "sha256": SUITE_HASH}],
            "expected": "PASS fixture_count=70",
            "observed": json.dumps(validate_report, separators=(",", ":")),
            "outcome": "PASS"
            if validate_result["passed"]
            and validate_report.get("fixture_count") == 70
            and validate_report.get("status") == "PASS"
            else "FAIL",
            "reproduction_id": "REPRO-POSTROOT-SUITE-VALIDATION",
            "subject_refs": ["phase0.postroot_acceptance_contract_suite"],
        }
    )

    build_check = run_cmd(
        [
            sys.executable,
            "tools/postroot/build_postroot_acceptance_suite.py",
            "--check",
            str(SUITE_PATH),
        ]
    )
    reproduction_results.append(
        {
            "evidence_refs": [{"logical_id": "phase0.postroot_acceptance_contract_suite", "sha256": SUITE_HASH}],
            "expected": "exit 0",
            "observed": str(build_check["exit_code"]),
            "outcome": "PASS" if build_check["passed"] else "FAIL",
            "reproduction_id": "REPRO-POSTROOT-SUITE-BUILD-CHECK",
            "subject_refs": ["phase0.postroot_acceptance_contract_suite"],
        }
    )

    postroot_tests = run_cmd([sys.executable, "-m", "unittest", "discover", "-s", "tests/postroot", "-v"])
    reproduction_results.append(
        {
            "evidence_refs": [{"logical_id": "phase0.postroot_acceptance_contract_suite", "sha256": SUITE_HASH}],
            "expected": "ALL_PASS",
            "observed": "PASS" if postroot_tests["passed"] else f"FAIL exit {postroot_tests['exit_code']}",
            "outcome": "PASS" if postroot_tests["passed"] else "FAIL",
            "reproduction_id": "REPRO-POSTROOT-UNITTESTS",
            "subject_refs": ["phase0.postroot_acceptance_contract_suite"],
        }
    )

    phase0_tests = run_cmd([sys.executable, "-m", "unittest", "discover", "-s", "tests/phase0", "-v"])
    reproduction_results.append(
        {
            "evidence_refs": [{"logical_id": "phase0.governance_verifier", "sha256": sha256_file(BUNDLE / "governance-verifier.json")}],
            "expected": "ALL_PASS",
            "observed": "PASS" if phase0_tests["passed"] else f"FAIL exit {phase0_tests['exit_code']}",
            "outcome": "PASS" if phase0_tests["passed"] else "FAIL",
            "reproduction_id": "REPRO-PHASE0-UNITTESTS",
            "subject_refs": ["phase0.governance_verifier"],
        }
    )

    reproduction_results.extend(falsification_reproductions(root_doc, manifest, results_doc))
    reproduction_results = sorted(reproduction_results, key=lambda r: r["reproduction_id"])

    findings: list[dict] = []
    if primary_errors:
        for i, err in enumerate(sorted(primary_errors)):
            findings.append(
                _finding(
                    f"INT-HASH-ERR-{i}",
                    "INVALID_APPROVAL_REVIEW_HASH_IDENTITY_OR_INDEX",
                    "OPEN",
                    "MATERIAL",
                    err,
                    "Restore exact-hash governed inputs",
                    [],
                    ["phase0.candidate_evidence_root"],
                    hash_lookup,
                )
            )
    if bundle_errors:
        for i, err in enumerate(sorted(bundle_errors)):
            findings.append(
                _finding(
                    f"INT-BUNDLE-ERR-{i}",
                    "EVIDENCE_CONTRADICTION" if "mismatch" in err else "MISSING_REQUIRED_EVIDENCE",
                    "OPEN",
                    "MATERIAL",
                    err,
                    "Correct candidate bundle member",
                    [],
                    ["phase0.candidate_evidence_root"],
                    hash_lookup,
                )
            )

    for repro in reproduction_results:
        if repro["outcome"] == "FAIL":
            findings.append(
                _finding(
                    f"INT-REPRO-FAIL-{repro['reproduction_id']}",
                    "EVIDENCE_CONTRADICTION",
                    "OPEN",
                    "MATERIAL",
                    f"Reproduction {repro['reproduction_id']} failed: expected {repro['expected']}, observed {repro['observed']}",
                    "Investigate verifier or bundle integrity",
                    [],
                    repro.get("subject_refs", []),
                    hash_lookup,
                )
            )

    findings = sorted(findings, key=lambda f: f["finding_id"])
    recommended = derive_outcome(findings, reproduction_results)

    coverage_assertion_ids = sorted(MANDATORY_ASSERTIONS)
    coverage_logical_ids = sorted(
        {lid for lid, *_ in tuples}
        | {r["logical_id"] for r in input_refs}
        | {r["logical_id"] for r in member_refs}
        | {
            "phase0.postroot_acceptance_contract_suite",
            "phase0.postroot_acceptance_contract_suite.approval",
        }
    )

    limitations = sorted(
        [
            "Acceptance-index construction rules were tested via approved postroot fixtures only; no completed postreview acceptance index is claimed.",
            "Peer ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT was not an input to this review class.",
            "Postroot suite and approval are companion inputs only and are excluded from the candidate evidence root tuple.",
        ]
    )

    summary = (
        f"Integrity and reproduction audit of candidate root {CANDIDATE_ROOT[:16]}... "
        f"completed with {len([f for f in findings if f['finding_status'] == 'OPEN'])} open findings; "
        f"recommended outcome {recommended}. "
        f"Candidate root recomputation {'matched' if recomputed_root == CANDIDATE_ROOT else 'mismatched'}. "
        f"Postroot fixture validation fixture_count={validate_report.get('fixture_count', 'unknown')}."
    )

    review_output = {
        "candidate_evidence_root": CANDIDATE_ROOT,
        "coverage_assertion_ids": coverage_assertion_ids,
        "coverage_logical_ids": coverage_logical_ids,
        "findings": findings,
        "limitations": limitations,
        "recommended_candidate_outcome": recommended,
        "reproduction_results": reproduction_results,
        "review_class": "INTEGRITY_AND_REPRODUCTION_AUDIT",
        "summary": summary,
    }

    review_output_hash = sha256_bytes(
        json.dumps(review_output, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )

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
    qualification_state = (
        "QUALIFYING" if terminal_state == "COMPLETE" and not disqualification else "NON_QUALIFYING"
    )

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
        "reproduction_results": reproduction_results,
        "review_class": "INTEGRITY_AND_REPRODUCTION_AUDIT",
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
                {
                    "component_id": "postroot_acceptance_suite",
                    "declared_version": SUITE_HASH[:16],
                    "runtime_context": "tools/postroot",
                },
            ],
            key=lambda x: (x["component_id"], x["declared_version"], x["runtime_context"]),
        ),
        "specification_hash": SPEC_HASH,
        "started_at": started,
        "terminal_state": terminal_state,
    }

    review_run_id = sha256_bytes(
        json.dumps(
            {k: v for k, v in run_record.items() if k != "review_run_id"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    run_record["review_run_id"] = review_run_id

    (out_dir / "phase0.ai_review_output.json").write_bytes(
        json.dumps(review_output, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    (out_dir / "phase0.ai_review_run.json").write_bytes(
        json.dumps(run_record, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )

    report = {
        "terminal_state": terminal_state,
        "qualification_state": qualification_state,
        "recommended_candidate_outcome": recommended,
        "finding_count": len(findings),
        "open_finding_count": len([f for f in findings if f["finding_status"] == "OPEN"]),
        "reproduction_count": len(reproduction_results),
        "reproduction_fail_count": len([r for r in reproduction_results if r["outcome"] == "FAIL"]),
        "review_run_id": review_run_id,
        "review_output_hash": review_output_hash,
        "output_dir": str(out_dir),
        "primary_errors": primary_errors,
        "bundle_errors": bundle_errors,
        "disqualification": disqualification,
        "fixture_validation": validate_report,
        "candidate_root_recomputed": recomputed_root,
        "candidate_root_match": recomputed_root == CANDIDATE_ROOT,
    }
    (out_dir / "_audit_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
