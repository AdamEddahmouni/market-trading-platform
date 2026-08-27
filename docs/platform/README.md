# Integrated Market Platform canonical documentation

| Field | Value |
|---|---|
| Document ID | `IMP-PLATFORM-INDEX` |
| Classification | `CANONICAL` |
| Lifecycle Status | `CANONICAL` |
| Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Program documentation entry point |
| Owner Role | IMP program architecture owner |
| Version | `1.0.0` |
| Last Verified | 2026-08-27 |
| Establishing Milestone | `IMP-REBASE-01` |
| Supersedes | Root and historical roadmaps as sources of current whole-program interpretation |
| Superseded By | None |

The Integrated Market Platform (IMP) is a governed market-research,
intelligence, evidence, and supervised-execution foundation. Its original core
architecture campaign is historically `COMPLETE_WITH_LIMITATIONS`; repository
closure is complete; evidence maturation is active through EVIDENCE-01B with
EVIDENCE-01C next. Several broader program families have reusable foundations
but no universal program abstraction and are therefore `PARTIAL`.

IMP's current safety posture is explicit: autonomous live execution is
disabled, a human must authorize any live session and confirm every order,
automatic broker failover is disabled, and no production live broker transport
is implemented or operationally accepted.

> This document is canonical for program-level interpretation and architecture. Where executable behavior is controlled by a designated schema, policy, gate, manifest, registry, or authority implementation, that executable authority controls within its defined scope.

## Truth classes

- `HISTORICAL_TRUTH` records what was accepted for a stated milestone and
  cutoff.
- `CURRENT_CANONICAL_TRUTH` explains the program as it is currently understood.
- `APPROVED_FUTURE_DESIGN` records accepted direction without claiming that the
  design is implemented.

Current canonical documents outrank historical documents for current program
interpretation. A frozen historical artifact remains authoritative for what
actually happened at its accepted cutoff.

## Canonical document map

| Read for | Canonical document |
|---|---|
| Whole-program shape and future attachment points | [Master Architecture](MASTER_ARCHITECTURE.md) |
| Current maturity and safety posture | [Program Status](PROGRAM_STATUS.md) |
| Active post-core sequencing | [Master Roadmap](MASTER_ROADMAP.md) |
| Topic-to-authority routing | [Canonical Truth Map](CANONICAL_TRUTH_MAP.md) |
| Subsystem responsibilities | [System Boundaries](SYSTEM_BOUNDARIES.md) |
| Information, human, execution, and broker authority | [Authority Model](AUTHORITY_MODEL.md) |
| Evidence classes and analytical method | [Data and Epistemic Model](DATA_AND_EPISTEMIC_MODEL.md) |
| Precedence, lifecycle, and anti-drift rules | [Documentation Standard](DOCUMENTATION_STANDARD.md) |
| Controlled program terminology | [Glossary](GLOSSARY.md) |

Recommended reading order is this index, Program Status, Master Architecture,
Authority Model, and then the subject-specific documents. Historical BUILD,
Phase, EVIDENCE, and acceptance artifacts remain in their original locations;
approved future systems are identified as future design and are not presented
as runtime capability.
