# SOP: Git worktrees and isolated implementation

**Status:** Authoritative agent/operator convention.

**Related:** [STATE_PATH_OPERATOR_CONVENTION.md](../STATE_PATH_OPERATOR_CONVENTION.md), skill `imp-repo-recon`, skill `imp-agent-orchestration`.

## When to isolate

Create a dedicated worktree when:

- the current checkout has unrelated dirty work
- parallel implementation is justified
- reconciliation must not disturb an evidence-sensitive tree
- the primary branch is not the intended base (`origin/main` unless the task says otherwise)

Read-only audits may use the current tree.

## Canonical layout

On this repository:

```text
<monorepo>/.worktrees/<purpose>
```

Example:

```powershell
git fetch origin main
git worktree add -b ops/<short-purpose> .worktrees/<short-purpose> origin/main
```

If an environment uses `/workspace/IMP/worktrees/<purpose>`, treat that as the
same convention under a different root. Do not invent a second parallel layout
on a machine that already uses `.worktrees/`.

Sibling checkouts such as `market-trading-platform-perf-p3` are **historical**.
Prefer `.worktrees/<purpose>` going forward.

## Branch names

Communicate intent. Do not use disposable names like `tmp`, `test`, `fix2`.

| Prefix | Use |
|---|---|
| `fix/` | defect repair |
| `feat/` | feature |
| `ui/` | interface-only |
| `research/` | research/spike, not product evidence |
| `diagnostic/` | read-mostly diagnosis |
| `reconcile/` | integration onto current main |
| `ops/` | developer-operating-system / tooling |
| `benchmark/` | performance measurement |

## Required metadata

Every isolated worktree records:

| Field | Meaning |
|---|---|
| **purpose** | one-line why it exists |
| **owner** | primary agent or operator |
| **base SHA** | usually `origin/main` at creation |
| **status** | `active` / `blocked` / `ready-to-integrate` / `abandoned` |
| **disposition** | `merge` / `cherry-pick` / `reimplement` / `defer` / `drop` / `unset` |

Put this in the session handoff. Do not maintain a committed inventory of every
local worktree (it goes stale immediately).

## Environment

Linked worktrees do not inherit `.venv`. From IMP:

```powershell
python tools/imp.py env
python tools/imp.py env bootstrap --link-venv
python tools/imp.py state-path
```

Empty worktree `.local/` is not proof that FTEP sessions do not exist.

## Hard rules

- One implementing agent per worktree.
- Do not reset, clean, or stash another lane's unique work.
- Integrate through the primary owner.
- Do not point an isolated worktree at live/prospective evidence just to make tests convenient.
