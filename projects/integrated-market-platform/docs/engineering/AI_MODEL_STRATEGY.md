# AI Model & Tool Strategy

**Status:** Authoritative Cursor model mapping for IMP (OPS-00).

**Always-on rule:** repo-root `.cursor/rules/imp-model-policy.mdc`.

**Machine-readable:** repo-root `.cursor/model-routing.json` (IMP copy kept identical).

Workload still determines *whether* to escalate. Current Cursor product names
are listed here so agents do not invent Fast substitutions or start on Grok
by default. If Cursor slugs change, update this table and `model-routing.json`
together — do not scatter names across architecture docs.

## Current Cursor mapping

| Policy tier | Current model | Cursor slug | Meaning |
|---|---|---|---|
| cheap | **Composer** | `composer-2.5` | Mechanical/low-risk work. **Not** Composer Fast. |
| normal (default) | **Composer** | `composer-2.5` | Ordinary implementation, tests, docs, UI, Git, ordinary orchestration. |
| high-reasoning (escalation) | **Grok 4.6 High** | `cursor-grok-4.6-high` | Only when an escalation trigger applies. |

**Forbidden:** any Fast variant (`composer-2.5-fast`, Fast Grok, automatic
speed-optimized substitutions). If a family offers Fast and normal/high, use
the normal/high-quality variant or do not use that family.

## Default

Start every normal implementation and investigation on **Composer**. Stay there
while it is making reliable progress.

Large but mechanical tasks stay on Composer. Prefer **good decomposition +
Composer** over an expensive reasoning model when decomposition solves it.

## Escalation to Grok 4.6 High

Escalate only when there is an actual reason:

- **Complex architecture:** disagreeing subsystems, major schema/state-machine,
  provider architecture, evidence-model or orchestration design.
- **Difficult debugging:** Composer attempted a reasonable diagnosis and is
  stuck; behavior contradicts the code; cross-service or nondeterministic cause.
- **Reconciliation:** substantial branch divergence, competing implementations,
  architectural merge conflicts, evidence-sensitive branch integration.
- **High-risk evidence:** forward-test temporal integrity, prospective evidence,
  scheduler/liveness, trading-state transitions, provenance — where a bad
  assumption could invalidate experimental evidence.
- **Large synthesis:** conflicting multi-agent findings that need a canonical
  decision.
- **Composer failure:** repetition, unexplained root cause, lost architecture,
  unsafe simplification, or material stall despite sufficient information.

Do **not** escalate merely because the task is large, many files exist, Grok is
available, quota remains, or a previous task needed Grok.

Touching Paper, `modeAuthority`, or persistence is a *reason to consider*
escalation, not an automatic Grok start. Well-specified edits in those areas
may remain on Composer; escalate when the *decision* is hard or high-risk.

## Parallel agents and orchestrator

Each lane follows this ladder independently. Do not launch several Grok agents
by default. Orchestrator defaults to Composer; escalate orchestration only when
findings conflict, architecture must be decided, or evidence-sensitive
synthesis exceeds Composer.

## Research / web-capable use

- External library version research
- Broker/API documentation
- CVE / security advisories
- Dependency evaluation

External info must **not** silently override repository contracts.

## Tool selection

| Need | Tool |
|------|------|
| Internal architecture | Codebase search, read docs |
| Validation | `python tools/imp.py`, vitest, build |
| Provider behavior | `docs/providers/`, then web if stale |
| GitHub PR/issues | `gh` CLI |
| Repo starting state | skill `imp-repo-recon` |
| Branch integration | skill `imp-reconciliation` |

## Freshness policy

Isolate product/runtime version tables in [STACK.md](STACK.md) and lockfiles.
This file's Cursor slug table is the exception for *agent model* routing.

## Delegation

Use `.cursor/agents/` role prompts with the task contract in
[templates/AGENT_TASK_CONTRACT.md](templates/AGENT_TASK_CONTRACT.md).
Parallelism: [AGENT_OPERATING_SYSTEM.md](AGENT_OPERATING_SYSTEM.md).
