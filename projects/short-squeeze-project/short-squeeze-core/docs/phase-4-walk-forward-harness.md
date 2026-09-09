# Phase 4 — Walk-forward harness scaffold (sprint item 1.2)

**Status:** scaffold committed; **no model has been fit**.
**Preregistration:** [phase-4-calibration-preregistration.md](phase-4-calibration-preregistration.md)
(§2.2 dependence rule, §6 regime slices, §7 purge/embargo + degeneracy gate)
**Cutpoints addendum:** [phase-4-calibration-regime-cutpoints-addendum.md](phase-4-calibration-regime-cutpoints-addendum.md)
(open item O-2 — pending reviewer confirmation)
**Version:** `phase_4_walkforward_harness.v1`
**Code:** `src/squeeze_core/calibration/walkforward.py`; runner
`tools/run_walk_forward_plan.py`; tests `tests/calibration/test_walkforward.py`

## 1. Scope — structure only

This scaffold implements the pre-registered **split machinery** and nothing else:

- **Chronological ordering** of labeled boundaries by boundary time (ties broken
  by case id).
- **Symbol grouping (ADR-0054):** all boundaries of one symbol form one
  dependent group and are assigned to evaluation whole — a cluster never
  straddles a fold split. BIYA's three boundaries land in one group (tested).
- **Purge/embargo windows (O-2):** per evaluation window start `E`, the purge
  window is `[E − w, E)` with `w = 30` calendar days and the embargo window is
  `[E − w − e, E − w)` with `e = 15` calendar days. A training boundary at time
  `t` is admissible iff `t < E − (w + e)` — its label window plus embargo buffer
  clear before the fold starts.
- **Expanding-window folds:** each fold holds out the next unconsumed cluster
  run; training is every boundary of a non-evaluation symbol whose time is at
  least `w + e` calendar days before the evaluation window start (earlier
  evaluation clusters re-enter training once their label windows clear the gap
  — necessary at this sample size; the grouping rule still holds per fold).
- **Regime slices:** the four exhaustive half-open UTC slices from the O-2
  addendum; membership by boundary time; a boundary exactly at a cutpoint
  belongs to the later slice.
- **Degeneracy gate (prereg §7):** fewer than two non-empty evaluation folds
  flags the plan degenerate. No random or time-shuffled split is ever
  substituted.

The harness **never fits, never produces a probability, and never consumes an
outcome label.** Fitting (sprint item 1.3) is gated on the preregistration's
open items ([§10](phase-4-calibration-preregistration.md#10-open-items-to-lock-before-any-fit)).

## 2. Measured structure of the committed cohort

Emitted by `tools/run_walk_forward_plan.py` from the 35 committed historical
outcome-observation fixtures (33 symbol clusters; BIYA grouped):

- **Regime slices:** all 35 boundaries fall in `POST_NORMALIZATION` (frozen
  2026 cohort); `PRE_2020`, `MEME_REGIME`, and `HIGH_RATE` are **empty** and are
  reported as empty — never padded, re-weighted, or dropped (prereg §6).
- **Folds:** 2 non-empty evaluation folds — exactly the prereg §7 minimum, so
  the plan is **not** flagged degenerate, but it sits at the floor.
- **Admissible training boundaries: 0 in both folds.** The cohort has two
  boundary instants (~2026-07-17 and ~2026-07-18/08-17) roughly 30 days apart;
  each instant falls inside the other's purge/embargo gap. This is the honest
  structural finding: item 1.3's fits would have **no training data** under the
  pre-registered windows. It must be reported as-is (`NOT_CALIBRATED`,
  `RESEARCH_ONLY` retained) — the windows are outcome-blind and pre-registered,
  so they are **not** relaxed to manufacture a fit.

## 3. Outputs

- `reports/calibration/phase_4_walk_forward_plan.json` — the fold plan
  (`phase_4_walkforward_harness.v1`), including per-fold boundary indices,
  symbol sets, exclusion windows, regime counts, empty regimes, and the
  degeneracy verdict.
- `reports/calibration/phase_4_walk_forward_plan.md` — the human-readable
  summary with the limitations block and the honest structural note.

Both are regenerated artifacts; re-run the runner after any registry/fixture
change and commit the refreshed outputs in the same change.

The item 1.3 reporting skeleton consumes this plan's diagnostics as the F-3 input
of the preregistered feasibility ladder — see
[phase-4-fit-report-skeleton.md](phase-4-fit-report-skeleton.md) and
`tools/run_fit_report_skeleton.py`.

## 4. Tests

`tests/calibration/test_walkforward.py` covers: cutpoint membership and
exhaustiveness (including the cutpoint-instant edge), naive-datetime rejection,
empty/negative input rejection, cluster non-straddling, purge/embargo exclusion
arithmetic, expanding-window release, train/eval symbol disjointness, the
degeneracy gate, plan serialization, loader parsing (single fixture, array,
invalid payload), and the committed 35/33 cohort structure including the
no-training-boundaries finding and the probability-free field check.

## Revision history

| Date | Change |
|---|---|
| 2026-09-05 | Initial scaffold (sprint item 1.2): grouped chronological folds, purge 30 / embargo 15 (O-2), regime slices, degeneracy gate, diagnostics; committed-cohort structure measured and recorded; no fitting performed |
| 2026-09-05 | Cross-link: the item 1.3 fit-report skeleton consumes these diagnostics as the F-3 gate input ([phase-4-fit-report-skeleton.md](phase-4-fit-report-skeleton.md)) |
