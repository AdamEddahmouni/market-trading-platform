# 10 — Technical Debt Register

Status: **WS03 PASS + WS04 current-state pass (2026-09-06/07)**.
WS03 covered provenance debt; WS04 adds current-state debt categories below
(product-correctness debt still lands with WS05/WS06). Reconciles with IMP's
own `docs/engineering/TECH_DEBT.md` (which already carries TD-001..TD-007 and
related entries) rather than duplicating it.

Severity: P0 (immediate) · P1 (high) · P2 (medium) · P3 (low) · P4 (informational).

## WS04 current-state debt additions (categories per controller §51)

| ID | Category | Severity | Item | Evidence | Proposed handling |
|---|---|---|---|---|---|
| TD-W1 | MISSING_PROVIDER / MISSING_RUNTIME_PATH | P1 | IBKR Level-1 + Level-2 runtime data integration for CVD absent (professor-required, LATER-002). Observational L1 tooling exists (`tools/ibkr`, 8/24) but has no L2 depth and is not wired to the CVD lane | `tools/ibkr/*` (no reqMktDepth), `order_flow/*` fixture-first; live CVD only via Moomoo (gated) | WS07 COMPLETE backlog; WS05 correctness boundary (P1-1 = MS-01) |
| TD-W2 | MULTI_ASSET_BLOCKER | P1 | Authoritative portfolio/risk ledger is equity-share-only; options ledger separate; no futures/bonds/crypto/gold/silver/commodity position semantics | `portfolio/ledger.py` (position_shares), `portfolio/options_ledger.py` | WS05 multi-asset portfolio/risk design (P1-2 = MS-02) |
| TD-W3 | MISSING_PROVIDER | P2 | No verified live provider wire for any lane (EVIDENCE-01B implemented but not operationally accepted; G1–G6 closed); broker paper fixture-first | PROGRAM_STATUS §Live-readiness; `.env.example` gates; `docs/engineering/FORWARD_VALIDATION_READINESS_CHECKLIST.md` | WS06 provider-readiness campaign |
| TD-W4 | MISSING_RUNTIME_PATH | P2 | New mandated domains (Bonds, Crypto, Gold, Silver, Commodities, Industry) absent as product capability; roadmap predates mandate | zero src matches; MASTER_ROADMAP grep | WS07 backlog; roadmap update (MS-13) |
| TD-W5 | STUB | P3 | `OptionChainProvider` / `FuturesChainProvider` are protocols without live implementations (fixture adapters only) | `providers/contracts.py`; `providers/adapters/*` | WS07 provider increment |
| TD-W6 | BROKEN_WORKFLOW | P3 | Squeeze/Futures donor-bridge servers not running at :8787/:8788 → availability tests skip | full-receipt skip_details; `donor_bridge` 8 skips | WS06 bridge runtime ops |
| TD-W7 | FIXTURE_ONLY | P3 | Order-flow/options/futures/whale lanes rely on admitted research fixtures (PIT-aligned) | `tests/fixtures/providers/*` admission manifests | WS06 fixture-regeneration SOP (extends TD-P7) |
| TD-W8 | UI_BACKEND_GAP | P3 | No UI lanes/pages for Bonds/Crypto/Gold/Silver/Commodities/Industry/Government; API has no routes for them either | `laneRegistry.ts` (11 lanes); `ui_api/server.py` | WS07 |
| TD-W9 | TEST_GAP / TOOLING | P3 | `validate changed` under-selects to 21 mandatory tests when the snapshot is embedded under `projects/` (path-prefix matches no suite globs) | WS04 changed run; WORK_LOG 2026-09-05 | WS06: map `projects/`-prefixed paths in the monorepo embedding |
| TD-W10 | PROVENANCE RECORD | P3 | WS03 integration map omitted the IBKR observational tooling (present since 8/24); records now corrected in 05 §6 | `4853df0`; `tools/ibkr/*` | re-verify provenance sweep at WS05 |
| TD-W11 | RELIABILITY | P3 | Pre-existing dirty `cross_lane/fusion.py` + `opportunity.py` keep one golden test failing in the working tree; excluded from audit baseline | `git diff`; full receipt (1 failure) | resolve/commit or isolate at WS05/06 |

Note on severity honesty (§45/§46): missing mandated domains are product-value
gaps (P2), not safety incidents; no P0 debt is raised. LIVE-001 blocked state
is not debt — it is a designed safety boundary.

