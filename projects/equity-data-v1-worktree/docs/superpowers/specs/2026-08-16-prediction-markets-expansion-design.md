# Prediction Markets, Event Intelligence & Whale Research Expansion

**Logical ID:** `foundation.prediction_markets_expansion.proposal`

**Status:** `PROPOSED` — planning and architecture only

**Date:** 2026-08-16

**Scope:** Future architecture, research planning, capability taxonomy, roadmap
integration, and proposed ADRs for prediction/event markets as a first-class
future research and trading domain; event intelligence; fair-probability research;
public participant/wallet intelligence; cross-platform and cross-asset
intelligence; resolution semantics; simulation; risk; and Swim With the Whales
evolution.

**Implementation authority:** None

**Phase transition authority:** None

**Provider/broker/live-trading authority:** None

**Terminology:** **Polymarket** is the prediction-market platform. **Polygon** is
one blockchain/network associated with Polymarket settlement architecture. Do not
confuse the two.

## 1. Relationship to existing authority

Revision 3 remains the sole forward-looking canonical foundation authority until a
future revision supersedes it. This document is **subordinate** to Revision 3 on
conflict. It does not modify governed evidence, phase pass publications, accepted
ADRs, or `canonical-authority.json`.

Phases 0 through 8 and UI-001 remain `PASS` on the admitted equity intraday
fixture (`ADMITTED-SHORTSQ-BIYA-BARS-001`). This expansion is a **future,
separately authorized track** that begins only after explicit feasibility studies,
accepted ADRs, and phase-gated implementation authorizations.

This document authorizes no provider connection, Kalshi/Polymarket adapter,
whale ingestion, on-chain ingestion, model implementation, paper trading, or live
trading.

## 2. Economic objective

Prediction markets extend the platform's economic objective without creating a
gambling-style silo:

> **Find measurable informational or structural advantages in event probabilities,
> participant evidence, and cross-asset propagation — validate them honestly, act
> only when expected opportunity exceeds realistic spread, fees, slippage, latency,
> capital lockup, and resolution uncertainty — and abstain when it does not.**

No guaranteed profitability is claimed or implied.

## 3. Non-negotiable preservation

Prediction-market integration must conform to existing foundational rules:

- provider-neutral canonical contracts; no `KalshiEngine` as conceptual core;
- strategies never consume provider SDK objects;
- provenance travels with data;
- `event_time` and availability time are separate;
- correction/revision history is preserved — especially resolution rules;
- quality failures remain explicit;
- unsupported capabilities remain unavailable;
- participant anonymity preserved where venues do not expose identity;
- independent risk cannot be bypassed;
- deterministic replay must remain deterministic;
- research/model outputs do not independently authorize trades;
- simulation must model realistic execution and contract payoffs;
- profitability claims require evidence;
- live trading remains independently gated;
- jurisdiction and execution eligibility are explicit capability boundaries.

## 4. Three core opportunities

### A. Tradable instruments

Independent calibrated probability vs executable market price after friction:

```text
Real-world evidence → point-in-time features → OutcomeProbabilityModel
  → fair probability → order book → executable price → fees/spread/slippage
  → expected value → strategy → risk → simulation/execution
```

### B. Intelligence layer (no position required)

Crowd-derived probabilities become features for other assets:

```text
Election / Fed / regulation / FDA / macro-release / policy-event probability
  → sector equities, rates, futures, FX, crypto, affected instruments
```

Prediction markets are part of the **Information Intelligence Layer** even when
the system holds no prediction-market position.

### C. Whale/trader intelligence (where legitimately public)

Study large traders, profitable wallets, specialists, concentration, timing, and
historical performance — especially on transparent/on-chain venues. Do not assume
every venue exposes participant identity.

See [PREDICTION_MARKET_WHALE_INTELLIGENCE.md](../../architecture/PREDICTION_MARKET_WHALE_INTELLIGENCE.md).

## 5. Asset-class architecture

### 5.1 Traditional (existing trajectory)

Equities, ETFs, futures, equity options, futures options where supported.

### 5.2 Crypto (proposed expansion track)

See [2026-08-16-crypto-influence-expansion-design.md](./2026-08-16-crypto-influence-expansion-design.md).

