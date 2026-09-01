# ADR-0001: Mode-Specific Surface Architecture

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-08-31 |
| Supersedes | Shared `*Page.tsx` with inline mode gating |

## Context

A single page with inline Demo/Paper/Live conditionals became hard to test, reason about, and extend. Safety-sensitive controls risked leaking across modes.

## Decision

Each primary route uses `Mode*Route` → dedicated `Demo*Page`, `Paper*Page`, `Live*Page` with shared `*Observability` components for data display.

## Consequences

- Clearer authority boundaries per page
- More files, but consistent pattern across Now/Portfolio/Workspace/Explore/Research/Discover
- App integration tests navigate all mode variants

## References

- [Mode-specific surfaces completion](../../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md)
- [ARCHITECTURE.md](../ARCHITECTURE.md)
