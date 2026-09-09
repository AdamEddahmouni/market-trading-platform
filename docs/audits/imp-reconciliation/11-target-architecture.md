# 11 — Target Architecture

Status: **FINAL (WS07, 2026-09-07)** — WS05 preliminary reconciled with
WS06 product/engineering evidence and finalized. The design target;
**nothing here is implemented by WS07** (implementation proceeds via the
master backlog (12) and recovery waves (13)).

WS07 finalization changes: no architectural reversal of WS05; additions and
confirmations are recorded in §13.

Sources: [06-architecture-correctness.md](06-architecture-correctness.md)
(full evidence), [05-capability-matrix.md](05-capability-matrix.md),
[04-current-state.md](04-current-state.md), [02-scope-authority-ledger.md]
(02-scope-authority-ledger.md).

---

## 1. Guiding decisions (WS05 evidence-backed)

1. **One canonical multi-asset domain model, not per-domain stacks.**
   Instrument identity is the XA-01 kernel extended (CRYPTO, Bond descriptor,
   commodity contract identity); Futures/Option contracts stay the typed
   tradable-contract models; the two asset-class vocabularies consolidate into
   one.
2. **The authoritative portfolio becomes denomination-aware and
   instrument-keyed.** Positions are (instrument_id, signed quantity, unit),
   market value = price × qty × multiplier, cash/P&L per currency with an
   explicit FX boundary; options ledger merges in on a single numeric base
   (integer minor units / Decimal).
3. **Risk becomes input/calculation/decision/enforcement/presentation
   separated**, with buying-power, notional exposure, instrument-kind, and
   multi-asset margin as inputs — enforcement stays at submission time.
4. **Market data keeps its envelope/admission/timestamp layer** (verified
   good) and adds an incremental depth engine for Level 2.
5. **Providers keep capability Protocols + fail-closed composition** and add
   a Provider Capability Registry (roles, gates, freshness, discovery).
6. **IBKR becomes one provider with separated sessions** — market-data and
   account/portfolio read paths from the existing observational seed, depth
   capability added, execution separated and LIVE-gated.
7. **Trading keeps the internal-Paper verified core** and adds server-side
   preview binding, content-derived idempotency, working-order remainders,
   replace, cash/BP enforcement, and instrument-kind validation.
8. **Claude Code News / Eric futuresX contribute concepts only**
   (news-driven bracket semantics; depth/contract concepts) — never code;
   browser-driven Tradovate execution is not canonical IMP execution.
9. **No new architectural generation for Bonds/Crypto/Commodities**: they
   ride the shared instrument/portfolio/evidence primitives.

---

## 2. Domain model (target)

| Concept | Target definition |
|---|---|
| User / principal | Single-user local tool with optional auth; loopback-bound; unchanged |
| OperationalIdentity | Unchanged (`mode, broker, account_id, portfolio_id, environment`) — verified |
| Mode | DEMO / PAPER / LIVE with orthogonal data/execution dimensions; process-level; unchanged authority model |
| Account | Operational accounts as today; broker-backed discovery added via provider capability `discover_accounts` when a broker adapter exists |
| Instrument | Canonical identity (XA-01 extended) + typed contracts: EquityInstrument (ticker/exchange/currency/share-class), OptionContract (existing), FuturesContract (existing), BondInstrument (new: issuer, CUSIP/ISIN, maturity, coupon, par, currency, credit tier), CryptoPair (new: base/quote/venue/network, spot|derivative), CommodityInstrument (existing COMMODITY + contract identity via futures relationships) |
| Venue / currency | Venue = venue_id in identity/aliases; currency = per-instrument denomination + per-account base currency; FX layer explicit |
| Quote / Trade / Bar | Unchanged (envelope/admission/normalization/observational state) |
| OrderBook | **New incremental depth engine**: INSERT/UPDATE/DELETE/CLEAR per side+price, per-level sequence, full snapshot on subscribe/reconnect, TTL + stale eviction, `book_sequence` mandatory on live streams |
| Portfolio | Positions keyed by instrument identity with denomination-aware valuation; per-currency cash; merged options legs; margin inputs |
| Position / Balance / Transaction | Derived from event-sourced fills (unchanged) but computed over the multi-asset model |
| Order / OrderDraft / OrderPreview | Draft = frontend typed draft (unchanged); Preview = **server-issued preview record with fingerprint** (intent hash, observation time/cursor, identity, market-state); Order = canonical lifecycle extended (TIF/stop/OCO/bracket/REPLACE states) |
| RiskDecision | APPROVE/RESIZE/REJECT retained; inputs extended (cash/BP, notional, instrument-kind, margin, stale/entitlement) |
| Execution / Fill | Internal simulator retained; fills aggregated (remaining_qty, avg price); replace; late-fill handling |
| Snapshot | Account-scoped snapshot cache unchanged; live book adds staleness |
| ResearchObservation / Signal / Opportunity / Alert | Unchanged evidence chain (NormalizedLaneEvidence → EvidenceV1 → FusedOpportunity); ownership documented; industry lane added via instrument metadata |
| SourceEvidence / Timestamp / Freshness | Unchanged (event/provider/available/received/ingested + admission); depth staleness added; CVD session anchors added |

