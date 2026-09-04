# BUILD 25 Known Limitations Register

Each limitation is explicitly non-blocking unless marked otherwise.

## KL-001 — No live broker execution authorization

- **Scope:** Execution plane
- **Why it exists:** BUILD 01–25 intelligent-engine program is paper-only by design
- **Risk:** Cannot validate real broker fill semantics or latency
- **Mitigation:** PAPER execution path fully tested; live adapters rejected at policy layer
- **What would close it:** Separate live-execution authorization campaign
- **Blocking:** no

## KL-002 — Moomoo/IBKR unavailable in cloud/replay acceptance

- **Scope:** Provider plane
- **Why it exists:** Live broker sessions require credentials and external infrastructure
- **Risk:** Provider disconnect semantics validated via fixtures only
- **Mitigation:** Replay fault machinery and quality engine tests
- **What would close it:** Provider expansion campaign with live soak tests
- **Blocking:** no

## KL-003 — Mongo parity optional

- **Scope:** Persistence
- **Why it exists:** MongoDB is opt-in via `IMP_TEST_MONGODB_URI`
- **Risk:** Backend-specific ordering edge cases may differ
- **Mitigation:** InMemory reference backend; mongo schema/integration tests when available
- **What would close it:** Mandatory Mongo in CI with parity acceptance subset
- **Blocking:** no

## KL-004 — Production fusion path may abstain in control-only state

- **Scope:** Intelligence plane BUILD 14
- **Why it exists:** Default fusion path requires specialist evidence pipeline completion
- **Risk:** End-to-end live-like forecast generation not exercised in all acceptance fixtures
- **Mitigation:** BUILD 14 unit tests; golden lifecycle uses champion fixture forecasts
- **What would close it:** Forward shadow campaign with production fusion enabled
- **Blocking:** no

## KL-005 — True prediction attempt denominator unavailable

- **Scope:** Evaluation metrics
- **Why it exists:** Selectivity denominators require production attempt logging not yet wired
- **Risk:** Some diagnostic ratios are informational only
- **Mitigation:** Brier/log-loss metrics on labeled cohorts
- **What would close it:** Production observability campaign
- **Blocking:** no

## KL-006 — Historically bounded LLM unavailable for live replay

- **Scope:** BUILD 19 temporal knowledge firewall
- **Why it exists:** No historically clean bounded LLM provider in fixture environment
- **Risk:** Firewall tested via synthetic profiles, not live model calls
- **Mitigation:** Adversarial profile tests A08 and knowledge firewall unit suite
- **What would close it:** Bounded historical LLM fixture provider
- **Blocking:** no

## KL-007 — Paper fill model intentionally simplified

- **Scope:** BUILD 22 paper execution
- **Why it exists:** Internal simulation uses replay bars, not full market microstructure
- **Risk:** Fill prices may differ from production broker models
- **Mitigation:** Deterministic fill rules; no lookahead in quote selection
- **What would close it:** Enhanced simulator campaign
- **Blocking:** no

## KL-008 — No monitoring daemon or external alert delivery

- **Scope:** BUILD 23 governance
- **Why it exists:** Governance plane is library/service-level, not operational infrastructure
- **Risk:** Telemetry storms tested in-process only
- **Mitigation:** Adaptation dedup/cooldown policies; A22 storm scenario
- **What would close it:** Production observability infrastructure campaign
- **Blocking:** no

## KL-009 — Performance figures are local-development baselines only

- **Scope:** BUILD 25 acceptance
- **Why it exists:** Acceptance runs on developer machine, not production hardware
- **Risk:** Cannot infer production SLOs from BUILD 25 timings
- **Mitigation:** Informational runtime recording in acceptance metadata
- **What would close it:** Dedicated performance campaign with controlled hardware
- **Blocking:** no

## KL-010 — Platform UI validation errors may remain pre-existing

- **Scope:** Platform/UI suites
- **Why it exists:** UI_STORE_SOURCE_MISSING and related issues predate BUILD 25
- **Risk:** UI projection gaps do not affect intelligent-engine scientific integrity
- **Mitigation:** Intelligence acceptance isolated from UI optional failures
- **What would close it:** UI operator console campaign
- **Blocking:** no
