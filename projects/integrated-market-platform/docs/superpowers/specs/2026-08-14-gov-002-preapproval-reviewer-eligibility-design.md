# GOV-002 Preapproval Reviewer-Eligibility Result Design

**Document status:** Written specification pending principal review  
**Documented on:** 2026-08-14  
**Scope:** Documentation and governance design only  
**Designed logical artifact:** `phase0.preapproval_reviewer_eligibility`  

## 1. Decision summary

GOV-002 requires a zero-violation preapproval reviewer-eligibility result in
addition to the effective sole-principal role assignment and the approved
`AI-REVIEW-PROCESS-001` procedure. This specification defines that future
result as one standalone, human-reviewable JSON artifact.

The result will:

- bind the exact approved role-assignment and AI-review-procedure bytes;
- evaluate exactly the six preapproval checks already declared by
  `AI-REVIEW-PROCESS-001`;
- distinguish demonstrated ineligibility from missing evidence;
- become effective only through external exact-hash principal approval; and
- remain separate from postroot AI review runs, review coverage, approval
  records, the candidate-root manifest, and final acceptance evidence.

This design does not create the result, execute its checks, claim that GOV-002
passes, begin Phase 0, authorize implementation, or authorize the deferred JSON
schema, fixture, or test-vector suite.

## 2. Chosen approach and rejected alternatives

### 2.1 Chosen: standalone exact-hash-approved JSON result

The result is a compact single JSON document in `docs/superpowers/governance`.
It contains explicit authority bindings, six check results, a deterministic
aggregate, effectivity rules, and non-authorizations. The principal reviews and
approves its exact bytes after validation.

This approach is selected because it is auditable with the current
documentation-only authority, preserves evidence isolation, and requires no
executable verifier.

### 2.2 Rejected: verifier-only generated result

A governed verifier could eventually produce the result, but no verifier
implementation or executable-evidence work is authorized. Requiring one now
would improperly turn this governance increment into implementation work.

### 2.3 Rejected: result embedded in the future GOV-002 assertion record

Embedding the eligibility determination in the assertion result would couple
the evidence used by GOV-002 to GOV-002's own evaluation record. A standalone
input is clearer, reusable by the later assertion evaluator, and less exposed to
circular or mixed-stage reasoning.

## 3. Governing authority and observed baseline

The following hashes were freshly verified before this written specification
was created:

| Authority | Exact SHA-256 | Evidence state |
|---|---|---|
| `docs/superpowers/specs/2026-08-13-integrated-market-platform-foundation-design.md` | `B4EAE3240F6F968A6B393263D849013259A00187E209C8632E38DE890996D04D` | Canonical foundation specification; implementation readiness remains blocked |
| `docs/superpowers/plans/2026-08-13-phase-0-governance-and-no-live-safety.md` | `EE22C688167F5016D7ED1953BB1DAE516BC6AB343655A7D96535C6605D37E904` | Exact written-plan baseline previously approved by the principal |
| `docs/superpowers/governance/2026-08-14-phase-0-role-assignment.json` | `37C24D60FF9ACB8411BA0D5FA5A2C5DBC8811DFD30E4180DD377A2C3BADA2163` | Effective through external conversational exact-hash principal approval |
| `docs/superpowers/governance/2026-08-14-ai-review-process-001.json` | `EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8` | Effective through external conversational exact-hash principal approval |

The role assignment and procedure retain preapproval-era status text inside
their immutable approved bytes. Their effectivity is established by the
external attributable approval evidence, not by rewriting the approved files.
This specification does not create or claim a formal
`phase0.approval_records` artifact.

If any bound hash differs when the result is later prepared, preparation must
stop. The changed bytes must be identified and their authority and approval
state re-established before a result can be produced or approved.

## 4. Artifact identity and location

The future result has these fixed identity properties:

| Property | Required value |
|---|---|
| Logical ID | `phase0.preapproval_reviewer_eligibility` |
| Artifact type | `PREAPPROVAL_REVIEWER_ELIGIBILITY_RESULT` |
| Schema version | `1.0.0` |
| Relative path | `docs/superpowers/governance/2026-08-14-gov-002-preapproval-reviewer-eligibility.json` |
| Media type | `application/json` |
| Phase | `PHASE_0_PREAPPROVAL` |
| Human principal | `PROJECT-PRINCIPAL-001` |

