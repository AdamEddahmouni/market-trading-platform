# Options Lane — Current State Audit (Deliverable 1)

**Status:** Baseline audit for causal redesign  
**Date:** 2026-08-18  
**Scope:** `integrated-market-platform` canonical subject; donor internship patterns referenced

---

## Executive summary

The Options lane today is **Phase 11 complete**: a fixture-first unusual-activity whale family on BIYA only. It is **not** a distribution-intelligence engine. It provides liquidity-gated activity events, a per-event `confirmation_score`, and read-only UI — with strong ADR guardrails against universal scoring and direction-from-volume fallacies.

Estimated completion vs. target architecture: **~8–12%** (activity plumbing + governance; no P vs Q, no surface, no Greeks, no strategy optimizer).

---

## 1. What exists today

### 1.1 Data flow

```text
biya_options_slice.json (fixture)
    → FixtureOptionsProvider
    → liquidity_gate + confirmation_score (fixture-supplied inputs)
    → provider envelope (OPTIONS_EVENT / whale_event family "options")
    → whale ledger ingest
    → query_options_summaries (PIT-filtered)
    → GET /workspace/BIYA/options
    → OptionsWorkspacePanel (activity table)
```

### 1.2 Core modules

| Module | Path | Responsibility |
|---|---|---|
| Scoring patterns | `donor_patterns/options_lane.py` | `liquidity_gate`, `confirmation_score`, `project_options_confirmation` |
| Fixture adapter | `providers/adapters/fixture_options.py` | BIYA-only offline adapter |
| Envelope | `providers/envelope.py` | `build_options_envelope`, `activity_to_options_event` |
| Ledger | `providers/whale_ledger.py` | `OPTIONS_FAMILY`, `query_options_summaries` |
| Projections | `providers/projections.py` | `build_workspace_options_payload`, `options_available` |
| Institutional | `features/institutional.py` | `query_institutional_evidence(OPTIONS_FAMILY)` |
| Squeeze cross-ref | `donor_bridge/institutional_ignition.py` | `build_institutional_options_card` |
| Cross-lane | `cross_lane/evidence.py` | Contract enums only |
| Cross-lane adapter | `donor_bridge/cross_lane_adapter.py` | Order flow only; `options_available: False` hardcoded |
| UI API | `ui_api/server.py` | `/workspace/{symbol}/options` |
| UI | `ui/src/components/options/*` | Activity table, capability banners |
| Provider stub | `providers/contracts.py` | `OptionChainProvider` protocol — unimplemented |
| Phase 11 governance | `phase11_assertions.py`, `tools/phase11/*` | PASS evidence |

### 1.3 Entitlement

- **BIYA only** for whale options family
- All other symbols: `unavailable` / `WHALE_NO_ENTITLED_SOURCE`
- Capability ID: `whale.options` (AVAILABLE for entitled fixtures)
- `options.chain`: UNSUPPORTED (wireframe aspirational)

### 1.4 Data model (current)

**No canonical full option contract model.** Two shapes:

**Fixture activity** (`tests/fixtures/providers/options/biya_options_slice.json`):
`strike`, `expiry`, `option_type`, `bid`, `ask`, `volume`, `open_interest`, `volume_oi_ratio`, `iv_rank`, `volume_ratio`, `skew_signal`, `direction_label`, `event_time`, `source`

**Normalized whale_event** (`envelope.py`):
Adds `confirmation_score`, `liquidity_ok`, `liquidity_reasons`, `direction_label` (supports_long | supports_short | neutral | ambiguous), `epistemic_class: DERIVED`, `research_only: true`

**Missing from model:** `underlying_id`, `option_id`, `DTE`, `exercise_style`, `settlement_style`, `multiplier`, `deliverable`, `intrinsic/extrinsic`, `provider Greeks`, `quality` flags per contract, corporate-action adjustment metadata.

### 1.5 Scoring today

`confirmation_score` = weighted blend of fixture `iv_rank`, `volume_ratio`, `skew_signal` (weights 0.35/0.35/0.30), scaled 0–100.

This is **per-event unusual-activity context**, not:
- directional edge
- volatility edge
- skew edge
- P vs Q mispricing

### 1.6 Cross-lane integration today

| Integration | Status |
|---|---|
| Squeeze ignition Options card | Shows activity count, vol/OI, direction ambiguity — BIYA fixture only |
| `cross_lane_adapter` Options publisher | **Not implemented** — hardcodes `options_available: False` |
| Causal evaluator Options fields | Evaluator accepts cross_lane snapshot; Options signals not populated from IMP |
| Catalyst bridge `options_score` | Separate internship donor field — **not unified** with whale confirmation_score |

### 1.7 UI today

`OptionsWorkspacePanel`: read-only activity table with score, liquidity badge, direction label, epistemic disclaimer.

