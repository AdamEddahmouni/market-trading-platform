# 06 — Architecture, Trading Correctness, and Safety Audit (WS05)

Status: **COMPLETE (WS05, 2026-09-07)**. Canonical WS05 output.

Scope (controller §WS05): canonical domain model; Demo/Paper/Live context
end-to-end; multi-account isolation through every cache/query/API/service/
provider; Interactive Brokers target architecture; CVD/Level 2 semantics and
mathematical correctness; Level 2 state machine; Options/Futures/Bonds/Crypto/
Gold/Silver/Commodities target fit; trading lifecycle; preview-to-submission
integrity; idempotency; partial fill / cancel / replace; provider
reconciliation; risk; intelligence/research boundaries; cache/query-key/
frontend-state; API/error contracts; reliability/recovery/concurrency;
observability/secrets; KEEP_AS_IS; architecture blockers; Target Architecture
vNext (full detail in [11-target-architecture.md](11-target-architecture.md));
ADR candidates.

Evidence discipline: every material finding cites exact source paths; findings
use the schemas in §85–§88 of the controller (ARCH-/SAFE-/TRD-/MA-). No code
was rewritten during WS05. The only intentionally untouched files remain the
pre-existing dirty `cross_lane/fusion.py` + `opportunity.py` (WS01 baseline
exclusion; assessed read-only in §48 below).

Method: source inspection of `projects/integrated-market-platform/` at parent
`d691050` (canonical snapshot; child `main` @ `072e62e`), reusing the WS04
fresh validation baseline (3580 tests / 48 skipped / 1 excluded environmental
failure / 0 errors). All commands actually run are recorded in
[15-validation-evidence.md](15-validation-evidence.md). No new test suites were
needed to reach the conclusions below; WS04's fresh baseline already exercised
the runtime paths assessed here.

---

## 1. Executive architecture verdict

**IMP's current architecture CAN support the authorized product, but not
before two P1 architectural corrections, and only on the strength of the
identity/futures/options/evidence domain models plus the mode/account/paper
safety fabric.** The platform foundation, market-data envelope/admission/
timestamp layer, operational identity + account-scoped cache model, the
event-sourced internal Paper ledger with RT-01 tracing and SQLite restart
recovery, the Q-series-hardened formula libraries, the futures contract/roll
model, the option contract model, and the cross-lane evidence contract chain
are architecturally sound and verified. Those are KEEP_AS_IS.

The architecture is **not** multi-asset at the portfolio/risk/order boundary:
the authoritative ledger is single-instrument and share-denominated
(`portfolio/ledger.py`, `paper/ledger.py`), the options ledger is separate and
float-based, and there is no futures/bonds/crypto/commodity position,
notional, margin, or exposure semantics anywhere. The instrument identity
kernel (XA-01) is multi-asset-shaped but incomplete (no CRYPTO class; bond
descriptors are flat strings; gold/silver only generic COMMODITY) and there
are **two** asset-class vocabularies (`paper.contracts.ASSET_CLASSES` vs
`xa01.enums.XaAssetClass`). The provider-contract architecture is correct but
the professor-required IBKR L1/L2 runtime data path for CVD/Level-2 is absent
and the Level-2 book model is **snapshot-replacement only** — it cannot
correctly ingest real incremental IBKR depth streams.

No P0 architecture/safety defect was found: no reachable unintended Live
execution, no cross-account/cross-mode execution path, no data corruption
path, no silent provider/local divergence in any verified path, no stale
preview that can bypass risk (risk is re-run at submission). The highest
safety-relevant weaknesses are: (1) the **preview→submission binding is
frontend-only** (the server accepts a submit without any preview proof, and
the replay cursor can move between preview and submit), (2) **buying power is
DISPLAY_ONLY** (no cash check in `risk/decision.py`), and (3) the **live
order-book state has no staleness control** and is presented as
`book_state_valid: True` unconditionally.

---

## 2. Architecture target-fit scorecard

| Area | Score | Basis |
|---|---|---|
| Instrument identity | **PARTIAL** | XA-01 kernel multi-asset-shaped (asset-class/kind/denomination/relationship) but no CRYPTO class, no typed bond maturity/coupon fields, gold/silver only COMMODITY; second asset-class vocabulary in `paper/contracts.py` |
| Accounts | **MOSTLY_READY** | OperationalIdentity + registry + snapshot cache isolation verified; broker-backed account discovery absent (live blocked by design) |
| Modes | **MOSTLY_READY** | Backend mode authority + env gates + offline denial verified (mandatory invariants); frontend workspace query keys not mode-scoped (P3) |
| Providers | **PARTIAL** | Capability Protocol contracts + composition + fail-closed stubs are right; IBKR L1/L2 CVD adapter MISSING (P1); all live wires unverified; crypto/bond providers absent |
| Market data | **MOSTLY_READY** (offline) / **PARTIAL** (live) | Envelope/admission/timestamp/freshness architecture excellent; live wires gated; L2 book = snapshot-only, no staleness on depth (P2) |
| Portfolio | **BLOCKING** | Authoritative ledger single-instrument share-only; options ledger separate float; no multiplier/margin/notional; blocks 6 authorized domains' portfolio semantics (P1-2) |
| Trading | **PARTIAL** | Internal Paper verified (idempotent, traced, restart-recoverable); lifecycle gaps: preview binding, replace absent, partial-fill = one-shot fill only; broker wire fixture-only |
| Risk | **PARTIAL** | Equity core limits ENFORCED (kill switch, max order/position/open orders); buying power DISPLAY_ONLY; no multi-asset/notional/margin |
| Research | **MOSTLY_READY** | Evidence→signal→opportunity→decision separation good; provenance classes + DAG validation; fusion formula explicit |
| Intelligence | **MOSTLY_READY** | Participant evidence envelopes + cross-lane signals coherent; government macro layer (FRED vintage, CFTC PIT, EIA, weather) good; Industry MISSING (product gap, not architecture) |
| Frontend state | **PARTIAL** | Draft-carry/re-preview invariant implemented well in `OrderTicket.tsx`; query keys symbol-scoped not mode-scoped; 2000-line zod schema duplication |
| API contracts | **PARTIAL** | Dict envelopes, no generated shared contracts, no versioning, frontend-specific schemas; error contract is string-reason-code based |
| Testing | **MOSTLY_READY** | 3580 tests incl. mode/account isolation + lifecycle + golden formulas; gaps: no provider-contract suite for IBKR L2, no concurrency stress, no preview-binding test |
| Multi-asset readiness | **PARTIAL** | Identity kernel + futures/options contracts strong; portfolio/risk/execution not ready (P1-2); crypto/bond/commodity identity gaps (MA-*) |

---

## 3. Canonical Domain Ownership Matrix

Canonical owner = the module that is authoritative for the concept. "Duplicate
definitions" notes where the same concept has more than one definition.

| Domain entity | Canonical owner | Duplicate definitions / equivalents | Frontend equivalent | API equivalent | Persistence | Tests |
|---|---|---|---|---|---|---|
| User / principal | `platform/security/*`, `request_auth.py` (session principal) | none (single-user local; auth optional per TD-005) | `auth/session.ts`, `AuthProvider.tsx` | `/auth/session` | none (in-memory session) | platform suite |
| OperationalIdentity | `operational_identity.py` | none — one model; cache keys derive from it | `mode-session/types.ts` (Mode only, not full identity) | envelopes carry `operational_identity` | SQLite session record | platform 474 |
| Mode (DEMO/PAPER/LIVE) | `operating_modes.py` + `MODE_AUTHORITY.md` | `legacy_mode_label` (UI-001 compat label) — intentional | `mode-session/modeMetadata.ts` | `as_of_context` in `/context` | session record data_mode | mandatory invariants 21 |
| Account | `ui_api/account_registry.py` (descriptors) + `operational_identity.py` | none | `/accounts` view | `/accounts`, `/paper/portfolio` view_mode | ledger session | ui1 13 |
| Provider | `providers/contracts.py` (Protocols) + `providers/composition.py` | `operating_modes.PROVIDER_IDS` (data-provider enum) — two lists | `liveCanary.ts` etc. | `/provider/health` | config only | provider suites |
| Instrument identity | `xa01/contracts.py` + `xa01/registry.py` | **`paper/contracts.ASSET_CLASSES` (2nd vocabulary); `InstrumentKind` vs `paper.build_instrument_ref.asset_class`** | schemas.ts instrument fields | `/instruments/...` | xa04 catalog store | xa01 12, xa04 30 |
| AssetClass | `xa01/enums.XaAssetClass` | **paper ASSET_CLASSES tuple (CRYPTO present here, absent in XaAssetClass)** | — | — | — | — |
| Venue | `xa01/contracts.ExternalIdentifier.venue_id` + `providers/contracts.SymbolMapping.venue_id` | none | — | — | — | — |
| Currency | `xa01/contracts.DenominationMetadata.currency` (default USD) | hard-coded USD defaults in `paper/contracts.py:63`, `risk/policy.py:22` | — | — | ledger policy | — |
| Quote (L1) | `market_data/observational_state.QuoteSnapshot` + `order_flow/l1.py` | `providers/envelope.py` L1 fields | live panel | `/market-state` | capture journal | market_data 44 |
| Trade | `market_data/normalization.classified_trade_from_ticker` + `order_flow/contracts.ClassifiedTrade` | `observational_state` trades deque vs whale ledger trade rows | order-flow lane | `/workspace/.../order-flow` | capture | order_flow 66 |
| Bar | `execution/simulator` (BAR_OHLCV_1M) + replay store | none | charts | `/paper/orders/preview` input | replay events | phase7 |
| OrderBook / depth | `market_data/observational_state.books` (SNAPSHOT) + `order_flow/lob_*` + `ofi.py` | fixture book (`fixture_order_book.py`) separate adapter output | order-book lane | `/workspace/.../order-book` | capture | of16 suites |
| Portfolio | `portfolio/ledger.py` (equity) + `portfolio/options_ledger.py` (options) | **two ledgers, different numeric bases (int minor vs float)**; `paper/ledger.py` per-session | `usePaperPortfolioQuery` | `/paper/portfolio` | SQLite events + snapshot | platform 474 |
| Position | derived from ledger fills (`paper/ledger.project_positions`) | options ledger position key separate | PaperPortfolioPage | `/paper/positions` | derived | platform |
| Balance / cash | `portfolio/ledger.build_ledger_state` (cash_minor int) | options ledger float cash | portfolio page | `/paper/account` | derived | platform |
| Order | `paper/contracts.py` (intent + lifecycle) + `paper/ledger.py` | `broker_paper` separate path; `execution/simulator` order dict | OrderTicket | `/paper/orders` | SQLite events | phase7, platform |
| Fill | `execution/simulator` + `paper/ledger.append_fill` | options `simulate_multi_leg_entry` separate fill shape | fills panel | `/paper/fills` | SQLite events | phase7 |
| RiskDecision | `risk/decision.py` + `risk/kill_switch.py` + `risk/policy.py` | options execution has own risk plumbing (`options/execution`) | ticket preview state | `/paper/risk` | RiskDecisionRecorded events | phase7, intelligence 1165 |
| Transaction | ledger events (OrderIntentCreated…PositionChanged) | none | order history | `/paper/order-history` | SQLite | platform |
| ResearchObservation / Evidence | `cross_lane/evidence.py` (NormalizedLaneEvidence) | `intelligence/contracts/evidence.py` (EvidenceV1), `participant/evidence.py` (family dataclasses), `provider/whale_ledger.py` — 3-4 layers, coherent chain | Evidence lane UI | `/workspace/.../evidence` | ledger/store | participant 76 |
| Signal | `cross_lane/evidence.py` EvidenceSignal enum | `order_flow/contracts` forecast signals; `intelligence/contracts/signal.py` | lane panels | workspace payloads | store | cross_lane 39 |
| Opportunity | `cross_lane/opportunity.py` (FusedOpportunity) | `intelligence/contracts/opportunity.py` | cockpit | `/workspace/.../order-flow` etc. | store | cross_lane golden |
| Alert | `strategy/*`, `of03` registry | none | attention feed | `/attention` | store | strategy suites |
| Timestamp / freshness | `market_data/timestamps.py` (event/provider/available/received/ingested) + `live_admission.py` | FRED vintage fields (release-time semantics) | `formatPaperSourceTimeLabel` | lane provenance `retrieved_at_ns` | capture | market_data |

Key duplicate-definition findings: **two asset-class vocabularies**
(ARCH-004), **two ledgers with different numeric bases** (MA-003),
**layered-but-coherent evidence vocabularies** (ARCH-010, consolidation
opportunity only).

