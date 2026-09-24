# IMP unified operator and research control plane

| Field | Value |
|---|---|
| Document ID | `IMP-UNIFIED-OPERATOR-RESEARCH-CONTROL-PLANE` |
| Classification | `CANONICAL` |
| Primary Truth Class | `APPROVED_FUTURE_DESIGN` |
| Canonical Subject | Product requirements for operating research, campaigns, experiments, and IMP development through governed UI workflows |
| Establishing Milestone | Product direction approved 2026-09-24 |
| Version | `1.0` |
| Last Verified | `2026-09-24` |
| Supersedes | None |
| Superseded By | None |

IMP should become the primary place to **use and operate IMP**. Engineering tools,
GitHub, provider services, schedulers, and model runtimes may remain backends.
Operators should progressively create, monitor, review, and preserve market
research and project work in IMP instead of reconstructing it from terminal
commands, agent chats, and scattered files. This is a target architecture, not
a claim that the listed UI or dispatch capabilities exist today.

## Two control planes

| Plane | Owns | Authority boundary |
|---|---|---|
| Trading | Market data, research use, campaigns, strategy state, Paper operations, monitoring, and future Live operations | Existing provider, evidence, qualification, risk, session, order, broker, and reconciliation gates remain independent. Live remains OFF under current authority. |
| Development | Source changes, isolated worktrees, validation, reviews, releases, documentation, project agents, and infrastructure jobs | May propose and execute only explicitly granted engineering operations; it cannot acquire trading or empirical authority by sharing an interface. |

Both planes may share navigation, identity, and read-only status projections.
Permissions, commands, audit trails, and consequences remain separate. The UI
is a client of existing authorities, never a new authority. A generalized web
terminal is not the default control surface.

## Research and experimentation workspace

The product should support a durable progression:

`observation -> hypothesis -> investigation -> experiment -> evaluated finding -> strategy candidate -> qualification campaign -> Paper -> separately authorized Live eligibility`.

Each promotion records the human decision and the evidence used. Failure and
inconclusive results remain searchable. An investigation can retain its
objective, assets, time range, sources, citations, contradictions, findings,
human notes, and attached agent work. A campaign holds its hypothesis,
protocol and frozen version, dependencies, required sessions, exclusions,
stopping rules, progress, observations, and evaluation. An experiment records
its frozen inputs, parameters, run attempts, outputs, comparisons, and
disposition. Dataset and artifact views show source, content version, point-in-
time lineage, transformations, use rights, and consumers.

These product objects reference the existing [run and artifact standard](../platform/REPRODUCIBILITY_AND_RUN_STANDARD.md)
and Operating Fabric. They do not create a competing run ledger or replace
frozen FTEP records. A campaign can span multiple runs and market sessions;
the run ledger records individual operations and attempts. Historical evidence
is indexed by reference and remains immutable under its own protocol.

## Typed operations and visible lifecycle

Recurring work should expose a stable machine-readable command or API, an
event and structured state, an audit trail, and a read model before gaining a
UI control. Candidate operations include `inspect campaign readiness`,
`create isolated worktree`, `run named validation suite`, `start approved
collector`, `compare experiment runs`, and `request independent research`.
Commands accept typed inputs, enforce allowed scopes and idempotency, and
return explicit reasons for refusal. Arbitrary shell text, agent suggestions,
or a green UI label do not bypass a gate.

Consequential work shows `PROPOSED -> REVIEWED -> APPROVED -> EXECUTED ->
VERIFIED`, with actor, timestamp, target identity, software version, and
outcome at each completed stage. Skipped or inapplicable stages must be
explicit. A pending approval is not execution. Agent output remains a proposal
or research artifact until a human and the relevant domain authority promote
it. Existing rules for Paper and Live remain controlling.

The Run Console should show collectors, campaigns, experiments, scheduled
jobs, agents, and relevant Paper processes with heartbeat, runtime identity,
data freshness, failure reason, and linked evidence. A work queue should show
dependencies and actionable versus blocked state. A missing process, stale
heartbeat, wrong SHA, unavailable credential, or future RTH window must appear
as a named blocker, not as a generic healthy or completed state.

## Reproducibility minimum

A consequential experiment or research run links its hypothesis and decision
cutoff to protocol version, dataset and frozen revision, code SHA, parameters,
environment, actor/agent attribution, timestamps, attempts, results, artifacts,
and final human disposition. Comparisons must retain conditions and baseline
identity. Point-in-time source facts and later knowledge remain distinguishable.
The [run standard](../platform/REPRODUCIBILITY_AND_RUN_STANDARD.md) controls
field semantics, evidence strength, retry, retention, and historical migration.

## Delivery sequence

1. Expose read-only campaign, run, artifact, dependency, and process status
   from current authorities; reconcile status rather than copying state into
   the UI. Existing frozen evidence remains read-only.
2. Add typed creation and dispatch for low-consequence research and controlled
   experiments, with durable run linkage and explicit failure states.
3. Add governed campaign setup, scheduling, evidence browsing, and approval
   flows only after their operation contracts and authority checks are tested.
4. Extend development controls for isolated work, validation, review, and
   release through separately permissioned adapters. Live-market controls
   require their own future qualification and authorization program.

Acceptance for each operation requires a defined owner, typed contract,
permission and refusal tests, audit evidence, readback, recovery semantics,
and UI states for pending, failed, stale, and completed work. No phase may
retroactively arm, backfill, or reclassify a frozen empirical campaign.
