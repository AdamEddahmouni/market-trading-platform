# Phase 4 — Walk-forward fold plan (structure only)

- Harness: `phase_4_walkforward_harness.v1`
- Preregistration: `phase_4_calibration_preregistration.v0.6-draft`
- Boundaries: 35 (33 symbol clusters)
- Folds: 2 (2 non-empty evaluation; 2 with empty training)
- Purge/embargo: 30 / 15 calendar days (O-2 addendum §4)
- Degenerate: **no**

## Regime slices (recorded, never padded)

| Slice | Boundaries |
|---|---:|
| `PRE_2020` | 0 (empty) |
| `MEME_REGIME` | 0 (empty) |
| `HIGH_RATE` | 0 (empty) |
| `POST_NORMALIZATION` | 35 |
| `UNASSIGNED` | 0 |

## Folds

| Fold | Evaluation | Training | Purge window | Embargo window |
|---|---|---|---|---|
| 0 | 31 boundaries (ADVB, APVO, ATAI, AVTX, BHVN, BIYA, CADL, CELZ, CGEM, GDC, GOAI, GPRE, IOVA, KLRS, LBGJ, LMNX, MGNX, NXXT, OBE, PESI, PMAX, SG, SLS, SSPC, STAK, TRVI, VMAR, XNCR, ZNTL) | 0 boundaries | 2026-06-17 → 2026-07-17 | 2026-06-02 → 2026-06-17 |
| 1 | 4 boundaries (AACB, AACG, AACI, AADX) | 0 boundaries | 2026-07-18 → 2026-08-17 | 2026-07-03 → 2026-07-18 |

## Limitations

- `HISTORICAL_CASE_BOUNDARIES_NOT_INDEPENDENT`
- `DETECTION_EVALUABILITY_LIMITED`
- `SINGLE_HORIZON_SUPPORTABLE_WHILE_O1_OPEN`
- `STRUCTURE_ONLY_NO_FIT_NO_PROBABILITY`

## Honest structural note

This plan partitions the owned 24-hour outcome labels only. Where a
fold shows zero admissible training boundaries, that fact is the
finding: fitting (sprint item 1.3) must report the structure as-is,
keep the evaluator's `RESEARCH_ONLY` horizon slots, and never
re-shuffle splits or backfill probabilities into unsupported
horizons (preregistration §2.3, §7, §8).
