---
name: imp-agent-orchestration
description: Decide single vs parallel IMP agents, define lanes and worktree ownership, apply Composer-first escalation per lane, and synthesize results. Use before launching subagents or when coordinating multiple investigations.
---

# IMP agent orchestration

Default: **one agent**. Parallelism is a tool, not a goal.

## Decide

Launch a parallel lane only if all are true:

- genuinely independent
- safely separable
- unlikely duplicated effort or conflicting architecture
- isolated from shared mutable state
- substantial enough to justify orchestration overhead

Otherwise keep one agent.

## Task contract (every delegated lane)

Copy [AGENT_TASK_CONTRACT.md](../../../docs/engineering/templates/AGENT_TASK_CONTRACT.md):

- Goal, scope, non-goals
- State (branch/worktree/base SHA)
- Evidence constraints
- Expected deliverable
- Model policy: start Composer; escalate per `.cursor/rules/imp-model-policy.mdc`; never Fast
- Integration authority: worker may commit to its isolated branch; primary owns canonical integration

## Model

- Orchestrator defaults to Composer.
- Each lane starts on Composer and escalates to Grok 4.6 High only for that lane's trigger.
- Do not launch several Grok agents by default.

## Git

- One mutable worktree per implementing agent.
- Parallel implementation: `<repo>/.worktrees/<purpose>` on intent-named branches.
- Read-only audits may share a tree.
- Primary owner reconciles Git and architecture.

## Synthesize

Subagents return bounded findings. They do not declare what is canonical.
The primary inspects the combined diff, resolves conflicts, validates, and reports.