## 3. Asset-class extensions (target)

One extensible identity kernel (avoid class explosion): `XaAssetClass` +
`InstrumentKind` extended with `CRYPTO` (+ `CRYPTO_PAIR` kind), `BOND`/
corporate variant, commodity contract identity via existing futures model;
typed contract records (`OptionContract`, `FuturesContract` exist; Bond and
CryptoPair as typed dataclasses sharing the descriptor/relationship model).
Gold/Silver remain explicit first-class domains (MND-006/007) implemented as
relationships over commodity primitives.

## 4. Target market-data architecture

```
Provider raw (IBKR L1/L2, Moomoo, futures/bond/crypto adapters)
  → Adapter (capability contracts; IBKR seeded from tools/ibkr)
  → Admission (live_admission unchanged; + depth staleness)
  → Canonical observation (envelope/normalization unchanged)
  → Freshness/Provenance (timestamp set + per-capability TTL + session anchors)
  → Cache/Stream (observational state + incremental book engine + AccountSnapshotCache)
  → Domain consumer (CVD/OFI/LOB engines; order-flow lane; portfolio marks)
  → API/UI (lane projections unchanged shape)
```
Supports L1, L2 (incremental), bars, options chains (provider-backed),
macro (FRED vintages), news (gated).

## 5. Target provider architecture

Provider Capability Registry: provider → roles (MARKET_DATA,
BROKER_EXECUTION, ACCOUNT_DATA, PORTFOLIO_DATA, NEWS, FUNDAMENTALS, MACRO,
REGULATORY, ALTERNATIVE_DATA, AI) → capabilities → env gates → freshness
policy → discovery (`capabilities()` per adapter) → fail-closed
`UNSUPPORTED_CAPABILITY`. Roles:

| Provider | Target roles | Notes |
|---|---|---|
| IBKR | MARKET_DATA (L1+L2, required for CVD), ACCOUNT_DATA, PORTFOLIO_DATA, (EXECUTION separated, LIVE-gated) | Seed `tools/ibkr`; depth engine; paper account ↔ PAPER mode mapping |
| Moomoo | MARKET_DATA (observational) | unchanged |
| Tradier | BROKER_EXECUTION (sandbox paper, fixture-first → verified wire) | unchanged direction |
| FinViz | FUNDAMENTALS/SCREENING | unchanged |
| SEC/EDGAR/FTD, FINRA/NASDAQ/NYSE/CBOE | REGULATORY/DISCLOSURE | unchanged |
| FRED/ALFRED, CFTC, EIA, NOAA | MACRO | unchanged |
| Anthropic | AI (assistant) | optional; abstraction boundary retained |
| Tradovate | BROKER_EXECUTION (Futures) — if retained as primary | decision OPEN (D3/D16); adapter, never CDP browser |
| Crypto venues, Bond providers, Commodity providers | TBD | no invented commitments |

## 6. Target trading architecture

```
Draft (frontend typed) → Preview (server-issued, fingerprinted:
intent hash + observation time/cursor + identity + market-state)
 → Risk (inputs: cash/BP, notional, instrument-kind, limits; decision:
APPROVE/RESIZE/REJECT) → Confirmation (UI, current-preview required)
 → Submission Intent (content-derived idempotency key, client_order_id)
 → Provider Adapter (capability contract; internal simulator | broker adapter)
 → Provider Ack (SUBMITTED/ACKNOWLEDGED) → Canonical Order State (lifecycle
+ REPLACE states) → Fill/Reconciliation (multi-fill aggregation; broker-
authoritative reconciliation; late-fill/cancel handling)
```
Invariants: stale previews never submit (server binding); retries never
duplicate (content-derived keys + per-ledger lock); provider state and local
state never silently diverge (BROKER mode reconciliation); continuous/family
futures symbols never executable (instrument-kind validation).

## 7. Target portfolio architecture

Reconciled from: provider snapshots (broker paths) + fills (event-sourced
ledger) + market prices (marks with freshness). Positions keyed by instrument
identity; denomination-aware valuation; per-currency cash + explicit FX;
realized/unrealized P&L computed once in the canonical ledger (backend
authoritative; frontend renders only); attribution parity invariant retained.

## 8. Target risk architecture