---

## 4. Multi-asset instrument model (§8) — assessment

Classification: **MULTI_ASSET_PARTIAL**.

What is already correct:
- XA-01 kernel has asset-class, instrument-kind, denomination (currency,
  price-unit kind, contract multiplier, tick size), external identifier types
  (TICKER/CUSIP/ISIN/PROVIDER_SYMBOL), and typed relationships
  (UNDERLYING/CONTRACT_ROOT/DENOMINATED_IN/BENCHMARK_OF)
  (`xa01/enums.py`, `xa01/contracts.py`).
- `contracts/futures.py` models family vs tradable contract, Decimal spec
  (multiplier/tick/tick_value/point_value), expiry/first-notice/last-trade/
  delivery, settlement type, margins, lead/roll state, event/available times —
  the strongest domain contract in the codebase.
- `contracts/options.py` models underlying_id, option_id, call/put, Decimal
  strike, expiry, DTE, exercise/settlement style, multiplier, deliverable spec,
  bid/ask/OI with event/available times.

What is missing / wrong for the authorized set:
- **No CRYPTO asset class** in `XaAssetClass`/`InstrumentKind`; no venue/chain
  identity for crypto; no spot-vs-derivative pair identity (MA-001).
- **Bonds**: `SOVEREIGN_DEBT` exists but descriptor fields (maturity_date,
  coupon, issue_date, sovereign_issuer) are flat optional strings; no CUSIP
  typing beyond alias, no yield/price-unit semantics beyond
  `PriceUnitKind.YIELD_RATE`; no corporate bond identity at all (MA-002).
- **Gold/Silver**: only generic `COMMODITY` + commodity_code; no spot vs
  futures vs ETF proxy resolution; contract spec for GC/SI comes only via the
  futures model (MA-004).
- **Two vocabularies**: `paper/contracts.ASSET_CLASSES` includes CRYPTO and
  PREDICTION_MARKET but XA-01 does not; `build_instrument_ref` defaults to
  `EQUITY`/`US_EQUITY`/multiplier `1` — every paper/execution path constructs
  instruments through the equity-defaulting helper (ARCH-004).
- Options contract identity is properly typed in `contracts/options.py`; the
  workspace/paper layer keys on the underlying symbol string (the paper
  instrument ref has no option contract fields beyond optional
  strike/expiration/option_right strings) — options execution remains
  fixture-scoped, so this is latent, not yet wrong (MA-005 note).

Verdict: the identity *kernel* can support all classes with extension
(CRYPTO class, bond descriptor typing, commodity contract identity, one
canonical asset-class vocabulary); the *runtime* instrument ref used by
portfolio/trading/risk cannot. The equity-centric default in
`build_instrument_ref` + share-denominated ledger is the blocker (P1-2).

## 5. Symbol vs instrument audit (§9)

Current state — symbols and instrument identity are **not systematically
conflated in the identity layer**, but **are conflated at the runtime/UI
boundary**:

- XA-01 distinguishes alias (PROVIDER_SYMBOL/EXCHANGE_SYMBOL/TICKER/DISPLAY_
  TICKER) from canonical_id, and futures distinguish family/underlying/
  contract_id. Options distinguish underlying_id from option_id. Good.
- The **paper/execution boundary uses bare `symbol`/`instrument_id` strings**:
  `build_instrument_ref(instrument_id=..., symbol=...)` carries no contract
  disambiguation for futures (`ES` vs `ESU6`) or options; `OrderTicket` and
  the API accept an arbitrary symbol; `_require_order_instrument` resolves the
  "active operator instrument" by string. Nothing validates that a submitted
  `instrument_id` is a TRADABLE contract vs a family/continuous/root symbol
  (MA-005, SAFE-003).
- The workspace lanes are symbol-keyed in the URL (`/workspace/:symbol`) —
  acceptable for equities; futures/options need a contract-resolved route or
  an instrument_id-based route.

Target identity semantics (design only, not implemented — see 11):
`symbol` (display alias) ≠ `ticker` (exchange symbol) ≠ `instrument_id`
(canonical) ≠ `contract_id` (tradable instance) ≠ `underlying_id` ≠
`asset` (base asset) ≠ `venue-specific identifier`. Submission instruments
must always resolve to a tradable contract identity with denomination
(multiplier/tick/currency).

## 6. Account / operational identity (§10)

**CORRECT, KEEP_AS_IS.** `OperationalIdentity(mode, broker, account_id,
portfolio_id, environment)` is a frozen, validated dataclass; every cache key
derives from it (`cache_key()` over canonical bytes, sha256); demo views are
explicitly prefixed (`demo:`), never used for mutations; paper identity is
derived (`derive_paper_identity`), broker label separated from data mode;
canary LIVE identity carries environment="canary". Trace:
frontend (`/paper/portfolio` view_mode) → `resolve_paper_portfolio_identity`
→ identity → `AccountSnapshotCache` keys → ledger session. No implicit/default
identity was found: `resolve_operational_account` raises on ambiguity when no
account_id is given, and `parse_operational_identity` fails closed on missing
mode/broker/account. One design note: the process holds one active
`PaperExecutionLedger` (single active account per runtime) — consistent with a
single-user local tool; concurrent multi-account state is not modeled (not a
defect; document for multi-account futures).

## 7. Demo / Paper / Live architecture (§11)

**CORRECT (backend); MOSTLY_READY (frontend).** Semantics (from
`MODE_AUTHORITY.md` + code):
- DEMO = `data_mode∈{FIXTURE_REPLAY,HISTORICAL_CAPTURE}`, `execution_mode=NONE`,
  `execution_authority=BLOCKED`, read-only.
- PAPER = `execution_mode=INTERNAL_SIMULATION` AND `execution_authority∈
  {AUTHORIZED,PAPER_ONLY}` behind `IMP_PAPER_EXECUTION`; BROKER_PAPER behind
  its own gate (`IMP_BROKER_PAPER_EXECUTION`, `PAPER_ONLY` authority).
- LIVE = `data_mode∈{LIVE_OBSERVATIONAL,BROKER_DELAYED}`, `execution_mode=NONE`,
  `execution_authority=BLOCKED`; LIVE-001 blocked; `open_paper_session`
  rejects `requested_mode == "LIVE"`.

Mode selection is process-startup-level (data_mode resolved from env/startup),
so a runtime crossover requires restart — a strong isolation property.
`resolve_execution_authority` gates each execution mode by its own env flag;
restart restore derives authority from the stored execution mode
(`local_state/startup.ledger_from_session`), so a stale `IMP_PAPER_EXECUTION`
cannot resurrect a BROKER_PAPER session. Cross-mode cache keys include mode
(`operational_identity.cache_key_parts`). The live gate chain
(`_assert_live_execution_allowed` → internal simulation gates →
provider connection state → probe staleness) runs on submit and on restored
sessions. WS04 mandatory invariants (21) plus paper governance/qualification
suites pass on the fresh baseline.

Residual (P3): frontend workspace lane query keys are **not mode-scoped**
(`["workspace", symbol, "order-flow"]`); mode switch unmounts the shell so
queries refetch (staleTime 0), but the key structure is a latent stale-state
risk if refetch semantics change (SAFE-002). No Demo/Paper→Live execution
crossover is plausible at the backend: Live authority is process-level and
blocked; the mode enum is validated at identity construction.

## 8. Multi-account architecture (§12)

**CORRECT for the implemented scope.** `AccountSnapshotCache` keys on
`identity.cache_key(logical_id)` (mode+broker+account+environment+portfolio),
refresh locks are per-entry-key (coalescing, no cross-account contention),
`CachedSnapshot` carries identity + source_time + stale/refresh flags.
`/canary/*` projections are account-scoped; `list_operational_accounts` and
`resolve_operational_account` fail closed on ambiguity. No global singleton
account, no default-account fallback, no shared refresh lock across accounts,
no missing account id in query keys was found. Broker-backed account discovery
is absent (live blocked) — the target IB adapter must add real account
discovery + entitlement-gated subscription isolation (§14).

## 9. Provider architecture (§13)

**MOSTLY_CORRECT, needs the capability-role separation finished.** Current:
- Role separation is capability-based (`providers/contracts.py` Protocols:
  Disclosure, ReferenceData, EquityQuote, OptionChain, FuturesChain/Positioning/
  Bars/Macro/Margin, DistributionForecast, OrderFlow, PaperExecution) —
  MARKET_DATA vs BROKER_EXECUTION vs fundamentals/macro are separated by
  capability, not by one undifferentiated "provider".
- Composition registry (`providers/composition.py`) with fail-closed stubs
  (Unconfigured*Provider), mutual exclusion for broker-paper adapters
  (P4-SAFE-001), `EXECUTION_ENABLE` gating of the paper-execution slot.
- `providers/registry.py` CapabilityDescriptor/ProviderDescriptor registry and
  `planner.py` QueryPlanner (license-class policy, cache keys) exist as a
  provider-selection layer.
- Adapters: fixture adapters for every research lane, recorded-response Tradier
  sandbox (fail-closed `BROKER_TRANSPORT_NOT_IMPLEMENTED` without a fixture
  record), Moomoo live observational, live-gated FRED/CFTC/EIA/NOAA/SEC/CBOE.

Gaps for the target: provider **roles** (MARKET_DATA vs BROKER_EXECUTION vs
ACCOUNT_DATA vs PORTFOLIO_DATA vs NEWS vs FUNDAMENTALS vs MACRO vs REGULATORY
vs ALTERNATIVE_DATA vs AI) are implied by capability but not modeled as a
first-class role registry; there is no capability **discovery** at runtime
from providers (fixed composition instead); IBKR, crypto, and bond providers
absent. Target: keep the Protocol-per-capability shape; add a Provider
Capability Registry (provider → roles → capabilities → gates → freshness
policy) as the single source the UI/planner consult (§75 of controller).

## 10. Interactive Brokers target architecture (§14) — see also ARCH-001

Decision-relevant findings (implementation deferred to WS07+):
1. **One IB adapter exposing multiple capabilities, with two sessions.**
   A single `IBKR` provider adapter per capability role (MARKET_DATA via
   Client Portal REST + TWS; ACCOUNT/PORTFOLIO via Client Portal REST;
   EXECUTION via a *separate* authorized session) — not one monolithic client.
   Market-data subscriptions and execution sessions must be separable objects
   (different credentials, entitlements, lifecycle).
2. **Market-data vs execution separation: YES** — `tools/ibkr/client.py`
   (read-only REST allowlist + pacing + penalty box + capture) is the correct
   seed for the market-data/account adapter; execution must be a distinct
   capability gated by LIVE-001 (absent today, by design).
3. **IB account identity ≠ operational identity**: map IB account → `OperationalIdentity.account_id` at the adapter boundary; never let IB account ids leak into cache keys directly (use canonical identity).
4. **Subscription/entitlement failures**: use the existing admission vocabulary — `ENTITLEMENT_MISSING` (already in `live_admission.py`) surfaced per capability with a visible reason (the CVD lane already distinguishes `ENTITLEMENT_MISSING` in `build_live_order_flow_payload`).
5. **L1/L2 subscription management**: capability registry + subscription manager keyed by instrument+capability (the current `market_data/subscription_manager.py` shape); L2 depth requires the incremental book engine of §12.
6. **Reconnects**: `LiveAdmissionEngine.on_reconnect/on_disconnect` resets sequence state; the depth engine must add book-reset semantics (see ARCH-003).
7. **Pacing/rate-limit isolation**: keep `tools/ibkr/pacing.py` (per-path slot + penalty box) as the adapter's transport guard; never route non-IB pacing through it.
8. **Depth lifecycle**: full-book snapshot on subscribe → incremental insert/update/delete → periodic resync; stale-book eviction (see ARCH-003).
9. **Paper vs Live IB accounts**: IMP PAPER → IB paper account under `PAPER_ONLY` authority; IMP LIVE (observational) → read-only Client Portal REST under the existing live gate; LIVE execution remains LIVE-001-blocked.

The existing `tools/ibkr` observational client is the **seed** for the
required adapter (D19 → recommend SEED, with L2 depth + account/portfolio
capabilities added; the L1 snapshot/history/secdef REST surface and TWS L1 via
`tws_client.py` remain; `reqMktDepth` integration is new work).

## 11. Tradovate / Claude Code News target fit (§15)

`Claude Code News` (SRC-006, NOT_YET_INTEGRATED, zero IMP matches) decomposes:
- **Product-relevant behavior (candidate for canonical Futures workflow,
  reimplemented, not copied):** news-buffer-driven daily direction brief;
  one-trade-per-day discipline; fixed stop/target with a trailing ladder;
  honest-limits documentation; shadow-log/shadow-report audit habit;
  preflight config verification; SIGUSR-based operational control.
