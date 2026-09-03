# Architecture Decision Records (ADR)

**Status:** Index for significant architectural decisions.

## When to write an ADR

- Cross-cutting design choice affecting multiple subsystems
- Safety or authority semantics
- Hard-to-reverse contract decisions

Do **not** backfill speculative ADRs. Link existing specs when they already capture the decision.

## Format

Use [0000-template.md](0000-template.md). Number sequentially: `0001-short-title.md`.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-mode-specific-surfaces.md) | Mode-specific surface architecture | Accepted |
| [0002](0002-paper-workspace-canonical-boundary.md) | Paper Workspace as canonical decision boundary | Accepted |
| [0003](0003-correlation-provenance-snapshot-semantics.md) | Correlation, provenance, and snapshot semantics | Accepted |
| [0004](0004-react-query-key-invariants.md) | React Query key semantic invariants | Accepted |
| [0005](0005-initial-bundle-budget.md) | Initial JavaScript bundle budget | Accepted |
| [0006](0006-lane-provenance-envelope.md) | Lane provenance envelope | Accepted |
| [0007](0007-operational-account-identity.md) | Operational account identity and snapshot isolation | Accepted |
| [0008](0008-operator-authentication-authorization.md) | Operator authentication and account-scoped authorization | Accepted |

## Related existing decisions

Formal ADRs also exist under `docs/superpowers/decisions/` (e.g. ADR-LIVE-001 observational boundary). This folder captures IMP UI/platformization decisions not yet in that tree.
