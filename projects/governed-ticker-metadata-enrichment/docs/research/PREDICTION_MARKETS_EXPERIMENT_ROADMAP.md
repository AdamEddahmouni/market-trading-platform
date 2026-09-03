# Prediction Markets Experiment Roadmap

**Status:** `PROPOSED` — not authorized until feasibility and ADR acceptance

**Authority:** Subordinate to
[2026-08-16-prediction-markets-expansion-design.md](../superpowers/specs/2026-08-16-prediction-markets-expansion-design.md)

## Purpose

Preregistered research sequence for prediction-market domains. No experiment
authorizes trading or implementation.

## Research tracks (ordered)

### Track 1 — Model mispricing (first)

**Question:** Can an independently calibrated event-probability model consistently
identify prediction-market mispricing after realistic spread, fees, and latency?

**Method:** `OutcomeProbabilityModel` with walk-forward evaluation, calibration
reports, executable-price edge, simulation with friction. Benchmark against market
at decision time.

**Do not start with automatic trading.**

### Track 2 — Public participant intelligence (second)

**Question:** Do historically skilled, domain-specialist participants contain
incremental predictive information **after activity becomes publicly observable**?

**Method:** Point-in-time `ParticipantTrackRecord`, copy-latency measurement,
five-way ablation including `MARKET + WHALES`. Polymarket-style public wallet data
where lawful; Kalshi anonymous flow features only where identity unavailable.

### Track 3 — Cross-asset intelligence (third)

**Question:** Do changes in prediction-market probabilities contain incremental
point-in-time information for related equities, futures, or crypto?

**Method:** `MarketImpliedProbabilityFeature`, event studies with PIT joins,
lead/lag analysis, probability velocity features. Test macro, regulation, elections,
corporate events separately.

### Track 4 — Cross-platform disagreement (fourth)

**Question:** When legitimately comparable contracts diverge across venues, which
market leads and does an executable convergence opportunity remain?

**Method:** `CanonicalRealWorldEvent` mapping with `settlement_equivalent` checks,
cross-venue lead/lag, structural consistency engine, executable arbitrage simulation
with full friction and semantic risk.

## Strategy family experiments (after infrastructure)

Preregister before each:

| Family | Prerequisite |
|---|---|
| Model mispricing | Track 1 positive or informative null |
| Model + whale agreement | Tracks 1–2 |
| Whale following | Track 2 + replay |
| Whale disagreement | Track 2 |
| Cross-venue dislocation | Track 4 |
| Event reaction | Influence + Track 3 |
| Prediction as asset signal | Track 3 |
| Relative consistency | Cross-market consistency engine |
| Market making | Simulation extensions + entitled execution |

## Five-way ablation protocol

```text
MARKET ONLY
MODEL ONLY
MARKET + MODEL
MARKET + WHALES
MARKET + MODEL + WHALES
```

Run on suitable markets with sufficient sample and explicit abstention logging.

## False-edge red team

Each experiment survives: leakage, hindsight, leaderboard leakage, survivorship,
retroactive labels, fee/liquidity omissions, impossible latency, unrealistic fills,
resolution blindness, semantic equivalence errors, hedge blindness, MM misclassification.

## Null results

Informative null results are successful outcomes. Document why edge was absent.

## Related documents

- [PREDICTION_MARKETS_FEASIBILITY_STUDY_PLAN.md](./PREDICTION_MARKETS_FEASIBILITY_STUDY_PLAN.md)
- [PREDICTION_MARKET_PROBABILITY_RESEARCH.md](../architecture/PREDICTION_MARKET_PROBABILITY_RESEARCH.md)
- [PREDICTION_MARKET_WHALE_INTELLIGENCE.md](../architecture/PREDICTION_MARKET_WHALE_INTELLIGENCE.md)
- [PREDICTION_MARKETS_EXPANSION_TRACK.md](../roadmap/PREDICTION_MARKETS_EXPANSION_TRACK.md)
