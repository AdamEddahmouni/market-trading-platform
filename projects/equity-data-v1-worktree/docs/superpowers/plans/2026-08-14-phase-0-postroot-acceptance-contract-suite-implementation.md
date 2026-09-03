# Phase 0 Postroot Acceptance Contract Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build, validate, and prepare for exact-hash approval the candidate-neutral postroot contract suite required to unblock the Phase 0 integrity review, without changing the current candidate evidence root or launching either formal review.

**Architecture:** A standard-library-only postroot toolchain under `tools/postroot/` defines the closed-contract dialect, deterministic identity/index/final-gate algorithms, reason registry, and synthetic fixture catalog. A deterministic builder publishes one canonical governed JSON suite; a separate validator reproduces every fixture result and verifies the committed artifact. Exact-hash principal approval is a mandatory stop point before a suite-approval record can be created.

**Tech Stack:** CPython 3.11 standard library, existing `market_platform_foundation.canonical` hash helpers where their LF-terminated profile is applicable, a postroot no-trailing-newline canonical encoder, `unittest`, canonical JSON, SHA-256, Git.

## Global Constraints

- The controlling written design is `docs/superpowers/specs/2026-08-14-phase-0-postroot-acceptance-contract-suite-design.md`, approved SHA-256 `EBD2E7A4153C09239792B8BDA952C672815BB323B524DF227A10D79750691D22`.
- Bind `AI-REVIEW-PROCESS-001` at SHA-256 `EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8`.
- Preserve candidate evidence root `78FA6A96D4193F53018ECFA7DFFAFFEBA3DA398A4E0116056C7C3BDDE8D2C482` and every historical evidence root byte-for-byte.
- Do not modify existing files under `evidence/phase0/`, `src/market_platform_foundation/`, `tests/phase0/`, `tools/phase0/`, or `manifests/phase0/`.
- Place executable support only under `tools/postroot/` and tests only under `tests/postroot/`; these paths are outside the existing Phase 0 distribution-policy include set.
- The governed suite is one JSON object encoded as UTF-8 without BOM, recursively sorted keys, compact separators, and no trailing newline.
- Use no third-party dependency, package download, network access, provider, broker, model service, remote Git host, donor execution, or private donor data.
- All fixture subjects are synthetic. Include no credential value, account identifier, sensitive absolute path, conversation content, market data, trade data, or donor data.
- Do not create a suite-approval record before the principal approves the complete suite's exact SHA-256.
- Do not create review-run, coverage, candidate-approval, acceptance-index, final-result, or Phase 0 `PASS` artifacts in this plan.
- Do not run the Phase 0 distribution or evidence pipeline from a postroot implementation commit.
- Each task starts from a clean worktree and ends with the named tests passing and one focused commit.

---

## File structure

Create these focused files:

- `tools/postroot/__init__.py` — marks the postroot tool package and exports no behavior.
- `tools/postroot/contract_core.py` — strict JSON parsing, no-LF canonical encoding, hashing, closed-schema validation primitives, and structured validation results.
- `tools/postroot/acceptance_algorithms.py` — content-derived identities, exact index membership, index/root hashes, and final outcome precedence.
- `tools/postroot/suite_definition.py` — complete contract declarations, reason-code registry, authority metadata, and synthetic fixtures.
- `tools/postroot/build_postroot_acceptance_suite.py` — deterministic `--write`/`--check` suite builder protected by the offline guard.
- `tools/postroot/validate_postroot_acceptance_suite.py` — independent committed-suite and fixture validator protected by the offline guard.
- `tools/postroot/build_postroot_suite_approval.py` — post-approval record builder; unusable without explicit approved hash and timestamp arguments.
- `tests/postroot/test_contract_core.py` — parser, canonicalization, schema, and diagnostic tests.
- `tests/postroot/test_acceptance_algorithms.py` — identity, index, root-hash, membership, and precedence tests.
- `tests/postroot/test_suite_definition.py` — suite shape, authority, contract, reason, sanitization, and fixture-completeness tests.
- `tests/postroot/test_suite_cli.py` — deterministic builder and validator CLI tests.
- `tests/postroot/test_suite_approval.py` — approval record identity, argument, and exact-suite-hash tests.
- `docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json` — generated governed suite.
- `docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite-approval.json` — generated only after exact-hash approval.

The plan does not alter the existing Phase 0 package or verifier. Review and final-gate implementation, if later authorized, consume this suite but are separate work.

---

### Task 1: Postroot canonical and closed-contract core

**Files:**
- Create: `tools/postroot/__init__.py`
- Create: `tools/postroot/contract_core.py`
- Create: `tests/postroot/test_contract_core.py`

**Interfaces:**
- Consumes: Python standard library only.
- Produces: `strict_loads(raw: bytes) -> object`, `canonical_bytes(value: object) -> bytes`, `sha256_bytes(raw: bytes) -> str`, `hash_without_fields(value: dict[str, object], omitted: set[str]) -> str`, `validate_contract(value: object, contract: dict[str, object]) -> ValidationResult`.

- [ ] **Step 1: Write strict parsing and canonical-byte tests**

Create `tests/postroot/test_contract_core.py` with tests equivalent to:

