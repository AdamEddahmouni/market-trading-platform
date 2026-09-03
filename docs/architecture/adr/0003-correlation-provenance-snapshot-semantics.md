# ADR-0003: Correlation, Provenance, and Snapshot Semantics

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-08-31 (extended 2026-09-01 for source_time) |

## Context

Multiple overlapping identifiers caused confusion between routing handoffs, audit linkage, and persisted historical context.

## Decision

| Concept | Role |
|---------|------|
| `correlation_id` | Stable decision thread ID across draft → trace |
| Provenance encoding | Parsed from `correlation_id` / draft metadata (lane, attention) |
| `decision_source_snapshot` | Immutable bounded context at submit |
| `source_time` | Immutable capture time of source context (distinct from `created_time`) |

## Consequences

- Portfolio/trace can show historical context without implying current signal validity
- Legacy records without snapshot or source_time remain valid

## References

- [DATA_CONTRACTS.md](../DATA_CONTRACTS.md)
- [Source snapshot completion](../../superpowers/plans/2026-08-31-paper-decision-source-snapshot-completion.md)
- [Source time completion](../../superpowers/plans/2026-09-01-paper-decision-source-time-completion.md)
