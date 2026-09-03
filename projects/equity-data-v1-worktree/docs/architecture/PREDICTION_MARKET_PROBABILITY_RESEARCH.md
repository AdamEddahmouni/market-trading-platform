# Prediction Market Probability Research

**Status:** `PROPOSED` — future architecture guidance

**Authority:** Subordinate to Revision 3,
[MODEL_RESEARCH_AND_DATASETS.md](./MODEL_RESEARCH_AND_DATASETS.md), and
[2026-08-16-prediction-markets-expansion-design.md](../superpowers/specs/2026-08-16-prediction-markets-expansion-design.md)

## Purpose

Fair-probability estimation, calibration, model edge, and economic value — integrated
with existing research abstractions, not a parallel framework.

## Core abstraction

`OutcomeProbabilityModel`:

> Estimate the probability of a precisely defined prediction-market outcome using
> only information available at the evaluation time.

Integrates with: `ResearchDataset`, `FeatureSnapshot`, `ForecastTarget`,
`ForecastModel`, `TrainingManifest`, `Prediction`, `WalkForwardRun`,
`CalibrationReport`, `Experiment`, `StrategySpec`, `SimulationRun`.

## Model families (incremental — not build all at once)

- base-rate model
- Bayesian models
- logistic regression
- time-series probability model
- gradient boosting / calibrated ML
- ensemble models
- event-specific structured models
- domain-specific engines

Candidate domain engines (future): `ElectionPredictionModel`,
`EconomicReleaseModel`, `FedDecisionModel`, `SportsOutcomeModel`,
`CryptoEventModel`, `RegulatoryOutcomeModel`, `CorporateEventModel`,
`TechnologyOutcomeModel`.

A Fed outcome and an NFL game are different prediction problems. Use shared
infrastructure plus domain-specific models.

## Model input families

Each model uses only appropriate inputs:

| Family | Examples |
|---|---|
| Prediction microstructure | probability, spread, depth, volume, OFI, large trades, whale positions |
| News | verified reporting, source reliability, timing |
| Social / influence | actor statements, attention, sentiment, novelty |
| Traditional finance | prices, rates, options, macro |
| Crypto | spot, derivatives, on-chain |
| Domain structured | polls, indicators, sports stats, regulatory calendars, company data |

## Calibration (mandatory)

Prediction markets provide a clean calibration environment. Evaluate with:

- Brier score
- log loss
- reliability / calibration curves
- calibration error
- sharpness
- discrimination where appropriate

If the system states P=70%, events in comparable 70% buckets should resolve
positively roughly 70% of the time under valid evaluation.

Do not present arbitrary confidence scores as probabilities. Generic LLM
probability guesses are not calibrated engines.

## Market as baseline

Always benchmark against market probability at decision time. A complex model that
beats reality statistically but not the market at decision time may contain little
tradable information.

Closing-line / final-market benchmark: separate forecasting skill from trading skill.

## Model edge

For YES (verify venue payoff semantics):

```text
model probability = p
executable YES purchase price = a
expected friction = c
estimated edge ≈ p - a - c
```

For NO:

```text
estimated edge ≈ (1 - p) - NO_price - c
```

Use actual platform contract semantics — do not blindly apply simplified equations.

## Economic value chain

```text
Probability advantage
  → executable order-book price
  → spread → fees → slippage → latency
  → capital lockup → resolution uncertainty
  → expected net value
```

Time to resolution: research expected return, capital efficiency, opportunity cost.
Do not optimize solely for absolute contract edge.

## Model ensemble (long-term)

Potential architecture:

```text
base model + domain model + market-implied probability
  + microstructure + public information + participant evidence
```

Do not assume ensemble improvement — use ablation studies.

## Five-way ablation

Where participant data exists:

```text
MARKET ONLY
MODEL ONLY
MARKET + MODEL
MARKET + WHALES
MARKET + MODEL + WHALES
```

Determine whether participant data adds incremental economic value.

## Strategy abstention (model-related)

```text
ABSTAIN — insufficient edge
ABSTAIN — model outside trained domain
ABSTAIN — semantic ambiguity (resolution risk)
ABSTAIN — wide spread / low liquidity
```

## UI: model card semantics

Display: fair probability, executable YES price, raw difference, after-cost edge,
calibration quality, resolution risk. Never label as "guaranteed edge."

## First research track

> Can an independently calibrated event-probability model consistently identify
> prediction-market mispricing after realistic spread, fees, and latency?

Do not start with automatic trading.