```python
import unittest

from tools.postroot.contract_core import (
    ContractError,
    canonical_bytes,
    hash_without_fields,
    strict_loads,
    validate_contract,
)


class ContractCoreTests(unittest.TestCase):
    def test_canonical_bytes_have_no_trailing_newline(self):
        self.assertEqual(canonical_bytes({"z": 1, "a": 2}), b'{"a":2,"z":1}')

    def test_duplicate_key_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "JSON-DUPLICATE-KEY"):
            strict_loads(b'{"a":1,"a":2}')

    def test_bom_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "BYTE-UTF8-BOM"):
            strict_loads(b'\xef\xbb\xbf{}')

    def test_hash_omits_only_named_fields(self):
        left = hash_without_fields({"id": "ignored", "value": 1}, {"id"})
        right = hash_without_fields({"id": "different", "value": 1}, {"id"})
        self.assertEqual(left, right)

    def test_closed_object_rejects_extra_field(self):
        contract = {
            "additional_properties": "REJECT",
            "contract_id": "example",
            "field_rules": {
                "name": {"type": "string", "format": "NONEMPTY"},
            },
            "required_fields": ["name"],
            "schema_version": "1.0.0",
            "validation_rules": [],
        }
        result = validate_contract({"name": "ok", "extra": True}, contract)
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.reason_codes, ("SCHEMA-UNDECLARED-FIELD",))
```

- [ ] **Step 2: Run the new test and verify the expected import failure**

Run:

```powershell
$env:PYTHONPATH='src;.'
python -m unittest discover -s tests/postroot -p 'test_contract_core.py' -v
```

Expected: `ModuleNotFoundError: No module named 'tools.postroot.contract_core'`.

- [ ] **Step 3: Implement the core API**

Create an empty `tools/postroot/__init__.py`. Implement
`tools/postroot/contract_core.py` with these exact public shapes:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from typing import Any

SHA256_RE = re.compile(r"^[0-9A-F]{64}$")
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{9}Z$")


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class ValidationResult:
    status: str
    reason_codes: tuple[str, ...]


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("JSON-DUPLICATE-KEY")
        result[key] = value
    return result


def strict_loads(raw: bytes) -> object:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ContractError("BYTE-UTF8-BOM")
    try:
        text = raw.decode("utf-8", errors="strict")
        return json.loads(text, object_pairs_hook=_pairs_no_duplicates)
    except UnicodeDecodeError as exc:
        raise ContractError("BYTE-UTF8-INVALID") from exc
    except json.JSONDecodeError as exc:
        raise ContractError("JSON-PARSE-INVALID") from exc


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest().upper()


def hash_without_fields(value: dict[str, object], omitted: set[str]) -> str:
    return sha256_bytes(canonical_bytes({k: v for k, v in value.items() if k not in omitted}))
```

Add private recursive field validation supporting exactly `object`, `array`,
`string`, `integer`, and `boolean`; formats `NONEMPTY`, `SHA256`, `TIMESTAMP`, and
`LOGICAL_ID`; enum arrays; nested `field_rules`; array `item_rule`; and
`ordering` values `LEXICOGRAPHIC_UNIQUE` or `SEQUENCE`. `validate_contract`
must return every independently evaluable sorted unique schema code from:

```python
SCHEMA_CODES = {
    "SCHEMA-ADDITIONAL-PROPERTY-POLICY",
    "SCHEMA-ARRAY-DUPLICATE",
    "SCHEMA-ARRAY-ORDER",
    "SCHEMA-ENUM-INVALID",
    "SCHEMA-FORMAT-INVALID",
    "SCHEMA-MISSING-REQUIRED-FIELD",
    "SCHEMA-TYPE-INVALID",
    "SCHEMA-UNDECLARED-FIELD",
}
```

Reject booleans where `integer` is required. Validate timestamps by both regular
expression and `datetime.strptime(value[:26] + "Z", "%Y-%m-%dT%H:%M:%S.%fZ")`.

- [ ] **Step 4: Run the focused tests**

Run the Task 1 command again.

Expected: all `ContractCoreTests` pass.

- [ ] **Step 5: Commit the core**

```powershell
git add tools/postroot/__init__.py tools/postroot/contract_core.py tests/postroot/test_contract_core.py
git commit -m "feat: add postroot contract validation core"
```

---

### Task 2: Deterministic acceptance identities and gate algorithms

**Files:**
- Create: `tools/postroot/acceptance_algorithms.py`
- Create: `tests/postroot/test_acceptance_algorithms.py`

**Interfaces:**
- Consumes: `canonical_bytes`, `hash_without_fields`, and `sha256_bytes` from Task 1.
- Produces: `record_identity`, `expected_index_logical_ids`, `compute_index_hashes`, `verify_index_hashes`, and `derive_final_outcome`.

- [ ] **Step 1: Write algorithm tests**

Create tests that exercise these exact cases:

```python
import unittest

from tools.postroot.acceptance_algorithms import (
    compute_index_hashes,
    derive_final_outcome,
    expected_index_logical_ids,
    record_identity,
)


