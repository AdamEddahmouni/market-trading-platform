# MC11 — Macro Context (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Shared macro event ontology and multi-dimensional `MacroContextEvidence` on admitted fixtures  
**Prerequisites:** MC5 IMPLEMENTED, Platform P0 PIT, Futures F7 macro calendar (consumer)

## 1. Purpose

Unify macro event semantics in Market Context and resolve **MC-D10** (macro surprise fragmented in Futures only). Market Context owns event taxonomy and surprise-derived regime tags; Futures F7 continues to own calendar risk / curve interpretation.

## 2. Shared macro ontology

| Event type | Regime dimension | Owner |
|---|---|---|
| `NFP`, `GDP`, `RETAIL_SALES` | `growth_regime` | Market Context |
| `CPI`, `PPI`, `PCE` | `inflation_regime` | Market Context |
| `FOMC`, `FED_SPEECH` | `monetary_policy_regime` | Market Context |
| Cross-cutting surprise / event window | `risk_regime`, `volatility_regime`, `liquidity_regime` | Market Context |

Futures publishes `FUTURES_MACRO_EVENT_RISK` from F7; MC11 publishes `MACRO_REGIME_CONTEXT` — complementary, not duplicate.

## 3. Scoring model (`macro_context_v1`)

### Inputs

- Fixture macro events (`boxl_macro_context_slice.json`)
- `prediction_cutoff` PIT gate

### Regime mapping

| Dimension | Rule |
|---|---|
| `growth_regime` | Latest past NFP/GDP: actual > consensus → `EXPANDING`; actual < consensus → `CONTRACTING`; else `STABLE` |
| `inflation_regime` | Latest past CPI/PPI: actual > consensus → `ELEVATED`; actual < consensus → `DISINFLATIONARY`; else `STABLE` |
| `monetary_policy_regime` | FOMC within 48h → `POLICY_EVENT_IMMINENT`; else `NEUTRAL` |
| `risk_regime` | Event window active or max surprise z ≥ 1.5 → `ELEVATED`; else `NORMAL` |
| `volatility_regime` | `ELEVATED` when `risk_regime=ELEVATED`; else `NORMAL` |
| `liquidity_regime` | `STRESSED` when risk and inflation both elevated; else `NORMAL` |

Surprise z-score reuses F7 `compute_surprise_zscore`.

## 4. PIT rules

- Include events only when `release_time` or `scheduled_time` ≤ `prediction_cutoff`
- Future events may inform `monetary_policy_regime` window only when `scheduled_time` is known at cutoff

## 5. Quality flags

- `MACRO_CONSENSUS_MISSING` — no PIT-valid events
- `MACRO_SURPRISE_UNAVAILABLE` — no actual/consensus pairs
- `MACRO_REGIME_PARTIAL` — fewer than 3 regime dimensions resolved

## 6. Cross-lane boundary

- Publishes `MACRO_REGIME_CONTEXT` when `risk_regime=ELEVATED` or inflation/growth non-STABLE
- Does not reimplement F7 calendar snapshot or curve/carry semantics

## 7. Fixtures

| Fixture | Scope |
|---|---|
| `boxl_macro_context_slice.json` | Macro event rows |
| `boxl_macro_context_expected.json` | Golden MC11 regression |

## 8. Out of scope

- Live government data ingest
- Equity-specific macro beta estimation
- Trade signals
