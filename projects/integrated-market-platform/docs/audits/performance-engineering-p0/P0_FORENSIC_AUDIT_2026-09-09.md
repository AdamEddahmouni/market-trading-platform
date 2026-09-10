# P0 Forensic Audit — IMP Performance Engineering & Developer Operating System

**Date:** 2026-09-09  
**Classification:** P0 complete (audit + baseline + control-plane foundation)  
**Exceptions:** NOTION_CONTEXT_BLOCKED, NOTION_SYNC_BLOCKED

## Executive result

**COMPLETE_WITH_EXPLICIT_EXCEPTIONS**

P0 forensic audit, performance baseline, developer-operating-system map, and
minimal control-plane fixes are delivered in-repo. Notion read/sync blocked (no
MCP). No broad optimization performed. Professor-directed uncommitted work
preserved.

---

## Baseline state

| Item | Value |
|------|-------|
| Branch | `main` |
| HEAD | `bf0715fdfca91b278e5c30edb6ff6707c448084d` |
| Accepted remote SHA | `bf0715fdfca91b278e5c30edb6ff6707c448084d` (HEAD matches) |
| Working tree | Dirty — 71+ changed paths (professor-directed news/intelligence/evaluation + docs) |
| Professor work preserved | Yes — no reset/clean/stash/commit |
| Latest FULL reference | 4456 passed, 48 skipped, 0 failures (user-reported) |
| Latest changed reference | 2304 passed, 28 skipped (professor lane) |
| G15 integrity | Intact — E2E tier isolated; validation manifest authoritative |
| Live execution | Disabled |

---

## Notion context used

**Availability:** Not available (no Notion MCP namespace in session)

**Pages that should have been read:**

- Integrated Market Platform / Current Status & Roadmap
- Professor-Directed Priority Program — Sep 9, 2026
- Performance Engineering & Test Efficiency Program
- Performance Engineering: forensic baseline & optimization audit (task)
- Sync Status — Local ↔ GitHub ↔ Notion
- Current Week — Week 3

**Relevant state (from repository, not Notion):**

- Primary lane: Paper forward-testing bridge (next product increment)
- Performance lane: P0 audit (this work)
- Professor stack: news foundation, AI inference, strategy evaluation lab — uncommitted, validated locally

**Discrepancies:** Not verified against Notion; repository is authoritative.

See [NOTION_DEVELOPMENT_LIFECYCLE.md](NOTION_DEVELOPMENT_LIFECYCLE.md).

---

## Repository discovery audit

**Current path:** Monorepo root `market-trading-platform/` → canonical IMP at
`projects/integrated-market-platform/` → `AGENTS.md` → `docs/README.md` →
`DEVELOPER_OPERATING_SYSTEM.md`.

**Ambiguity sources:**

- Dual tree: monorepo snapshot vs standalone `integrated-market-platform/` child repo
- Donor `Claude Code News/` gitignored at monorepo root — correctly outside IMP validation
- Shell default Python 3.10 vs required 3.11 `.venv`
- Large `docs/`, `artifacts/`, phase tooling — agents grep repeatedly for commands

**Repeated work:** AGENTS + 5 alwaysApply rules + handbook + VALIDATION.md overlap;
validation command discovery; monorepo path prefix normalization.

**Recommendations:** Lightweight context index in DEVELOPER_OPERATING_SYSTEM (added);
always activate `.venv` before `imp.py`; scoped AGENTS for news/intelligence (P6).

---

## AGENTS.md authority map

| Path | Scope | Parent |
|------|-------|--------|
| `AGENTS.md` | Root router | — |
| `ui/AGENTS.md` | Frontend | Root |
| `src/.../paper/AGENTS.md` | Paper backend | Root |

**Duplication:** Safety/mode rules repeated in `.cursor/rules` (intentional layering).

**Conflicts:** None on safety; stale `full_suite_required` in cursor artifacts (fixed P0).

**Stale:** Hardcoded Windows Python path in root AGENTS; cloud handoff branch Aug 2025.

**Missing:** Scoped AGENTS for `news/`, `intelligence/inference/`, `news_strategy_evaluation/`.

---

## Cursor / project rules audit

- **Global (alwaysApply):** developer-workflow, work-logging, authoritative-docs,
  inspect-before-edit, no-fabricated-data
- **Glob:** mode-authority-ui, react-query-keys, paper-execution-safety
- **Agents (7):** architecture, implementation, testing, debugging, safety-review,
  frontend-review, documentation-review
- **Skills (7):** feature-development, bug-fixing, testing, investigation, documentation,
  review, goal-closure

**Problems:** Token-heavy alwaysApply stack; broken link in authoritative-docs (fixed);
no news/intelligence glob rules.

---

## SOP audit

