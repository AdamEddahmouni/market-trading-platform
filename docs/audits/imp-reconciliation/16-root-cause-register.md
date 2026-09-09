# 16 — Master Root-Cause Register (WS07)

Status: **COMPLETE (WS07, 2026-09-07)**. Canonical root-cause model for the
IMP reconciliation program. Collapses the WS04 current-state registers, WS05
architecture/safety/trading/multi-asset findings, and WS06
product/engineering findings into the smallest set of coherent root causes
that the master backlog (12) and recovery roadmap (13) are built on.

Rule applied (controller §10/§11/§91): one root cause owns one coherent
correction. Downstream findings are listed per root cause and are NOT
duplicated as independent backlog items. Historical rows in the source
registers are never deleted — they are marked SUPERSEDED / OWNED_BY where a
canonical backlog item now owns them.

Schema: ID · Title · Severity · Evidence · Authorized capabilities affected ·
Current consequence · Target correction · Dependencies · Downstream findings
collapsed · Validation · Confidence.

Severity: P0 immediate · P1 core blocker/severe correctness/architecture ·
P2 major · P3 optimization/debt · P4 polish. Confidence: CONFIRMED ·
HIGH_CONFIDENCE · MODERATE_CONFIDENCE · LOW_CONFIDENCE · UNKNOWN.

---

## Register

### RC-001 — Authoritative portfolio/risk domain is equity-share-centric

| Field | Value |
|---|---|
| ID | RC-001 |
| Title | Authoritative portfolio/risk domain is equity-share-centric (single-instrument sessions, share-denominated, no multiplier/notional/margin/FX) |
| Severity | **P1** |
| Evidence | `paper/ledger.py` (`position_shares`, one instrument per session), `portfolio/ledger.py` (int minor units), `portfolio/options_ledger.py` (float, separate), `execution/simulator.py` (futures float), `paper/contracts.py:63`/`risk/policy.py:22`/`xa01/contracts.py:31` (USD defaults); WS04 P1-2/MS-02; WS05 ARCH-002/MA-003/MA-006/ARCH-008/ARCH-011 |
| Authorized capabilities affected | Options, Futures, Bonds, Crypto, Gold, Silver, Commodities portfolio + risk semantics; cross-asset P&L/exposure; multi-currency; buying-power (MND-001..008, LATER-002..008, Tier E supporting architecture) |
| Current consequence | **G13 (2026-09-09):** Paper options/futures submit/fill → `CanonicalPortfolio` with CONTRACTS+multiplier, explicit margin facts (fail-closed), and canonical lifecycle (partial/replace/cancel) — **closed for Paper derivative execution**. Remaining: bonds/crypto/commodity product surfaces; O9 `options_ledger` compatibility projection (NON_AUTHORITATIVE); futures research-engine float paths; production FX aggregation |
| Target correction | Canonical multi-asset portfolio keyed by instrument identity with denomination-aware valuation (price × qty × multiplier), per-currency cash with explicit FX boundary, merged options ledger on one integer-minor/Decimal base, notional/gross/net exposure; USD-only documented until FX layer exists |
| Dependencies | RC-004 (one vocabulary) must land first; instrument identity extensions (RC-004) feed position keys |
| Downstream findings collapsed | ARCH-002, MA-003, MA-006, ARCH-008 (futures float), ARCH-011 (USD), AB-001, P1-2, MS-02, TD-W2, TD-A2, TD-A7, CON-05 |
| Validation | Portfolio parity test (existing equity behavior preserved), cross-asset valuation goldens, options-ledger numeric-conversion goldens, mode/account isolation regression |
| Confidence | CONFIRMED |

### RC-002 — Missing IBKR L1/L2 runtime market-data adapter for CVD

