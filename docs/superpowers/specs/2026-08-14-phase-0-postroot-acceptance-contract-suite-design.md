# Phase 0 Postroot Acceptance Contract Suite Design

**Document date:** 2026-08-14  
**Status:** WRITTEN_SPEC_REVIEW_PENDING  
**Design scope:** Governance documentation only  
**Intended suite logical ID:** `phase0.postroot_acceptance_contract_suite`  
**Controlling review procedure:** `AI-REVIEW-PROCESS-001`  
**Target procedure SHA-256:** `EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8`

## 1. Purpose

This design resolves the deferred prerequisite that currently prevents a
qualifying `INTEGRITY_AND_REPRODUCTION_AUDIT` from beginning. It defines a
single, self-contained, canonical JSON contract suite containing the missing
acceptance-index construction rules, closed schemas, positive fixtures, and
adversarial fixtures required by `AI-REVIEW-PROCESS-001`.

The future suite is a separately governed postroot review input. It is not a
member of the existing candidate evidence root, does not change or approve any
candidate-root member, and does not itself perform a review or final gate.

This document does not create or approve the suite. It defines the design that
a later implementation plan may realize after the written specification is
reviewed.

## 2. Controlling boundaries

The design is subordinate to the following exact authorities:

- `foundation.canonical_specification.revision_3`, SHA-256
  `7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35`;
- the Revision 2 Phase 0 safety authority incorporated by Revision 3;
- the controlling Phase 0 governance plan, SHA-256
  `EE22C688167F5016D7ED1953BB1DAE516BC6AB343655A7D96535C6605D37E904`;
- `AI-REVIEW-PROCESS-001`, SHA-256
  `EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8`.

The current candidate evidence root remains
`78FA6A96D4193F53018ECFA7DFFAFFEBA3DA398A4E0116056C7C3BDDE8D2C482`.
This design does not claim that root is accepted or that Phase 0 is complete.
Phase 0 remains `BLOCKED_PENDING_POSTROOT_ACCEPTANCE`.

The following remain unauthorized by this design:

- either formal independent AI review run;
- review coverage publication;
- candidate-root reconstruction;
- creation of final candidate approval records;
- acceptance-index or final-result publication;
- Phase 0 `PASS`;
- Phase 0A or any later implementation phase;
- dependency, provider, broker, model-service, package-registry, remote Git, paper,
  or live access;
- mutation of any existing candidate or historical evidence root.

## 3. Problem statement

The approved review procedure defines review-run, review-output, and coverage
contracts in prose, but its `future_companion_suite` section deliberately left
the executable contract suite deferred. A qualifying integrity review cannot
begin until the following are separately approved and supplied as sanitized
governed inputs:

1. exact acceptance-index construction rules;
2. positive and adversarial acceptance-index fixtures;
3. closed schemas and vectors needed to validate review outputs, run records,
   coverage, approvals, the acceptance index, and the final result;
4. exact expected results and reason codes that make reproduction falsifiable.

Focused Phase 0 unit tests are not a substitute for this normative suite. The
suite must permit a fresh-context reviewer to test the future final-gate
contracts without receiving an authoring transcript, ungoverned evidence, or a
completed acceptance index.

## 4. Alternatives considered

### 4.1 Selected: one postroot canonical JSON suite

One exact-hash-approved JSON artifact contains all contract declarations and
test vectors. This minimizes approval ambiguity, prevents incomplete fixture
selection, and preserves the current candidate evidence root.

### 4.2 Rejected: manifest plus separate schema and fixture files

Multiple files are easier to edit independently, but require a second manifest,
multiple exact hashes, transitive completeness checks, and more opportunities to
supply a reviewer with only part of the approved suite.

### 4.3 Rejected: add the suite to the preapproval candidate root

This would bind the suite directly into a rebuilt candidate, but would invalidate
the current root and require the candidate evidence workflow to be repeated
before review. The approved procedure permits separately approved class-specific
review inputs, so that cost is unnecessary.

## 5. Artifact model

### 5.1 Contract suite

The intended governed path is:

`docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json`

The intended logical ID is:

`phase0.postroot_acceptance_contract_suite`

