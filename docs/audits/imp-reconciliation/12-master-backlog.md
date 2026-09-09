# 12 — Master Backlog

Status: **COMPLETE (WS07, 2026-09-07)**. Canonical implementation backlog for
the IMP reconciliation program. Every item: owned by exactly one root cause
(16), belongs to exactly one recovery wave (13), has non-placeholder
acceptance criteria, and carries all required fields. Registers: FIX ·
CONSOLIDATE · MIGRATE · REPLACE_BOUNDED · ADD · TEST · DOCUMENT · CLEANUP ·
HARDEN. Priorities: P0 destructive/safety · P1 core blocker/severe
correctness/architecture · P2 major · P3 optimization/usability/debt · P4
polish. Complexity: XS/S/M/L/XL. Parallelization: PARALLEL_SAFE /
PARALLEL_AFTER_DEPENDENCY / SERIAL.

Baseline for all "Current State": WS04 fresh validation (3580 tests / 48
skipped / 1 excluded environmental / 0 errors), UI 438, typecheck clean;
WS05/WS06 findings as cited. Nothing in this backlog is implemented by WS07.

### G13 closure status (2026-09-09; append-only)

| Concept | ID / location | Status |
|---|---|---|
| OPTIONS_PAPER_E2E | 14k matrix | **COMPLETE** |
| FUTURES_PAPER_E2E | 14k matrix | **COMPLETE_WITH_EXPLICIT_MARGIN_FACT_REQUIREMENT** |
| FUTURES_MARGIN_INFRASTRUCTURE | `risk/margin_facts.py` + `paper/margin_resolution.py` | **COMPLETE** |
| BROKER_MARGIN_MODEL | — | **NOT_GLOBALLY_AVAILABLE / EXPLICIT_FACTS_REQUIRED** |
| LEGACY_OPTIONS_LEDGER | `portfolio/options_ledger.py` | **DEPRECATED_NON_AUTHORITATIVE** (O9 lane) |
| GOVERNED_FX | G4 financial gate | **COMPLETE_ENOUGH_FOR_FAIL_CLOSED_DERIVATIVE_SETTLEMENT** |
| CRYPTO_PAPER_READINESS | — | **AUDITED_SECONDARY** (unchanged) |
| WAVE_7_SELECTOR_READINESS | BL-0704 dependency | **READY** (G13 closure; Wave 7 not started) |

Validation at closure: FULL **4380/48/0/0** (+25 G13 tests in `tests/trading_correctness/test_g13_paper_derivatives.py`).

### G14 closure status (2026-09-09; append-only)

| Concept | ID / location | Status |
|---|---|---|
| UNIFIED_INSTRUMENT_SELECTOR | `ui_api/instrument_selector.py` + `CanonicalInstrumentSelector.tsx` | **COMPLETE** — `/instruments/search`; selector on Options/Futures modules + `InstrumentSelectionEmpty` |
| ROUTE_CODEC | `instrument_route_codec.py` + `instrumentIdentity.ts` | **COMPLETE** — encode/decode round-trip |
| OPTIONS_PRODUCT_SURFACE | `/workspace/:id/options-product` + `OptionsProductSurface.tsx` | **COMPLETE (Paper)** — G12 runtime + G13 portfolio; inline Paper preview |
| FUTURES_PRODUCT_SURFACE | `/workspace/:id/futures-product` + `FuturesProductSurface.tsx` | **COMPLETE (Paper w/ margin facts)** — family/continuous non-actionable |
| QUERY_KEY_FACTORY | `queryKeyFactory.ts` + `canonicalQueryKey.ts` | **COMPLETE for G14 product/selector keys** — workspace lane keys legacy (equity parity) |
| LEGACY_WHALE_LANES | `/workspace/:symbol/options|futures` | **COMPATIBILITY retained** |
| LIVE_EXECUTION | — | **NOT_ENABLED** |

Validation at G14 closure pass: backend G14 **11/11**; CHANGED **3856/48/0/0**; FULL **4391/48/0/0**; UI typecheck pass; build **202.91 KiB gzip**.

---

## WAVE 0 — Truth / Safety / Planning Corrections

### BL-0001 Donor-governance supersession (RC-013)
- Priority: **P2** · Type: PROVENANCE/DOCUMENTATION · Complexity: S · Parallelization: PARALLEL_SAFE
- Authorized requirements: Professor correction LATER-012 (Heller = mistaken donor); program truth
- Evidence: TD-P1, DOC-003, D12/D17, 03 §documentation corrections (12 docs enumerated)
- Current state: 9+ governance docs treat GridIQ/DS-340W as legitimate; permissions record cites wrong Lucas; reuse matrix cites absent files
- Target state: every enumerated doc carries SUPERSEDED/HISTORICAL header + correction context; history preserved; zero deletion
- Affected files: `docs/superpowers/{governance,decisions,plans}/*`, `docs/research/donors/*`, `docs/engineering/{PROVIDER_DUPLICATION_AUDIT,WORK_LOG}.md`, fixture inventory (list in 17 §4)
- Dependencies: none
- Strategy: in-place header annotations + pointer to 01/03/16; no rewrites of authority pages (already honest)
- Safety risk: none · Regression risk: low (docs only)
- Tests required: docs-link validator; grep sweep (no Heller-treated-as-authorized)
- Runtime validation: n/a · Documentation required: the annotations themselves
- Acceptance criteria: 12/12 enumerated docs annotated; `check_docs_links.py` passes; grep confirms zero governance docs treat Heller as current-authorized
- Wave: 0

### BL-0002 `validate changed` — monorepo prefix normalization (RC-012)
- Priority: **P2** · Type: DEV_TOOLING/TESTING · Complexity: S · Parallelization: SERIAL (foundation for BL-0003/0004)
- Authorized requirements: canonical developer command truthfulness (DEVELOPER_INFRASTRUCTURE)
- Evidence: FC-18, TD-W9, TD-TS1, WS06 §17 (proven in 3 ways), `tools/validate.py` (EXECUTABLE_ROOTS)
- Current state: `projects/integrated-market-platform/...` paths match no suite globs → 21 mandatory tests only locally; CI unaffected (strips prefix)
- Target state: changed-path selection works identically from the monorepo snapshot and the child repo; prefixed paths normalized before matching
- Affected files: `projects/integrated-market-platform/tools/validate.py`, `tools/validate.py` tests, CI workflows (verify)
- Dependencies: none
- Strategy: strip/translate the `projects/integrated-market-platform/` prefix at selection time (single normalize hook); add `--explain` regression tests
- Safety risk: none (CI unaffected) · Regression risk: medium (selection change); mitigate with explain-tests
- Tests required: `validate changed --explain` prefixed-src → platform suite; prefixed tests → owning suite; full selection parity child-vs-snapshot
- Runtime validation: run `validate changed` from snapshot root on a real change
- Documentation required: WORK_LOG + AGENTS.md note (monorepo layout supported)
- Acceptance criteria: prefixed `src/market_platform_foundation/paper/execution.py` selects the platform suite (not 0); prefixed `tests/platform/test_*.py` selects platform; full parity with child-repo selection
- Wave: 0

### BL-0003 `validate changed` — fixture/config/test-fixture ownership (RC-012)
- Priority: **P2** · Type: DEV_TOOLING/TESTING · Complexity: M · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0002)
- Authorized requirements: same
- Evidence: FC-18 (modes b/c), TD-TS1, WS06 §17
- Current state: `fixtures/**`, `config/**`, `tests/fixtures/**` select zero suites
- Target state: fixture/config changes map to consuming suites (ownership map) or escalate to a defined core checkpoint
- Affected files: `tools/validate.py`, `tools/validation_manifest.json` (add fixture ownership metadata), manifest tests
- Dependencies: BL-0002
- Strategy: add a fixture-ownership registry (fixture path → consuming suites) built from manifest `source_globs`/`test_globs` + a curated fixtures map; unmatched fixture → core checkpoint
- Safety risk: none · Regression risk: medium (fixture edits now trigger more tests — intended)
- Tests required: fixture-edit → owning suites; config-edit → owning suites; unknown fixture → checkpoint
- Runtime validation: `validate changed` with a real fixture edit
- Documentation required: manifest format note
- Acceptance criteria: editing `tests/fixtures/providers/order_flow/admitted_cvd_nvda.json` selects order-flow suites; editing `config/modes.yaml` selects mode-affected suites
- Wave: 0

### BL-0004 `full_suite_required` honest rename + shared-module map (RC-012)
- Priority: P3 · Type: DEV_TOOLING · Complexity: S · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0002)
- Authorized requirements: same as BL-0002
- Evidence: FC-19 (misleading label), TD-TS1(c), WS06 §17.3 (shared modules in 0 suite globs)
- Current state: `full_suite_required=true` runs 5 core suites + mandatory (not the 451s full); name over-promises; shared-module edits escalate bluntly
- Target state: flag renamed `core_checkpoint_required`; output prints exactly which suites ran; shared modules map to true dependents where practical
- Affected files: `tools/validate.py`, `tools/imp.py`, manifest, CI output consumers
- Dependencies: BL-0002
- Strategy: rename field/flag with deprecation alias; print suite list; add shared-module dependency map for the 7 identified shared modules
- Safety risk: none · Regression risk: low (output-only + naming)
- Tests required: flag-rename assertion; shared-module `numeric.py` change → mapped dependents or explicit checkpoint message
- Runtime validation: run changed with shared-module edit; verify printed suites
- Documentation required: AGENTS.md command reference
- Acceptance criteria: `validate changed` with `src/.../numeric.py` prints "core checkpoint" listing exactly the suites that ran; no consumer references the old flag name
- Wave: 0

### BL-0005 Short-squeeze snapshot refresh (RC-014)
- Priority: **P2** · Type: REPOSITORY · Complexity: M · Parallelization: PARALLEL_SAFE
- Authorized requirements: original project scope (ORG-001, LATER-013); repo truth
- Evidence: REPO-001, TD-P5/TD-RP1, D10 (three truths: manifest `78b7467` vs child `9de7b2f` vs plan `41f52bb`)
- Current state: snapshot lags child by 316 files; manifest not updated
- Target state: snapshot == child HEAD `fix/frozen-followups` @ `9de7b2f` (reconciled with plan `41f52bb` evidence); manifest updated; guarded import documented
- Affected files: `projects/short-squeeze-project/`, `workspace-manifest.json`
- Dependencies: none
- Strategy: guarded snapshot refresh (import child state with manifest record; no blind copy); verify diff clean after
- Safety risk: none (read-only research tree) · Regression risk: medium (316-file diff); verify child is clean + CI unaffected
- Tests required: manifest-vs-child parity test; snapshot CI still passes
- Runtime validation: diff -rq snapshot vs child (clean)
- Documentation required: workspace-manifest update + WORK_LOG
- Acceptance criteria: snapshot identical to child (modulo caches); manifest records the new commit; parent CI passes
- Wave: 0

### BL-0006 MASTER_ROADMAP / PROGRAM_STATUS mandate refresh (RC-014)
- Priority: P3 · Type: DOCUMENTATION · Complexity: S · Parallelization: PARALLEL_SAFE
- Authorized requirements: MND-001..008 (mandated domains)
- Evidence: DOC-005, FC-16, MS-13, TD-DO2 (zero new-domain mentions)
- Current state: roadmap predates the mandate; new domains absent
- Target state: roadmap + program status list all authorized domains and reference the master backlog (12) + waves (13)
- Affected files: `projects/integrated-market-platform/docs/platform/MASTER_ROADMAP.md`, `PROGRAM_STATUS.md`
- Dependencies: none
- Strategy: rewrite roadmap section to the authorized domain set; link backlog
- Safety risk: none · Regression risk: low
- Tests required: docs-link validator; grep roadmap for mandated domains
- Runtime validation: n/a
- Documentation required: the refresh
- Acceptance criteria: grep confirms Bonds/Crypto/Gold/Silver/Commodities/Whale/Industry/Government present in roadmap; links valid
- Wave: 0

### BL-0007 AGENTS.md canonical edit-tree statement (RC-014)
- Priority: P3 · Type: DEV_TOOLING/DOCUMENTATION · Complexity: XS · Parallelization: PARALLEL_SAFE
- Authorized requirements: developer infrastructure truthfulness
- Evidence: DEV-003, TD-DV1 (top fresh-developer friction: which tree is canonical)
- Current state: no statement resolves snapshot-vs-child-vs-worktree ambiguity
- Target state: AGENTS.md states: canonical edit target = `projects/integrated-market-platform/` (tracked snapshot); child repo mirrors it; `validate changed` supported from both after BL-0002
- Affected files: `projects/integrated-market-platform/AGENTS.md`
- Dependencies: BL-0002 (so the statement is true)
- Strategy: one paragraph + tree diagram
- Safety risk: none · Regression risk: none
- Tests required: none (docs)
- Runtime validation: fresh-clone smoke per the statement
- Documentation required: the statement
- Acceptance criteria: a fresh developer can determine the edit target without tribal knowledge
- Wave: 0

