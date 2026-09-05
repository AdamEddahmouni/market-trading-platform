# Phase 3F Cohort Expansion — Batch 01 Acquisition Plan

## Status

**Preregistered (2026-08-17).** This document was committed before any bar data was
fetched, inspected, or computed for the five Batch 3F-01 symbols. It authorizes IBKR
historical intake, Stage 1 evidence construction, Phase 3A freeze, and Stage 2
forward-outcome acquisition for the symbols below only.

## Discovery audit

| Source | Result |
|--------|--------|
| `batch01_discovery_rows.json` (13 scanner rows) | Exhausted — all symbols already in cohort |
| Phase 2V comparison manifest (KLRS, LBGJ, SG, SLS, TRVI) | Exhausted — all symbols already in cohort |
| KLOS identity conflict case | Excluded (`BLOCKED_CONFLICTING_IDENTITY`) |
| Archived `screener_snapshot.json` (local forensic archive) | Not present in workspace; no additional rows extractable |
| Archived BIYA news evidence (`biya_news.jsonl`) | Five US equity tickers co-mentioned with BIYA; no scanner field values |

Batch 01 adds five symbols discovered via **archived news co-occurrence** only (log-name
evidence, same class as KLRS/SG before IBKR extension). No saved scanner snapshot row
exists for any of them. IBKR contract resolvability was verified offline before
preregistration.

## Cohort

Exactly five symbols in frozen source order:

| # | Symbol | Case ID | Frozen Boundary (UTC) | Discovery provenance |
|---|--------|---------|----------------------|----------------------|
| 1 | CELZ | BATCH3F01_CELZ_20260718 | 2026-07-18T13:37:55.017661Z | `biya_news.jsonl` (Stocktwits, 2026-06-26) |
| 2 | GDC | BATCH3F01_GDC_20260718 | 2026-07-18T13:37:55.017661Z | `biya_news.jsonl` (Stocktwits, 2026-06-26) |
| 3 | ADVB | BATCH3F01_ADVB_20260718 | 2026-07-18T13:37:55.017661Z | `biya_news.jsonl` (MT Newswires, 2026-07-20) |
| 4 | GOAI | BATCH3F01_GOAI_20260718 | 2026-07-18T13:37:55.017661Z | `biya_news.jsonl` (MT Newswires, 2026-07-20) |
| 5 | NXXT | BATCH3F01_NXXT_20260718 | 2026-07-18T13:37:55.017661Z | `biya_news.jsonl` (MT Newswires, 2026-07-20) |

The frozen boundary matches Batch 01 scanner capture time. These symbols share the
cohort boundary for outcome comparability; news publication timestamps are **not** used
as detection boundaries.

Normalized discovery rows: `intake/batches/phase-3f-cohort-expansion-01/normalized/batch3f_discovery_rows.json`.

## Window adjustment

Identical to Phase 3E Stage 2: the frozen boundary falls on Saturday 2026-07-18. The
forward window shifts to the next US equity trading day (Monday 2026-07-21).

| Parameter | Value |
|-----------|-------|
| Adjusted forward start | 2026-07-21T13:37:55Z |
| Adjusted forward end | 2026-07-22T13:37:55Z |
| Calendar shift | +72 hours (Saturday → Monday) |

## IBKR request parameters

| Parameter | Value |
|-----------|-------|
| Source | IBKR TWS API via IB Gateway (localhost:4001) |
| `whatToShow` | `TRADES` |
| `barSizeSetting` | `1 min` |
| `useRTH` | `0` |
| `formatDate` | `2` |
| `keepUpToDate` | `False` |
| Detection-context `endDateTime` | `20260718 13:37:55 UTC` |
| Forward-outcome `endDateTime` | `20260722 13:37:55 UTC` |
| `durationStr` | `86400 S` |

Bar semantics follow ADR-0066 (identical to Phase 3E Stage 2).

## Outcome computation protocol

1. Compute reference price: first eligible trade-bar close at or after the detection boundary.
2. For each forward bar, compute percentage return from reference price.
3. Apply `phase_3b_outcome_label_policy.v1` (24h horizon, ±25% thresholds).

## Leakage audit requirements

Same five checks as Phase 3E Stage 2:

1. This acquisition plan committed before outcome capture.
2. Boundary freeze committed before outcome capture.
3. Phase 3A request frozen before outcome capture.
4. Phase 3A result frozen before outcome capture.
5. Outcome manifest is a separate contract from the evaluation freeze.

## Artifact output

| Artifact | Location |
|----------|----------|
| Detection-context bars | `intake/local-bars/ibkr-batch-05/raw/{SYMBOL}-detection-context.*` |
| Forward outcome bars | `intake/local-bars/ibkr-batch-05/raw/{SYMBOL}-forward-outcome.*` |
| Evidence bundles | `build/acquisition/evidence-bundles/{SYMBOL}/` |
| Stage 2 outcomes | `build/acquisition/stage2/outcomes/{SYMBOL}/` |
| Evaluation fixtures | `tests/fixtures/evaluation/{symbol}_boundary_evaluation.json` |
| Outcome fixtures | `tests/fixtures/research/{symbol}_outcome_observation.json` |

## Non-goals

- No threshold tuning or composite scores
- No trading simulation
- No KLOS promotion
- No Adam scoring calibration

## Acknowledged limitations

- No scanner snapshot field values exist for these symbols; detection remains
  `UNEVALUABLE` under Batch 07 price-level blocking (expected, does not block cohort counting).
- News co-occurrence is weaker provenance than Batch 01 scanner rows; documented explicitly.
- Short-pressure evidence (published SI, borrow) remains UNKNOWN for historical IBKR symbols.