| ID | Category | Severity | Item | Evidence | Proposed handling |
|---|---|---|---|---|---|
| TD-P1 | PROVENANCE / STALE_DOCUMENTATION | P2 | 9+ donor governance documents still treat GridIQ/DS-340W as legitimate donors (pre-Heller-correction): permissions record, ADR-GRIDIQ-001, phase gate, ADR-DONOR-001, DONOR_REUSE_MATRIX, GRID_IQ_NOTES, DS340W_NOTES, revision-3 donor plans, PROVIDER_DUPLICATION_AUDIT, fixture inventory | grep list in 03 §Documentation corrections | WS07 Wave 1: add superseded headers + correction context (preserve history, never delete) |
| TD-P2 | PROVENANCE / MIGRATION | P3 | `donor_patterns/` package name implies donor-derived code; contents are independent IMP lane formulas (CVD/options/futures/order-book/edgar) with honest docstrings | module docstrings | WS07: annotate namespace or restructure; zero behavior change |
| TD-P3 | PROVENANCE | P3 | `tests/gridiq/test_required_future_tests.py` name + docstring reference donor notes; behavior is independent-implementation conformance | file head | WS07: annotate as conformance harness (no test change) |
| TD-P4 | PROVIDER_COUPLING / MISSING | P2 | IB L1/L2 runtime adapter absent for scope-required CVD capability; also missing IBKR execution (LIVE-001 blocked) | zero IBKR client matches; README ADR table | WS04/WS05: record as MISSING scope gap → WS07 COMPLETE backlog |
| TD-P5 | STALE_DOCUMENTATION | P3 | short-squeeze snapshot manifest lag (manifest `78b7467` vs child `9de7b2f` vs plan `41f52bb`) | WS01 | WS06: snapshot refresh via guarded import |
| TD-P6 | DONOR_COUPLING | P3 | Donor runtime-state research bridges (`internship_client`, `squeeze_client`) read external donor state; isolated from execution path by P2-4 test | donor_bridge + isolation test | KEEP; re-verify isolation at WS06 |
| TD-P7 | FIXTURE_DEPENDENCY | P3 | Order-flow/options tests depend on research-only admitted fixtures (PIT-aligned to BIYA window); fixture regeneration path must stay documented | admission manifests | WS06: document fixture regeneration SOP |

No P0 provenance debt identified; TD-W1/TD-W2 are the first P1 current-state
debt items (missing required runtime data path + architecture blocker — both
product-delivery, not safety). Missing functionality beyond these is recorded
as MISSING_SCOPE in 04-current-state.md §7 and the WS07 backlog.

## WS05 architecture debt additions (categories per controller §90)

Status: **WS05 PASS (2026-09-07)** — from 06-architecture-correctness.md.
Each row maps to one ARCH-/TRD-/MA- root cause in 06 §63 (no duplicate
issues). Severity: P0 immediate · P1 high · P2 medium · P3 low.

