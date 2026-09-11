# ADR-0012: News strategy evaluation laboratory

**Status:** Accepted  
**Date:** 2026-09-09  
**Context:** Professor-directed post-G15 increment 3

## Decision

Implement a canonical **non-executable** news intelligence strategy evaluation laboratory in `intelligence/news_strategy_evaluation/` that:

1. Freezes decision-time information in `StrategyFeatureSnapshot`
2. Applies versioned baseline and AI-enhanced policies (AI as feature, not authority)
3. Measures subsequent realized outcomes over explicit horizons
4. Reports baseline comparison, calibration, and AI incremental delta
5. Records `EvaluationShadowRecord` without broker/Paper submit authority
6. Replays deterministically from fixture packs

Initial empirical lane: **ES futures equity index** (not MES-specific; MES absent from spec registry).

## Rationale

- Prior increments delivered deterministic news foundation and analysis-only intelligence boundary
- Professor program requires outcome measurement before Paper forward testing
- Existing IMP facilities (P6 shadow, walk-forward research, Paper qualification) serve different planes — extend via new package rather than conflate with execution

## Consequences

### Positive

- Event-time-safe evaluation with poison tests
- Reproducible experiment records and hashes
- Clear bridge boundary for future Paper preview integration

### Negative / deferred

- No durable persistence yet
- Fixture-only empirical validation in this increment
- No live shadow runtime validation required for software acceptance

## Safety invariants

- No MODE_AUTHORITY changes
- No order/preview/broker path
- No automatic prompt or policy mutation

## Alternatives considered

| Alternative | Rejected because |
|-------------|------------------|
| Bolt into `inference/` | Violates ADR-0011 analysis-only boundary |
| Reuse donor MES executor rules | Donor strategy is audit input, not authority |
| New Paper shadow submit path | Would cross execution boundary |

## Related

- ADR-0010, ADR-0011
- [NEWS_STRATEGY_EVALUATION.md](../NEWS_STRATEGY_EVALUATION.md)
