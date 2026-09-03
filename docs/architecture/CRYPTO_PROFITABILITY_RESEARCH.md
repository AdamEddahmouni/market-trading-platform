# Crypto Profitability Research Framework

**Status:** `PROPOSED` — future architecture guidance

**Extends:** [MODEL_RESEARCH_AND_DATASETS.md](./MODEL_RESEARCH_AND_DATASETS.md)

## Economic objective

Optimize for **robust expected economic value after realistic costs and risk** —
not accuracy, hit rate, raw return, or backtest P&L alone.

```text
gross edge
- spread - fees - slippage - latency decay - market impact
- funding - borrow - adverse selection
= realistic expected edge
```

## Profitability hierarchy

1. Evidence quality
2. Reproducibility
3. Point-in-time correctness
4. Out-of-sample persistence
5. Net-of-cost expectancy
6. Risk-adjusted return
7. Drawdown
8. Tail risk
9. Capacity
10. Operational reliability

High gross return with unrealistic fills ranks below lower-return robust strategies.

## Expected value principle

A signal is useful only if it provides enough economic edge to compensate for
risk and cost. Direction prediction alone is insufficient.

Conceptually: `EV = P(win)×E[win] - P(loss)×E[loss] - E[cost]` — distributions
may require richer treatment than a single equation.

## Cost model

Parameterize and version every backtest/simulation run:

commission; transaction fees; maker/taker; regulatory fees; spread; slippage;
funding; borrow; market impact.

Never hard-code promotional broker pricing into research.

## Latency decay curves

For fast events, estimate edge at +0s, +1s, +2s, +5s, +10s, +30s, +60s.

If required latency is impossible with available infrastructure, **reject the
strategy**.

## Slippage sensitivity

Stress-test high-speed strategies at 0, 5, 10, 20, 50, 100 bps (asset-appropriate).
Reject strategies whose profitability vanishes under minimally realistic slippage.

## Walk-forward validation

Train / validation / untouched test; walk-forward; rolling retraining; regime
analysis. Freeze parameters before each test period.

## Multiple-hypothesis control

Track experiment count, failed hypotheses, parameter searches, model variations.
Maintain experiment registry. Consider statistical controls for multiple comparisons.
Do not publish only winners.

## Strategy preregistration

Before serious evaluation, freeze: hypothesis; data; features; target; entry;
exit; sizing; costs; risk; evaluation metric; success criteria. Changes → new
strategy version.

## Economic validation gate

Before economic conclusions require:

```text
prediction evaluation
AND execution simulation
AND cost sensitivity
AND risk evaluation
```

A model can improve accuracy and still be useless for trading.

## Edge robustness scorecard (internal research artifact)

Not a buy score. Categories:

- statistical evidence
- out-of-sample evidence
- economic evidence
- cost robustness
- latency robustness
- regime robustness
- parameter robustness
- capacity
- operational reliability

## Strategy graveyard

Record rejected strategies: hypothesis; why promising; test; failure; data;
lesson. Prevents rediscovering false edges.

## Research leaderboard (future)

Rank validated strategies by net expectancy, risk-adjusted return, drawdown,
stability, capacity, confidence, live/paper degradation — not gross backtest return.

## Walk-forward strategy selection

Strategy selectors must themselves be tested point-in-time. No retrospective
picking of period winners.

## Portfolio and meta-strategy

Eventually: strategy correlation; asset correlation; exposure; volatility
targeting; risk budgets; drawdown interaction; opportunity selection among
validated strategies based on expected risk-adjusted value — not a universal buy score.

## Profitability attribution

Every result answers: why did we make/lose money?

Break down: signal; timing; entry; exit; spread; slippage; fee; funding;
adverse selection; regime; catalyst; model; risk sizing.

## Post-trade learning

Simulation/paper/live feed research ledger — not automatic retraining. Capture
expected vs realized; predicted probability; realized return; slippage; latency;
quality state; failure reason. Retraining requires explicit research/version process.

## False-edge red team checklist

Leakage; observability; timestamp alignment; final engagement misuse; retroactive
wallet labels; fee/funding omissions; impossible latency; unrealistic fills;
survivorship; cherry-picked actors; pump chasing; universal score creep; AI
execution authority; live scope creep.

## Null results

No edge; edge disappears after latency; fees destroy edge; whale data adds no
value — record as successful outcomes.

## Core rule

Never optimize to make a historical chart look profitable. Optimize the
probability that a **future unknown observation**, processed with only
information actually available at the time, could produce positive risk-adjusted
outcome after all realistic costs.