| Field | Value |
|---|---|
| ID | RC-002 |
| Title | Professor-required IBKR Level 1 + Level 2 runtime data integration for CVD/Level-2 is absent |
| Severity | **P1** |
| Evidence | Historical: `tools/ibkr` REST + TWS L1 without depth. **G8–G11 (2026-09-08/09):** outer transport + query provider inject L1/L2/TRADES streaming and read-only contract/secdef/historical/account queries into canonical src; classified IBKR tape→CVD offline (G9/BL-0304); depth TTL admission (G10/BL-0303). Remaining: live provider verification (bounded canary harness present; not executed). WS04 P1-1/MS-01; WS05 ARCH-001/AB-002; LATER-002 |
| Authorized capabilities affected | CVD/Level-1/Level-2 measurement (CORE_REQUIRED, LATER-001/002); order-flow lane live data |
| Current consequence | **IMPLEMENTATION_COMPLETE / LIVE_VERIFICATION_PENDING:** observational IBKR surfaces runtime-wired offline; live CVD requires entitled tick-by-tick tape (not L1 fabrication); live provider remains LIVE_PROVIDER_UNVERIFIED |
| Target correction | One IBKR provider adapter (market-data capability: L1 + L2 depth + account/portfolio read) seeded from `tools/ibkr` (D19 SEED), depth engine per RC-003, CVD lane wiring, entitlement/pacing/reconnect semantics (06 §10) |
| Dependencies | RC-003 (incremental depth engine) for L2 ingestion; provider capability registry (RC-009 direction) for roles/gates |
| Downstream findings collapsed | ARCH-001, AB-002, P1-1, MS-01, TD-W1, TD-P4, TD-A1, ADR-C-002, D19 |
| Validation | IBKR provider-contract suite (fixture-recorded L1/L2 streams), entitlement-loss test, reconnect/book-reset test, CVD-from-IB-live-replay test (recorded), pacing penalty-box tests |
| Confidence | CONFIRMED |

### RC-003 — Level-2 book is snapshot-replacement only; no incremental engine, reset, or staleness control

| Field | Value |
|---|---|
| ID | RC-003 |
| Title | Live order-book state replaces the whole book per event; cannot correctly ingest real incremental IBKR depth streams; no depth staleness; no book reset protocol |
| Severity | **P1** |
| Evidence | `market_data/observational_state.py` (`update_semantics="SNAPSHOT"`), `ui_api/live_projections.py` (hardcoded `book_state_valid: True`), `market_data/live_admission.py` (staleness gated `"L1" in capability or "SNAPSHOT" in capability` — DEPTH never flagged STALE), no insert/update/delete semantics, no book TTL, no reconnect rebuild; WS05 ARCH-003/ARCH-009/SAFE-004/AB-003 |
| Authorized capabilities affected | CVD/Level-2 live measurement (LATER-002), order-book lane, LOB/OFI signal quality |
| Current consequence | Real IBKR `reqMktDepth` streams (incremental add/update/delete + refresh + reset) cannot be represented safely; stale books can persist and be presented as valid; multi-level OFI rank pairing mis-pairs on level churn |
| Target correction | Canonical depth event model (INSERT/UPDATE/DELETE/CLEAR per side+price), full-book snapshot on subscribe/reconnect, per-level sequence, book TTL + stale eviction, explicit book validity in payload, delta-based or identity-preserving OFI |
| Dependencies | Feeds RC-002 (IB adapter needs this engine); independently buildable on fixture depth streams |
| Downstream findings collapsed | ARCH-003, ARCH-009, SAFE-004, AB-003, ARCH-006 (OFI pairing), TD-A3, TD-A9, ADR-C-003 |
| Validation | Depth state-machine tests (insert/update/delete/clear), reconnect/reset tests, stale-depth TTL test, OFI goldens with level-churn cases, payload quality assertions |
| Confidence | CONFIRMED |

### RC-004 — Two asset-class vocabularies + incomplete identity kernel + equity-defaulting runtime instrument ref

**Status: MATERIALLY_ADVANCED_BY_G1 (2026-09-07)** — one canonical vocabulary (CRYPTO/BOND added; paper `ASSET_CLASSES` deprecated compat view); crypto pair, typed bond, commodity spot/proxy, and continuous-series identities; explicit tradability + fail-closed continuous-futures guard; evidence in 15 (G1 section). BL-0101..0104 CLOSED_BY_G1. Remaining: runtime ref equity defaults at legacy call sites (paper/execution paths) and shim removal — scheduled with downstream migrations, not identity blockers.

