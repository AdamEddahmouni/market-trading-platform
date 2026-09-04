# IMP-REBASE-02 acceptance evidence

Disposition: `IMP_REBASE_02_COMPLETE`

IMP-REBASE-02 establishes three canonical program standards governing run
identity, observability, and test/evaluation semantics across IMP. It is
documentation-only and grants no provider, policy, model, qualification,
release, risk, execution, broker, or autonomous-agent authority.

## Package

- [Acceptance report](REBASE02_ACCEPTANCE_REPORT.md) — implementation identity,
  document map, consistency matrix, validation, and acceptance judgment.
- [Known limitations](REBASE02_KNOWN_LIMITATIONS.md) — program limitations
  separated from limitations of this milestone.
- [Accepted-surface hashes](REBASE02_FILE_HASHES.json) — sorted SHA-256 and byte
  length for every accepted file except the manifest itself.

The implementation contract is the
[final REBASE-02 specification](../../../docs/superpowers/specs/2026-08-27-imp-rebase-02-reproducibility-observability-evaluation-operational-standards-implementation-spec.md).
Historical design evidence remains in the REBASE-02 design document. REBASE-01
and REBASE-00 acceptance packages remain authoritative for their cutoffs.

## Scope statement

This milestone does **not** implement:

- Universal Run Ledger or run-record runtime
- trace backend or OpenTelemetry integration
- artifact registry runtime
- workflow engine
- benchmark gating
- adaptive intelligence runtime
- EVIDENCE semantic changes

Primary downstream handoff: `IMP-OF-01` — Universal Append-Only Run and Artifact
Ledger.