The suite is candidate-neutral. It binds the procedure ID and procedure hash but
does not hard-code a candidate root. Each review-run record separately binds the
exact suite hash and candidate root in `input_artifact_hashes` and
`candidate_evidence_root`.

The suite must contain no self-hash. Before exact-hash approval its effectivity
state is `PENDING_EXACT_HASH_PRINCIPAL_APPROVAL`.

### 5.2 Suite approval record

The intended governed path is:

`docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite-approval.json`

The intended logical ID is:

`phase0.postroot_acceptance_contract_suite.approval`

This sanitized record captures the later attributable principal approval of the
exact suite bytes. It contains:

- `approval_record_id`;
- `approved_at`;
- `approved_by_principal_id`;
- `approved_capacities`;
- `approved_logical_id`;
- `approved_sha256`;
- `approval_scope`;
- `procedure_id`;
- `procedure_sha256`;
- `status`.

`approval_record_id` is the uppercase SHA-256 of canonical record bytes with
only `approval_record_id` omitted. The record is valid only when the principal
has approved the exact suite hash after inspecting the complete unchanged file.
The suite file cannot prove its own approval.

Suite approval is distinct from the later exact-candidate-root approvals in
`phase0.approval_records`. It cannot approve a candidate, a review, an index, a
final result, or Phase 0.

### 5.3 Acceptance-index membership

The completed acceptance index later maps both suite artifacts in addition to:

- every member in the exact candidate-root tuple array;
- `phase0.candidate_evidence_root`;
- `phase0.ai_review_runs`;
- `phase0.ai_review_coverage`;
- `phase0.approval_records`.

`phase0.acceptance_index` and `phase0.final_acceptance_result` are never ordinary
index members. The suite and its approval are postroot inputs and do not become
members of the existing candidate evidence root.

## 6. Canonical data profiles

### 6.1 Canonical JSON

All suite objects, embedded structured values, expected derived objects, and
future governed results use `PHASE0-CANONICAL-JSON-1.0.0`:

- UTF-8 without BOM;
- Unicode NFC strings;
- recursively sorted object keys;
- no duplicate object keys;
- no insignificant whitespace;
- no trailing newline;
- lowercase JSON literals;
- signed base-10 integers only, with no decimals, exponents, leading plus,
  leading zeroes, or negative zero;
- set-valued arrays deduplicated and sorted by their declared identity rule;
- sequence arrays preserved only where the contract explicitly declares order
  meaningful.

### 6.2 Closed contract dialect

The suite uses a self-contained dialect named
`PHASE0-CLOSED-CONTRACT-1.0.0`. It does not reference a remote metaschema or
require a third-party schema library.

Each contract declaration contains exactly:

- `additional_properties` with the required value `REJECT`;
- `contract_id`;
- `field_rules`;
- `required_fields`;
- `schema_version`;
- `validation_rules`.

Each field rule declares:

- field name;
- primitive or compound type;
- required format, enumeration, range, or identity constraints;
- array ordering and uniqueness semantics when applicable;
- nested required fields for compound values.

No implicit optional fields or extension fields are permitted in version 1.0.0.
Any later field addition creates a new contract version and suite revision.

## 7. Suite top-level contract

The suite top-level object contains exactly:

- `acknowledgements`;
- `artifact_type`;
- `authority_bindings`;
- `canonical_encoding_profile`;
- `closed_contract_profile`;
- `contract_schemas`;
- `documented_on`;
- `effectivity`;
- `fixture_catalog`;
- `logical_id`;
- `non_authorizations`;
- `reason_code_registry`;
- `schema_version`;
- `suite_scope`;
- `supersession`;
- `validation_order`.

`artifact_type` is `PHASE0_POSTROOT_ACCEPTANCE_CONTRACT_SUITE`.
`schema_version` is `1.0.0`. `contract_schemas` and `fixture_catalog` are sorted
by their stable identities. Authority bindings include the procedure and the
controlling plan by logical ID and exact hash.

## 8. Required contract schemas

### 8.1 Independent review output

The suite restates the procedure's closed review-output contract without
weakening it. Required fields are:

- `candidate_evidence_root`;
- `coverage_assertion_ids`;
- `coverage_logical_ids`;
- `findings`;
- `limitations`;
- `recommended_candidate_outcome`;
- `reproduction_results`;
- `review_class`;
- `summary`.