class AcceptanceAlgorithmTests(unittest.TestCase):
    def test_record_identity_omits_only_identity_field(self):
        record = {"approval_record_id": "X", "status": "APPROVED"}
        self.assertEqual(
            record_identity(record, "approval_record_id"),
            record_identity({**record, "approval_record_id": "Y"}, "approval_record_id"),
        )

    def test_expected_index_ids_add_exact_postroot_set(self):
        ids = expected_index_logical_ids(["a", "b"])
        self.assertEqual(
            ids,
            (
                "a",
                "b",
                "phase0.ai_review_coverage",
                "phase0.ai_review_runs",
                "phase0.approval_records",
                "phase0.candidate_evidence_root",
                "phase0.postroot_acceptance_contract_suite",
                "phase0.postroot_acceptance_contract_suite.approval",
            ),
        )

    def test_index_hashes_are_order_independent_before_normalization(self):
        base = {
            "candidate_evidence_root": "A" * 64,
            "index_members": [
                {"logical_id": "b", "member_sha256": "B" * 64},
                {"logical_id": "a", "member_sha256": "A" * 64},
            ],
            "logical_id": "phase0.acceptance_index",
        }
        self.assertEqual(compute_index_hashes(base), compute_index_hashes({**base, "index_members": list(reversed(base["index_members"]))}))

    def test_fail_precedes_blocked(self):
        self.assertEqual(derive_final_outcome("PASS", ["FAIL", "BLOCKED"], False), "FAIL")

    def test_absence_blocks_when_nothing_is_invalid(self):
        self.assertEqual(derive_final_outcome("PASS", [], True), "BLOCKED")
```

- [ ] **Step 2: Run the tests to verify the import failure**

Run:

```powershell
$env:PYTHONPATH='src;.'
python -m unittest discover -s tests/postroot -p 'test_acceptance_algorithms.py' -v
```

Expected: import failure for `tools.postroot.acceptance_algorithms`.

- [ ] **Step 3: Implement exact algorithms**

Create `tools/postroot/acceptance_algorithms.py` around these definitions:

```python
from __future__ import annotations

from .contract_core import canonical_bytes, hash_without_fields, sha256_bytes

POSTROOT_INDEX_IDS = {
    "phase0.ai_review_coverage",
    "phase0.ai_review_runs",
    "phase0.approval_records",
    "phase0.candidate_evidence_root",
    "phase0.postroot_acceptance_contract_suite",
    "phase0.postroot_acceptance_contract_suite.approval",
}


def record_identity(record: dict[str, object], identity_field: str) -> str:
    return hash_without_fields(record, {identity_field})


def expected_index_logical_ids(candidate_ids: list[str]) -> tuple[str, ...]:
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ValueError("INDEX-DUPLICATE-LOGICAL-ID")
    return tuple(sorted(set(candidate_ids) | POSTROOT_INDEX_IDS))


def compute_index_hashes(index: dict[str, object]) -> tuple[str, str]:
    provisional = {k: v for k, v in index.items() if k not in {"index_sha256", "root_hash"}}
    rows = provisional.get("index_members")
    if not isinstance(rows, list):
        raise ValueError("INDEX-MEMBERS-INVALID")
    ordered_rows = sorted(rows, key=lambda row: (str(row["logical_id"]), str(row.get("repository_relative_path", ""))))
    provisional["index_members"] = ordered_rows
    index_sha256 = sha256_bytes(canonical_bytes(provisional))
    ordered_pairs = sorted(
        [[str(row["logical_id"]), str(row["member_sha256"])] for row in ordered_rows],
        key=lambda pair: (pair[0], pair[1]),
    )
    root_input = {"index_sha256": index_sha256, "ordered_member_pairs": ordered_pairs}
    return index_sha256, sha256_bytes(canonical_bytes(root_input))


def verify_index_hashes(index: dict[str, object]) -> tuple[str, ...]:
    expected_index, expected_root = compute_index_hashes(index)
    reasons = []
    if index.get("index_sha256") != expected_index:
        reasons.append("INDEX-SHA256-MISMATCH")
    if index.get("root_hash") != expected_root:
        reasons.append("INDEX-ROOT-HASH-MISMATCH")
    return tuple(sorted(reasons))


def derive_final_outcome(
    assertion_aggregate_status: str,
    observed_invalid_statuses: list[str],
    required_evidence_absent: bool,
) -> str:
    if assertion_aggregate_status == "FAIL" or "FAIL" in observed_invalid_statuses or "INVALID" in observed_invalid_statuses:
        return "FAIL"
    if assertion_aggregate_status == "BLOCKED" or "BLOCKED" in observed_invalid_statuses or required_evidence_absent:
        return "BLOCKED"
    return "PASS" if assertion_aggregate_status == "PASS" else "BLOCKED"
