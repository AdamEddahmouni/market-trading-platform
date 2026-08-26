# Governed Opportunity Engine (BUILD 21)

> BUILD 21 converts governed champion forecasts into point-in-time, quality-aware opportunity candidates. An `OpportunityV1` is permission to enter deterministic execution/risk consideration, not permission to trade.

## Build boundaries

| Build | Responsibility |
| --- | --- |
| BUILD 20 | Champion authority — which system is champion |
| BUILD 21 | Opportunity authority — whether a champion forecast is economically interesting enough for execution/risk consideration |
| BUILD 22 | Paper execution / deterministic risk — sizing, portfolio, orders |

```text
prediction ≠ opportunity automatically
opportunity ≠ trade
OpportunityV1 ≠ TradeProposalV1
OpportunityV1 ≠ order
OpportunityV1 ≠ execution authority
```

## Core pipeline

```text
ChampionAssignmentV1 → ForecastV1 → OpportunityContext → OpportunityPolicyV1
  → OpportunityAssessmentV1 → OpportunityV1 (if EMIT)
```

Every forecast evaluation produces a durable `OpportunityAssessmentV1`. Only eligible assessments emit `OpportunityV1`.

## OpportunityV1 (reused BUILD 01 contract)

- Reused unchanged for BUILD 21 semantics.
- `created_at_ns` = opportunity decision time.
- `valid_until_ns` = logical expiry (forecast horizon boundary and/or policy lifetime).
- `side` = LONG or SHORT from forecast probability (no NEUTRAL opportunities).
- `expected_return` / `expected_net_edge` remain unset for direction-only forecasts.
- No execution fields (quantity, broker, order type).

## Champion lineage

Opportunities require:

1. Forecast lineage matches governed champion (`champion_candidate_id` / `candidate_artifact_hash`).
2. Champion assignment effective at `forecast.decision_time_ns`.
3. Same champion assignment still authoritative at `opportunity_decision_time_ns` (v1 rule: suppress if champion changed).

Control and challenger/shadow forecasts do not create production opportunities.

## Time semantics

- `forecast.decision_time_ns <= opportunity_decision_time_ns` (hard integrity).
- `forecast_age_ns = opportunity_decision_time_ns - forecast.decision_time_ns`.
- Forecast expired when `opportunity_decision_time_ns >= forecast_expiry_ns`.
- At exact expiry boundary: no new opportunity.

## Point-in-time context

All context inputs must satisfy `available_time_ns <= opportunity_decision_time_ns`.

Never use unbounded “latest” queries in the opportunity core.

## Probability view

Uses BUILD 14 / BUILD 16 `ProbabilityView`:

- `RAW`, `CALIBRATED`, `OPERATIONAL` (default for production policy).
- No silent fallback when calibrated is required but missing.

## Probability edge

For symmetric binary `direction_up_down` with `p_up`:

- LONG edge = `p_up - reference` (default reference 0.5).
- SHORT edge = `(1 - p_up) - reference`.

**Dimensional integrity:** probability edge is dimensionless. Spread and fees are in basis points. Never subtract `spread_bps` from probability.

## Economic value

BUILD 21 does not claim expected monetary return from directional probability alone. Direction-only forecasts mark `economic_value_status = UNAVAILABLE_DIRECTION_ONLY`. Magnitude-aware economics only when `ForecastEstimate.expected_value` exists.

## Quality / capability

BUILD 04 `QualityDecision` is authoritative:

- `FAIL_CLOSED` → no opportunity.
- `ABSTAIN` → no opportunity.
- `DEGRADE` → policy-controlled.

## Uncertainty / OOD

BUILD 14 uncertainty fields are reused. OOD forecasts suppressed by default.

## Liquidity

Spread gate uses PIT `spread_bps` from BUILD 06 signals. Depth imbalance is context only — not a liquidity level.

## Persistence

- `opportunity_policies` — immutable policy records.
- `opportunity_assessments` — every assessment auditable.
- `opportunities` — eligible opportunities only.
- No Mongo TTL. Logical expiry ≠ record deletion.

## Replay

Historical replay resolves champion assignment and market context as-of historical decision time. Current champion or current market state must not affect historical assessments.

## BUILD 22 handoff

BUILD 22 consumes:

- `OpportunityV1`, assessment lineage, champion assignment, forecast, direction, probability/edge, expiry, quality, uncertainty, spread context, optional economic estimate.

BUILD 22 adds portfolio state, sizing, risk limits, order construction, and paper execution.

BUILD 22 must reject expired `OpportunityV1` records rather than asking BUILD 21 to recreate them.