The output has no `review_output_hash` field. That hash is computed over the
exact canonical output bytes.

### 8.2 Independent review-run record

The suite restates every required field and nested shape in
`AI-REVIEW-PROCESS-001`, including:

- exact procedure, specification, plan, configuration, registry, assertion-run,
  candidate-root, input-artifact, and output hashes;
- model-service and declared-version disclosure;
- runtime and tool version disclosure;
- eligibility, isolation, disqualification, terminal-state, and qualification
  fields;
- findings, reproductions, coverage arrays, and recommended outcome;
- exact timestamps and `review_run_id` derivation.

`review_run_id` is computed from canonical run-record bytes with only that field
omitted. A mismatch is invalid evidence and cannot be treated as an absent run.

### 8.3 Review coverage result

The coverage contract preserves the procedure's exact qualification rules:

- exactly two distinct selected qualifying run IDs;
- exactly one run per declared review class;
- exact procedure, candidate-root, registry, and assertion-run binding;
- complete candidate logical-ID union;
- complete active mandatory assertion-ID union;
- no extra IDs;
- no duplicate semantic identities;
- all eight isolation checks `PASS` for each selected run;
- no invalid selected-run reason and no disqualification code.

Missing required class runs with no selected invalid record produce `BLOCKED`.
Any selected malformed, duplicated, mismatched, extra, or nonqualifying record
produces `INVALID`. Only the full predicate produces `QUALIFIED`.

The coverage result retains the procedure's exact field set. It does not add a
suite field. Instead, coverage validation requires the selected integrity run's
existing `input_artifact_hashes` array to contain the exact suite and
suite-approval logical IDs and hashes. This preserves the approved coverage
schema while making suite use independently verifiable.

### 8.4 Preapproval reviewer-eligibility result

The suite restates the exact closed contract for
`phase0.gov_002_preapproval_reviewer_eligibility` without changing the approved
record. It validates the six required check identities, check order, count
consistency, allowed reason codes, authority bindings, zero-violation `ELIGIBLE`
predicate, effectivity fields, and prohibition on postroot evidence as an input
to GOV-002.

Fixtures distinguish a valid zero-violation result, unavailable required
preapproval evidence (`BLOCKED`), an established eligibility violation
(`INELIGIBLE`), and demonstrably invalid record identity, count, hash, or
evidence references (`FAIL` in the consuming gate).

### 8.5 Suite approval record

The suite approval schema enforces the fields and identity rule in Section 5.2.
It permits only `APPROVED` or `REVOKED` status. `APPROVED` requires the exact
suite logical ID, exact suite hash, exact procedure ID/hash, the acknowledged
principal identity, all declared approval capacities, and a canonical timestamp.

### 8.6 Candidate approval bundle

`phase0.approval_records` is a closed object containing:

- exact candidate root, plan, specification, procedure, suite, registry, and
  assertion-run hashes;
- a sorted set of attributable approval records;
- the exact required owner and approver capacities;
- observed, missing, extra, and duplicate capacities;
- aggregate approval status and reason codes.

Missing required approvals produce `BLOCKED`. A selected approval with an
invalid identity, hash, principal, capacity, timestamp, or candidate binding
produces `FAIL`. Approvals cannot change an assertion or review outcome.

### 8.7 Acceptance index

The acceptance index top-level object contains exactly:

- `candidate_evidence_root`;
- `index_members`;
- `index_sha256`;
- `logical_id`;
- `procedure_id_and_hash`;
- `root_hash`;
- `root_id`;
- `schema_version`;
- `suite_id_and_hash`.

Each `index_members` row contains exactly:

- `byte_length`;
- `logical_id`;
- `media_type`;
- `member_sha256`;
- `repository_relative_path`;
- `root_id`.

Rows are sorted lexicographically by `logical_id`, then
`repository_relative_path`. Each logical ID appears exactly once. Every path is
normalized, repository-relative, nonempty, nonescaping, nonabsolute, and maps to
exactly one regular file under the opaque registered `root_id`. Symlinks and
reparse-point escapes are rejected.

The expected index logical-ID set is the exact set union of:

