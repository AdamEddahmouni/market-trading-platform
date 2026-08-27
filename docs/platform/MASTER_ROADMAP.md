# IMP master roadmap

| Field | Value |
|---|---|
| Document ID | `IMP-MASTER-ROADMAP` |
| Classification | `CANONICAL` |
| Lifecycle Status | `CANONICAL` |
| Truth Class | `CURRENT_CANONICAL_TRUTH` and `APPROVED_FUTURE_DESIGN` |
| Canonical Subject | Active post-core program sequencing and dependencies |
| Owner Role | IMP program architecture owner |
| Version | `1.0.0` |
| Last Verified | 2026-08-27 |
| Establishing Milestone | `IMP-REBASE-01` |
| Supersedes | Historical roadmaps as sources of current post-core planning |
| Superseded By | None |

BUILD01-35 is preserved as the **ORIGINAL CORE ARCHITECTURE CAMPAIGN** with
historical status `COMPLETE_WITH_LIMITATIONS`. Its historical details remain in
their accepted artifacts and are not rewritten here.

> This document is canonical for program-level interpretation and architecture. Where executable behavior is controlled by a designated schema, policy, gate, manifest, registry, or authority implementation, that executable authority controls within its defined scope.

## Independent active tracks

```text
EVIDENCE TRACK

EVIDENCE-01B
    -> EVIDENCE-01C
        -> EVIDENCE-01D
            -> EVIDENCE-01E

PROGRAM PLATFORM TRACK

IMP-REBASE-01
    -> IMP-REBASE-02
        -> IMP-OF-01
            -> IMP-OF-02
```

The EVIDENCE track is semantically independent. EVIDENCE-01C does **not**
depend on REBASE-02, OF-01, RT-01, or XA-01. Future integration requires its own
approved change and must preserve the frozen campaign's policy and exclusion
semantics.

## Post-core dependency graph

```text
IMP-REBASE-02
    -> IMP-OF-01
        -> IMP-OF-02
            -> IMP-OF-03

IMP-REBASE-02
    -> IMP-RT-01
        -> IMP-RT-02
            -> IMP-RT-03 only if measurement justifies it

IMP-REBASE-02
    -> IMP-XA-01
        -> IMP-XA-02 and bounded domain branches

IMP-OF-01 + IMP-RT-01
    -> instrumentation can emit durable run/artifact references

IMP-OF-01 + IMP-XA-01
    -> first admitted cross-asset source emits attributed runs

IMP-OF-01
    -> IMP-AI-01 attributable read-only AI runs

IMP-OF-03 + IMP-AI-01
    -> IMP-AI-02 governed workflow/tool/skill expansion

IMP-XA-01 + IMP-AI-01
    -> IMP-NARRATIVE-01
```

RT-01 and XA-01 may proceed in parallel after REBASE-02. OF-03 follows the
ledger and adapter foundations rather than blocking measurement or kernel
design. AI-01 requires attributable read-only runs and may prepare alongside
OF work, while AI-02 depends on OF-03's governed workflow/control registry.

## Milestone handoffs

| Milestone | Required outcome | Explicit non-outcome |
|---|---|---|
| `IMP-REBASE-02` | Standards for run attribution, artifact identity, code/data/model/config provenance, attempts/retries, logs, metrics, traces/correlation, evaluation, benchmarks, and documentation validation | Does not implement the full Operating Fabric |
| `IMP-OF-01` | Minimal append-only run and artifact identity/index with source/code/config/data attribution, parent-child links, and immutable outcome/disposition; validation is the first adapter | Does not replace existing evidence, validation, or artifact records |
| `IMP-OF-02` | Provider-smoke, replay/research, model, and EVIDENCE-reference adapters | Does not rewrite frozen EVIDENCE records |
| `IMP-RT-01` | Current-path stage measurements and reproducible benchmark harness from provider receipt through downstream action/broker stages where present | Does not redesign the bus or implement tracing in REBASE-01 |
| `IMP-XA-01` | Canonical identity, temporal/provenance compatibility, source-admission template, and bounded sovereign-rates reference scope | Does not implement universal cross-asset schemas/adapters in REBASE-01 |
| `IMP-OF-03` | Registry/indexes for existing workflows, capabilities, SOPs, incidents, and debt with owners and lifecycle | Does not force heterogeneous workflows into one engine |
| `IMP-AI-01` | Attributable, source-aware, read-only AI runs with prompt/evidence/tool lineage and claim-citation evaluation | Does not grant execution authority |

Production live broker transport and autonomous execution remain separate
safety and qualification programs. No roadmap item here authorizes either.
