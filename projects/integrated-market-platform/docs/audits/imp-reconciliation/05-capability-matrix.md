# 05 — Capability Matrix (authoritative combined: REQUIREMENT + PROVENANCE + IMPLEMENTATION + VERIFICATION + STATUS)

Status: **COMPLETE (WS04, 2026-09-06/07)**. Supersedes the WS02 scope-only and
WS03 provenance passes. This is the authoritative combined matrix. Fields per
capability: Capability · Authorized requirement · Authority · Importance ·
Current implementation locations · Runtime path · Provider/data dependency ·
Tests · Verification depth · Status · Known defects · Missing behavior ·
Provenance · Confidence · Recommended next action.

Authority legend: A=ORIGINAL · B=PROFESSOR · C=ADAM MANDATE · D=DONOR ·
E=SUPPORTING · F=IMPLEMENTATION. Importance: CORE_REQUIRED /
IMPORTANT_SUPPORTING / OPTIONAL / FUTURE / EXPERIMENTAL / DETAILS_TO_BE_DEFINED.
Verification depth: V0 presence · V1 unit · V2 focused runtime · V3
integration · V4 end-to-end workflow · V5 production readiness.
Confidence: CONFIRMED · HIGH_CONFIDENCE · MODERATE_CONFIDENCE · LOW_CONFIDENCE · UNKNOWN.

Baseline for all "Tests" rows: fresh `validate full` = 3580 tests, 48 skipped,
1 failure (excluded dirty-tree `cross_lane` golden), 0 errors; per-suite
counts from `.local/ws04-full.json` (evidence in 15).

---

## 1. Platform & market-data foundation

| Capability | Authorized requirement | Authority | Importance | Implementation locations | Runtime path | Provider/data dependency | Tests | Verif. depth | Status | Known defects | Missing behavior | Provenance | Confidence | Next action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Platform foundation (config/env/auth/authz/identity/secrets/error handling/health) | Supporting architecture; fail-closed | E (+ safety invariants) | CORE_REQUIRED | `operating_modes.py`, `operational_identity.py`, `platform/security/*`, `request_auth.py`, `credential_audit.py`, `offline_guard.py`, `canonical.py`, `errors.py` | Env gates at startup; session tokens; loopback-only; offline network denial | none (stdlib-only) | platform 474, phase0 51, postroot 40, validation 60 | V3 | COMPLETE_VERIFIED | none found | V5 (production ops) unverified | native | CONFIRMED | Keep; WS05 correctness pass |
| Market data layer (normalization, PIT, provenance, quality, caching) | Supporting architecture | E | CORE_REQUIRED | `market_data/*` (live_runtime, admission, observational_state, recorder, replay), `providers/envelope.py`, `runtime/bitemporal_store.py`, `runtime/pit_joins.py`, `storage/*` | Envelope → admission → observational state; live runtime gated | Moomoo OpenD (gated); fixtures; recorded replay | market_data 44, runtime 22, storage 9, ibkr 47 | V3 offline / V2 live-gated | COMPLETE_UNVERIFIED (live paths) | Live wires unverified (EVIDENCE-01B not accepted) | Verified real-wire observational campaign (G5) | native (GridIQ PORT_ADAPT for caching only) | HIGH_CONFIDENCE | WS05/W06 |
| Instrument identity (multi-asset kernel) | Cross-asset canonical identity (XA-01) | E | CORE_REQUIRED | `xa01/*` (enums, kernel), `xa04/*` (catalog persistence), `contracts/identity.py` | Identity kernel + catalog store | none (stdlib) | xa01 12, xa04 30 (6 skip) | V3 | PARTIAL | No CRYPTO asset class; no bond maturity/coupon fields; gold/silver only as generic COMMODITY; no crypto venue identity | Crypto venue/chain id; bond detail; per-commodity contract identity | IMP-XA-01 accepted w/ limitations | HIGH_CONFIDENCE | WS05 multi-asset target fit |

## 2. Market/asset domains

