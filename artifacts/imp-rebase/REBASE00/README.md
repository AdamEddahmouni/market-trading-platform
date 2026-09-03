# IMP-REBASE-00 Program Truth Audit

Status: `IMP_REBASE_00_COMPLETE_WITH_LIMITATIONS`

Audit date: 2026-08-26

Starting source: `37326d682e48d74285b47dfdf870e71e6433af70`

Scope: documentation, architecture, authority, reproducibility, operations, future sequencing

Runtime semantics changed: no

This package separates three things the repository currently mixes: accepted historical truth, executable current truth, and approved future design. It is an audit and migration input, not a replacement architecture and not qualification evidence.

## Package

- `01_EXECUTIVE_TRUTH_AND_DECISIONS.md` — current program truth and decisions.
- `02_DOCUMENTATION_AUTHORITY_AND_MIGRATION.md` — inventory summary, precedence, drift, and future document dispositions.
- `03_ARCHITECTURE_REALITY_AND_REUSE.md` — executable boundaries, authority map, and reusable foundations.
- `04_REPRODUCIBILITY_AND_OPERATING_FABRIC.md` — tests, runs, models, data, workflows, operations, observability, and debt.
- `05_DOMAIN_BASELINES.md` — Evidence, cross-asset, real-time, narrative/motive, and AI/agent baselines.
- `06_GAPS_DEPENDENCIES_AND_SEQUENCE.md` — gap matrix, dependency graph, REBASE-01 scope, and proposed milestone sequence.
- `07_KNOWN_LIMITATIONS.md` — explicit uncertainty and audit limitations.
- `REBASE00_DOCUMENTATION_INVENTORY.json` — structured classification of 621 documentation/evidence surfaces.
- `REBASE00_FILE_HASHES.json` — package integrity manifest generated after final content is frozen.

## Reading rule

Facts are labeled `VERIFIED`, `INFERRED`, `PROPOSED`, or `UNKNOWN`. A historical BUILD or EVIDENCE artifact is authoritative only for its original subject and cutoff. It does not become current architecture merely because it is immutable.

## Non-authority statement

This package grants no execution, risk, release, provider-admission, dataset-admission, model-promotion, qualification, or evidence-sufficiency authority. Executable policies and frozen EVIDENCE contracts retain their existing authority.