### BL-0008 `imp.py env` exit-code policy (RC-014)
- Priority: P3 · Type: DEV_TOOLING · Complexity: XS · Parallelization: PARALLEL_SAFE
- Authorized requirements: developer command truthfulness
- Evidence: DEV-004, TD-DV2, D28 (always exits 0)
- Current state: `imp.py env` informational-only
- Target state: non-zero exit on hard-prereq failure (wrong Python version; missing npm when UI work planned); optional providers remain informational
- Affected files: `projects/integrated-market-platform/tools/imp.py` (+ tests)
- Dependencies: none
- Strategy: add exit codes for hard prereqs; keep `--informational` flag
- Safety risk: none · Regression risk: low (scripts that ignored exit code unaffected)
- Tests required: env-fail exit code tests
- Runtime validation: run `imp.py env` with wrong python (expected non-zero)
- Documentation required: AGENTS.md env section
- Acceptance criteria: `imp.py env` returns non-zero on 3.10/system python; zero on correct venv
- Wave: 0

### BL-0009 Handoff-file consolidation + rules de-duplication (RC-020)
- Priority: P3 · Type: DOCUMENTATION/DEV_TOOLING · Complexity: S · Parallelization: PARALLEL_SAFE
- Authorized requirements: developer infrastructure clarity
- Evidence: DEV-005/DEV-006, TD-DV3, CON-09 (five current-state docs; rules repeated)
- Current state: task_plan/progress/findings at root + WORK_LOG + PROGRAM_STATUS + docs authority overlap; rules repeat across AGENTS/.cursor/handbook/SOPs
- Target state: WORK_LOG + docs authority = canonical current-state; planning scratch demoted; AGENTS.md = router; rules point not duplicate
- Affected files: `projects/integrated-market-platform/` root handoffs, AGENTS.md, `.cursor/rules`
- Dependencies: BL-0007
- Strategy: demote scratch (archive, not delete); prune duplicated rule text to pointers
- Safety risk: none · Regression risk: low
- Tests required: docs-link validator
- Runtime validation: n/a
- Documentation required: consolidation itself
- Acceptance criteria: exactly one "current state" authority (WORK_LOG + docs authority map); no rule text duplicated verbatim across layers
- Wave: 0

### BL-0010 ADR canonical home (RC-020)
- Priority: P3 · Type: DOCUMENTATION · Complexity: S · Parallelization: PARALLEL_SAFE
- Authorized requirements: documentation ownership
- Evidence: DOC-004, TD-DV3, CON-07, D27 (three ADR homes)
- Current state: `docs/architecture/*.md` + `docs/superpowers/decisions/*.json` + `docs/research/donors/*`
- Target state: `docs/architecture/` markdown canonical; superpowers JSON = machine-readable mirrors; new ADRs (incl. ADR-C-001..010) land in canonical home
- Affected files: docs/architecture + superpowers/decisions
- Dependencies: none
- Strategy: declare owner in docs authority map; migrate key existing ADRs; add index
- Safety risk: none · Regression risk: low
- Tests required: ADR index test; docs-link validator
- Runtime validation: n/a
- Documentation required: authority map update
- Acceptance criteria: every new ADR (WS08+ implementation ADRs) exists in `docs/architecture/`; JSON mirrors reference canonical
- Wave: 0

### BL-0011 `donor_patterns/` namespace annotation + gridiq test annotation (RC-020)
- Priority: P3 · Type: PROVENANCE/DOCUMENTATION · Complexity: XS · Parallelization: PARALLEL_SAFE
- Authorized requirements: provenance truth
- Evidence: TD-P2/TD-P3, D18 (namespace implies donor code; contents are independent)
- Current state: `donor_patterns/` package name + `tests/gridiq/test_required_future_tests.py` docstring reference donors
- Target state: namespace docstring states "independent IMP lane formulas (concept-derived, reimplemented, no donor code)"; gridiq test annotated as conformance harness; rename deferred (zero behavior change)
- Affected files: `donor_patterns/__init__.py`, `tests/gridiq/test_required_future_tests.py` head
- Dependencies: none
- Strategy: annotation only; no renames in Wave 0
- Safety risk: none · Regression risk: none
- Tests required: none (docstring-only)
- Runtime validation: n/a
- Documentation required: annotation
- Acceptance criteria: no IMP docstring implies donor code ownership of `donor_patterns/`
- Wave: 0

### BL-0012 Evidence-homes ownership documentation (RC-020)
- Priority: P3 · Type: DOCUMENTATION · Complexity: XS · Parallelization: PARALLEL_SAFE
- Authorized requirements: architecture ownership clarity
- Evidence: ARCH-010, CON-06 (three evidence homes, coherent chain, undocumented boundaries)
- Current state: `cross_lane/evidence.py` + `participant/evidence.py` + `intelligence/contracts/evidence.py`
- Target state: documented ownership: NormalizedLaneEvidence = canonical normalization; participant families = specialist input; EvidenceV1 = specialist contract; raw provider payload ≠ canonical observation (boundary preserved)
- Affected files: `docs/architecture/` ownership note + module docstrings
- Dependencies: none
- Strategy: documentation + docstring headers
- Safety risk: none · Regression risk: none
- Tests required: none
- Runtime validation: n/a
- Documentation required: ownership model
- Acceptance criteria: a reader can name the canonical evidence contract and the two specialist homes without ambiguity
- Wave: 0

---

## WAVE 1 — Canonical Domain Foundation

### BL-0101 One asset-class vocabulary (RC-004)
- **Status: CLOSED_BY_G1 (2026-09-07)** — `XaAssetClass` extended with `CRYPTO`/`BOND`; `paper.contracts.ASSET_CLASSES` deprecated as backward-compat view; vocabulary-parity tests in `tests/xa01/test_xa01_g1_serialization.py` + collision tests; evidence in 15 (G1 section). Remaining shim removal is cleanup after all consumers migrate (not a blocker).
- Priority: **P2** · Type: DOMAIN_MODEL/MULTI_ASSET · Complexity: M · Parallelization: SERIAL (foundation for Wave 1)
- Authorized requirements: multi-asset identity (Tier E; MND-001..008)
- Evidence: ARCH-004, TD-A4, CON-01, ADR-C-004, MA-001 (CRYPTO present in one vocabulary only)
- Current state: `paper/contracts.ASSET_CLASSES` (incl. CRYPTO/PREDICTION_MARKET) vs `xa01.enums.XaAssetClass` (no CRYPTO)
- Target state: one canonical vocabulary in XA-01; paper layer resolves through it; compat shim until consumers migrate
- Affected files: `xa01/enums.py`, `xa01/contracts.py`, `paper/contracts.py`, `paper/*`, `execution/*`, consumers of `build_instrument_ref`
- Dependencies: none
- Strategy: extend XA-01 → deprecate paper tuple → migrate call sites → remove shim
- Safety risk: low (identity change) · Regression risk: high (every paper/execution path); mitigate with parity tests
- Tests required: identity resolution tests per class/kind; vocabulary-parity test; full equity-path regression
- Runtime validation: full validation at closure
- Documentation required: identity model doc
- Acceptance criteria: `paper ASSET_CLASSES` removed (or pure re-export); no runtime path constructs asset-class outside XA-01
- Wave: 1

### BL-0102 XA-01 CRYPTO class + pair/venue identity (RC-004)
- **Status: CLOSED_BY_G1 (2026-09-07)** — `XaAssetClass.CRYPTO` + `InstrumentKind.CRYPTO_PAIR` + `register_crypto_pair` (base/quote/venue/network, spot product type, provider aliases); `tests/xa01/test_xa01_crypto_identity.py`; evidence in 15 (G1 section).
- Priority: **P2** · Type: DOMAIN_MODEL/MULTI_ASSET · Complexity: M · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0101)
- Authorized requirements: Crypto domain identity (MND-002)
- Evidence: MA-001, AB-004, TD-A13, ADR-C-010 (no CRYPTO class/kind; no venue/chain/pair)
- Current state: `LaneId.CRYPTO` + paper ASSET_CLASSES have CRYPTO; XA-01 does not; no pair/venue/network identity
- Target state: `XaAssetClass.CRYPTO` + `InstrumentKind.CRYPTO_PAIR` + CryptoPair identity (base/quote/venue/network, spot|derivative)
- Affected files: `xa01/enums.py`, `xa01/contracts.py`, `xa01/registry.py`, tests
- Dependencies: BL-0101
- Strategy: additive enum/contract extension; no providers yet
- Safety risk: none · Regression risk: low (additive)
- Tests required: crypto identity resolution tests (BTC-USD pair, venue, spot/derivative)
- Runtime validation: xa01 suite
- Documentation required: identity model
- Acceptance criteria: `BTC-USD@venue` resolves as CRYPTO pair with base/quote; distinct from equity ticker identity
- Wave: 1

### BL-0103 Bond descriptor typing + corporate identity (RC-004)
- **Status: CLOSED_BY_G1 (2026-09-07)** — `XaAssetClass.BOND` + `InstrumentKind.BOND` + `register_bond` (issuer, CUSIP/ISIN alias, maturity, coupon, par, credit tier); corporate + sovereign both representable; `tests/xa01/test_xa01_bond_identity.py`; evidence in 15 (G1 section).
- Priority: **P2** · Type: DOMAIN_MODEL/MULTI_ASSET · Complexity: M · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0101)
- Authorized requirements: Bonds domain identity (MND-001)
- Evidence: MA-002, TD-A13, ADR-C-010 (flat strings; no corporate; no yield-price in portfolio)
- Current state: `SOVEREIGN_DEBT` with flat optional strings; no corporate bond identity; `PriceUnitKind.YIELD_RATE` exists
- Target state: typed BondInstrument (issuer, CUSIP/ISIN alias, maturity, coupon, par, currency, credit tier); corporate class; yield-price unit wired
- Affected files: `xa01/contracts.py`, `xa01/enums.py`, XA-02 reuse (`fred/*`, `xa02/*`)
- Dependencies: BL-0101
- Strategy: additive typed contract; keep FRED vertical as rates foundation
- Safety risk: none · Regression risk: low
- Tests required: bond identity resolution (UST 10Y, corporate, CUSIP alias); yield-unit tests
- Runtime validation: xa01/xa02 suites
- Documentation required: identity model
- Acceptance criteria: a 10Y Treasury and a corporate bond both resolve typed identities with maturity/coupon/par/currency
- Wave: 1

### BL-0104 Gold/Silver/commodity contract identity (RC-004)
- **Status: CLOSED_BY_G1 (2026-09-07)** — economic commodity + `COMMODITY_SPOT` + `register_commodity_proxy` (GLD) + futures-contract relationships (UNDERLYING/CONTRACT_ROOT/BENCHMARK_OF) + `commodity_sector`; `tests/xa01/test_xa01_commodity_identity.py`; evidence in 15 (G1 section).
- Priority: P3 · Type: DOMAIN_MODEL/MULTI_ASSET · Complexity: S · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0101)
- Authorized requirements: Gold/Silver/Commodities (MND-006/007/008)
- Evidence: MA-004, TD-A13 (generic COMMODITY only; GC/SI keys in xa03/eia)
- Current state: gold/silver only as COMMODITY; spot/futures/ETF proxy identity absent
- Target state: commodity contract identity via futures model + relationships (UNDERLYING/CONTRACT_ROOT/BENCHMARK_OF); spot/reference instruments typed
- Affected files: `xa01/*`, `contracts/futures.py` (reuse), `xa03/catalog.py`, `eia/cross_asset.py`
- Dependencies: BL-0101
- Strategy: relationship-based identity; no new stacks
- Safety risk: none · Regression risk: low
- Tests required: GC-future/GLD-proxy/spot-gold identity resolution
- Runtime validation: xa01/xa03 suites
- Documentation required: identity model
- Acceptance criteria: gold expressible as spot, GC future, and GLD proxy with explicit relationships; same for silver
- Wave: 1

### BL-0105 Canonical multi-asset portfolio model (RC-001)
- **Status: COMPLETE_BY_G2 (2026-09-07)** — one canonical account/mode-scoped, instrument-keyed portfolio model (`portfolio/canonical.py`) with per-currency Decimal cash, `ValuationMark` contract (currency + provenance + fresh/stale/missing), asset-aware valuation (equity qty×mark; options contracts×premium×multiplier; futures notional + mark-to-market P&L, never equity-style cash value; crypto base-units × pair price; bonds face × explicit price basis), explicit FX boundary (no 1:1 fallback; COMPLETE/PARTIAL/MISSING_FX/STALE), deterministic serialization, controlled mutation boundary, XA-01-tradability admission (reference identities rejected), provider snapshot normalization with `UNRESOLVED_INSTRUMENT` fail-closed, and Paper equity parity via a dual-run read-side adapter. 109 new tests in `tests/portfolio/`; FAST 21 passed; FULL clean apart from the known pre-existing cross_lane golden. Remaining follow-ons kept explicit: options-ledger merge (BL-0106), futures Decimal conversion (BL-0107), and migration of `paper_projections`/frontend consumers to the canonical model (conservative, not part of G2). Evidence in 15 (G2 section).
- Priority: **P1** · Type: MULTI_ASSET/PORTFOLIO · Complexity: XL · Parallelization: SERIAL (Wave 1 core)
- Authorized requirements: cross-asset portfolio (MND-001..008; Tier E)
- Evidence: ARCH-002, MA-006, AB-001, P1-2, MS-02, TD-W2/TD-A2, ADR-C-001
- Current state: single-instrument share-denominated ledger; no multiplier/notional/margin; no cross-asset exposure/P&L; USD-only
- Target state: portfolio keyed by instrument identity; denomination-aware valuation (price × qty × multiplier); per-currency cash + explicit FX boundary; notional gross/net; realized/unrealized P&L computed once; attribution parity retained
- Affected files: `portfolio/ledger.py`, `paper/ledger.py`, `portfolio/options_ledger.py` (merge), `paper_projections`, `risk/decision.py` inputs, `ui/src/components/portfolio/*`
- Dependencies: BL-0101..0104 (identity); BL-0106 (ledger merge)
- Strategy: introduce canonical position model alongside (dual-run) → migrate paper paths → verify parity vs equity baseline → remove compat
- Safety risk: HIGH (portfolio is authoritative truth) · Regression risk: HIGH; mitigate with parity goldens (equity behavior preserved)
- Tests required: portfolio parity (equity), cross-asset valuation goldens (option premium×multiplier, futures notional, bond par), per-currency cash, FX boundary, realized/unrealized P&L goldens
- Runtime validation: paper workflow end-to-end + full validation at closure
- Documentation required: portfolio architecture section
- Acceptance criteria: existing equity Paper behavior bit-identical; options/futures/bond positions expressible with correct notional/P&L; attribution parity invariant holds; FULL clean
- Wave: 1