### 5.3 Prediction markets (future first-class family)

Event contracts with YES/NO or multi-outcome semantics; resolution rules as
first-class data; capital lockup until settlement; jurisdiction-dependent
execution.

Shared canonical concepts extend existing contracts where possible: instrument
identity; venue; event time; availability time; provenance; trade; quote; depth;
order; fill; fee; position; P&L; quality.

Prediction shares are not stock shares. Binary payouts, complement mechanics, void
scenarios, and rule amendments require explicit semantics.

See [PREDICTION_MARKET_CAPABILITY_MODEL.md](../../architecture/PREDICTION_MARKET_CAPABILITY_MODEL.md)
and [PREDICTION_MARKET_RESOLUTION_AND_EVENTS.md](../../architecture/PREDICTION_MARKET_RESOLUTION_AND_EVENTS.md).

## 6. Provider-neutral capability model

Capabilities are closed, explicit, and versioned. Kalshi and Polymarket are
**future candidate adapters**, not the architecture core.

```text
PREDICTION_MARKET_DISCOVERY
PREDICTION_MARKET_QUOTES | TRADES | ORDERBOOK | HISTORY | LIFECYCLE | RESOLUTION
PREDICTION_MARKET_EXECUTION | POSITIONS | SETTLEMENTS
PREDICTION_PUBLIC_PARTICIPANT_ACTIVITY | HOLDERS | WALLET_POSITIONS
```

A provider exposing trades but not public trader identity must not satisfy
participant-copy capabilities. Public research-data capability and lawful
execution capability are separate per provider and jurisdiction.

Example configuration (verify at implementation — do not hard-code):

```text
Polymarket: DATA / WHALE RESEARCH ONLY (unless lawful U.S. execution verified)
Kalshi: DATA + DEMO (execution when authorized)
future provider: DATA + EXECUTION
```

## 7. Canonical event hierarchy

```text
PredictionEvent
  └─ PredictionMarket
        ├─ Outcome
        ├─ OrderBook
        ├─ Trade
        ├─ ResolutionRule (versioned)
        └─ Settlement
```

Cross-provider mapping uses `CanonicalRealWorldEvent` with separate dimensions:

- `same_real_world_topic` — entity resolution
- `settlement_equivalent` — semantic equivalence (often false when questions differ)

`ResolutionSemanticRisk`: `LOW`, `MODERATE`, `HIGH`, `AMBIGUOUS`.

Never overwrite historical rules when they change. Use `ResolutionRuleVersion`:
`effective_at`, `observed_at`, `content_hash`, `source`, `rules`.

## 8. Implied probability semantics

Distinguish — do not label every displayed price as "true probability":

```text
last trade | best bid | best ask | midpoint
model-implied fair probability
```

Trading strategies use **executable price**, not decorative midpoint.

## 9. Fair-probability engine

Core research abstraction: `OutcomeProbabilityModel` — estimate probability of a
precisely defined outcome using only information available at evaluation time.

Possible families: base-rate, Bayesian, logistic, time-series probability, gradient
boosting, calibrated ML, ensembles, event-specific structured models.

Domain engines (build incrementally, not all at once): election, economic release,
Fed decision, sports, crypto event, regulatory, corporate, technology policy.

LLM probability guesses are not calibrated engines. LLMs assist evidence processing;
probability estimates require evaluated methodology.

See [PREDICTION_MARKET_PROBABILITY_RESEARCH.md](../../architecture/PREDICTION_MARKET_PROBABILITY_RESEARCH.md).

## 10. Model edge and economic value

For YES (verify actual contract payoffs per venue):

```text
estimated edge ≈ p - executable_YES_price - friction
```

Direction prediction alone is insufficient. Require:

```text
probability advantage → executable price → spread → fees → slippage → latency
  → capital lockup → resolution uncertainty → expected net value
```

Time to resolution matters: 4% edge resolving tomorrow ≠ 4% resolving in nine
months.

Distinguish **outcome uncertainty** from **resolution uncertainty** (how written
rules classify what happened).

Always benchmark against market probability at decision time. Keep forecasting
skill and trading skill separate.

## 11. Major future subsystems

