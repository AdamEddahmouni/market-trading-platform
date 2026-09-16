# IMP Agent Operating System

**Status:** Authoritative control plane for AI-assisted IMP development (OPS-00).

**Scope:** How agents choose models, isolate Git state, protect evidence, validate, and hand off.

**Not in scope:** Product architecture, FTEP campaign procedure, or RTH runtime operation.

This file is the **index**. Always-on behavior lives in short Cursor rules. Repeatable
procedures live in skills. Long-form product doctrine stays in architecture docs.

## Hierarchy (source of truth)

When instructions conflict, reconcile explicitly. Do not silently pick one.

1. **Safety invariants** — [MODE_AUTHORITY.md](../architecture/MODE_AUTHORITY.md), [SECURITY.md](SECURITY.md), env gates
2. **Always-on Cursor rules** — repo-root `.cursor/rules/imp-*.mdc` (identity, model, parallelism, evidence, git)
3. **Agent routers** — repo-root [AGENTS.md](../../../../AGENTS.md), this tree's [AGENTS.md](../../AGENTS.md), scoped `ui/` and `paper/` AGENTS files
4. **This operating system** — rules + skills + this index
5. **Developer command plane** — [DEVELOPER_OPERATING_SYSTEM.md](DEVELOPER_OPERATING_SYSTEM.md)
6. **Subsystem SOPs and architecture** — [docs/README.md](../README.md)
7. **Task prompt / skill** — bounded workflow
8. **Agent-local decisions** — must not contradict 1–6

Machine-readable model/parallelism policy:
[../../../../.cursor/model-routing.json](../../../../.cursor/model-routing.json)
(IMP copy, kept identical:
[../../.cursor/model-routing.json](../../.cursor/model-routing.json))

## What is a rule vs a skill vs a doc

| Kind | Use for | Examples |
|---|---|---|
| **Rule** (`alwaysApply`) | Behavior that must hold almost always | Composer-first, no Fast models, one-agent default, evidence class, Git safety |
| **Skill** | A repeatable workflow loaded when relevant | recon, reconciliation, validation, handoff, orchestration, evidence audit |
| **Doc / SOP** | Long-form procedure or architecture | worktrees, branch reconciliation, FTEP, MODE_AUTHORITY |

Do not paste runbooks into always-on rules.

Always-on rules and OPS skills are duplicated at:

- monorepo root `.cursor/` — this Cursor workspace
- `projects/integrated-market-platform/.cursor/` — Cloud / IMP-as-root checkouts

Keep those copies aligned when the operating system changes.

## Skills

Repo-root and IMP `.cursor/skills/` (same OPS skill names):

| Skill | When |
|---|---|
| `imp-repo-recon` | Session start, before mutation, before reconciling branches |
| `imp-reconciliation` | Isolated branches vs current `origin/main` (including RTH15-00) |
| `imp-validation` | Choosing and honestly reporting checks |
| `imp-evidence-integrity` | Diffs that touch experiments, FTEP, RTH, timestamps, schedulers |
| `imp-agent-orchestration` | Deciding single vs parallel execution |
| `imp-handoff` | Session end or ownership transfer |

IMP-scoped implementation skills remain under `projects/integrated-market-platform/.cursor/skills/` (`imp-testing`, `imp-feature-development`, `imp-bug-fixing`, `imp-review`, `imp-investigation`, `imp-documentation`, `imp-goal-closure`).

## Model policy (summary)

Start on **Composer**. Escalate to **Grok 4.6 High** only for reasoning difficulty,
architectural reconciliation, difficult debugging, high-risk evidence decisions,
multi-agent synthesis, or material Composer stall. Never Fast variants.
Parallel lanes escalate individually. Orchestrator defaults to Composer.

Full text: `.cursor/rules/imp-model-policy.mdc` and [AI_MODEL_STRATEGY.md](AI_MODEL_STRATEGY.md).

## Parallelism policy (summary)

One agent by default. Parallelize only independent substantial work. One primary
owner. No concurrent mutation of the same worktree. Isolated implementation uses
[GIT_WORKTREE.md](sops/GIT_WORKTREE.md).

## Git / worktrees

Canonical isolated trees: `<monorepo>/.worktrees/<purpose>` on intent-named
branches. Linked worktrees still use `python tools/imp.py env bootstrap --link-venv`
and [STATE_PATH_OPERATOR_CONVENTION.md](STATE_PATH_OPERATOR_CONVENTION.md) for
FTEP SQLite (do not treat empty worktree `.local` as “no sessions”).

## Validation

Command pyramid remains [DEVELOPER_OPERATING_SYSTEM.md](DEVELOPER_OPERATING_SYSTEM.md).
Honesty rules: skill `imp-validation`.

## Handoff

Template: [templates/AGENT_HANDOFF.md](templates/AGENT_HANDOFF.md). Skill: `imp-handoff`.

## Delegated task contract

Template: [templates/AGENT_TASK_CONTRACT.md](templates/AGENT_TASK_CONTRACT.md).

## RTH15-00

RTH15-00 (reconcile isolated/post-close work onto current `main`) is **not cancelled**.
It runs **after** this operating system is in effect, using `imp-repo-recon` then
`imp-reconciliation`. OPS-00 itself must not merge RTH branches, mutate RTH
evidence, or restart prospective runs.

## Superseded operating guidance

These remain readable history but **do not control** current agent operations:

- Vendor-agnostic “cheap means a faster/weaker model” reading of pre-OPS-00
  [AI_MODEL_STRATEGY.md](AI_MODEL_STRATEGY.md) — **cheap maps to Composer, never Fast**
- Automatic high-reasoning/Grok start merely because a Paper or architecture
  file is in the diff — **start Composer; escalate when the decision is hard or high-risk**
- [DEVELOPER_OPERATING_SYSTEM.md](DEVELOPER_OPERATING_SYSTEM.md) 2026-09-10
  local lane topology — already marked historical
- [DEVELOPER_OPERATING_SYSTEM_AUDIT.md](DEVELOPER_OPERATING_SYSTEM_AUDIT.md) —
  already marked historical 2026-09-02
- Prompt-only operating doctrine restated in one-off chats — replace with this
  index + rules + skills