Inputs (positions, prices, multipliers, margins, FX, cash, stale/entitlement
state) → Calculation (per-asset exposure → aggregate notional/gross/net) →
Decision (limits vs aggregate, APPROVE/RESIZE/REJECT) → Enforcement
(submit-time, cannot be bypassed) → Presentation (ticket/portfolio/dashboard).
Order of increments: (1) buying-power + instrument-kind (P2 today), (2)
notional/margin multi-asset (with ADR-C-001), (3) concentration/leverage.

## 9. Target intelligence architecture

Unchanged chain, extended: participants (envelopes) + government (FRED/CFTC/
EIA/NOAA vintages + policy/regulatory workflow lane) + news/market-context →
NormalizedLaneEvidence → EvidenceV1 (specialist) → FusedOpportunity →
decision gates. Industry: instrument-metadata dimension + evidence lane (no
new stack). One documented evidence ownership model (three homes → explicit
boundaries at WS07).

## 10. Target frontend architecture

Server-state ownership (React Query) with **mode-scoped lane keys**
(`["mode", "workspace", symbol, lane]`); account/mode context from `/context`
unchanged; route domains per product area (Dashboard/Markets/Research/
Portfolio/Trading/Orders/Analytics + domain lanes incl. new domains);
trading draft lifecycle unchanged (typed draft + re-preview) with server
preview tokens; data-freshness display from lane provenance + admission
quality. No visual redesign in WS05.

## 11. Target test architecture

Layers: domain unit (existing + numeric goldens), provider contract (add
IBKR L1/L2, depth engine, crypto/bond stubs), integration (existing),
safety regression (existing mandatory invariants + §67 additions: preview
binding, duplicate-under-retry, cancel races, depth reconnect/reset, stale
depth, instrument-kind rejection, query-key isolation), UI component
(existing), E2E (deferred; not required for local tool). Each ADR candidate
(06 §61) lists its required regression suites.

## 12. Open inputs carried to WS07

- Future execution provider: IBKR vs Tradovate vs both (D3/D16) — adapter
  shape recommended here; provider choice is a product/professor decision.
- Paid options providers (Unusual Whales / iVolatility): not required
  (donor-specific); IB option chain is authorized-optional (LATER-007).
- IB data purchase status (D13): unknown; adapter design independent.
- Which whale evidence families become provider-backed (D20): product
  decision.
- Crypto/bond/commodity provider commitments: TBD — no inventions here.

WS07 will convert this target + the ADR candidates into dependency-aware
remediation increments and the master backlog.

---

## 13. WS07 finalization (2026-09-07)

### 13.1 Finalized decisions (engineering-correctness ones resolved, product ones left explicit)