| Phase | Current | Recommended |
|-------|---------|-------------|
| Startup | AGENTS + DOS + optional Notion | Add explicit Notion read when MCP available (documented) |
| Dev loop | FAST → focused → affected | Reinforced; agents sometimes jump to changed on large diffs |
| Review | imp.py review | Keep; add selector explain for large changed fan-out |
| Closure | imp.py closure + WORK_LOG | Four-part milestone chain formalized (impl→val→docs→Notion) |

Existing SOPs: `docs/engineering/sops/` (12 files) — no dedicated news SOP yet.

---

## Developer command interface

Canonical router: `python tools/imp.py` from IMP root.

| Command | Stage | Cost (measured/reference) |
|---------|-------|---------------------------|
| `env` | Startup | tiny (fails on wrong Python) |
| `format` / `lint` | Pre-edit | cheap |
| `validate fast` | Invariant gate | **3.4s** (21 tests) |
| `test focused <sel>` | Iteration | **0.4–1.2s** (news/intelligence) |
| `validate changed` | PR/ordinary | **~2304 tests / minutes** (dirty-tree dependent) |
| `validate full` | Closure | **~539s / 4392 tests** (G15 ref) |
| `validate e2e` | Product acceptance | **~69s / 6 tests** |
| UI `npm test -- --run` | Frontend | **~72s** |
| `closure` | Final | FULL + UI + docs |

---

## Validation pyramid

1. **FAST** — 21 mandatory invariants  
2. **FOCUSED** — explicit selectors  
3. **AFFECTED/CHANGED** — manifest selection + cheap checks  
4. **DOMAIN** — offline full-tier per domain  
5. **FULL** — all offline full-tier suites  
6. **E2E/LIVE** — opt-in product/live gates  

**Misuse:** Running changed when only docs changed but artifacts FAIL_SAFE escalates;
running FULL during iteration; shell Python 3.10 bypassing venv.

---

## Test performance baseline

See [PERFORMANCE_BASELINE.json](PERFORMANCE_BASELINE.json).

---

## Slow-test profile

**Dominant suites (G15 + manifest):** `platform`, `ui1`, `donor_bridge` — GLOBAL_STATE_MUTATION
or SERIAL_REQUIRED; ~79–106s each in prior evidence.

**Root causes:** Application/service container setup, temp repos, global registries,
HTTP test clients, large discover directories under `tests/platform/`.

**Categories:** FIXTURE + APPLICATION STARTUP + GLOBAL STATE dominate over TEST BODY.

---

## Fixture / setup / teardown analysis

| Pattern | Classification |
|---------|------------------|
| Platform Paper/API app construction | MUST_REMAIN_ISOLATED (P4 candidate reuse) |
| JSON fixture loads | SAFE_TO_REUSE (read-only) |
| Temp git trees (closure/postroot) | MUST_REMAIN_ISOLATED |
| News replay packs | SAFE_TO_REUSE after path stability |
| Mongo optional integration | COULD_REUSE_AFTER_REFACTOR |

No broad fixture sharing implemented in P0.

---

## Subprocess / filesystem analysis

- Validation workers spawn isolated Python subprocesses per suite (startup ~0.5s each)
- E2E spawns Playwright + server (68s tier)
- UI Vitest/jsdom startup (~72s for 454 tests)
- `benchmark.py` confirms Python startup ~38ms median

---

## Invariant coverage map

See [INVARIANT_COVERAGE_MAP.json](INVARIANT_COVERAGE_MAP.json).

---

## Duplicate / overlap analysis

- **Intentional layering:** unit (news/intelligence) + platform integration + E2E acceptance
- **Near redundancy candidates:** platform + ui1 mode-surface overlap (uncertain — defer P1)
- **Exact redundancy:** Not identified without module-level diff (P1)

No deletion recommended in P0.

---

## Parallel-safety map

See [PARALLEL_SAFETY_MAP.json](PARALLEL_SAFETY_MAP.json).

Summary: 45 PARALLEL_SAFE, 11 GLOBAL_STATE_MUTATION, 5 SERIAL_REQUIRED, 5 RESOURCE_HEAVY, 12 LIVE_EXCLUSIVE.

---

## Affected / changed selector analysis

**Current dirty tree (72 paths):**

- `core_checkpoint_required=true`
- **FAIL_SAFE:** `artifacts/g*-runtime-performance.json` (unclassified → core checkpoint)
- **OWNING:** 52 paths → suites: news, intelligence, platform, finviz, …
- **Selected suites (9):** phase0, finviz, news, platform, contracts, intelligence, providers, runtime, validation

**Why ~2304 tests:** News/intelligence/platform source ownership + neighbor expansion +
core checkpoint diagnostics + 21 mandatory invariants — not selector bug.

**Selector plan:** Shadow CHANGED vs FULL recall evidence (OPT-004); BL-0801 partitioning (P3).

---

## Frontend / E2E performance findings

- Vitest: **71.9s** wall (454 tests ref)
- E2E: **68.8s** (6 Playwright tests) — appropriate for product acceptance tier
- Build/typecheck: not measured; CI runs all three serially

