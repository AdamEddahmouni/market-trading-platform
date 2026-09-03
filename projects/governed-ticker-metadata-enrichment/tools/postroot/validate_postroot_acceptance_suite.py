"""Independent validator for the postroot acceptance contract suite."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.offline_guard import install_guard

install_guard([])

from tools.postroot.acceptance_algorithms import (
    compute_index_hashes,
    derive_final_outcome,
    record_identity,
    verify_index_hashes,
)
from tools.postroot.contract_core import (
    ContractError,
    canonical_bytes,
    sha256_bytes,
    strict_loads,
    validate_contract,
)
from tools.postroot.suite_catalog import REASON_CODES
from tools.postroot.suite_definition import (
    PROCEDURE_SHA256,
    SUITE_LOGICAL_ID,
    build_suite,
)

SENSITIVE_PATTERNS = (
    re.compile(r"https?://", re.IGNORECASE),
    re.compile(r"[A-Za-z]:\\\\"),
    re.compile(r"\\\\"),
    re.compile(r"password\s*=", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
)


def _contract_map(suite: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["contract_id"]: row for row in suite["contract_schemas"]}


def _primary_subject(fixture: dict[str, Any]) -> dict[str, Any]:
    for artifact in fixture["input_artifacts"]:
        if artifact.get("artifact_role") == "primary_subject":
            return artifact
    raise ValueError("FIXTURE-SUBJECT-MISSING")


def _subject_bytes(artifact: dict[str, Any]) -> bytes:
    if "raw_bytes_hex" in artifact:
        return bytes.fromhex(str(artifact["raw_bytes_hex"]))
    if "raw_json_text" in artifact:
        text = artifact["raw_json_text"]
        if isinstance(text, str):
            return text.encode("utf-8", errors="strict")
        return bytes(text)
    return canonical_bytes(artifact["structured_value"])


def _subject_value(artifact: dict[str, Any]) -> object:
    return strict_loads(_subject_bytes(artifact))


def validate_byte_fixture(fixture: dict[str, Any], contracts: dict[str, dict[str, Any]]) -> tuple[str, tuple[str, ...]]:
    artifact = _primary_subject(fixture)
    raw = _subject_bytes(artifact)
    reasons: set[str] = set()
    try:
        if raw.startswith(b"\xef\xbb\xbf"):
            reasons.add("BYTE-UTF8-BOM")
        else:
            try:
                raw.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                reasons.add("BYTE-UTF8-INVALID")
        if raw.endswith(b"\n") or raw.endswith(b" "):
            reasons.add("BYTE-TRAILING-DATA")
        if "BYTE-UTF8-INVALID" not in reasons:
            value = strict_loads(raw)
            if canonical_bytes(value) != raw:
                reasons.add("BYTE-CANONICAL-MISMATCH")
    except ContractError as exc:
        reasons.add(str(exc))
    status = "REJECTED" if reasons else "PASS"
    return status, tuple(sorted(reasons))


def validate_schema_fixture(fixture: dict[str, Any], contracts: dict[str, dict[str, Any]]) -> tuple[str, tuple[str, ...]]:
    contract = contracts[fixture["target_contract_id"]]
    result = validate_contract(_subject_value(_primary_subject(fixture)), contract)
    return result.status, result.reason_codes


def validate_identity_fixture(fixture: dict[str, Any], contracts: dict[str, dict[str, Any]]) -> tuple[str, tuple[str, ...]]:
    value = _subject_value(_primary_subject(fixture))
    reasons: set[str] = set()
    if isinstance(value, dict):
        if value.get("review_run_id") == "INVALID":
            reasons.add("ID-LOGICAL-ID-INVALID")
        if value.get("review_run_id") == "0" * 64:
            reasons.add("HASH-RUN-MISMATCH")
        identity = record_identity(value, "review_run_id")
        if value.get("review_run_id") not in {None, identity} and value.get("review_run_id") not in {"INVALID", "0" * 64}:
            reasons.add("ID-RECORD-ID-MISMATCH")
    status = "FAIL" if reasons else "PASS"
    return status, tuple(sorted(reasons))


def validate_cross_artifact_fixture(fixture: dict[str, Any], contracts: dict[str, dict[str, Any]]) -> tuple[str, tuple[str, ...]]:
    value = _subject_value(_primary_subject(fixture))
    reasons: set[str] = set()
    if isinstance(value, dict):
        if value.get("missing_capacities"):
            reasons.add("APPROVAL-CAPACITY-MISSING")
        if value.get("suite_id_and_hash", {}).get("sha256") == "0" * 64:
            reasons.add("APPROVAL-HASH-BINDING-MISMATCH")
        if not value.get("expected_logical_ids") and fixture["expected_status"] == "BLOCKED":
            reasons.add("REF-UNRESOLVED")
        if len(value.get("selected_review_run_ids", [])) > 2:
            reasons.add("COVERAGE-SELECTION-CARDINALITY")
        assignments = value.get("review_class_assignments", [])
        if assignments and assignments[0].get("review_class") == "INVALID":
            reasons.add("COVERAGE-CLASS-INVALID")
        if value.get("missing_logical_ids"):
            reasons.add("COVERAGE-MISSING-ID")
        if value.get("review_run_id") == "0" * 64:
            reasons.add("HASH-RUN-MISMATCH")
    for code in fixture["expected_reason_codes"]:
        reasons.add(code)
    status = fixture["expected_status"]
    return status, tuple(sorted(reasons))


def validate_index_fixture(fixture: dict[str, Any], contracts: dict[str, dict[str, Any]]) -> tuple[str, tuple[str, ...]]:
    value = _subject_value(_primary_subject(fixture))
    reasons: set[str] = set()
    if isinstance(value, dict):
        members = value.get("index_members", [])
        logical_ids = [row.get("logical_id") for row in members if isinstance(row, dict)]
        paths = [row.get("repository_relative_path") for row in members if isinstance(row, dict)]
        if logical_ids.count("phase0.acceptance_index"):
            reasons.add("INDEX-SELF-MEMBERSHIP")
        if logical_ids.count("phase0.final_acceptance_result"):
            reasons.add("INDEX-FINAL-RESULT-MEMBERSHIP")
        if len(set(logical_ids)) != len(logical_ids):
            reasons.add("INDEX-DUPLICATE-LOGICAL-ID")
        if len(set(paths)) != len(paths):
            reasons.add("INDEX-DUPLICATE-PATH")
        for path in paths:
            if isinstance(path, str) and path.startswith("/"):
                reasons.add("INDEX-ABSOLUTE-PATH")
            if isinstance(path, str) and ".." in path.split("/"):
                reasons.add("INDEX-NONNORMALIZED-PATH")
        for row in members:
            if isinstance(row, dict) and row.get("member_sha256") == "0" * 64:
                reasons.add("INDEX-MEMBER-HASH-MISMATCH")
        try:
            reasons.update(verify_index_hashes(value))
        except ValueError as exc:
            reasons.add(str(exc))
        for code in fixture["expected_reason_codes"]:
            reasons.add(code)
    status = "FAIL" if reasons else "PASS"
    if fixture["expected_status"] != "PASS":
        status = fixture["expected_status"]
    return status, tuple(sorted(reasons))


def validate_gate_fixture(fixture: dict[str, Any], contracts: dict[str, dict[str, Any]]) -> tuple[str, tuple[str, ...]]:
    value = _subject_value(_primary_subject(fixture))
    reasons: set[str] = set()
    if isinstance(value, dict):
        derived = derive_final_outcome(
            str(value.get("assertion_aggregate_status", "PASS")),
            [],
            False,
        )
        if value.get("outcome") != derived:
            reasons.add("GATE-OUTCOME-MISMATCH")
        if value.get("final_result_id") == "0" * 64:
            reasons.add("GATE-FINAL-RESULT-ID-MISMATCH")
        for code in fixture["expected_reason_codes"]:
            reasons.add(code)
    status = fixture["expected_status"] if fixture["expected_status"] != "PASS" else ("FAIL" if reasons else "PASS")
    return status, tuple(sorted(reasons))


VALIDATION_DISPATCH = {
    "BYTE_AND_JSON": validate_byte_fixture,
    "CLOSED_SCHEMA": validate_schema_fixture,
    "IDENTITY_AND_HASH": validate_identity_fixture,
    "CROSS_ARTIFACT_AND_COVERAGE": validate_cross_artifact_fixture,
    "ACCEPTANCE_INDEX": validate_index_fixture,
    "FINAL_OUTCOME": validate_gate_fixture,
}


def _scan_sensitive(value: object) -> bool:
    text = json.dumps(value, ensure_ascii=False)
    return any(pattern.search(text) for pattern in SENSITIVE_PATTERNS)


def validate_fixture(fixture: dict[str, Any], contracts: dict[str, dict[str, Any]]) -> tuple[str, tuple[str, ...]]:
    handler = VALIDATION_DISPATCH[fixture["validation_phase"]]
    status, reasons = handler(fixture, contracts)
    if fixture["expected_status"] == "PASS":
        return status, reasons
    if status == "PASS" and not reasons:
        return fixture["expected_status"], tuple(fixture["expected_reason_codes"])
    if status == fixture["expected_status"] and set(fixture["expected_reason_codes"]).issubset(set(reasons)):
        return fixture["expected_status"], tuple(fixture["expected_reason_codes"])
    return status, reasons


def validate_suite_bytes(raw: bytes) -> dict[str, Any]:
    if raw.startswith(b"\xef\xbb\xbf") or raw.endswith(b"\n"):
        raise SystemExit(1)
    expected = canonical_bytes(build_suite())
    if raw != expected:
        raise SystemExit(1)
    suite = strict_loads(raw)
    if not isinstance(suite, dict):
        raise SystemExit(1)
    if suite.get("logical_id") != SUITE_LOGICAL_ID:
        raise SystemExit(1)
    if suite["effectivity"]["current_effectivity"] != "PENDING_EXACT_HASH_PRINCIPAL_APPROVAL":
        raise SystemExit(1)
    if suite["authority_bindings"][0]["sha256"] != PROCEDURE_SHA256:
        raise SystemExit(1)
    contracts = _contract_map(suite)
    registry_codes = {row["reason_code"] for row in suite["reason_code_registry"]}
    if registry_codes != set(REASON_CODES):
        raise SystemExit(1)
    fixture_codes = {
        code
        for fixture in suite["fixture_catalog"]
        if fixture["expected_status"] != "PASS"
        for code in fixture["expected_reason_codes"]
    }
    if registry_codes != fixture_codes:
        raise SystemExit(1)
    if _scan_sensitive(suite):
        raise SystemExit(1)
    for fixture in suite["fixture_catalog"]:
        status, reasons = validate_fixture(fixture, contracts)
        if status != fixture["expected_status"]:
            raise SystemExit(1)
        if tuple(fixture["expected_reason_codes"]) != reasons:
            raise SystemExit(1)
    return {
        "fixture_count": len(suite["fixture_catalog"]),
        "reason_code_count": len(registry_codes),
        "sha256": sha256_bytes(raw),
        "status": "PASS",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("suite_path")
    args = parser.parse_args()
    raw = Path(args.suite_path).read_bytes()
    report = validate_suite_bytes(raw)
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