| Capability | Authorized requirement | Authority | Importance | Implementation locations | Runtime path | Provider/data dependency | Tests | Verif. depth | Status | Known defects | Missing behavior | Provenance | Confidence | Next action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Equities (general research) | Core domain | A/B/E | CORE_REQUIRED | discovery/, finviz/, news/, research/, market_data/equity | discovery screens → workspace lanes | FinViz (gated), news (gated), fixtures | platform 474, research 104, finviz 57 | V3 | COMPLETE_UNVERIFIED | live gates closed | provider-verified research feeds | original | HIGH_CONFIDENCE | WS06 |
| Short Squeeze | Evidence-driven research screener; part of integrated platform (ORG-001, LATER-013) | A + B | CORE_REQUIRED | `short_intelligence/*` (squeeze, pressure, features, store), `contracts/squeeze_structural.py`, `squeeze_models/*`, `donor_bridge/squeeze_client.py`, child `short-squeeze-project` (ADAM pins, `adam_v1.py`) | providers → store → pressure state → allocation hints → squeeze bridge :8787 → projections → UI | FINRA/NASDAQ/NYSE/CBOE RegSHO, SEC FTD (gated); child screener FROZEN_DEMO server (not running) | short_intelligence 37, squeeze_models 11, donor_bridge 87 (8 skip) | V3 | PARTIAL | No calibrated squeeze predictor (explicitly NOT_CALIBRATED, Phase 4 skeleton); borrow/CTB/locate UNKNOWN (no lending source); squeeze bridge server not running (skip) | Calibration (Phase 4); borrow/lending data; calibrated prediction | original screener + provenance gates (INT-014/015) | HIGH_CONFIDENCE | WS05/07: calibration plan; bridge runtime |
| CVD / Level 1 / Level 2 | CVD calc, L1+L2 data, depth, aggressor classification (LATER-001/002) | B (+D) | CORE_REQUIRED | `donor_patterns/cvd_formulas.py` (Lee-Ready, BVC, cumulative delta, OFI), `order_flow/*` (cvd, aggressor, l1, ofi, lob_*), `providers/adapters/fixture_order_flow.py`, `recorded_order_flow.py`, `live_projections.build_live_order_flow_payload` | Formula library → fixture/recorded replay → workspace; Moomoo live path when gates open | **IBKR L1+L2 REQUIRED (LATER-002) — MISSING**; Moomoo live (gated); NVDA/ES fixtures | order_flow 66, formulas 30, market_data 44, donor_patterns 14 | V3 formula+fixture; V2 live-code | PARTIAL | IBKR L2 absent; IBKR L1 observational not wired to CVD; ingest does not classify live trades (fixture pre-baked delta); OFI BBO-only | IBKR L1/L2 runtime integration; runtime trade classification from live tape | CVD Bubble concepts (INT-005/006) — reimplemented, Q-hardened | CONFIRMED | WS05/07: IB L1/L2 adapter (P1-1) |
| Options | Chains/strikes/expirations, volume/OI, Greeks, unusual activity, confirmation, risk (LATER-004/007) | B (+D) | CORE_REQUIRED | `options/*` (iv, greeks, surface, surface_qa, risk_neutral, breeden_litzenberger, delta_hedged, event_vol, strategy, edge, flow, payoff, execution, r_o6, zerodte), `donor_patterns/options_lane.py`, `cboe_options/*`, `portfolio/options_ledger.py`, `providers/adapters/fixture_options.py`, `option_contract_builder.py` | fixtures (BIYA/NVDA) → analytics engines → workspace options lane; CBOE public stats (gated) | BIYA/NVDA fixtures; CBOE options stats (gated); **no live chain provider** (protocol only) | options 147, cboe_options 46, formulas 30, contracts 38 | V3 | PARTIAL | No provider chains; no Greeks/IV from live market; execution = conservative simulator on fixtures; BL needs ≥3 strikes | Live OptionChainProvider; dealer gamma flow correctness (R-07); provider Greeks | internship concepts (INT-007/008/009), reimplemented | CONFIRMED | WS05/07: chain provider, O-series completion |
| Futures | Contract identity, market data, L2, news, execution, risk, automation (LATER-003/005/008/011) | B (+D) | CORE_REQUIRED | `contracts/futures.py`, `futures/*` (roll, curve, basis, carry, continuous, notional, positioning, leverage_stress, relative_value, advanced_*), `donor_patterns/futures_lane.py`, `order_book_lane.py`, `providers/adapters/fixture_futures*`, `live_cftc_positioning.py` | fixtures (ES/CL) + CFTC COT (gated) → engines → workspace futures lane | fixtures; CFTC COT live (gated); **IBKR futures runtime MISSING; Tradovate MISSING** | futures 65, contracts 38, distribution 9 | V3 | PARTIAL | `futures_positioning` label for depth-derived imbalance (self-declared); no live futures bars; no margin engine beyond fixtures | IBKR/Tradovate runtime; curve/carry on live data; futures execution | futuresX patterns (INT-010/011), reimplemented; CCN NOT integrated (INT-012) | CONFIRMED | WS05/07: provider decision (IB vs Tradovate vs adapters — D3/D16) |
| Bonds / Fixed Income | Treasuries/yields/curve/rates/duration/credit/portfolio (MND-001) | C | CORE_REQUIRED (domain) | `xa02/*` (FRED rates vertical, PIT, typed cross-asset refs), `fred/*`, `xa01` SOVEREIGN_DEBT identity, `PriceUnitKind.YIELD_RATE` | FRED/ALFRED (gated) → XA-02 vertical → rates context | FRED/ALFRED (gated) | xa02 21, fred 30 | V3 (groundwork) | MISSING (domain) / PARTIAL (groundwork) | No bond instruments, maturities, duration, credit spreads, corporate bonds, pricing, portfolio | Whole domain | no donor lineage; XA-02 accepted | HIGH_CONFIDENCE | WS07 backlog (never OUT_OF_SCOPE) |
| Crypto | Market data/assets/analytics/portfolio/intelligence (MND-002) | C | CORE_REQUIRED (domain) | LaneId.CRYPTO declared; planning docs (`docs/research/CRYPTO_*`, `ON_CHAIN_FEASIBILITY_STUDY_PLAN.md`, `docs/architecture/CRYPTO_*`) | none | none | none | V0 | MISSING | — | Whole domain | no donor lineage; planning docs | CONFIRMED (absence) | WS07: feasibility → increment |
| Gold | Pricing/data, futures/spot/ETF relations, portfolio exposure (MND-006) | C | CORE_REQUIRED (domain) | GC key in `xa03/catalog.py`, `eia/cross_asset.py` family IDs; COMMODITY identity class | none | none | none | V0 | MISSING | — | Whole domain | no donor lineage | CONFIRMED (absence) | WS07 |
| Silver | Same as Gold, explicitly visible (MND-007) | C | CORE_REQUIRED (domain) | SI key in `eia/cross_asset.py` family IDs | none | none | none | V0 | MISSING | — | Whole domain | no donor lineage | CONFIRMED (absence) | WS07 |
| Broader Commodities | Energy/ag/industrial metals/precious (MND-008) | C | CORE_REQUIRED (domain) | `eia/*` (EnergyCommodity, CL/NG), `cftc/*` COT, `futures/families/registry.py` (CL/NG/RB/HO), `fred/cross_asset.py` | EIA/CFTC (gated) → macro context | EIA, CFTC (gated) | eia 23, cftc 20, energy domain 324 | V3 (energy groundwork) | PARTIAL (energy) / MISSING (domain) | No agriculture/industrial metals/portfolio/analytics | Commodity domain beyond energy macro | no donor lineage | HIGH_CONFIDENCE | WS07 |

