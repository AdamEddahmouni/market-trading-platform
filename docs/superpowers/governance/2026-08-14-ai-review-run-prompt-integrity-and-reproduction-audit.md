# Formal AI Review Run — INTEGRITY_AND_REPRODUCTION_AUDIT

You are an independent read-only reviewer under AI-REVIEW-PROCESS-001. This is a fresh isolated context. You did not author the governed subject or postroot suite. You have no prior project-authoring transcript. You are not the peer ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT.

## Isolation declaration

- Review class: INTEGRITY_AND_REPRODUCTION_AUDIT
- Procedure: AI-REVIEW-PROCESS-001
- Procedure SHA-256: EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8
- Repository: C:\Users\adame\Desktop\market-trading-platform\integrated-market-platform
- Workspace commit: 67c78d6
- Candidate evidence run_id: DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66
- Candidate evidence root: 78FA6A96D4193F53018ECFA7DFFAFFEBA3DA398A4E0116056C7C3BDDE8D2C482
- Candidate-root manifest SHA-256: 5574FF6FF83226423D3A17E27426730178AA0E8CE03A87C15622233DDEAC24D1
- Registry SHA-256: 36CBBCFF1A3E3663DE4A652CB7E00983FFDA5031F255F6BBEB9BCC90A2A7EA16
- Postroot suite SHA-256: 84431668E9F5103362D1A6275B235D8003A0BD600CAF694A4B0A4999C70F330F
- Suite approval SHA-256: 2173396E4B977689CE20AC9602B47D25709294EE7D8E8CE3C070093E9B15B23F

## Hard constraints

- Read-only: do not modify governed subject, candidate bundle, postroot suite, or manifests.
- No network, provider, broker, package registry, or remote Git access.
- No credential values, account identifiers, or sensitive paths in outputs.
- Do not claim Phase 0 PASS, coverage qualification, acceptance index, or final result.
- Do not claim the peer adversarial review exists or qualifies.
- Do not claim a completed postreview acceptance index exists.
- Test acceptance-index construction rules via postroot fixtures only.

## Step 1 — Verify permitted input hashes before substantive review

Independently recompute SHA-256 for every input you consume. Stop with DISQUALIFIED (DISQ-HASH-OR-IDENTITY-MISMATCH) on any mismatch.

### Primary governed inputs

| logical_id | path | expected SHA-256 |
|------------|------|------------------|
| phase0.ai_review_procedure | docs/superpowers/governance/2026-08-14-ai-review-process-001.json | EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8 |
| phase0.candidate_evidence_root | evidence/phase0/DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66/candidate-evidence-root.json | 5574FF6FF83226423D3A17E27426730178AA0E8CE03A87C15622233DDEAC24D1 |
| phase0.assertion_run_manifest | evidence/phase0/DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66/assertion-run-manifest.json | 66074C7AA5D52B0D782D9604456D3E01487B7E6B69A9B95377C7954D188EA154 |
| phase0.assertion_registry | evidence/phase0/DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66/assertion-registry.json | 80286553F6E2124DDC998CA7FB94B53518E644F79B93712C34D3D38CCF1C3097 |
| phase0.postroot_acceptance_contract_suite | docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json | 84431668E9F5103362D1A6275B235D8003A0BD600CAF694A4B0A4999C70F330F |
| phase0.postroot_acceptance_contract_suite.approval | docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite-approval.json | 2173396E4B977689CE20AC9602B47D25709294EE7D8E8CE3C070093E9B15B23F |
| phase0.gov_002_preapproval_reviewer_eligibility | docs/superpowers/governance/2026-08-14-gov-002-preapproval-reviewer-eligibility.json | 5686F548A495E9DC215474083EBC6775C921D5B7AD8E6DB98EF132DDC27C4EE4 |
| manifests/phase0/registry.json | manifests/phase0/registry.json | 36CBBCFF1A3E3663DE4A652CB7E00983FFDA5031F255F6BBEB9BCC90A2A7EA16 |

