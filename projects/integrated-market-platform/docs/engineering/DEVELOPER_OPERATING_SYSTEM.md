# IMP Developer Operating System

**Status:** Authoritative developer workflow architecture.
**Scope:** Repository discovery, execution, validation, review, and closure.

The operating system is a thin control plane around existing authorities. The
validation manifest remains the only suite inventory, `tools/validate.py`
remains the Python validator, backend authority remains the safety boundary,
and UI commands remain owned by `ui/package.json`.

## Canonical command interface

Run from the repository root. Prefer the router so command choice, timing, and
evidence are consistent:

| Command | Purpose | Default cost |
|---|---|---|
| `python tools/imp.py env` | Safe runtime, Git, worktree, interpreter, timezone, and gate-presence diagnostics | tiny |
| `python tools/imp.py env bootstrap --link-venv` | Explicitly link a shared canonical `.venv` into a linked worktree | tiny |
| `python tools/imp.py env install-opend` | Install optional vendor OpenD SDK (`moomoo-api`) into the IMP interpreter | tiny |
| `python tools/imp.py ci jobs` | Classify which expensive GitHub CI slices current changes need (no tests) | tiny |
| `python tools/imp.py format` | Changed-file whitespace check (`git diff --check`) | tiny |
| `python tools/imp.py lint` | Python compile check and UI typecheck when UI is affected | cheap |
| `python tools/imp.py validate fast` | Run mandatory catastrophic invariants | fast |
| `python tools/imp.py test focused <selector>` | Explicit unittest selector(s) in one isolated worker | focused |
| `python tools/imp.py test affected` | Manifest-selected changed suites and mandatory invariants | affected |
| `python tools/imp.py validate changed` | Canonical changed validation with optional JSON evidence | affected |
| `python tools/imp.py validate domain <name>` | Domain milestone validation | domain |
| `python tools/imp.py validate full` | All offline full-tier suites | expensive |
| `python tools/imp.py review` | Format gate plus fail-fast affected validation | review |
| `python tools/imp.py closure` | Full backend closure, docs/UI gates as applicable, report | most expensive |

`test affected` is an ergonomic alias for manifest `changed` selection. It
does not infer live suites or replace mandatory invariants. `test focused`
requires exact selectors of the form
`tests/path/test_file.py::TestClass::test_method`.

## Validation pyramid

1. **FAST:** catastrophic mandatory invariants only.
2. **PLAN:** `python tools/imp.py validate changed --plan` when changed scope is unclear; executes zero tests.
3. **FOCUSED:** exact regression selectors while iterating.
4. **AFFECTED:** changed tests, direct owners, BL-0801 directional dependents,
   and mandatory invariants; safe Python suites run in parallel.
5. **DOMAIN:** all offline full-tier suites for one domain at a milestone.
6. **CHANGED:** the canonical affected result plus cheap checks; a
   `core_checkpoint_required` result is preliminary, never closure evidence.
7. **FULL:** all offline full-tier suites once at final closure.

`SERIAL_REQUIRED`, `GLOBAL_STATE_MUTATION`, and `LIVE_EXCLUSIVE` work stays
serial. `PARALLEL_SAFE` work may use the configured worker count.
`RESOURCE_HEAVY` work is capped by the existing validator. Live validation is
opt-in and never substitutes for offline FULL.

For UI changes, add `cd ui && npm test`, `npm run typecheck`, and
`npm run build`; the build retains the 200 KiB gzip budget. For documentation
changes, run `tools/check_docs_links.py`.

## Agent delegation

Use `.cursor/agents/` for role-specific instructions:

- `architecture` — boundaries, invariants, and design review.
- `implementation` — scoped code changes following existing ownership.
- `testing` — focused/affected validation and evidence interpretation.
- `debugging` — reproduction, root cause, and regression tests.
- `safety-review` — Demo/Paper/Live, risk, execution, account, temporal, and
  persistence review.
- `documentation-review` — authority hierarchy, links, and stale duplication.
- `frontend-review` — query/state semantics, mode surfaces, accessibility, and
  bundle behavior.

Default to **one agent**. Parallel delegation is appropriate only for
independent read-only discovery, independent pure implementation slices in
separate worktrees, or isolated `PARALLEL_SAFE` tests. Keep shared files,
validation-manifest changes, persistence, authority, execution, evidence-
sensitive runtime, CI, and documentation-index changes serial. A reviewer must
inspect the combined diff after parallel work. See
[AGENT_OPERATING_SYSTEM.md](AGENT_OPERATING_SYSTEM.md) and
[sops/GIT_WORKTREE.md](sops/GIT_WORKTREE.md).

## Model routing

Canonical policy is repo-root `.cursor/rules/imp-model-policy.mdc` plus
[AGENT_OPERATING_SYSTEM.md](AGENT_OPERATING_SYSTEM.md). Machine-readable copy:
`.cursor/model-routing.json`. Durable explanation:
[AI_MODEL_STRATEGY.md](AI_MODEL_STRATEGY.md).

