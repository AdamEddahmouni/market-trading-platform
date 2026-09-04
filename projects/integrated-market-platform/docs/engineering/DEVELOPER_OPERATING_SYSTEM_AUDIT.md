# IMP Developer Operating System — Current-State Audit

**Date:** 2026-09-02
**Repository:** `integrated-market-platform`
**Purpose:** Evidence-backed baseline for reducing developer workflow latency without changing product behavior or safety authority.

## Repository baseline

- Git root: `integrated-market-platform`.
- Branch: `feat/p6-shadow-run-1-forward-validation`, one commit ahead of its
  remote tracking branch.
- The worktree is already dirty: 44 tracked modifications and 47 untracked
  files were present before this audit's control-plane changes.
- Fresh baseline FAST evidence:
  `PYTHONPATH=src .venv\Scripts\python.exe tools\validate.py fast` —
  21 tests passed, 0 skipped, 0 failures, 0 errors, 4.366 seconds.
- Existing work-log evidence records the most recent aggregate baseline as
  `validate.py changed`: 1,232 tests, 9 skipped, 1 failure, 91 errors in
  530.542 seconds; and `validate.py full`: 2,209 tests, 9 skipped, 1 failure,
  92 errors in 734.902 seconds. These are dirty-tree baseline evidence, not
  failures attributable to this control-plane work.

## Current workflow map

| Concern | Current authoritative path | Observed workflow |
|---|---|---|
| Repository discovery | `AGENTS.md`, `docs/README.md`, scoped `AGENTS.md` files | Read a root router, documentation index, architecture/security docs, handbook, work log, and optionally scoped guides. |
| Python validation | `tools/validation_manifest.json`, `tools/validate.py`, `validation_worker.py` | `fast`, `changed`, `domain`, `full`, `live`, `extended`, and informational `benchmark`. |
| Affected tests | `tools/validate.py` source/test globs plus one-hop neighbors | Safe direct ownership and neighbor expansion; Python suites are process-isolated and parallel only for `PARALLEL_SAFE`. |
| Frontend validation | `ui/package.json` | Separate `npm test`, `npm run typecheck`, and `npm run build`; not part of Python FULL. |
| Documentation validation | `tools/check_docs_links.py` | Separate command, invoked by CI and manually. |
| CI | `.github/workflows/imp-validate.yml` | One Python job and one UI job; Python runs FAST then CHANGED serially; no Python dependency cache or reusable workflow. |
| Agent guidance | Seven `.cursor/rules/*.mdc`, root/scoped `AGENTS.md`, AI guides/SOPs | Safety guidance is strong but command selection and delegation policy are distributed across repeated documents. |
| Hooks | No project `.cursor/hooks.json` or repo hook scripts | No automatic post-edit formatting/cheap validation or deterministic shell boundary enforcement. |
| Skills/subagents | No repo-local `.cursor/skills/` or `.cursor/agents/` inventory | Agents rely on general instructions and manually chosen delegation. |
| Metadata | `tools/validation_manifest.json` | Validation domains, suites, invariants, invalidators, ownership, and scheduling safety are machine-readable; repository/domain/safety routing is otherwise prose. |
| Closure | `WORK_LOG.md`, completion-record template, historical plans | Human-readable closure exists; no canonical machine-readable report joins changed areas, evidence, baseline failures, docs, and risk. |
| Telemetry | Validation JSON timing and `tools/benchmark.py` | Per-run timing is available, but no lightweight event schema aggregates validation runtime, CI runtime, repeated checks, or agent iteration counts. |

## Largest bottlenecks

1. **Command assembly and repeated context gathering.** The same root reads,
   validation matrix, UI commands, safety references, and work-log procedure
   are repeated across `AGENTS.md`, `AI_AGENT_GUIDE.md`, `VALIDATION.md`,
   `VALIDATION_ARCHITECTURE.md`, the handbook, and scoped guides.
2. **Split Python/UI orchestration.** Python affected validation, UI tests,
   typecheck, build, docs links, review, and closure have no single deterministic
   entry point, so agents spend turns deciding which commands to compose.
3. **Expensive aggregate validation on dirty trees.** The recorded CHANGED and
   FULL baselines take 530.542 and 734.902 seconds respectively while
   reporting failures across pre-existing dirty areas. The existing manifest
   can select safely, but the result is not automatically attached to a
   closure/baseline record.
4. **No automatic safety/workflow boundary.** Dangerous shell operations and
   protected branches are documented but not mechanically gated by project
   hooks.
5. **No progressive delegation contract.** There are no specialized repo-local
   architecture, implementation, verification, debugging, safety, documentation,
   or frontend review agents with explicit parallelism rules.
6. **Closure evidence is fragmented.** Work-log entries and completion records
   are useful historical references, but changed areas, validation evidence,
   known baseline failures, documentation deltas, and risk status must be
   assembled manually.

## After-implementation comparison

The first routed measurements provide two separate signals:

- Direct versus routed FAST validation was measured twice each with the same
  validator: direct median `3.185s`, routed median `3.253s`, or `0.067s`
  additional router overhead. The new command path is therefore effectively
  constant-time overhead while removing manual command assembly.
- The final routed CHANGED run selected `2,176` tests, skipped `34`, and
  completed in `425.317s`. It reported `3` baseline failures and `1` baseline
  error, with `full_suite_required=true`; the errors/failures are the
  pre-existing intelligence and validation findings (including the closure
  inventory gap and manifest-count expectation). The new router tests and all
  mandatory FAST invariants passed.
- The old path required separate validation, UI, docs, review, and closure
  decisions spread across multiple references. The new path exposes those
  decisions through one router and writes a closure report, while retaining
  the same manifest worker, mandatory selectors, serial/parallel safety
  classes, offline gate stripping, and backend authority. This reduces
  workflow turns/context assembly without weakening test selection.

The affected wall times are not a controlled like-for-like performance
benchmark because the worktree contents and selected suite set changed. The
router benchmark is the controlled evidence for command overhead; FULL remains
the required final correctness evidence.

## Safety constraints carried forward

The control plane must preserve, and must not reinterpret, the authoritative
rules in `docs/architecture/MODE_AUTHORITY.md`, `docs/engineering/SECURITY.md`,
and the Paper lifecycle documentation:

- Demo is read-only; Live is observational and `LIVE-001` remains blocked.
- Paper mutation requires backend `INTERNAL_SIMULATION` + `PAPER_ONLY` authority
  and explicit environment gates.
- Workspace remains the canonical Paper submit boundary.
- Risk authority, execution controls, account identity/isolation, source-time
  semantics, immutable provenance, persistence correctness, offline network
  denial, and fail-closed behavior remain authoritative.
- Speed improvements may select less work only when the manifest proves the
  omitted work is outside the relevant scope; they may never weaken a required
  invariant or turn a preliminary result into closure evidence.

## Target architecture boundary

The smallest coherent change is a thin `tools/imp.py` command router over
existing authorities, plus machine-readable routing metadata and evidence
artifacts. It should add:

- `imp env`, `format`, `lint`, `test affected`, `test focused`,
  `validate changed`, `validate full`, `review`, and `closure`;
- a documented FAST → AFFECTED/FOCUSED → DOMAIN → CHANGED → FULL closure
  pyramid, with existing manifest safety classes retained;
- repo-local skills, specialized subagent instructions, scoped Cursor rules,
  project hooks, Bugbot guidance, and lightweight JSONL telemetry;
- a closure report that records baseline-vs-current status without mutating
  product behavior.

The existing manifest remains the sole suite inventory, and the existing
validation worker remains the Python test execution authority.
