# 13 — Recovery Roadmap & Dependency-Aware Implementation Waves

Status: **COMPLETE (WS07, 2026-09-07)**. The definitive, dependency-aware
recovery plan converting the master backlog (12) into executable waves.
Supersedes the controller-suggested skeleton — WS01–WS06 evidence (esp. WS05
architecture blockers + WS06 product/engineering findings) justified the
ordering below.

Rules applied (controller §43/§65/§73): dependencies explicit; no work begins
before its foundation exists; high-risk migrations ordered safely;
parallel-safe work marked; product value visible per wave; validation defined
per wave; rollback/migration concerns stated; cleanup happens after
replacement, not before; no wave depends on undefined architecture.

---

## 1. Dependency graph (root cause level)

```text
RC-013/014/020 (program truth + docs)  ─┐  Wave 0 (parallel-safe)
RC-012 (validate changed)              ─┤
                                        │
RC-004 (identity vocabulary) ───────────┤  Wave 1 foundation
   ├─ RC-004 extensions (CRYPTO/Bond/Commodity)
   └─ RC-001 (multi-asset portfolio) ←──┘  SERIAL core
        └─ RC-008 (idempotency), RC-005 (preview binding)  Wave 2
             ├─ RC-006 (risk: BP + instrument-kind)   ← needs RC-004 + RC-001(cash)
             └─ RC-007 (lifecycle: remainder/replace) ← needs RC-005
RC-003 (depth engine) ────────────────┐  Wave 3 (buildable on fixtures)
RC-002 (IBKR adapter) ────────────────┴── depends on RC-003 for L2
RC-009 (provider registry + live wires) ← needs RC-002/003
RC-015 (missing domains) ──────────────── needs RC-004 + RC-001 + RC-009
RC-010/011 (API/frontend contracts+keys) ← parallel-safe; RC-011 independent
RC-016 (testing/E2E) ──────────────────── needs RC-005 for meaningful E2E
RC-017 (validation perf) ──────────────── after RC-012
RC-018/019 (cleanup) ──────────────────── after replacements
```

Key edges (what unblocks what):

```text
canonical instrument model (RC-004, BL-0101..0104)
  → multi-asset portfolio (RC-001, BL-0105)
    → cross-asset risk (RC-006 part, BL-0209)
    → multi-asset order model (BL-0203)
      → provider-backed execution (BL-0301, BL-0403/0404)

IB provider architecture (BL-0301)
  → IB L1/L2 (BL-0301) + incremental depth (BL-0302)
    → live CVD (BL-0304) + depth staleness (BL-0303)
      → CVD UX/live validation (BL-0601/0603, BL-0901)

validate-changed correctness (RC-012, BL-0002..0004)
  → trustworthy validation for every later change
    → validation performance (RC-017, BL-0801)

program truth (RC-013/014, BL-0001/0005/0006/0007)
  → clean baseline for architecture migration (professor-facing traceability)
```

## 2. Recovery waves (definitive)

### Wave 0 — Truth / Safety / Planning Corrections

| Field | Value |
|---|---|
| Goal | Establish a clean, truthful, trustable post-reconciliation baseline: correct donor-governance authority, working `validate changed`, true repo state, honest roadmap/dev docs. Zero architectural risk. |
| Major backlog items | BL-0001 (donor-governance supersession) · BL-0002 (validate changed prefix) · BL-0003 (fixture/config ownership) · BL-0004 (flag rename + shared-module map) · BL-0005 (SS snapshot refresh) · BL-0006 (roadmap refresh) · BL-0007 (edit-tree statement) · BL-0008 (env exit policy) · BL-0009 (handoff consolidation) · BL-0010 (ADR home) · BL-0011 (namespace annotations) · BL-0012 (evidence-homes doc) |
| Dependencies | none upstream |
| Parallel work | BL-0001/0005/0006/0007/0008/0009/0010/0011/0012 are PARALLEL_SAFE; BL-0002 is SERIAL foundation; BL-0003/0004 after BL-0002 |
| Product result | Truthful provenance, trustworthy local validation, honest roadmap — the foundation every later wave validates against. No user-visible product change (by design). |
| Closure gate | `validate changed` selects correctly for prefixed/fixture/shared-module changes (explain-tests green); 12 donor-governance docs annotated; snapshot matches child; roadmap lists mandated domains; AGENTS.md states edit target; FULL still 3580/48/1-excluded/0; docs links valid |