1. logical IDs from the candidate-root tuple array;
2. `phase0.candidate_evidence_root`;
3. `phase0.postroot_acceptance_contract_suite`;
4. `phase0.postroot_acceptance_contract_suite.approval`;
5. `phase0.ai_review_runs`;
6. `phase0.ai_review_coverage`;
7. `phase0.approval_records`.

No other logical ID is allowed in schema version 1.0.0.

### 8.8 Final acceptance result

The final result contains exactly:

- `assertion_aggregate_status`;
- `candidate_evidence_root`;
- `completed_at`;
- `final_result_id`;
- `index_sha256`;
- `logical_id`;
- `outcome`;
- `reason_codes`;
- `review_coverage_status`;
- `root_hash`;
- `schema_version`;
- `suite_sha256`.

`final_result_id` is the uppercase SHA-256 of canonical final-result bytes with
only `final_result_id` omitted. Its `logical_id` is
`phase0.final_acceptance_result`.

## 9. Deterministic acceptance-index construction

The constructor applies the following exact sequence:

1. Strictly parse and validate the procedure, suite, suite approval, candidate
   root, candidate members, review bundle, coverage result, and candidate
   approval bundle.
2. Recompute the candidate evidence root from its exact ordered tuple array.
3. Verify every candidate tuple member's logical ID, byte length, media type, and
   SHA-256.
4. Verify exactly two qualifying review records and their output hashes.
5. Recompute the coverage result and require its stored fields to equal the
   recomputed fields.
6. Verify the suite approval and every required candidate approval.
7. Construct the exact index member set in Section 8.7.
8. Resolve and hash each mapped file without following an escaping symlink or
   reparse point.
9. Construct the provisional index object without `index_sha256` or `root_hash`.
10. Compute `index_sha256` as the uppercase SHA-256 of the provisional canonical
    bytes.
11. Construct `root_hash_input` as exactly:

    ```json
    {
      "index_sha256": "<64-uppercase-hex>",
      "ordered_member_pairs": [
        ["<logical_id>", "<member_sha256>"]
      ]
    }
    ```

    `ordered_member_pairs` is sorted lexicographically by logical ID, then member
    SHA-256.
12. Compute `root_hash` as the uppercase SHA-256 of canonical
    `root_hash_input` bytes.
13. Insert `index_sha256` and `root_hash` into the final index object.
14. Recompute both values from the final object using the same omission rules and
    require exact equality.

The index never hashes bytes that already contain their own derived hash. It
never maps itself or the final result as an ordinary member.

## 10. Final-gate derivation

The final gate validates all inputs before applying outcome precedence:

```text
if the assertion aggregate is FAIL:
    outcome = FAIL
else if any selected approval, review, coverage item, hash, identity,
        suite binding, index field, or final-result field is invalid:
    outcome = FAIL
else if the assertion aggregate is BLOCKED:
    outcome = BLOCKED
else if a required approval, qualifying review, coverage item, suite input,
        index member, or governed input is absent:
    outcome = BLOCKED
else:
    outcome = PASS
```

Demonstrable invalidity takes precedence over absence. An absent required record
is `BLOCKED`; a present selected malformed record is `FAIL`. A material open
review finding or a qualifying review recommendation of `BLOCKED` blocks the
gate. A qualifying review recommendation of `FAIL` fails the gate. Approval
cannot waive either outcome.

The final result is derived only after the completed index has verified. It is
not added back to the index.

## 11. Validation order and diagnostics

Validation phases are fixed:

1. `BYTE_AND_JSON`;
2. `CLOSED_SCHEMA`;
3. `IDENTITY_AND_HASH`;
4. `CROSS_ARTIFACT_AND_COVERAGE`;
5. `ACCEPTANCE_INDEX`;
6. `FINAL_OUTCOME`.

A byte or strict-JSON failure terminates interpretation of that artifact because
later fields cannot be trusted. Otherwise the validator accumulates every
independently evaluable violation, deduplicates reason codes, and sorts them
lexicographically. It does not invent downstream failures for values that cannot
be computed safely.

The suite's reason-code registry groups codes by prefix:

