# IMP master roadmap

| Field | Value |
|---|---|
| Document ID | `IMP-MASTER-ROADMAP` |
| Classification | `CANONICAL` |
| Primary Truth Class | `APPROVED_FUTURE_DESIGN` |
| Canonical Subject | Post-core milestone ownership and dependency graph |
| Establishing Milestone | `IMP-REBASE-01` |
| Version | `1.2` |
| Last Verified | `2026-08-29` |
| Supersedes | [Revision 3 roadmap projection](../roadmap/REVISION_3_ROADMAP.md) as whole-program master only |
| Superseded By | None |

This roadmap expresses intended direction and dependencies. Display order and
milestone numbering do not imply implementation, qualification, production
eligibility, or authorization. BUILD01-35 remains historical, and EVIDENCE is
an independent semantic track.

## Dependency vocabulary

- **Hard dependency:** the destination cannot safely satisfy its contract before
  the source is accepted.
- **Per-operation hard dependency:** the edge applies to each operation class,
  not to unrelated operation classes.
- **Parallel-safe after common foundation:** bounded preparation or
  implementation can proceed concurrently after the shared prerequisite.
- **Later integration dependency:** design may begin earlier, but accepted
  runtime integration must attach to the named foundation.
- **Soft dependency:** coordination is helpful but not acceptance-blocking.
  REBASE-01 establishes no soft dependency for EVIDENCE-01C.

## Milestone catalog

| ID | Canonical name | Boundary |
|---|---|---|
| `IMP-REBASE-02` | Reproducibility, Observability, Evaluation & Operational Standards | `COMPLETE` — shared standards established; do not implement Universal Run Ledger, adapters, workflow registry, end-to-end tracing, or documentation automation |
| `IMP-OF-01` | Append-Only Run and Artifact Ledger | Implement durable run identity, artifact linkage, history, attribution, relationships, and retry/attempt preservation |
| `IMP-OF-02` | Operation Adapters | Connect bounded operation classes to the accepted ledger without rewriting their frozen records |
| `IMP-RT-01` | End-to-End Instrumentation | `IMP_RT_01_COMPLETE_WITH_LIMITATIONS` — trace semantics, fixture baseline measurements, and ingest-path stage instrumentation; queue/signal/real-provider paths remain follow-ons |
| `IMP-RT-02` | Measured State and Feature Optimization | Optimize only bottlenecks demonstrated by RT-01 evidence |
| `IMP-RT-03` | Event-Bus or Native Hot-Path Decision | Decide only if measured need remains after RT-02 |
| `IMP-XA-01` | Cross-Asset Kernel | Define shared extension/source contracts and one bounded sovereign/rates reference vertical |
| `IMP-XA-02` | First Admitted Cross-Asset Source Vertical | Admit a bounded vertical under XA-01 and ledger requirements |
| `IMP-OF-03` | Workflow and Control Registry | `IMP_OF_03_COMPLETE_WITH_LIMITATIONS` — machine-readable capability/SOP/workflow registry; not an execution engine or second ledger |
| `IMP-AI-01` | Attributable Read-Only AI Research | Add reproducible attribution and evaluation while preserving no-execution authority |
| `IMP-AI-02` | Governed AI Workflows and Tools | Expand only after the workflow/control registry |
| `IMP-NARRATIVE-01` | Narrative and Motive Method | Define uncertain thesis/motive treatment and admitted boundaries |
| `EVIDENCE-01C` | Bounded Real-Provider Shakedown and Operational Acceptance | Produce the next EVIDENCE operational-acceptance record independently |

## Hard dependencies

| From | To | Meaning |
|---|---|---|
| `IMP-REBASE-01` | `IMP-REBASE-02` | Current terminology and ownership precede program-wide standards |
| `IMP-REBASE-02` | `IMP-OF-01` | Ledger implementation requires agreed run, artifact, outcome, disposition, and attempt semantics |
| `IMP-REBASE-02` | `IMP-RT-01` contract/design | Trace and benchmark work must use common correlation and reproducibility standards |
| `IMP-REBASE-02` | `IMP-XA-01` contract preparation | Cross-asset contracts must use common provenance, evaluation, and documentation standards |
| `IMP-OF-01` | `IMP-OF-02` | Adapters require an accepted ledger target |
| `IMP-OF-01` | `IMP-AI-01` | AI operations require durable attribution before expansion |
| `IMP-RT-01` | `IMP-RT-02` | Measure before optimizing |
| `IMP-RT-02` | `IMP-RT-03` | Event-bus or native-path decisions require measured need |
| `IMP-XA-01` | `IMP-XA-02` | A bounded admitted source requires the shared extension/source template |
| `IMP-OF-03` | `IMP-AI-02` | Governed AI workflow/tool expansion requires the workflow/control registry |