The artifact is a GOV-002 evidence input. It is not a qualifying AI review-run
record, AI review coverage result, human approval record, assertion result,
candidate-root manifest, acceptance index, or final acceptance result.

Once effective, it is eligible for later inclusion among preapproval
candidate-root members. This design neither constructs a candidate root nor
claims that candidate-root construction is authorized.

## 5. Serialization boundary

The result uses a human-reviewable governance-document JSON profile rather than
the minified review-run profile defined inside `AI-REVIEW-PROCESS-001`.

Required byte rules are:

- UTF-8 without a byte-order mark;
- LF line endings only;
- one JSON object followed by exactly one trailing LF;
- two-space indentation;
- every object key recursively sorted by ascending Unicode code point;
- no duplicate object keys;
- lowercase JSON booleans and `null`;
- base-10 non-negative integers for counts;
- Unicode NFC strings;
- no insignificant trailing whitespace; and
- arrays ordered by the field-specific rules in this specification.

The file does not contain its own SHA-256. Its external approval evidence binds
the logical ID and the SHA-256 computed over the complete exact byte sequence.

## 6. Top-level contract

The result contains exactly these top-level members, in recursively sorted key
order:

1. `acknowledgements`
2. `artifact_type`
3. `authority_bindings`
4. `check_results`
5. `documented_on`
6. `effectivity`
7. `eligibility_determination`
8. `governance_effect`
9. `logical_id`
10. `non_authorizations`
11. `record_status`
12. `schema_version`
13. `supersession`
14. `validation_contract`

Additional top-level members are invalid in version `1.0.0`.

### 6.1 `acknowledgements`

This is an array ordered by `acknowledgement_id`. It must state at least that:

- the artifact evaluates documentary preapproval eligibility only;
- preparing or approving it is not a qualifying independent AI review;
- it does not claim that a candidate root or postroot evidence exists;
- an `ELIGIBLE` determination is necessary but not sufficient for GOV-002 to
  pass; and
- neither GOV-002 eligibility nor GOV-002 PASS authorizes implementation or
  Phase 0 execution.

Each item contains exactly `acknowledgement_id` and `statement`.

### 6.2 `authority_bindings`

This array contains exactly four entries, sorted by `logical_id`:

- `foundation.canonical_specification`
- `phase0.ai_review_procedure`
- `phase0.governance_plan`
- `phase0.role_assignment`

Each entry contains exactly:

- `approval_basis`;
- `effectivity_state`;
- `logical_id`;
- `logical_path`; and
- `sha256`.

Paths are workspace-relative logical paths. No absolute path, credential value,
account identifier, external conversation transcript, or reversible sensitive
path mapping is embedded.

The role assignment and procedure must use the exact hashes in Section 3 and
must state that their effectivity comes from external conversational exact-hash
principal approval. The plan must identify its exact written-plan approval. The
specification must retain its implementation-readiness-blocked status.

### 6.3 `check_results`

This array contains exactly one item for each check ID in Section 7, in the exact
order listed there. Each item contains exactly:

- `check_id`;
- `evidence_refs`;
- `expected_condition`;
- `observed_condition`;
- `reason_codes`; and
- `status`.

`evidence_refs` is a sorted unique array of logical-ID-plus-JSON-Pointer strings
or logical-ID-plus-section-locator strings. It contains only references that
resolve within the four exact authority bindings. `reason_codes` is a sorted
unique array.

Allowed check statuses are:

- `PASS`: the expected condition is demonstrated by the bound evidence;
- `FAIL`: the bound evidence demonstrates a violation; and
- `BLOCKED`: evidence needed to decide the check is absent, unreadable,
  mismatched, ambiguous, or not effective.

A `PASS` item has an empty `reason_codes` array. A `FAIL` or `BLOCKED` item has
one or more applicable reason codes. Unknown statuses and unknown reason codes
make the artifact invalid.

### 6.4 `documented_on`

This is the calendar date on which the result bytes are prepared, formatted
`YYYY-MM-DD`. It is provenance only and does not determine authority,
effectivity, check status, or approval time.

### 6.5 `effectivity`

Before external approval, the immutable result must declare:

- activation requires explicit principal approval of the complete file by exact
  SHA-256;
- `approval_event_state` is `NOT_YET_OCCURRED_OR_RECORDED`;
- `current_effectivity` is `PENDING_EXACT_HASH_PRINCIPAL_APPROVAL`;
- approval must bind `logical_id` and `sha256`;
- effectivity begins at the timestamp in the external exact-hash approval
  evidence; and
