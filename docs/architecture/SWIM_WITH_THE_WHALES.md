# Swim With the Whales doctrine

Revision 3 is authoritative if this guidance conflicts with it. This doctrine
defines future research semantics; it implements no ingestion, signal, strategy,
risk, execution, or AI capability.

## Operating loop

`observe → verify → contextualize → align when justified`

1. **Observe:** retain the source event and every relevant time and capability.
2. **Verify:** establish identity, provenance, availability, quality, and what the
   source can actually support.
3. **Contextualize:** normalize magnitude, freshness, market regime, conflicts,
   missing capabilities, and alternative explanations.
4. **Align when justified:** a preregistered strategy may consume selected,
   transparent evidence. It may also remain neutral, abstain, or be contrarian.

Evidence is not intent, identity, a recommendation, or an order.

## Eight separately inspectable evidence families

1. **Regulatory/disclosure:** Form 4, 13D/G, 13F, amendments, holdings, and
   beneficial ownership with reporting, filing, acceptance, and availability
   times. Delayed filings are never described as live positions.
2. **Large transactions:** size anomalies normalized to an appropriate reference
   such as ADV, rolling volume, float, open interest, or visible depth.
3. **Order book:** visible liquidity, replenishment, withdrawal, imbalance,
   consumption, absorption, and exhaustion without invented participant identity.
4. **Order flow:** signed volume, CVD, OFI, size distribution, aggressive-large-
   trade concentration, and quote depletion with explicit aggressor provenance.
5. **Options:** unusual volume, open-interest relationships/change, premium,
   strike/term concentration, skew, IV, liquidity, and exposure estimates without
   assuming trader intent.
6. **Futures positioning:** public aggregates, trader categories, volume/open
   interest, roll behavior, basis, and multi-market context with delay retained.
7. **Fund/ETF/cross-asset:** flows/proxies, creations/redemptions, rebalances,
   rates, volatility, correlations, sector, and regime context.
8. **Public catalyst:** earnings, guidance, filings, offerings, buybacks, M&A,
   activist activity, insider purchases, macro releases, and news with source and
   availability semantics.

## Semantic separation

Every claim moves through distinct layers:

`observed fact → derived measurement → hypothesis → strategy interpretation → independent risk decision → authorized execution result → accounting`

- A fact states what the source published or the venue exposed.
- A measurement states a reproducible transformation and uncertainty.
- A hypothesis states an explanation that may be wrong.
- A strategy declares how selected evidence affects decision rules.
- Risk can reject or reduce an intent; evidence cannot override it.
- Execution and accounting report what actually happened, not what was forecast.

Supported direction states include `supports_long`, `supports_short`, `neutral`,
`ambiguous`, `conflicting`, `stale`, and `unavailable`. Contradiction and
missingness remain information; no forced consensus is allowed.

## Strategy declaration

Every future strategy declares one relationship:

- `WHALE_ALIGNED`: qualifying evidence, freshness, agreement, contradiction,
  timing, invalidation, and risk implications are explicit.
- `WHALE_NEUTRAL`: whale evidence is intentionally excluded from the rule.
- `WHALE_CONTRARIAN`: the strategy preregisters why measured pressure may reverse.

Evidence presence never automatically creates an entry. There is no universal
whale score or buy score. A calibrated model output may be a score only when its
target, version, inputs, calibration, uncertainty, and limitations stay explicit.

## Provenance chains

Examples of required resolvability:

```text
filing → accession/raw filing → parser version → canonical disclosure
  → derived ownership delta → research feature → strategy decision

raw trade → source/provider → canonical trade → aggressor classification
  → normalized large-trade classifier → evidence item → strategy context
```

The system must explain accumulation, distribution, conflict, staleness, and
unavailability from source to decision. Anonymous events receive no invented
identity. Unknown aggressor remains unknown. Stale evidence remains stale.

## Unified framework — traditional, crypto, influence, prediction markets

Swim With the Whales evolves into four complementary perspectives on the same
platform — not disconnected products:

### Traditional markets

Follow measurable institutional footprints: disclosures, large prints, order
flow, options, depth. Uses the eight evidence families below.

### Crypto (future)

Follow observable capital movement: wallets, exchange flows, derivatives,
cross-venue flow, order books. Size is normalized to liquidity and supply — no
static dollar whale threshold. Exchange inflow is not assumed to mean sell;
withdrawal is not assumed to mean buy. These are testable hypotheses.

### Influence markets (future)

Follow attention only when it demonstrably converts into capital:

```text
public event → attention → participation → order flow → positioning → price
```

Each transition must be verified. Do not trade because someone important said
something. See [INFLUENCE_INTELLIGENCE.md](./INFLUENCE_INTELLIGENCE.md).

### Prediction markets (future)

Follow demonstrated information advantage where historical evidence shows relevant
domain skill, observable latency permits action, and hedge blindness is acknowledged:

```text
public participant action (where legitimately observable)
  → first observable time
  → point-in-time participant quality and specialization
  → position magnitude and liquidity context
  → market price after detection
  → remaining estimated edge
  → simulation
```

Never implement `whale buys → automatically copy`. Prefer:

> This wallet currently has a visible net YES position on this venue.

over:

> This trader believes YES.

Kalshi-style anonymous large flow may support size and directional flow features
without participant identity. Polymarket-style public wallet data may support
wallet-level research where lawful — Polymarket is the platform; Polygon is a
settlement network; do not conflate.

**Prediction-market maxim:**

> Do not copy the biggest bettor. Identify who repeatedly knows more than the
> market, determine when that skill is relevant, and verify that the information
> advantage still exists by the time you can act.

See [PREDICTION_MARKET_WHALE_INTELLIGENCE.md](./PREDICTION_MARKET_WHALE_INTELLIGENCE.md)
and [2026-08-16-prediction-markets-expansion-design.md](../superpowers/specs/2026-08-16-prediction-markets-expansion-design.md).

### Central whale rule

> Do not follow a whale merely because it appears large. Follow the wake only
> when the wake is measurable, timely, economically relevant, and confirmed by
> the surrounding market. Never assume the whale knows more than the market.

### Whale confluence (transparent, not scored)

Potential confluence components remain separately inspectable:

```text
verified public catalyst
+ historically influential actor/asset pair (empirical)
+ social acceleration
+ large wallet movement
+ aggressive market buying
+ OI expansion
+ acceptable funding
+ sufficient liquidity
```

No `WHALE SCORE 97` unless a rigorously validated model defines such a
probability with full provenance. See
[ON_CHAIN_INTELLIGENCE.md](./ON_CHAIN_INTELLIGENCE.md) and
[CRYPTO_PROFITABILITY_RESEARCH.md](./CRYPTO_PROFITABILITY_RESEARCH.md).

## No-authority boundary

Whale evidence is strategy input only. It cannot create an order intent by
itself, override independent risk, bypass execution authorization, mutate a
position, or change accounting. A future research assistant may explain and cite
this evidence but has the same no-authority boundary.
