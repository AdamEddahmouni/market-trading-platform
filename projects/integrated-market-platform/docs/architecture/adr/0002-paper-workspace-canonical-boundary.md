# ADR-0002: Paper Workspace as Canonical Decision Boundary

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-08-31 |

## Context

Paper Command surfaced candidates but direct submit would skip decision context, preview, and revalidation.

## Decision

- Paper Command **hands off** to Workspace with draft + `sourceContext`
- Workspace cockpit is the canonical place for preview → submit
- Paper Command cannot submit orders directly

## Consequences

- Extra navigation step; stronger audit trail and operator clarity
- Unified handoff for attention and lane origins

## References

- [PAPER_DECISION_LIFECYCLE.md](../PAPER_DECISION_LIFECYCLE.md)
- [Command → Workspace handoff completion](../../superpowers/plans/2026-08-31-paper-command-workspace-handoff-completion.md)