Full candidate bundle path:

`evidence/phase0/DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66/`

Confirm postroot suite logical IDs are absent from candidate `ordered_member_tuples`.

## Step 2 — Eligibility check

Evaluate `disqualification_rules`. Record `eligibility_result`. Proceed only if ELIGIBLE.

## Step 3 — Assigned minimum actions

Per `review_classes` INTEGRITY_AND_REPRODUCTION_AUDIT:

1. Independently recompute candidate evidence root from `ordered_member_tuples` using `market_platform_foundation.verifier.candidate_root` logic.
2. Recompute assertion aggregation from `assertion-results.json`; verify `aggregate_status` matches `candidate-evidence-root.json`.
3. Verify active assertion-set equality, selected-run membership (run_id `DA8BEB60D6A83FD30629FA76F5B8F6EFD157E22236849FC2ED0C5186439D7A66`), predicate identity, and `mandatory_set_hash`.
4. Execute postroot suite validation (all 70 fixtures, 62 reason codes):

```powershell
cd C:\Users\adame\Desktop\market-trading-platform\integrated-market-platform
$env:PYTHONPATH='src;.'
python tools/postroot/validate_postroot_acceptance_suite.py docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json
python tools/postroot/build_postroot_acceptance_suite.py --check docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json
python -m unittest discover -s tests/postroot -v
python -m unittest discover -s tests/phase0 -v
```

5. Test acceptance-index construction rules and postroot fixtures (index self-hash avoidance, root-hash golden vectors, final-result identity and precedence) without claiming a completed postreview index exists.
6. Attempt falsification: hash mismatch, identity mismatch, mixed-run, missing-member, extra-member, supersession, non-circularity cases.
7. Validate suite approval record binds exact suite hash, procedure hash, and approval scope `INTEGRITY_REVIEW_COMPANION_INPUT_ONLY`.

Record every reproduction in `reproduction_results` with `reproduction_id`, expected/observed outcomes, and `evidence_refs`.

## Step 4 — input_artifact_hashes binding

Your run record MUST include `input_artifact_hashes` entries for at minimum:

- phase0.ai_review_procedure
- phase0.candidate_evidence_root
- phase0.postroot_acceptance_contract_suite
- phase0.postroot_acceptance_contract_suite.approval
- phase0.gov_002_preapproval_reviewer_eligibility
- phase0.assertion_run_manifest
- Every other candidate tuple member you actually consumed

Sorted lexicographically by `logical_id` then `sha256`.

## Step 5 — Outcome derivation

Apply `finding_semantics` and `run_outcome_scope_rule` within this class's scope only. Do not infer peer-review or coverage state.

## Step 6 — Deliverables (write outside governed subject)

Write to an isolated directory (never inside the candidate bundle):

### A. Review output (`phase0.ai_review_output.contract`)

Same canonical rules as adversarial class. `review_class` must be INTEGRITY_AND_REPRODUCTION_AUDIT.

### B. Review run record (`phase0.ai_review_run.contract`)

Same required fields as adversarial class. Include postroot suite and approval in `input_artifact_hashes`.

Compute `review_run_id` and `review_output_hash` per procedure.

- `terminal_state`: COMPLETE | DISQUALIFIED | FAILED
- `qualification_state`: QUALIFYING only if COMPLETE and eligible

## Step 7 — Self-validation

- Recompute all hashes and identities
- Confirm fixture validation status PASS with `fixture_count` 70
- Confirm candidate root recomputation matches `78FA6A96D4193F53018ECFA7DFFAFFEBA3DA398A4E0116056C7C3BDDE8D2C482`
- Report: `terminal_state`, `recommended_candidate_outcome`, finding count, `review_run_id`, `review_output_hash`, artifact paths

Do not publish as formal evidence until separately validated. Do not claim Phase 0 PASS.