| Field | Value |
|---|---|
| ID | RC-004 |
| Title | `paper/contracts.ASSET_CLASSES` (incl. CRYPTO/PREDICTION_MARKET) vs `xa01.enums.XaAssetClass` (no CRYPTO); XA-01 lacks CRYPTO class/kind, typed bond descriptors, commodity contract identity; `build_instrument_ref` defaults EQUITY/US_EQUITY/multiplier 1 at every paper/execution boundary |
| Severity | **P2** (identity blocker for 6 domains; not a runtime defect in equity scope) |
| Evidence | `paper/contracts.py:38-46`, `xa01/enums.py`, `xa01/contracts.py` (flat bond strings), `contracts/futures.py` (family vs contract correct), `contracts/options.py` (typed); WS05 ARCH-004/MA-001/MA-002/MA-004/AB-004 |
| Authorized capabilities affected | Crypto (MND-002), Bonds (MND-001), Gold/Silver (MND-006/007), Commodities (MND-008) identity; all non-equity runtime boundaries |
| Current consequence | Six mandated domains cannot be identified canonically; a second vocabulary drifts independently; every non-equity instrument is constructed through an equity-defaulting helper |
| Target correction | One canonical vocabulary (extend `XaAssetClass`/`InstrumentKind` with CRYPTO + CRYPTO_PAIR, typed BondInstrument, commodity contract identity via futures model); runtime instrument ref carries asset-class + contract fields; equity defaults removed from the shared path |
| Dependencies | None upstream (foundation for RC-001) |
| Downstream findings collapsed | ARCH-004, MA-001, MA-002, MA-004, AB-004, TD-A4, TD-A13, CON-01, ADR-C-004, ADR-C-010 |
| Validation | Identity resolution tests (each class × kind × contract), vocabulary-parity test (paper layer resolves through XA-01), regression on equity paths |
| Confidence | CONFIRMED |

### RC-005 — No server-side preview→submission binding

| Field | Value |
|---|---|
| ID | RC-005 |
| Title | Preview is an ephemeral frontend dry-run; the server accepts a submit without any preview proof, and the replay cursor can move between preview and submit |
| Severity | **P2** (Paper-only integrity today; escalates before any Live execution) |
| Status note (G1, 2026-09-07) | G1 advanced the identity portion only: `build_user_order_intent` now fails closed on reference/synthetic instrument refs (instrument-kind validation prerequisite, BL-0203 identity part). Server preview binding itself remains BL-0201 (not part of G1). |
| Evidence | `ui_api/paper_projections.py` (`_preview`/`_submit` both re-derive from body; no preview_id/intent-hash/cursor binding), `OrderTicket.tsx` `confirmedRequestIsCurrent` (fields only, ignores limit_price_minor + decision-source drift), `_paper_observation_time` evaluated per call; WS05 TRD-001/SAFE-001/AB-006; WS06 §8 |
| Authorized capabilities affected | Approved dashboard→workspace draft-carry → re-preview → submit invariant (controller §4); trading integrity (Tier E) |
| Current consequence | A stale preview shown to the user can diverge from the executed fill (Paper P&L divergence); submit-without-preview is possible (risk still applies, so no safety bypass, but the integrity invariant is frontend-only) |
| Target correction | Server issues `preview_id` + binds (intent hash, observation time/cursor, identity, market-state fingerprint); submit requires a valid, current preview; stale → `PREVIEW_STALE` rejection; UI carries preview_id; replay-cursor change invalidates |
| Dependencies | None architectural; small touch of trading lifecycle (RC-007 states) |
| Downstream findings collapsed | TRD-001, SAFE-001, AB-006, TD-A5, ADR-C-005, UX-005 (draft-refresh note stays) |
| Validation | Preview/submit integrity tests (stale preview rejection, cursor-move invalidation, instrument/mode/account change rejection, replay of same submit) |
| Confidence | CONFIRMED |

### RC-006 — Buying power display-only + no instrument-kind validation at the order boundary

| Field | Value |
|---|---|
| ID | RC-006 |
| Title | No cash/buying-power check in `evaluate_risk` (DISPLAY_ONLY); no tradable-contract/instrument-kind validation on submission (continuous/family futures could be submitted) |
| Severity | **P2** (P2 Paper; escalates to P1 before any Live execution — SAFE-003) |
| Evidence | `grep -rn buying_power risk/` = 0 hits; `risk/decision.py` (kill switch, max order/position/open orders only); `paper/contracts.py build_instrument_ref` accepts arbitrary symbol strings; WS05 TRD-006/SAFE-003/MA-005/AB-005/AB-007 |
| Authorized capabilities affected | Risk enforcement completeness (Tier E), safe futures/options execution, buying-power correctness |
| Current consequence | Cash is never checked at submission; a non-tradable instrument id (futures family/continuous/root) can be submitted as an order instrument |
| Target correction | Cash/BP check in `evaluate_risk` (against multi-asset cash once RC-001 lands; equity-minor check first), instrument-kind validation at the order boundary (TRADABLE_SECURITY/FUTURE_CONTRACT/OPTION_CONTRACT) with `UNSUPPORTED_INSTRUMENT_KIND` rejection |
| Dependencies | BP check can land on equity base before RC-001; instrument-kind check needs RC-004 |
| Downstream findings collapsed | TRD-006, SAFE-003, MA-005, AB-005, AB-007, TD-A6, ADR-C-006 |
| Validation | BP enforcement tests (insufficient cash rejected), instrument-kind rejection test (continuous/family symbol rejected, tradable contract accepted) |
| Confidence | CONFIRMED |