### BL-0106 Options ledger merge into canonical ledger (RC-001)
- Priority: **P2** · Type: MULTI_ASSET/PORTFOLIO · Complexity: L · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0105)
- Authorized requirements: options portfolio (LATER-004)
- Evidence: MA-003, TD-A7, CON-05 (float options ledger vs int-minor equity ledger)
- Current state: `portfolio/options_ledger.py` float, separate position key
- Target state: options legs in canonical ledger with Decimal/minor-units; option contract identity + multiplier; float removed
- Affected files: `portfolio/options_ledger.py`, `portfolio/ledger.py`, options execution/strategy consumers
- Dependencies: BL-0105
- Strategy: conversion adapter → dual-write → single ledger → remove float path
- Safety risk: medium (numeric conversion) · Regression risk: high (options tests); mitigate with conversion goldens
- Tests required: numeric-conversion goldens (premium×multiplier), options-ledger parity vs old float values, options execution regression
- Runtime validation: options domain suite
- Documentation required: numeric policy
- Acceptance criteria: options positions/P&L identical (within documented rounding) after merge; no float cash in canonical ledger
- Wave: 1

### BL-0107 Futures roll/variation-margin/spread P&L → Decimal (RC-001)
- Priority: **P2** · Type: NUMERIC_CORRECTNESS · Complexity: M · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0105)
- Authorized requirements: futures correctness (LATER-003/008)
- Evidence: ARCH-008, TRD-007, TD-A7, ADR-C-008 (float `round(...,6)`)
- Current state: `simulate_futures_roll`/`variation_margin_change`/`calendar_spread_pnl` float
- Target state: Decimal/minor-units with golden numerics
- Affected files: `execution/simulator.py`, futures tests
- Dependencies: BL-0105 (numeric base)
- Strategy: Decimal conversion + goldens; no behavior change beyond precision
- Safety risk: low · Regression risk: medium; goldens catch
- Tests required: futures numeric goldens (roll, VM, spread)
- Runtime validation: futures domain suite
- Documentation required: numeric policy
- Acceptance criteria: futures P&L paths use Decimal; goldens pass; no float rounding in money paths
- Wave: 1

### BL-0108 USD-only documentation + FX boundary (RC-001)
- Priority: P3 · Type: DOMAIN_MODEL · Complexity: XS · Parallelization: PARALLEL_SAFE
- Authorized requirements: currency correctness (future multi-currency)
- Evidence: ARCH-011, AB-008 (undocumented USD defaults)
- Current state: `currency="USD"` defaults in paper/risk/xa01
- Target state: documented limitation; FX layer boundary defined (per-instrument denomination + per-account base currency) for when needed
- Affected files: docs + module docstrings
- Dependencies: BL-0105
- Strategy: documentation; no FX implementation yet
- Safety risk: none · Regression risk: none
- Tests required: none
- Runtime validation: n/a
- Documentation required: currency limitation note
- Acceptance criteria: USD-only is an explicit documented limitation with an FX boundary design
- Wave: 1

---

## WAVE 2 — Trading / Risk Correctness

### BL-0201 Server preview tokens + fingerprint binding (RC-005)
- **Status: COMPLETE_BY_G3 (2026-09-07)** — server-side preview record (`paper/preview.py` PreviewStore: preview_id + intent digest + account/mode/instrument/side/qty/type/limit + risk-policy revision + portfolio-state revision + bounded TTL) with fail-closed `verify_preview_submit` (PREVIEW_NOT_FOUND/EXPIRED/INTENT_MISMATCH/ACCOUNT_MISMATCH/MODE_MISMATCH/PORTFOLIO_STALE/POLICY_STALE); UI route requires a current matching preview before submit; risk still re-run at submit. Strategy automation path uses an equivalent server-authoritative binding: `PreparedPaperExecution` with content-derived idempotency key (derived from risk_decision_id, verified at `_submit_prepared` via PREPARED_EXECUTION_IDEMPOTENCY_MISMATCH) and explicit prepared risk-reference-price handoff (approved_notional_minor // approved_quantity) into the final submit-time financial recheck. Evidence in 15 (G3 section); tests in `tests/trading_correctness/` (test_preview_binding.py, test_strategy_authority.py).
- Priority: **P2** · Type: TRADING · Complexity: M · Parallelization: PARALLEL_SAFE
- Authorized requirements: preview→submission integrity (controller §4; Tier E)
- Evidence: TRD-001, SAFE-001, AB-006, TD-A5, ADR-C-005, WS06 §8 (invisible to user today)
- Current state: no preview_id/hash/cursor binding; submit re-derives; `_paper_observation_time` per call; UI fingerprint partial
- Target state: server preview record (preview_id + intent hash + observation time/cursor + identity + market-state fingerprint); submit requires valid current preview; `PREVIEW_STALE` rejection; cursor change invalidates
- Affected files: `ui_api/paper_projections.py`, `paper/contracts.py` (preview state), `ui/src/components/paper/OrderTicket.tsx`, paperOrderDraft.ts
- Dependencies: none (small lifecycle touch)
- Strategy: additive preview record → wire UI → reject stale
- Safety risk: medium (trading path) · Regression risk: medium; lifecycle tests
- Tests required: preview/submit integrity tests (stale preview rejected; cursor-move invalidation; instrument/mode/account change rejection; same-intent replay)
- Runtime validation: paper workflow E2E + full at closure
- Documentation required: trading lifecycle section
- Acceptance criteria: a submit without a current matching preview is rejected with `PREVIEW_STALE`; scrubbing the cursor between preview and submit invalidates; risk still re-run at submit
- Wave: 2

### BL-0202 Buying-power/cash enforcement (RC-006)
- **Status: COMPLETE_BY_G3 (2026-09-07)** — final server-side cash gate on both executable submit paths (`_enforce_buy_side_cash_availability` INTERNAL_SIMULATION, `_enforce_broker_buy_side_cash_availability` BROKER_PAPER): required <= available where available subtracts working-order obligations (working_remaining × effective price × contract_multiplier); LIMIT prices at limit, MARKET uses conservative bar close/high (internal) or live mark (broker); fail-closed REQUIRED_PRICE_MISSING when no price evidence; strategy path supplies server-authoritative reference price from the approved risk decision (cannot bypass insufficient cash); currency from canonical instrument metadata when intent currency absent; exact-cash boundary accepted, +1 minor unit rejected; partial fill shrinks reservation; replace recomputes reservation. Evidence in 15 (G3 section); tests in `tests/trading_correctness/` (test_financial_enforcement.py, test_strategy_authority.py) and platform broker fixtures updated to supply live marks (UI-path parity).
- Priority: **P2** · Type: RISK · Complexity: S · Parallelization: PARALLEL_SAFE (equity base) / PARALLEL_AFTER_DEPENDENCY (BL-0105 for multi-asset)
- Authorized requirements: risk enforcement (Tier E)
- Evidence: TRD-006, AB-007, TD-A6, ADR-C-006 (grep zero buying_power in risk/)
- Current state: BP DISPLAY_ONLY; no cash check
- Target state: cash/BP check in `evaluate_risk` on equity minor-int base; multi-asset cash after BL-0105; clear `RISK_BLOCKED: insufficient buying power`
- Affected files: `risk/decision.py`, `risk/policy.py`, `paper/contracts.py`, tests
- Dependencies: BL-0105 for multi-asset; equity check can land first
- Strategy: add BP computation from ledger cash → enforce APPROVE/REJECT → UI surfaces real BP
- Safety risk: low (adds a check) · Regression risk: medium; limits tests
- Tests required: BP enforcement tests (insufficient cash rejected; margin-case limits)
- Runtime validation: paper workflow with cash-limited scenarios
- Documentation required: risk model
- Acceptance criteria: order exceeding available cash is rejected at submit; BP shown = enforced value
- Wave: 2

### BL-0203 Instrument-kind validation at order boundary (RC-006)
- **Status: COMPLETE_BY_G3 (2026-09-07)** — canonical identity admission at the order boundary: tradable securities (equity/ETF), option contracts (with multiplier), and specific future contracts admitted; family/continuous/reference identities rejected; unresolved aliases fail closed with UNKNOWN_INSTRUMENT; ES family cannot masquerade as equity; arbitrary legacy equity fallback closed. Operator fixtures canonically register BIYA/AAPL; preview mutation tests reach PREVIEW_INTENT_MISMATCH specifically (MSFT canonically registered first). Evidence in 15 (G3 section); tests in `tests/trading_correctness/` (test_identity_admission.py).
- Priority: **P2** · Type: TRADING/MULTI_ASSET · Complexity: S · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0101)
- Authorized requirements: safe futures/options execution (LATER-003/004); continuous-future non-execution
- Evidence: SAFE-003, MA-005, AB-005, TD-A6, ADR-C-006 (arbitrary symbol accepted; continuous/family could submit)
- Current state: `build_instrument_ref` equity-defaults; `_require_order_instrument` string resolution
- Target state: submission validates instrument-kind (TRADABLE_SECURITY/FUTURE_CONTRACT/OPTION_CONTRACT); continuous/family/root rejected with `UNSUPPORTED_INSTRUMENT_KIND`; `ES` vs `ESU6` disambiguated
- Affected files: `paper/contracts.py`, order submission path, `contracts/futures.py` resolution, tests
- Dependencies: BL-0101
- Strategy: contract-resolution service → kind validation → rejection
- Safety risk: low (adds rejection) · Regression risk: medium; execution tests
- Tests required: instrument-kind rejection test (continuous/family rejected; tradable accepted; option contract accepted with multiplier)
- Runtime validation: paper workflow + futures domain
- Documentation required: trading lifecycle
- Acceptance criteria: submitting a futures family/continuous symbol is impossible; option/future contracts carry multiplier in the instrument ref
- Wave: 2

### BL-0204 Working-order remainder + fill aggregation (RC-007)
- **Status: COMPLETE_BY_G3 (2026-09-07)** — requested/submitted/filled/working-remainder truth corrected: projection exposes `working_remaining` and working obligations use working_remaining × effective price × multiplier (not the original desired quantity); partial fills shrink reservation; replace recomputes it; REPLACED included in open obligation states and preview portfolio revision. Evidence in 15 (G3 section); tests in `tests/trading_correctness/` (test_lifecycle_remainder.py, test_financial_enforcement.py).
- Priority: **P2** · Type: TRADING · Complexity: L · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0201)
- Authorized requirements: trading lifecycle completeness (Tier E)
- Evidence: TRD-003, TD-A8, ADR-C-007 (one-shot fill; no remainder; cancel-after-partial unsupported internally)
- Current state: simulator emits one fill; PARTIALLY_FILLED has no working remainder
- Target state: remaining_qty + avg_fill_price + multiple fills per order; cancel-after-partial works; broker path consistent
- Affected files: `execution/simulator.py`, `paper/execution.py`, `paper/contracts.py`, `paper/ledger.py` (fill aggregation), UI order panels
- Dependencies: BL-0201
- Strategy: order-model remainder → simulator multi-fill → ledger aggregation → broker parity
- Safety risk: medium (order truth) · Regression risk: high; lifecycle tests
- Tests required: multi-fill/remainder tests, avg-price goldens, cancel-after-partial, broker cumulative-status parity
- Runtime validation: paper workflow with participation-capped fills
- Documentation required: trading lifecycle
- Acceptance criteria: a partially-filled order retains a working remainder; fills aggregate to avg price; cancel-after-partial resolves to CANCELLED with remainder never silently dropped
- Wave: 2

### BL-0205 Replace lifecycle (RC-007)
- **Status: COMPLETE_BY_G3 (2026-09-07)** — REPLACE_PENDING → REPLACED with REPLACE_PENDING/REPLACED non-terminal working evidence; already-filled quantity immutable; replacement total cannot be below cumulative filled; working remainder = replacement authorized total − cumulative fills; replace revision/count persisted in OrderReplaced event body (replace_revision projection bug fixed); duplicate replace request idempotent (no second event); REPLACED remains a working obligation; cancel after replace works; price/quantity replacement recomputes cash obligation; restart/replay reconstructs replacement truth. Evidence in 15 (G3 section); tests in `tests/trading_correctness/` (test_replace_lifecycle.py).
- Priority: P3 · Type: TRADING · Complexity: M · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0204)
- Authorized requirements: order management (Tier E); bracket semantics direction
- Evidence: TRD-004, TD-A8, ADR-C-007, UX-007 (no replace anywhere)
- Current state: no REPLACE_PENDING/REPLACED states; no `replace_order`; no UI
- Target state: replace = cancel+submit-same-client-order-id with explicit states; capability in provider contracts; UI affordance
- Affected files: `paper/contracts.py`, `paper/execution.py`, `providers/contracts.py`, `ui` order management
- Dependencies: BL-0204
- Strategy: states → capability → UI
- Safety risk: medium · Regression risk: medium
- Tests required: replace lifecycle tests, idempotency-under-replace, broker-path replace
- Runtime validation: paper workflow
- Documentation required: trading lifecycle
- Acceptance criteria: an open order can be replaced (qty/limit) with REPLACE_PENDING → REPLACED; replaced orders trace to original client_order_id
- Wave: 2