| ID | Category | Severity | Item | Root cause (06 §63) | Proposed handling |
|---|---|---|---|---|---|
| TD-A1 | PROVIDER_ARCHITECTURE / MISSING_RUNTIME_PATH | P1 | IBKR L1/L2 CVD runtime adapter absent (observational tooling is L1-only, no depth, not wired to CVD) | ARCH-001 | WS07 increment: IB adapter seeded from `tools/ibkr` + depth engine (ADR-C-002) |
| TD-A2 | MULTI_ASSET / DOMAIN_MODEL | P1 | Authoritative portfolio/risk ledger equity-share-only; options ledger separate float; no multiplier/notional/margin semantics | ARCH-002 (MA-006) | WS07: canonical multi-asset portfolio (ADR-C-001) |
| TD-A3 | MULTI_ASSET / RELIABILITY | P1 | Level-2 book is snapshot-replacement only; no incremental depth events, no book reset/reconnect, no depth staleness | ARCH-003 (+ARCH-009) | WS07: incremental depth engine (ADR-C-003) |
| TD-A4 | IDENTITY / DOMAIN_MODEL | P2 | Two asset-class vocabularies (paper ASSET_CLASSES vs XaAssetClass); equity-defaulting instrument ref at the runtime boundary | ARCH-004 | WS07: consolidate vocabularies (ADR-C-004) |
| TD-A5 | TRADING_LIFECYCLE / STATE | P2 | Preview→submission binding absent server-side; replay cursor can move between preview and submit | TRD-001 (SAFE-001) | WS07: server preview tokens + fingerprint binding (ADR-C-005) |
| TD-A6 | RISK | P2 | Buying power DISPLAY_ONLY — no cash check in risk; instrument-kind not validated at submission | TRD-006 (SAFE-003) | WS07: cash/BP + instrument-kind enforcement (ADR-C-006) |
| TD-A7 | NUMERIC_CORRECTNESS | P2 | Options ledger float vs equity minor-int; futures roll/variation-margin/spread P&L float | MA-003 (ARCH-008) | WS07: single numeric base + Decimal/minor-units (ADR-C-001/-008) |
| TD-A8 | TRADING_LIFECYCLE | P2 | Partial fills one-shot (no working remainder); replace absent; late-fill-during-cancel unmodeled | TRD-003/004/005 | WS07: remainder + replace states (ADR-C-007) |
| TD-A9 | STATE / CACHE | P2 | Live order-book state has no staleness control and is presented `book_state_valid:True` unconditionally | ARCH-009 | WS07 (with ADR-C-003): depth TTL + quality in payload |
| TD-A10 | API / TESTING | P2 | Frontend zod schemas duplicate backend dict envelopes (no versioned contract); error contract string-based | ARCH-007 | WS06/07: typed error taxonomy + contract direction |
| TD-A11 | STATE | P3 | Frontend workspace lane query keys not mode-scoped | ARCH-005 (SAFE-002) | WS06: mode-scope lane keys + query-key isolation test |
| TD-A12 | CACHE / STATE | P3 | CVD cumulative delta has no session anchor/reset (series restarts on restart/rollover) | TRD-008 | WS07: session boundaries in series |
| TD-A13 | IDENTITY / MULTI_ASSET | P2 | XA-01 lacks CRYPTO class/kind; bond descriptor flat strings; gold/silver generic COMMODITY | MA-001/002/004 | WS07: identity extensions (ADR-C-010) |
| TD-A14 | OBSERVABILITY | P4 | No request-id header propagation; layered error codes not fully typed | ARCH-007 (partial) | WS06: request-id + typed error taxonomy |
| TD-A15 | RELIABILITY / CONCURRENCY | P3 | Idempotency relies on single-process route lock; keys not content-derived | TRD-002 | WS07: content-derived keys + per-ledger locking |

## WS06 product/engineering debt additions (categories per controller §91)

Status: **WS06 PASS (2026-09-07)** — from 07-product-engineering.md. Root
causes only; each row maps to one finding in 07 (no duplicate issues).
Severity: P0 · P1 · P2 · P3. No P0/P1 raised by WS06.