**Not implemented** (documented in wireframe `07-options.md`):
- Chain grid
- IV surface / skew / term structure charts
- P vs Q comparison card
- Strategy recommendations
- Flow classification breakdown
- Dealer gamma panel

### 1.8 Tests today

| Test file | Coverage |
|---|---|
| `tests/providers/test_options.py` | Provider, ledger, PIT, UI payload |
| `tests/donor_patterns/test_donor_patterns.py` | `liquidity_gate` only |
| `tests/donor_bridge/test_institutional_ignition.py` | Options ignition card |
| `tests/ui1/test_ui_api.py` | Capability assertions |

**Not tested:** IV solver, Greeks, surface QA, flow classification, dealer models, P vs Q, strategy payoff, execution.

### 1.9 Governance guardrails (working as designed)

| Guardrail | Evidence |
|---|---|
| No universal whale/options score | ADR-WHALE-004, Rev 3 foundation spec |
| Calls ≠ automatically bullish | ADR-WHALE-004 direction ambiguity policy; UI disclaimer |
| No GEX/dealer gamma claims | Not implemented |
| No delta = probability | Not implemented (no Greeks) |
| Fail closed on missing data | BIYA-only entitlement; unavailable elsewhere |
| `research_only: true` on derived scores | Envelope metadata |

---

## 2. What does not exist

| Capability | Status |
|---|---|
| Live `OptionChainProvider` (Tradier-class) | Stub only |
| Full options chain normalization | No schema |
| IV engine (internal normalized IV) | None |
| Greeks engine | None |
| Volatility surface σ(K,T) | None |
| Surface quality / no-arbitrage cleaning | None |
| Risk-neutral distribution Q | None |
| Physical distribution P | None (platform forecast interface ADR-fcast-001 only) |
| P vs Q comparison | None |
| Volatility risk premium estimation | None |
| Realized volatility engine (Parkinson, Garman-Klass, etc.) | Bar RV only at platform level |
| Event volatility / IV crush | None |
| Event state machine | None |
| Signed options flow | None |
| Abnormal flow baselines | None |
| Dealer positioning / GEX | Enum placeholder only |
| Strategy generation / payoff engine | None |
| Expected P&L distribution | None |
| Options execution in simulator | Bar-only simulator |
| Exercise / assignment | None |
| Corporate action adjusted contracts | None |
| Historical expired chain archive | None |
| 0DTE specialization | None |
| Options quality taxonomy (formal) | Partial (liquidity reasons only) |

---

## 3. Anti-pattern audit

| Anti-pattern | Found? | Detail |
|---|---|---|
| Universal Options Score | **Partial risk** | `confirmation_score` displayed as "Score" without component breakdown |
| Call volume = bullish | **Guarded** | ADR + ambiguous direction_label; fixture assigns direction |
| Put/call ratio = bullish | **N/A** | Not implemented |
| Delta = probability | **N/A** | No Greeks |
| OI × gamma = dealer gamma | **N/A** | No gamma math |
| IV = RV forecast | **N/A** | No IV engine |
| High call volume → squeeze ignition | **Low risk** | Ignition card counts elevated activity with ambiguity disclaimer |
| Substituting missing flow with volume | **N/A** | Fail closed |
| Forcing trade recommendations | **Guarded** | Explicitly out of Phase 11 scope |

---

## 4. Relationship to Short Squeeze lane

| Aspect | Current state |
|---|---|
| SS causal redesign | P0/P1 complete in squeeze-core |
| Options contribution to SS | Institutional card only; cross-lane evidence **not wired** (D-07) |
| SS contribution to Options | Not consumed |
| Shared cross-lane contract | `evidence.py` — partial signal set |
| Competing roadmaps | **Resolved** — see `OPTIONS_SHORT_SQUEEZE_ROADMAP_RECONCILIATION.md` |

---

## 5. Phase 11 vs. target gap

Phase 11 delivered honest fixture plumbing. The target architecture requires nine additional major subsystems (O1–O9) plus shared platform milestones (P2, P3, P4). Phase 11 assets **extend** into O1; they do not satisfy O2–O8.

---

## 6. Recommended immediate actions

1. Formalize canonical option contract schema (O1)
2. Extend cross-lane evidence signals and Options publisher adapter (SHARED P3 partial)
3. Define Options quality taxonomy constants (O1)
4. Plan IV engine interface without live provider (O2 research)
5. Do **not** expand `confirmation_score` into primary lane output
6. Do **not** implement dealer GEX before flow correctness (R-07)

---

## Related documents

- `OPTIONS_DISCREPANCY_REGISTER.md`
- `OPTIONS_TARGET_ARCHITECTURE.md`
- `OPTIONS_SHORT_SQUEEZE_ROADMAP_RECONCILIATION.md`
- `docs/superpowers/specs/2026-08-17-phase-11-whale-options-design.md`
- `docs/superpowers/decisions/2026-08-17-adr-whale-004-options-envelope-semantics.json`
