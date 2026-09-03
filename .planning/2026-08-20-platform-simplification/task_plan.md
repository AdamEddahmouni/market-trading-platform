# Platform Simplification and Validation Architecture Plan

## Goal

Minimize the cost and wall-clock time of high-confidence validation while preserving full offline coverage, PIT/bitemporal semantics, security, provider neutrality, live/offline separation, and the intentional dirty tree.

## Current Phase

**Complete** — landing in logical commits (2026-08-21).

## Phases

### Phase 1: Requirements and repository discovery

- [x] Read the attached work package.
- [x] Verify repository identity, branch, HEAD, and dirty-tree constraints.
- [x] Finish mapping the existing runner, tests, and repository guidance.
- [x] Present design alternatives and obtain user approval.
- [x] Write and self-review the approved design specification.
- [x] Obtain user review of the written specification.
- **Status:** complete

### Phase 2: Approved design and implementation plan

- [x] Write the approved design document.
- [x] Self-review it for scope, ambiguity, and contradictions.
- [x] Write a staged, test-first implementation plan.
- **Status:** complete

### Phase 3: Baseline and independent audits

- [x] Measure canonical full-suite, discovery, startup, import, fixture-I/O, and production-operation baselines.
- [x] Audit redundancy, invariants, parallel safety, live gating, and manifest drift.
- [x] Reconcile findings before broad edits.
- **Status:** complete — see `evidence/performance/test-baseline.json`

### Phase 4: Validation architecture implementation

- [x] Implement canonical manifest and structured runner behavior test-first.
- [x] Implement fast, changed, domain, full, live, and extended modes test-first.
- [x] Implement optional JSON and selection explanations.
- [x] Add profiling/benchmark evidence and documentation.
- **Status:** complete

### Phase 5: Measured low-risk acceleration

- [x] Benchmark worker counts and adopt only deterministic parallelism.
- [x] Optimize proven fixture/import/runner bottlenecks.
- [x] Consolidate or remove code/tests only with replacement evidence.
- **Status:** complete — see `docs/engineering/PROVIDER_DUPLICATION_AUDIT.md`

### Phase 6: Acceptance and reporting

- [x] Run fast repeatedly, changed, affected domains, and final full offline validation.
- [x] Verify live gating, offline network prohibition, security, and PIT invariants.
- [x] Produce measured before/after artifacts and acceptance report.
- **Status:** complete — see `evidence/platform/simplification-acceptance-report.md`

## Decisions Made

| Decision | Rationale |
|---|---|
| Treat the current dirty tree as user-owned and preserve it | Explicit work-package constraint |
| Use no network or live-provider probes for baseline work | Offline suite and live-gate separation are correctness boundaries |
| Centralize edits after concurrent read-only audits | Avoids conflicting changes without a private subagent primitive |
| Do not touch trading logic | Explicit engineering-infrastructure scope |
| Make `tools/run_all_tests.py` a strictly offline compatibility wrapper | User delegated the choice; explicit live commands are safer, faster, and less ambiguous |
| Use a manifest-driven subprocess runner | Preserves isolation while enabling structured results, targeting, and measured suite-level parallelism |

## Errors Encountered

| Error | Attempt | Resolution |
|---|---:|---|
| Combined repository/prompt probe output was truncated | 1 | Split subsequent reads into smaller bounded chunks |
| Guessed two test filenames that do not exist | 1 | Enumerated actual test paths with `rg --files` before selecting exact invariant IDs |