### BL-0206 Late-fill-during-cancel handling (RC-007)
- **Status: COMPLETE_BY_G3 (2026-09-07)** — `_cancel_broker_paper_order` calls cancel-time late-fill capture; late fill appended once with reconciliation provenance; duplicate fill IDs ignored; cancellation does not erase prior fills; reconciliation event recorded; terminal broker orders are not continuously re-polled; Tradier/Moomoo cancel status events surfaced via `events` collection. Evidence in 15 (G3 section); tests in `tests/trading_correctness/` (test_late_fill.py) and platform CancelDispatch tests updated to a provider returning an empty `events` stream.
- Priority: P3 · Type: TRADING · Complexity: S · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0204)
- Authorized requirements: trading lifecycle correctness (Tier E)
- Evidence: TRD-005, TD-A8 (fill-after-cancel unmodeled)
- Current state: broker path cumulative status polls; orchestrator closes the PARTIALLY_FILLED loop; race unmodeled
- Target state: fill-after-cancel-detected reconciliation event; late fill never silently lost or double-counted
- Affected files: `paper/broker_paper.py`, `paper/ledger.py`, `paper/execution.py`
- Dependencies: BL-0204
- Strategy: reconciliation event + ledger handling
- Safety risk: low · Regression risk: medium
- Tests required: late-fill cancel test (fill arriving after cancel accepted with explicit provenance)
- Runtime validation: broker-paper recorded-fixture tests
- Documentation required: trading lifecycle
- Acceptance criteria: a fill that arrives after CANCELLED is recorded as a reconciliation event with provenance, never silently dropped or double-applied
- Wave: 2

### BL-0207 Content-derived idempotency + per-ledger locking (RC-008)
- **Status: COMPLETE_BY_G3 (2026-09-07)** — per-ledger `RLock` (`submit_critical_section`) covering idempotency lookup → conflict detection → intent/risk/order/fill append → `record_idempotent_order`; BROKER_PAPER records idempotency BEFORE the external provider call and releases the lock before the network call; no GIL-reliant concurrency proof — thread-barrier tests prove one logical order / one fill under concurrent same-key submits, IDEMPOTENCY_CONFLICT for same-key different-intent, independent per-account scope, and restart/replay reconstruction. Evidence in 15 (G3 section); tests in `tests/trading_correctness/` (test_idempotency_replay.py, test_strategy_authority.py).
- Priority: P3 · Type: TRADING/RELIABILITY · Complexity: M · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0201)
- Authorized requirements: idempotency (Tier E)
- Evidence: TRD-002, TD-A15 (client-supplied keys; single-process lock)
- Current state: lookup→record atomic only under `LEDGER_ROUTE_LOCK`; keys not content-derived
- Target state: content-derived idempotency key (intent hash) + server-issued retry token per attempt; per-ledger locking
- Affected files: `ui_api/server.py`, `paper/ledger.py`, paperOrderDraft.ts, tests
- Dependencies: BL-0201 (intent hash)
- Strategy: key derivation → retry tokens → lock scope
- Safety risk: low · Regression risk: medium
- Tests required: duplicate-submit stress (same intent → same order; lost-key retry → detected duplicate; multi-thread route tests)
- Runtime validation: paper workflow
- Documentation required: idempotency model
- Acceptance criteria: two submits with identical intent return the same order; a client that lost its key cannot create a duplicate; multi-thread route test passes
- Wave: 2

### BL-0208 CVD session anchors/reset (RC-003)
- **Status: COMPLETE_BY_G3 (2026-09-07)** — deterministic CVD session semantics implemented (`order_flow/cvd.py`); session boundary/reset explicit, never silent; deterministic session behavior proven by tests. Evidence in 15 (G3 section); tests in `tests/trading_correctness/` (test_cvd_session.py). No exchange-calendar modeling added (out of scope for current architecture).
- Priority: P3 · Type: CVD/MARKET_DATA · Complexity: S · Parallelization: PARALLEL_SAFE
- Authorized requirements: CVD correctness (LATER-001/002)
- Evidence: TRD-008, TD-A12 (cumulative delta no reset semantics)
- Current state: series restarts on restart/rollover; no session boundary marker
- Target state: session boundary + reset semantics in the CVD series; anchor marker in payload
- Affected files: `order_flow/cvd.py`, `ui_api/live_projections.py`, formula tests
- Dependencies: none
- Strategy: add session anchor to series state
- Safety risk: none · Regression risk: low
- Tests required: session-reset CVD test
- Runtime validation: order-flow suite
- Documentation required: CVD model note
- Acceptance criteria: CVD series carries a session anchor; reset is explicit and never silent
- Wave: 2

### BL-0209 Cross-asset risk hooks (RC-001/006)
- **Status: COMPLETE_BY_G3 (2026-09-07)** — typed cross-asset pre-trade hook boundary (`risk/pretrade.py` evaluate_pretrade / PreTradeRiskContext) wired into BOTH executable BUY financial enforcement paths (internal + broker-paper): typed context consumes canonical G1 identity + G2 cash; hooks can reject (NON_EXECUTABLE_INSTRUMENT, UNSUPPORTED_RISK_MODEL, INSUFFICIENT_CASH, INSUFFICIENT_POSITION, INSUFFICIENT_SETTLEMENT_CURRENCY, REQUIRED_PRICE_MISSING); hooks cannot bypass account/mode authority (checked before); default path still performs authoritative financial checks; no duplicate conflicting financial implementation remains. Evidence in 15 (G3 section); tests in `tests/trading_correctness/` (test_pretrade_hooks.py).
- Priority: P3 · Type: RISK/MULTI_ASSET · Complexity: L · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0105, BL-0202)
- Authorized requirements: multi-asset risk (Tier E)
- Evidence: 06 §37 (notional/margin inputs), ADR-C-006 extension
- Current state: equity-share limits only; no notional/margin/concentration
- Target state: risk inputs = positions + prices + multipliers + margins + FX; aggregate notional/gross/net; APPROVE/RESIZE/REJECT generalized; concentration/liquidity as advisory-first
- Affected files: `risk/decision.py`, `risk/policy.py`, `paper/contracts.py`, tests
- Dependencies: BL-0105, BL-0202
- Strategy: input domain generalization → aggregate exposure → limits
- Safety risk: medium (risk is enforcement) · Regression risk: high; goldens
- Tests required: cross-asset notional tests, margin cases, concentration advisory tests
- Runtime validation: full at closure
- Documentation required: risk architecture
- Acceptance criteria: risk evaluates multi-asset notional exposure; existing equity limit behavior unchanged; margin inputs for futures/options present
- Wave: 2

---

### BL-0210 Cross-lane occurrence-weight honesty (golden-blocker reconciliation) (RC-001 follow-on)
- **Status: COMPLETE_BY_G31 (2026-09-08)** — `cross_lane/fusion.py` `_occurrence_weight` no longer returns a silent 1.0 for missing occurrence evidence: squeeze-aligned template with no hazard AND no occurrence model output fails closed to UNAVAILABLE (`OCCURRENCE_UNAVAILABLE`); non-squeeze-aligned paths carry an explicit `OCCURRENCE_UNAVAILABLE` quality flag with factor 1.0; `PAYOFF_ALREADY_NET_TOLERANCE` replaces the magic 1e-9; formula_ledger + SHARED_P4_EV_OPPORTUNITY_SPEC bumped to fusion v2; golden fixture regenerated with hash forensics (`.local/g31-hash-forensics.py`) proving the V1→V2 snapshot delta is the intended semantic change. This removes the last known FULL failure (the previously excluded cross_lane golden): FULL **3870/48/0**, FAST 21/0, CHANGED 3233/48/0. Evidence in 15 (G3.1 section); tests in `tests/cross_lane/` (test_opportunity_fusion.py +6, test_portfolio_p5.py +3).
- Priority: P3 · Type: CORRECTNESS · Complexity: S · Parallelization: PARALLEL_SAFE
- Authorized requirements: cross-lane evidence honesty (06 §37/§55)
- Evidence: G3 closure exception (15 G3 section); RC-001
- Current state: silent occurrence weight 1.0 when a squeeze-aligned template lacked occurrence model output
- Target state: fail-closed occurrence; golden green (no excluded failures)
- Affected files: `cross_lane/fusion.py`, `tests/cross_lane/*`, golden fixture, formula_ledger, SHARED spec
- Dependencies: BL-0209 (risk hooks)
- Strategy: harden `_occurrence_weight` → regenerate golden → forensic hash proof → full validation
- Safety risk: low (research-lane honesty) · Regression risk: low; golden + forensics
- Tests required: occurrence fail-closed, non-squeeze flag, already-net tolerance, golden
- Runtime validation: full at closure
- Documentation required: this status + 15 G3.1 section
- Acceptance criteria: no silent 1.0 occurrence; FULL green with zero failures
- Wave: 2

### BL-0211 Canonical multi-asset accounting kernel (G4 — instrument economics + options-ledger convergence + futures Decimal + per-currency obligations)
- **Status: COMPLETE_BY_G4 (2026-09-08)** — one canonical multi-asset accounting foundation replacing the remaining equity-centric/fragmented assumptions. (1) `portfolio/instrument_economics.py` — fail-closed economics contract derived from XA-01 descriptors/refs (quantity unit kind-driven; derivative multiplier explicit and positive; missing multiplier/currency/unknown kind fail closed; multiplier=1 valid only for equity/ETF). (2) `portfolio/accounting.py` — central exact-Decimal kernel (notional/exposure/premium/variation-P&L/realized/cash-requirement/reservation; binary float rejected at the boundary). (3) canonical portfolio mutation boundary now rejects derivative positions without CONTRACTS unit + positive multiplier (new `INVALID_POSITION_ECONOMICS`). (4) Options ledger (`portfolio/options_ledger.py`) rewritten to Decimal-exact, marked NON-AUTHORITATIVE compatibility over the O9 simulation lane, with a canonical position adapter (`build_canonical_option_positions` — same-identity partial fills aggregate, contract quantity truth, exact premium cost basis). (5) Futures Decimal proofs (1 contract / scaling / long-short sign / no drift / replay) via the kernel + canonical valuation; roll/reference identities remain non-executable. (6) Per-currency obligations (`working_order_obligations_by_currency`, `currency_available_cash_minor`), per-currency financial gate + pretrade context (`currency_cash_minor`); missing currency bucket fails closed INSUFFICIENT_SETTLEMENT_CURRENCY — never 1:1. (7) G3.1-precondition repair: three callers of the fail-closed `register_future_contract` (2 portfolio tests + 1 trading-correctness test + 1 xa01 adapter test) updated to supply explicit multipliers, plus a new spec-less-future fail-closed test. Evidence in 15 (G4 section); tests: `tests/portfolio/test_instrument_economics.py` (27), `tests/trading_correctness/test_multi_asset_accounting.py` (31), xa01 +1. FULL **3929/48/0**, FAST 21/0, CHANGED 3347/48/0.
- Priority: **P1** · Type: ARCHITECTURE/FOUNDATION · Complexity: XL · Parallelization: SERIAL (accounting foundation)
- Authorized requirements: multi-asset accounting kernel; reorders the 19 §1 G4 slot (IBKR adapter) per current mandate; folds in BL-0106 (options-ledger merge) and BL-0107 (futures Decimal)
- Evidence: G2 portfolio foundation, G3 trading-correctness; current-state matrix in 14a (G4 Phase 0)
- Current state: equity-centric accounting; independent float options ledger; USD-only obligations; multiplier fallbacks; futures notional/cash conflation risk
- Target state: one canonical instrument-economics contract + exact-Decimal kernel; options converge to canonical state (float ledger NON-AUTHORITATIVE); per-currency cash/obligations; fail-closed unknown economics/FX
- Affected files: `portfolio/{accounting,instrument_economics,canonical,options_ledger}.py`, `options/execution.py` (presentation boundary), `risk/{financial,pretrade}.py`, `paper/{execution,broker_paper}.py` (gates), tests + docs
- Dependencies: G2 (canonical portfolio), G3 (gates), XA-01 (identity/economics)
- Strategy: bounded checkpoints (economics contract → accounting kernel → canonical position validation → options Decimal convergence → futures proofs → per-currency gate → replay/tests → validation)
- Safety risk: low-medium; all gates preserved; no margin model invented; futures still UNSUPPORTED_RISK_MODEL at gate
- Regression risk: low; existing suites green; exact-Decimal options arithmetic preserves golden O9 snapshots (float only at JSON boundary)
- Tests required: multi-asset accounting section (equity/option/future/currency/identity/consistency/replay), economics contract, canonical derivative-position fail-closed
- Runtime validation: full at closure
- Documentation required: this status + 15 G4 section + WORK_LOG + PROGRAM_STATUS + formula_ledger + 14a matrix
- Acceptance criteria: 16-point G4 closure standard — canonical economics for equity/option/future; multiplier canonical; no independent float option authority; futures P&L exact; canonical positions represent all three classes; per-currency cash/obligations; unknown FX fail closed; partial/replace/cancel reservation intact; replay identical; idempotency safe; FAST/CHANGED/FULL green with zero failures
- Wave: 2

