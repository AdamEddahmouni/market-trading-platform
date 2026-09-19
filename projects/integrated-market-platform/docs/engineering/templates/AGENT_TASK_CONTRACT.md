# Agent task contract

Use for every substantial delegated agent lane. Copy and fill. Keep it short.

## Goal

What result is required?

## Scope

What subsystem/files may be inspected or changed?

## Non-goals

What must not be touched?

## State

- Canonical base: `origin/main` SHA `________`
- Worker branch/worktree: `________`
- Dirty-tree policy: preserve unrelated files / isolated worktree (circle one)

## Evidence constraints

Does this touch prospective, FTEP, RTH, heartbeat, or scheduler state?
If yes, mutations allowed: `________` / `NONE`.

## Expected deliverable

Code / findings / tests / report (circle). Success looks like: `________`

## Model policy

- Start on **Composer**
- Escalate to **Grok 4.6 High** only per `.cursor/rules/imp-model-policy.mdc`
- Never Fast model variants

## Integration authority

- Worker may commit to its isolated branch: yes/no
- Worker may merge to canonical `main`: **no** (unless explicitly delegated)
- Primary owner of canonical integration: `________`
