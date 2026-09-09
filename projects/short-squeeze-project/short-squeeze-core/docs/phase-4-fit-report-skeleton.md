# Phase 4 — Baseline-fit reporting skeleton (sprint item 1.3)

**Status:** reporting skeleton committed **before any fit**; the fitting stage stays
blocked on preregistration [§10](phase-4-calibration-preregistration.md) open items
(O-2/O-3/O-4/O-6).
**Prereg:** [phase-4-calibration-preregistration.md](phase-4-calibration-preregistration.md)
(`phase_4_calibration_preregistration.v0.6-draft`)
**Harness:** [phase-4-walk-forward-harness.md](phase-4-walk-forward-harness.md)
(`phase_4_walkforward_harness.v1`)
**Sprint:** [SHORT_SQUEEZE_SPRINT_PLAN_2026-09-06.md](research/SHORT_SQUEEZE_SPRINT_PLAN_2026-09-06.md)
item 1.3
**Version:** `phase_4_fit_report_skeleton.v1`

## 1. Purpose

Sprint 1.3's acceptance is disjunctive: *"diagnostics from 1.2 pass the preregistered
thresholds **or** the result is honestly reported as not-yet-calibrated
(`RESEARCH_ONLY` retained — no forced flip)"*. This skeleton implements the second
arm so the fit attempt is **ready the moment O-2/O-3/O-4/O-6 are confirmed**: the
moment they are, the fit runs, the measured metrics slot into the prepared gate
ladder, and the report either keeps its honest `NOT_CALIBRATED` verdict or is
re-issued as a fit result — no reporting machinery gets invented under deadline
pressure after a fit exists.

The skeleton is **not a fit**: no model is estimated, no probability is produced, and
no fitted threshold exists. It measures the preregistered feasibility-gate ladder
(prereg [§8.1](phase-4-calibration-preregistration.md)) over committed inputs and
reports the verdict with the failing gate(s) named.

## 2. Feasibility-gate ladder (preregistration §8.1, in order)

| Gate | Rule | Input (committed) | Result on the committed cohort |
|---|---|---|---|
| F-1 evaluable positives | ≥ 10 | dataset rows: `outcome_label = SUBSTANTIAL_UPWARD_MOVE` → `Y_1 = 1` | **FAIL** — 3 positives (base rate 0.10 over 30 evaluable) |
| F-2 evaluable negatives | ≥ 10 | dataset rows: `NO_SUBSTANTIAL_UPWARD_MOVE` → `Y_1 = 0` | pass — 27 negatives |
| F-3 fold structure | ≥ 2 non-empty chronological evaluation folds (§7) | 1.2 diagnostics: `phase_4_walk_forward_plan.json` | pass — 2 folds (exactly at floor) |
| F-4 horizon data (O-1) | owned forward paths for any horizon k > 1 to be calibrated | owner data-feasibility statement, **not structurally decidable** | recorded with `passed=None`; multi-day slots stay `RESEARCH_ONLY` |

Design points:

- **Label mapping (prereg §3):** only `SUBSTANTIAL_UPWARD_MOVE` counts as a positive;
  `NO_SUBSTANTIAL_UPWARD_MOVE` is the negative class; `SUBSTANTIAL_DOWNWARD_MOVE` is
  the retained mirror, not the squeeze target; `MIXED_OR_VOLATILE` /
  `OUTCOME_UNKNOWN` / `OUTCOME_INSUFFICIENT_DATA` are unevaluable for this target.
  Synthetic rows (`SYNTHETIC_EDGE_CASE`) are excluded per ADR-0053.
- **F-4 is not a structural failure.** It is an owner data-feasibility statement
  (O-1): it cannot pass or fail from committed data, so it is recorded with
  `passed=None`, constrains which horizons may calibrate, and never fails the ladder
  by itself. Only the structurally decidable gates (F-1..F-3) drive the failure
  verdict; `all_feasibility_gates_passed` is true iff F-1..F-3 all pass.
- **Slot statuses use the snapshot contract's vocabulary** (`RESEARCH_ONLY |
  CALIBRATED`, `src/squeeze_core/intelligence/contracts.py`). A slot may only become
  `CALIBRATED` through the item 1.4 wiring after the gates pass and the owner-gated
  fitting stage succeeds. While the report is a skeleton, **every** slot — including
  horizon 1 — stays `RESEARCH_ONLY`; the `owned_forward_path_data` field records *why*
  (no data at all vs. no fit yet).

## 3. Honest verdict on the committed cohort

`NOT_CALIBRATED`, failing gate **F-1** named (3 positives < 10), with:

- `RESEARCH_ONLY` retained on every horizon slot (1/3/5/10/20);
- `fit_attempted = false` and `fit_blocked_by` carrying O-2/O-3/O-4/O-6 plus the
  failing gate;
- the recorded structural facts carried into the report: 2 non-empty evaluation
  folds (exactly at the §7 floor) with 0 admissible training boundaries in both, and
  all 35 historical boundaries `POST_NORMALIZATION` (3 empty regimes reported as
  empty);
- limitations block: `HISTORICAL_CASE_BOUNDARIES_NOT_INDEPENDENT`,
  `DETECTION_EVALUABILITY_LIMITED`, `SINGLE_HORIZON_SUPPORTABLE_WHILE_O1_OPEN`,
  `COUNTERFACTUAL_EXPLORATION_ONLY`, `SMALL_SAMPLE_WARNING`,
  `REPORT_SKELETON_NO_FIT_NO_PROBABILITY`.

Nothing is force-flipped to `CALIBRATED`, no split is shuffled, and no window is
relaxed (prereg §2.3, §7, §8.2, §11).

## 4. Runner and outputs

```bash
.venv/Scripts/python.exe tools/run_fit_report_skeleton.py
```

- `reports/calibration/phase_4_fit_report_skeleton.json` — the gate ladder, outcome
  counts, horizon coverage, verdict, blockers, notes, limitations
  (`phase_4_fit_report_skeleton.v1`).
- `reports/calibration/phase_4_fit_report_skeleton.md` — the human-readable report
  with the failing gate named.

Both are regenerated artifacts; re-run the runner after any registry/fixture change
and commit the refreshed outputs in the same change.

## 5. Tests

`tests/calibration/test_fit_report.py` covers: the label→`Y_1` mapping, SYN exclusion,
base rate (including the empty-denominator case), committed-fixture counts (3/27/5),
prereg-matching thresholds, F-1/F-2/F-3 pass-fail arithmetic (including
at-threshold), F-4's non-decidability and owned-multi-day recording, ladder order,
the real-cohort verdict (F-1 failing, F-4 unevaluated), `RESEARCH_ONLY` retention,
the no-probability field contract, §10 blockers present even when all gates pass,
blocker listing, slot-status vocabulary, and byte-equality of the committed JSON/MD
against a fresh regeneration.

## Revision history

| Date | Change |
|---|---|
| 2026-09-05 | Initial skeleton (sprint item 1.3): preregistered F-1..F-4 gate ladder over committed inputs; honest `NOT_CALIBRATED` verdict with F-1 named; slot statuses in the snapshot contract's vocabulary; §10 fit blockers carried on the report; no fitting performed |
