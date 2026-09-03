# Prediction Market Simulation and Risk

**Status:** `PROPOSED` — future architecture guidance

**Authority:** Subordinate to Revision 3 and
[2026-08-16-prediction-markets-expansion-design.md](../superpowers/specs/2026-08-16-prediction-markets-expansion-design.md)

## Purpose

Extend deterministic simulation, capital accounting, and risk for prediction-market
contract semantics — never treat prediction shares as stock shares.

## Simulator extensions

The platform's deterministic simulator remains canonical. Kalshi demo supplements
testing but does not replace simulation.

Support:

- binary payouts and multi-outcome markets where applicable
- YES/NO complement mechanics
- market and limit orders
- partial fills
- fees, spread, price/time priority
- settlement and void scenarios
- position accounting and capital lockup

Distinct from equity simulation: payoff caps, complement relationships, resolution
timing, rule-change risk at position level.

## Capital accounting

Account for:

```text
contract acquisition cost | realized sale P&L | settlement payout
fees | locked collateral | available cash | unrealized mark
settlement timing
```

Reconcile exactly with existing accounting discipline.

## Market-making research (separate family)

Potential objectives: quote around fair probability, capture spread, manage
inventory, adjust for new evidence.

Requirements: inventory limits, adverse-selection model, latency, fee model,
queue/fill assumptions, probability volatility.

No market-making claims without realistic execution testing.

## Structural arbitrage research

Categories: complementary-outcome discrepancies, mutually exclusive discrepancies,
nested-range inconsistencies, same-event cross-platform disagreements.

Do not claim arbitrage until verifying executable bid/ask, fees, size, rules,
settlement equivalence, capital requirements, timing.

## Risk dimensions

Prediction-market-specific risk:

- max event exposure
- correlated-event exposure (ten election markets ≠ ten independent risks)
- long-duration capital lock
- liquidity and resolution ambiguity
- rule-change risk
- concentration and participant-copy concentration
- political/event correlation
- tail outcomes

Aggregate at event level:

```text
Fed | macro | election | crypto regulation
```

may form correlated clusters.

## Strategy abstention (risk-related)

```text
ABSTAIN — semantic ambiguity
ABSTAIN — market integrity concern
ABSTAIN — jurisdiction/execution unavailable
ABSTAIN — insufficient liquidity after friction
```

## Profitability requirements

Same economic framework as all platform strategies:

- point-in-time correctness
- out-of-sample validation
- executable price, spread, fee, slippage, latency
- capital requirements, settlement, resolution uncertainty
- risk and capacity

Reject false edge aggressively. Null results are successful outcomes.

## Integration

Extends Phase 7 simulation/accounting patterns — not a parallel sim stack. Risk
remains independent of evidence and model outputs.