- **Donor-specific / inappropriate for canonical IMP execution:** CDP-driving
  the TradingView desktop DOM and the Tradovate order ticket through a browser
  (`src/live/broker_ui.js`); iMessage text notification path; macOS launchd
  deployment. These are donor operating choices, not requirements — IMP's
  canonical execution must go through provider adapters (IBKR and/or a
  Tradovate adapter) with the existing preview/risk/idempotency/RT-01 path,
  never through browser automation (WS96 operating rule).
- **Tradovate role:** a possible BROKER_EXECUTION adapter provider for
  Futures — decision stays OPEN (D3/D16) between IBKR and Tradovate for the
  primary Futures execution provider; both can be adapters behind one
  capability contract. Do not import the CCN codebase.
- The **bracket/trailing behavior** is product-relevant (brackets = OCO/
  stop+target, trailing ladder) and should be designed into the target order
  model (currently absent: no OCO/stop/TIF in `paper/contracts.py`), driven
  from strategy intent, not from donor code.

## 12. Provider capability interface (§16)

The target shape (discover_accounts, get_account_snapshot, get_positions,
get_orders, get_quotes, get_bars, subscribe_trades, subscribe_depth,
preview_order, submit_order, cancel_order, replace_order) is **already
approximated** by the Protocol set + `broker_execution.py` (BrokerOrderStatusEvent,
BrokerAccountSnapshot, BrokerPositionSnapshot) + reconciliation engine +
`paper/broker_paper.py` adapter orchestration (submit/poll/cancel/reconcile).
Gaps: no `discover_accounts` (live blocked), no `replace_order` anywhere, no
`subscribe_depth` in the Protocol layer (Moomoo MBP via live runtime instead),
no capability **discovery** from adapters (fixed composition). Target: keep
Protocols; add explicit capability discovery (`capabilities()` per adapter)
and fail-closed `UNSUPPORTED_CAPABILITY` for providers that cannot implement a
role (e.g., a quote-only provider must not fake bars).

## 13. Market-data architecture (§17)

**CORRECT in shape; live wires unverified.** Trace is as specified:
provider → raw payload → admission (`live_admission.py` blocking flags) →
envelope (`providers/envelope.py`, `live_envelope_from_capture`) →
normalization (`market_data/normalization.py`: l1/levels/classified trades) →
observational state (per-instrument quotes/trades/books + metrics) → domain
consumers (CVD path, order-book lane, LOB features) → API → UI. Duplicated
normalization: minor — `observational_state.apply_admitted` re-implements
small field fallbacks (`_optional_float`) on top of `normalization`
functions; acceptable. Provider leakage: none found (Moomoo-specific parsing
is confined to `provider_time.py` + normalization helpers; quality checks
reuse canonical OF flags).

## 14. Market-data time semantics (§18)

`TimestampSet` defines event/provider/available/received/ingested as epoch-ns;
`provider_time.py` parses Moomoo naive ET session strings (documented
assumption: America/New_York wall time; lag = event-to-local-receipt, not
exchange latency); `event_time_ns_from_payload` deliberately never uses
received time as a fake event time; cached pushes and first-push snapshots are
flagged (`INITIAL_CACHED_EVENT`, `SNAPSHOT_UPDATE_MISMATCH`) and block
execution admission. `source_time`/`display_time` as named concepts do not
exist (UI formats provider/available times directly) — acceptable, but the
target should standardize the label set. No timezone ambiguity was found (all
internal times epoch-ns; the only naive datetime path is the documented
provider parser). **Gap:** FRED vintage (event vs release vs revision) is
handled in the fred layer (`vintage_date`, `revision_number`,
`revision_delta`, ALFRED knowledge intervals) — good.

## 15. Freshness architecture (§19)

**CORRECT with two gaps.** Per-observation freshness: admission evaluates
clock drift, L1/SNAPSHOT staleness (quote_stale_threshold_ms /
execution_freshness_threshold_ms), disconnected/entitlement states; execution
admission is fail-closed on STALE/CLOCK_DRIFT/PROVIDER_DISCONNECTED/
ENTITLEMENT_MISSING/INITIAL_CACHED_EVENT/SNAPSHOT_UPDATE_MISMATCH.
`AccountSnapshotCache` records source_time/retrieved_at/stale/refresh_failed
per entry. Gaps:
- **DEPTH/ORDER_BOOK events never receive STALE checks** (staleness block is
  `"L1" in capability or "SNAPSHOT" in capability`) — a stale book can sit in
  `observational_state.books` indefinitely (ARCH-009).
- CVD cumulative-delta has **no session anchor/reset**: the series restarts at
  server restart or deque rollover; there is no session boundary marker for
  session-level CVD (`order_flow/cvd.py` `compute_cvd_state` has no reset
  semantics) (TRD-008, P3).

## 16. CVD / Level 2 architecture (§20)

Current: formula library (`donor_patterns/cvd_formulas.py`: Lee-Ready, BVC,
cumulative delta, OFI) + `order_flow/*` (aggressor, cvd, ofi, l1, lob_*,
liquidity, metaorder, execution_forecast) over admitted fixtures; Moomoo live
observational path (`build_live_order_flow_payload`) computes CVD from live
trades when the live gate is open (gated/unverified on the real wire);
**IBKR L1/L2 runtime integration MISSING (P1-1)**. Target live chain (design
in §16/§74): IBKR trade stream + IBKR L1 + IBKR L2 → normalized
order-flow observations (classified trades + depth deltas) → canonical depth
state (incremental book) → CVD/OFI calculations → signal/research layer → UI.
Formula-vs-fixture semantics: `compute_cvd_state` consumes pre-aggregated bar
`delta` (fixture semantics); the live path converts per-trade to bar rows with
`aggressor_provenance` — formulas do not assume fixture internals, but the
live classification confidence depends on provider-native side labels
(unverified on wire). No fixture assumption would break on real streams at the
formula layer; the **book layer** (snapshot-only) is the real-stream blocker
(ARCH-003).

## 17. CVD mathematical correctness (§21)

**CORRECT_WITH_LIMITATIONS** (formulas standard; limitations documented):
- `classify_aggressor`: price≥ask → buy, price≤bid → sell, else tick rule,
  else prev_dir carry, else 0 (indeterminate). Standard Lee-Ready + tick rule;
  midpoint variant available. At-the-quote trades (price==ask/bid) classify as
  aggressive — standard convention, assumption explicit.
- BVC: `erf`-based normal CDF split; population σ documented (not sample);
  insufficient window (≥10) or σ=0 → 50/50 split; index 0 → 0. Assumption-
  explicit, fail-safe (never fabricates direction).
- `cumulative_delta`: running sum; no reset semantics (caller responsibility —
  gap, TRD-008).
- `ofi_events`: Cont-Kukanov-Stoikov; NaN → 0 contribution (not NaN
  propagation) — safe.
- Zero handling: delta 0 → UNKNOWN side, excluded from buy/sell volume,
  counted in unknown_fraction; confidence model (native 1.0/inferred 0.55–0.75/
  unknown 0) is conservative. `cvd_confidence = native_frac + 0.5*inferred_frac`
  — reasonable, documented.
- Out-of-order/duplicates: handled at the admission layer (DUPLICATE,
  REGRESSION, SEQUENCE_GAP flags), not inside formulas — correct layering.
- **Multi-level OFI rank-based pairing** (`ofi.py compute_multilevel_ofi`):
  pairs level N in prev snapshot with level N in curr snapshot; when levels
  insert/delete between snapshots, rank identity breaks (a level that shifted
  rank is mis-paired, and an empty rank contributes the whole new size as an
  add). This is an approximation; documented as limitation (ARCH-006 note).
- Q-series hardening evidence stands; Q-series closure does not cover the live
  wire (unverified).

## 18. Level 2 state machine (§22)

**UNSUITABLE for real IBKR depth as-is (ARCH-003, P1).** Current model:
`observational_state.apply_admitted` **replaces the entire book** on every
DEPTH/ORDER_BOOK event (`update_semantics: "SNAPSHOT"`); `assess_book` checks
only crossed/locked/partial/MBO-unavailable flags; `book_sequence` continuity
is optional (`snapshot_pair_sequence_valid` returns True when neither snapshot
has a sequence); `on_reconnect` resets admission sequence state but there is
**no book reset/rebuild protocol**; there is no insert/update/delete event
semantics, no per-level identity, no partial-depth handling beyond the
DEPTH_PARTIAL flag, no stale-book eviction. `build_live_order_book_payload`
hardcodes `book_state_valid: True` and exposes only the BBO. Real IBKR
`reqMktDepth` streams are incremental (add/update/delete + periodic refresh +
book reset on reconnect) — the current structure cannot represent them safely.
Target: canonical depth event model (INSERT/UPDATE/DELETE/CLEAR per
side+price), full-book snapshots on subscribe/reconnect, monotonic per-level
sequence, book TTL + stale eviction, and snapshot-pair OFI computed only when
level identity is preserved (or switch to delta-based OFI).

## 19. Options architecture (§23)

**PARTIAL — analytics strong, execution/portfolio not.** `contracts/options.py`
+ `options/*` (147 tests: surface, Greeks, IV, risk-neutral/BL-Q, delta-hedged,
event-vol, strategy optimizer, payoff, flow, execution O9, r_o6, zerodte) are
fixture-scoped but typed correctly (Decimal strike/multiplier, option_id vs
underlying_id — no symbol-string contract identity in the analytics layer).
The `OptionChainProvider` protocol exists with no live implementation
(fixture-only). The paper/portfolio layer has an options ledger
(`portfolio/options_ledger.py`) **separate from the equity ledger** and
**float-based** (MA-003). Execution = `OptionsConservativeSimulator` on NBBO
fixture spreads; strategy confirmation uses `donor_patterns/options_lane.py`
(independent reimplementation; zero donor terminology — WS03 confirmed).
Target (design in 11): chains provider → canonical OptionContract stream →
Greeks/IV from live quotes → strategy/confirmation on current chain → orders
into the canonical order model with option instrument identity (contract_id +
underlying + multiplier) — the contract model supports this; the order/
portfolio/risk layers do not yet.

## 20. Options provider separation (§24)

