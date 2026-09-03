# Crypto, On-Chain, Influence Intelligence & Profitability Research Expansion

**Logical ID:** `foundation.crypto_influence_expansion.proposal`

**Status:** `PROPOSED` — planning and architecture only

**Date:** 2026-08-16

**Scope:** Future architecture, research planning, capability taxonomy, roadmap
integration, and proposed ADRs for cryptocurrency as a first-class future asset
family; on-chain intelligence; influence intelligence; cross-venue intelligence;
crypto derivatives; wallet/actor research; event-reaction research; copy/follow
research; crypto-native risk and simulation; and Swim With the Whales evolution.

**Implementation authority:** None

**Phase transition authority:** None

**Provider/broker/live-trading authority:** None

## 1. Relationship to existing authority

Revision 3 remains the sole forward-looking canonical foundation authority until
a future revision supersedes it. This document is **subordinate** to Revision 3
on conflict. It does not modify governed evidence, phase pass publications,
accepted ADRs, or `canonical-authority.json`.

Phases 0 through 8 and UI-001 remain `PASS` on the admitted equity intraday
fixture (`ADMITTED-SHORTSQ-BIYA-BARS-001`). This expansion is a **future,
separately authorized track** that begins only after explicit feasibility studies,
accepted ADRs, and phase-gated implementation authorizations.

This document authorizes no provider connection, broker adapter, whale ingestion,
on-chain ingestion, social API connection, model implementation, paper trading,
or live trading.

## 2. Economic objective

The platform is engineered to maximize the probability of discovering and
exploiting **real, reproducible, risk-adjusted, net-of-cost edge** while
aggressively rejecting false edges caused by look-ahead, leakage, latency, fees,
spread, slippage, survivorship, selection bias, overfitting, data snooping,
stale information, bad attribution, unavailable liquidity, unrealistic fills,
manipulated social activity, pump-and-dump behavior, and unrealistic reaction
speed.

> **Find measurable informational or structural advantages, validate them
> honestly, act only when expected opportunity exceeds realistic cost and risk,
> and abstain when it does not.**

No guaranteed profitability is claimed or implied.

## 3. Non-negotiable preservation

Crypto and influence integration must conform to existing foundational rules:

- provider-neutral canonical contracts; providers selected by capability;
- strategies never consume provider SDK objects;
- provenance travels with data;
- `event_time` and availability time are separate;
- correction/revision history is preserved;
- quality failures remain explicit;
- unsupported capabilities remain unavailable;
- bars cannot masquerade as order flow;
- anonymous trades cannot acquire invented participant identity;
- independent risk cannot be bypassed;
- orders cannot directly mutate positions; only fills affect positions;
- deterministic replay must remain deterministic;
- research/model outputs do not independently authorize trades;
- simulation must model realistic execution;
- profitability claims require evidence;
- live trading remains independently gated.

Crypto APIs do not create exceptions.

## 4. Asset-class architecture

### 4.1 Traditional (existing trajectory)

Equities, ETFs, futures, equity options, futures options where supported.

### 4.2 Crypto (future first-class family)

Crypto spot; perpetual swaps; dated crypto futures; crypto options; stablecoins;
tokenized assets where eventually appropriate.

Shared canonical concepts extend existing contracts where possible:

instrument identity; venue; quote currency; base currency; tick; lot; event time;
availability time; provenance; trade; quote; depth; order; fill; fee; position;
P&L; quality.

Asset-specific semantics remain explicit. Crypto is not “stocks that trade 24/7.”

Structural differences include: continuous 24/7 trading; many independent
exchanges; no single consolidated tape; venue-specific books and prices;
maker/taker fees; stablecoin quotes; perpetual funding; liquidations; leverage;
fragmented price discovery; blockchain settlement and finality; wallet activity;
DEX and CEX activity; protocol events; token emissions/unlocks; chain and
exchange outages; stablecoin depegs.