### BL-0212 Canonical incremental L2 order-book engine (G5 — depth-state correctness, staleness/reset semantics, deterministic replay)
- **Status: COMPLETE_BY_G5 (2026-09-08)** — one canonical provider-neutral incremental market-by-price book engine resolving ARCH-003/ARCH-006/ARCH-009. (1) `order_flow/order_book/` canonical domain: `contracts.py` (DepthOperation INSERT/UPDATE/DELETE/RESET, DepthSide BID/ASK, DepthUpdate event with instrument_id/side/op/price/size/position/source/source_time_ns/received_time_ns/sequence/subscription_id/provider_event_id/schema_version/provenance; Decimal-exact price/size — `Decimal(str(v))` boundary normalization, binary float rejected; `ApplyResult` contract with APPLIED/NOOP/DUPLICATE/REJECTED/INVALIDATED/RESET_APPLIED outcomes + reason/sequence_state/validity/generation/update_count), `engine.py` (price-keyed side-ordered `IncrementalOrderBook`: bids descending / asks ascending; explicit insert/update/delete semantics; position is advisory rank metadata cross-checked — mismatch fails closed STRUCTURALLY_CORRUPT; conflicting duplicate insert invalidates; UPDATE of missing level invalidates (recovery-required); DELETE of absent price is benign no-op; delete never removes an unrelated rank; zero size only on DELETE; RESET clears all levels + advances generation + clears sequence continuity + marks RESET_PENDING; sequence state machine NO_SEQUENCE/BASE/CONTIGUOUS/DUPLICATE/GAP/REGRESSION — gap/regression fail closed INVALID, recovery required before trust; generation gate rejects late old-subscription events; `state_hash()` deterministic; never reads a wall clock), `freshness.py` (pure `evaluate_book_freshness(book, as_of_time_ns, policy)` → FRESH/STALE/INVALID/UNAVAILABLE; thresholds in policy not projections; INVALID beats STALE; stale book never presented as valid without qualifier), `projection.py` (deterministic legacy snapshot dict projection with additive `book_status`/`book_status_reason`/`sequence_status`/`generation`/timestamps; `ingest_snapshot_dict` compatibility ingestion), `replay.py` (`replay(events)`/`replay_state_hash`/`measure_replay_throughput` — duplicate events never double-apply; RESET boundaries and gap invalidation replay identically). (2) Order-flow adaptation: `ofi.py` adds versioned `OFI_METHOD_MULTILEVEL_PRICE_ALIGNED` (`compute_multilevel_ofi_price_aligned`) — price-keyed signed size deltas, eliminating the rank N→N mis-pairing (ARCH-006); legacy rank-sum method retained unchanged. (3) Store/API: `market_data/observational_state.py` holds canonical engines per instrument; full-book provider pushes enter via explicit `replace_from_snapshot` (RESET-then-load, never blind UPDATE); `book_state_valid` in stored books and `ui_api/live_projections.py` is derived truth (ARCH-009 hardcoded `True` removed). (4) CVD untouched in authority — `order_flow/cvd.py` session-anchor/reset metadata (BL-0208) preserved with its tests. Evidence: 15 (G5 section), current-state matrix 14b, replay-performance evidence `g5-order-book-replay-evidence.json` (~93k/45k/23k events/sec at 10/50/100 levels, PERFORMANCE_MEASURED — no production claim). Tests: `tests/order_flow/test_order_book_*.py` (82) + `tests/market_data/test_canonical_book_integration.py` (5). FULL **4016/48/0**, FAST 21/0, CHANGED 3481/48/0. IBKR `reqMktDepth` mapping documented for G6 only — no runtime IBKR work.
- Priority: **P1** · Type: ARCHITECTURE/FOUNDATION · Complexity: L · Parallelization: SERIAL (market-data foundation)
- Authorized requirements: incremental L2 book engine (AB-003/ARCH-003); snapshot replacement becomes ingestion compatibility only; deterministic replay; staleness/validity derived truth
- Evidence: WS05 ARCH-003/006/009; 06 §18 (WS05); current-state matrix 14b (G5 checkpoint A)
- Current state: snapshot-replacement-only book (`update_semantics: "SNAPSHOT"`), ad hoc consumer re-sorts, hardcoded `book_state_valid: True`, no insert/update/delete/reset/sequence/staleness, rank-pair OFI mis-pairing on shift
- Target state: one canonical incremental engine authoritative; explicit mutation semantics; sequence/generation/reset/staleness explicit; deterministic replay; snapshot compatibility projection; price-aligned OFI (v2 method, v1 retained)
- Affected files: `order_flow/order_book/*` (new), `order_flow/{ofi,cvd,contracts,__init__}.py`, `market_data/observational_state.py`, `ui_api/live_projections.py`, tests + docs + formula_ledger (`of.multilevel_ofi_price_aligned`)
- Dependencies: G4 (baseline); G6 (IBKR adapter) consumes the engine
- Strategy: bounded checkpoints A→H (baseline map → contracts → snapshot compat → sequence/reset/staleness → CVD interop → replay/perf → focused+affected validation → FAST/CHANGED/FULL + docs)
- Safety risk: low-medium; canonical engine fails closed on gap/regression/corruption; existing order-flow/CVD consumers unchanged in authority
- Regression risk: low; trading_correctness 122 green; order_flow 66 green; CVD 8 green; legacy OFI v1 byte-identical (new method additive)
- Tests required: basic state, incremental ops (head/middle/tail), side isolation, sequence 5-state, reset/generation/late-event, state integrity, staleness, replay determinism, snapshot round trip, OFI price-aligned no false rank-pair
- Runtime validation: full at closure
- Documentation required: this status + 15 G5 section + WORK_LOG + PROGRAM_STATUS + 00-program-state + formula_ledger + 14b matrix
- Acceptance criteria: 23-point G5 closure standard — one canonical engine; explicit insert/update/delete/reset; snapshot no longer authoritative; explicit sequence handling; gaps/out-of-order fail closed; generation isolation; explicit staleness; derived `book_state_valid`; empty/one-sided/crossed explicit; deterministic replay; no double-apply; CVD semantics intact; OFI rank-shift resolved; snapshot compat available; no provider state machine in canonical domain; IBKR mapping documented not implemented; focused/trading_correctness/FAST/CHANGED/FULL green; no unrelated dirty work reverted; docs updated
- Wave: 2

### BL-0213 IBKR observational L1/L2 provider adapter (G6 — canonical runtime boundary)
- **Status: COMPLETE_BY_G6 (2026-09-08)** — canonical provider-neutral IBKR observational runtime at `src/market_platform_foundation/providers/ibkr_observational/` (14 modules: adapter, capability, capture, constants, contracts, diagnostics, errors, identity, l1, lifecycle, mapping, pacing, rank). IBKR callback facts → XA-01 canonical instrument identity → canonical L1 quote facts and/or `DepthUpdate` → `ObservationalStateStore` → G5 `IncrementalOrderBook`. Verified operation/side mapping (0=INSERT/1=UPDATE/2=DELETE; 0=ASK/1=BID) in `constants.py` with evidence chain; L2 rank/position state translates IB position-oriented callbacks to price-keyed canonical events (price-changing UPDATE emits DELETE+INSERT; DELETE resolves price from rank state; rank disagreement fails closed/RESET); `DepthUpdate.sequence=None` always (NO_SEQUENCE truthful); L1 subscription-local accumulation (bid/ask/sizes/last/delayed) with explicit entitlement/delayed state; subscribe/cancel/reconnect/generation/late-reqId rejection/local pacing caps; provider error normalization (evidence-backed codes only); memory-only capture by default (`capture_path=None`); replay through adapter normalization path; diagnostics/readiness; NO execution capability registered; offline gate blocks transport I/O; runtime `src` does not import `tools/ibkr` implementation. 91 new provider tests; FAST 21/0; CHANGED **3572/48/0**; FULL **4107/48/0** — zero failures; adapter throughput measured (ADAPTER_PERFORMANCE_MEASURED, dev machine only); live provider **LIVE_PROVIDER_UNVERIFIED**.
- Priority: **P1** · Type: IBKR/PROVIDER · Complexity: L · Parallelization: SERIAL (consumes G5 engine)
- Authorized requirements: CVD L1+L2 IB data (LATER-002); IB for options maybe (LATER-007); Futures IB data (LATER-008)
- Evidence: 14c G6 matrix; G5 BL-0212 engine; WS05 ARCH-001; verified IBKR TWS API depth docs
- Current state (pre-G6): `tools/ibkr` observational REST/TWS tooling only; no canonical adapter; no depth wiring to store
- Target state: canonical runtime adapter with L1/L2 observational boundary, entitlement/pacing/lifecycle, capture/replay, store integration — **achieved**
- Affected files: `providers/ibkr_observational/*` (new), `market_data/observational_state.py`, `tests/providers/test_ibkr_observational_*.py` (new), `tests/providers/ibkr_observational_support.py`, docs/evidence
- Dependencies: G5 (BL-0212 canonical book engine); G1 XA-01 identity
- Safety risk: low — observational only; no placeOrder/cancelOrder/modifyOrder/exerciseOptions; offline fail-closed
- Regression risk: low — G5 order_book 87 green; trading_correctness 122 green; providers 216 green
- Tests required: L1 accumulation, delayed/entitlement, L2 mapping/rank/DELETE/price-change UPDATE, lifecycle/reconnect/generation, safety/offline, capture/replay, performance measurement, provider registry readiness
- Runtime validation: FULL green at closure
- Documentation required: 14c matrix + 15 G6 section + WORK_LOG + PROGRAM_STATUS + 00-program-state + BL-0213 status
- Acceptance criteria: 30-point G6 closure standard (see 14c + closure report) — all met with FULL green
- Wave: 3 (foundation; precedes broader BL-0301 convergence)

## WAVE 3 — IBKR / Live Market-Data Foundation

### BL-0301 IBKR adapter seeded from `tools/ibkr` (RC-002)
- Priority: **P1** · Type: IBKR/PROVIDER · Complexity: XL · Parallelization: SERIAL within Wave 3 (foundation)
- Authorized requirements: CVD L1+L2 IB data (LATER-002 verbatim); IB for options maybe (LATER-007); Futures IB data (LATER-008)
- Evidence: ARCH-001, AB-002, P1-1, MS-01, TD-A1, ADR-C-002, D19 (SEED recommended)
- Current state: **IMPLEMENTATION_COMPLETE (G12)** — observational L1/L2/TRADES streaming + contract/secdef + historical bars + read-only account observation runtime-wired; G11.1 live canary verified contract/bars/account/L1 (delayed); L2/TRADES **LIVE_CONNECTED_NOT_ENTITLED** (external account subscription — **not** an IMP implementation blocker per 14j); provider account facts `READ_ONLY_OBSERVATIONAL`; execution authority absent by design
- Target state: one IBKR provider adapter with market-data capability (L1 + L2 + bars + secdef) and account/portfolio read; execution capability separate and LIVE-gated (absent by design); capability-registry-compatible
- Affected files: `providers/adapters/ibkr_*.py` (new), `tools/ibkr/*` (seed), `providers/contracts.py`, `providers/composition.py`, tests
- Dependencies: BL-0302 (depth engine) for L2; BL-0401 (registry) for roles
- Strategy: adapt `tools/ibkr/client.py` (allowlist/pacing/capture) → add capability surface → record fixture streams → contract tests
- Safety risk: LOW at build (read-only); LIVE gates preserved · Regression risk: medium
- Tests required: IBKR provider-contract suite (recorded L1/L2 streams), pacing penalty-box, entitlement-loss, error mapping, Paper↔Live account mapping
- Runtime validation: recorded-wire replay; live-gated canary (documented, not CI)
- Documentation required: IBKR provider doc
- Acceptance criteria: IBKR adapter exposes L1/L2/account capabilities behind capability contracts; no execution capability outside LIVE-001; CVD can consume its L1/L2 output (BL-0304)
- Wave: 3

### BL-0302 Incremental depth engine + book lifecycle (RC-003)
- Priority: **P1** · Type: LEVEL2/MARKET_DATA · Complexity: L · Parallelization: PARALLEL_SAFE (buildable on fixture depth streams)
- Authorized requirements: Level-2 measurement (LATER-001/002)
- Evidence: ARCH-003, AB-003, TD-A3, ADR-C-003 (snapshot-only book)
- Current state: `observational_state.apply_admitted` replaces whole book; no events; no reset; `book_sequence` optional
- Target state: depth event model (INSERT/UPDATE/DELETE/CLEAR per side+price), full snapshot on subscribe/reconnect, per-level sequence, book TTL + stale eviction, `book_sequence` mandatory on live streams
- Affected files: `market_data/observational_state.py`, `market_data/depth_engine.py` (new), `market_data/live_admission.py`, `ui_api/live_projections.py`, order-book lane
- Dependencies: none (fixture-first)
- Strategy: new depth engine alongside snapshot store → migrate consumers → remove snapshot path
- Safety risk: low (research/display) · Regression risk: medium; state-machine tests
- Tests required: depth state-machine tests (insert/update/delete/clear), reconnect/book-reset, sequence continuity, TTL eviction, payload quality
- Runtime validation: order-book suite + recorded depth replay
- Documentation required: L2 architecture
- Acceptance criteria: incremental depth events produce correct book state; reconnect triggers rebuild; stale books evicted; `book_state_valid` reflects real state (never hardcoded true)
- Wave: 3