### RC-007 — Trading lifecycle gaps: one-shot partial fills, no replace, late-fill-during-cancel unmodeled

| Field | Value |
|---|---|
| ID | RC-007 |
| Title | Partial fills are one-shot (no working remainder, no fill aggregation, cancel-after-partial unsupported internally); replace absent (no REPLACE_PENDING/REPLACED states, no `replace_order` capability, no UI); fill-after-cancel race unmodeled |
| Severity | **P2** |
| Evidence | `execution/simulator.py` (one fill per order), `paper/execution.py` cancel (PARTIALLY_FILLED → NOT_SUPPORTED internal), `paper/contracts.py` ORDER_LIFECYCLE_STATES (no REPLACE states), broker path cumulative status polls; WS05 TRD-003/004/005; WS06 UX-007 |
| Authorized capabilities affected | Trading lifecycle completeness (Tier E), order-management UX, CCN bracket semantics direction (brackets need working orders) |
| Current consequence | A partially-filled order's remainder is not re-workable; orders cannot be modified; cancel-vs-fill races are not reconciled |
| Target correction | Working-order remainder + fill aggregation (remaining_qty, avg_fill_price, multiple fills per order), replace = cancel+submit-same-client-order-id with explicit REPLACE_PENDING/REPLACED states, fill-after-cancel-detected reconciliation event |
| Dependencies | Order model (RC-004 identity for multi-asset later); internal simulator first, broker path after |
| Downstream findings collapsed | TRD-003, TRD-004, TRD-005, TD-A8, ADR-C-007, UX-007 |
| Validation | Multi-fill/remainder tests, replace lifecycle tests, late-fill cancel test, idempotency-under-replace |
| Confidence | CONFIRMED |

### RC-008 — Idempotency correct under single-process lock but not content-derived; concurrency assumption undocumented

| Field | Value |
|---|---|
| ID | RC-008 |
| Title | Idempotency keys are client-supplied (not content-derived); the lookup→record pair is atomic only under `LEDGER_ROUTE_LOCK` (single-process); a client that loses its key after a timed-out submit can create a duplicate |
| Severity | P3 (single-process local tool; documented) |
| Evidence | `ui_api/server.py` `LEDGER_ROUTE_LOCK`, `paper/ledger.py lookup_idempotent_order`, `paperOrderDraft.ts` random attempt keys; WS05 TRD-002/TD-A15 |
| Authorized capabilities affected | Trading idempotency guarantee (Tier E) |
| Current consequence | Correct today under the route lock; would race under multi-process deployment or direct-caller paths |
| Target correction | Content-derived idempotency key (intent hash) + server-issued retry token per submission attempt; per-ledger locking for multi-process readiness |
| Dependencies | RC-005 preview binding (intent hash shared) |
| Downstream findings collapsed | TRD-002, TD-A15 |
| Validation | Duplicate-submit stress tests (same intent → same order; new key after timeout → detected duplicate) |
| Confidence | CONFIRMED |

### RC-009 — Provider layer lacks capability registry/discovery; all live wires unverified; protocol-only chain providers

| Field | Value |
|---|---|
| ID | RC-009 |
| Title | Provider roles/capabilities are implied by Protocols but not a first-class registry with runtime discovery, gates, and freshness policy; no RUNTIME_VERIFIED live wire exists (G1–G6 closed, EVIDENCE-01B not operationally accepted); OptionChainProvider/FuturesChainProvider are protocol-only |
| Severity | P2 |
| Evidence | `providers/contracts.py` (Protocols), `providers/composition.py` (fixed composition, fail-closed stubs), `providers/registry.py` + `planner.py`, no `capabilities()` per adapter, no live-wire evidence; WS04 §4/§5; WS05 §9/§12; WS06 TEST-003 |
| Authorized capabilities affected | Provider-backed runtime for every lane; production readiness (MS-09); options/futures live chains (MS-12) |
| Current consequence | No lane can claim live support; the UI/planner cannot consult a single capability source; chain providers exist only as fixture adapters |
| Target correction | Provider Capability Registry (provider → roles → capabilities → env gates → freshness policy → discovery), fail-closed `UNSUPPORTED_CAPABILITY`, live-wire verification campaign (EVIDENCE-01C/G5) per provider, chain providers implemented behind the registry |
| Dependencies | RC-002/003 for IBKR L2; independent for registry shape |
| Downstream findings collapsed | TD-W3, TD-W5, MS-09, MS-12, ADR-C-009, CON-08, TEST-003 (coverage classification), D20 (elevation) |
| Validation | Capability discovery tests, per-provider recorded-wire contract tests, live-gated canaries (documented, not run in CI) |
| Confidence | HIGH_CONFIDENCE |