See [CRYPTO_MARKET_STRUCTURE.md](../../architecture/CRYPTO_MARKET_STRUCTURE.md)
and [CRYPTO_ASSET_AND_CAPABILITY_MODEL.md](../../architecture/CRYPTO_ASSET_AND_CAPABILITY_MODEL.md).

### 4.3 Prediction markets (future — separate expansion track)

Event contracts; resolution rules as first-class data; fair-probability research;
public participant intelligence where lawful. Not a gambling silo — integrates
with influence, cross-asset features, and Swim With the Whales.

See [2026-08-16-prediction-markets-expansion-design.md](./2026-08-16-prediction-markets-expansion-design.md).

## 5. Provider-neutral crypto capability model

Capabilities are closed, explicit, and versioned. Examples:

```text
CRYPTO_SPOT_QUOTES | TRADES | DEPTH | EXECUTION
CRYPTO_PERP_QUOTES | TRADES | DEPTH | FUNDING | OPEN_INTEREST | LIQUIDATIONS | EXECUTION
CRYPTO_OPTIONS_CHAIN | QUOTES | GREEKS | EXECUTION
ONCHAIN_BLOCKS | TRANSACTIONS | TOKEN_TRANSFERS | ENTITY_LABELS | DEX_TRADES
SOCIAL_EVENTS | PUBLIC_INFLUENCE_EVENTS
```

Moomoo is one **future candidate adapter**, not the crypto architecture. If
provider A and provider B report different BTC/USD prices, preserve provider,
venue/upstream source, instrument, price, event time, and receive time. Do not
collapse venue-specific markets into a fictional universal price.

## 6. Major future subsystems

| Subsystem | Guidance document |
|---|---|
| Crypto market intelligence | [CRYPTO_ASSET_AND_CAPABILITY_MODEL.md](../../architecture/CRYPTO_ASSET_AND_CAPABILITY_MODEL.md) |
| Cross-venue intelligence | [CROSS_VENUE_INTELLIGENCE.md](../../architecture/CROSS_VENUE_INTELLIGENCE.md) |
| Crypto derivatives | [CRYPTO_DERIVATIVES_INTELLIGENCE.md](../../architecture/CRYPTO_DERIVATIVES_INTELLIGENCE.md) |
| On-chain intelligence | [ON_CHAIN_INTELLIGENCE.md](../../architecture/ON_CHAIN_INTELLIGENCE.md) |
| Influence intelligence | [INFLUENCE_INTELLIGENCE.md](../../architecture/INFLUENCE_INTELLIGENCE.md) |
| Whale / large-capital flows | [SWIM_WITH_THE_WHALES.md](../../architecture/SWIM_WITH_THE_WHALES.md) |
| Profitability research | [CRYPTO_PROFITABILITY_RESEARCH.md](../../architecture/CRYPTO_PROFITABILITY_RESEARCH.md) |
| Simulation and risk | [CRYPTO_SIMULATION_AND_RISK.md](../../architecture/CRYPTO_SIMULATION_AND_RISK.md) |

Each subsystem operates independently from market-data adapters where required
(on-chain and influence engines). Cross-exchange aggregation is a **derived**
layer; underlying venue identity is never discarded.

## 7. Swim With the Whales — unified framework

Three complementary perspectives (see updated doctrine):

1. **Traditional markets:** measurable institutional footprints (disclosures,
   large prints, order flow, options, depth).
2. **Crypto:** observable capital movement (wallets, exchange flows, derivatives,
   cross-venue flow, order books).
3. **Influence markets:** attention that demonstrably converts into capital
   (public event → attention → participation → order flow → positioning → price).

**Central whale rule:**

> Do not follow a whale merely because it appears large. Follow the wake only
> when the wake is measurable, timely, economically relevant, and confirmed by
> the surrounding market. Never assume the whale knows more than the market.

Confluence components remain separately inspectable. No `WHALE SCORE 97` without
a rigorously validated model that defines such a probability.

## 8. Influence intelligence pipeline

