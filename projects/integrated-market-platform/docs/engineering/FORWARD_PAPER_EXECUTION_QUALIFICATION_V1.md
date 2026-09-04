# BUILD 27 — Forward Paper Execution Qualification

> BUILD 27 tests paper execution prospectively using only information available when each opportunity, risk decision, order, and fill occurs. It does not optimize the strategy or authorize real trading.

## Core principle

```text
BUILD 26 = forward forecast qualification
BUILD 27 = forward PAPER execution qualification
```

Paper execution evidence is evidence. It is not live-trading authorization.

## Five price concepts

| Concept | Role |
| --- | --- |
| Forecast market price | Intelligence snapshot at forecast decision |
| Opportunity reference | Spread/liquidity context at opportunity emission |
| Trade-proposal reference | Ask (buy) or bid (sell) at proposal time |
| Paper fill price | BarConservativeSimulator bar high/low at fill bar |
| Forecast terminal/outcome price | BUILD 15 settlement only; never a fill input |

## Fill model

Canonical simulator: `BarConservativeSimulator` (`phase7.bar-conservative/1.1.0`).

- Market long fills use bar **high** after order activation.
- Market short fills use bar **low** after order activation.
- Participation cap limits volume per bar.
- Reference pricing for sizing uses conservative ask/bid (`reference_price_for_side`).

## Realism limitations

- `QUEUE_POSITION_UNMODELED`
- `PARTIAL_FILLS_MODELED` (participation cap only)
- `MARKET_IMPACT_UNMODELED`
- `ZERO_FEES` paper policy
- `BAR_CONSERVATIVE_FILL` (not quote-level touch)
- `LIMITED_DEPTH` (bar volume cap)

## Risk sequencing

Each risk decision uses the paper portfolio snapshot at decision time. Sequential trades evolve cash, positions, and exposure. Concurrent proposals must not double-spend gross/net capacity.

## Paper PnL

Paper PnL reflects the frozen simulator's fill and fee assumptions. It is **not** realizable live PnL.

## No policy tuning

OpportunityPolicy, ExecutionPolicy, sizing, risk limits, and fill model are frozen for each qualification run.

## No live authorization

```text
PAPER_EXECUTION_QUALIFIED ≠ live broker authorization
```

BUILD 27 requires:

- `execution_mode = PAPER`
- `execution_authority = PAPER_ONLY` or `AUTHORIZED` (paper path only)
- zero real broker submit/cancel calls

## Forward vs replay paper

| Class | Meaning |
| --- | --- |
| `FORWARD_PAPER` | Genuine forward opportunity with BUILD 26 receipt lineage |
| `REPLAY_PAPER` | Deterministic reproduction; not additional forward evidence |
| `COUNTERFACTUAL_PAPER` | Synthetic; never forward evidence |

## Evidence handoff

```text
PaperExecutionQualificationReport
  → BUILD 23 execution health
  → BUILD 24 research triggers (execution anomalies)
  → forward accumulation programs
```