### RC-010 — Frontend/backend API contracts manually duplicated and error taxonomy ad-hoc

| Field | Value |
|---|---|
| ID | RC-010 |
| Title | 2,000-line manual Zod layer (`ui/src/api/schemas.ts`) duplicates backend dict envelopes with enum drift + passthrough erosion + schema-less `/explain`/`/inspect`; error responses are ad-hoc string reason-codes with no canonical taxonomy; `_send_json(default=str)` creates nullable mismatch risk; no versioning |
| Severity | P2 |
| Evidence | `ui/src/api/schemas.ts` (~70 schemas, passthrough on ProviderHealth/MarketState/OpportunityInput), `ui_api/server.py` reason codes, `_send_json(default=str)`; WS05 ARCH-007; WS06 API-004/005/006, UX-011; CON-02/03 |
| Authorized capabilities affected | API contract integrity, error UX, developer velocity on every new surface |
| Current consequence | Type drift invisible until runtime; frontend string-parses error codes; new domains will duplicate the pattern |
| Target correction | Canonical error taxonomy (12 categories per WS05) + typed frontend union; generated/shared API contracts (OpenAPI generation from backend projection builders or a typed contract package) with `schemas.test.ts` retained as interim guard; nullable/versioning rules |
| Dependencies | None upstream (can be incremental) |
| Downstream findings collapsed | ARCH-007, API-004, API-005, API-006, UX-011, TD-A10, TD-AP1, TD-UE3, CON-02, CON-03, D24, D25 |
| Validation | Contract parity tests (backend serialization ↔ frontend schemas), error-taxonomy round-trip tests, schema-drift regression |
| Confidence | CONFIRMED |

### RC-011 — Frontend workspace query keys not mode/account-scoped

| Field | Value |
|---|---|
| ID | RC-011 |
| Title | Workspace lane query keys are `["workspace", symbol, lane]` — mode is not a key dimension; mode switching relies on remount + staleTime-0 refetch; stale-mode lane payloads can be displayed briefly on switch; scrub does not invalidate lane keys |
| Severity | P2 (stale display risk; no execution crossover — backend authority is process-level) |
| Evidence | `ui/src/api/hooks.ts` (keys + refetch-interval decision), `queryKeys.test.ts` (account isolation tested; mode isolation absent); WS05 ARCH-005/SAFE-002; WS06 UX-009/UX-010; CON-04 |
| Authorized capabilities affected | Demo/Paper/Live UI state integrity (Tier E); approved mode-first product |
| Current consequence | **G14 (2026-09-09):** G14 product/selector/paper-preview query keys are mode+account+instrument scoped via `queryKeyFactory` / compact runtime keys; isolation tests added. **Remaining:** legacy workspace lane keys `["workspace", symbol, lane]` unchanged for equity parity and bundle budget — mode isolation on lanes deferred |
| Target correction | Mode-scoped (and account/provider/as-of where applicable) query-key factory with invalidation on scrub; isolation test asserting keys differ across modes/accounts |
| Dependencies | None upstream |
| Downstream findings collapsed | ARCH-005, SAFE-002, UX-009, UX-010, TD-A11, TD-UE2, CON-04, D23 |
| Validation | Query-key isolation test (mode × account × symbol × lane uniqueness), scrub-invalidation test — **G14 product keys proven**; lane keys partial |
| Confidence | CONFIRMED (partial progress) |

### RC-012 — `validate changed` under-selects in local monorepo scenarios

