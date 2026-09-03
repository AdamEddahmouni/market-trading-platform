# Formal AI Review Run — ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT

You are an independent read-only reviewer under AI-REVIEW-PROCESS-001. This is a fresh isolated context. You did not author the governed subject. You have no prior project-authoring transcript. You are not the peer INTEGRITY_AND_REPRODUCTION_AUDIT.

## Isolation declaration

- Review class: ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT
- Procedure: AI-REVIEW-PROCESS-001
- Procedure SHA-256: EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8
- Repository: C:\Users\adame\Desktop\market-trading-platform\integrated-market-platform
- Workspace commit for read-only inspection: 67c78d6
- Candidate evidence run_id: DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66
- Candidate evidence root: 78FA6A96D4193F53018ECFA7DFFAFFEBA3DA398A4E0116056C7C3BDDE8D2C482
- Candidate-root manifest SHA-256: 5574FF6FF83226423D3A17E27426730178AA0E8CE03A87C15622233DDEAC24D1
- Member count: 40

## Hard constraints

- Read-only: do not modify any file under the governed subject, evidence bundle, or manifests.
- No network, provider, broker, package registry, or remote Git access.
- No credential values, account identifiers, or sensitive paths in outputs.
- Do not claim Phase 0 PASS, coverage qualification, acceptance index, or final result.
- Do not claim the peer integrity review exists or qualifies.
- Postroot suite artifacts are outside this class's required inputs; do not require them.

## Step 1 — Verify permitted input hashes before substantive review

Independently recompute SHA-256 for every input you consume. Stop with DISQUALIFIED (DISQ-HASH-OR-IDENTITY-MISMATCH) on any mismatch.

### Primary governed inputs

| logical_id | path | expected SHA-256 |
|------------|------|------------------|
| phase0.ai_review_procedure | docs/superpowers/governance/2026-08-14-ai-review-process-001.json | EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8 |
| phase0.candidate_evidence_root | evidence/phase0/DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66/candidate-evidence-root.json | 5574FF6FF83226423D3A17E27426730178AA0E8CE03A87C15622233DDEAC24D1 |
| phase0.assertion_run_manifest | evidence/phase0/DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66/assertion-run-manifest.json | 66074C7AA5D52B0D782D9604456D3E01487B7E6B69A9B95377C7954D188EA154 |
| phase0.assertion_registry | evidence/phase0/DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66/assertion-registry.json | 80286553F6E2124DDC998CA7FB94B53518E644F79B93712C34D3D38CCF1C3097 |
| phase0.gov_002_preapproval_reviewer_eligibility | docs/superpowers/governance/2026-08-14-gov-002-preapproval-reviewer-eligibility.json | 5686F548A495E9DC215474083EBC6775C921D5B7AD8E6DB98EF132DDC27C4EE4 |
| phase0.governance_plan | docs/superpowers/plans/2026-08-13-phase-0-governance-and-no-live-safety.md | EE22C688167F5016D7ED1953BB1DAE516BC6AB343655A7D96535C6605D37E904 |

### Candidate bundle directory (sanitized 40-member evidence)

`evidence/phase0/DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66/`

Verify every file named in `candidate-evidence-root.json` `ordered_member_tuples` matches its declared `member_sha256` and `byte_length`. Confirm these logical IDs are **absent** from the tuple array:

- phase0.postroot_acceptance_contract_suite
- phase0.postroot_acceptance_contract_suite.approval
- phase0.ai_review_runs
- phase0.ai_review_coverage
- phase0.acceptance_index
- phase0.final_acceptance_result
- phase0.approval_records
- phase0.candidate_evidence_root

## Step 2 — Eligibility check

Evaluate AI-REVIEW-PROCESS-001 `disqualification_rules`. Record `eligibility_result` with `violation_count` and sorted `violations`. Proceed only if ELIGIBLE.

## Step 3 — Assigned minimum actions

Per `review_classes` ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT:

