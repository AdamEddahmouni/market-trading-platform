# Phase 3F Cohort Expansion — Batch 03 Acquisition Plan

## Status

**Preregistered (2026-08-17).** This document was committed before any bar data was
fetched, inspected, or computed for the three Batch 3F-03 symbols. It authorizes IBKR
historical intake, Stage 1 evidence construction, Phase 3A freeze, and Stage 2
forward-outcome acquisition for the symbols below only.

## Discovery audit

| Source | Result |
|--------|--------|
| `batch01_discovery_rows.json` (13 scanner rows) | Exhausted — all symbols already in cohort |
| Phase 2V comparison manifest (KLRS, LBGJ, SG, SLS, TRVI) | Exhausted — all symbols already in cohort |
| Phase 3F Batch 01/02 `biya_news.jsonl` co-occurrence | Exhausted — all US equity tickers already in cohort |
| Archived `prime_log.csv` (forensic archive) | PMAX, STAK remain (ATAI, CADL, CGEM, IOVA already in cohort) |
| Archived `squeeze_score_history.csv` / `corroboration_history.csv` | APVO observed 2026-07-17 in platform screening universe |
| Archived `screener_snapshot.json` (local forensic archive) | Exhausted at 13 rows — no additional scanner field values |
| KLOS identity conflict case | Excluded (`BLOCKED_CONFLICTING_IDENTITY`) |

Batch 03 adds two symbols from **archived platform prime logs** (PMAX, STAK) and one from
**archived screening-universe history** (APVO). No saved scanner snapshot row exists for
any of them. IBKR contract resolvability was verified offline before preregistration.

## Cohort

Exactly three symbols in frozen source order:

| # | Symbol | Case ID | Frozen Boundary (UTC) | Discovery provenance |
|---|--------|---------|----------------------|----------------------|
| 1 | PMAX | BATCH3F03_PMAX_20260718 | 2026-07-18T13:37:55.017661Z | `prime_log.csv` (2026-07-17T09:01:13Z) |
| 2 | STAK | BATCH3F03_STAK_20260718 | 2026-07-18T13:37:55.017661Z | `prime_log.csv` (2026-07-17T12:24:39Z) |
| 3 | APVO | BATCH3F03_APVO_20260718 | 2026-07-18T13:37:55.017661Z | `squeeze_score_history.csv` / `corroboration_history.csv` (2026-07-17T19:19:21Z) |

The frozen boundary matches Batch 01 scanner capture time. These symbols share the
cohort boundary for outcome comparability; prime-log and screening-universe observation
timestamps are **not** used as detection boundaries.

Normalized discovery rows: `intake/batches/phase-3f-cohort-expansion-03/normalized/batch3f03_discovery_rows.json`.

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
- Prime-log and screening-universe history are weaker provenance than Batch 01 scanner rows;
  documented explicitly.
- Short-pressure evidence (published SI, borrow) remains UNKNOWN for historical IBKR symbols.
