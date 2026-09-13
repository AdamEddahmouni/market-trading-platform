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

Mint path (Path A): MATCHED `StrategyMatch` → `bridge_strategy_match_to_opportunity` → `OpportunityEngine.assess` → persist assessment always, `OpportunityV1` only on `EMIT`. Bounded Paper/Demo `PathAScanCaller` runs the existing `UniversalStrategyScanner` library once and mints through that path. The one-shot CLI `tools/path_a_prospective_run.py` injects `PathAScanCaller` via `build_paper_demo_path_a_invoke` (Paper/Demo only), which now registers the real (non-fixture) baseline strategy catalog (`build_paper_demo_strategy_catalog`, `strategy/path_a_strategy_catalog.py`): the existing `FORECAST_MOMENTUM` / `WHALE_ALIGNED` / `WHALE_CONTRARIAN` baseline-only interpretations (`strategy/evaluation.py`) evaluated through the real production `interpret_strategy` evaluator against the real fetched quote when available. Catalog evaluators never call `build_preregistration`. `build_paper_demo_path_a_invoke` may load a previously persisted Phase-6 record (`strategy/path_a_preregistration_store.py`) only when identity matches the spec and `registered_at` is before quote `event_time_ns`; otherwise `preregistration=None` and entries abstain (`ABSTAIN_NO_PREREGISTRATION`) — honest `EMPTY` / `NO_MATCHED_STRATEGY`. A lawful scanner MATCHED still cannot OE-EMIT: the honesty invoke leaves `forecast_resolver` returning `None` (`FORECAST_UNAVAILABLE`). That is not a tradable edge, not item 7 PROVED, and not a fixture `ForecastV1`. The MATCHED loop (bridge/OE) is not entered on honest EMPTY. A Paper/Demo MATCHED test fixture on `PathAProspectiveComposer` does invoke `OpportunityEngine.assess`; if G7 fail-closes, overall status stays `G7_NOT_ACTIONABLE` even when Path A is `MINTED`. That fixture is software proof, not an empirical MATCHED hop. Optional PD-09 schema v6 persist is a later hop on `PathAProspectiveComposer` after MINTED Paper results (`ForwardTestService.create_decision` + `forward_test_signal_links`); persist-off stays `INTENTIONAL_EPHEMERAL`. It is not a daemon, not Live, not FTEP empirical, and not `StrategyPaperRuntime` workstation wiring. Goal 001 ingest remains a review assembler over already-minted rows.

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