### Wave 1 — Canonical Domain Foundation

| Field | Value |
|---|---|
| Goal | One canonical multi-asset identity + portfolio domain that every authorized asset class rides on. THE architecture migration (BL-0105) — done with dual-run + parity, not rewrite. |
| Major backlog items | BL-0101 (one vocabulary) · BL-0102 (CRYPTO identity) · BL-0103 (Bond identity) · BL-0104 (Gold/Silver/Commodity identity) · BL-0105 (canonical multi-asset portfolio) · BL-0106 (options ledger merge) · BL-0107 (futures Decimal) · BL-0108 (USD doc) |
| Dependencies | Wave 0 (trustworthy validation to verify this wave) |
| Parallel work | BL-0101 SERIAL; BL-0102/0103/0104 PARALLEL_AFTER BL-0101; BL-0105 SERIAL core; BL-0106/0107 after BL-0105; BL-0108 any time |
| Product result | Platform can represent every authorized instrument class with correct valuation; equity behavior bit-identical (parity-protected). Unlocks all domain surfaces (Wave 5). |
| Closure gate | identity tests pass; portfolio parity passes (existing equity behavior preserved); options/futures fixtures pass; no Demo/Paper/Live regression; FULL clean |

### Wave 2 — Trading / Risk Correctness

| Field | Value |
|---|---|
| Goal | Close the trading-integrity gaps: server-side preview binding, real buying-power enforcement, instrument-kind validation, working remainders, replace, late-fill handling, content-derived idempotency, CVD session anchors, cross-asset risk hooks. |
| Major backlog items | BL-0201 (preview binding) · BL-0202 (BP/cash) · BL-0203 (instrument-kind) · BL-0204 (remainders) · BL-0205 (replace) · BL-0206 (late-fill) · BL-0207 (idempotency) · BL-0208 (CVD anchors) · BL-0209 (cross-asset risk hooks) |
| Dependencies | Wave 1 (BL-0203 needs identity; BL-0202 multi-asset cash needs BL-0105) |
| Parallel work | BL-0201 PARALLEL_SAFE (small lifecycle touch); BL-0202/0203 after Wave 1; BL-0204..0207 after BL-0201; BL-0208 independent; BL-0209 after BL-0105/BL-0202 |
| Product result | The approved "draft → re-preview → fresh-passing-preview → submit" invariant becomes server-enforced; Paper trading correct under multi-fill/cancel/replace; risk enforces what it displays. |
| Closure gate | preview/submit integrity tests pass; BP enforcement tests pass; instrument-kind rejection passes; remainder/replace lifecycle tests pass; late-fill test passes; paper workflow E2E (once BL-0802 lands) green; FULL clean |

### Wave 3 — IBKR / Live Market-Data Foundation

| Field | Value |
|---|---|
| Goal | The professor-required IBKR L1/L2 data path: adapter seeded from `tools/ibkr` + incremental depth engine with book lifecycle/staleness. |
| Major backlog items | BL-0301 (IBKR adapter) · BL-0302 (depth engine) · BL-0303 (depth staleness) · BL-0304 (IB L1→CVD) · BL-0305 (subscription lifecycle) · BL-0306 (OFI delta-based) |
| Dependencies | BL-0302 buildable on fixture depth streams (no external dep); BL-0301 needs BL-0302 for L2; BL-0304/0305 after BL-0301/0302 |
| Parallel work | BL-0302 PARALLEL_SAFE (fixture-first); BL-0301 SERIAL within wave; BL-0303 after BL-0302; BL-0306 after BL-0302 |
| Product result | CVD/Level-2 live measurement on IB data becomes possible (gated); order-book lane shows real incremental depth with truthful staleness. |
| Closure gate | depth state-machine tests pass (insert/update/delete/clear, reconnect rebuild, TTL); IBKR contract suite passes on recorded streams; entitlement-loss + pacing tests pass; CVD-on-IB replay identical to fixture semantics; all live gates remain closed in CI |

### Wave 4 — Authorized Existing Lanes to Runtime

