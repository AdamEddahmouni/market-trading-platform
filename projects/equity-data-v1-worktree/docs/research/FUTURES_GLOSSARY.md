# Futures Glossary (Deliverable 115)

Canonical definitions for the Futures lane. Shared concepts reference platform docs; lane-specific semantics defined here.

---

## futures contract

A standardized agreement to buy or sell an underlying at a future date. Identified by `contract_id` (e.g. `ESU26`), distinct from `instrument_family` (e.g. `ES`).

**Does not mean:** A timeless ticker symbol or a continuous research series.

---

## forward

Economic forward price implied by curve; may differ from tradeable futures price near expiration.

---

## notional

`Contracts × Multiplier × RelevantUnderlyingPrice`. Economic exposure — not the same as margin capital.

---

## multiplier / tick / tick value / point value

Contract specification fields. PnL must use tick economics, not generic percentage returns.

---

## initial / maintenance / variation margin

Exchange/broker capital requirements and daily mark-to-market cash flows. Margin ≠ economic risk at risk.

---

## spot / basis / carry

- **Spot:** Reference price for underlying or deliverable.
- **Basis:** Explicitly signed per `BasisDefinition` (e.g. `FUTURES_MINUS_SPOT`).
- **Carry:** Roll/financing/storage economics — family-specific formula.

**Does not mean:** Basis and carry are interchangeable or universally signed.

---

## contango / backwardation

Curve shape descriptors — not inherently bullish/bearish without asset context.

---

## term structure / curve slope / curvature

Properties of `FuturesCurveSnapshot` across expirations.

---

## calendar spread

`F(T1) - F(T2)` modeled as its own object with spread volatility, carry, and fundamentals.

---

## roll / lead contract / continuous contract / back adjustment

- **Roll:** Close old + open new contract; must be simulated with costs.
- **Lead contract:** Analysis/trading contract selected by deterministic rule — not always nearest expiry.
- **Continuous series:** Research artifact — must not masquerade as tradeable contract.

---

## open interest

Outstanding matched long/short contracts. **Does not mean:** Rising OI is bullish — every contract has a long and short.

---

## COT / hedging pressure

CFTC Commitments of Traders positioning by participant category. `observation_time` ≠ `publication_time`.

**Does not mean:** Commercials = smart money; speculators = dumb money.

---

## settlement / physical delivery / first notice

Official daily/final settlement prices and delivery mechanics. Strategies need delivery guardrails.

---

## price limits

Exchange circuit breakers — stops may remain unfilled when locked limit.

---

## DV01 / CTD / conversion factor / implied repo

Treasury futures delivery-option concepts. Do not fake without deliverable-basket data.

---

## liquidation cascade

Futures leveraged long/short forced exit — distinct from equity short squeeze.

**Does not mean:** Short Squeeze lane state machine or stock borrow recall.

---

## delivery squeeze / corner

Physical deliverable scarcity + concentrated spot-month positioning + delivery obligation.

---

## fair value vs directional forecast

Fair carry/pricing relative value ≠ expected underlying return. Market at fair value does not imply zero expected futures return.

---

## missing ≠ zero

Missing COT ≠ neutral positioning. Missing inventory ≠ normal inventory. Missing margin ≠ no stress.