```

Add input checks that reject duplicate logical IDs, duplicate paths, self/index
membership, final-result membership, missing SHA-256 fields, and unsortable rows
with their exact `INDEX-` reason codes.

- [ ] **Step 4: Run the focused tests**

Expected: all Task 2 tests pass.

- [ ] **Step 5: Commit the algorithms**

```powershell
git add tools/postroot/acceptance_algorithms.py tests/postroot/test_acceptance_algorithms.py
git commit -m "feat: add postroot acceptance algorithms"
```

---

### Task 3: Closed contract declarations and authority boundary

**Files:**
- Create: `tools/postroot/suite_definition.py`
- Create: `tests/postroot/test_suite_definition.py`

**Interfaces:**
- Consumes: design constants and procedure/plan hashes.
- Produces: `build_contract_schemas() -> list[dict[str, object]]` and `build_suite() -> dict[str, object]`.

- [ ] **Step 1: Write contract inventory tests**

Test that `build_contract_schemas()` produces exactly these sorted IDs:

```python
EXPECTED_CONTRACT_IDS = (
    "phase0.acceptance_index.contract",
    "phase0.ai_review_coverage.contract",
    "phase0.ai_review_output.contract",
    "phase0.ai_review_run.contract",
    "phase0.approval_records.contract",
    "phase0.final_acceptance_result.contract",
    "phase0.preapproval_reviewer_eligibility.contract",
    "phase0.postroot_acceptance_contract_suite.approval.contract",
)
```

Also assert:

```python
self.assertEqual(suite["logical_id"], "phase0.postroot_acceptance_contract_suite")
self.assertEqual(suite["effectivity"]["current_effectivity"], "PENDING_EXACT_HASH_PRINCIPAL_APPROVAL")
self.assertNotIn("candidate_evidence_root", suite["suite_scope"])
self.assertEqual(
    suite["authority_bindings"][0]["sha256"],
    "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8",
)
```

- [ ] **Step 2: Run the tests and verify the missing module failure**

Run:

```powershell
$env:PYTHONPATH='src;.'
python -m unittest discover -s tests/postroot -p 'test_suite_definition.py' -v
```

Expected: import failure for `tools.postroot.suite_definition`.

- [ ] **Step 3: Implement the suite shell and all eight contracts**

Define immutable constants:

```python
PROCEDURE_ID = "AI-REVIEW-PROCESS-001"
PROCEDURE_SHA256 = "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8"
PLAN_SHA256 = "EE22C688167F5016D7ED1953BB1DAE516BC6AB343655A7D96535C6605D37E904"
SPECIFICATION_SHA256 = "7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35"
SUITE_LOGICAL_ID = "phase0.postroot_acceptance_contract_suite"
SUITE_APPROVAL_LOGICAL_ID = "phase0.postroot_acceptance_contract_suite.approval"
```

Use a helper with no optional fields:

```python
def contract(contract_id: str, field_rules: dict[str, object], validation_rules: list[str]) -> dict[str, object]:
    return {
        "additional_properties": "REJECT",
        "contract_id": contract_id,
        "field_rules": field_rules,
        "required_fields": sorted(field_rules),
        "schema_version": "1.0.0",
        "validation_rules": validation_rules,
    }
```

For review output, review run, and coverage, copy every exact required field,
enum, nested required-field list, ordering rule, and identity rule from
`AI-REVIEW-PROCESS-001`; do not add a suite field to the coverage object. Require
the integrity run's existing `input_artifact_hashes` array to contain both suite
logical IDs and hashes.

For preapproval eligibility, copy the six exact check IDs and all count,
ordering, reason, authority, and effectivity rules from
`2026-08-14-gov-002-preapproval-reviewer-eligibility.json`.

For the remaining four contracts, use the exact required fields in Design
Sections 8.5 through 8.8. Encode SHA-256, timestamp, logical-ID, enum, sorted-set,
nested-object, and sequence semantics in `field_rules`; put cross-field hash and
outcome rules in `validation_rules`.

Return a suite shell with exactly the top-level fields in Design Section 7 and
these exact non-authorizations:

```python
NON_AUTHORIZATIONS = [
    "ACCEPTANCE_INDEX_PUBLICATION",
    "AI_REVIEW_COVERAGE_PUBLICATION",
    "CANDIDATE_APPROVAL_PUBLICATION",
    "CANDIDATE_ROOT_RECONSTRUCTION",
    "FINAL_ACCEPTANCE_RESULT_PUBLICATION",
    "FORMAL_AI_REVIEW_RUN_EXECUTION",
    "PHASE_0A_OR_LATER_PHASE_WORK",
    "PHASE_0_PASS",
    "PROVIDER_BROKER_MODEL_OR_REMOTE_ACCESS",
]
```

- [ ] **Step 4: Run declaration tests**

Expected: exact contract inventory, required fields, procedure hash, pending
effectivity, and candidate-neutrality tests pass.

- [ ] **Step 5: Commit the declarations**

```powershell
git add tools/postroot/suite_definition.py tests/postroot/test_suite_definition.py
git commit -m "feat: define postroot acceptance contracts"
```

---

### Task 4: Reason registry and synthetic fixture catalog

**Files:**
- Modify: `tools/postroot/suite_definition.py`
- Modify: `tests/postroot/test_suite_definition.py`

**Interfaces:**
- Consumes: contract IDs and validation phases from Task 3.
- Produces: `build_reason_code_registry()` and `build_fixture_catalog()`.

- [ ] **Step 1: Add registry and coverage tests**

Assert exact prefix coverage and one adversarial fixture per reason:

```python
REQUIRED_PREFIXES = (
    "APPROVAL-", "BYTE-", "COVERAGE-", "GATE-", "HASH-", "ID-",
    "INDEX-", "JSON-", "REF-", "REVIEW-", "SCHEMA-",
)