| Field | Value |
|---|---|
| ID | RC-012 |
| Title | `validate changed` selects no suites for (a) `projects/integrated-market-platform/`-prefixed paths, (b) `fixtures/**`/`config/**`/`tests/fixtures/**`, and (c) shared modules escalate bluntly to 5 core suites; `full_suite_required=true` does not run the full suite |
| Severity | P2 (developer-system correctness; CI unaffected because it strips the prefix — no production safety path) |
| Evidence | WS06 controlled `--explain` runs (FC-18), `tools/validate.py` (`EXECUTABLE_ROOTS={src,tools,ui,manifests}`, child-relative globs), telemetry (changed ≈74s avg), WS05 §56; TD-W9/TD-TS1/DEV-001/002 |
| Authorized capabilities affected | Canonical developer command interface truthfulness (DEVELOPER_INFRASTRUCTURE) |
| Current consequence | Local monorepo changes are silently under-validated (21 mandatory tests only); fixture edits select nothing; `full_suite_required` over-promises |
| Target correction | Normalize the `projects/integrated-market-platform/` prefix in monorepo embedding; add fixture/config/test-fixture ownership mapping; shared-module dependency map or honest flag rename (`core_checkpoint_required` + print what ran) |
| Dependencies | None upstream |
| Downstream findings collapsed | FC-18, FC-19, TD-W9, TD-TS1, DEV-001, DEV-002, D26 |
| Validation | `validate changed --explain` regression tests: prefixed src path → platform suite; fixture change → consuming suites; shared-module change → mapped dependents or explicit core checkpoint |
| Confidence | CONFIRMED |

### RC-013 — Stale donor-governance documentation pre-dates the Heller correction

| Field | Value |
|---|---|
| ID | RC-013 |
| Title | 9+ governance documents still treat GridIQ/DS-340W as legitimate donors (permissions record cites the wrong Lucas; reuse matrix cites files absent locally; ADR-GRIDIQ-001 authorization framing pre-dates the correction) |
| Severity | P2 (provenance truth; no code impact — implementation is independent and kept) |
| Evidence | `docs/superpowers/governance/2026-08-14-donor-code-permissions.json`, ADR-GRIDIQ-001, phase gate, ADR-DONOR-001, DONOR_REUSE_MATRIX, GRID_IQ_NOTES, DS340W_NOTES, revision-3 plans, PROVIDER_DUPLICATION_AUDIT, fixture inventory; WS01 findings; TD-P1; WS06 DOC-003/TD-DO1 |
| Authorized capabilities affected | Provenance/governance truth (program + professor-facing traceability) |
| Current consequence | False legitimacy record persists in governance; fresh agents/readers can mistake mistaken donors as authorized |
| Target correction | Add `SUPERSEDED`/`HISTORICAL` headers + Heller-correction context in place; preserve history; no deletion; no code change |
| Dependencies | None upstream (Wave 0) |
| Downstream findings collapsed | TD-P1, TD-DO1, DOC-003, D12, D17, TD-P2/P3 (naming annotations, same wave) |
| Validation | Grep sweep: zero governance docs treat Heller material as current-authorized; docs-link validator passes |
| Confidence | CONFIRMED |

### RC-014 — Repository/program-truth drift: SS snapshot lag, roadmap stale vs mandate, edit-tree ambiguity, handoff sprawl

| Field | Value |
|---|---|
| ID | RC-014 |
| Title | Short-squeeze snapshot manifest `78b7467` vs child `9de7b2f` vs plan `41f52bb` (three truths); MASTER_ROADMAP predates the mandate (zero new-domain mentions); fresh developers cannot tell which tree is canonical to edit; five parallel "current state" documents |
| Severity | P2 (repo truth) / P3 (docs/dev friction) |
| Evidence | `workspace-manifest.json`, child HEADs, hardening plan; WS01 TD-P5; WS06 REPO-001/DOC-005/DEV-003/DEV-005 (FC-16, MS-13, TD-RP1/TD-DO2/TD-DV1/TD-DV3) |
| Authorized capabilities affected | Repository truth, roadmap truth, developer onboarding (DEVELOPER_INFRASTRUCTURE) |
| Current consequence | Snapshot lags real child state; roadmap understates authorized scope; edit-tree ambiguity is the #1 fresh-developer friction |
| Target correction | Guarded SS snapshot refresh with evidence; MASTER_ROADMAP refresh with mandated domains; AGENTS.md canonical edit-tree statement; consolidate handoff files (keep WORK_LOG + docs authority) |
| Dependencies | None upstream (Wave 0) |
| Downstream findings collapsed | REPO-001, TD-P5, TD-RP1, DOC-005, TD-DO2, DEV-003, TD-DV1, DEV-005, CON-09, FC-16, MS-13 |
| Validation | Manifest-vs-child diff clean; roadmap grep includes all mandated domains; fresh-clone smoke test follows AGENTS.md |
| Confidence | CONFIRMED |

### RC-015 — Missing authorized domain surfaces (Bonds, Crypto, Gold, Silver, Commodities, Industry, Government workflow)

