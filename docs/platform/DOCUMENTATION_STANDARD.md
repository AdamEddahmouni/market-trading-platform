# IMP documentation standard

| Field | Value |
|---|---|
| Document ID | `IMP-DOCUMENTATION-STANDARD` |
| Classification | `CANONICAL` |
| Lifecycle Status | `CANONICAL` |
| Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Documentation truth, lifecycle, precedence, and anti-drift rules |
| Owner Role | IMP documentation governance owner |
| Version | `1.0.0` |
| Last Verified | 2026-08-27 |
| Establishing Milestone | `IMP-REBASE-01` |
| Supersedes | Ad hoc program-level documentation precedence |
| Superseded By | None |

This standard applies prospectively to new or materially revised program and
supporting documentation. It does not mechanically relabel or rewrite frozen
historical artifacts.

> This document is canonical for program-level interpretation and architecture. Where executable behavior is controlled by a designated schema, policy, gate, manifest, registry, or authority implementation, that executable authority controls within its defined scope.

## Independent classification axes

### Truth classes

| Class | Meaning |
|---|---|
| `HISTORICAL_TRUTH` | What was accepted or observed for an identified subject and cutoff. |
| `CURRENT_CANONICAL_TRUTH` | The current authoritative program-level explanation. |
| `APPROVED_FUTURE_DESIGN` | Accepted direction that must not be represented as implemented. |

### Lifecycle classes

| Class | Meaning |
|---|---|
| `CANONICAL` | Current program authority for its declared subject. |
| `HISTORICAL` | Preserved record whose authority is bounded to its subject and cutoff. |
| `ACTIVE_SUPPORTING` | Maintained subsystem explanation verified against current authority. |
| `RUNBOOK` | Environment- or operation-scoped procedure. |
| `REFERENCE` | Descriptive lookup material that does not independently authorize behavior. |
| `GENERATED` | Mechanically derived output whose source and generation context control. |
| `EXPERIMENTAL` | Proposal, research, or unaccepted design. |
| `SUPERSEDED` | Retained content replaced for its former current subject by an explicit successor. |

`STALE` is an audit finding, not a desired stable lifecycle class.

### Maturity vocabulary

Use `PLANNED`, `DESIGNED`, `IMPLEMENTED`, `VALIDATED`,
`OPERATIONALLY_ACCEPTED`, `QUALIFIED`, `PRODUCTION_ELIGIBLE`, or `DEPRECATED`.
Use `WITH_LIMITATIONS`, `BLOCKED`, or `AWAITING_EXTERNAL_EVIDENCE` only as
explicit qualifiers. Historical milestone labels remain unchanged inside
historical records.

## Precedence

For the subject directly controlled, precedence is:

1. Executable schemas, policies, gates, registries, and validation manifests.
2. Accepted hashed authority manifests and explicitly scoped frozen policies.
3. Current canonical program documents under `docs/platform/`.
4. Active supporting subsystem documents verified against code.
5. Runbooks and environment-scoped operational references.
6. Experimental designs and research proposals.
7. Immutable historical BUILD, Phase, and EVIDENCE artifacts for their original
   subject and cutoff.

For current program interpretation, current canonical documents outrank
historical documents. For what actually happened at an accepted historical
cutoff, the frozen artifact remains authoritative for that historical fact.
For example, `MASTER_ARCHITECTURE.md` cannot reinterpret what BUILD26 accepted,
and BUILD26 cannot override current whole-program architecture.

Recency alone does not override a frozen contract. A same-level conflict is
unresolved until an explicitly authorized reconciliation identifies the
controlling source and disposition.

## Anti-drift rule

Canonical summaries may explain executable authority but must not become
independently maintained copies of mutable values. Qualification thresholds,
risk limits, provider capability matrices, policy identifiers, validation and
test counts, model registry values, and future workflow registry values must be
referenced or generated from the controlling source. Historical examples are
permitted only when labeled with their subject and cutoff.

## Canonical metadata

New canonical Markdown documents begin with a compact table containing:

- document ID;
- classification;
- lifecycle status;
- canonical subject;
- owner role;
- version;
- last verified date;
- establishing milestone;
- supersedes; and
- superseded by.

A truth-class field is recommended. Canonical document identity must not depend
on a transient HEAD SHA; exact Git identities belong in milestone acceptance
evidence. When behavior is executable, include the standard executable-authority
disclaimer used by this canonical layer.

## Change and preservation rules

- Update [Program Status](PROGRAM_STATUS.md) whenever an accepted milestone
  materially changes program state.
- Update architecture, roadmap, boundaries, authority, and glossary documents
  only when their declared subjects change.
- Preserve BUILD, Phase, EVIDENCE, settlement, prediction-ledger, release,
  closure, and CLEANUP evidence. Supersede by reference rather than rewriting.
- Keep the active EVIDENCE campaign semantically isolated from program-platform
  work unless a separately approved change explicitly integrates them.
- Validate links, referenced repository paths, JSON, hashes, consistency,
  protected-history diffs, whitespace, and repository policy before acceptance.
- When a canonical run, workflow, capability, skill, or SOP registry exists,
  link or generate views from it; do not describe a future registry as current.