- `BYTE-` for encoding, BOM, trailing bytes, and canonical-byte violations;
- `JSON-` for parse and duplicate-key failures;
- `SCHEMA-` for closed-shape, type, enum, format, and ordering violations;
- `ID-` for logical, run, result, approval, and semantic identity failures;
- `HASH-` for content, input, output, and derived-hash mismatches;
- `REF-` for unresolved or contradictory cross-artifact references;
- `REVIEW-` for review qualification, class, isolation, and outcome failures;
- `COVERAGE-` for union, selection, duplicate, missing, and extra-ID failures;
- `APPROVAL-` for attribution, capacity, scope, effectivity, and root-binding
  failures;
- `INDEX-` for membership, path, self-reference, index hash, and root hash
  failures;
- `GATE-` for final outcome and precedence mismatches.

Every registry entry contains one exact semantic condition and one exact gate
effect. The implemented suite must contain at least one adversarial fixture for
every reason code.

## 12. Fixture model

Each fixture contains exactly:

- `expected_derived_values`;
- `expected_reason_codes`;
- `expected_status`;
- `fixture_id`;
- `input_artifacts`;
- `invariant_under_test`;
- `target_contract_id`;
- `validation_phase`.

Fixture input artifacts are fully synthetic exact UTF-8 JSON text stored as JSON
strings. This permits representation of duplicate object keys, BOMs, trailing
newlines, noncanonical whitespace, and malformed JSON. No fixture contains a
credential, account identifier, sensitive path, real conversation content,
provider identifier, broker identifier, market data, trade data, or donor data.

`expected_status` is one of `PASS`, `BLOCKED`, `FAIL`, `QUALIFIED`, `INVALID`,
or `REJECTED`, restricted by the target contract. `expected_reason_codes` is a
sorted unique array. `expected_derived_values` contains exact hashes and IDs
when computable and an exact `NOT_COMPUTABLE` sentinel otherwise.

## 13. Minimum fixture catalog

The implemented suite must include:

### 13.1 Canonical and schema fixtures

- one golden instance for every contract;
- duplicate key;
- UTF-8 BOM;
- trailing newline and trailing non-whitespace bytes;
- noncanonical object-key order;
- undeclared field;
- missing required field;
- wrong primitive or compound type;
- invalid enum, timestamp, integer, and uppercase SHA-256 formats;
- unsorted or duplicate set array.

### 13.2 Preapproval reviewer-eligibility fixtures

- valid six-check, zero-violation `ELIGIBLE` result;
- unavailable required authority producing `BLOCKED`;
- each check-scoped violation producing `INELIGIBLE`;
- missing, extra, duplicated, or misordered check identity;
- inconsistent pass, block, fail, required, or violation counts;
- malformed or unresolved authority and evidence reference;
- false use of review, coverage, approval, index, or final-result evidence as a
  preapproval input.

### 13.3 Review-run and coverage fixtures

- two qualifying isolated classes with complete union;
- one missing review class;
- duplicate review-run identity;
- more than two selected identities;
- invalid or duplicated class assignment;
- inherited authoring context violation;
- undeclared tool or external-access violation;
- governed-subject mutation violation;
- wrong candidate, suite, procedure, registry, run, or output hash;
- missing and extra logical or assertion IDs;
- failed isolation check;
- disqualification code omission or mismatch;
- deterministic recommendation/outcome mismatch.

### 13.4 Approval fixtures

- valid suite exact-hash approval;
- valid complete candidate approval bundle;
- missing required capacity;
- extra or duplicate capacity;
- wrong principal identity;
- wrong candidate, suite, procedure, plan, specification, registry, or run hash;
- invalid approval-record identity;
- revoked or not-yet-effective approval;
- approval attempting to waive `BLOCKED` or `FAIL`.

### 13.5 Acceptance-index fixtures

- complete golden index and exact derived hashes;
- missing or extra member;
- duplicate logical ID;
- duplicate or multiply mapped path;
- absolute, escaping, or nonnormalized path;
- wrong opaque root ID;
- symlink or reparse escape declaration;
- wrong media type, byte length, or member hash;
- candidate-root tuple mismatch;
- suite or suite-approval omission;
- index self-membership;
- final-result membership;
- wrong index omission boundary;
- wrong pair ordering;
- wrong `index_sha256`;
- wrong `root_hash`.