## 3. Cross-market intelligence layers

| Capability | Authorized requirement | Authority | Importance | Implementation locations | Runtime path | Provider/data dependency | Tests | Verif. depth | Status | Known defects | Missing behavior | Provenance | Confidence | Next action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Whale / Large-Participant | Large trades/options flow/block/institutional behavior (MND-003) | C | CORE_REQUIRED (domain) | `participant/*` (institutional_13f, metaorder, forced_flow, crowding, derivatives, skill, copyability, cross_asset, evidence, bridge), `donor_patterns/edgar_whale.py`, `donor_patterns/{fund_etf,large_print,order_book,catalyst}_lane.py`, `cross_lane/evidence.py` signals, `intelligence/*` | fixtures (13F/crowding/skill/fund-etf/large-prints/metaorder/MBO) → participant lane → cross-lane evidence → fusion | SEC EDGAR (gated); fixtures | participant 76, sec_edgar 21, donor_patterns 14, cross_lane 39 | V3 (fixture lanes) | PARTIAL | Fixture-only data for most families; fusion golden test blocked by dirty tree; live feeds absent | Live 13F/fund-flow/metaorder feeds; full fusion participation; UI whale cockpit | independent (INT-016/017); SWIM_WITH_THE_WHALES doctrine | MODERATE_CONFIDENCE | WS05/07: elevate families per doctrine |
| Industry Intelligence | Sectors/industries/peers/trends/supply chains (MND-004) | C | CORE_REQUIRED (domain) | none (only incidental "industry" text in `market_context/impact_components.py`) | none | none | none | V0 | MISSING | — | Whole domain | no donor lineage | CONFIRMED (absence) | WS07 |
| Government / Public-Sector | Macro/policy/central banks/Treasury/regulatory (MND-005) | C | CORE_REQUIRED (domain) | `fred/*`, `cftc/*`, `eia/*`, `weather/*`, `sec_edgar/*`, `sec_ftd/*`, `cboe_regsho/*`, `market_context/macro.py`, `xa02/*`, `xa03/*` | providers → PIT verticals → market context macro | FRED, CFTC, EIA, NOAA/NWS/CPC, SEC, CBOE (all gated) | fred 30, cftc 20, eia 23, weather 41, sec_edgar 21, sec_ftd 16, market_context 123 | V3 offline / live-gated | PARTIAL (provider/macro layer) / MISSING (policy/regulatory workflow) | No policy/legislation/contracts workflow; live gates closed | Government policy/regulatory event intelligence beyond macro | no donor lineage; independent providers | HIGH_CONFIDENCE | WS05/07 |
| Market Context / News | News, catalysts, narrative, sentiment, surprise, reaction (B/C/E) | B/C/E | CORE_REQUIRED | `market_context/*` (catalyst, sentiment, event_clustering, entity_resolution, expectations, reaction, propagation, synthesis, narrative, macro, impact_components), `news/*` (aggregator, providers), `donor_bridge/projections.py` (catalyst bridge) | fixtures (BOXL catalyst, BIYA disclosure) + news providers (gated) → workspace lanes | NewsAPI/Finnhub (gated), fixtures | market_context 123, news 5, donor_bridge 87 | V3 | PARTIAL | No unified cockpit (self-declared deficiencies 1–10 in MARKET_CONTEXT audit); LLM extraction ungoverned in donor path | Entity resolution runtime; surprise engine; reaction fusion on live data | catalyst concepts (INT-009), independent MC work | MODERATE_CONFIDENCE | WS06 |
| Research | Symbol research, watchlists, screeners, fundamentals, technicals, notes, AI assist (E/B/C) | E/B/C | CORE_REQUIRED | `research/*` (baseline, decision_research, dataset_pipeline, evaluation), `assistant/*` (MRA-001/002), `ui_api` discovery/research projections, `ui/src/components/research*` | research pipeline → projections → UI research pages | fixtures; news (gated); Anthropic optional | research 104, assistant 17, phase5r 14, mra001 3, mra002 3 | V3 | PARTIAL | No provider-backed fundamentals/technicals; assistant inference stub default | Live fundamentals; provenance-tracked AI research | native + GridIQ PORT_ADAPT (assistant store) | MODERATE_CONFIDENCE | WS06 |
| Analytics | Performance/returns/attribution/risk/cross-asset (E/C) | E/C | IMPORTANT_SUPPORTING | `attribution/*`, `reporting/*`, `distribution.py`, `analysis.py`, `portfolio/attribution_materializer.py`, `ui_api` research-analytics + strategy-profitability | fill-driven attribution → projections → UI | internal (ledger) | distribution 9, platform 474 (attribution parity), of02 33 | V3 | PARTIAL | Cross-asset analytics missing; attribution sidecar non-authoritative (declared) | Cross-asset analytics; user-facing analytics workflow completeness | native (P0-4 attribution parity) | MODERATE_CONFIDENCE | WS05/06 |