1. Trace every active mandatory assertion to exact evidence: GOV-001, GOV-002, GOV-003, GOV-004, SEC-001, SAFE-001, SAFE-002, SAFE-003-STATIC, SAFE-P0-001
2. Cross-check `assertion-results.json` and `assertion-aggregate.json` against `assertion_run_manifest` `assertion_observations`.
3. Test canonical-authority uniqueness, role resolution, approvals, scope exclusions, structural no-live claims, and secret-safe evidence boundaries.
4. Attempt to falsify every claimed PASS; record BLOCKED, FAIL, ambiguous, or unsupported conditions with materiality.
5. Verify documented exclusions are enforced and not hiding required evidence.
6. Recompute or independently check covered assertion predicates where read-only local tools permit (CPython 3.11 stdlib, `src/market_platform_foundation/`).

Useful read-only commands:

```powershell
cd C:\Users\adame\Desktop\market-trading-platform\integrated-market-platform
$env:PYTHONPATH='src;.'
python -m unittest discover -s tests/phase0 -v
```

Candidate subject commit recorded in assertion-run-manifest: `subject_git_commit = 55b09254b1720753f1f6bad2c5ac41ea9656bbac` (Evidence is frozen in the bundle; do not re-run the evidence pipeline.)

## Step 4 — Outcome derivation

Apply `finding_semantics` and `run_outcome_scope_rule`:

- FAIL if predicate contradiction or invalid approval/review/hash/identity/index
- else BLOCKED if required evidence absent or material OPEN findings remain
- else PASS

Record `recommended_candidate_outcome` independently. Do not infer peer-review or postroot acceptance state.

## Step 5 — Deliverables (write outside governed subject)

Write to an isolated directory (for example a new folder under `evidence/phase0/review-runs/` — never inside the candidate bundle):

### A. Review output (`phase0.ai_review_output.contract`)

Canonical JSON (PHASE0-CANONICAL-JSON-1.0.0): UTF-8, no BOM, no trailing newline. Required fields:

- `candidate_evidence_root`
- `coverage_assertion_ids` (sorted unique; only IDs you actually reviewed)
- `coverage_logical_ids` (sorted unique; only logical IDs you actually reviewed)
- `findings` (sorted by `finding_id`; each with `finding_status`, `finding_type`, `materiality`, `reason`, `recommended_resolution`, `evidence_refs`, affected IDs)
- `limitations` (sorted unique strings; empty array if none)
- `recommended_candidate_outcome` (PASS | BLOCKED | FAIL)
- `reproduction_results` (sorted by `reproduction_id`)
- `review_class`: ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT
- `summary` (non-empty sanitized conclusion)

Compute `review_output_hash` = SHA-256 of canonical output bytes (hash field omitted).

### B. Review run record (`phase0.ai_review_run.contract`)

Include all required fields from AI-REVIEW-PROCESS-001 `review_run_record_contract`:

- `review_procedure_id_and_hash`: {procedure_id: AI-REVIEW-PROCESS-001, sha256: EAAA84B1...}
- `candidate_evidence_root`, `registry_hash`, `plan_hash`, `run_id`, `review_class`
- `input_artifact_hashes` (sorted by `logical_id`; every consumed input)
- `model_service_and_declared_version` (disclose exact model/service used)
- `runtime_and_tool_versions` (declare every tool/runtime component)
- `eligibility_result`, `findings`, `reproduction_results`, coverage arrays
- `recommended_candidate_outcome`, `review_output_hash`
- `terminal_state`: COMPLETE | DISQUALIFIED | FAILED
- `qualification_state`: QUALIFYING only if COMPLETE and no disqualification
- `disqualification_reason_codes` (empty unless DISQUALIFIED)
- `started_at`, `completed_at` (canonical timestamps)
- `canonical_configuration_hash`

Compute `review_run_id` = SHA-256 of canonical run-record bytes with only `review_run_id` omitted.

## Step 6 — Self-validation

- Recompute `review_output_hash` and `review_run_id`
- Confirm run record fields match hashed review output where required
- Confirm no credential/sensitive data in outputs
- Report: `terminal_state`, `recommended_candidate_outcome`, finding count, `review_run_id`, `review_output_hash`, and path to written artifacts

Do not publish artifacts as formal evidence until separately validated by the principal. Do not claim Phase 0 PASS.