### BL-0303 Depth staleness/TTL + payload quality (RC-003)
- Priority: **P2** · Type: LEVEL2/MARKET_DATA · Complexity: S · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0302)
- Authorized requirements: freshness correctness (Tier E)
- Evidence: ARCH-009, SAFE-004, TD-A9 (DEPTH never flagged STALE; hardcoded valid)
- Current state: staleness check L1/SNAPSHOT-only; `book_state_valid: True` hardcoded
- Target state: depth TTL + stale eviction + explicit quality in payload; stale book blocks LOB-feature use
- Affected files: `market_data/live_admission.py`, `ui_api/live_projections.py`
- Dependencies: BL-0302
- Strategy: extend freshness model to DEPTH capability
- Safety risk: low · Regression risk: low
- Tests required: stale-depth display tests, TTL tests
- Runtime validation: order-book suite
- Documentation required: freshness model
- Acceptance criteria: a stalled depth feed surfaces stale state; payload reports book validity truthfully
- Wave: 3

### BL-0304 IBKR L1 wiring into CVD lane (RC-002)
- Priority: **P2** · Type: CVD/IBKR · Complexity: M · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0301)
- Authorized requirements: CVD L1 (LATER-002)
- Evidence: ARCH-001 (L1 observational not wired), WS04 §4/§5
- Current state: **COMPLETE (offline/replay, G9)** — IBKR tick-by-tick trade tape (`IBKR_TRADES`) maps to `ClassifiedTrade` via Lee-Ready + canonical L1 context; store → G3 CVD proven in replay. L1-only still does not fabricate trades. Live tape verification remains separate
- Target state: IBKR L1 quotes/trades → normalized order-flow observations → CVD/OFI; runtime trade classification from live tape
- Affected files: `order_flow/*`, `market_data/normalization.py`, `live_projections.py`, `providers/adapters`
- Dependencies: BL-0301
- Strategy: adapter output → admission → normalization → CVD path
- Safety risk: low · Regression risk: medium
- Tests required: IB-L1-to-CVD replay test, trade-classification confidence tests
- Runtime validation: recorded IB stream replay
- Documentation required: CVD provider doc
- Acceptance criteria: IBKR L1 feed produces classified trades + CVD identical to fixture semantics on recorded stream
- Wave: 3

### BL-0305 IBKR subscription lifecycle / entitlements / reconnect (RC-002/003)
- Priority: **P2** · Type: IBKR/RELIABILITY · Complexity: M · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0301/0302)
- Authorized requirements: provider reliability (Tier E)
- Evidence: 06 §10 (subscription manager shape, admission vocabulary ENTITLEMENT_MISSING, reconnect resets), ARCH-003 (book rebuild missing)
- Current state: **IMPLEMENTATION_COMPLETE (G12)** — lifecycle/entitlement/reconnect proven offline + G11.1 bounded live canary executed; L2/TRADES not entitled on current account (external limit); rerunnable via `tools/ibkr/canary.py` when subscriptions change
- Target state: subscription manager keyed by instrument+capability; entitlement failures → ENTITLEMENT_MISSING with visible reason; reconnect → sequence reset + book rebuild; pacing isolation preserved
- Affected files: `market_data/subscription_manager.py`, `market_data/live_admission.py`, `tools/ibkr/pacing.py` (reuse)
- Dependencies: BL-0301, BL-0302
- Strategy: lifecycle manager → reconnect protocol → tests
- Safety risk: low · Regression risk: medium
- Tests required: entitlement-loss tests, reconnect/book-reset tests, pacing tests
- Runtime validation: recorded + live-gated canary
- Documentation required: IBKR ops doc
- Acceptance criteria: entitlement loss surfaces per-capability reason; reconnect rebuilds L1 + L2 state; pacing penalty box never violated
- Wave: 3

### BL-0306 Delta-based / identity-preserving OFI (RC-003)
- Priority: P3 · Type: CVD/LEVEL2 · Complexity: M · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0302)
- Authorized requirements: L2 signal quality (LATER-001/002)
- Evidence: ARCH-006 (rank pairing mis-pairs on level churn)
- Current state: `compute_multilevel_ofi` pairs rank N→N across snapshots
- Target state: delta-based OFI over the incremental depth engine (identity-preserving)
- Affected files: `order_flow/ofi.py`, `order_flow/lob_features.py`
- Dependencies: BL-0302
- Strategy: recompute OFI from depth deltas
- Safety risk: none · Regression risk: medium; goldens
- Tests required: OFI goldens incl. level-churn cases
- Runtime validation: order-flow suite
- Documentation required: OFI model note
- Acceptance criteria: level inserts/deletes between updates do not mis-pair; empty-rank add artifact removed
- Wave: 3

---

## WAVE 4 — Authorized Existing Lanes to Runtime

### BL-0401 Provider Capability Registry (RC-009)
- Priority: **P2** · Type: PROVIDER · Complexity: L · Parallelization: PARALLEL_SAFE
- Authorized requirements: provider architecture (Tier E)
- Evidence: 06 §9/§12, ADR-C-009, CON-08 (roles implied; no discovery; fixed composition)
- Current state: capability Protocols + composition + fail-closed stubs; no role registry; no `capabilities()`
- Target state: Provider Capability Registry (provider → roles → capabilities → gates → freshness policy → discovery); fail-closed `UNSUPPORTED_CAPABILITY`
- Affected files: `providers/registry.py`, `providers/contracts.py`, `providers/composition.py`, adapters, UI readiness surfaces
- Dependencies: none (registry shape independent)
- Strategy: registry model → adapters report capabilities → UI/planner consult
- Safety risk: low · Regression risk: medium; provider suites
- Tests required: capability discovery tests, UNSUPPORTED_CAPABILITY fail-closed tests
- Runtime validation: provider health surface
- Documentation required: provider architecture
- Acceptance criteria: every adapter declares capabilities; the registry is the single source the UI/planner consult; a quote-only provider cannot fake bars
- Wave: 4

### BL-0402 Live-wire verification campaign (RC-009)
- Priority: **P2** · Type: PROVIDER/OPERABILITY · Complexity: L · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0401)
- Authorized requirements: verified live paths (MS-09; EVIDENCE-01C)
- Evidence: TD-W3 (no RUNTIME_VERIFIED wire; G1–G6 closed), WS04 §4/§5, TEST-003
- Current state: all providers CONFIGURED+IMPLEMENTED+TESTED with live gates closed; no verified wire
- Target state: per-provider recorded-wire contract evidence + live-gated canaries (Moomoo, Tradier sandbox, IBKR L1, FRED/CFTC/EIA/NOAA/SEC/CBOE, FinViz) with documented acceptance
- Affected files: `tests/live_*` suites, provider health, `docs/engineering/FORWARD_VALIDATION_READINESS_CHECKLIST.md`
- Dependencies: BL-0401
- Strategy: recorded-wire campaign per provider → canary gates → acceptance records
- Safety risk: LOW (all gates remain closed in CI; live-gated only) · Regression risk: low
- Tests required: live suites gated; recorded fixtures replayed in CI
- Runtime validation: canary runs under explicit live gate
- Documentation required: provider acceptance records
- Acceptance criteria: each provider has a recorded-wire evidence row + canary gate; no provider claims RUNTIME_VERIFIED without evidence
- Wave: 4

### BL-0403 Live OptionChainProvider (RC-009)
- Priority: P3 · Type: OPTIONS/PROVIDER · Complexity: L · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0401; BL-0103 identity)
- Authorized requirements: options analysis (LATER-004/007)
- Evidence: TD-W5, WS05 §19/§20 (protocol-only; CBOE stats live-gated)
- Current state: OptionChainProvider protocol + fixture adapter only
- Target state: live chain provider (CBOE public or IB-option chain) behind the capability contract; Greeks/IV from live quotes
- Affected files: `providers/adapters/option_chain_*.py`, `options/*`, `cboe_options/*`
- Dependencies: BL-0401
- Strategy: adapter → contract tests → analytics wiring
- Safety risk: low · Regression risk: medium
- Tests required: chain-provider contract tests (recorded), analytics-on-live-chain replay
- Runtime validation: live-gated canary
- Documentation required: options provider doc
- Acceptance criteria: options analytics consume a provider-backed chain; fixture path retained for offline
- Wave: 4

### BL-0404 Futures live data pipeline hardening (RC-009)
- Priority: P3 · Type: FUTURES/PROVIDER · Complexity: M · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0401)
- Authorized requirements: futures live data (LATER-003/008)
- Evidence: WS05 §21 (research engines strong; runtime absent), TD-W5
- Current state: CFTC COT live-gated; fixtures for bars/positioning
- Target state: provider-backed futures bars (IBKR or chosen adapter) + COT pipeline verified
- Affected files: `futures/*`, `providers/adapters`, `live_cftc_positioning.py`
- Dependencies: BL-0401
- Strategy: adapter per D3/D16 provider choice (BL-0904 tracks decision)
- Safety risk: low · Regression risk: medium
- Tests required: futures adapter contract tests
- Runtime validation: live-gated canary
- Documentation required: futures provider doc
- Acceptance criteria: futures engines consume provider-backed data; fixture path retained
- Wave: 4

### BL-0405 Squeeze bridge runtime reliability (RC-015)
- Priority: P3 · Type: SHORT_SQUEEZE/OPERABILITY · Complexity: S · Parallelization: PARALLEL_SAFE
- Authorized requirements: short-squeeze research (ORG-001, LATER-013)
- Evidence: TD-W6 (bridge :8787 not running; 8 skips), WS06 §3
- Current state: donor_bridge availability tests skip; bridge server not running
- Target state: documented bridge startup/ops; availability tests pass or explicitly skip with reason
- Affected files: `donor_bridge/squeeze_client.py`, ops docs
- Dependencies: none
- Strategy: ops SOP + verified startup path
- Safety risk: none · Regression risk: low
- Tests required: availability tests with server running (local)
- Runtime validation: start bridge; run donor_bridge suite
- Documentation required: bridge ops SOP
- Acceptance criteria: squeeze bridge availability no longer silently skips; SOP documented
- Wave: 4

---

## WAVE 5 — Multi-Asset Product Domains

### BL-0501 Bonds domain (RC-015)
- Priority: **P2** · Type: BONDS/MULTI_ASSET · Complexity: L · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0103, BL-0105)
- Authorized requirements: Bonds/Fixed Income (MND-001)
- Evidence: MS-03, WS06 §3 (MISSING surface), XA-02 groundwork
- Current state: FRED/ALFRED vertical + XA-02; no instruments, no surface, no portfolio
- Target state: structural integration: identity (BL-0103) + provider path (FRED) + research/workspace surface (rates/curve/duration) + portfolio compatibility (BL-0105) + tests + truthful status
- Affected files: new `bonds/*` modules, `xa02/*` reuse, `ui` Bonds route/lane, API routes
- Dependencies: BL-0103, BL-0105, BL-0402 (provider evidence)
- Strategy: identity → data path → analytics → surface → portfolio
- Safety risk: low · Regression risk: medium
- Tests required: bond domain tests (curve, duration, yield↔price), portfolio compatibility, UI truthfulness
- Runtime validation: domain suite
- Documentation required: bonds product doc
- Acceptance criteria: Bonds has discoverable navigation, research workflow, portfolio-compatible positions, tests, truthful status (per 18 structural line)
- Wave: 5

### BL-0502 Crypto domain (RC-015)
- Priority: **P2** · Type: CRYPTO/MULTI_ASSET · Complexity: L · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0102, BL-0105)
- Authorized requirements: Crypto (MND-002)
- Evidence: MS-04, WS06 §3 (MISSING), planning docs exist (CRYPTO_*)
- Current state: LaneId + planning docs only
- Target state: identity (BL-0102) + research/workspace surface (pairs, 24/7 semantics) + portfolio compatibility (BL-0105) + provider path (exchange TBD — D14 open) + tests
- Affected files: new `crypto/*` modules, `xa01` (done in BL-0102), `ui` Crypto route/lane, market-session 24/7 handling
- Dependencies: BL-0102, BL-0105
- Strategy: identity → session semantics → surface → portfolio; provider committed later (D14)
- Safety risk: low · Regression risk: medium
- Tests required: crypto identity, 24/7 freshness, portfolio compat, UI truthfulness
- Runtime validation: domain suite
- Documentation required: crypto product doc
- Acceptance criteria: Crypto has identity, research surface, portfolio-compatible positions, tests, truthful status; provider choice explicit (DECISION_REQUIRED/OPEN documented)
- Wave: 5

### BL-0503 Gold/Silver visible domains (RC-015)
- Priority: P3 · Type: COMMODITIES/MULTI_ASSET · Complexity: M · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0104, BL-0105)
- Authorized requirements: Gold (MND-006), Silver (MND-007) — explicitly visible
- Evidence: MS-05/06, WS06 §3 (MISSING)
- Current state: GC/SI keys in xa03/eia only
- Target state: first-class visible domains over commodity primitives (spot/futures/ETF relationships, portfolio exposure, surface)
- Affected files: `xa03/*`, `eia/cross_asset.py`, new commodity surfaces, `ui` routes
- Dependencies: BL-0104, BL-0105
- Strategy: identity → exposure analytics → surface
- Safety risk: low · Regression risk: low
- Tests required: gold/silver identity + exposure tests
- Runtime validation: domain suite
- Documentation required: commodities product doc
- Acceptance criteria: Gold and Silver appear as named domains (never hidden under generic commodities) with research + portfolio relevance
- Wave: 5

