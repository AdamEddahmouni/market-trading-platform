# Agent handoff — RTH15-00

Skill: `imp-handoff`. Session: RTH15-00 orchestration & reconciliation.

## Canonical state

- repository: `AdamEddahmouni/market-trading-platform` (IMP at `projects/integrated-market-platform/`)
- branch: `reconcile/rth15-00`
- worktree: `.worktrees/reconcile-rth15-00`
- HEAD SHA: set at commit time on this branch (base `origin/main` `d06f1f4c1154913c561fc3c7c42aa46f452a2a15`)
- upstream / ahead-behind vs `origin/main`: this branch only; do not use stale local `main` `3aaa3e8a`
- worktree cleanliness: product changes on this worktree; primary checkout `item7/natural-settlement` remains dirty/untracked and **was not cleaned**

## Objective

Reconcile isolated and post-close RTH-cycle work onto current canonical `main` without mutating evidence or Item 7.

## Completed

See [RTH15_00_TARGET_STATE.md](RTH15_00_TARGET_STATE.md) and [RTH15_00_RECONCILIATION_MATRIX.md](RTH15_00_RECONCILIATION_MATRIX.md).

Landed on this branch (software/docs only):

- evidence capture-context sidecar (`#196` unique)
- ranked-summary leak hygiene (`instrument_key` / `decision_support.authority` omitted from public cards)
- next-RTH latency hop catalog (read-only)
- selected UX on current contracts (#123/#124/#126/#128/#201 subset)
- Sep 15 diagnosis/review archives + UI redesign **plan docs**

## Validated

- `python tools/imp.py env` — healthy (IMP `.venv` junction)
- `python tools/imp.py format` — exit 0
- `python tools/imp.py lint` — exit 0 after `ui/npm ci` (worktree had no `node_modules`; first lint failed `'tsc' is not recognized`)
- `python tools/imp.py validate fast` — 23/0/0, exit 0; `perf=SEVERE_REGRESSION` vs FAST baseline (10.2s vs 1.8s median) — environment/timing, tests passed
- unittest modules evidence/leak/opportunity_api/latency — 33/0, exit 0
- `python tools/check_docs_links.py` — OK, 223 governance markdown files
- `python tools/imp.py validate changed` — first run: intelligence **error** (sidecar CLI printed to worker stdout); providers **failed** 11. After capturing CLI stdout, intelligence worker **1937 passed / 0 failed**. Providers 11 failures remain `ENVIRONMENT` (OpenD reachable / vendor SDK present on this VM; tests expect unreachable/SDK-missing). Not a product regression from this branch. Not success for providers on this machine.
- UI `npm test` — 113 files / 526 tests passed
- `npm run typecheck` — exit 0
- `npm run build` — exit 0
- `validate full` / `closure` — `NOT_RUN`
- Intelligence Benchmark Protocol — **not found / not executed**
- Prospective/natural-cycle jobs — **not executed**

## Active isolated work

| Worktree / branch | Purpose | Owner | Base SHA | Status | Disposition |
|---|---|---|---|---|---|
| primary `item7/natural-settlement` @ `c44231fa` | Item 7 natural settlement (#222) | operator | behind 1 / ahead 3 vs origin | dirty untracked review artifacts | `KEEP_ISOLATED_PENDING_EVIDENCE` — do not clean |
| `ui/operator-redesign-v2` | Operator redesign implementation | isolated | 66 behind | incomplete shell | `KEEP_ISOLATED`; plan docs recovered |
| `.worktrees/ops-canonical-agent-os` | OPS-00 | merged via #223 | `6618c8d9` | landed | canonical |
| Phase 2–5 / diagnosis / repair leftovers | Campaign leftovers | various | many remotes `gone` | retain | `SUPERSEDED_BY_MAIN` or archive |

## Evidence-sensitive state

`NONE OBSERVED` for `STAGE_2_APPLIED_AWAITING_NATURAL_CYCLE` (no branch, artifact, or matching Windows scheduled task).

Item 7 #222 remains isolated. Frozen Sep 15 empirical pin `7aade60`. `PROSPECTIVE_NO_POST_SIGNAL_BAR` not rewritten.

`NO HISTORICAL OR PROSPECTIVE EVIDENCE MUTATED`.

## Blockers

- Item 7 natural settlement: evidence/acceptance gate on #222 (orthogonal; did not freeze this increment)
- Providers CHANGED on this VM: OpenD/SDK environment (do not weaken tests)

## Deferred

- UI redesign foundation/shell implementation
- Intelligence Benchmark Protocol (not found; not executed)
- Open UX drafts after selective recovery
- Phase leftover worktree deletion

## Next work

Highest leverage after this PR merges: **Item 7 #222 natural-settlement review on its own isolated tree** (do not mix with this worktree), or continue operator UX redesign **reimplementation** on current Opportunity contracts — Composer default; Grok 4.6 High only if schema/architecture conflict appears.

Starting SHA: current `origin/main` after this PR merges (verify explicitly).

## Model / escalation notes

Stayed on Composer. No Grok 4.6 High escalation. No Fast models. No parallel mutating agents.

## Architecture decisions

- Public ranked cards omit leak-shaped names; keep `instrument_id`; real secrets still 500.
- Sidecar is optional metadata; cannot upgrade evidence class.
- Latency catalog is diagnostic, not production telemetry.

## Docs

WORK_LOG, PROGRAM_STATUS RTH15-00 row, target state, matrix, this handoff.