| Field | Value |
|---|---|
| Goal | Turn the four original professor streams (Short Squeeze, CVD/Level-2, Options, Futures) into provider-backed runtime lanes with verified wires. |
| Major backlog items | BL-0401 (Provider Capability Registry) · BL-0402 (live-wire verification campaign) · BL-0403 (live OptionChainProvider) · BL-0404 (futures live data) · BL-0405 (squeeze bridge ops) |
| Dependencies | Wave 3 (IBKR); BL-0401 registry first within wave |
| Parallel work | BL-0401 PARALLEL_SAFE; BL-0402/0403/0404 after BL-0401; BL-0405 independent |
| Product result | Lanes show provider-backed or explicitly FIXTURE_ONLY data with verified status; no false live claims; options/futures gain live chains; CVD/Level-2 live. |
| Closure gate | capability registry tests pass; each provider has recorded-wire evidence row + canary gate; live suites gated correctly; no RUNTIME_VERIFIED claim without evidence; FULL clean |

### Wave 5 — Multi-Asset Product Domains

| Field | Value |
|---|---|
| Goal | Structural integration of the six mandated later domains + Government workflow: Bonds, Crypto, Gold, Silver, Commodities, Industry, Government — identity → provider → surface → portfolio → tests → truthful status. |
| Major backlog items | BL-0501 (Bonds) · BL-0502 (Crypto) · BL-0503 (Gold/Silver) · BL-0504 (Commodities) · BL-0505 (Industry) · BL-0506 (Government workflow) |
| Dependencies | Wave 1 (identity + portfolio); Wave 4 (providers) |
| Parallel work | each domain PARALLEL_AFTER_DEPENDENCY (they share primitives but not files); BL-0501/0502 can run in parallel once BL-0105 lands |
| Product result | Authorized scope visibly expands from equity-only to the full multi-asset workstation; every mandated domain discoverable with research + portfolio relevance. |
| Closure gate | per-domain: identity tests pass; workspace surface renders truthfully (FIXTURE_ONLY/RESEARCH_ONLY/PARTIAL as honest); portfolio compatibility test passes; domain suite green; no Demo/Paper/Live regression; FULL clean |

### Wave 6 — Intelligence Product Completion

| Field | Value |
|---|---|
| Goal | Complete the intelligence layers: whale cockpit + elevated families, market-context lane wired, news/research surfaces. |
| Major backlog items | BL-0601 (whale cockpit) · BL-0602 (market-context lane) · BL-0603 (news/research) |
| Dependencies | Wave 4 (provider evidence); BL-0602 independent |
| Parallel work | BL-0602 PARALLEL_SAFE; BL-0601/0603 after Wave 4 |
| Product result | Cross-market intelligence becomes a first-class user surface (whale, macro/government, market context, news) with provenance tagging throughout. |
| Closure gate | lane-registry parity test passes; whale families provider-backed with truthful status; market-context lane reachable; entity-resolution/surprise/reaction tests pass; FULL clean |

### Wave 7 — Frontend / API / Product Convergence

| Field | Value |
|---|---|
| Goal | One coherent product shell: mode-scoped state, canonical error taxonomy + generated contracts, multi-asset instrument selector, product IA, truthfulness/accessibility polish. |
| Major backlog items | BL-0701 (query keys) · BL-0702 (error taxonomy) · BL-0703 (contracts) · BL-0704 (instrument selector) · BL-0705 (IA) · BL-0706 (route↔lane guard) · BL-0707 (stale/next_action UX) · BL-0708 (a11y) · BL-0709 (truthfulness) |
| Dependencies | Wave 5 domains (surfaces to navigate); BL-0701 independent; BL-0703 after BL-0702 |
| Parallel work | BL-0701/0702/0706/0707/0708/0709 PARALLEL_SAFE; BL-0703 after BL-0702; BL-0704/0705 after BL-0101 |
| Product result | The product reads as ONE integrated multi-asset market platform (not lane collection / not donor merger); state, errors, and contracts are coherent. |
| Closure gate | query-key isolation tests pass; error taxonomy round-trip green; contract parity tests pass; selector resolves all classes; navigation per product IA; UI 438+ green; typecheck clean; bundle budget respected |

### Wave 8 — Developer-System / Performance / Cleanup

| Field | Value |
|---|---|
| Goal | Fast, honest, clean engineering system: validation performance, real E2E, dead routes, src→tools inversion, CORS, repo hygiene, Mongo docs. |
| Major backlog items | BL-0801 (validation perf) · BL-0802 (E2E) · BL-0803 (dead routes) · BL-0804 (inversion/CORS) · BL-0805 (repo hygiene) · BL-0806 (Mongo docs) · BL-0807 (docs consolidation) |
| Dependencies | BL-0801 after Wave 0; BL-0802 after Wave 2; cleanup after replacements (17) |
| Parallel work | BL-0803/0804/0805/0806 PARALLEL_SAFE; BL-0802 SERIAL (E2E harness); BL-0801 after BL-0002..0004 |
| Product result | Developer loop speed; CI/local parity; honest surface. No user-visible change (infrastructure). |
| Closure gate | FULL time reduced with equal/higher coverage; E2E suite green (gated); no dead routes; no src→tools edge; CORS loopback; no empty pytest dirs; docs links valid |