### BL-0504 Broader Commodities domain (RC-015)
- Priority: P3 · Type: COMMODITIES/MULTI_ASSET · Complexity: M · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0104, BL-0105)
- Authorized requirements: Broader Commodities (MND-008)
- Evidence: MS-07 (energy groundwork only)
- Current state: EIA/CFTC energy + CL/NG family registry
- Target state: commodity domain beyond energy (agriculture/industrial metals as roadmap), portfolio exposure, surface
- Affected files: `eia/*`, `cftc/*`, `futures/families/registry.py`, surfaces
- Dependencies: BL-0104, BL-0105
- Strategy: extend energy groundwork; explicit roadmap for ag/metals
- Safety risk: low · Regression risk: low
- Tests required: commodity identity/registry tests
- Runtime validation: energy domain suite
- Documentation required: commodities product doc
- Acceptance criteria: Broader Commodities has a coherent domain home with energy complete and ag/metals explicitly roadmap'd (never silently dropped)
- Wave: 5

### BL-0505 Industry intelligence (RC-015)
- Priority: **P2** · Type: INDUSTRY · Complexity: M · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0101)
- Authorized requirements: Industry (MND-004)
- Evidence: MS-08, WS05 §39 (rides instrument metadata + evidence lanes; no new stack)
- Current state: absent (incidental mentions only)
- Target state: sector/industry as instrument-metadata dimension + evidence lane (peers, relative performance, supply chains via relationships)
- Affected files: `xa01` metadata extensions, `market_context/*`, new industry evidence lane, UI
- Dependencies: BL-0101
- Strategy: metadata → evidence lane → surface
- Safety risk: none · Regression risk: low
- Tests required: industry metadata + evidence tests
- Runtime validation: domain suite
- Documentation required: intelligence doc
- Acceptance criteria: Industry has a discoverable research surface built on instrument metadata + evidence (no separate data stack)
- Wave: 5

### BL-0506 Government policy/regulatory workflow (RC-015)
- Priority: P3 · Type: GOVERNMENT · Complexity: M · Parallelization: PARALLEL_SAFE (backend groundwork exists)
- Authorized requirements: Government/Public-Sector (MND-005)
- Evidence: MS-11, WS05 §40 (macro correct; policy workflow missing)
- Current state: FRED/CFTC/EIA/NOAA/SEC providers + PIT verticals; no user workflow
- Target state: policy/regulatory event workflow (release calendar, revision surfacing) as an evidence lane + surface
- Affected files: `market_context/macro.py`, `fred/*`, new policy lane, UI
- Dependencies: none (backend-ready)
- Strategy: release-calendar evidence lane → surface
- Safety risk: none · Regression risk: low
- Tests required: policy-lane tests (release/revision surfacing)
- Runtime validation: macro suite
- Documentation required: government product doc
- Acceptance criteria: Government has a user workflow surfacing FRED/COT/EIA/NOAA/SEC data with revision semantics
- Wave: 5

---

## WAVE 6 — Intelligence Product Completion

### BL-0601 Whale cockpit + elevated families (RC-015)
- Priority: P3 · Type: WHALE · Complexity: L · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0105 evidence chain unchanged)
- Authorized requirements: Whale/Large-Participant (MND-003)
- Evidence: D20 (which families elevate), WS06 §3 (no cockpit), SWIM_WITH_THE_WHALES doctrine
- Current state: fixture lanes + EDGAR gated; fusion exposure minimal in UI
- Target state: whale cockpit surface; elevate 13F/crowding/skill families to provider-backed lanes per doctrine; fusion participation visible
- Affected files: `participant/*`, `cross_lane/*`, `ui` whale surfaces, `sec_edgar/*`
- Dependencies: BL-0401 (capability evidence)
- Strategy: cockpit IA → family elevation → fusion surfacing
- Safety risk: none · Regression risk: low
- Tests required: elevated-family adapter tests, fusion participation tests
- Runtime validation: participant suite
- Documentation required: whale doctrine alignment
- Acceptance criteria: whale families have provider-backed lanes with truthful status; a cockpit surface aggregates them
- Wave: 6

### BL-0602 Market-context lane wiring (RC-018/D22)
- Priority: P3 · Type: RESEARCH/UI_UX · Complexity: M · Parallelization: PARALLEL_SAFE
- Authorized requirements: Market Context / News (B/C/E)
- Evidence: DEL-02, FC-17, API-004 (backend engines real; no lane)
- Current state: `/workspace/:symbol/market-context` backend route; no lane registry entry
- Target state: market-context as a real workspace lane (sentiment/event/expectation surfaced); route↔registry parity
- Affected files: `laneRegistry.ts`, `App.tsx`, `ui/src/components/marketcontext/*`, endpoints/hooks
- Dependencies: none
- Strategy: lane → panel → parity test
- Safety risk: none · Regression risk: low
- Tests required: lane-registry parity test, panel rendering tests
- Runtime validation: ui suite
- Documentation required: product IA
- Acceptance criteria: market-context is reachable from the workspace with provenance-tagged payloads; registry/route/test parity holds
- Wave: 6

### BL-0603 News/research surface completeness (RC-015)
- Priority: P3 · Type: RESEARCH/NEWS · Complexity: M · Parallelization: PARALLEL_SAFE
- Authorized requirements: News/Research (Tier E/B/C)
- Evidence: WS06 §3 (research READ_ONLY), 05 (news 5 tests), MARKET_CONTEXT audit deficiencies 1–10
- Current state: news aggregator + providers gated; research surfaces read-only
- Target state: research workflows completed for entity resolution, surprise, reaction on live data (as data arrives); news surfaces truthful
- Affected files: `news/*`, `market_context/*`, `research/*`, UI
- Dependencies: BL-0402 (provider evidence)
- Strategy: fill documented deficiencies in dependency order
- Safety risk: none · Regression risk: low
- Tests required: entity-resolution + surprise + reaction tests
- Runtime validation: market_context suite
- Documentation required: research doc
- Acceptance criteria: research/news surfaces render provider-backed or explicitly FIXTURE_ONLY data with provenance
- Wave: 6

---

## WAVE 7 — Frontend / API / Product Convergence

### BL-0701 Mode-scoped query-key factory (RC-011)
- Priority: **P2** · Type: UI_UX/STATE · Complexity: M · Parallelization: PARALLEL_SAFE
- Authorized requirements: Demo/Paper/Live state integrity (Tier E)
- Evidence: ARCH-005, SAFE-002, UX-009/UX-010, TD-A11/TD-UE2, CON-04, D23
- Current state: `["workspace", symbol, lane]` keys; mode read inside hooks
- Target state: query-key factory with mode/account/provider/as-of dimensions; scrub invalidates lane keys; isolation test
- Affected files: `ui/src/api/hooks.ts`, `ui/src/api/queryKeys.ts` (new), `queryKeys.test.ts`
- Dependencies: none
- Strategy: factory → migrate keys → invalidations → tests
- Safety risk: none · Regression risk: medium (cache semantics); mitigate
- Tests required: query-key isolation test (mode × account × symbol × lane), scrub-invalidation test
- Runtime validation: ui suite
- Documentation required: frontend state doc
- Acceptance criteria: mode switch cannot reuse another mode's lane data; scrub invalidates lanes; keys provably distinct per dimension
- Wave: 7

### BL-0702 Canonical error taxonomy (RC-010)
- Priority: **P2** · Type: API · Complexity: M · Parallelization: PARALLEL_SAFE
- Authorized requirements: API contract integrity (Tier E)
- Evidence: API-004, TD-AP1, CON-03, D24 (12 target categories)
- Current state: ad-hoc reason codes; frontend string-parses
- Target state: canonical taxonomy enum (12 categories) backend + typed frontend union; existing codes mapped
- Affected files: `ui_api/errors.py` (new), `server.py` handlers, `ui/src/api/errors.ts`, tests
- Dependencies: none
- Strategy: additive enum → map codes → typed frontend
- Safety risk: low · Regression risk: medium; API tests
- Tests required: error-taxonomy round-trip tests, mapping tests
- Runtime validation: ui1/ui2 suites
- Documentation required: API doc
- Acceptance criteria: every backend error emits a canonical category; frontend has a typed union; no string-parsing of codes
- Wave: 7

### BL-0703 Generated/shared API contracts (RC-010)
- Priority: **P2** · Type: API/FRONTEND · Complexity: L · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0702)
- Authorized requirements: API contract integrity (Tier E)
- Evidence: ARCH-007, UX-011, API-005/006, TD-A10/TD-UE3, CON-02, D25
- Current state: 2,000-line manual Zod; passthrough erosion; schema-less `/explain`/`/inspect`
- Target state: generated/shared contracts (OpenAPI from backend projection builders or typed contract package); schemas.test.ts retained as interim guard; nullable/versioning rules
- Affected files: backend projection builders, contract generation tooling, `ui/src/api/schemas.ts`, `schemas.test.ts`
- Dependencies: BL-0702
- Strategy: generate initial contract → migrate frontend → retire manual schemas incrementally
- Safety risk: none · Regression risk: medium; contract parity tests
- Tests required: contract parity tests (backend serialization ↔ frontend schemas), schema-drift regression
- Runtime validation: ui + ui1/ui2 suites
- Documentation required: API contract doc
- Acceptance criteria: frontend types derive from backend contract source; drift is compile-time caught; `/explain`/`/inspect` typed
- Wave: 7

### BL-0704 Multi-asset instrument selector (RC-015/004)
- Priority: P3 · Type: UI_UX/MULTI_ASSET · Complexity: L · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0101, BL-0701)
- Authorized requirements: multi-asset product (Tier E/B/C)
- Evidence: 07 §28 (equity symbol input insufficient for contracts/pairs/bonds), WS06 product inputs
- Current state: `LiveSymbolLookup` searches any string; no asset-aware selector
- Target state: asset-aware instrument selector (equity ticker / option contract / futures contract / bond / crypto pair) resolving through identity
- Affected files: `ui/src/components/discover/LiveSymbolLookup.tsx`, workspace routes, hooks
- Dependencies: BL-0101, BL-0701
- Strategy: identity-backed selector component → route param migration
- Safety risk: none · Regression risk: medium
- Tests required: selector resolution tests per asset class
- Runtime validation: ui suite
- Documentation required: product IA
- Acceptance criteria: users can discover/select any authorized instrument class through one selector; workspace routes resolve contracts not bare symbols
- Wave: 7

### BL-0705 Product IA / navigation restructure (RC-015)
- Priority: P3 · Type: UI_UX · Complexity: L · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0704)
- Authorized requirements: integrated-platform mandate (LATER-006); approved dashboard direction
- Evidence: 07 §3/§4, §28 (Dashboard/Markets/Research/Portfolio/Trading/Orders/Analytics/Intelligence/Settings shape); no silos
- Current state: mode-routed launcher + 11 workspace lanes; new domains absent
- Target state: top-level IA (Dashboard, Markets, Research, Portfolio, Trading, Orders, Analytics, Intelligence, Settings) with asset workflows nested; no Equity/Options/Futures/Crypto/Bond Apps as silos
- Affected files: `ui/src/App.tsx`, NavShell, route registry
- Dependencies: BL-0704, BL-0501..0506 (domain surfaces)
- Strategy: IA map → navigation → route migration
- Safety risk: none · Regression risk: medium; route tests
- Tests required: navigation/route tests, lane-registry parity
- Runtime validation: ui suite
- Documentation required: product IA doc
- Acceptance criteria: navigation reflects the authorized product structure; all domains reachable; dashboard compact+exceptions preserved
- Wave: 7

### BL-0706 Route↔lane registry drift guard (RC-020)
- Priority: P3 · Type: UI_UX/TESTING · Complexity: S · Parallelization: PARALLEL_SAFE
- Authorized requirements: UI maintainability
- Evidence: UX-007, TEST-004 (registry internal-only; App routes hard-coded)
- Current state: 11 explicit `<Route>`s + separate laneRegistry; no parity test
- Target state: registry is the single lane source; App routes derive or a test asserts parity
- Affected files: `ui/src/App.tsx`, `ui/src/laneRegistry.ts`, tests
- Dependencies: none
- Strategy: parity test first; then derive routes
- Safety risk: none · Regression risk: low
- Tests required: route↔registry parity test
- Runtime validation: ui suite
- Documentation required: none
- Acceptance criteria: adding a lane to the registry without a route (or vice versa) fails a test
- Wave: 7

### BL-0707 Loading/error/stale UX + next_action surfacing (RC-010)
- Priority: P3 · Type: UI_UX · Complexity: S · Parallelization: PARALLEL_SAFE
- Authorized requirements: truthful UX (Tier E)
- Evidence: UX-002/003/012, OPS-002, TD-OP1, TD-UE5
- Current state: honest but often non-actionable unavailable states; staleness limited to squeeze readiness
- Target state: empty/error states surface operator `next_action`; staleness chips where operationally important (per controller §15)
- Affected files: `ui/src/components/*`, readiness surfaces
- Dependencies: none
- Strategy: wire readiness next_action into panels
- Safety risk: none · Regression risk: low
- Tests required: error-state rendering tests
- Runtime validation: ui suite
- Documentation required: none
- Acceptance criteria: every Unavailable state points to an action or an honest "why" (gate/provider/entitlement)
- Wave: 7