## 4. Trading / portfolio / platform services

| Capability | Authorized requirement | Authority | Importance | Implementation locations | Runtime path | Provider/data dependency | Tests | Verif. depth | Status | Known defects | Missing behavior | Provenance | Confidence | Next action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Portfolio / Accounts | Multi-account, positions, P&L, orders/fills, snapshots (E) | E | CORE_REQUIRED | `portfolio/ledger.py`, `portfolio/options_ledger.py`, `paper/ledger.py`, `ui_api/paper_projections.py`, `account_registry.py` | fill-driven ledger → projections → UI | internal | platform 474 | V3 | PARTIAL (equity-functional; multi-asset NOT functional) | Equity-only authoritative ledger; options ledger separate; no futures/bonds/crypto positions | Multi-asset portfolio semantics (P1-2) | native | CONFIRMED | WS05 multi-asset portfolio (P1-2) |
| Multi-account | Account discovery, selector, identity, switching, scoped caches (E) | E | CORE_REQUIRED | `operational_identity.py`, `account_registry.py`, `account_snapshot_cache.py`, `ui_api/server.py /accounts`, canary contexts | identity → account registry → scoped cache keys → projections | internal | platform 474, ui1 13 | V3 | PARTIAL / COMPLETE_UNVERIFIED | Broker-backed accounts absent (live blocked) | Verified broker account discovery | native (TD-003 closure VALID — evidence reproduced) | HIGH_CONFIDENCE | WS06 |
| Trading lifecycle | preview → risk → submit → fill/cancel → reconciliation (E) | E | CORE_REQUIRED | `paper/execution.py`, `paper/contracts.py`, `paper/broker_paper.py`, `execution/simulator.py`, `execution/options_conservative.py`, `ui_api/server.py` POST routes | Workspace draft → preview (revalidate) → submit (idempotent) → simulator fill → ledger → cancel | internal; Tradier/Moomoo sandbox fixtures | execution 2, phase7 3, platform 474, rt01 26 | V3 | PARTIAL (internal Paper COMPLETE_VERIFIED; broker paper PARTIAL; LIVE MISSING) | Broker wire fixture-only; cancel limited to ACTIVATED/WORKING; bar-conservative fills only | Broker paper real wire; partial-fill sophistication; LIVE (blocked by design) | native; RT-01 traced | CONFIRMED | WS06 broker wire; WS05 correctness |
| Risk enforcement | Buying power, position/order limits, concentration, stale data (E) | E | CORE_REQUIRED | `risk/decision.py`, `risk/kill_switch.py`, `risk/policy.py`, `market_data/live_admission.py` (stale/disconnect fail-closed) | evaluate_risk on preview+submit; kill switch; max order/position/open orders | internal | platform 474, phase7 3, intelligence 1165 (governance/qualification) | V3 | PARTIAL (equity core ENFORCED; breadth advisory/missing) | No multi-asset risk (P1-2); concentration/gross/net advisory only; no margin/leverage for futures | Multi-asset risk; margin; concentration enforcement | native | HIGH_CONFIDENCE | WS05 |
| Demo / Paper / Live | Mode isolation; Live observational only; LIVE-001 blocked (E+safety) | E + safety invariants | CORE_REQUIRED | `operating_modes.py`, `operational_identity.py`, `paper/execution.py` authority checks, `market_data/live_runtime.py`, `platform/security/*` | UI mode context → backend authority → account-scoped query keys → provider gate | internal; Moomoo/IBKR observational (gated) | platform 474, intelligence 1165 (paper governance/qualification), mandatory invariants 21 | V3 | COMPLETE_UNVERIFIED (Live blocked by design) | Live observational wires unverified | Real-wire observational verification (G5/EVIDENCE-01C deferred) | native | CONFIRMED | WS06 |
| Alerts / Automation | Alerts, automation (E) | E | IMPORTANT_SUPPORTING | `strategy/scanning.py`, `strategy/runtime.py`, `strategy/eligibility.py`, `of03` workflow registry | scanning → eligibility gate → runtime (research/paper) | internal | strategy tests in intelligence 1165 | V3 | PARTIAL | Automation is research/paper-scoped; eligibility gate enforced for execution claims | Production automation/alerts UX | native (P1-1 eligibility gate) | MODERATE_CONFIDENCE | WS06 |
| Dashboard / UX | Integrated workstation UX (E) | E | IMPORTANT_SUPPORTING | `ui/src/components/*` (Mode*Route per demo/paper/live; 11 workspace lanes; operator control; canary; assistant) | React routes → API → projections | internal | UI 438 passed, typecheck clean | V3 | PARTIAL | No lanes for Bonds/Crypto/Gold/Silver/Commodities/Industry/Government/Whale-cockpit | New-domain pages; unified whale/market-context cockpit | native | HIGH_CONFIDENCE | WS06 |
| API reality | Read-only + gated POST surfaces (E) | E | CORE_REQUIRED | `ui_api/server.py` (90+ routes), projections modules | GET/POST handlers → projections → store/providers | internal; live routes gated | ui1 13, ui2 5, platform 474, mra001 3, mra002 3 | V3 | COMPLETE_UNVERIFIED → PARTIAL | Fixture-only routes present (workspace lanes); no route for new domains | New-domain routes; provider-live route verification | native | HIGH_CONFIDENCE | WS06 |