| ID | Category | Severity | Root cause | Finding (07) | Proposed handling |
|---|---|---|---|---|---|
| TD-UE1 | UX / MULTI_ASSET | P2 | No user surface or navigation for the six mandated later domains (Bonds, Crypto, Gold, Silver, Commodities, Industry) or a dedicated Government workflow; UI has no asset-aware instrument selector | UX-001/UX-002 (§3 product matrix) | WS07 backlog + shared-shell IA (never OUT_OF_SCOPE) |
| TD-UE2 | UX / STATE | P2 | Workspace lane query keys not mode-scoped → stale-data reuse and DEMO/PAPER/LIVE cache collision on mode switch | UX-009 (§11) | WS07: mode/account-scoped query-key factory + isolation test |
| TD-UE3 | FRONTEND / CONTRACTS | P2 | 2,000-line manually-synced Zod layer with enum drift, passthrough erosion (provider health/market state), and schema-less `/explain`/`/inspect` | UX-011 (§12) | WS07: generated/shared API contracts; keep schemas.test.ts interim |
| TD-UE4 | UX / TRADING_LIFECYCLE | P3 | No Replace affordance; working-remainder one-shot; post-submit confirmation thin; refresh drops carried draft state | UX-005/007/008 (§8/§10) | WS07: order-management UX w/ TRD-003..005 |
| TD-UE5 | UX / FRESHNESS | P3 | Stale presentation limited to squeeze readiness; operator-critical stale states not surfaced on now/portfolio surfaces | UX-012 (§13) | WS07: freshness chips where operationally important only |
| TD-UE6 | UX / TRUTHFULNESS | P3 | Demo dashboard hardcodes `BIYA / REPLAY` sample label in markup | UX-001 (§6) | WS07: move to context payload |
| TD-UE7 | ACCESSIBILITY | P3 | Modal focus not trapped (`LiveModeConfirmation`); charts lack text alternatives | ACC-001 (§24) | WS07: focus trap + chart summaries (product correctness) |
| TD-AP1 | API / CONTRACTS | P2 | Ad-hoc reason-code taxonomy; none of the target categories exist; frontend string-parses codes | API-004 (§16) | WS07: canonical error taxonomy + typed frontend union |
| TD-AP2 | API / DUPLICATION | P3 | `/paper/{account,positions,fills,risk,orders-GET}` + `/workspace/:symbol/market-context` + `/capabilities` have no frontend callers | API-004 (§15, DEL-01/02/05) | WS07: verify tests, then archive/deprecate; wire market-context lane or archive |
| TD-AP3 | API / OWNERSHIP | P3 | `src/ui_api` imports `tools.platform.control_service` (src→tools inversion); unbounded `Access-Control-Allow-Origin: *` | API-001/002 (§14) | WS07: move control service under src or invert; tighten CORS |
| TD-TS1 | TESTING / TOOLING | P2 | `validate changed` under-selects in three ways: (a) monorepo `projects/` prefix matches no globs (21 tests only); (b) `fixtures/`, `config/`, `tests/fixtures/` select nothing; (c) shared modules escalate bluntly; `full_suite_required` does not run the full suite | DEV-001/002 (§17) | WS07: prefix mapping + fixture/config ownership + rename flag + shared-module map |
| TD-TS2 | TESTING / E2E | P2 | No real E2E tests (mode launch → draft → preview → submit → portfolio); UI coverage is component-level Vitest only | TEST-001 (07 §18a) | WS07: E2E strategy decision (Playwright) for the Paper workflow |
| TD-TS3 | TESTING / PERF | P3 | FULL validation 451s dominated by serial GLOBAL_STATE_MUTATION suites (platform 106s, ui1 79s) + heavy fixtures (donor_bridge 83.5s) | PERF-001 (07 §24) | WS07: split platform/ui1; raise heavy workers on safe runners |
| TD-DV1 | DEV_TOOLING | P2 | Fresh-developer must know which tree is canonical (snapshot vs child repo vs worktree); `validate changed` only correct in child layout | DEV-003 (§19) | WS07: AGENTS.md canonical edit-tree statement + monorepo test |
| TD-DV2 | DEV_TOOLING | P3 | `imp.py env` always exits 0 (informational) — agents cannot gate on wrong Python/npm | DEV-004 (§19) | WS07: non-zero exit for hard prerequisites |
| TD-DV3 | DEV_TOOLING | P3 | Five parallel "current state" docs; rules repeated across AGENTS/.cursor/handbook/SOPs; ADRs in three homes | DEV-005/006, DOC-004 (§19/§20) | WS07: consolidate ownership, keep authority map |
| TD-DO1 | DOCUMENTATION | P2 | 9+ donor-governance docs still treat GridIQ/DS-340W as legitimate (pre-Heller correction) | DOC-003 (§20; TD-P1 carried) | WS07 Wave 1: superseded headers in place (never delete) |
| TD-DO2 | DOCUMENTATION | P3 | MASTER_ROADMAP predates the mandate (new domains absent) | DOC-005 (FC-16/MS-13) | WS07: roadmap refresh |
| TD-DP1 | DEPENDENCY | P3 | pymongo repositories are alternate persistence vs canonical SQLite; Mongo install cost for optional paths | DEP-001 (§21, DEL-07) | WS07: mark optional or isolate |
| TD-RP1 | REPOSITORY | P2 | Short-squeeze snapshot manifest is stale vs child HEAD vs plan (three truths); no resync during audit | REPO-001 (§22) | WS07: guarded snapshot refresh |
| TD-RP2 | REPOSITORY | P3 | Empty `pytest-equity-*` dirs; child-repo STALE CI workflow copies; `/capabilities` duplication | REPO-002/003 (§22, DEL-03/04/05) | WS07: cleanup + pointer |
| TD-PF1 | PERFORMANCE | P3 | Live-mode polling (2s×3 + 5s×2 when LIVE) over REST despite push feed existing | PERF-004 (§23) | WS07: push-first for live lane data |
| TD-OP1 | OPERABILITY | P3 | Read-only panels show `Unavailable` without operator `next_action` already present in readiness payload | OPS-002 (§24) | WS07: surface next_action in error/empty states |

