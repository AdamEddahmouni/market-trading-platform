# ADR-0010: News Catalyst Deterministic Foundation

*Status: Accepted — professor-directed post-G15 increment*

## Context

The Claude Code News donor audit (SRC-006) validated that deterministic collection, filtering, and event-time discipline must precede any AI or execution layer. IMP already had read-only news aggregation (`news/aggregator.py`) but lacked explicit publication/retrieval semantics, governed source/catalyst policy, and replay-safe filtering.

## Decision

Extend `src/market_platform_foundation/news/` with:

- `NewsArticleEvent` canonical contract with separate `published_time` and `retrieved_time`
- `SourceTrustCatalog` and `CatalystRegistry` policy models
- Composable filter chain: observability → dedupe → recency → source → catalyst
- `NewsReplayHarness` for event-time-safe as-of replay
- `NewsIntelligenceService` as read-only downstream boundary

No AI inference, broker calls, or Live execution changes.

## Safety consequences

- MODE_AUTHORITY, Paper lifecycle, preview/risk, and account isolation unchanged
- `NewsIntelligenceService` is observational only (`read_only=True`, `execution_authority=False`)
- Donor Tradovate/CDP/Anthropic paths are not imported

## Deferred

- Paper strategy signal generation
- Production persistence / append-only event log for inference records
- Live wire provider integrations (PR Newswire, Benzinga, etc.)
- BUILD 09 `NEWS_EVENT` detector wiring into intelligence routing

## References

- [NEWS_EVENT_FOUNDATION.md](../NEWS_EVENT_FOUNDATION.md)
- [CCN forensic audit](../../audits/post-g15-professor-directed/CCN_FORENSIC_AUDIT_2026-09-09.md)
- [DATA_CONTRACTS.md](../DATA_CONTRACTS.md)