```text
Influence event
    → Actor verification
    → Asset resolution
    → Novelty assessment
    → Historical impact model (ACTOR × EVENT TYPE × ASSET × REGIME × HORIZON)
    → Current market reaction
    → Order-flow confirmation
    → Derivatives confirmation
    → On-chain context
    → Liquidity / spread / cost
    → Strategy
    → Risk
    → Execution simulation
```

The strategy may abstain at every stage. Influence is not sentiment alone.

Social research requires point-in-time semantics: first observed content, edits,
deletions, engagement snapshots at publication +10s/+30s/+1m/… — never final
engagement totals for historical prediction.

## 9. Research architecture integration

Extend existing research abstractions — do not fork a parallel crypto framework:

`ResearchDataset`, `FeatureSnapshot`, `ForecastTarget`, `ForecastModel`,
`TrainingManifest`, `Prediction`, `WalkForwardRun`, `CalibrationReport`,
`Experiment`, `StrategySpec`, `SimulationRun`.

See [MODEL_RESEARCH_AND_DATASETS.md](../../architecture/MODEL_RESEARCH_AND_DATASETS.md)
and [CRYPTO_PROFITABILITY_RESEARCH.md](../../architecture/CRYPTO_PROFITABILITY_RESEARCH.md).

## 10. Simulation

The platform's deterministic simulator remains canonical. Broker paper trading is
not the simulation system. Future crypto simulation models venue-specific spread,
maker/taker fees, minimum size, tick/step, slippage, latency, market impact,
liquidity, partial fills, 24/7 sessions, funding, liquidation risk, leverage
constraints, venue outages, and stale books. Spot, perpetual, futures, and options
require distinct fill models.

See [CRYPTO_SIMULATION_AND_RISK.md](../../architecture/CRYPTO_SIMULATION_AND_RISK.md).

## 11. UI integration

Crypto does not create a giant navigation silo. The five-domain model
(NOW / EXPLORE / WORKSPACE / RESEARCH / PORTFOLIO) spans asset classes.
Unsupported cockpit modules remain explicitly unavailable.

See updated [instrument-cockpit.md](../../product/ux/instrument-cockpit.md).

## 12. Future expansion track ordering

This ordering is **navigational** only. No phase is authorized by this list.

```text
Existing canonical foundation (Phases 0–8, UI-001 PASS on admitted fixture)
       ↓
Crypto data feasibility study (Phase 0A-style characterization)
       ↓
Influence feasibility study (separate)
       ↓
On-chain feasibility study (one chain first)
       ↓
Accepted crypto/influence ADRs
       ↓
Crypto canonical contract extensions
       ↓
One verified crypto adapter (capability-honest)
       ↓
Crypto replay on admitted crypto bytes
       ↓
Crypto order flow (when entitled)
       ↓
Crypto derivatives layer (when entitled)
       ↓
Influence event research dataset
       ↓
On-chain intelligence layer
       ↓
Whale confluence research
       ↓
Preregistered crypto/influence strategies
       ↓
Crypto-capable simulation extensions
       ↓
Shadow mode
       ↓
Paper when provider supports it
       ↓
Controlled live authorization (separate, not now)
```

See [CRYPTO_INFLUENCE_EXPANSION_TRACK.md](../../roadmap/CRYPTO_INFLUENCE_EXPANSION_TRACK.md).

## 13. Proposed ADRs

Proposed decisions are recorded in `docs/superpowers/decisions/` with
`status: PROPOSED`. They are **not** registered in `manifests/phase1/adr-registry.json`
until accepted through governance.

| Candidate ADR | Topic |
|---|---|
| ADR-CRYPTO-001 | Crypto instrument and venue identity |
| ADR-CRYPTO-002 | 24/7 accounting boundaries |
| ADR-CHAIN-001 | Blockchain time, finality, and reorg semantics |
| ADR-CHAIN-002 | On-chain entity attribution |
| ADR-INFL-001 | Public influence event identity and versioning |
| ADR-INFL-002 | First-observed and engagement snapshot semantics |
| ADR-INFL-003 | Influence actor identity |
| ADR-VENUE-001 | Cross-exchange aggregation rules |
| ADR-SIM-CRYPTO-001 | Crypto simulation extensions |