| Field | Value |
|---|---|
| ID | RC-015 |
| Title | Six mandated later domains have no user surface and no domain implementation; Government has backend macro but no workflow; these are MISSING_AUTHORIZED_SCOPE, not regressions and not defects |
| Severity | P2 (product-value gap, not safety) |
| Evidence | WS04 MS-03..08/MS-11 (zero src matches per domain, roadmap absent); WS06 §3 product-surface matrix (MISSING rows); MND-001..008 |
| Authorized capabilities affected | Bonds, Crypto, Gold, Silver, Commodities, Industry, Government (CORE_REQUIRED domains) |
| Current consequence | Authorized scope is ~50% complete; the product reads as equity-only from the UI |
| Target correction | Structural integration per domain: canonical identity (RC-004) → provider path (RC-009) → research/workspace surface → portfolio compatibility (RC-001) → risk compatibility → tests → truthful status. Not every advanced strategy; structural completion line defined in 18 |
| Dependencies | RC-004 (identity) first; RC-001 (portfolio) for portfolio compatibility; RC-009 for providers |
| Downstream findings collapsed | MS-03..08, MS-11, TD-W4, TD-W8, TD-UE1, D14 (details-to-be-defined), D20 (whale elevation), D22 (market-context lane) |
| Validation | Per-domain acceptance: identity tests pass, workspace surface renders truthfully, portfolio compatibility test, domain tests pass, status COMPLETE_VERIFIED_FOR_RESEARCH or explicit PARTIAL |
| Confidence | CONFIRMED (absence) |

### RC-016 — Critical test gaps: no real E2E, missing safety-regression cases, missing provider contracts

| Field | Value |
|---|---|
| ID | RC-016 |
| Title | No browser/process-level E2E (438 UI tests are component-level; backend routes covered by ui1/ui2 API suites); missing tests for preview binding, query-key isolation, depth engine, IBKR entitlement/reconnect, replace, multi-fill remainders, late-fill cancel, multi-asset identity/portfolio, BP enforcement |
| Severity | P2 |
| Evidence | WS06 TEST-001/TEST-002/TEST-004 (§18a); WS05 §55 critical-safety test register; TD-TS2 |
| Authorized capabilities affected | Every safety/trading invariant's regression protection |
| Current consequence | Key architecture corrections (RC-005/006/007/003) would land without regression gates; no E2E proves the primary Paper workflow end-to-end |
| Target correction | E2E strategy decision (Playwright for the Paper workflow: launch → mode → research → draft → preview → submit → monitor → portfolio); per-ADR regression suites defined in 06 §61; manifest `e2e` classification |
| Dependencies | Parallel to Wave 0–2; E2E meaningful after RC-005 lands |
| Downstream findings collapsed | TEST-001, TEST-002 (gaps), TEST-004, TD-TS2, 06 §55 register |
| Validation | E2E suite passes; safety-register suites added per 06 §67 and 12 backlog |
| Confidence | CONFIRMED |

### RC-017 — Full validation is materially slow (451s)

| Field | Value |
|---|---|
| ID | RC-017 |
| Title | FULL validation ≈ 451s dominated by serial GLOBAL_STATE_MUTATION suites (platform 106s, ui1 79s) + RESOURCE_HEAVY fixture loads (donor_bridge 83.5s, integration 50s, providers 39s) |
| Severity | P3 (optimization; no coverage reduction permitted) |
| Evidence | `.local/ws04-full.json` per-suite parse (WS06 PERF-001), telemetry (domain 22 runs/2463s); TD-TS3 |
| Authorized capabilities affected | Developer feedback loop (DEVELOPER_INFRASTRUCTURE) |
| Current consequence | Agents/developers avoid `validate changed` and run expensive domain/full runs; slow closure |
| Target correction | Split platform/ui1 by concern, raise heavy-worker count on resource-safe runners, cache immutable preparation, improve affected selection (after RC-012) — only where evidence supports |
| Dependencies | RC-012 (selection correctness) first; no coverage reduction |
| Downstream findings collapsed | PERF-001, TD-TS3, DEV-001/002 (partial) |
| Validation | Re-measured FULL time with equal-or-higher test count; per-suite breakdown |
| Confidence | HIGH_CONFIDENCE (measurement); MODERATE (fix effectiveness) |

### RC-018 — Dead/duplicate API surface, src→tools inversion, unbounded CORS, Mongo optionality