## Per-operation dependency

`IMP-OF-02 -> IMP-OF-03` is hard for each operation class: registry design may
begin after `IMP-REBASE-02`, but an operation class cannot receive an accepted
registry entry until its `IMP-OF-02` ledger adapter is demonstrated. An
unrelated adapter class does not block that entry.

## Parallel-safe branches

After `IMP-REBASE-02`, these bounded branches may proceed concurrently:

- `IMP-OF-01` ledger implementation;
- `IMP-RT-01` measurement-contract and benchmark preparation;
- `IMP-XA-01` contract preparation.

This does not make all runtime integration parallel-safe.

## Later integration dependencies

- `IMP-RT-01` runtime stages must attach to `IMP-OF-01` durable
  run/correlation identity, although measurement-contract work may begin
  earlier.
- `IMP-XA-02` admitted source runs must emit `IMP-OF-01` ledgered runs, although
  `IMP-XA-01` contract work may begin earlier.
- `IMP-NARRATIVE-01` should reuse XA identity/event relationships and AI
  attribution where its eventual admitted boundary requires them; this is later
  integration planning, not a dependency imposed on EVIDENCE.

## Exact handoffs

### IMP-REBASE-02

`COMPLETE`. Established reproducibility; operation taxonomy; run, attempt,
outcome, and disposition semantics; artifact identity and linkage; data,
model, config, and code provenance; retry-history preservation; retention and
redaction; structured logging and correlation/trace identity; evaluation and
benchmark reproducibility; documentation validation expectations; and
change/evidence workflow. Reconciled with existing `RunManifestV1`, validation
reports, subsystem ledgers, and frozen records. Did not implement the
Universal Run Ledger, adapters, workflow registry, end-to-end tracing, or
documentation automation.

### IMP-OF-01

Implement capabilities rather than speculative class names: durable run
identity, append-only outcome/disposition history, source/code/config/data
attribution, artifact association, parent-child relationships, and
attempt/retry preservation. Reuse existing evidence and validation patterns;
index immutable records rather than replacing them.

### IMP-RT-01

`IMP_RT_01_COMPLETE_WITH_LIMITATIONS`. Executable ingest-path tracing, named
latency profiles with root-to-terminal elapsed semantics, fixture baseline
evidence, and tracing OFF/ON domain equivalence are accepted. Queue workload,
signal path, real-provider observational trace, and unified
opportunity→risk→order_ready chain remain follow-ons rather than acceptance
blockers.

### IMP-XA-01

Establish canonical identity participation, temporal/provenance/quality
compatibility, relationship-extension requirements, a source-admission
template, and one bounded sovereign/rates reference vertical. Do not create a
universal financial ontology or treat macro series as tradable bond data.

### IMP-AI-01

Read-only means no authority to mutate canonical runtime or program state,
policies, risk, execution, release, provider admission, prediction, settlement,
or qualification state. AI research may read permitted sources and create
non-authoritative research artifacts and audit evidence. Promotion requires a
separately governed human decision.

## Independent EVIDENCE track

`EVIDENCE-01C` has no hard or soft dependency on `IMP-REBASE-02`, `IMP-OF-01`,
`IMP-OF-02`, `IMP-RT-01`, `IMP-XA-01`, `IMP-OF-03`, `IMP-AI-01`, or a
Narrative/Motive milestone. It may run in temporal parallel. Optional future
indexing may reference its frozen records without changing campaign semantics,
qualification rules, or the historical record.

```text
EVIDENCE-01 -> EVIDENCE-01A -> EVIDENCE-01B -> EVIDENCE-01C
     independent of the REBASE / OF / RT / XA / AI dependency graph
```
