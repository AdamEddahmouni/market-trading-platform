# IMP program status

| Field | Value |
|---|---|
| Document ID | `IMP-PROGRAM-STATUS` |
| Classification | `CANONICAL` |
| Lifecycle Status | `CANONICAL` |
| Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Current whole-program maturity and safety status |
| Owner Role | IMP program architecture owner |
| Version | `1.0.0` |
| Last Verified | 2026-08-27 |
| Establishing Milestone | `IMP-REBASE-01` |
| Supersedes | Current-status claims in the root README and historical roadmaps |
| Superseded By | None |

This is the maintainable authority for current program status. It uses stable
milestone identities rather than a transient repository HEAD.

> This document is canonical for program-level interpretation and architecture. Where executable behavior is controlled by a designated schema, policy, gate, manifest, registry, or authority implementation, that executable authority controls within its defined scope.

## Current baseline

| Program area | Current state | Meaning |
|---|---|---|
| Original core architecture campaign, BUILD01-35 | `COMPLETE_WITH_LIMITATIONS` (historical) | BUILD35 accepted its recorded candidate as `FULL_SYSTEM_ACCEPTED_WITH_LIMITATIONS`; this is historical acceptance, not present production readiness. |
| Repository closure | `COMPLETE` | Post-BUILD35 closure and CLEANUP-01 are accepted history. |
| EVIDENCE | `IN_PROGRESS` | EVIDENCE-01 policy, EVIDENCE-01A campaign, and EVIDENCE-01B runtime operationalization exist. EVIDENCE-01C is the next semantic milestone and is not accepted yet. |
| Program re-baseline | `IMP-REBASE-01` | Current canonical program documentation is established by this milestone. |
| IMP Operating Fabric | `PARTIAL` | Validation, manifests, campaign identities, orchestrators, runbooks, and operational patterns exist; universal run, workflow, capability, SOP, and artifact authorities do not. |
| Cross-Asset | `PARTIAL` | Macro/rates series, energy, futures positioning, institutional, options, and market-context foundations exist; a canonical cross-asset identity and relationship kernel does not. |
| Real-Time Opportunity Fabric | `PARTIAL` | Bounded observational callbacks, hot state, features, routing, and opportunity foundations exist; program-wide causal tracing, measured latency budgets, and a universal opportunity state fabric do not. |
| Narrative/Motive | `PARTIAL` | Point-in-time context, hypotheses, selected narrative features, and participant evidence exist; canonical narrative and motive engines do not. |
| AI/Agents | `PARTIAL` | A bounded, read-only research assistant and versioned fixture-derived labels exist; universal attributable agent runs, tools, skills, and approval registries do not. |
| Autonomous execution | `DISABLED` | No autonomous live trading authority exists. |
| Production live broker transport | `ABSENT` | It is not implemented or operationally accepted. Historical live-canary frameworks use mock transport and do not establish production transport. |

`PARTIAL` does not mean “half implemented.” It means useful, verified subsystem
foundations exist while a named universal program abstraction is missing. The
exact existing and missing parts are maintained in
[Master Architecture](MASTER_ARCHITECTURE.md).

## Live-readiness ladder

```text
REAL MARKET OBSERVATION
  != LIVE EXECUTION TRANSPORT
  != OPERATIONALLY ACCEPTED LIVE EXECUTION
  != AUTHORIZED LIVE SESSION
  != AUTHORIZED ORDER
  != BROKER FILL

BROKER FILL
  -> reconciliation into canonical state
```

No step grants the next. Release approval, qualification, prediction, provider
availability, or an execution-mode setting cannot skip this ladder. Current
executable safety and authority sources are indexed in the
[Canonical Truth Map](CANONICAL_TRUTH_MAP.md).

## Maintenance rule

Any accepted milestone that materially changes program state must update
`PROGRAM_STATUS.md` as part of its acceptance scope. An update must cite the
new executable or accepted authority, preserve the prior historical cutoff,
and avoid copying mutable limits or counts into this document.