| Subsystem | Guidance document |
|---|---|
| Capability and contracts | [PREDICTION_MARKET_CAPABILITY_MODEL.md](../../architecture/PREDICTION_MARKET_CAPABILITY_MODEL.md) |
| Resolution and events | [PREDICTION_MARKET_RESOLUTION_AND_EVENTS.md](../../architecture/PREDICTION_MARKET_RESOLUTION_AND_EVENTS.md) |
| Probability research | [PREDICTION_MARKET_PROBABILITY_RESEARCH.md](../../architecture/PREDICTION_MARKET_PROBABILITY_RESEARCH.md) |
| Whale / participant intelligence | [PREDICTION_MARKET_WHALE_INTELLIGENCE.md](../../architecture/PREDICTION_MARKET_WHALE_INTELLIGENCE.md) |
| Cross-asset intelligence | [PREDICTION_MARKET_CROSS_ASSET_INTELLIGENCE.md](../../architecture/PREDICTION_MARKET_CROSS_ASSET_INTELLIGENCE.md) |
| Simulation and risk | [PREDICTION_MARKET_SIMULATION_AND_RISK.md](../../architecture/PREDICTION_MARKET_SIMULATION_AND_RISK.md) |
| Influence integration | [INFLUENCE_INTELLIGENCE.md](../../architecture/INFLUENCE_INTELLIGENCE.md) |
| Whale doctrine | [SWIM_WITH_THE_WHALES.md](../../architecture/SWIM_WITH_THE_WHALES.md) |
| Model research framework | [MODEL_RESEARCH_AND_DATASETS.md](../../architecture/MODEL_RESEARCH_AND_DATASETS.md) |

## 12. Swim With the Whales — fourth perspective

Four complementary perspectives on one platform — not disconnected products:

1. **Traditional markets:** measurable institutional footprints.
2. **Crypto:** observable capital movement.
3. **Influence markets:** attention that converts into capital.
4. **Prediction markets:** demonstrated information advantage where historical
   evidence shows relevant domain skill, observable latency permits action, and
   hedge blindness is acknowledged.

**Prediction-market maxim:**

> **Do not copy the biggest bettor. Identify who repeatedly knows more than the
> market, determine when that skill is relevant, and verify that the information
> advantage still exists by the time you can act.**

Never implement `whale buys → automatically copy`. Test copy latency end-to-end.
Reject copy strategies when the market reprices before replication is realistic.

Prefer: "This wallet currently has a visible net YES position on this venue" over
"This trader believes YES."

## 13. Internal model vs whales vs market

Three separately inspectable surfaces — never average blindly:

```text
MARKET             executable crowd-implied probability
OUR MODEL          independent calibrated estimate
SPECIALIST WHALES  derived participant evidence (where public)
```

Disagreement may be more valuable than consensus. Example contradiction:

```text
Market 40% | Model 59% | Whales 32%
```

## 14. Cross-market intelligence

Within prediction markets: probability disagreement, lead/lag, liquidity, price
discovery, structural consistency (mutually exclusive outcomes, nested thresholds).

Cross-platform: same-event divergence across Kalshi/Polymarket/other — not
automatic arbitrage until executable bid/ask, fees, semantics, jurisdiction, and
capital movement are verified.

Cross-asset: `MarketImpliedProbabilityFeature` feeding equities, futures, crypto.
Study probability **change** and velocity — not only level. Determine lead/lag
empirically.

See [PREDICTION_MARKET_CROSS_ASSET_INTELLIGENCE.md](../../architecture/PREDICTION_MARKET_CROSS_ASSET_INTELLIGENCE.md).

## 15. Influence + prediction markets

Connect Influence Engine:

```text
Public statement → Influence event → prediction-market repricing
  → sector/crypto reaction
```

Prediction-market movement is supporting evidence, not proof.

## 16. Event knowledge graph

Extend event/entity graph conceptually:

```text
Actor → Statement → Policy Event → Prediction Markets / Assets
Prediction Market → Participants | Assets → Strategies
```

Do not implement an unnecessarily complicated graph database until requirements
justify it.

## 17. Research architecture integration

Extend existing abstractions — do not fork a parallel prediction framework:

`ResearchDataset`, `FeatureSnapshot`, `ForecastTarget`, `ForecastModel`,
`TrainingManifest`, `Prediction`, `WalkForwardRun`, `CalibrationReport`,
`Experiment`, `StrategySpec`, `SimulationRun`.

Calibration: Brier score, log loss, reliability curves, calibration error,
sharpness. If the system says P=70%, comparable 70% buckets should resolve ~70%
under valid evaluation.

Five-way ablation where applicable:

```text
MARKET ONLY | MODEL ONLY | MARKET+MODEL | MARKET+WHALES | MARKET+MODEL+WHALES
```

## 18. Strategy families (none assumed profitable)

- Model mispricing (executable edge after friction)
- Model + whale agreement
- Whale following (skilled specialists, post-observability)
- Whale disagreement (high-quality specialists vs market)
- Cross-venue probability dislocation
- Event reaction (news/social before other assets reprice)
- Prediction market as asset signal
- Relative market consistency (probabilistic constraint violations)
- Market making (separate family — inventory, adverse selection, fees)

Common abstentions: insufficient edge, wide spread, low liquidity, semantic
ambiguity, model outside domain, participant conflict, integrity concern,
jurisdiction unavailable.

## 19. Integrity safeguards

Never design around improperly obtained nonpublic information, outcome manipulation
by controlling actors, venue restriction evasion, or prohibited participant copying.

Flags: `ACTOR_CONTROLS_OUTCOME`, `DIRECT_INFLUENCE_RISK`,
`NONPUBLIC_INFORMATION_RISK`, `MARKET_INTEGRITY_RISK` — may cause automatic
abstention.

Public-actor markets (what someone will say/do) require special care; controlling
person trades are not ordinary whale intelligence.

## 20. Simulation

Extend deterministic simulator — canonical for historical research. Demo trading
(Kalshi demo) supplements but does not replace simulation.

Support: binary/multi-outcome payouts, YES/NO complements, limit/market orders,
partial fills, fees, spread, settlement, void, position accounting, capital lockup.

See [PREDICTION_MARKET_SIMULATION_AND_RISK.md](../../architecture/PREDICTION_MARKET_SIMULATION_AND_RISK.md).

## 21. UI integration

Prediction markets extend Workspace architecture — not a gambling silo. Cockpit
modules: Overview, Probability, Order Book, Trades, Whales, Our Model, Evidence,
Related Markets, Underlying Data, News/Influence, Resolution, History, Replay.

NOW cards surface attention priority — not trade recommendations. Model cards show
calibration and resolution risk — not "guaranteed edge."

Cross-asset Market Story connects prediction markets, treasuries, ES/NQ, BTC, etc.

Explanation contract: WHAT → WHY → evidence → conflicts → model → executable market
→ resolution rules → provenance → raw.

See updated [instrument-cockpit.md](../../product/ux/instrument-cockpit.md).

## 22. Replay

Global historical replay at time T shows only: probability, book, trades, participant
reputation, positions, news, model state, and **rule version at T**. Essential for
honest whale-copy backtesting. Participant rankings must be point-in-time — no
leaderboard leakage or survivorship bias.

## 23. Provider candidates (verify at phase start)

### Kalshi

Characterize: discovery, events, series, rules, settlement sources, books, trades,
history, lifecycle, WebSockets, order entry, fills, positions, fees, demo, rate
limits, participant visibility. Whale intelligence from anonymous large flow only
unless API proves identity.

### Polymarket / Polymarket US

Characterize: Gamma API, Data API, CLOB API, WebSockets, wallet activity, positions,
holders, trades, OI, resolution, chain/settlement (Polygon is network — not
platform), jurisdiction. Do not assume international capabilities for U.S. users.

### Other lawful API-accessible exchanges

Research during feasibility — do not assume Kalshi and Polymarket remain the only
useful providers.

See [PREDICTION_MARKETS_FEASIBILITY_STUDY_PLAN.md](../../research/PREDICTION_MARKETS_FEASIBILITY_STUDY_PLAN.md).

## 24. Data licensing

Per provider: API terms, storage, redistribution, derived-data rights, historical
retention, commercial use, model-training rights. Public API ≠ unrestricted
redistribution.

