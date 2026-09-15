# Strategy research promotion registry

Governed registry for strategy research promotion evidence. Research runs and
parity artifacts may advance **review eligibility** only; they do not grant
Paper or Live execution authority.

## Lifecycle

`DISCOVERED` → `RUNNABLE` → `PARITY_CHECKED` → `HISTORICAL_VALIDATED` →
`OOS_VALIDATED` → `RESEARCH_APPROVED` → `FTEP_ELIGIBLE` → `FTEP_TESTING` →
`PROMOTION_REVIEW` (or `REJECTED` from any prior state).

Transitions fail closed when required evidence fields or parity artifacts are
missing. Numerical thresholds on research metrics never auto-activate Paper or
Live.

## Code

- Types: `market_platform_foundation.intelligence.promotion.research_types`
- Registry: `market_platform_foundation.intelligence.promotion.research_registry`
- Serialization: `market_platform_foundation.intelligence.promotion.research_serialization`

## Relationship to execution eligibility

`strategy.eligibility` remains the sole execution-intent predicate (preregistration,
BUILD 20 champion promotion, forward evidence class). The research promotion
registry is subordinate: MATLAB, PineTS, Edge Stats, options-flow, and Grok
research paths must still pass canonical eligibility and risk boundaries before
any order-ready intent.

## Acceptance

Software acceptance label: `STRATEGY_RESEARCH_PROMOTION_REGISTRY_READY`
(`tests/intelligence/test_strategy_research_promotion_registry.py`).