**CORRECT today** — reference data (contracts/option_contract_builder),
market data (chain protocol/fixtures), analytics (options/*), execution
(conservative simulator) are separate modules with separate providers; CBOE
public stats is a distinct live-gated source; no Unusual Whales/iVolatility
dependency exists (WS03: zero matches; donor trial providers never adopted).
Target keeps this separation: chain provider (reference+market data) ≠
analytics (own) ≠ execution provider (IBKR/Tradovate decision later).

## 21. Futures architecture (§25)

**PARTIAL — research engines strong; runtime/execution absent.**
`contracts/futures.py` (family vs contract, Decimal spec, margins, roll
state), `futures/*` (roll, curve, basis, carry, continuous, notional,
positioning, leverage_stress, relative_value, advanced_*), CFTC COT live
adapter (gated), fixtures (ES/CL). The futuresX-derived helpers are correct
and incomplete exactly as WS04 stated. The architecture needed to combine
Eric-futuresX depth/contract concepts + Claude Code News news/execution
workflow concepts + canonical IMP provider architecture is: futures instrument
identity through XA-01 (already has FUTURE/FUTURE_CONTRACT/FUTURE_FAMILY),
tradable-contract execution through the target order model (contract_id,
multiplier, tick), news-driven strategy through the strategy/evidence layers
(not donor code), and IBKR/Tradovate adapters behind capability contracts —
**without merging donor codebases** (all three remain separate inputs to the
canonical design in 11).

## 22. Futures contract selection (§26)

**CORRECT.** `futures/roll.py select_lead_contract` selects
`execution_contract_id` from tradable contracts (volume+OI+DTE rule v1,
roll-window aware); `continuous.py` builds adjusted/unadjusted series as
`ContinuousSeriesPoint(price, contract_id, roll_adjustment, methodology)` —
continuous series **always carry the underlying contract_id** and are never
themselves executable in the research engine. The invariant "a continuous
symbol must never become an executable contract accidentally" is structurally
protected at the research layer. **Gap (MA-005/SAFE-003):** the paper/execution
layer accepts arbitrary `symbol` strings with no contract-kind validation —
nothing prevents a future submission with a `FUTURE_FAMILY`/continuous id as
the instrument. The target order model must validate instrument-kind
(TRADABLE_SECURITY/FUTURE_CONTRACT/OPTION_CONTRACT) before submission.

## 23. Bonds / Fixed Income architecture readiness (§27)

**Groundwork correct; domain absent; one identity blocker.** FRED/ALFRED
vertical (XA-02, `fred/*` with vintage/revision semantics, typed cross-asset
refs, `PriceUnitKind.YIELD_RATE`) is the correct macro foundation. Identity
blockers: `SOVEREIGN_DEBT` exists but there is no **corporate bond** identity
and no typed bond instrument (maturity/coupon/par/issue are flat optional
strings in `InstrumentDescriptor`); no bond pricing/curve/duration/credit
model; portfolio semantics absent (ledger is share-only). Equity-centric
assumptions that block Bonds: quantity-as-shares, price-per-share
denomination, no face/par/100-price convention, no yield↔price conversion in
the portfolio layer. Target (11): extend XA-01 with a typed Bond descriptor
(issuer, CUSIP/ISIN alias, maturity, coupon, par, currency, credit tier) and a
yield-price unit; reuse XA-02 FRED vertical for rates/curve. Not an ad-hoc
silo: bonds ride the shared instrument/portfolio primitives.

## 24. Crypto architecture readiness (§28)

**Not startable from current primitives without identity + venue work.**
`LaneId.CRYPTO` exists; `paper.contracts.ASSET_CLASSES` includes CRYPTO; but
XA-01 has **no CRYPTO asset class / instrument kind**, no venue/chain
identity, no pair model, no 24/7 session concept (`market_sessions.py` is
equity-RTH oriented), no spot-vs-derivative distinction, no custody/wallet
evidence model. Incompatible current assumptions: universal closing session
(ReplayStore/fixture replay is session-anchored), equity quote normalization
fields, share-denominated portfolio. Target (11): add CRYPTO to XaAssetClass +
InstrumentKind, a CryptoPair identity (base/quote/venue) and optionally
network/chain aliases; document continuous 24/7 semantics in the market-data
layer (freshness thresholds must not assume RTH close); portfolio via the
shared cross-asset model (quantity in base units, quote currency). Do not
build a separate crypto stack.

## 25. Gold / Silver / Commodity architecture readiness (§29)

**Prepared by the futures model; identity layer needs per-commodity contract
identity.** GC/SI keys exist in `xa03/catalog.py` and `eia/cross_asset.py`
family registries; `FuturesFamily` includes METALS/ENERGY/AGRICULTURE/
CRYPTO_FUTURES; `contracts/futures.py` can represent GC/SI futures contracts;
EIA/CFTC macro groundwork exists. Missing: spot/reference instrument identity
(spot gold vs GC future vs GLD proxy), commodity-category hierarchy beyond
family strings, and portfolio exposure semantics. Target: represent spot/
reference as `TRADABLE_SECURITY`/`COMMODITY_ECONOMIC` instruments and
futures/ETFs as related instruments (UNDERLYING/CONTRACT_ROOT/BENCHMARK_OF
relationships already exist) — shared commodity primitives, no per-commodity
ad-hoc architecture. Gold/Silver remain first-class visible domains (MND-006/
007) over those primitives.

## 26. Portfolio domain correctness (§30)

**CORRECT for equities; wrong base for multi-asset.** `portfolio/ledger.py`
uses exact integer minor units (price_scale 100 default), signed
position_shares, position_cost_basis_minor (weighted-cost preservation across
partial closes/reversals), realized P&L with commission/fee handling, and an
audited `_realized_delta`/`_cost_basis_after_fill` pair (documented reversal
semantics). Backend-authoritative: the ledger is the single source; the
frontend renders projections; attribution parity is a tested invariant (WS04).
Unrealized P&L uses a live mark when available (`apply_live_mark`) else last
fill price — documented. **Wrong base for multi-asset:** no contract
multiplier in notional/P&L, no margin, no per-instrument multi-position model
(one ledger = one instrument per session), options ledger separate + float.
Provider-authoritative reconciliation exists only in BROKER_PAPER mode
(records reports + operator corrections; `INTERNAL_AUTHORITATIVE` otherwise) —
correct: the broker becomes authoritative only when a broker path exists.

## 27. Cross-asset portfolio architecture (§31)

**BLOCKING (P1-2).** Required changes identified (design in 11):
1. Portfolio keyed by instrument identity (not session-scoped single
   instrument): positions = list of (instrument_id, signed quantity, unit of
   measure: shares/contracts/base-units).
2. Denomination-aware valuation: market value = price × quantity ×
   contract_multiplier (futures), option premium × multiplier, bond face/par,
   crypto base units × quote price; per-currency cash and P&L with explicit FX
   (USD-only today, ARCH-011).
3. Cross-asset exposure: gross/net exposure must be notional (not share
   counts); margin/leverage for futures/options as risk inputs.
4. Trading-calendar awareness: futures RTH/ETH vs crypto 24/7 vs equity
   sessions — already partially modeled (`market_sessions.py`,
   `contracts/futures.py` RTH fields); portfolio time-stamping must not assume
   one session.
5. Options ledger merges into the canonical ledger with option contract
   identity + multiplier (float → Decimal/minor-units conversion).

## 28. Order domain model (§32)

**PARTIAL — too equity-specific for the authorized set.** `build_user_order_intent`
+ `build_instrument_ref` (paper/contracts.py): side (BUY/SELL), quantity int,
order_type {MARKET, LIMIT} only, limit_price_minor, client_order_id,
idempotency_key, correlation_id, decision_source_snapshot, lineage refs,
quantity_facts (audited), research_candidate_id (CAND-<uuid> enforced). What's
missing for multi-asset: TIF (day/GTC/IOC/FOK), stop price/stop-limit,
OCO/bracket (needed for CCN bracket semantics), option/futures-specific
legs at the execution layer (options execution has its own intent), contract
multiplier/tick on the instrument ref (multiplier defaults "1"), account/mode
binding at intent construction (binding is implicit via the ledger, which is
fine — but the intent itself carries no identity; the ledger carries it).

## 29. Trading lifecycle state machine (§33)

Canonical lifecycle table (from `paper/contracts.py` VALID_ORDER_TRANSITIONS +
broker path):

| State | Meaning | Transitions to | Present in IMP? |
|---|---|---|---|
| CREATED | intent built, not submitted | RISK_ACCEPTED, RISK_REJECTED, REJECTED, ACTIVATED, SUBMITTED | YES |
| RISK_ACCEPTED | risk passed | SUBMITTED, ACTIVATED, WORKING | YES |
| RISK_REJECTED | risk blocked (terminal) | — | YES (terminal) |
| SUBMITTED | dispatched to broker | ACTIVATED, WORKING, REJECTED, CANCEL_PENDING | YES (broker path) |
| WORKING | working at broker | PARTIALLY_FILLED, FILLED, CANCEL_PENDING, REJECTED, EXPIRED | YES |
| ACTIVATED | simulator activation | PARTIALLY_FILLED, FILLED, REJECTED, CANCEL_PENDING | YES |
| PARTIALLY_FILLED | partial fill | FILLED, CANCEL_PENDING | YES |
| FILLED | complete (terminal) | — | YES |
| CANCEL_PENDING | cancel requested | CANCELLED | YES |
| CANCELLED | terminal | — | YES |
| REJECTED | terminal | — | YES |
| EXPIRED | terminal | — | YES |
| PREVIEW / VALIDATED / CONFIRMED | preview-state | — | **NO (preview is a dry-run envelope, not a lifecycle state)** |
| ACKNOWLEDGED | broker ack | — | NO (SUBMITTED covers) |
| REPLACE_PENDING / REPLACED | replace lifecycle | — | **NO (replace absent)** |

Assessment: no impossible states found; transitions are enforced by
`validate_order_transition` (with a documented special-case fallback allowing
terminal from CREATED/ACTIVATED). Missing states: explicit
PREVIEW/VALIDATED/CONFIRMED (preview is ephemeral — acceptable today, but the
preview→submission binding gap (§34) is the consequence), ACKNOWLEDGED
(optional), REPLACE_PENDING/REPLACED (replace absent — P3). Race conditions:
ledger-mutating HTTP routes serialize on `LEDGER_ROUTE_LOCK`; the ledger
lookup→record idempotency pair is atomic only under that lock (single-process
assumption; documented in `server.py`). The lifecycle itself is
**PARTIALLY_CORRECT for the internal Paper path** (verified) and
**PARTIALLY_CORRECT for broker paper** (fixture-only wire).

## 30. Preview-to-submission integrity (§34)

**PARTIALLY_CORRECT — server-side binding absent (TRD-001, P2).**
- What holds: submission re-runs risk against current ledger state
  (`execute_order_intent` → `evaluate_risk`), so a stale preview **cannot**
  bypass risk; the UI (`OrderTicket.tsx`) only enables submit when
  `preview.risk_status === "PASS"` and `confirmedRequestIsCurrent` (same
  instrument/side/quantity/order_type), re-previews automatically on draft
  arrival (WS65 invariant implemented at the UI layer), and invalidates on
  field edit; `_assert_live_execution_allowed(submit=True)` re-checks the
  live gates on submit.
- What does not hold: there is **no server-side binding** between the preview
  response and the submit request (no preview_id, no intent-hash check, no
  observation-time/cursor binding). The submit re-derives everything from the
  body; `_paper_observation_time` is evaluated at each call, so scrubbing the
  replay cursor between preview and submit changes the executed fill without
  invalidating the preview; `confirmedRequestIsCurrent` ignores
  limit_price_minor and decision-source-snapshot drift; a client can submit
  without ever previewing (risk still applies).
- Target correction: server issues `preview_id` + binds (intent_hash,
  observation_time/cursor, identity, market-state fingerprint); submit
  requires a valid, current preview (reject stale previews with
  `PREVIEW_STALE`), with the account/mode/instrument/price/risk-state
  fingerprint re-validated at submit; UI carries the preview_id.

## 31. Trading idempotency (§35)

**CORRECT_WITH_LIMITATIONS (TRD-002, P2).** Idempotency key is
client-supplied (defaults to client_order_id; UI generates one random key per
preview attempt and reuses it for the corresponding submit — retries of the
same submit return the recorded order via `lookup_idempotent_order`);
ledger-mutating routes serialize on `LEDGER_ROUTE_LOCK`; duplicate submit
returns `duplicate: true` with the original order. Limitations: (1) the
lookup→record pair is atomic only under the route lock (single-process
assumption; the pattern would race under multi-process deployment or direct
`submit_interactive_order` callers); (2) keys are not content-derived, so a
client that loses the key after a timed-out submit could retry with a new key
and create a duplicate (UI mitigates by reusing the same request object, but
the server cannot detect it); (3) no browser-retry/double-click protection at
the transport layer beyond the key. Target: content-derived idempotency key
(intent hash) + server-issued retry token per submission attempt; keep the
route lock or move to per-ledger locking for multi-process safety.

## 32. Partial fill correctness (§36)

**LIMITED (TRD-003, P2).** The internal simulator emits **one** fill per order:
if the participation cap binds, the order is PARTIALLY_FILLED with a single
fill and **no working remainder** (no subsequent fills, no average-price
aggregation); cancel-after-partial raises `PAPER_ORDER_CANCEL_NOT_SUPPORTED`
(internal path); the broker-paper path supports PARTIALLY_FILLED → FILLED and
PARTIALLY_FILLED → CANCEL_PENDING via cumulative status polls (recorded-fixture
verified), with the `open_order_count` accounting shared between paths. The
ledger records each fill as an event and recomputes position/cost-basis from
fills — multi-fill support at the *ledger* level is fine; it is the
*simulator/working-order* model that is single-shot. Target: working-order
remainder + fill aggregation (remaining_qty, avg_fill_price, multiple fills
per order) in the order model.

## 33. Cancellation / replacement correctness (§37)

**PARTIALLY_CORRECT (TRD-004/005, P3).** Cancel: internal path supports
ACTIVATED/WORKING (CREATED→CANCEL deliberately absent, documented E11);
broker path supports SUBMITTED/ACTIVATED/WORKING/PARTIALLY_FILLED with
CANCEL_PENDING → CANCELLED through cumulative status events; late fill during
cancel is not modeled (broker status poll is cumulative; the orchestrator
closes the PARTIALLY_FILLED-forever loop per `broker_paper.py`). **Replace:
absent entirely** — no REPLACE_PENDING/REPLACED states, no replace_order
capability, no UI. Target: add replace (modify quantity/limit) as
cancel+submit-with-same-client-order-id semantics with explicit state machine
entries, plus late-fill reconciliation (fill-after-cancel-detected event).

## 34. Provider reconciliation architecture (§38)

**CORRECT for the implemented scope.** BROKER_PAPER mode treats the broker as
authoritative: `_reconcile_broker_paper` fetches orders/account/positions,
builds a report (`platform/reconciliation/engine.py`),
records it as an immutable ledger event, and allows operator corrections
(RESOLVED/HELD) with `RECONCILIATION_HOLD`/`MISMATCH` statuses never silently
absorbed (P4-REC-002). Restart recovery replays events and re-derives
open-order count; config-hash compatibility prevents resuming an incompatible
session. Gaps for the target: no polling cadence (reconciliation is
on-demand), no missed-event gap detection beyond cumulative status polls, no
IBKR-native reconciliation; local state is never authoritative when a broker
path exists (correct rule, verified).

## 35. Risk architecture (§39)

**PARTIALLY_CORRECT.** Separation exists: risk *calculation* (`risk/decision.py`
+ `risk/policy.py` + `risk/kill_switch.py`), risk *decision* (APPROVE/RESIZE/
REJECT), risk *enforcement* (submit path calls `evaluate_risk` and
`submit_interactive_order` refuses without `PAPER_EXECUTION_AUTHORITIES` +
INTERNAL_SIMULATION), risk *display* (project_risk, ticket preview). **Can
submission bypass risk?** No — the submit path always calls `evaluate_risk`;
there is no bypass path found. But the calculation is equity-share-only and
the enforcement surface is thin (see §36).

## 36. Pre-trade risk (§40) — control classification

| Control | Status | Class |
|---|---|---|
| Kill switch | `risk/kill_switch.py`, enforced in `evaluate_risk` | **ENFORCED** |
| Max order size | `max_order_shares`, APPROVE/RESIZE/REJECT | **ENFORCED** (share units) |
| Max position size | `max_position_shares` projected | **ENFORCED** (share units) |
| Max open orders | `max_open_orders`, maintained across lifecycle + replay | **ENFORCED** |
| **Buying power / cash** | **no cash check in `evaluate_risk`** (grep: zero buying_power in risk/) | **DISPLAY_ONLY** (TRD-006, P2) |
| Gross/net exposure | share counts in preview envelope only | ADVISORY (display) |
| Concentration | not present | NOT_IMPLEMENTED |
| Liquidity | `cross_lane` liquidity gates (research) — not connected to order risk | NOT_IMPLEMENTED (at risk layer) |
| Stale data | market-data admission blocks execution on STALE/EXECUTION_STALE (L1 path) | ENFORCED (L1/market data), N/A for DEPTH |
| Unsupported instrument | no instrument-kind validation at order boundary | NOT_IMPLEMENTED (MA-005) |
| Account restrictions | authority/mode checks at submit | ENFORCED |
| Market state | `_assert_live_execution_allowed` gates + internal-simulation gate | ENFORCED (live path) |
| Provider capability | fail-closed stubs; `_assert_live_execution_allowed` probe checks | ENFORCED (live path) |
| Mode restrictions | execution_authority/mode checks | ENFORCED |

## 37. Cross-asset risk readiness (§41)

Not implemented; extensibility required: option notional (premium×multiplier)
and Greeks (delta exposure), futures notional/margin (initial/maintenance from
`FuturesContractSpec` + margins fields already modeled), bond duration/credit,
crypto volatility, commodity leverage, cross-asset concentration. The target
risk model must separate **risk inputs** (positions, prices, multipliers,
margins, FX) from **calculation** (per-asset exposure → aggregate) from
**decision** (limits vs aggregate) from **enforcement** (submit-time) from
**presentation**. The existing APPROVE/RESIZE/REJECT envelope generalizes; the
input domain must become multi-asset (see 11 §Target Risk).

## 38. Whale / large-participant architecture (§42)

**COHERENT, layered (ARCH-010, consolidation opportunity, P3).** Evidence
chain: family dataclasses (`participant/evidence.py`: Insider/Activist/
InstitutionalHolding/ParticipantSkill; `contracts/participant.py`:
MetaorderEvidence, DerivativeParticipantEvidence, ForcedFlowEvidence) →
`ParticipantEvidenceEnvelope` (participant_id, participant_type,
identity_confidence, mechanism, directional_clarity, horizon,
research_classification, provenance_class, source_provenance, quality_flags)
→ `NormalizedLaneEvidence` (cross_lane) → fusion. The envelope carries
exactly the target fields of §42 (source, participant type, instrument,
timestamp, direction, magnitude, confidence, provenance). The `futures_positioning`
whale-family label for depth-derived imbalance is a known naming-semantics
item (WS04, carry to WS07). COT/13F families exist as fixtures + gated live
(EDGAR). No blocker; elevation of families to provider-backed lanes is a WS07
product decision (D20).

## 39. Industry intelligence architecture (§43)

**MISSING as a domain** (product gap, not architecture). Nothing blocks a
coherent connection: instrument metadata (XA-01 aliases/relationships),
sector/industry as instrument metadata extensions (no new stack needed), news/
fundamentals providers (gated), and the market-context evidence chain can all
feed `NormalizedLaneEvidence`. Target: industry = instrument-metadata
dimension + evidence lane (sectors/peers/supply chains via relationships),
no separate data stack.

## 40. Government / public-sector architecture (§44, §45)

**CORRECT for macro; policy/regulatory workflow missing (product gap).**
FRED/ALFRED: vintage/revision-first (vintage_date, revision_number,
revision_delta, ALFRED knowledge intervals, `revision_delta` helper) —
look-ahead protected; CFTC COT: publication-delay PIT (`cot_point_in_time_valid`);
EIA/NOAA/SEC/CBOE adapters live-gated with PIT fixtures. These feed canonical
PIT verticals (XA-02/03) + market-context macro, not just raw provider data.
Target: keep; add policy/regulatory event workflow (release calendar,
revision surfacing) as an evidence lane.

## 41. Research / signal / opportunity / decision boundaries (§46, §47)

**CORRECT.** Layers verified: raw source → normalized observation
(envelope/admission) → research feature (options/futures/order-flow engines)
→ evidence/signal (`NormalizedLaneEvidence` + EvidenceSignal) → opportunity
(`FusedOpportunity` with disclaimer) → decision (strategy runtime with
eligibility gate; `research_candidate_id` CAND-<uuid> enforced; decision-source
snapshot validated against correlation) → order (paper path). Research results
cannot silently become executable orders: eligibility gate + preview re-run +
explicit user submission at the Workspace boundary. The fused EV uses an
**uncalibrated occurrence probability** (Phase 4 NOT_CALIBRATED) — carried
with a research disclaimer and quality flags; flagged so it is never mistaken
for a calibrated edge (TRD-009, P3).

## 42. Cross-lane fusion architecture (§48)

**ARCHITECTURALLY CORRECT; dirty-tree state is environmental.** Assessed
read-only (files untouched per WS05 §83):
- Ownership: `cross_lane/fusion.py` (engine) + `cross_lane/opportunity.py`
  (contracts) + `cross_lane/extractors.py` (input adapters) — one owner.
- Input contracts: typed dataclasses (ProbabilityInput, PayoffInput, CostInput,
  LiquidityInput, FuturesInput) each with source_ref + quality_flags; no
  raw-dict smuggling.
- Output contract: decomposed `FusedOpportunity` (fused_net_ev, occurrence_
  weight, liquidity_factor, gross_ev_before_weights, template,
  squeeze_aligned) + explicit method/version + replay_hash; no opaque score.
- Formula: `gross_ev × occurrence_factor × liquidity_factor × futures_regime_
  factor`, friction handled once (already-net tolerance), liquidity factor
  gates (0.0 → NO_ACTIONABLE_EDGE/LIQUIDITY_BLOCKED). No double-counted
  friction found (PAYOFF_EV_ALREADY_NET_OF_FRICTION flag exists).
- Provenance: source_refs + quality flags + disclaimer on every output.
- Stale-evidence/conflicting-signals: inputs are per-snapshot; quality flags
  surface missing inputs; cross-lane DAG validation (evidence.py) prevents
  circular reinforcement (MC-D20 lag rules).
- Cross-asset readiness: futures regime inputs exist (FuturesInput) — the
  fusion engine is class-agnostic; probability layer is squeeze-centric today
  (occurrence requires squeeze-aligned template) — acceptable scope.
- The single failing golden test (`test_bullish_active_squeeze_fusion_golden`)
  is caused by the pre-existing dirty working tree (replay-hash mismatch), not
  by the committed engine — environmental, excluded from baseline (WS04 §8).

## 43. Formula ownership audit (§49)

| Formula | Canonical owner | Duplicates found |
|---|---|---|
| CVD / cumulative delta / BVC / OFI | `donor_patterns/cvd_formulas.py` | none (consumers import it) |
| Aggressor classification | `order_flow/aggressor.py` over cvd_formulas | none |
| LOB features / OFI pair | `order_flow/ofi.py`, `order_flow/lob_features.py` | none |
| Risk-neutral distribution | `contracts/risk_neutral_distribution.py` + `options/risk_neutral.py` | single chain |
| Squeeze scoring | `squeeze_models/*` + `short_intelligence/*` | single chain (child screener separate governed repo, bridged) |
| Fusion score | `cross_lane/fusion.py` | none |
| P&L / cost basis | `portfolio/ledger.py` | **options ledger duplicates P&L on a float base** (MA-003) |
| Exposure | `paper_projections` share counts | options exposure separate |
| Option confirmation | `donor_patterns/options_lane.py` → `options/*` | none |
| Depth imbalance | `order_flow/lob_features.py` | futures lane label naming item (WS04) |

## 44. Numeric precision audit (§50)

| Value | Classification | Evidence |
|---|---|---|
| Equity price/cash/P&L | **DECIMAL_REQUIRED — implemented as int minor units** | `numeric.py` + `portfolio/ledger.py` |
| Options strike/multiplier/ledger | **DECIMAL_REQUIRED — strike/multiplier Decimal, but ledger float** | `contracts/options.py` (Decimal) vs `portfolio/options_ledger.py` (float cash) — MA-003 |
| Futures spec/prices | DECIMAL_REQUIRED — Decimal | `contracts/futures.py` |
| Futures roll/variation-margin/spread P&L | **DECIMAL_REQUIRED — currently float** | `execution/simulator.py` `simulate_futures_roll`/`simulate_variation_margin_change`/`simulate_calendar_spread_pnl` — TRD-007 (P2) |
| Order quantity | INTEGER_UNITS | `paper/contracts.py` (int enforced) |
| CVD/OFI deltas | FLOAT_ACCEPTABLE (measurement, not money) | order_flow |
| Risk thresholds | INTEGER_UNITS (shares) today; notional later | risk/policy |
| Fees/commission | int minor units | paper/contracts |

## 45. Currency architecture (§51)

**USD-only, intentional but undocumented as a limitation.** `currency: str =
"USD"` defaults in `paper/contracts.py:63`, `risk/policy.py:22`,
`xa01/contracts.py:31`; `DenominationMetadata.currency` exists; **no FX
conversion, no multi-currency totals, no per-position currency.** Futures
contracts carry `currency` (USD default); FRED vertical is USD macro. Target:
currency is per-instrument denomination + per-account base currency with
explicit FX layer before any multi-currency portfolio; document USD-only as a
current limitation (11).

## 46. Cache architecture (§52)

| Cache | Owner | Key scope | TTL | Notes |
|---|---|---|---|---|
| `AccountSnapshotCache` | `ui_api/account_snapshot_cache.py` | identity (mode+broker+account+env+portfolio) × logical_id, sha256 | none (manual/refresh) | per-entry refresh locks; stale-on-failure flags — **correct** |
| Storage dataset/projection cache | `storage/*` | sha256 content-addressed + logical_ids | precision policy | WS04 KEEP_AS_IS |
| Live runtime state | `market_data/observational_state.py` | instrument_id only (read-only observational) | trades deque 500; quotes/books overwritten | no book TTL (ARCH-009) |
| Provider planner cache | `providers/planner.py` | cache_key per request | configured | license-class aware |
| Frontend React Query | `ui/src/api/hooks.ts` | symbol-scoped lane keys; NOT mode-scoped | staleTime 0 default | ARCH-005 |

No cross-account leakage: AccountSnapshotCache keys are identity-scoped and
tested (TD-003 closure VALID). No cross-mode leakage at backend: mode is in
every identity key and is process-level. Frontend lane keys are the only
contextually under-scoped keys (P3).

## 47. Frontend query-key architecture (§53) / state ownership (§54)

- Query keys: workspace lanes are `["workspace", symbol, lane]` (+ dataMode for
  squeeze/evidence); paper portfolio split by view mode (paperPortfolio vs
  demoPortfolio); live canary keys include account_id. **Mode is not in
  workspace lane keys** — switching modes relies on remount + staleTime 0
  refetch (ARCH-005, P3).
- State ownership: server state (React Query) vs client UI state (useState
  in ticket/scrub) vs draft trading state (`paperOrderDraft.ts` typed, key-
  validated, route-symbol-checked) vs persistent settings (operator store) vs
  mode/account (ApplicationBootstrap + context). Duplicated truth is limited:
  draft state is frontend-only by design (server re-derives at submit);
  preview state is frontend-only (server has no preview record — the TRD-001
  gap); `confirmedRequestIsCurrent` is the ticket's staleness check.

## 48. API / error contract architecture (§55, §56)

- API: stdlib HTTP server, 90+ routes, GET read-only + gated POSTs; payloads
  are **dict envelopes** with `authority_boundary`/`as_of_context`/
  `capability_states` decorations; UI has its own **2000-line zod schemas.ts**
  — frontend-specific duplication, no generated/versioned contract from the
  backend (ARCH-007, P2; schema-drift risk; `schemas.test.ts` mitigates
  partially).
- Error contract: string `reason_code` + message + HTTP status; categories
  present include VALIDATION (UI_REQUEST_INVALID, ORDER_*), PROVIDER_UNAVAILABLE
  (PROVIDER_NOT_CONFIGURED, BROKER_TRANSPORT_NOT_IMPLEMENTED), RISK_BLOCKED
  (RISK_*), MODE_BLOCKED (PAPER_EXECUTION_NOT_AUTHORIZED, OPERATING_MODE_
  UNSUPPORTED), AUTH (authorization_http_status), TIMEOUT/STALE (QUAL-LIVE-*),
  RATE_LIMITED (IBKR RateLimitError). Not yet a typed enum with a canonical
  taxonomy (STALE_DATA vs PROVIDER_REJECTED vs UNSUPPORTED_CAPABILITY are
  partially distinguishable) — target taxonomy in 11 (§Target API).

## 49. Reliability / failure-mode audit (§57)

| Failure | Current behavior | Verdict |
|---|---|---|
| Provider outage (live) | admission blocks on PROVIDER_DISCONNECTED; live gates block execution | visible + safe + recoverable |
| Timeout | bounded transports (IBKR timeout, live waits with monotonic deadlines) | safe |
| Malformed payload | admission INVALID_QUOTE; envelope build fail-closed | safe |
| Stale quote | STALE/EXECUTION_STALE flags; execution blocked | safe (L1); **depth not covered (ARCH-009)** |
| Credential expiration | provider health surfaces; fail-closed stubs | visible |
| Rate limit | IBKR pacer penalty box; 429 → RateLimitError | safe |
| Backend restart | SQLite event restore + config-hash compatibility + OPEN_SESSION_DETECTED banner | safe + auditable |
| Frontend reconnect | startup readiness + mode transition retry | safe |
| IBKR reconnect (target) | admission on_reconnect resets sequences; **book rebuild missing** | gap (ARCH-003) |
| Subscription loss (live) | capability registry probe stale → gates | visible |

Silent incorrect behavior was not found in verified paths; the depth-staleness
and preview-binding gaps are the closest to it (both display/integrity-level,
not execution-safety).

## 50. Restart / recovery architecture (§58)

**CORRECT.** Open-order truth = replayed ledger events (`open_order_count`
re-derived from OrderStateChanged events); positions/cash/P&L = replayed fills;
idempotency index restored from SQLite; live marks restored from snapshot
(mark_quality="RESTORED", waits for fresh evidence); provider sessions are
rebuilt at startup (live runtime is process-lifecycle); subscriptions are not
restored (live observational re-subscribes per UI) — acceptable for a local
tool; previews are intentionally not restored (ephemeral).

## 51. Concurrency architecture (§59)

**CORRECT for single-process design; documented assumptions.** `LEDGER_ROUTE_LOCK`
serializes all ledger-mutating routes; AccountSnapshotCache refresh locks are
per-entry; ledger append uses an atomic batch for Fill+Position; the
idempotency lookup→record pair is atomic under the route lock; no shared
mutable state across accounts (identity-scoped). Residual: multi-process or
direct-caller races on idempotency (TRD-002); live runtime feed callbacks
append to deques without locks (observational only, single consumer thread);
no deadlock path found. Target: per-ledger locking + content-derived
idempotency for multi-process readiness.

## 52. Observability / secrets (§60, §61)

- Observability: structured event log (`log_server_event`), RT-01 traces
  (intent→risk→submission→state→fill→portfolio), account/mode/provider/order
  ids in ledger events and traces; lane provenance timestamps on API payloads;
  feed metrics (lag p50/p95, queue depth, dropped, duplicates, reconnects) in
  `/provider/health`. Error classification is reason-code-based (partially
  typed). No request-id header propagation found (P4).
- Secrets: `.env.example` documents gates; `credential_audit.py` scans for
  secrets with redaction; `assert_no_secrets_in_payload` blocks responses
  containing secrets (UI_SECRET_LEAK_BLOCKED); IBKR client sanitizes error
  bodies and never logs credentials; `.env`/`.venv`/node_modules gitignored.
  **No exposure found** (WS03 zero provider tokens in IMP; `finviz/api_keys.py`
  remnant token is empty). No rotation during WS05 (per §61).

## 53. Authentication / authorization (§62)

IMP is a **single-user local tool** with optional auth (`IMP_AUTH_ENFORCEMENT_MODE`,
session tokens, `permitCapability` for paper.order.submit) and loopback-only
HTTP by default. No enterprise auth imposed. Trading/account actions are
loopback-bound and capability-gated; a malicious LAN client would still be
blocked by backend authority checks (auth is a UX layer, backend authority is
the boundary — MODE_AUTHORITY.md states this). Verdict: appropriate; do not
impose multi-user auth.

## 54. UI architecture target fit (§63–§65)

- Navigation today: mode-routed launcher → Dashboard (Now) / Explore / Discover
  / Research / Portfolio / 11 workspace lanes / Live canary / Settings /
  Control / Assistant. The 11 lanes map to authorized streams (squeeze,
  order-flow, order-book, options, futures, catalyst, fund-etf, disclosure,
  institutional-flow, large-transactions, evidence). Missing routes: Bonds,
  Crypto, Gold, Silver, Commodities, Industry, Government, unified whale
  cockpit (WS04 §7 MS-08/TD-W8). Adding them is additive (new lanes + route
  registry entries), not a redesign — the lane registry + Mode*Route pattern
  supports it.
- Dashboard semantics (§64): compact metrics + exceptions is the implemented
  direction (Attention feed with tiers + Now page); P&L/cash/BP/exposure/open
  orders/risk utilization exist on the Paper portfolio page; data health
  exists via provider health + quality summaries. Preserved; WS06 reviews
  surface.
- Draft carry / re-preview invariant (§65): implemented in `OrderTicket.tsx`
  (auto re-preview on draft arrival; submit gated on current PASS preview).
  **Architecture preserves the invariant at the UI layer; the server does not
  enforce it** (TRD-001).

## 55. Testing architecture (§66, §67)

Classification of the 3580-test baseline: unit + domain (formulas, contracts),
provider-contract (fixture adapters, Tradier recorded responses, IBKR
observational client 47), integration (replay, paper lifecycle, broker paper
on recorded responses, canary), safety regression (mandatory invariants 21,
paper governance/qualification in intelligence 1165), UI component (438),
E2E (none browser-driven; UI tests are component-level). Gaps:
- overmocking: minimal (providers are fixture-first by design, recorded
  responses);
- missing provider contracts: **IBKR L1/L2 runtime adapter (absent — no depth
  contract tests), crypto/bond providers (absent)**;
- missing concurrency tests: idempotency-under-lock behavior is tested via
  route tests but there is no multi-thread stress test;
- lifecycle gaps: no test asserts the preview→submit binding (because it
  doesn't exist server-side) — a regression test must accompany the target
  change; no replace-lifecycle tests (feature absent);
- fixture-only confidence: documented per lane (05) and never counted as
  runtime capability.

Critical safety test register (target additions): Demo/Paper/Live isolation
(exists — extend to frontend query-key isolation), account isolation (exists),
cache isolation (exists), **query-key isolation (add)**, **stale preview
invalidation (add with TRD-001)**, duplicate submission (exists — add
content-derived key case), partial fills (add multi-fill/remainder case),
cancel races (add late-fill-during-cancel), provider reconnect + **book
rebuild (add with ARCH-003)**, stale depth (add with ARCH-009), IBKR L1/L2
subscription/entitlement failure (add with ARCH-001), multi-asset identity
(add with MA-*).

## 56. Performance architecture (§68)

MEASURED: FULL validate 451s (60 suites), UI 438 tests 57s, domain runs 2–320s
(WS04). STRONGLY_INDICATED: `validate changed` under-selects (21 tests) in the
monorepo embedding (tooling, not runtime). SPECULATIVE: Level-2 throughput —
no depth-stream benchmark exists; snapshot-replacement book state + per-request
book features could be a throughput problem with a real IBKR depth stream
(ARCH-003 note; measure at WS06/07 before the adapter increment). No other
material performance evidence was found; no action without measurement.

## 57. Architecture convergence audit (§69)

| Generation A (older) | Generation B (newer) | Disposition |
|---|---|---|
| `donor_patterns/` lane formulas | Q-series-hardened formulas (same files, hardened in place) | KEEP_CURRENT (annotate namespace, TD-P2) |
| `donor_bridge/` read-only research bridges | canonical provider projections | KEEP_CURRENT (research-only; isolation tested) |
| Equity-share ledger (`portfolio/ledger.py`) | (target) multi-asset portfolio | MIGRATE_OLD_TO_NEW (P1-2) |
| Options float ledger (`portfolio/options_ledger.py`) | (target) merged multi-asset ledger | CONSOLIDATE (MA-003) |
| Two asset-class vocabularies (paper ASSET_CLASSES vs XaAssetClass) | one canonical enum | CONSOLIDATE (ARCH-004) |
| Legacy UI-001 mode label (`legacy_mode_label`) | orthogonal data/execution dimensions | KEEP_CURRENT (compat layer; REMOVE_COMPAT_LAYER_LATER at WS07) |
| `providers/contracts.py` Protocols + composition | (target) Provider Capability Registry | MIGRATE_OLD_TO_NEW (additive) |
| Live book SNAPSHOT replacement | (target) incremental depth engine | REPLACE (ARCH-003) |

No permanent dual architecture is justified today except the documented
compat label; the ledger duality is the one that must converge (P1-2/MA-003).

## 58. Repository / package structure (§70)

Module organization reflects **domain ownership for the new layers**
(options/, futures/, order_flow/, participant/, market_data/, cross_lane/,
intelligence/, xa01..05/) and **historical phase naming for the older layers**
(donor_patterns/, donor_bridge/, phase*_assertions.py at root, of01..03,
rt01, local_state). The `donor_patterns/` name is provenance debt (TD-P2):
contents are independent lane formulas. Root-level phase assertion modules
(phase0a..phase16) are governance artifacts, not domain code. Renaming/
reorganization would improve clarity but is deferred to WS07 (zero behavior
change, mechanical). `intelligence/` + `participant/` + `cross_lane/` overlap
is the main structural smell (three evidence homes) — document ownership
boundaries at WS07 (ARCH-010).

## 59. KEEP_AS_IS register (§71) — verified this workstream

| Area | Evidence (this WS05) | Why keep |
|---|---|---|
| Operational identity + account-scoped cache keys | `operational_identity.py`, `account_snapshot_cache.py` | Correct identity/cache isolation; tested |
| Demo/Paper/Live backend authority + env gates + offline guard | `operating_modes.py`, `offline_guard.py`, MODE_AUTHORITY, mandatory invariants | Verified safety boundary; fail-closed |
| Paper event-sourced ledger + idempotency + RT-01 + SQLite recovery | `paper/ledger.py`, `local_state/*`, `rt01/*` | Append-only, traced, restart-recoverable, single numeric base |
| Market-data envelope/admission/timestamp/freshness | `providers/envelope.py`, `market_data/{live_admission,timestamps,provider_time}.py` | Correct time semantics + fail-closed admission |
| Q-series formula libraries (CVD/BVC/OFI, options, futures) | `donor_patterns/cvd_formulas.py`, `options/*`, `futures/*`, formula ledger | Standard math, golden replay, fail-closed numerics |
| Futures contract/roll/continuous model | `contracts/futures.py`, `futures/{roll,continuous}.py` | Family vs contract separation; Decimal; continuous never executable |
| Option contract model | `contracts/options.py` | Typed identity + Decimal + deliverable spec |
| Cross-lane evidence/fusion contracts | `cross_lane/evidence.py`, `cross_lane/{fusion,opportunity}.py` (committed state) | Typed inputs, explicit formula, DAG validation, provenance |
| Participant evidence envelopes + families | `contracts/participant.py`, `participant/*` | Coherent whale evidence chain |
| FRED vintage/ALFRED revision + bitemporal store | `fred/*`, `runtime/bitemporal_store.py` | Revision-safe macro evidence |
| Provider capability Protocols + composition + fail-closed stubs | `providers/{contracts,composition,registry}.py` | Capability-based, fail-closed |
| IBKR observational client (allowlist/pacing/capture) | `tools/ibkr/*` | Seed for the required adapter; read-only safe |
| Storage/dataset cache subsystem, canonical validation system, governance docs | WS04 §9 (unchanged) | Foundational, independent, tested |
| Cross-lane fusion dirty-tree state | WS01 baseline exclusion | Environmental; not committed code |

## 60. Architecture Blocker Register (§72)

| ID | Blocker | Severity | Authorized capabilities blocked | Root cause | Target correction |
|---|---|---|---|---|---|
| AB-001 | Equity-only authoritative portfolio/risk ledger (single-instrument sessions, share-denominated, no multiplier/notional/margin) | **P1** | Options/Futures/Bonds/Crypto/Gold/Silver/Commodities portfolio + risk semantics (P1-2) | Ledger designed as per-session equity sim; options ledger bolted on separately | Canonical multi-asset portfolio + denomination-aware valuation + merged ledger (ARCH-002, MA-003) |
| AB-002 | IBKR L1/L2 CVD runtime adapter absent | **P1** | CVD/Level-2 live measurement (LATER-002, professor-required) | Provider not integrated; L1 observational tooling not wired; no L2 | IB adapter with L1+L2 market-data capability + CVD wiring (ARCH-001) |
| AB-003 | Level-2 book = snapshot replacement; no incremental event model, no book reset/stale control | **P1** | Real IBKR depth ingestion; correct Level-2 state | Observational state store replaces book per event | Incremental depth engine + book lifecycle (ARCH-003) |
| AB-004 | No CRYPTO asset class/kind in XA-01; no venue/chain identity | P2 | Crypto domain identity (MND-002) | Identity enum predates mandate | Add CRYPTO + pair/venue identity (MA-001) |
| AB-005 | Order/instrument boundary accepts arbitrary symbol; no tradable-contract validation | P2 | Safe Futures/Options execution (continuous/family could be submitted) | `build_instrument_ref` equity-defaulting, no kind check | Instrument-kind validation at submission + contract resolution (MA-005) |
| AB-006 | No server-side preview→submission binding | P2 | Trading UX integrity invariant (§65) | Preview is ephemeral dry-run; submit re-derives | Preview tokens + fingerprint binding (TRD-001) |
| AB-007 | Buying power not enforced (cash never checked in risk) | P2 | Risk completeness before broker-backed execution | Risk limits share-only; cash omitted | Cash/BP check in evaluate_risk (TRD-006) |
| AB-008 | USD-only currency assumption undocumented | P3 | Multi-currency portfolio (future) | Defaults hard-coded USD | Document; FX layer when needed (ARCH-011) |

## 61. ADR candidates (§82)

| ADR_CANDIDATE_ID | Problem | Recommendation (target architecture) | Migration risk | Dependencies | Tests required |
|---|---|---|---|---|---|
| ADR-C-001 | Multi-asset portfolio/ledger | Canonical position model + denomination-aware valuation; merge options ledger | High (all portfolio/trading paths) | Identity consolidation (ADR-C-004) | portfolio parity, cross-asset valuation golden |
| ADR-C-002 | IBKR L1/L2 CVD adapter | IB adapter (market-data + account/portfolio) seeded from `tools/ibkr`; depth engine (ADR-C-003) | Medium | Depth engine; entitlement gates | IBKR provider-contract suite, CVD live replay |
| ADR-C-003 | Incremental L2 book | Depth event model + book lifecycle + stale TTL | Medium | ADR-C-002 | book state-machine tests, reconnect/reset tests |
| ADR-C-004 | One asset-class vocabulary | Consolidate paper ASSET_CLASSES into XaAssetClass (+CRYPTO, +bond typing, +commodity identity) | Medium | xa01 registry | identity resolution tests |
| ADR-C-005 | Preview binding | Server preview tokens + fingerprint + invalidation | Low | trading lifecycle | preview/submit integrity tests |
| ADR-C-006 | Risk completeness | Buying-power/cash + notional exposure + instrument-kind checks | Medium | ADR-C-001/004 | risk enforcement tests |
| ADR-C-007 | Replace + working-order remainders | Replace states + multi-fill aggregation | Medium | order model | lifecycle/replace tests |
| ADR-C-008 | Order numeric base for futures/options P&L | Decimal/minor-units in roll/variation-margin/spread simulators | Low | — | numeric golden tests |
| ADR-C-009 | Provider Capability Registry | Roles + capability discovery + gates + freshness policy | Low-Medium | provider contracts | capability discovery tests |
| ADR-C-010 | Crypto/bond/commodity identity extensions | CRYPTO class + pair identity; Bond descriptor typing; commodity contract identity | Medium | ADR-C-004 | identity tests |

## 62. Target-fit classification of the ten framework questions (§3)

For each important subsystem, the framework answers are summarized in the
matrix below (canonical responsibility → current owner → ownership clear? →
abstraction correct? → model correct? → dependency direction? → safety
boundaries? → asset-class support? → provider support? → failure behavior? →
disposition):

| Subsystem | Disposition | Notes |
|---|---|---|
| Instrument identity kernel (XA-01) | **KEEP_AND_HARDEN** | Extend CRYPTO/bond/commodity; consolidate vocabularies |
| Futures contracts/roll/continuous | **KEEP_AND_HARDEN** | Add submission-time contract validation |
| Options contracts/analytics | **KEEP_AND_HARDEN** | Wire live chain provider; merge portfolio |
| Market-data envelope/admission/timestamps | **KEEP_AND_HARDEN** | Add depth staleness + session anchors |
| Live book state | **REPLACE** (bounded) | Incremental depth engine (ARCH-003) — bounded replacement, not blanket rewrite |
| Provider contracts/composition | **KEEP_AND_HARDEN** | Add capability registry + discovery |
| IBKR tooling | **KEEP_AS_IS → MIGRATE** to adapter seed | Add L1/L2 depth + account/portfolio capabilities (ARCH-001) |
| Paper ledger + execution | **KEEP_AS_IS** (internal path) | Add replace/remainder/BP checks; keep event sourcing |
| Options ledger | **CONSOLIDATE** into canonical ledger | Float→minor-units merge (MA-003) |
| Order model | **KEEP_AND_HARDEN** | Add TIF/stop/OCO/bracket + contract validation |
| Risk | **KEEP_AND_HARDEN** | BP/cash + notional + multi-asset inputs |
| Preview/submission | **KEEP_AND_HARDEN** | Server-side binding (TRD-001) |
| Cross-lane fusion | **KEEP_AS_IS** | Environmental dirty-tree only |
| Evidence/intelligence | **KEEP_AS_IS** (+ consolidation note) | Three evidence homes → document ownership at WS07 |
| Frontend state/query keys | **KEEP_AND_HARDEN** | Mode-scope lane keys (ARCH-005) |
| API/error contracts | **KEEP_AND_HARDEN** | Typed error taxonomy; contract generation direction |
| Storage/dataset cache | **KEEP_AS_IS** | WS04 |
| Local-state recovery | **KEEP_AS_IS** | Verified |
| `donor_patterns/`/`donor_bridge/` naming | **SIMPLIFY** (annotate) | TD-P2; rename deferred to WS07 |

---

## 63. Findings register

### ARCH findings (architecture)

| ID | Title | Severity | Current architecture | Evidence | Correctness | Capabilities affected | Root cause | Disposition | Target | Migration deps | Tests required | Confidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ARCH-001 | IBKR L1/L2 CVD runtime adapter missing | **P1** | Observational Client Portal REST + TWS L1 only; no depth; not wired to CVD lane | `tools/ibkr/*` (no reqMktDepth); `order_flow/*` fixture-first; WS04 P1-1 | INCORRECT (missing required capability, not wrong code) | CVD/Level-2 (LATER-002) | Provider integration never authorized/executed (LIVE gates) | IB adapter (ADR-C-002) | depth engine (ARCH-003) | IBKR provider-contract + CVD live replay | CONFIRMED |
| ARCH-002 | Equity-only portfolio/risk model | **P1** | Single-instrument share-denominated ledger; options ledger separate float | `paper/ledger.py` (position_shares), `portfolio/ledger.py`, `portfolio/options_ledger.py` (float) | PARTIALLY_CORRECT (equity-correct; multi-asset wrong) | Options/Futures/Bonds/Crypto/Gold/Silver/Commodities portfolio+risk | Ledger designed per-session equity sim | MIGRATE (ADR-C-001) | identity consolidation | parity + valuation goldens | CONFIRMED |
| ARCH-003 | Level-2 book is snapshot-replacement only; no incremental events, reset, or stale control | **P1** | `observational_state` replaces book per DEPTH event; `update_semantics="SNAPSHOT"`; no insert/update/delete; no book TTL; `book_state_valid:True` hardcoded in payload | `market_data/observational_state.py`, `ui_api/live_projections.py`, staleness check only for L1/SNAPSHOT | INCORRECT for real IBKR depth streams | CVD/Level-2 live; order-book lane | State store designed for MBP snapshots | REPLACE_BOUNDED (ADR-C-003) | ARCH-001 | depth state-machine + reconnect/reset tests | CONFIRMED |
| ARCH-004 | Two asset-class vocabularies + equity-defaulting instrument ref | P2 | `paper/contracts.ASSET_CLASSES` (incl. CRYPTO) vs `xa01.enums.XaAssetClass` (no CRYPTO); `build_instrument_ref` defaults EQUITY/US_EQUITY/multiplier 1 | `paper/contracts.py:38-46`, `xa01/enums.py` | PARTIALLY_CORRECT | All non-equity domains at runtime boundary | Parallel evolution | CONSOLIDATE (ADR-C-004) | — | identity resolution tests | CONFIRMED |
| ARCH-005 | Frontend workspace query keys not mode-scoped | P3 | `["workspace", symbol, lane]`; mode switch relies on remount+refetch | `ui/src/api/hooks.ts` | CORRECT_WITH_LIMITATIONS | UX state integrity across modes | Key design predates mode session | KEEP_AND_HARDEN | — | query-key isolation test | CONFIRMED |
| ARCH-006 | Multi-level OFI rank-based pairing approximation | P3 | Pairs level N→N across snapshots; level insert/delete mis-pairs; empty rank counts whole size as add | `order_flow/ofi.py compute_multilevel_ofi` | PARTIALLY_CORRECT (documented approximation) | Level-2 signal quality | Snapshot-pair formulation | KEEP_AND_HARDEN (delta-based or identity-preserving OFI) | ARCH-003 | OFI golden incl. level-churn cases | HIGH |
| ARCH-007 | Frontend zod schemas duplicate backend envelopes; no versioned contract | P2 | 2000-line `schemas.ts`; backend returns dicts | `ui/src/api/schemas.ts` | PARTIALLY_CORRECT | API contract integrity | No codegen/versioning | KEEP_AND_HARDEN (contract direction) | — | schema-drift test exists; extend | HIGH |
| ARCH-008 | Futures roll/variation-margin/spread P&L float | P2 | `simulate_futures_roll`/`variation_margin_change`/`calendar_spread_pnl` float rounding | `execution/simulator.py` | PARTIALLY_CORRECT | Futures P&L correctness | Simulator convenience | KEEP_AND_HARDEN (Decimal/minor) (ADR-C-008) | — | numeric goldens | CONFIRMED |
| ARCH-009 | Live order-book has no staleness control and is presented valid unconditionally | P2 | Stale check scoped to L1/SNAPSHOT; book overwritten per event; payload hardcodes `book_state_valid:True` | `live_admission.py:203-224`, `ui_api/live_projections.py` | INCORRECT (display) | Order-book lane freshness | Depth excluded from freshness model | KEEP_AND_HARDEN (part of ARCH-003) | — | stale-depth display tests | CONFIRMED |
| ARCH-010 | Three evidence homes (cross_lane / intelligence / participant) | P3 | NormalizedLaneEvidence vs EvidenceV1 vs family dataclasses — coherent chain but duplicated shapes | `cross_lane/evidence.py`, `intelligence/contracts/evidence.py`, `participant/evidence.py` | CORRECT_WITH_LIMITATIONS | Maintainability | Layered evolution | KEEP_AS_IS + ownership documentation at WS07 | — | none | HIGH |
| ARCH-011 | USD-only currency assumption undocumented | P3 | `currency="USD"` defaults; no FX | `paper/contracts.py:63`, `risk/policy.py:22`, `xa01/contracts.py:31` | CORRECT_WITH_LIMITATIONS (intentional) | Multi-currency future | Scope | DEFER (document now) | — | — | CONFIRMED |

### SAFE findings (safety)

| ID | Behavior | Reachability | Impact | Current protection | Failure path | Severity | Required correction | Test required | Confidence |
|---|---|---|---|---|---|---|---|---|---|
| SAFE-001 | Replay cursor moves between preview and submit; submission executes at the new cursor without invalidating the preview shown to the user | UI paper workspace (scrub while ticket open) | Paper-only P&L divergence between displayed preview and executed fill; no live risk (risk re-run at submit) | UI `confirmedRequestIsCurrent` (fields only); server re-runs risk at submit | scrub → submit | P2 | Server preview tokens + observation-time/cursor binding; invalidate on cursor change (TRD-001) | preview/submit integrity test | CONFIRMED |
| SAFE-002 | Workspace lane query keys shared across modes; a stale mode's lane payload can be displayed briefly on mode switch | UI mode switch | Stale display (research-only lanes); no execution crossover (backend authority is mode-agnostic and process-level) | Shell unmount + staleTime 0 refetch; backend mode isolation | switch mode with cached lane data | P3 | Mode-scope lane query keys (ARCH-005) | query-key isolation test | CONFIRMED |
| SAFE-003 | A non-tradable instrument id (futures family/continuous/root symbol) could be submitted as an order instrument | API/UI paper path (any symbol string) | Wrong-contract paper fill today; wrong-contract live order later (LIVE still blocked) | No instrument-kind validation at the order boundary | submit with family symbol | P2 (paper); escalates to P1 before any Live execution | Instrument-kind/tradable-contract validation at submission (MA-005, ADR-C-006) | instrument-kind rejection test | HIGH |
| SAFE-004 | Stale depth book presented as valid (`book_state_valid:True`) and used by LOB features | LIVE observational order-book lane | Research/display degradation; not execution-relevant (execution uses L1/execution buffer) | None for depth (stale check L1-only) | feed stalls → stale book persists | P2 | Depth staleness + TTL + explicit quality in payload (ARCH-009) | stale-depth test | CONFIRMED |

### TRD findings (trading correctness)

| ID | Title | Severity | Evidence | Correctness | Disposition | Tests required |
|---|---|---|---|---|---|---|
| TRD-001 | Preview→submission binding absent server-side | P2 | `ui_api/paper_projections.py` (preview/submit both re-derive from body; no preview_id); `OrderTicket.tsx` (UI-only gating) | PARTIALLY_CORRECT | Server preview tokens + fingerprint + invalidation (ADR-C-005) | preview/submit integrity |
| TRD-002 | Idempotency correct under single-process lock; not content-derived; race if lock bypassed | P2 | `server.py` LEDGER_ROUTE_LOCK; `ledger.lookup_idempotent_order`; `paperOrderDraft.ts` random attempt keys | CORRECT_WITH_LIMITATIONS | Content-derived keys + per-ledger locking for multi-process | duplicate-submit stress |
| TRD-003 | Partial fills are one-shot (single fill, no working remainder, cancel-after-partial unsupported internally) | P2 | `execution/simulator.py` (one fill); `paper/execution.cancel_interactive_order` (PARTIALLY_FILLED → NOT_SUPPORTED); broker path supports cancel from partial | PARTIALLY_CORRECT | Working remainder + fill aggregation + cancel-after-partial (ADR-C-007) | multi-fill/remainder tests |
| TRD-004 | Replace absent (no REPLACE_PENDING/REPLACED; no replace_order) | P3 | `paper/contracts.py` ORDER_LIFECYCLE_STATES; broker path grep | NOT_IMPLEMENTED | Replace states + capability (ADR-C-007) | replace lifecycle tests |
| TRD-005 | Cancel semantics correct for implemented scope; late-fill-during-cancel not modeled | P3 | `paper/execution.py`, `paper/broker_paper.py` (cumulative status, PARTIALLY_FILLED loop closure) | PARTIALLY_CORRECT | fill-after-cancel-detected event | late-fill cancel test |
| TRD-006 | Buying power DISPLAY_ONLY (no cash check in risk) | P2 | grep: zero buying_power in `risk/`; `project_account` reports BP = cash | INCORRECT (control gap) | Cash/BP check in evaluate_risk (ADR-C-006) | BP enforcement test |
| TRD-007 | Futures roll/variation-margin/spread P&L float | P2 | `execution/simulator.py` (float rounding) | PARTIALLY_CORRECT | Decimal/minor-units (ARCH-008) | numeric goldens |
| TRD-008 | CVD cumulative delta has no session anchor/reset | P3 | `order_flow/cvd.py`; deque rollover restarts series | PARTIALLY_CORRECT | Session boundary + reset semantics in series | session-reset CVD test |
| TRD-009 | Fusion EV weights use uncalibrated occurrence probability (Phase 4 NOT_CALIBRATED) | P3 | `cross_lane/fusion.py` `_occurrence_weight` (squeeze_hazard_probability); squeeze_models Phase 4 skeleton | CORRECT_WITH_LIMITATIONS (flagged + disclaimer) | Calibration plan (WS07); keep flags/disclaimer | calibration-gate test later |

### MA findings (multi-asset)

| ID | Title | Severity | Evidence | Assessment | Disposition |
|---|---|---|---|---|---|
| MA-001 | No CRYPTO asset class/kind in XA-01; no venue/chain/pair identity | P2 (identity blocker, not missing impl) | `xa01/enums.py` (XaAssetClass/InstrumentKind lack CRYPTO) | Blocks Crypto domain identity (MND-002) | Extend enums + pair identity (ADR-C-010) |
| MA-002 | Bond identity flat (maturity/coupon/par strings); no corporate bond class; no yield-price unit in portfolio | P2 (identity readiness) | `xa01/contracts.py` InstrumentDescriptor strings; no corporate issuer model | Blocks Bonds portfolio/analytics (MND-001) | Typed Bond descriptor + XA-02 reuse (ADR-C-010) |
| MA-003 | Options ledger separate + float cash/position key vs equity minor-int ledger | P2 | `portfolio/options_ledger.py` (float), `portfolio/ledger.py` (int) | Two portfolio truths, different numeric bases | CONSOLIDATE into canonical ledger (ADR-C-001) |
| MA-004 | Gold/Silver only generic COMMODITY; no spot/futures/ETF proxy identity | P3 | `xa01` COMMODITY class; GC/SI keys in xa03/eia | Gold/Silver domain identity readiness (MND-006/007) | Commodity contract identity via futures model + relationships |
| MA-005 | Order boundary accepts arbitrary symbol; no tradable-contract/family validation; paper instrument ref lacks multiplier defaults | P2 | `paper/contracts.py build_instrument_ref` (EQUITY/US_EQUITY/multiplier "1"); `_require_order_instrument` string resolution | Continuous/family could be submitted (SAFE-003) | Instrument-kind validation + contract resolution at submission (ADR-C-006) |
| MA-006 | Cross-asset exposure/P&L absent (share counts only; no notional/margin/FX) | P1 (same root as ARCH-002) | `paper_projections` exposure shares; ledger share-only | Blocks cross-asset portfolio/risk | Canonical portfolio + notional valuation (ADR-C-001) |

---

## 64. Target Architecture vNext — summary

Full design in [11-target-architecture.md](11-target-architecture.md). WS05
conclusions that bound the target:

1. **Domain model**: keep OperationalIdentity/ledger-event-sourcing/mode
   authority as-is; consolidate the two asset-class vocabularies; introduce a
   canonical multi-asset Portfolio (positions by instrument identity,
   denomination-aware valuation, per-currency cash, explicit FX boundary);
   keep FuturesContract/OptionContract as the tradable-contract types and
   make submission validate instrument-kind.
2. **Asset-class extensions**: extend XA-01 (CRYPTO, Bond descriptor typing,
   commodity contract identity) rather than new parallel models; one
   extensible InstrumentDescriptor + typed contracts (option/futures already
   typed; bonds/crypto ride the same identity).
3. **Market data**: keep envelope/admission/timestamp layer; replace the
   snapshot-only book with an incremental depth engine (insert/update/delete/
   clear + sequence + TTL + reconnect rebuild); add depth staleness; add CVD
   session anchors.
4. **Providers**: keep capability Protocols + composition; add a Provider
   Capability Registry (roles, gates, freshness, discovery); IB adapter seeded
   from `tools/ibkr` with L1/L2 market-data + account/portfolio capabilities;
   Tradovate as a possible BROKER_EXECUTION adapter (decision OPEN); crypto/
   bond providers TBD (no invented commitments).
5. **Trading**: keep the internal-Paper verified path; add server-side preview
   tokens + fingerprint binding, content-derived idempotency, working-order
   remainders, replace states, cash/BP enforcement, instrument-kind checks;
   Decimal for futures/options P&L.
6. **Intelligence/research**: keep the evidence chain (normalized lane
   evidence → EvidenceV1 → opportunity); document ownership of the three
   evidence homes; industry rides instrument metadata + evidence lanes.
7. **Frontend/API**: mode-scope lane query keys; typed error taxonomy;
   versioned API contracts (generation direction); keep draft-carry/re-preview
   UX and add server enforcement.
8. **Testing**: add the §67 safety-register suites as regression gates.

## 65. Technical-debt changes (this workstream)

See [10-technical-debt.md](10-technical-debt.md) — added TD-A1..A11 mapped to
the categories of controller §90 (DOMAIN_MODEL, MULTI_ASSET,
PROVIDER_ARCHITECTURE, TRADING_LIFECYCLE, RISK, IDENTITY, CACHE, STATE, API,
RELIABILITY, CONCURRENCY, NUMERIC_CORRECTNESS, TESTING, OBSERVABILITY). No
duplicate issues: TD-A entries reference the ARCH-/TRD-/MA- root causes rather
than restating them.

## 66. Open decisions resolved (this workstream)

See [14-open-decisions.md](14-open-decisions.md):
- D19 (IBKR observational tooling as seed vs separate) → **recommended SEED**
  (ARCH-001/ADR-C-002); professor-facing decision only if a different IB
  integration strategy is preferred.
- D3/D16 (Future execution provider IB vs Tradovate) → architectural shape
  recommended (both as capability adapters; bracket semantics from CCN
  reimplemented in the target order model); provider choice remains
  DECISION_REQUIRED (professor/product).
- D13 (IB data purchase) → remains UNKNOWN (no repo evidence; does not block
  the adapter design).

## 67. Closure statement

WS05 closure criteria (§94) met: canonical domain ownership mapped (§3);
multi-asset identity assessed (§4-5); operational identity/account/mode
assessed (§6-8); Demo/Paper/Live boundaries assessed (§7); provider
architecture assessed (§9); IB target architecture defined (§10); Tradovate/
CCN target fit assessed (§11); market-data architecture assessed (§13-15);
timestamp/freshness assessed (§14-15); CVD/L2 live architecture defined
(§16-18); Level-2 state semantics assessed (§18); Options/Futures/Bonds/Crypto/
Gold/Silver/Commodities assessed (§19-25); portfolio assessed (§26-27); order
model assessed (§28); trading lifecycle assessed (§29); preview/submission
integrity assessed (§30); idempotency assessed (§31); partial fills assessed
(§32); cancel/replace assessed (§33); provider reconciliation assessed (§34);
risk assessed (§35-37); whale/industry/government intelligence assessed
(§38-40); research/signal/opportunity/decision boundaries assessed (§41);
cross-lane fusion assessed (§42); formula ownership assessed (§43); numeric
precision assessed (§44); cache/query-key/frontend-state assessed (§46-47);
API/error contracts assessed (§48); reliability/recovery/concurrency assessed
(§49-51); observability/secrets assessed (§52); auth assessed (§53); UI target
fit assessed (§54); testing assessed (§55); performance classified (§56);
architecture convergence assessed (§57); repository structure assessed (§58);
KEEP_AS_IS identified (§59); blockers prioritized (§60); Target Architecture
vNext documented (§64 + 11); ADR candidates exist (§61). No P0 findings;
P0 containment not required. No code changed.