## 5. Engineering infrastructure (never inflates product completion)

| Capability | Requirement | Authority | Importance | Implementation | Tests | Verif. depth | Status | Confidence |
|---|---|---|---|---|---|---|---|---|
| Validation system (imp.py, validate.py, manifest) | DEVPOS | E | DEVELOPER_INFRASTRUCTURE | `tools/*`, CI workflows | validation 60 + full ladder | V3 | COMPLETE_VERIFIED (V3; `validate changed` under-select in monorepo = known gap) | HIGH_CONFIDENCE |
| Governance/docs/agent workflows | DEVPOS | E | DEVELOPER_INFRASTRUCTURE | PROGRAM_STATUS, MASTER_ARCHITECTURE, WORK_LOG, AGENTS.md, `.cursor/*` | docs link checks | V3 | COMPLETE_UNVERIFIED (roadmap stale vs mandate — MS-13) | HIGH_CONFIDENCE |

---

## 6. Provenance columns (from WS03; corrected in WS04)

| Capability | Lineage | Donor dependency | Mistaken-donor exposure | Integration status |
|---|---|---|---|---|
| Short Squeeze | original screener + provenance gates | SRC-008 (original) | none | INT-014/015 ACTIVE |
| CVD/L1/L2 | `cvd_formulas.py` reimplemented from CVD Bubble concepts | SRC-003 concepts + fixture | none | INT-005/006 ACTIVE; **IBKR runtime MISSING (P1-1)** |
| Options | `options_lane.py` reimplemented from internship concepts | SRC-004 concepts + field shapes | none | INT-007/008/009 ACTIVE |
| Futures | `futures_lane.py`/`order_book_lane.py` PORT_ADAPT | SRC-005 concepts | none | INT-010 ACTIVE (patterns); INT-011 (IBKR runtime) / INT-012 (CCN) NOT integrated |
| Dataset projection/caching | independent (sha256, logical_ids) | SRC-002 patterns (PORT_ADAPT) | governance only | INT-001 ACTIVE; KEEP + re-annotate (WS07) |
| Assistant/UI patterns | independent | SRC-002 concepts | governance only | INT-002/003/004 ACTIVE; re-annotate |
| Whale/Market Context | independent evolution | none | none | INT-016/017 ACTIVE |
| IBKR observational tooling | independent (ADR-LIVE-002) | none (donor-independent) | none | **PRESENT since 8/24 — WS03 provenance map missed it; corrected here** |
| Bonds/Crypto/Gold/Silver/Commodities/Industry/Government | none | NO_DONOR_LINEAGE_IDENTIFIED | none | NOT_STARTED (scope-protected) |