- **Composer (default):** exploration, mechanical edits, ordinary
  implementation, tests, docs, UI, Git, and ordinary orchestration.
  The historical **cheap** and **normal** tiers both map here — never to a
  Fast variant.
- **Grok 4.6 High (escalation only):** architectural reconciliation, difficult
  debugging after Composer stall, high-risk evidence-sensitive decisions,
  multi-agent synthesis, or material Composer failure.

Do not start on Grok because a task is large or because a Paper/architecture
file appears in the diff. Never use Fast model variants.

## Evidence and closure

The router records lightweight JSONL command telemetry under
`.local/developer-workflow/telemetry.jsonl` by default; override with
`IMP_TELEMETRY_PATH`. It records command identity, exit status, and wall time,
never environment values or credentials.

`imp closure` writes
`artifacts/developer-workflow/closure-report.json` with changed files/areas,
validation evidence, baseline failure classification, documentation changes,
risk status, and telemetry location. Existing dirty-tree failures must be
carried as baseline evidence rather than silently reclassified.

## Notion development lifecycle

Notion is the human/project/internship planning and evidence layer. It does not
replace code, Git, local working-tree truth, tests, CI, or validation artifacts.

**Authority precedence:** local working tree = implementation truth; accepted
Git history = source-control truth; tests/validation artifacts = software
acceptance evidence; Notion = planning, task state, roadmap, human context.

**Substantial task startup** (when Notion tools are authenticated): read the
smallest relevant Notion context set (task, current week, roadmap slice) before
implementation; compare Notion status to verified repository state; flag
mismatches; proceed from repository truth.

**Material task closure:** gather exact validation evidence, then sync verified
status to the relevant Notion task/pages. Never invent Notion access or updates.
If Notion is unavailable, report `NOTION_SYNC_BLOCKED` with intended updates.

**Milestone chain:** implementation → validation → canonical repository
documentation → Notion status/evidence. Git commit/PR/merge remains a separate
explicit step.

## Test removal governance

A test may not be removed or consolidated solely because it is slow or numerous.
Before removal require: (1) exact invariant identified, (2) surviving test(s)
identified, (3) layer difference considered, (4) failure-path coverage
considered, (5) selector/affected implications considered, (6) focused validation
green, (7) appropriate broader validation green, (8) before/after performance
evidence when removal is performance-motivated.

## Performance program

Forensic baselines and optimization ledgers live under
[performance-engineering-p0](../audits/performance-engineering-p0/README.md).
Optimize measured hotspots only; preserve assurance invariants. Performance work
is secondary/enabling and must not displace primary product increments.

## Local lane topology (historical 2026-09-10)

The table below is the **2026-09-10** worktree topology. It is **not** current
procedure. Current landing is `git fetch origin main` → `origin/main`; see
[PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) and the live command sheet
[DEVELOPER_RUNBOOK.md](DEVELOPER_RUNBOOK.md).

| Lane | Branch | Worktree | Purpose |
|------|--------|----------|---------|
| Primary professor | `work/professor-paper-forward-testing` | Repository root | Product increments (Paper forward-testing bridge next) |
| Checkpoint ref | `checkpoint/post-g15-professor-p0-2026-09-09` | (ref only) | Recovery anchor at `cd145fc` |
| Performance P3–P7 | `perf/p3-validation-selector` … `perf/p7-continuous-performance-budgets` | Sibling worktrees | Selector/evidence/scheduler/budget optimization only |

Create performance refactors in the dedicated worktree; integrate back through
explicit merge/cherry-pick after validation. Do not treat the 2026-09-10
professor root as the current landing branch. Remote `main` remains the accepted
baseline until an explicit publish step.

### Linked Git worktrees

Performance and parallel development may use linked Git worktrees. In that
layout the worktree root contains a `.git` **file** (`gitdir: …`) rather than a
`.git` **directory**. Canonical repository discovery in
`src/market_platform_foundation/git_ref.py` resolves both forms, returns the
worktree top level as `repo_root()`, and reads shared branch metadata through
Git's `commondir` indirection. Ordinary single-checkout clones are unchanged.

**Environment bootstrap:** linked worktrees do not automatically inherit a local
`.venv`. Run `python tools/imp.py env` to inspect interpreter resolution and
`python tools/imp.py env bootstrap --link-venv` to create a portable junction or
symlink to the canonical shared environment. Validation commands launched through
`tools/imp.py` automatically use the resolved interpreter.

**Durable state paths:** linked worktrees use a local `.local/` that is test/dev
only. Canonical FTEP empirical SQLite stays on the primary IMP checkout unless
`IMP_STATE_DIR` overrides it. Run `python tools/imp.py state-path` before FTEP
operator reads; see [STATE_PATH_OPERATOR_CONVENTION.md](STATE_PATH_OPERATOR_CONVENTION.md).

## Safety and ownership

The control plane does not authorize or execute trades. It preserves
[MODE_AUTHORITY.md](../architecture/MODE_AUTHORITY.md), [SECURITY.md](SECURITY.md),
Paper lifecycle authority, and the validation manifest. Hooks can block
dangerous workflow commands, but hooks are defense-in-depth; backend gates,
offline guards, and persisted audit controls remain authoritative.