| Field | Value |
|---|---|
| ID | RC-018 |
| Title | `/paper/{account,positions,fills,risk,orders-GET}`, `/workspace/:symbol/market-context` route, `/capabilities` have no frontend callers; `src/ui_api` imports `tools.platform.control_service`; `Access-Control-Allow-Origin: *`; pymongo repositories duplicate canonical SQLite persistence |
| Severity | P3 |
| Evidence | WS06 §15 (DEL-01..07 candidates), API-001/002, DEP-001, TD-AP2/TD-AP3/TD-RP2/TD-DP1, D21/D22/D29 |
| Authorized capabilities affected | API maintainability, security posture, dependency footprint |
| Current consequence | Surface area larger than used; coupling to tooling layer; unbounded CORS on loopback; optional Mongo install cost |
| Target correction | Verify test coverage then archive/deprecate dead routes (wire market-context as a real lane — backend engines are real value — per D22); move control service under `src` or invert; tighten CORS to loopback; mark Mongo optional/isolated |
| Dependencies | RC-010 for contract work; independent otherwise |
| Downstream findings collapsed | DEL-01..07 (as dispositions), API-001/002, DEP-001, TD-AP2, TD-AP3, TD-DP1, TD-RP2 (CI copies), D21/D22/D29 |
| Validation | Caller-grep + test-coverage evidence per route before change; CORS header test; Mongo isolation test |
| Confidence | CONFIRMED |

### RC-019 — Repository hygiene: empty pytest dirs, stale child CI copies, donor-tree remnants

| Field | Value |
|---|---|
| ID | RC-019 |
| Title | Empty `pytest-equity-*` dirs at parent root; child-repo `.github/workflows/*.yml` STALE copies of canonical parent CI; large donor remnant trees (read-only by policy) |
| Severity | P3 |
| Evidence | WS06 REPO-002/REPO-003/REPO-004; DEL-03/DEL-04 |
| Authorized capabilities affected | Repository clarity (DEVELOPER_INFRASTRUCTURE) |
| Current consequence | Confusing artifact dirs; duplicated CI files that could be mistaken as canonical |
| Target correction | Remove empty artifact dirs (evidence: zero files); replace stale child CI copies with a pointer to parent CI or delete (parent verified canonical); donor trees stay read-only per policy (KEEP_LOCAL_ONLY) |
| Dependencies | None (Wave 8 cleanup) |
| Downstream findings collapsed | REPO-002, REPO-003, REPO-004, DEL-03, DEL-04 |
| Validation | `find` census (0 files before delete); CI still canonical at parent; docs pointer present |
| Confidence | CONFIRMED |

### RC-020 — Documentation ownership sprawl: ADR triplication, rules duplication, evidence-homes ambiguity

| Field | Value |
|---|---|
| ID | RC-020 |
| Title | ADRs live in three homes (`docs/architecture/*.md`, `docs/superpowers/decisions/*.json`, `docs/research/donors/*`); rules repeat across AGENTS/.cursor/handbook/SOPs; three evidence homes (`cross_lane`/`intelligence`/`participant`) lack documented ownership boundaries; `donor_patterns/` name implies donor code |
| Severity | P3 |
| Evidence | WS06 DOC-004/DEV-006; WS05 ARCH-010; TD-DV3; TD-P2/P3; CON-06/07 |
| Authorized capabilities affected | Maintainability, onboarding (DEVELOPER_INFRASTRUCTURE) |
| Current consequence | Wasteful context duplication; ambiguous ownership for evidence and ADR records; misleading package name |
| Target correction | `docs/architecture/` markdown = canonical ADR owner, superpowers JSON = machine-readable mirrors; AGENTS.md = router, rules point not duplicate; evidence-homes ownership documented; `donor_patterns/` namespace annotation (rename deferred, zero behavior change) |
| Dependencies | None (Wave 0/8) |
| Downstream findings collapsed | DOC-004, DEV-006, ARCH-010, TD-DV3, TD-P2, TD-P3, CON-06, CON-07 |
| Validation | Single-owner grep per concept; docs-link validator; ADR index test |
| Confidence | HIGH_CONFIDENCE |

---

## Reconciliation notes

- Every P1 architecture blocker (AB-001..003) maps to exactly one root cause:
  AB-001 → RC-001, AB-002 → RC-002, AB-003 → RC-003.
- Every WS05 finding (ARCH-001..011, SAFE-001..004, TRD-001..009, MA-001..006)
  appears under exactly one RC (downstream column). No finding is orphaned.
- Every WS06 finding (UX-*, API-*, TEST-*, DEV-*, DOC-*, DEP-*, REPO-*,
  PERF-*, OPS-*) appears under exactly one RC.
- Missing mandated domains (MS-03..08, MS-11) are RC-015 (MISSING scope), never
  "regression".
- Live execution absence (MS-15/LIVE-001) is a designed safety boundary, not a
  root cause.
- 20 root causes, 0 duplicate ownerships; the master backlog (12) implements
  these with dependency-aware waves (13).