codes = {row["reason_code"] for row in suite["reason_code_registry"]}
fixture_codes = {
    code
    for fixture in suite["fixture_catalog"]
    if fixture["expected_status"] != "PASS"
    for code in fixture["expected_reason_codes"]
}
self.assertTrue(all(any(code.startswith(prefix) for code in codes) for prefix in REQUIRED_PREFIXES))
self.assertEqual(codes, fixture_codes)
self.assertEqual(
    [row["fixture_id"] for row in suite["fixture_catalog"]],
    sorted(row["fixture_id"] for row in suite["fixture_catalog"]),
)
```

- [ ] **Step 2: Run the new tests and verify they fail**

Expected: failure because the registry and fixture catalog are empty.

- [ ] **Step 3: Add the exact reason registry**

Register one semantic condition and gate effect for each of these codes:

```text
APPROVAL-CAPACITY-DUPLICATE
APPROVAL-CAPACITY-EXTRA
APPROVAL-CAPACITY-MISSING
APPROVAL-HASH-BINDING-MISMATCH
APPROVAL-IDENTITY-INVALID
APPROVAL-NOT-EFFECTIVE
APPROVAL-PRINCIPAL-MISMATCH
APPROVAL-WAIVER-ATTEMPT
BYTE-CANONICAL-MISMATCH
BYTE-TRAILING-DATA
BYTE-UTF8-BOM
BYTE-UTF8-INVALID
COVERAGE-CLASS-INVALID
COVERAGE-DUPLICATE-IDENTITY
COVERAGE-EXTRA-ID
COVERAGE-ISOLATION-INVALID
COVERAGE-MISSING-ID
COVERAGE-SELECTION-CARDINALITY
GATE-FINAL-RESULT-ID-MISMATCH
GATE-OUTCOME-MISMATCH
GATE-PRECEDENCE-MISMATCH
HASH-CANDIDATE-ROOT-MISMATCH
HASH-CONTENT-MISMATCH
HASH-PROCEDURE-MISMATCH
HASH-REGISTRY-MISMATCH
HASH-REVIEW-OUTPUT-MISMATCH
HASH-RUN-MISMATCH
HASH-SUITE-MISMATCH
ID-DUPLICATE-SEMANTIC-IDENTITY
ID-LOGICAL-ID-INVALID
ID-RECORD-ID-MISMATCH
INDEX-ABSOLUTE-PATH
INDEX-DUPLICATE-LOGICAL-ID
INDEX-DUPLICATE-PATH
INDEX-EXTRA-MEMBER
INDEX-FINAL-RESULT-MEMBERSHIP
INDEX-MEMBER-BYTE-LENGTH-MISMATCH
INDEX-MEMBER-HASH-MISMATCH
INDEX-MISSING-MEMBER
INDEX-NONNORMALIZED-PATH
INDEX-ROOT-HASH-MISMATCH
INDEX-ROOT-ID-MISMATCH
INDEX-SELF-MEMBERSHIP
INDEX-SHA256-MISMATCH
INDEX-SYMLINK-OR-REPARSE-ESCAPE
JSON-DUPLICATE-KEY
JSON-PARSE-INVALID
REF-CONTRADICTORY-BINDING
REF-UNRESOLVED
REVIEW-AUTHORING-CONTEXT
REVIEW-CLASS-MISSING
REVIEW-DISQUALIFICATION-CODE-MISMATCH
REVIEW-GOVERNED-SUBJECT-MUTATION
REVIEW-OUTCOME-MISMATCH
REVIEW-UNDECLARED-TOOL-OR-EXTERNAL-ACCESS
SCHEMA-ARRAY-DUPLICATE
SCHEMA-ARRAY-ORDER
SCHEMA-ENUM-INVALID
SCHEMA-FORMAT-INVALID
SCHEMA-MISSING-REQUIRED-FIELD
SCHEMA-TYPE-INVALID
SCHEMA-UNDECLARED-FIELD
```

Use gate effect `FAIL` for demonstrably invalid selected evidence, `REJECTED`
for unparseable fixture subjects before selection, and `BLOCKED` only for exact
absence codes represented by coverage or approval fixtures. Every description is
a nonempty sanitized sentence.

- [ ] **Step 4: Add complete fixture builders**

Implement `fixture(...)` so every fixture has exactly the eight fields from
Design Section 12. Use only synthetic values such as `"A" * 64`, `"B" * 64`,
opaque `ROOT-TEST-001`, and repository-relative `synthetic/fixture-name.json`
paths.

Add the full minimum catalog from Design Sections 13.1 through 13.6. Use exact
UTF-8 JSON strings for malformed byte cases and structured artifact arrays for
cross-artifact cases. Each registered code must appear in at least one
adversarial fixture and every fixture code must be registered. Include golden
fixtures with IDs:

```text
GOLDEN-ACCEPTANCE-INDEX-001
GOLDEN-AI-REVIEW-COVERAGE-001
GOLDEN-AI-REVIEW-OUTPUT-001
GOLDEN-AI-REVIEW-RUN-001
GOLDEN-APPROVAL-RECORDS-001
GOLDEN-FINAL-ACCEPTANCE-RESULT-001
GOLDEN-PREAPPROVAL-ELIGIBILITY-001
GOLDEN-SUITE-APPROVAL-001
```

For missing-evidence fixtures, set the expected contract status to `BLOCKED`
with the contract-specific missing reason. For present malformed artifacts, set
`FAIL` or `INVALID` according to the consuming contract. For raw parse subjects,
set `REJECTED`.

- [ ] **Step 5: Run fixture inventory tests**

Expected: all reason codes are registered, all have adversarial coverage, every
contract has a golden vector, fixture IDs are unique/sorted, and all fixture
content passes the sanitization word/path scan.

- [ ] **Step 6: Commit the registry and catalog**

```powershell
git add tools/postroot/suite_definition.py tests/postroot/test_suite_definition.py
git commit -m "feat: add postroot contract fixtures"
```

---

### Task 5: Deterministic suite builder and governed artifact

**Files:**
- Create: `tools/postroot/build_postroot_acceptance_suite.py`
- Create: `tests/postroot/test_suite_cli.py`
- Create: `docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json`

**Interfaces:**
- Consumes: `build_suite()` and no-LF canonical bytes.
- Produces: deterministic governed suite bytes and CLI exit status.

- [ ] **Step 1: Write CLI tests**

Use a temporary output path and subprocess invocation with these assertions:

```python
def test_two_writes_are_byte_identical(self):
    first = self.run_builder("--write", self.first)
    second = self.run_builder("--write", self.second)
    self.assertEqual(first.returncode, 0)
    self.assertEqual(second.returncode, 0)
    self.assertEqual(self.first.read_bytes(), self.second.read_bytes())
    self.assertFalse(self.first.read_bytes().endswith(b"\n"))