---

## Production runtime baseline

`tools/benchmark.py` — fixture-backed operations sub-ms to low-ms; representative
simulation ~1.2ms/op. No production hot path requiring P5 rewrite at P0.

---

## Agent workflow audit

Typical waste: repeated git status; grep for validation commands; reading overlapping
AGENTS/rules/handbook; `--explain` still executes full changed (no explain-only mode);
Notion context skipped when unavailable without explicit blocker flag.

---

## Context-loading findings

Hierarchy: global rules → AGENTS → scoped AGENTS → task docs → code.

Reduce: fix stale terminology; link performance audit index; defer full handbook reads
when DOS suffices.

---

## Agent architecture findings

Existing agents cover implementation/review/testing adequately.

**Prefer skills over new agents:** Notion sync, profiling, selector explain.

**No agent explosion recommended.**

---

## Skills audit

7 repo skills under `.cursor/skills/imp-*`. Gap: Notion lifecycle skill (blocked on MCP).

---

## SOP / Skill / Command / Agent decision matrix

| Workflow | Mechanism |
|----------|-----------|
| Repository discovery | AGENTS + docs/README (RULE/DOC) |
| Task startup | SOP in DOS + optional Notion skill |
| Validation selection | `imp.py` COMMAND |
| Profiling | `benchmark.py` COMMAND |
| Closure | `imp-goal-closure` SKILL + `imp.py closure` |
| Notion sync | SKILL (future) / SOP |
| Architecture review | `imp-architecture` AGENT |

---

## CI audit

`.github/workflows/imp-validate.yml`: actionlint → fast → changed → docs links → UI (typecheck, test, build).

**Duplication:** fast + changed both run Python setup; no pip/uv cache.

**Critical path:** changed Python job + UI job (parallel jobs, serial steps within).

---

## Hooks audit

`.cursor/hooks.json`: beforeShellExecution (policy.py), afterFileEdit (format+lint).

**Cost:** cheap on edit. **Value:** blocks destructive git ops. No pre-commit yaml.

---

## Documentation authority findings

Authoritative: MODE_AUTHORITY, DOS, validation manifest, architecture news docs (new).

Historical: superpowers/plans completion records, BUILD artifacts.

Duplicate: VALIDATION.md vs DOS command tables (acceptable cross-link).

---

## Low-risk P0 improvements made

| Category | Changes |
|----------|---------|
| rules | `core_checkpoint_required` terminology; authoritative-docs link fix |
| SOPs | Notion lifecycle + test deletion governance in DEVELOPER_OPERATING_SYSTEM.md |
| agents | testing.md terminology |
| skills | imp-testing terminology |
| commands/tooling | benchmark artifact at artifacts/p0-performance-baseline.json |
| docs | performance-engineering-p0 audit pack; docs/README index |
| Notion | NOTION_DEVELOPMENT_LIFECYCLE.md spec only (sync blocked) |

---

## Performance opportunity ledger

See [OPTIMIZATION_LEDGER.json](OPTIMIZATION_LEDGER.json).

Top priority: **P3** artifacts classification + BL-0801 partitioning before **P2** parallelization.

---

## Validation (P0 changes)

| Command | Result |
|---------|--------|
| `validate fast` | 21 passed, 3.447s |
| `benchmark.py --include-fast` | Report written |
| Docs/rules changes | `check_docs_links.py` pending |

---

## Notion synchronization

**NOTION_SYNC_BLOCKED**

**Intended updates:**

- Performance Engineering program → P0 complete with exceptions
- Forensic audit task → evidence links to `docs/audits/performance-engineering-p0/`
- Development & Validation Log → FAST 3.4s; changed selection analysis; vitest 72s
- Current Week → P0 done; next P3 selector work queued

---

## Known limitations

- Notion unavailable
- FULL not re-run (used G15 reference)
- Single-run timings; Windows warm venv
- `--explain` does not skip test execution
- CI telemetry not inspected locally

---

## Recommended P1–P7 execution order

1. **P3** — Selector + artifacts evidence classification (BL-0801)  
2. **P4** — platform/ui1 fixture/setup optimization  
3. **P2** — Safe parallelization within PARALLEL_SAFE  
4. **P6** — CI cache, rule consolidation, Notion skill, AGENTS portability  
5. **P1** — Test rationalization with invariant map  
6. **P5** — Production runtime (low priority at current measurements)  
7. **P7** — Budgets after variance baselines  

---

## Worktree isolation (next increment)

Use clean worktree from `bf0715f` for P3 selector changes; profile professor dirty tree
read-only; never mix broad test rewrites with uncommitted professor work.

---

## Primary professor lane status

The governed **Paper forward-testing bridge** remains the PRIMARY IMP product-development
next step. This P0 audit is secondary/enabling and did not replace that authority.