| Topic | Final decision | Status | Owner (if product) |
|---|---|---|---|
| Canonical instrument identity | XA-01 kernel extended (CRYPTO class + CRYPTO_PAIR kind + pair/venue identity; typed BondInstrument with issuer/CUSIP/maturity/coupon/par/credit; commodity contract identity via futures relationships); `symbol` ≠ `ticker` ≠ `instrument_id` ≠ `contract_id` ≠ `underlying_id` ≠ `asset` ≠ venue-specific identifier; continuous/family symbols never executable (instrument-kind validation at submission) | RESOLVED (RC-004, BL-0101..0104, BL-0203) | — |
| Asset-class vocabulary | ONE canonical vocabulary in XA-01; `paper.contracts.ASSET_CLASSES` deprecated with compat shim until consumers migrate | RESOLVED (RC-004, BL-0101) | — |
| Portfolio | Instrument-keyed positions + denomination-aware valuation (price × qty × multiplier); per-currency cash + explicit FX boundary; options ledger merged on integer-minor/Decimal; equity behavior parity-protected; USD-only documented | RESOLVED (RC-001, BL-0105..0108) | — |
| Risk | input → calculation → decision → enforcement → presentation separated; buying-power/cash + instrument-kind first, then notional/margin multi-asset, then concentration/liquidity advisory | RESOLVED (RC-006, BL-0202/0203/0209) | — |
| Trading lifecycle | Current states retained + PREVIEW/VALIDATED/CONFIRMED (server preview record) + REPLACE_PENDING/REPLACED + working remainder/fill aggregation + late-fill reconciliation; TIF/stop/OCO/bracket designed into the order model (CCN concepts reimplemented, never copied) | RESOLVED (RC-005/007/008, BL-0201/0204/0205/0206/0207) | — |
| Preview/submission | Server-issued preview_id + fingerprint (intent hash, observation time/cursor, identity, market-state); stale → PREVIEW_STALE rejection; UI carries preview_id | RESOLVED (RC-005, BL-0201) | — |
| Provider architecture | Protocol-per-capability retained + Provider Capability Registry (roles → capabilities → gates → freshness → discovery) + fail-closed UNSUPPORTED_CAPABILITY; browser-driven Tradovate CDP NOT canonical (concept-only) | RESOLVED (RC-009, BL-0401) | — |
| IBKR | One adapter, market-data + account/portfolio sessions seeded from `tools/ibkr`; execution separated and LIVE-gated; pacing/penalty box reused; paper ↔ PAPER account mapping | RESOLVED (RC-002, BL-0301/0305, D19 SEED) | — |
| Level-2 | Incremental depth event model (INSERT/UPDATE/DELETE/CLEAR per side+price) + full snapshot on subscribe/reconnect + per-level sequence + TTL/stale eviction + truthful book validity + delta-based OFI | RESOLVED (RC-003, BL-0302/0303/0306) | — |
| API contracts | Canonical 12-category error taxonomy + generated/shared contracts (OpenAPI/codegen from projection builders) with schemas.test.ts interim | RESOLVED (RC-010, BL-0702/0703, D24/D25) | — |
| Frontend state | Query-key factory with mode/account/provider/as-of dimensions; scrub invalidates lanes; isolation test | RESOLVED (RC-011, BL-0701, D23) | — |
| Product IA | Dashboard / Markets / Research / Portfolio / Trading / Orders / Analytics / Intelligence / Settings; asset workflows nested; no per-asset silo apps | RESOLVED (RC-015, BL-0705) | — |
| Claude Code News | KEEP_AS_PRODUCT_REQUIREMENT (news buffering, daily brief, trade discipline, bracket semantics, trailing ladder, one-trade/day, shadow logs, honest limits — reimplemented natively); REIMPLEMENT_NATIVE (TradingView CDP → provider adapter only); REFERENCE_ONLY (launchd, iMessage, SIGUSR ops model); DO_NOT_ADOPT (CDP-driving Tradovate DOM). Tradovate role = optional BROKER_EXECUTION adapter, provider choice OPEN (D3/D16) | RESOLVED (WS05 §11 + WS07) | Provider choice: DECISION_REQUIRED (professor/product) |
| Futures execution provider | IB vs Tradovate vs both as capability adapters; choice product-dependent | DECISION_REQUIRED (D3/D16) | professor/product |
| IB data purchase | unknown; does not block adapter design | OPEN (D13) | Adam/professor |
| Whale families elevation | 13F/crowding/skill first per SWIM_WITH_THE_WHALES doctrine; fixture-first retained | RECOMMENDED (BL-0601, D20) | product |
| Crypto/bond provider commitments | TBD at implementation; identity + research + portfolio compatibility first (CORE); wallet execution = POST_CORE | OPEN (D14) | product |

### 13.2 Scope boundary (core completion vs post-core, controller §14)

| Class | Content |
|---|---|
| CORE_COMPLETION | Identity for all 8 asset domains; multi-asset portfolio/risk base; IBKR L1/L2 CVD path (professor-required); Paper workflow + preview binding + BP enforcement; Bonds/Crypto/Gold/Silver/Commodities/Industry/Government structural integration (research + portfolio compatibility + truthful surface); intelligence layers surfaced; canonical API/frontend state; validated dev system |
| POST_CORE_EXTENSION | Live execution (LIVE-001 authorization); on-chain crypto wallet execution; paid premium data subscriptions beyond IB L1/L2; advanced strategies (calibrated squeeze predictor, sophisticated options strategies); production-grade multi-process deployment |
| EXPERIMENTAL | Provider-specific research experiments (fixture-based); MRA AI research depth |
| RESEARCH_ONLY | Admitted donor fixtures (CVD NVDA, Options BIYA) — never runtime authority |
| DEVELOPER_INFRASTRUCTURE | Validation, CI, commands, docs governance, AGENTS — reported separately (18) |

### 13.3 Architecture quality gate (controller §66) — all answers exist in this file + 06

How an instrument is identified (XA-01 + typed contracts) · how an account is
identified (OperationalIdentity, verified) · how a provider capability is
selected (Capability Registry) · how market data becomes canonical
(envelope/admission/normalization, verified) · how L2 state is built
(incremental depth engine) · how freshness is tracked (TimestampSet + TTL +
session anchors) · how portfolio state is calculated (denomination-aware
ledger) · how risk is calculated/enforced (input→decision→enforcement) · how
an order is previewed (server preview record) · how submission is bound
(preview fingerprint) · how provider state reconciles (broker-authoritative
reconciliation) · how evidence becomes opportunity (evidence chain → fusion) ·
how UI state is scoped (mode/account query keys) · how multi-asset domains
reuse primitives (shared identity/portfolio/evidence, no silos).