def test_check_rejects_changed_bytes(self):
    self.run_builder("--write", self.first)
    self.first.write_bytes(self.first.read_bytes() + b"\n")
    result = self.run_builder("--check", self.first)
    self.assertNotEqual(result.returncode, 0)
    self.assertIn("SUITE-BYTES-MISMATCH", result.stderr)
```

- [ ] **Step 2: Run CLI tests and verify the missing script failure**

Run:

```powershell
$env:PYTHONPATH='src;.'
python -m unittest discover -s tests/postroot -p 'test_suite_cli.py' -v
```

Expected: failure because the builder does not exist.

- [ ] **Step 3: Implement `--write` and `--check`**

The script must:

1. insert repository `src` and root paths into `sys.path`;
2. install `market_platform_foundation.offline_guard.install_guard([])` before
   loading suite implementation modules;
3. accept exactly one of `--write PATH` or `--check PATH`;
4. call `canonical_bytes(build_suite())`;
5. for `--write`, refuse to overwrite existing unequal bytes unless
   `--replace-unapproved` is explicitly supplied;
6. for `--check`, compare exact bytes and emit only the suite SHA-256 on success;
7. use exit code 0 for success and nonzero for mismatch or invalid arguments.

Core main structure:

```python
def main() -> int:
    args = parse_args()
    expected = canonical_bytes(build_suite())
    target = Path(args.write or args.check)
    if args.check:
        if not target.is_file() or target.read_bytes() != expected:
            raise SystemExit("SUITE-BYTES-MISMATCH")
        print(sha256_bytes(expected))
        return 0
    if target.exists() and target.read_bytes() != expected and not args.replace_unapproved:
        raise SystemExit("REFUSE-UNEQUAL-SUITE-OVERWRITE")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(expected)
    print(sha256_bytes(expected))
    return 0
```

- [ ] **Step 4: Generate the governed suite once**

Run:

```powershell
$env:PYTHONPATH='src;.'
python tools/postroot/build_postroot_acceptance_suite.py --write docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json
```

Expected: one uppercase 64-character SHA-256. Record it in the task log but do
not call it approved.

- [ ] **Step 5: Run builder tests and exact-byte check**

Run the Task 5 test command, then:

```powershell
python tools/postroot/build_postroot_acceptance_suite.py --check docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json
```

Expected: tests pass and the same suite SHA-256 is printed.

- [ ] **Step 6: Commit builder and unapproved suite**

```powershell
git add tools/postroot/build_postroot_acceptance_suite.py tests/postroot/test_suite_cli.py docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json
git commit -m "feat: publish unapproved postroot contract suite"
```

---

### Task 6: Independent suite validator and fixture reproduction

**Files:**
- Create: `tools/postroot/validate_postroot_acceptance_suite.py`
- Modify: `tests/postroot/test_suite_cli.py`

**Interfaces:**
- Consumes: committed suite, contract core, algorithms, and expected fixture results.
- Produces: sanitized aggregate `{fixture_count, reason_code_count, sha256, status}` and process exit code.

- [ ] **Step 1: Add validator tests**

Test these cases:

```python
def test_committed_suite_validates(self):
    result = self.run_validator(self.committed_suite)
    self.assertEqual(result.returncode, 0)
    report = json.loads(result.stdout)
    self.assertEqual(report["status"], "PASS")
    self.assertGreater(report["fixture_count"], 40)

def test_changed_suite_is_rejected(self):
    changed = self.temp_dir / "changed.json"
    changed.write_bytes(self.committed_suite.read_bytes() + b"\n")
    result = self.run_validator(changed)
    self.assertNotEqual(result.returncode, 0)
    self.assertNotIn(str(changed.resolve()), result.stderr)