## 25. Future expansion track ordering

Navigational only — no phase authorized by this list.

```text
Existing canonical foundation (Phases 0–8, UI-001 PASS)
       ↓
Prediction-market feasibility study (Kalshi, Polymarket, alternatives)
       ↓
Accepted prediction-market ADRs
       ↓
Canonical prediction contracts
       ↓
Kalshi read-only adapter
       ↓
Historical replay on admitted prediction bytes
       ↓
Probability research (first track)
       ↓
Polymarket/public participant research (second track)
       ↓
Whale-copy studies (post-observability latency)
       ↓
Cross-market / cross-asset intelligence
       ↓
Simulation extensions
       ↓
Demo/shadow (Kalshi demo where useful)
       ↓
Controlled execution if lawful and authorized
```

See [PREDICTION_MARKETS_EXPANSION_TRACK.md](../../roadmap/PREDICTION_MARKETS_EXPANSION_TRACK.md).

## 26. First research tracks

1. Can an independently calibrated event-probability model identify mispricing
   after realistic spread, fees, and latency? (No auto-trading first.)
2. Do historically skilled domain-specialist participants add incremental
   information **after activity becomes publicly observable**?
3. Do prediction-market probability changes contain incremental information for
   related equities, futures, or crypto?
4. When comparable contracts diverge across venues, which leads and does
   executable convergence remain?

## 27. Proposed ADRs

| Candidate ADR | Topic |
|---|---|
| ADR-PRED-001 | Prediction market instrument and event identity |
| ADR-PRED-002 | Resolution rule versioning and semantic risk |
| ADR-PRED-003 | Implied probability and executable price semantics |
| ADR-PRED-004 | Canonical real-world event mapping |
| ADR-PRED-005 | Public participant identity and Sybil semantics |
| ADR-PRED-006 | Prediction market lifecycle and settlement |
| ADR-PRED-007 | Jurisdiction and execution capability boundaries |
| ADR-SIM-PRED-001 | Prediction market simulation extensions |

Index: [PROPOSED_ADR_REGISTER_PREDICTION_MARKETS.md](../../architecture/PROPOSED_ADR_REGISTER_PREDICTION_MARKETS.md).

## 28. False-edge red team checklist

Survive adversarial review: leakage; hindsight; leaderboard leakage; survivorship
bias; retroactive wallet labels; fee and liquidity omissions; impossible latency;
unrealistic fills; resolution-rule blindness; semantic equivalence assumptions;
hedge blindness; market-maker misclassification; AI-as-oracle; universal score
creep; jurisdiction shortcuts.

Null results are successful outcomes.

## 29. AI / LLM role

LLMs may summarize rules, extract resolution sources, identify semantic differences,
match similar markets, explain results. LLM interpretation is not authoritative.

```text
original rules → deterministic extraction where possible → AI interpretation
  → human-review flag for ambiguity
```

Resolution amendment alerts: `MARKET RULES CHANGED` — what, when, position impact.

## 30. Acceptance conditions for this proposal

Correctly integrated as planning only when:

1. no phase pass status is falsely advanced;
2. no governed evidence is rewritten;
3. prediction markets plug into canonical architecture without an isolated app;
4. provider neutrality, PIT semantics, simulation, explainability, governance survive;
5. no universal buy/whale score or profitability promise is introduced;
6. proposed ADRs remain `PROPOSED` until governance accepts them;
7. Polymarket vs Polygon terminology is preserved;
8. traceability from feasibility plans to future phases is explicit.

## 31. Next authorized step

The next authorized step is **not implementation**. It is:

1. Principal review of this planning package;
2. Authorization of **Prediction Market Feasibility Study** — lawful characterization
   of Kalshi, Polymarket, and discovered alternatives;
3. Acceptance of proposed ADRs individually as decisions mature.

No provider connection, ingestion job, adapter implementation, or trading
authorization follows from this document alone.

## 32. Canonical philosophy (extended)

> **Observe deeply. Estimate independently. Compare against the crowd. Follow
> proven information advantage where it actually exists. Preserve disagreement.
> Model execution honestly. Respect resolution semantics. Abstain when the edge is
> gone.**