### 13.6 Final-gate fixtures

- fully valid `PASS`;
- valid `BLOCKED` caused by truly absent required evidence;
- valid `FAIL` caused by contradictory mandatory evidence;
- selected malformed record causing `FAIL` rather than `BLOCKED`;
- simultaneous fail and blocked conditions proving `FAIL` precedence;
- blocked assertion aggregate with otherwise complete evidence;
- review `BLOCKED` and review `FAIL` propagation;
- invalid index with otherwise passing inputs;
- incorrect stored final outcome;
- incorrect `final_result_id`.

## 14. Review input flow

The integrity review receives only:

1. the exact approved procedure and hash;
2. the exact candidate-root manifest and sanitized candidate bundle;
3. the exact suite and hash;
4. the exact suite-approval record;
5. the class-specific integrity-review instruction that names these exact
   inputs;
6. declared read-only local tools and version manifests.

The review independently verifies all hashes before substantive work. It tests
the suite's index rules and fixtures without constructing the completed
candidate acceptance index or claiming peer-review, coverage, candidate
approval, or final-result existence.

The adversarial conformance review may receive the suite only when its assigned
instructions require it. Neither run receives the project-authoring transcript,
the other run's context, credentials, sensitive paths, excluded evidence, or an
instruction permitting mutation.

## 15. Lifecycle and invalidation

The lifecycle is:

1. approve this written design for planning;
2. create an implementation plan limited to suite and offline validation work;
3. implement the suite and local tests without creating formal review evidence;
4. validate canonical bytes, contracts, fixtures, hashes, sanitization, and
   repository cleanliness;
5. present the complete suite and exact hash for principal review;
6. after explicit exact-hash approval, create and validate the sanitized suite
   approval record;
7. recheck every review prerequisite;
8. initialize exactly two fresh-context, read-only review runs;
9. follow the existing procedure-authorized order for coverage, candidate
   approval, acceptance index, and final result.

Changing any suite byte creates a new revision and requires a new suite hash and
approval. Changing an existing candidate-root member requires a new candidate
root and two new reviews. Earlier roots, suites, approvals, reviews, and coverage
remain immutable historical evidence.

## 16. Verification strategy for later implementation

Later implementation uses only the Python standard library and existing Phase 0
canonical JSON utilities. It must not add a dependency or contact a registry.

Required tests include:

- strict parsing of the suite and every embedded fixture input;
- closed-contract validation for every declared schema;
- one-to-one equality between reason codes and adversarial fixture coverage;
- deterministic fixture result reproduction across two executions;
- exact candidate-neutrality checks prohibiting a candidate root in top-level
  suite authority or scope fields while permitting synthetic candidate roots
  inside embedded fixture inputs;
- suite and suite-approval exclusion from preapproval candidate inputs;
- exact acceptance-index and root-hash golden vectors;
- final-result identity and precedence golden vectors;
- sanitization scans over suite and fixture contents;
- LF-only tracked bytes and zero working-tree CRLF/mixed entries for newly
  created files;
- clean repository and unchanged historical evidence-root checks.

The implementation must fail closed on an unknown contract ID, fixture target,
reason code, field, status, or validation phase.

## 17. Success criteria

This design is successfully implemented only when:

1. one canonical suite artifact exists at the intended postroot path;
2. its exact hash is reproducible and its canonical form validates;
3. every required contract is closed and unambiguous;
4. every registered reason code has at least one adversarial fixture;
5. all golden and adversarial expected results reproduce deterministically;
6. the suite contains no candidate-specific value or prohibited sensitive data;
7. the suite and approval are absent from the existing candidate-root tuple
   array and existing evidence roots remain unchanged;
8. no formal review or acceptance artifact is falsely claimed;
9. the complete unchanged suite is ready for attributable exact-hash principal
   approval;
10. after that approval, the integrity-review prerequisite can be re-evaluated
    without weakening `AI-REVIEW-PROCESS-001`.

## 18. Handoff to planning

After the user reviews and approves this written specification, the next step is
a separate implementation plan. That plan may define the suite construction,
offline validator, tests, approval checkpoint, and final review-prerequisite
check. It must not authorize or combine the two independent review runs with
suite implementation.