```

- [ ] **Step 2: Run tests and verify missing validator failure**

Expected: failure because the validator script does not exist.

- [ ] **Step 3: Implement validation phases**

The validator must install the offline guard first, then:

1. read raw bytes without printing a path;
2. reject BOM, trailing newline, invalid UTF-8, duplicate keys, noncanonical
   bytes, or top-level shape mismatch;
3. verify exact authority hashes and pending effectivity;
4. validate every contract declaration;
5. verify reason-code uniqueness, prefix validity, and one-to-one adversarial
   fixture coverage;
6. execute every embedded fixture through its declared validation phase;
7. compare exact expected status, sorted reasons, and derived values;
8. verify no prohibited sensitive term, absolute drive path, UNC path, URL,
   credential-like assignment, or non-synthetic content appears;
9. emit one compact JSON report with no absolute paths.

Use dispatch with no dynamic import:

```python
VALIDATION_DISPATCH = {
    "BYTE_AND_JSON": validate_byte_fixture,
    "CLOSED_SCHEMA": validate_schema_fixture,
    "IDENTITY_AND_HASH": validate_identity_fixture,
    "CROSS_ARTIFACT_AND_COVERAGE": validate_cross_artifact_fixture,
    "ACCEPTANCE_INDEX": validate_index_fixture,
    "FINAL_OUTCOME": validate_gate_fixture,
}
```

Reject unknown phases, contract IDs, statuses, or reason codes. Never execute
fixture text as code or pass it to a shell.

- [ ] **Step 4: Run all postroot tests and validator**

```powershell
$env:PYTHONPATH='src;.'
python -m unittest discover -s tests/postroot -v
python tools/postroot/validate_postroot_acceptance_suite.py docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json
```

Expected: all tests pass; validator emits `status: PASS`, exact suite SHA-256,
fixture count, and reason-code count.

- [ ] **Step 5: Commit the validator**

```powershell
git add tools/postroot/validate_postroot_acceptance_suite.py tests/postroot/test_suite_cli.py
git commit -m "feat: validate postroot acceptance suite"
```

---

### Task 7: Preservation, regression, and exact-hash approval checkpoint

**Files:**
- Modify: `tests/postroot/test_suite_definition.py`
- Do not create the suite approval record in this task.

**Interfaces:**
- Consumes: committed suite and immutable candidate evidence.
- Produces: a verified exact suite hash ready for principal review.

- [ ] **Step 1: Add preservation regression tests**

Read the current candidate manifest and assert:

```python
CANDIDATE_ROOT = "78FA6A96D4193F53018ECFA7DFFAFFEBA3DA398A4E0116056C7C3BDDE8D2C482"
SUITE_IDS = {
    "phase0.postroot_acceptance_contract_suite",
    "phase0.postroot_acceptance_contract_suite.approval",
}

