# Prediction Market Whale and Participant Intelligence

**Status:** `PROPOSED` — future architecture guidance

**Authority:** Subordinate to Revision 3,
[SWIM_WITH_THE_WHALES.md](./SWIM_WITH_THE_WHALES.md), and
[2026-08-16-prediction-markets-expansion-design.md](../superpowers/specs/2026-08-16-prediction-markets-expansion-design.md)

## Purpose

Extend Swim With the Whales for prediction markets — participant intelligence where
legitimately public, without blind copying, invented identity, or hedge blindness.

**Prediction-market maxim:**

> Do not copy the biggest bettor. Identify who repeatedly knows more than the
> market, determine when that skill is relevant, and verify that the information
> advantage still exists by the time you can act.

## Venue capability honesty

### Kalshi (typical expectation)

If public trades expose only market, size, price, taker side, time — whale
intelligence may identify:

```text
large transaction | large directional flow | unusual size
repeated aggressive flow | liquidity consumption
```

but not `"This is Trader X"`. Preserve participant anonymity.

### Polymarket-style venues

Where legitimate public data supports wallet-level research:

`PredictionMarketParticipant` / `PublicPredictionWallet`

Possible features: current/closed positions, trade history, activity, position
value, markets traded, specialization, holding duration, realized history.
Preserve provider identifiers.

Polymarket is the platform; Polygon is a settlement network — do not conflate.

## Never auto-copy

Forbidden pattern:

```text
whale buys → automatically copy
```

Required research pipeline:

```text
Observed participant action
  → first observable time
  → participant historical quality (point-in-time)
  → domain specialization
  → position magnitude
  → current market liquidity
  → market price after detection
  → remaining estimated edge
  → simulation
```

Critical question: Is the participant still worth following after we observe the
trade and the market has reacted?

## Copy latency measurement

```text
Whale transaction
  → provider publication
  → platform ingestion
  → participant recognition
  → strategy evaluation
  → order arrival
```

Reject copy strategies when repricing occurs before replication is realistic.

## Participant track record

`ParticipantTrackRecord` — point-in-time rankings only:

- total resolved markets, hit rate
- Brier-like performance where meaningful
- realized P&L where reliably derivable
- ROI, average entry probability
- market specialization, performance by category/horizon
- drawdown, concentration, sample size

Do not rank wallets solely by lifetime dollar profit — large bankroll ≠ skill.

## Specialist detection

`ParticipantSpecialization` — informative only in narrow domains:

```text
Wallet A — Overall: average | US elections: excellent | Crypto: poor | Sports: insufficient sample
```

Domains: politics, economics, crypto, technology, regulation, sports, entertainment,
climate, corporate events.

## Survivorship and leaderboard leakage

- Do not select best wallets today and test retroactively as though known then.
- At each historical time: which participants had demonstrated skill **as of then**?
- Current leaderboard status cannot be a historical feature.
- Reconstruct reputation from historical information only.

## Identity versioning

If labels or profiles change, preserve:

```text
known_at | effective_at | source | label_version
```

Do not backfill current identity into past decisions.

## Sybil and hedge blindness

- One wallet ≠ one human (multiple wallets, proxies, capital movement).
- Visible YES may be hedged across prediction markets, stocks, options, futures,
  crypto, private positions.

Prefer:

> "This wallet currently has a visible net YES position on this venue."

over:

> "This trader believes YES."

## Market-maker detection

Large activity may be liquidity provision: two-sided activity, high turnover, short
holds, spread capture, opposing inventory. Do not copy apparent directional
exposure from probable market makers without strategy understanding.

## Whale consensus (transparent)

`ParticipantConsensus` — separately inspectable, not a magic score:

```text
Top historically successful economic-policy specialists:
  7 supporting YES | 2 supporting NO | 4 no position
```

Weighting must be transparent and validated.

## Evidence types

Potential whale evidence (where supported):

- large market trade
- new large holder
- concentrated YES/NO position
- rapid accumulation/reduction
- successful specialist wallet activity
- convergence of historically strong participants

Do not assume whales are correct. Contrarian research (extreme consensus + extreme
price + contrary model) may be studied — preregister; do not auto-fade.

## Internal model vs whales vs market

Three separate surfaces — never average blindly. Disagreement may be valuable:

```text
Market 40% | Model 59% | Whales 32%
```

## UI: whale card semantics

Show participant identity only where legitimately public. Include confidence in
participant inference, visible net change, market probability move, links to trades
and historical performance. Not a trade recommendation.

## Second research track

> Do historically skilled, domain-specialist participants contain incremental
> predictive information after their activity becomes publicly observable?

## Integration with replay

At historical time T: participant reputation, positions, and trades observable at T
only. Essential for honest whale-copy backtesting.