### Wave 9 — Production Hardening / Final Acceptance

| Field | Value |
|---|---|
| Goal | Defensible production readiness: provider canaries, failure testing, ops documentation closure, safety-register regression completion. |
| Major backlog items | BL-0901 (canaries/failure) · BL-0902 (ops acceptance) · BL-0903 (safety-register suites) |
| Dependencies | all Waves 0–8 |
| Parallel work | BL-0901/0903 PARALLEL_AFTER_DEPENDENCY; BL-0902 after all |
| Product result | The product can defensibly claim production readiness per the criteria in 18 (or honestly state exactly what remains). |
| Closure gate | canaries exist per provider; failure modes fail-closed with visible reasons; §67 register fully covered; operating procedures documented; no claim exceeds evidence; FULL clean |

## 3. Rollback / migration concerns (high-risk migrations)

| Migration | Introduce | Migrate | Dual-run | Verify parity | Remove compat |
|---|---|---|---|---|---|
| Portfolio (BL-0105) | canonical position model beside ledger | paper paths | YES (equity dual-run) | parity goldens bit-identical | after FULL clean |
| Options ledger (BL-0106) | conversion adapter | options paths | YES (dual-write) | float→Decimal conversion goldens | after options suite green |
| Vocabulary (BL-0101) | XA-01 extension + compat shim | call sites | YES (shim) | identity resolution tests | after migration |
| Depth engine (BL-0302) | new engine beside snapshot store | consumers | YES | state-machine tests | after consumers migrated |
| Contracts (BL-0703) | generated types beside manual | frontend | YES | contract parity tests | after migration |

Cleanup-after-replacement rule: BL-0803/0805 (dead routes, empty dirs, stale
CI) execute only after the replacements are proven; no cleanup before
replacement (controller §65).

## 4. Validation strategy per wave

| Wave | During development | Closure | CI |
|---|---|---|---|
| 0 | FAST + focused + explain-tests | changed + FULL | fast + changed + docs |
| 1 | domain suites (identity/paper/options/futures) | FULL + parity goldens | fast + changed + domain |
| 2 | focused lifecycle suites | FULL + paper E2E (later) | fast + changed + lifecycle |
| 3 | depth/IBKR recorded-stream suites | FULL + replay | fast + changed (+ gated live) |
| 4 | provider contract suites | FULL + recorded wires | fast + changed + provider |
| 5 | per-domain suites | FULL | fast + changed + domain |
| 6 | intelligence suites | FULL | fast + changed + intelligence |
| 7 | UI + API suites | FULL + UI + typecheck + bundle | fast + changed + UI |
| 8 | perf measurement + E2E | FULL + E2E | full-at-closure + E2E (gated) |
| 9 | canaries + failure tests | FULL + acceptance | full + canaries (gated) |

Provider work additionally requires: recorded fixture + contract test +
live-gated canary (never in CI without explicit gate).

## 5. Product roadmap vs engineering roadmap (synchronized)

| Product capability (visible) | Engineering enabler (wave) |
|---|---|
| Trustworthy provenance + honest roadmap | Wave 0 |
| Multi-asset instruments + portfolio in Paper | Wave 1 |
| Server-enforced preview/risk correctness | Wave 2 |
| CVD/Level-2 live on IB data (gated) | Wave 3 |
| Verified live provider wires | Wave 4 |
| Bonds/Crypto/Gold/Silver/Commodities/Industry/Government surfaces | Wave 5 |
| Whale/Industry/Government intelligence UX | Wave 6 |
| One coherent multi-asset product shell | Wave 7 |
| Fast validation + real E2E | Wave 8 |
| Defensible production readiness | Wave 9 |

## 6. Wave acceptance gates (controller §73)

Each wave closes only when its closure gate (above) is demonstrated with
evidence — never because code exists. The full validation baseline (FULL
3580/48/1-excluded/0 at WS04) is re-run at each wave closure; the mandatory
invariants (21) + paper governance/qualification suites run in FAST/CI on
every change.