No new P0/P1 debt raised by WS06 (WS05 architecture P1s TD-A1..A3 stand).
WS06 findings map to WS07 backlog/increments, not to standalone fixes.

## WS07 final reconciliation (2026-09-07)

Every debt row now owns exactly one master-backlog item (12); no separate
debt/backlog duplication remains. Disposition per row family:

| Debt family | WS07 disposition | Owner (backlog) |
|---|---|---|
| TD-W1/TD-A1/TD-P4 (IB L1/L2 missing) | convert to backlog | BL-0301/0304 (RC-002) |
| TD-W2/TD-A2 (equity-only portfolio) | convert to backlog | BL-0105 (RC-001) |
| TD-A3/TD-A9 (L2 snapshot-only + staleness) | convert to backlog | BL-0302/0303 (RC-003) |
| TD-A4/TD-A13 (vocabularies + identity) | convert to backlog | BL-0101..0104 (RC-004) |
| TD-A5 (preview binding) | convert to backlog | BL-0201 (RC-005) |
| TD-A6 (BP + instrument-kind) | convert to backlog | BL-0202/0203 (RC-006) |
| TD-A7/ARCH-008 (numeric base) | convert to backlog | BL-0106/0107 (RC-001) |
| TD-A8 (lifecycle) | convert to backlog | BL-0204..0206 (RC-007) |
| TD-A10/TD-AP1 (contracts/taxonomy) | convert to backlog | BL-0702/0703 (RC-010) |
| TD-A11/TD-UE2 (query keys) | convert to backlog | BL-0701 (RC-011) |
| TD-A12 (CVD anchors) | convert to backlog | BL-0208 (RC-003) |
| TD-A15 (idempotency) | convert to backlog | BL-0207 (RC-008) |
| TD-W3/MS-09 (live wires) | convert to backlog | BL-0402 (RC-009) |
| TD-W4/TD-W8/TD-UE1 (missing domains/surfaces) | convert to backlog | BL-0501..0506 (RC-015) |
| TD-W5 (chain providers) | convert to backlog | BL-0403/0404 (RC-009) |
| TD-W6 (bridge ops) | convert to backlog | BL-0405 (RC-015) |
| TD-W9/TD-TS1 (validate changed) | convert to backlog | BL-0002..0004 (RC-012) |
| TD-P1/TD-DO1 (donor governance) | convert to backlog | BL-0001 (RC-013) |
| TD-P5/TD-RP1/REPO-001 (snapshot) | convert to backlog | BL-0005 (RC-014) |
| TD-P2/TD-P3 (naming annotations) | convert to backlog | BL-0011 (RC-020) |
| TD-DO2 (roadmap) | convert to backlog | BL-0006 (RC-014) |
| TD-TS2 (E2E) | convert to backlog | BL-0802 (RC-016) |
| TD-TS3 (perf) | convert to backlog | BL-0801 (RC-017) |
| TD-DV1..DV3 (dev system) | convert to backlog | BL-0007/0008/0009/0010 (RC-014/020) |
| TD-AP2/AP3 (routes/inversion/CORS) | convert to backlog | BL-0803/0804 (RC-018) |
| TD-DP1 (Mongo) | convert to backlog | BL-0806 (RC-018) |
| TD-RP2 (hygiene) | convert to backlog | BL-0805 (RC-019) |
| TD-PF1 (polling) | convert to backlog | BL-0603 (RC-015) + PERF-004 note |
| TD-OP1 (next_action) | convert to backlog | BL-0707 (RC-010) |
| TD-UE3..UE7 (UX polish) | convert to backlog | BL-0707..0709 (RC-010/020) |
| TD-W7/TD-P6/TD-P7 (fixture/donor bridge) | retain (KEEP_AS_IS behavior) | no backlog item (not debt — designed research boundaries) |
| TD-W10 (provenance record) | close | corrected in 05 §6; no action |
| TD-W11 (dirty cross_lane) | close (environmental) | leave untouched per D8; excluded from baseline |

All P0: 0 · P1 rows are the three architecture P1s → BL-0105/0301/0302. No
row left without an owner; no duplicate ownership.