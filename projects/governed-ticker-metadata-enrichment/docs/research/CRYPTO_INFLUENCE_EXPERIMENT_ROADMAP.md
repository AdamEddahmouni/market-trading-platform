# Crypto & Influence Experiment Roadmap

**Status:** `PROPOSED` — experiments designed, not executed, without authorization

**Principle:** Preregister, freeze, test point-in-time, report nulls honestly.

## Experiment 0 — Infrastructure null baseline

Establish latency and cost baseline on admitted crypto bytes (once available):
detection → decision → simulated fill at multiple delays. No strategy claim.

## Experiment 1 — Influence short-horizon (first influence study)

### Hypothesis

Verified public events from historically influential actors may predict abnormal
short-horizon activity in a target asset (e.g. DOGE) **after realistic detection
latency**.

### Data

- event publication and first_observed timestamps
- event content and type
- target asset trades/quotes
- volume, spread, controls

### Horizons

Seconds through hours — only where data quality supports.

### Comparisons

All events vs direct mentions vs positive vs negative vs novel vs repetitive.

### Measures

Abnormal return; volume; volatility; delayed entry; spread/slippage; net expectancy.

### Critical question

Does actionable edge remain **after the platform could realistically detect and
process the event**?

## Experiment 2 — Market confirmation layer

Compare:

```text
event alone
event + volume acceleration
event + volume + aggressive buying
```

Tests: capital must follow attention, not just statements.

## Experiment 3 — On-chain confirmation layer

Compare:

```text
influence + market confirmation
influence + market + whale/on-chain confirmation
```

Measure **incremental** economic value — ablation required.

## Candidate research families (all preregistered before testing)

| Family | Components |
|---|---|
| Influence-reaction | public event + historical actor/asset effect + order-flow confirmation |
| Influence + whale | public event + large-wallet behavior + flow confirmation |
| Exchange flow | on-chain exchange flow + derivatives + regime |
| Liquidation cascade | leverage extreme + liquidation acceleration + liquidity |
| Funding mean reversion | extreme funding + OI + structure + catalyst absence |
| Cross-venue lead/lag | Venue A → delayed Venue B |
| Whale accumulation | wallet accumulation + withdrawal + order-flow confirmation |
| Meme/narrative momentum | influence + mention acceleration + volume + liquidity gates |
| Narrative exhaustion | social acceleration + derivatives crowding + flow deterioration |

None are assumed to work.

## Regime analysis

Evaluate by: volatility; trend/range; leverage; risk-on/off; funding extremes;
social attention; liquidity stress; major catalyst presence.

## Experiment registry fields

hypothesis_id; preregistration hash; data manifest; feature versions; cost model
version; latency assumption; success criteria; outcome; failure reason; graveyard link.

## Null outcomes

Record and publish internally: no edge; latency kills edge; fees destroy edge;
whale data adds no value.

## Authorization

Each experiment requires separate research authorization after feasibility
studies and relevant ADR acceptance.