manifest = json.loads(CANDIDATE_MANIFEST.read_text(encoding="utf-8"))
self.assertEqual(manifest["candidate_evidence_root"], CANDIDATE_ROOT)
self.assertTrue(SUITE_IDS.isdisjoint(row[0] for row in manifest["ordered_member_tuples"]))
```

Capture and compare a read-only SHA-256 inventory for every existing file below
each `evidence/phase0/RUN_ID_DIRECTORY` before and after the postroot test suite. The test
must fail on any changed, added, removed, or renamed historical evidence file.

- [ ] **Step 2: Run the new preservation tests before commit**

Run:

```powershell
$env:PYTHONPATH='src;.'
python -m unittest discover -s tests/postroot -p 'test_suite_definition.py' -v
```

Expected: preservation tests pass. `git status --short` reports only the intended
modification to `tests/postroot/test_suite_definition.py`.

- [ ] **Step 3: Commit preservation tests**

```powershell
git add tests/postroot/test_suite_definition.py
git commit -m "test: preserve candidate during postroot suite work"
```

- [ ] **Step 4: Run complete verification from the clean commit**

Run:

```powershell
$env:PYTHONPATH='src;.'
python -m unittest discover -s tests/phase0 -v
python -m unittest discover -s tests/postroot -v
python tools/postroot/build_postroot_acceptance_suite.py --check docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json
python tools/postroot/validate_postroot_acceptance_suite.py docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json
git status --short --branch
git ls-files --eol
```

Expected: 48 Phase 0 tests pass with the existing one Windows capability skip;
all postroot tests pass; builder and validator agree on one hash; repository is
clean; the new files are `i/lf w/lf`; no
existing evidence changes are reported.

- [ ] **Step 5: Stop for principal exact-hash review**

Present:

- suite path and byte length;
- exact uppercase SHA-256 from both builder and validator;
- contract, fixture, and reason-code counts;
- all test results;
- current Git HEAD and clean status;
- confirmation that the candidate root and historical evidence are unchanged;
- explicit statement that the suite is unapproved and formal reviews remain
  blocked.

Do not proceed to Task 8 until the principal explicitly approves the exact suite
logical ID and SHA-256.

---

### Task 8: Exact-hash suite approval record after approval

**Files:**
- Create: `tools/postroot/build_postroot_suite_approval.py`
- Create: `tests/postroot/test_suite_approval.py`
- Create: `docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite-approval.json`

**Interfaces:**
- Consumes: the principal-approved suite SHA-256 and approval timestamp.
- Produces: one canonical suite approval record and content-derived `approval_record_id`.

- [ ] **Step 1: Write approval builder tests**

Test missing arguments, wrong suite hash, wrong procedure hash, noncanonical
timestamp, deterministic identity, and valid output. The valid record must have
exactly:

```python
APPROVAL_FIELDS = {
    "approval_record_id",
    "approved_at",
    "approved_by_principal_id",
    "approved_capacities",
    "approved_logical_id",
    "approved_sha256",
    "approval_scope",
    "procedure_id",
    "procedure_sha256",
    "status",
}
```

- [ ] **Step 2: Run the tests and verify the missing script failure**

Expected: import or subprocess failure because the builder does not exist.

- [ ] **Step 3: Implement the approval builder**

Require explicit command-line values for `--approved-suite-sha256` and
`--approved-at`; do not infer approval from the suite file. Verify the supplied
hash equals the actual suite hash. Construct:

```python
record_without_id = {
    "approved_at": args.approved_at,
    "approved_by_principal_id": "PROJECT-PRINCIPAL-001",
    "approved_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
    "approved_logical_id": "phase0.postroot_acceptance_contract_suite",
    "approved_sha256": args.approved_suite_sha256,
    "approval_scope": "INTEGRITY_REVIEW_COMPANION_INPUT_ONLY",
    "procedure_id": "AI-REVIEW-PROCESS-001",
    "procedure_sha256": PROCEDURE_SHA256,
    "status": "APPROVED",
}
record = {
    **record_without_id,
    "approval_record_id": sha256_bytes(canonical_bytes(record_without_id)),
}
```

Write no trailing newline. Refuse unequal overwrite unless an explicit
`--replace-unapproved-record` flag is present. Never accept an approval timestamp
that predates the approved suite commit.

- [ ] **Step 4: Generate the approval record with the actual approved values**

Run only after copying the exact hash and timestamp supplied by the principal
approval event into the task-specific PowerShell variables
`$suiteApprovalHash` and `$suiteApprovalTimestamp`:

```powershell
$env:PYTHONPATH='src;.'
python tools/postroot/build_postroot_suite_approval.py --approved-suite-sha256 $suiteApprovalHash --approved-at $suiteApprovalTimestamp --write docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite-approval.json
```

The variables are execution-time inputs from the principal's explicit approval
event, not values an implementer may infer or invent.

- [ ] **Step 5: Validate and commit the approval record**

Run all postroot tests and validate the record against the suite's approval
contract. Then commit:

```powershell
git add tools/postroot/build_postroot_suite_approval.py tests/postroot/test_suite_approval.py docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite-approval.json
git commit -m "docs: record exact-hash postroot suite approval"
```

Expected: approval identity recomputes, suite hash matches exact bytes, procedure
binding matches, and the record contains no candidate approval.

---

### Task 9: Final prerequisite audit and governed handoff

**Files:**
- Modify outside Git only: `C:\Users\adame\Desktop\market-trading-platform\CURSOR_SESSION_HANDOFF_2026-08-14.md`
- Do not create formal review outputs or evidence.

**Interfaces:**
- Consumes: approved suite, suite approval, candidate bundle, and procedure.
- Produces: a read-only prerequisite report and continuation handoff.

- [ ] **Step 1: Run final local verification**

Repeat the complete Task 7 commands. Additionally recompute hashes for the
procedure, suite, suite approval, candidate-root manifest, registry, and
assertion-run manifest. Verify the suite/approval logical IDs remain absent from
the candidate tuple array and present only as approved postroot inputs.

- [ ] **Step 2: Verify reviewer input eligibility without launching a reviewer**

Construct an in-memory list of the exact permitted sanitized integrity-review
inputs. Check that it contains the approved procedure, candidate-root manifest,
candidate bundle, approved suite, suite approval, class instruction, and declared
read-only tool versions—and nothing prohibited. Do not publish this list as a
review run or acceptance artifact.

- [ ] **Step 3: Update the Cursor handoff**

Record:

- current HEAD and clean status;
- suite and approval paths, logical IDs, hashes, and approval timestamp;
- test counts and results;
- preservation checks;
- exact candidate root and Phase 0 blocked state;
- whether all integrity-review prerequisites now resolve;
- the next procedure-authorized action;
- explicit reminder that the current authoring context is not either independent reviewer.

- [ ] **Step 4: Stop before formal review initialization**

Report the prerequisite outcome. If any prerequisite is missing or invalid,
report `BLOCKED` and do not launch either review. If all prerequisites pass,
request or confirm the separate authorization to initialize exactly two fresh,
read-only review contexts under `AI-REVIEW-PROCESS-001`.

The completion of this implementation plan does not change Phase 0 from
`BLOCKED_PENDING_POSTROOT_ACCEPTANCE`.

---

## Plan completion criteria

The plan is complete only when Tasks 1 through 7 have produced a deterministic,
validated, unapproved suite and stopped for exact-hash approval; Tasks 8 and 9
execute only after that approval. At no point does this plan create formal AI
review evidence, review coverage, candidate approval, an acceptance index, a
final acceptance result, or a Phase 0 pass claim.