---

## 7. WS05 architecture disposition pass (2026-09-07; evidence in 06)

Adds the WS05 target-fit dispositions to the authoritative matrix. Status
vocabulary unchanged; disposition vocabulary: KEEP / KEEP_AND_HARDEN /
SIMPLIFY / CONSOLIDATE / SPLIT / MIGRATE / REPLACE / REWRITE_BOUNDED /
DELETE / DEFER (06 §63 applies).

| Capability | WS05 disposition | Target-fit score | Key note |
|---|---|---|---|
| Platform foundation | KEEP_AS_IS | READY | verified identity/mode/gates/offline |
| Instrument identity (multi-asset) | KEEP_AND_HARDEN | PARTIAL | XA-01 extend CRYPTO/bond/commodity; consolidate paper ASSET_CLASSES (ARCH-004, MA-001/002/004) |
| Market data layer | KEEP_AND_HARDEN | MOSTLY_READY (offline) / PARTIAL (live) | + depth staleness + session anchors (ARCH-009, TRD-008) |
| CVD / Level 1 / Level 2 | KEEP_AND_HARDEN (formulas) + REPLACE_BOUNDED (live book) | PARTIAL | formulas CORRECT_WITH_LIMITATIONS; IB L1/L2 adapter MISSING (ARCH-001); book snapshot-only (ARCH-003) |
| Options | KEEP_AND_HARDEN | PARTIAL | contracts/analytics strong; chain provider + ledger merge needed (MA-003) |
| Futures | KEEP_AND_HARDEN | PARTIAL | contract/roll/continuous correct; runtime + execution absent (MA-005) |
| Bonds / Fixed Income | DEFER (domain) / groundwork KEEP | PARTIAL | XA-02 FRED vertical correct; identity extension needed (MA-002) |
| Crypto | DEFER (domain) | UNKNOWN | identity blocker MA-001; no providers |
| Gold / Silver / Commodities | DEFER (domain) | UNKNOWN | futures model can carry; identity extension needed (MA-004) |
| Whale / Large-Participant | KEEP_AS_IS (+ ownership docs) | MOSTLY_READY | coherent envelope chain (ARCH-010) |
| Industry Intelligence | DEFER (domain) | UNKNOWN | rides instrument metadata + evidence lanes |
| Government / Public-Sector | KEEP_AS_IS | MOSTLY_READY | FRED vintages + CFTC PIT correct |
| Research / Analytics | KEEP_AS_IS | MOSTLY_READY | evidence/signal/opportunity separation correct |
| Portfolio / Accounts | MIGRATE (ledger) | BLOCKING (multi-asset) | ARCH-002 / MA-006 / ADR-C-001 |
| Multi-account | KEEP_AS_IS | MOSTLY_READY | identity-scoped caches verified |
| Demo / Paper / Live | KEEP_AS_IS | MOSTLY_READY | backend CORRECT; frontend lane keys P3 (SAFE-002) |
| Trading lifecycle | KEEP_AND_HARDEN | PARTIAL | preview binding (TRD-001), replace, remainders, BP (TRD-006) |
| Risk enforcement | KEEP_AND_HARDEN | PARTIAL | BP DISPLAY_ONLY; instrument-kind absent (SAFE-003) |
| Frontend / UX | KEEP_AND_HARDEN | PARTIAL | draft-carry/re-preview good; keys + zod schemas (ARCH-005/007) |
| API reality | KEEP_AND_HARDEN | PARTIAL | typed error taxonomy + contract direction (ARCH-007) |