Index: [PROPOSED_ADR_REGISTER_CRYPTO_INFLUENCE.md](../../architecture/PROPOSED_ADR_REGISTER_CRYPTO_INFLUENCE.md).

## 14. Feasibility and experiments

Before broad implementation:

- [CRYPTO_FEASIBILITY_STUDY_PLAN.md](../../research/CRYPTO_FEASIBILITY_STUDY_PLAN.md)
- [INFLUENCE_FEASIBILITY_STUDY_PLAN.md](../../research/INFLUENCE_FEASIBILITY_STUDY_PLAN.md)
- [ON_CHAIN_FEASIBILITY_STUDY_PLAN.md](../../research/ON_CHAIN_FEASIBILITY_STUDY_PLAN.md)
- [CRYPTO_INFLUENCE_EXPERIMENT_ROADMAP.md](../../research/CRYPTO_INFLUENCE_EXPERIMENT_ROADMAP.md)
- [PROVIDER_AND_DATA_RESEARCH_MATRIX.md](../../research/PROVIDER_AND_DATA_RESEARCH_MATRIX.md)

Minimum validating dataset principle: procure data for a specific hypothesis
first; add expensive features only when ablation proves incremental economic value.

## 15. False-edge red team checklist

Every apparent crypto/influence edge must survive adversarial review:

- leakage and hindsight; event observability; timestamp alignment;
- final engagement misuse; retroactive wallet labels;
- fee, funding, and liquidity omissions; impossible latency;
- unrealistic fills; survivorship; cherry-picked actors;
- pump chasing; universal score creep; AI execution authority;
- live-trading scope creep.

Null results are successful outcomes.

## 16. Security and licensing

New APIs require secret stores, least privilege, separate read/trade credentials,
audit logs, and no credentials in research artifacts. Document permissible storage,
retention, redistribution, derived data, display rights, and model-training rights
per provider. Social and on-chain datasets are especially sensitive.

## 17. AI / LLM role

LLMs may classify event semantics, resolve entities, summarize evidence, detect
ambiguity, explain results, and research historical analogs. LLM output retains
provenance and uncertainty. LLMs must not invent posts, invent wallet attribution,
place trades, override risk, or treat rumors as facts.

Prefer rules, embeddings, classifiers, and small local models for high-volume
paths; frontier models only for ambiguous cases. See ADR-LLM-001.

## 18. Acceptance conditions for this proposal

This expansion is correctly integrated as planning only when:

1. no phase pass status is falsely advanced;
2. no governed evidence is rewritten;
3. crypto plugs into canonical architecture without a disconnected crypto app;
4. provider neutrality, PIT semantics, simulation, explainability, and governance survive;
5. no universal buy/whale score or profitability promise is introduced;
6. proposed ADRs remain `PROPOSED` until governance accepts them;
7. traceability from donor/research plans to future phases is explicit.

## 19. Next authorized step

The next authorized step is **not implementation**. It is:

1. Principal review of this planning package;
2. Authorization of **Crypto Data Feasibility Study** on a minimal asset set
   (e.g. BTC, ETH, DOGE) using lawful characterization only — no network fetches
   without separate authorization;
3. Parallel authorization of **Influence Feasibility Study** (X API and lawful
   public sources — characterization only);
4. Acceptance of proposed ADRs individually as decisions mature.

No provider connection, ingestion job, adapter implementation, or trading
authorization follows from this document alone.

## 20. Canonical philosophy (extended)

> **Observe deeply. Preserve provenance. Know what was knowable at the time.
> Measure what the data can actually support. Follow observable capital and
> verified attention only when the wake is real. Never optimize a historical
> chart. Optimize the probability that a future observation, processed with
> only information actually available at the time, could produce positive
> risk-adjusted outcome after all realistic costs.**