- any byte change requires a new hash and new approval.

The result is not edited after approval merely to update these embedded fields.
External attributable approval evidence establishes effectivity. This avoids a
self-referential approval cycle and preserves the approved bytes.

### 6.6 `eligibility_determination`

This object contains exactly:

- `blocked_check_count`;
- `failed_check_count`;
- `passed_check_count`;
- `required_check_count`;
- `status`;
- `violation_count`; and
- `violations`.

`required_check_count` equals `6`. The three check counts equal the numbers of
`BLOCKED`, `FAIL`, and `PASS` items and sum to six.

Allowed aggregate statuses are:

- `ELIGIBLE`;
- `INELIGIBLE`; and
- `BLOCKED`.

The deterministic precedence is:

```text
if failed_check_count > 0:                     status = INELIGIBLE
else if blocked_check_count > 0:               status = BLOCKED
else if passed_check_count = 6
     and violation_count = 0:                  status = ELIGIBLE
else:                                          artifact is invalid
```

Each demonstrated violation produces one `violations` item containing exactly:

- `check_id`;
- `evidence_refs`;
- `reason_code`; and
- `rule_ref`.

The array is sorted by `check_id`, then `reason_code`, then `rule_ref`.
`violation_count` equals its length. Every violation must correspond to a
`FAIL` check; `PASS` and `BLOCKED` checks do not create violation items.

An invalid artifact has no usable eligibility determination. It cannot be
treated as `ELIGIBLE`; GOV-002 remains blocked.

### 6.7 `governance_effect`

This object must state that:

- GOV-002 is blocked before an effective, valid, `ELIGIBLE`, zero-violation
  result exists;
- an effective eligible result permits GOV-002 to be reevaluated against all of
  its required evidence;
- the result does not by itself emit or replace the future GOV-002 assertion
  result;
- qualifying AI review runs and coverage remain postroot final-gate evidence;
  and
- the artifact creates no implementation or execution authority.

### 6.8 `non_authorizations`

This sorted unique array contains at least:

- `ACCEPTANCE_INDEX_CREATION`
- `AI_REVIEW_RUN_EXECUTION`
- `CANDIDATE_ROOT_CONSTRUCTION`
- `DEFERRED_JSON_SCHEMA_FIXTURE_OR_TEST_VECTOR_SUITE`
- `FORMAL_APPROVAL_RECORD_CREATION`
- `GIT_OR_REPOSITORY_MUTATION`
- `GOV_002_PASS_CLAIM`
- `IMPLEMENTATION_PLANNING`
- `PHASE_0_EXECUTION`
- `PHASE_0_IMPLEMENTATION`
- `PHASE_0_PASS_CLAIM`
- `PHASE_0A_DATA_WORK`
- `PROVIDER_BROKER_OR_LIVE_MARKET_ACCESS`

The later result may add a non-authorization only through a new designed and
approved revision. It may not omit any listed value.

### 6.9 `record_status`

Before exact-hash approval this equals
`READY_FOR_EXACT_HASH_PRINCIPAL_REVIEW`. It is an as-authored lifecycle marker,
not proof that approval occurred.

### 6.10 `supersession`

This object contains:

- `revision_rule`;
- `superseded_by`; and
- `supersedes`.

The initial result uses `null` for `superseded_by` and an empty array for
`supersedes`. Any content change after effectivity creates a new immutable
revision with a new exact-hash approval. Earlier approved bytes remain
historical and cannot be silently replaced.

### 6.11 `validation_contract`

This object restates the serialization profile, exact required check-ID set,
aggregate recomputation rule, count-consistency rule, evidence-resolution rule,
hash-binding rule, and additional-property rejection rule. It contains no
executable code and does not constitute the deferred JSON schema or fixture
suite.

## 7. Required checks

The exact check order and mapping to the procedure's six required statements is:

### 7.1 `PREELIG-ROLE-RESOLUTION-001`

**Expected condition:** The effective role assignment resolves every required
human Phase 0 owner and approver capacity to `PROJECT-PRINCIPAL-001`, discloses
all overlaps, and does not imply additional human participants.

Allowed `FAIL` reason codes are exactly:

- `PRINCIPAL_ID_MISMATCH`
- `REQUIRED_HUMAN_CAPACITY_UNRESOLVED`
- `ROLE_OVERLAP_DISCLOSURE_INCOMPLETE`