### BL-0708 Accessibility fixes (RC-020)
- Priority: P3 · Type: UI_UX · Complexity: S · Parallelization: PARALLEL_SAFE
- Authorized requirements: product correctness
- Evidence: ACC-001 (modal focus trap missing; charts lack text alternatives)
- Current state: strong base; two concrete gaps
- Target state: focus trap in `LiveModeConfirmation`; chart summaries (aria-label/summary)
- Affected files: `ui/src/components/*`, chart components
- Dependencies: none
- Strategy: focus trap + chart alternatives
- Safety risk: none · Regression risk: low
- Tests required: focus-trap test, chart-summary assertion
- Runtime validation: ui suite
- Documentation required: none
- Acceptance criteria: modal traps focus; charts have text alternatives
- Wave: 7

### BL-0709 Truthfulness polish (RC-010)
- Priority: P3 · Type: UI_UX · Complexity: XS · Parallelization: PARALLEL_SAFE
- Authorized requirements: truthful UI
- Evidence: UX-001 (BIYA/REPLAY hardcoded), UX-005 (draft refresh drops provenance), UX-008 (thin post-submit confirmation), TD-UE4/TD-UE6
- Current state: minor truthfulness/UX gaps
- Target state: demo label from context payload; draft-refresh note; explicit order-accepted confirmation
- Affected files: `DemoNowPage`, workspace draft carry, OrderTicket
- Dependencies: none
- Strategy: small targeted fixes
- Safety risk: none · Regression risk: low
- Tests required: component tests
- Runtime validation: ui suite
- Documentation required: none
- Acceptance criteria: no instrument-specific sample labels in markup; draft carry documents refresh behavior; submit gives explicit acceptance feedback
- Wave: 7

---

## WAVE 8 — Developer-System / Performance / Cleanup

### BL-0801 Validation performance split (RC-017)
- Priority: P3 · Type: PERFORMANCE · Complexity: L · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0002..0004)
- Authorized requirements: developer feedback loop
- Evidence: PERF-001, TD-TS3; **G15 measured** `artifacts/g15-validation-performance.json` (FAST 4.1s · CHANGED 453.6s · FULL 539.0s · E2E 68.8s)
- Current state: serial GLOBAL_STATE_MUTATION + heavy fixture loads; G15 isolated E2E from FAST/FULL/CHANGED
- **G15 status:** MEASURED (not closed — no manifest partition yet)
- Target state: split platform/ui1 by concern; raise heavy-worker count on resource-safe runners; cache immutable preparation; re-measured time with equal coverage
- Affected files: `tools/validation_manifest.json`, `tools/validate.py`, CI runner config
- Dependencies: BL-0002..0004
- Strategy: split suites (GLOBAL_STATE_MUTATION → smaller scoped suites), session-scope expensive fixtures, worker tuning
- Safety risk: none · Regression risk: medium (manifest changes); validation-gate tests
- Tests required: manifest self-validation; re-measured FULL comparison
- Runtime validation: FULL re-run
- Documentation required: performance note
- Acceptance criteria: FULL time reduced with test count equal-or-higher; no coverage reduction
- Wave: 8

### BL-0802 Real E2E suite (RC-016)
- Priority: **P2** · Type: TESTING · Complexity: L · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0201)
- Authorized requirements: end-to-end proof (TEST-001)
- Evidence: TEST-001; **G15** `e2e/` Playwright + `tools/e2e/harness.py` + `validate e2e` gate · [14m-g15-current-state-matrix.md](14m-g15-current-state-matrix.md)
- Current state: **CLOSED (G15)** — browser Paper equity + derivative + isolation + live-safety acceptance green
- **G15 status:** CLOSED
- Target state: Playwright (or equivalent) E2E for the Paper workflow: launch → mode → research → draft → preview → submit → monitor → portfolio; account switching; cancel; manifest `e2e` classification
- Affected files: new `e2e/` tree, manifest, CI job (gated)
- Dependencies: BL-0201 (server binding makes E2E meaningful)
- Strategy: E2E harness → core workflow → CI gating
- Safety risk: none · Regression risk: low
- Tests required: the E2E suite itself
- Runtime validation: local E2E run; CI gated
- Documentation required: E2E SOP
- Acceptance criteria: E2E covers the full Paper loop; CI runs it (or documents the gate); no fixture masquerading as live
- Wave: 8

### BL-0803 Dead-route archive/deprecate (RC-018)
- Priority: P3 · Type: API/CLEANUP · Complexity: S · Parallelization: PARALLEL_SAFE
- Authorized requirements: API maintainability
- Evidence: DEL-01/05, TD-AP2, D21; **G15** `artifacts/g15-dead-route-census.json` + deprecation headers on legacy GET `/paper/*` reads
- Current state: census complete; **ARCHIVE_FIRST** deprecation on legacy GET surfaces; `/paper/orders` POST **ACTIVE**; `/capabilities` global route deprecated (instrument-scoped path canonical)
- **G15 status:** ARCHIVE_FIRST complete (no destructive removal)
- Target state: deprecation headers + route log; removal after caller census
- Affected files: `ui_api/server.py`
- Dependencies: none
- Strategy: census → deprecate → remove
- Safety risk: low · Regression risk: medium; ui1/ui2 verification
- Tests required: caller census; ui1/ui2 run
- Runtime validation: ui1/ui2
- Documentation required: API doc
- Acceptance criteria: no frontend/test caller remains before removal; deprecated routes log clearly
- Wave: 8

### BL-0804 src→tools inversion + CORS tighten (RC-018)
- Priority: P3 · Type: API · Complexity: S · Parallelization: PARALLEL_SAFE
- Authorized requirements: API architecture
- Evidence: API-001/002, TD-AP3 (control_service import; `*` CORS)
- Current state: `src/ui_api` imports `tools.platform.control_service`; unbounded CORS
- Target state: control service under `src` (or clean inversion); CORS loopback-only
- Affected files: `ui_api/server.py`, `tools/platform/control_service.py` (move), tests
- Dependencies: none
- Strategy: move/invert → tighten CORS → tests
- Safety risk: none · Regression risk: medium
- Tests required: CORS header test, import-direction test
- Runtime validation: ui1/ui2
- Documentation required: none
- Acceptance criteria: no `src→tools` import edge in ui_api; CORS restricted to loopback
- Wave: 8

### BL-0805 Repository hygiene cleanup (RC-019)
- Priority: P3 · Type: CLEANUP · Complexity: XS · Parallelization: PARALLEL_SAFE
- Authorized requirements: repository clarity
- Evidence: REPO-002/003, DEL-03/04
- Current state: empty pytest dirs; stale child CI copies
- Target state: dirs removed; CI pointer present
- Affected files: parent root + child `.github/`
- Dependencies: none
- Strategy: remove/point per 17 §1/§2
- Safety risk: none · Regression risk: low
- Tests required: find census; CI check
- Runtime validation: parent CI
- Documentation required: pointer
- Acceptance criteria: no empty pytest dirs; no unlabeled stale CI copies
- Wave: 8

### BL-0806 Mongo optionality documentation (RC-018)
- Priority: P3 · Type: DEPENDENCY · Complexity: XS · Parallelization: PARALLEL_SAFE
- Authorized requirements: dependency clarity
- Evidence: DEP-001, DEL-07, D29 (SQLite canonical; Mongo optional)
- Current state: pymongo repos exist; docs ambiguous
- Target state: Mongo explicitly documented as optional alternate persistence; SQLite canonical; install guidance
- Affected files: README, docs
- Dependencies: none
- Strategy: documentation
- Safety risk: none · Regression risk: none
- Tests required: none
- Runtime validation: n/a
- Documentation required: dependency doc
- Acceptance criteria: README states SQLite canonical + Mongo optional; no doc implies Mongo required
- Wave: 8

### BL-0807 Docs consolidation completion (RC-020)
- Priority: P3 · Type: DOCUMENTATION · Complexity: S · Parallelization: PARALLEL_SAFE
- Authorized requirements: documentation ownership
- Evidence: DOC-004/007, DEV-006, CON-07/09
- Current state: ADR triplication (BL-0010), rules duplication (BL-0009), historical-by-design specs
- Target state: one canonical ADR owner; rules de-duplicated; docs-link valid
- Affected files: docs tree
- Dependencies: BL-0009, BL-0010
- Strategy: execute ownership consolidations
- Safety risk: none · Regression risk: none
- Tests required: docs-link validator
- Runtime validation: n/a
- Documentation required: consolidation itself
- Acceptance criteria: no rule text duplicated verbatim; ADRs single-owned; links 162/162
- Wave: 8

---

## WAVE 9 — Production Hardening / Final Acceptance

### BL-0901 Provider canaries + failure testing (RC-009/016)
- Priority: P3 · Type: OPERABILITY/RELIABILITY · Complexity: L · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0401/0402)
- Authorized requirements: production readiness (MS-09; 53 §criteria)
- Evidence: 04 §10 (production readiness ~29%), 06 §49/§57, WS06 §18a
- Current state: no canary; failure modes tested at unit level
- Target state: per-provider canary gates (documented, live-gated), failure-injection tests (disconnect, entitlement loss, rate limit, reconnect), observability acceptance
- Affected files: `tests/live_*`, ops docs, readiness surfaces
- Dependencies: BL-0401, BL-0402
- Strategy: canary harness → failure tests → acceptance
- Safety risk: LOW (gates closed in CI) · Regression risk: low
- Tests required: failure-injection tests
- Runtime validation: live-gated canary runs
- Documentation required: ops acceptance records
- Acceptance criteria: each provider has a canary; failure modes behave fail-closed with visible reasons (06 §49 table)
- Wave: 9

### BL-0902 Operational acceptance + documentation closure (RC-014/020)
- Priority: P3 · Type: OPERABILITY/DOCUMENTATION · Complexity: M · Parallelization: PARALLEL_AFTER_DEPENDENCY (all Waves 0–8)
- Authorized requirements: production-readiness documentation (53)
- Evidence: 04 §10, 07 §20 (no false claims — preserve)
- Current state: honest disclaimers; operating procedures partial
- Target state: documented operating procedures (startup, mode transitions, provider ops, recovery, incident), security posture, completion records closed
- Affected files: docs tree, PROGRAM_STATUS
- Dependencies: Wave 0–8 acceptance
- Strategy: ops docs per acceptance evidence
- Safety risk: none · Regression risk: none
- Tests required: docs-link validator
- Runtime validation: n/a
- Documentation required: the closure itself
- Acceptance criteria: operating procedures exist for every live path; no claim exceeds evidence
- Wave: 9

### BL-0903 Safety-register regression suite completion (RC-016)
- Priority: P3 · Type: TESTING · Complexity: L · Parallelization: PARALLEL_AFTER_DEPENDENCY (BL-0201..0207, BL-0302/0303)
- Authorized requirements: safety regression coverage (06 §67)
- Evidence: TEST-002 gaps (query-key isolation, stale preview, replace, late-fill, L2 stale, IBKR entitlement, multi-asset identity/portfolio, BP)
- Current state: critical gaps listed in 06 §55/§67
- Target state: every §67 register item has a regression suite in the manifest
- Affected files: tests tree + manifest
- Dependencies: the features under test (Wave 2/3/5)
- Strategy: add suites per 06 §55 as features land
- Safety risk: none · Regression risk: none
- Tests required: the added suites
- Runtime validation: full validation
- Documentation required: testing map update
- Acceptance criteria: §67 register fully covered; FULL includes the new suites and stays clean
- Wave: 9

---

## Backlog quality gate (64 §master backlog gate)

- Every P1 finding has an owner: AB-001 → BL-0105; AB-002 → BL-0301; AB-003 → BL-0302; P1-1 → BL-0301/0304; P1-2 → BL-0105. ✓
- Every authorized missing core domain has a path: BL-0501..0506 (+BL-0601..0603). ✓
- Every stale donor-governance item has a correction: BL-0001 (+BL-0011). ✓
- Every architecture blocker maps to implementation: AB-001..008 → BL-* above. ✓
- Every major deletion candidate has disposition: 17 §1. ✓
- Every consolidation candidate has target ownership: 17 §3. ✓
- Every critical missing test maps to work: BL-0903 + per-feature test fields. ✓
- Every major API/UX gap maps to work: BL-0701..0709, BL-0803/0804. ✓
- Every open product decision is explicit: 14 (post-WS07 status in 14 file). ✓
- Every item has acceptance criteria (non-placeholder). ✓
- Every item belongs to a wave. ✓

## Summary counts

| Priority | Count | Notes |
|---|---|---|
| P0 | 0 | no destructive/safety defects found (WS04–WS06) |
| P1 | 3 | BL-0105 (multi-asset portfolio), BL-0301 (IBKR adapter), BL-0302 (depth engine) — the three WS05 blockers AB-001/002/003 as implementation work |
| P2 | 25 | listed above |
| P3 | 40 | listed above |
| P4 | 0 | none raised |

Total: 68 items across 10 waves (Wave 0: 12, Wave 1: 8, Wave 2: 9, Wave 3: 6,
Wave 4: 5, Wave 5: 6, Wave 6: 3, Wave 7: 9, Wave 8: 7, Wave 9: 3).