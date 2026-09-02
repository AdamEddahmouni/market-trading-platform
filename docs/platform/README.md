# Integrated Market Platform documentation

| Field | Value |
|---|---|
| Document ID | `IMP-PLATFORM-INDEX` |
| Classification | `CANONICAL` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Program documentation navigation |
| Establishing Milestone | `IMP-REBASE-01` |
| Version | `1.0` |
| Last Verified | `2026-08-27` |
| Supersedes | No single current program-documentation index |
| Superseded By | None |

The Integrated Market Platform (IMP) is a safety-oriented market research and
supervised-execution foundation. It combines governed market observations,
point-in-time data handling, intelligence and prediction records, evidence and
settlement, opportunity and risk controls, execution-state machinery,
reconciliation, operational controls, and read-only user surfaces. It is not an
autonomous trading system. Production live broker transport is absent, live
sessions require human authorization, and each candidate order requires human
confirmation.

Program documentation is canonical for its declared explanatory subject. When
an executable schema, policy, gate, registry, manifest, frozen policy, or
implementation authority governs behavior, that source controls within its
scope.

## Read truth by class

- `CURRENT_CANONICAL_TRUTH` explains the accepted program state now and routes
  to the sources that control behavior.
- `HISTORICAL_TRUTH` records what happened or was accepted at a named cutoff;
  current prose cannot rewrite it.
- `APPROVED_FUTURE_DESIGN` states accepted direction only. It is not
  implementation, qualification, production eligibility, or authorization.

## Canonical documents

| Question | Canonical document |
|---|---|
| What is accepted now? | [Program Status](PROGRAM_STATUS.md) |
| How does the program fit together? | [Master Architecture](MASTER_ARCHITECTURE.md) |
| What comes next and what depends on what? | [Master Roadmap](MASTER_ROADMAP.md) |
| Which source controls a topic? | [Canonical Truth Map](CANONICAL_TRUTH_MAP.md) |
| Which subsystem owns a responsibility? | [System Boundaries](SYSTEM_BOUNDARIES.md) |
| What may inform, permit, authorize, execute, or reconcile? | [Authority Model](AUTHORITY_MODEL.md) |
| How are evidence, claims, inferences, narratives, and model outputs treated? | [Data and Epistemic Model](DATA_AND_EPISTEMIC_MODEL.md) |
| How are documents classified and kept current? | [Documentation Standard](DOCUMENTATION_STANDARD.md) |
| What does a controlled term mean? | [Glossary](GLOSSARY.md) |

## Recommended reading order

Start with [Program Status](PROGRAM_STATUS.md), then read
[Master Architecture](MASTER_ARCHITECTURE.md) and
[Authority Model](AUTHORITY_MODEL.md). Use
[Canonical Truth Map](CANONICAL_TRUTH_MAP.md) whenever a claim depends on an
executable or historical source. Read [Master Roadmap](MASTER_ROADMAP.md) for
future work only.

Historical BUILD, repository-closure, and EVIDENCE records remain in their
original artifact families. The accepted audit that established this routing is
[IMP-REBASE-00](../../artifacts/imp-rebase/REBASE00/README.md).