### 7.2 `PREELIG-PROCEDURE-DESIGNATION-001`

**Expected condition:** The role assignment designates
`AI-REVIEW-PROCESS-001` and explicitly prevents principal self-review from
being represented as independent review.

Allowed `FAIL` reason codes are exactly:

- `INDEPENDENT_REVIEW_DESIGNATION_MISSING`
- `PROCEDURE_ID_DESIGNATION_MISMATCH`
- `SELF_REVIEW_MISREPRESENTED_AS_INDEPENDENT`

### 7.3 `PREELIG-PROCEDURE-APPROVAL-001`

**Expected condition:** The designated procedure ID resolves to
`AI-REVIEW-PROCESS-001`; its exact SHA-256 equals the approved hash in Section
3; and external attributable exact-hash principal approval exists.

Allowed `FAIL` reason codes are exactly:

- `PROCEDURE_APPROVAL_ABSENT`
- `PROCEDURE_HASH_MISMATCH`
- `PROCEDURE_ID_MISMATCH`

### 7.4 `PREELIG-REVIEW-CONTROLS-001`

**Expected condition:** The approved procedure requires two distinct fresh
contexts, read-only governed inputs, non-authoring eligibility, sanitized
evidence, complete coverage union, and exact candidate-root binding.

Allowed `FAIL` reason codes are exactly:

- `CANDIDATE_ROOT_BINDING_CONTROL_MISSING`
- `COVERAGE_UNION_CONTROL_MISSING`
- `FRESH_CONTEXT_CONTROL_MISSING`
- `NON_AUTHORING_CONTROL_MISSING`
- `READ_ONLY_CONTROL_MISSING`
- `SANITIZATION_CONTROL_MISSING`

### 7.5 `PREELIG-NONCIRCULARITY-001`

**Expected condition:** The approved procedure preserves the separation between
preapproval GOV-002 evidence and postroot review-run and coverage evidence.

Allowed `FAIL` reason codes are exactly:

- `POSTROOT_EVIDENCE_USED_FOR_PREAPPROVAL`
- `PREPOSTROOT_BOUNDARY_UNDEFINED`
- `REVIEW_EVIDENCE_LIFECYCLE_CIRCULAR`

### 7.6 `PREELIG-NO-FALSE-EVIDENCE-001`

**Expected condition:** The bound artifacts do not falsely claim that an actual
AI review run, review coverage result, formal approval record, candidate root,
acceptance index, or final result currently exists.

Allowed `FAIL` reason codes are exactly:

- `FALSE_ACCEPTANCE_INDEX_CLAIM`
- `FALSE_AI_REVIEW_COVERAGE_CLAIM`
- `FALSE_AI_REVIEW_RUN_CLAIM`
- `FALSE_CANDIDATE_ROOT_CLAIM`
- `FALSE_FINAL_RESULT_CLAIM`
- `FALSE_FORMAL_APPROVAL_RECORD_CLAIM`

For any check, `REQUIRED_EVIDENCE_UNAVAILABLE` is the generic `BLOCKED` reason
when the required bytes, approval evidence, or locator cannot be resolved. It is
not a demonstrated violation and must not appear in `violations`.

## 8. Evidence-reference rules

Every evidence reference must resolve to one of the four exact authority
bindings. JSON references use RFC 6901 JSON Pointers. Markdown references use a
stable section heading and the exact document hash.

The result must not:

- cite itself as evidence for any of its six checks;
- cite a future assertion result, candidate root, approval record, AI review
  run, coverage result, acceptance index, or final result;
- cite a mutable unhashed path as authority;
- embed external conversation text; or
- convert an approval assertion into a formal approval-record claim.

External approval evidence may establish the effectivity of the role assignment,
procedure, and later eligibility result without becoming a
`phase0.approval_records` artifact.

## 9. Preparation and approval lifecycle

The later result is prepared through this sequence:

1. Recompute the four authority hashes.
2. Stop on any mismatch and re-establish authority and approval state.
3. Read the exact approved role assignment and procedure without modifying them.
4. Evaluate all six checks and record one result per check.
5. Recompute counts, violations, and the aggregate status.
6. Validate JSON structure, duplicate-key rejection, key and array ordering,
   encoding, line endings, evidence references, and non-authorizations.
