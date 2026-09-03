# MC6 — Expectations / Surprise (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** PIT `ExpectationSnapshot` store and fail-closed `SurpriseEvidence` on BOXL earnings + ES macro fixtures  
**Prerequisites:** MC2–MC5 IMPLEMENTED, Platform P0 PIT

## 1. Purpose

Bridge fixture consensus rows and macro release actuals into governed surprise semantics. Surprise is economic deviation — not semantic sentiment (MC4) or typed extraction (MC5).

## 2. Fixtures

| Fixture | Scope |
|---|---|
| `boxl_expectations_slice.json` | BOXL revenue consensus vs MC5 actual |
| `es_macro_expectations_slice.json` | ES NFP/CPI macro releases (revision row for CPI) |
| `boxl_surprise_expected.json` | Golden regression for BOXL workspace surprise block |

## 3. PIT rules

- Expectation visible only when `expectation.available_time <= prediction_cutoff`
- Actual visible only when `actual_available_time <= prediction_cutoff`
- Missing consensus → `SURPRISE_UNAVAILABLE` (never zero surprise)
- Missing actual at cutoff → no `SurpriseEvidence` row (not neutral)
- Revision surprise: compare actual to latest PIT-visible expectation revision

## 4. Surprise math (`expectations_v1`)

- `surprise = actual - expected` (median preferred over mean)
- `surprise_percent = surprise / expected × 100` when expected ≠ 0
- `standardized_surprise = surprise / dispersion` when dispersion > 0

## 5. Cross-lane boundary

- Publishes `EVENT_SURPRISE_POSITIVE` / `EVENT_SURPRISE_NEGATIVE` via evidence bus
- Options O7 / Futures F7 consume surprise — no IV crush or curve math duplication
- No SHARED P4 EV fusion (display + cross-lane evidence only)

## 6. Workspace

- `expectation_snapshots`, `surprise_evidence`, `surprise_summaries` on market context payload (BOXL)
- `macro_surprise_summaries` on futures workspace (ES fixture scope)

## 7. Acceptance

MC6 complete when PIT adversarial tests pass, golden `boxl_surprise_expected.json` matches, fail-closed missing-consensus tests pass, and cross-lane surprise evidence publishes without SHARED P4 fusion.