## Product-surface fields (WS06 addition, 2026-09-07)

Added per controller §93 without re-scoring WS04 completion. `User Surface`
uses FULL / PARTIAL / READ_ONLY / FIXTURE_ONLY / PLACEHOLDER / MISSING;
`API Surface` = route-family status; `UX Status` = WS06 verdict; full detail
and findings in 07-product-engineering.md (§3, §14, §15).

| Capability | User Surface | API Surface | Test Coverage | UX Status | Developer/Operational Readiness |
|---|---|---|---|---|---|
| Dashboard (Now) | FULL (compact + exceptions) | `/context`, `/attention`, `/paper/portfolio`, `/provider/health` | ui1/ui2 + per-mode page tests | APPROVED direction preserved | high |
| Portfolio | FULL (equity, Paper) | `/paper/portfolio`, `/paper/order-history`, `/paper/trace`, `/paper/strategy-profitability` | paper-portfolio tests | full tables on dedicated page (correct separation) | high |
| Trading Workspace | PARTIAL (Paper full; Demo/Live read-only) | `/workspace/:symbol/*` × 11 + `/paper/orders*` | workspace + paper tests | draft-carry typed & fingerprint-gated; server binding = TRD-001 | high (backend); P2 binding |
| Orders | PARTIAL | `/paper/orders`, `/paper/orders/cancel`, `/paper/order-history` | paper order-history/trace tests | no replace; remainder one-shot (TRD-003..005) | medium |
| Research | READ_ONLY | `/research/*`, `/assistant/*` | research/mra tests | coherent evidence→signal→opportunity separation | high |
| Analytics | READ_ONLY | `/research/analytics` | research analytics tests | panels only; cross-asset missing (scope) | medium |
| Short Squeeze | PARTIAL | `/explore/squeeze*`, `/workspace/:symbol/squeeze` | short_intelligence 37 + donor_bridge 87 | works read-only; bridge :8787 not running | medium |
| CVD / L1 / L2 | PARTIAL (FIXTURE-based) | `/workspace/:symbol/order-flow`, `order-book` | order_flow 66 + formulas 30 | live path gated; IBKR L1/L2 missing (AB-002) | medium |
| Options | PARTIAL (FIXTURE-based) | `/workspace/:symbol/options` | options 147 + cboe_options 46 | read-only analytics; no live chain | medium |
| Futures | PARTIAL (FIXTURE-based) | `/workspace/:symbol/futures`, `/explore/futures` | futures 65 + contracts 38 | read-only; no live runtime | medium |
| Bonds / Fixed Income | MISSING | none (backend XA-02/FRED only) | xa02 21 + fred 30 | no workflow | backend-only readiness |
| Crypto | MISSING | none | none | no workflow | none |
| Gold | MISSING | none | none | no workflow | none |
| Silver | MISSING | none | none | no workflow | none |
| Commodities | MISSING (UI) / PARTIAL (backend) | none (EIA/CFTC/energy context) | eia 23 + cftc 20 | no workflow | backend groundwork |
| Whale / Large-Participant | PARTIAL | `/workspace/:symbol/{institutional-flow,fund-etf,large-transactions,disclosure}` | participant 76 + sec_edgar 21 | read-only lanes; no whale cockpit; fusion UI minimal | medium |
| Industry Intelligence | MISSING | none | none | no workflow | none |
| Government / Public-Sector | PARTIAL (backend) / MISSING (workflow) | provider health/operator readiness only | fred/cftc/eia/weather/sec suites | no user workflow for FRED/COT/EIA/NOAA/SEC | backend-ready, surface absent |

No WS04 completion scores changed (WS06 evidence did not contradict WS04 on
any capability).