7. Compute the exact file SHA-256 and byte length.
8. Present the complete result and exact hash to `PROJECT-PRINCIPAL-001`.
9. Require explicit approval that names the logical ID and exact SHA-256.
10. Recompute the hash immediately before relying on the approval.
11. If it matches, treat the unchanged result as effective through the external
    approval evidence.
12. If it differs, stop and request approval for the new exact bytes.

No file is edited after exact-hash approval. No approval is inferred from design
approval, informal assent, approval of a different artifact, or approval of a
different hash.

## 10. GOV-002 transition rule

The following condition is necessary before GOV-002 may be reevaluated as a
candidate for PASS:

```text
role_assignment_effective
AND ai_review_procedure_effective
AND eligibility_result_effective
AND eligibility_result_valid
AND eligibility_result.status = ELIGIBLE
AND eligibility_result.violation_count = 0
```

Satisfying this condition does not itself publish a GOV-002 assertion result.
The later governed assertion evaluation must still resolve all required GOV-002
evidence in one selected evaluation run. An absent or invalid result leaves
GOV-002 `BLOCKED`; a demonstrated eligibility violation makes the eligibility
result `INELIGIBLE` and prevents GOV-002 PASS.

The result cannot use the qualifying postroot review runs or coverage map as
inputs. Those records remain required later at the final gate and cannot be
created before the candidate root exists.

## 11. Validation without the deferred suite

This increment deliberately defines no JSON Schema document, reusable fixture,
adversarial fixture, or test-vector suite. When the actual result is separately
authorized, one-off read-only validation may confirm:

- exact authority hashes;
- JSON parsing with duplicate-key rejection;
- exact top-level and nested field sets;
- recursive key ordering;
- exact six-check set and order;
- evidence-reference resolution;
- allowed statuses and reason codes;
- count and violation consistency;
- deterministic aggregate recomputation;
- required non-authorizations;
- UTF-8 without BOM and LF-only line endings; and
- exact SHA-256 and byte length.

The broader JSON schema, fixture, and test-vector suite remains deferred. If it
later becomes useful, it requires a separate design and explicit approval.

## 12. Failure handling

- **Authority hash mismatch:** stop; do not produce or approve a result against
  the mismatched bytes.
- **Approval evidence unavailable:** mark the affected check `BLOCKED` with
  `REQUIRED_EVIDENCE_UNAVAILABLE`; do not infer approval.
- **Demonstrated rule violation:** mark the affected check `FAIL`, emit the
  applicable violation item, and aggregate to `INELIGIBLE`.
- **Missing or duplicate check:** invalidate the artifact; GOV-002 remains
  blocked.
- **Unknown field, status, or reason code:** invalidate the artifact; GOV-002
  remains blocked.
- **Count or aggregate mismatch:** invalidate the artifact; do not trust the
  declared determination.
- **Post-approval byte change:** invalidate transfer of the earlier approval;
  compute and obtain approval for the new exact hash.
- **False current-state claim:** mark
  `PREELIG-NO-FALSE-EVIDENCE-001` as `FAIL` and aggregate to `INELIGIBLE`.

## 13. Explicit non-effects of this design

Approval of this written specification authorizes neither creation nor approval
of the designed result. A separate instruction is required to prepare that JSON
artifact.

Neither this specification nor the future eligibility result:

- amends the canonical foundation specification or Phase 0 plan;
- modifies the approved role assignment or AI-review procedure;
- clears GOV-001 or any gate other than permitting later GOV-002 reevaluation;
- begins Phase 0 or Phase 0A;
- authorizes application code, verifier code, dependency work, repository
  mutation, provider access, LFS retrieval, paper operation, or live trading;
- creates qualifying AI review runs or review coverage;
- creates a candidate root, approval record, assertion result, acceptance index,
  or final acceptance result; or
- approves the deferred JSON schema, fixture, or test-vector suite.

## 14. Acceptance criteria for the written specification

This specification is ready for principal review when:

- it preserves all four governing hashes exactly;
- it defines one standalone result without creating it;
- the result evaluates exactly six procedure-derived checks;
- `INELIGIBLE`, `BLOCKED`, and `ELIGIBLE` are deterministic and non-overlapping;
- the approval boundary is exact-hash and external;
- current preapproval and postroot evidence remain non-circular;
- GOV-002 and Phase 0 are not falsely reported as passing;
- the deferred suite remains deferred and unauthorized; and
- no unfinished marker, unresolved design choice, or implementation
  authorization is present.
