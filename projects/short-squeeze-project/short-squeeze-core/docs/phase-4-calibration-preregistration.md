# Phase 4 — Walk-forward horizon calibration preregistration

**Status:** DRAFT — written before any Phase 4 fitting; **not yet owner-reviewed**.
Fitting must not start until the open items in [§10](#10-open-items-to-lock-before-any-fit) are locked.
**Spec:** [SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md](research/SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md) (`squeeze_causal_research_spec.v1`)
**Roadmap:** [SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md](research/SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md) Phase 4 (closes spec §19 limitation 1)
**Sprint:** [SHORT_SQUEEZE_SPRINT_PLAN_2026-09-06.md](research/SHORT_SQUEEZE_SPRINT_PLAN_2026-09-06.md) item 1.1
**Version:** `phase_4_calibration_preregistration.v0.6-draft` (O-2, O-3, O-4 addenda linked; audit corrections 2026-09-05)

## 1. Purpose and ground rules

This document fixes — **before any model is fit** — (1) the dataset, (2) the outcome
definition, (3) the model sequence, (4) the regime slices, (5) the walk-forward
purge/embargo rule, (6) the metric set, (7) the GameStop non-dominance rule, and
(8) the pre-registered success/failure thresholds, for the Phase 4 horizon-probability
calibration of [SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md](research/SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md) §9–§13.

Ground rules, carried from the spec, ADRs, and the recorded sprint dataset decision:

- The calibration target is the **detection research predicate** (±25%/24h), **never a
  squeeze-mechanism claim** (spec §8; mechanism-class adjudication is a separate,
  separately-gated extension — sprint item 1.7).
- Calibration is a **research result, not a decision**: signal ≠ decision ≠ execution
  (spec §17), and no variant is auto-promoted to production policy
  (ADRs 0065/0067/0068).
- Nothing here authorizes live signal promotion, threshold changes, or trading
  capability ([LIMITATIONS.md](LIMITATIONS.md), ADR-0047).
- Missing or stale evidence is never fabricated or backfilled with current values
  (ADRs 0047/0062); `model_confidence` stays distinct from `data_confidence` (spec §16).
- Results publish with `COUNTERFACTUAL_EXPLORATION_ONLY` and `SMALL_SAMPLE_WARNING`
  framing until sample size and forward evidence justify otherwise (ADR-0067).

## 2. Dataset (pre-registered)

### 2.1 Sources and measured counts

All counts below are measured from the **committed fixture files** at the Phase 3F
registry state (tests that pin these counts: `tests/analysis/test_runner.py`,
`tests/analysis/test_registry_quality.py`).

| Quantity | Count | Source (committed fixture) |
|---|---:|---|
| Registered registry entries | 48 | `tests/fixtures/research/phase_3b_case_registry.json` (`phase_3b_case_registry.v1`) |
| — of which `COMPLETE` | 46 | same |
| — of which `EVALUATION_ONLY` | 1 (AACP, permanent `OUTCOME_UNEVALUABLE` — [AACP_OUTCOME_EXCLUSION_RECORD.md](calibration/AACP_OUTCOME_EXCLUSION_RECORD.md)) | same |
| — of which `BLOCKED_CONFLICTING_IDENTITY` | 1 (`KLOS_IDENTITY_CONFLICT`, excluded) | same |
| — of which ADR-0053 synthetic evaluations | 11 (`SYN_*`, excluded from historical analysis) | same |
| — historical case boundaries (excl. SYN, excl. KLOS) | 36 (incl. batch-05 AACB/AACG/AACI/AACP/AADX) | same |
| — unique historical symbols | 34 (BIYA ×3 boundaries) | same |
| Unique symbols in registry (incl. SYN symbols) | 46 | same |
| Registered BIYA boundaries | 3 (`BIYA_EARLIEST_BOUNDARY`, `BIYA_ARTIFACT_DISCOVERY`, `BIYA_LATEST_BOUNDARY`) | same |
| Analysis dataset case boundaries | 35 | `tests/fixtures/analysis` / `test_runner.py` constants |
| Analysis dataset unique symbols | 33 | same |
| Research-dataset rows | 46 (11 SYN + 35 historical-with-outcomes) | `phase_3b_research_dataset.json` (registry minus KLOS minus AACP) |
| — unique symbols in research dataset | 44 (11 SYN + 33 historical) | same |
| Committed outcome-observation files | 35 (33 unique symbols; BIYA ×3; 33 `COMPLETE` + 2 `PARTIAL`) | `tests/fixtures/research/*_outcome_observation.json` |
| Pipeline-registered boundaries incl. batch 05 | 36 (31 pre-batch-05 + AACB/AACG/AACI/AACP/AADX) | reconciled accounting (O-5, below) |
| Evaluable Stage-2 outcome labels | 35 (AACP has no outcome file) | reconciled accounting (O-5, below) |
| Policy threshold `min_case_count_for_recommendation` | 30 (**met**) | `src/squeeze_core/calibration/policies/phase_3d_calibration_policy_v1.json` |

> **O-5 reconciliation (2026-09-05, resolved):** counts above are measured from the
> regenerated committed fixtures. The registry now **includes batch-05** (48 entries;
> generator + Phase 3B/3C fixtures + analysis-test constants updated in the same
> change). The earlier "34 evaluable Stage-2 labels" figure counted 30 prior + 4
> batch-05 before the Batch-04 BIYA-artifact outcome was regenerated into the fixture
> set. The single source of truth lives in
> [COHORT_EXPANSION_PROGRESS.md](calibration/COHORT_EXPANSION_PROGRESS.md)
> (§ "Reconciled accounting").

### 2.2 Units of analysis and the dependence rule

- **Outcome observations are the modeling units.** Repeated boundaries for one symbol
  are **dependent** observations (ADR-0054). BIYA contributes three boundary
  observations but one independent symbol cluster.
- **Primary evaluation is at the unique-symbol (cluster) level**: any
  train/test/validation split must keep all of a symbol's boundaries in the same
  fold. Boundary-level results may be reported as secondary with an explicit
  dependence warning, never as independent evidence.
- **Intervals never assume independence** (ADR-0054): boundary-level intervals and
  reports carry the pipeline's `HISTORICAL_CASE_BOUNDARIES_NOT_INDEPENDENT` limitation
  and are secondary; primary interval estimates are unique-symbol-level.

### 2.3 Accepted limitations (recorded, not waived)

- **All owned outcome labels have `horizon = 24_HOURS`** (measured from
  `tests/fixtures/research/*_outcome_observation.json`, e.g. `KLRS_ARTIFACT_DISCOVERY`
  → `horizon: 24_HOURS`), per `phase_3b_outcome_label_policy.v1`. **Only the
  1-trading-day horizon is directly supportable today.** The 3/5/10/20-day slots in
  `HorizonModelSnapshot.hazard_by_horizon` must remain `RESEARCH_ONLY` (never forced
  `CALIBRATED`) unless owned multi-day forward-path data is acquired and registered
  (see [§10](#10-open-items-to-lock-before-any-fit), open item O-1).
- **Detection-evaluability** is limited (ADR-0067 recorded 28 of 30 boundaries
  detection-unevaluable at n=30; at the current 48-entry registry the regenerated
  Phase 3C confusion matrix measures **33 of 35 historical case boundaries**
  detection-unevaluable under the retained baseline policy —
  `phase_3c_historical_case_boundary_analysis.json`, `analysis_unit: CASE_BOUNDARY`,
  2 TP / 33 unevaluable / 35; at the unique-symbol level
  `phase_3c_confusion_matrix_summary.json` measures 1 TP / 32 unevaluable / 33). The
  sprint dataset decision accepts this limitation explicitly for Phase 4. No Batch 07
  semantics gate is lowered to inflate evaluability.
- **No backfill into unsupported horizons:** the evaluator's `occurrence_probability`
  fallback (`_horizon_probabilities_from_model`) must **not** fill the 3/5/10/20-day
  slots from a 1-day estimate. Partial `hazard_by_horizon` coverage keeps the
  uncovered slots `RESEARCH_ONLY`.
- Outcome labels describe forward price movement from a frozen boundary; they do not
  establish short-squeeze causation (ADR-0068).

## 3. Outcome definition (pre-registered)

- **Horizons (spec §9):** the target tuple is `HORIZON_DAYS = (1, 3, 5, 10, 20)`
  (trading days; `squeeze_core/intelligence/evaluator.py`). Horizon 1 is served by the
  owned 24_HOURS outcome labels (with the Stage-2 adjusted-Monday convention for
  weekend boundaries); horizons 3/5/10/20 require owned multi-day forward paths (O-1).
- **Reference price:** `first_eligible_trade_bar_close_at_or_after_boundary.v1`
  (from `phase_3b_outcome_label_policy.v1`).
- **Detection predicate (retained, unchanged):** `phase_3b_research_detection_policy.v1`
  (`PRICE_RANGE`, `MARKET_DATA_AVAILABLE`, `COMPLETED_BAR_AVAILABLE`) stays in force;
  the gate variants rejected by ADR-0067 (`momentum_full`, `short_pressure_core`,
  `momentum_pct_change`) are not revisited in Phase 4.
- **Predicate (unchanged production policy, retained by ADR-0068):** upward crossing
  of **+25%** within **24 hours** from the frozen boundary; the mirror downward
  predicate is **−25%** and is retained for outcome-policy continuity but is **not** a
  squeeze target.
- **Calibration target (occurrence):** for horizon k, `Y_k = 1` if the upward +25%
  crossing is observed within k trading days of the boundary (k = 1 only while O-1 is
  open). Time origin is the frozen boundary instant; events are determined from the
  point-in-time forward series only (ADR-0062 — no current prices).
- **Calibration target (magnitude, separate model per spec §11):** the maximum
  observed upward move percent within the window, modeled and reported separately from
  occurrence. Magnitude never substitutes for occurrence probability.
- **Mechanism labels** (`MARKET_SQUEEZE`, `LENDER_SQUEEZE`, `GAMMA_AMPLIFIED`,
  `ATTENTION_AMPLIFIED`, `COMBINED_REFLEXIVE`, …) are **out of scope** for this
  preregistration (spec §8, §21; sprint item 1.7 gate).

## 4. Model sequence (pre-registered)

1. **Interpretable logistic baseline** for occurrence at the 1-day window, and — when
   O-1 is closed — a **discrete-time hazard / Cox baseline** for
   time-to-first-crossing over the supported horizons, with event = first upward +25%
   crossing and right-censoring at the end of the owned forward window (never beyond
   owned data). The logistic/hazard baseline is the Phase 4 deliverable.
2. **Calibrated gradient-boosted trees** only if the pre-registered sample-size gates
   in [§8](#8-pre-registered-success-and-failure-thresholds) pass **and** the tree variant
   beats the baseline by the pre-registered margins: held-out **Brier skill score ≥
   baseline + 0.05 and PR-AUC ≥ baseline + 0.05**, with C-1..C-3 still passing on the
   same folds. Trees are an optional second step, never a replacement for the
   interpretable baseline.
3. **Temporal (sequence) models** require explicit written justification appended to
   this document before fitting (spec §10); the default is no temporal model.

Any regularization or feature-selection procedure is fixed here, not chosen by
outcome performance: the baseline is fit with the pre-registered feature set
([§5](#5-features-pre-registered-rules)) and, where needed, L1 (lasso) penalty chosen
by cross-validation on the **training** folds only.

## 5. Features (pre-registered rules)

- **Construction rules (from spec §5):** features are point-in-time and
  leakage-free; level / change / velocity / acceleration / percentile / z-score are
  kept distinct; the forbidden conflations in spec §5 never occur
  (`daily_short_volume ≠ outstanding_short_interest`, `FTD ≠ naked short count`,
  `threshold list ≠ forced-cover countdown`).
- **Missingness:** a feature the evaluator treats as `UNKNOWN` or absent at the
  boundary is modeled as missing — never imputed with later or current values
  (ADRs 0047/0062). Missingness indicators are permitted.
- **Candidate feature groups:** the causal dimension inputs the evaluator already
  consumes at the boundary (vulnerability, constraint pressure, short stress,
  ignition strength, reflexivity strength, remaining fuel) and their direct
  evidence-metric inputs (spec §3, §5 groups A–I).
- **Feature freeze addendum:** the exact final feature table is fixed outcome-blind
  in [phase-4-calibration-feature-table-addendum.md](phase-4-calibration-feature-table-addendum.md)
  (open item O-3) — the exact point-in-time feature list from the evaluator's
  evidence inputs (25 rule outcomes, 14 evidence metrics, 28 snapshot fields, 6
  derived dimension scores), **appended before any fit and before any
  label-timestamp or outcome inspection**. Feature *selection by outcome* is
  forbidden.

## 6. Regime slices and the GameStop non-dominance rule (pre-registered)

- **Slices (spec §12):** `pre-2020`, `meme-regime`, `high-rate` (+ a
  `post-normalization` slice so the partition is exhaustive). Exact calendar cutpoints
  are fixed outcome-blind in
  [phase-4-calibration-regime-cutpoints-addendum.md](phase-4-calibration-regime-cutpoints-addendum.md)
  (open item O-2) with a cited external regime calendar (SEC staff report, FOMC) and
  are never chosen after inspecting label timestamps or outcomes.
- **Empty slices:** any slice with zero (or below the §8 minimum) boundaries is
  reported as empty; it is never padded, re-weighted, or silently dropped from the
  report.
- **Non-dominance:** no single symbol cluster may contribute more than **30%** of the
  events in any training fold, and every published result must include a
  leave-one-symbol-out diagnostic showing the worst-case metric movement when the
  largest cluster is removed. This generalizes the spec's GameStop rule to whatever
  cluster is dominant in the data; it applies even though the current cohort contains
  no GameStop case.

## 7. Walk-forward splits: purge and embargo (pre-registered)

- **Splits:** chronological, ordered by boundary time. Repeated symbol boundaries are
  grouped (ADR-0054) and never straddle a fold boundary.
- **Purge/embargo:** a **purge** of `w` and an **embargo** of `e` follow each training
  boundary; exact values are fixed in the same outcome-blind addendum as O-2 —
  **purge `w` = 30 calendar days, embargo `e` = 15 calendar days** per
  [phase-4-calibration-regime-cutpoints-addendum.md](phase-4-calibration-regime-cutpoints-addendum.md).
  Fold results are reported per fold and pooled; the pooled report is the one judged
  against [§8](#8-pre-registered-success-and-failure-thresholds).
- **Degeneracy gate:** if chronological splitting leaves fewer than two non-empty
  evaluation folds (e.g. all labels cluster at one or two boundary instants), the
  result is **`NOT_CALIBRATED`** and is reported with the degeneracy named — no
  random/time-shuffled split is substituted to manufacture folds.
- **Scaffold note (2026-09-05):** the split machinery is implemented
  (`src/squeeze_core/calibration/walkforward.py`,
  [phase-4-walk-forward-harness.md](phase-4-walk-forward-harness.md)) and the
  committed cohort measures **2 non-empty evaluation folds with 0 admissible
  training boundaries** under these windows. This is a structural measurement,
  not a fit result; it is recorded for item 1.3's honest reporting and implies
  no change to the outcome-blind windows.

## 8. Pre-registered success and failure thresholds

These are decision rules over quantities measured *after* fitting; none were chosen
from outcome data.

### 8.1 Feasibility gates (failure ⇒ `NOT_CALIBRATED`, keep `RESEARCH_ONLY`)

| Gate | Rule (measured on the modeling set) |
|---|---|
| F-1 evaluable positives | positive events ≥ 10 (counted per §3 at horizon 1) |
| F-2 evaluable negatives | negative events ≥ 10 |
| F-3 fold structure | ≥ 2 non-empty chronological evaluation folds (§7) |
| F-4 horizon data | for any horizon k > 1 to be calibrated: owned forward-path data covering k (O-1) |

### 8.2 Calibration success (must pass on held-out evaluation folds, never training)

| Criterion | Pass threshold | Fail action |
|---|---|---|
| C-1 calibration curve slope | within [0.8, 1.2] on pooled held-out predictions | `NOT_CALIBRATED` |
| C-2 calibration curve intercept | \|intercept\| ≤ 0.2 (log-odds scale) | `NOT_CALIBRATED` |
| C-3 Brier skill score vs. base rate | > 0 at horizon 1 | `NOT_CALIBRATED` |

If F-1…F-4 or C-1…C-3 fail, the Phase 4 result is reported honestly as
**not-yet-calibrated** with the failing gate named (sprint 1.3 acceptance) — the
evaluator's `RESEARCH_ONLY` slots are retained; nothing is force-flipped to
`CALIBRATED`.

> **Reporting-skeleton note (2026-09-05):** the §8.1 feasibility ladder and the
> honest `NOT_CALIBRATED` report are implemented ahead of any fit
> (`src/squeeze_core/calibration/fit_report.py`,
> [phase-4-fit-report-skeleton.md](phase-4-fit-report-skeleton.md)); the committed
> cohort measures **F-1 failing** (3 positives < 10) with F-2/F-3 passing and F-4
> recorded as owner data-feasibility (`passed=None`, O-1). On the committed cohort
> the F-1 failure alone decides §8.2's honest-reporting arm; the C-1…C-3 gates
> remain unevaluable until the owner-gated fitting stage runs. Slot statuses use
> exactly the `HorizonModelSnapshot` contract vocabulary (`RESEARCH_ONLY |
> CALIBRATED`); nothing is force-flipped.

## 9. Metrics (pre-registered; never raw accuracy)

Primary, reported on held-out folds:

- Brier score and **Brier skill score vs. the base rate** (C-3 uses the latter);
- **PR-AUC** (precision-recall, appropriate for rare events); **precision and recall
  at the pre-registered operating point** (no threshold optimization) and precision@K
  for K ∈ {3, 5};
- **Calibration curve** with slope/intercept diagnostics (C-1/C-2) and, when the
  sample allows, a binwise plot with Wilson intervals;
- **Log loss**;
- **Expected trading value under explicit costs** (spec §17): `EV = P(win)×E[win] −
  P(loss)×E[loss] − costs`, reported **only** under a pre-registered reference cost
  set — **drafted 2026-09-05** in
  [phase-4-calibration-cost-set-addendum.md](phase-4-calibration-cost-set-addendum.md)
  (open item O-4): commission 0.50% + slippage 0.50% per side (round-trip 2.00%) for
  the long, 1× cash, ≤24 h reference position; financing 0.00%. EV is never used to
  tune thresholds or to claim backtest/P&L validity.

Magnitude model metrics: mean absolute error / pinball loss and an exceedance
calibration check, reported separately from occurrence metrics.

Every report carries `COUNTERFACTUAL_EXPLORATION_ONLY` / `SMALL_SAMPLE_WARNING` /
`NO_THRESHOLD_AUTO_PROMOTION` framing per ADRs 0067/0068 until the §8 gates pass and
forward evidence justifies promotion of the *framing* (never of policy).

The base rate and the positive/negative event counts are always reported alongside
the metrics; no outcome-informed resampling or class-weight tuning is permitted (class
imbalance is reported, not engineered away).

## 10. Open items to lock before any fit

| ID | Item | Who | Blocker if unresolved |
|---|---|---|---|
| O-1 | Owned multi-day forward-path data for horizons 3/5/10/20, or explicit acceptance that those slots stay `RESEARCH_ONLY` | Owner (data feasibility) | Horizons > 1 cannot be calibrated |
| O-2 | Regime cutpoints + purge/embargo values — **drafted 2026-09-05** in [phase-4-calibration-regime-cutpoints-addendum.md](phase-4-calibration-regime-cutpoints-addendum.md) (outcome-blind; SEC/FOMC cited calendar; purge 30 / embargo 15 calendar days) | Reviewer confirms addendum | §6/§7 executable once confirmed |
| O-3 | Final feature table (outcome-blind) — **drafted 2026-09-05** in [phase-4-calibration-feature-table-addendum.md](phase-4-calibration-feature-table-addendum.md): exact point-in-time list from the evaluator's evidence inputs (25 rule outcomes / 14 evidence metrics / 28 snapshot fields / 6 derived dimension scores), missingness + encoding rules fixed | Reviewer confirms addendum | §5 not executable |
| O-4 | Reference cost set for EV reporting (owner-specified, not tuned) — **drafted 2026-09-05** in [phase-4-calibration-cost-set-addendum.md](phase-4-calibration-cost-set-addendum.md): fixed reference position (long, 1× cash, ≤24 h), commission 0.50% + slippage 0.50% per side (round-trip 2.00%), financing 0.00%, fixed EV expression + reporting constraints | Owner confirms addendum | EV metric not reportable |
| O-5 | ~~Reconcile registry accounting across [COHORT_EXPANSION_PROGRESS.md](calibration/COHORT_EXPANSION_PROGRESS.md) vs. committed fixtures~~ — **Resolved 2026-09-05**: reconciled accounting added to the COHORT doc **and the registry fixture regenerated to include batch-05** (48 entries = 36 historical boundaries incl. batch-05 / 34 symbols / 11 SYN / 1 AACP EVALUATION_ONLY / 1 KLOS; 35 outcome files / 46 dataset rows / 35 evaluable / 1 AACP exclusion). Single source of truth: regenerated fixtures + COHORT doc | Owner + reviewer | ~~Dataset §2 not fully locked~~ — closed; reviewer re-check on final approval |
| O-6 | Owner review of this preregistration (status → approved or amended) | Owner | No fitting at all |

## 11. Non-goals

- No squeeze-mechanism label claim from detection-predicate outcomes.
- No change to Phase 3A/B/C/D policies, detection gates, or outcome thresholds.
- No promotion of any fitted variant to live signal status; no threshold optimization;
  no backtest or P&L claims.
- No imputation of missing historical evidence with current values (ADR-0062).
- No raw accuracy as an evaluation metric.
- No calibration of magnitude conflated with occurrence.
- No re-run of outcome-threshold sensitivity variants (`upward_28`, `upward_30`,
  `strict_35`) — rejected by ADR-0068 decisions 2–4.
- No Adam scoring calibration or weight tuning (`adam_evidence_gated_prime.v1`) —
  deferred per ADR-0067 decision 5 and ADRs 0069/0070.

## 12. Acceptance (sprint item 1.1)

A reviewer can state, before any fitting happens: **what** will be fit (logistic/hazard
baseline on the occurrence and magnitude of the ±25%/24h detection predicate, §3–§4),
**on what data** (the committed 24-hour outcome-observation set at the current registry
state, with dependence per ADR-0054, §2), **how it will be validated** (chronological
grouped walk-forward with purge/embargo, §6–§7), and **what counts as success**
(§8 gates plus the §9 metric set, with `NOT_CALIBRATED` as the honest default).

## Revision history

| Date | Change |
|---|---|
| 2026-09-05 | Initial draft (v0.1); dataset counts measured from committed fixtures; 24h-horizon data limitation and O-1..O-6 recorded before any fitting |
| 2026-09-05 | O-5 resolved (part 1): reconciled accounting added to [COHORT_EXPANSION_PROGRESS.md](calibration/COHORT_EXPANSION_PROGRESS.md); §2 updated to measured counts; SYN entry count corrected 9→11 |
| 2026-09-05 | O-5 resolved (part 2): registry fixture regenerated to include batch-05 (generator `_batch05_entries()`; AACP `EVALUATION_ONLY`); Phase 3B/3C fixtures + analysis-test constants updated in the same change; §2 table re-measured (48 registry entries = 36 historical boundaries / 34 symbols / 11 SYN / 1 AACP / 1 KLOS; 46 dataset rows; 35 evaluable labels) |
| 2026-09-05 | Spec/ADR audit (v0.2-draft, outcome-blind): gaps closed — spec §9 horizon tuple `(1,3,5,10,20)` enumerated with 1-day ≡ owned 24h label; §10 hazard event/censoring pinned and tree-variant margins fixed (Brier skill ≥ +0.05, PR-AUC ≥ +0.05); §13 precision+recall added and base-rate/imbalance reporting required; ADR-0054 independence framing (`HISTORICAL_CASE_BOUNDARIES_NOT_INDEPENDENT`); ADR-0067 retained detection predicate + rejected gate variants + current 33/35 unevaluable measurement + no occurrence-probability backfill into unsupported horizons; ADR-0068 outcome-variant rejection + Adam deferral added to non-goals |
| 2026-09-05 | O-2 addendum drafted and linked (v0.3-draft): exhaustive 4-slice partition (pre-2020 / meme-regime / high-rate / post-normalization) from the SEC meme-stock staff report + FOMC calendar; purge 30 / embargo 15 calendar days with re-derivation rule; pending reviewer confirmation |
| 2026-09-05 | O-3 addendum drafted and linked (v0.4-draft): exact point-in-time feature table from the evaluator's evidence inputs (25 rule outcomes / 14 evidence metrics / 28 snapshot fields / 6 derived dimension scores), fixed encodings + missingness indicators, explicit non-features; pending reviewer confirmation |
| 2026-09-05 | O-4 addendum drafted and linked (v0.5-draft): reference cost set for EV reporting — fixed reference position (long, 1× cash, ≤24 h), commission 0.50% + slippage 0.50% per side (round-trip 2.00%), financing 0.00%, fixed EV expression + reporting constraints; not-tuned/outcome-blind; pending owner confirmation |
| 2026-09-05 | Cross-addendum audit (v0.6-draft, outcome-blind, no fixture changes): §2.1 gains the research-dataset rows (46 rows / 44 unique symbols) to match the COHORT single source of truth; §2.3 detection-evaluability citation corrected to `phase_3c_historical_case_boundary_analysis.json` (CASE_BOUNDARY: 2 TP / 33 unevaluable / 35) with the unique-symbol-level figure (1 TP / 32 unevaluable / 33) noted alongside; all measured counts re-verified against committed fixtures |
| 2026-09-05 | §7 scaffold note: walk-forward split machinery implemented (sprint item 1.2); committed cohort measures 2 non-empty evaluation folds / 0 admissible training boundaries under the pre-registered windows — recorded for item 1.3's honest reporting, no windows changed |
| 2026-09-05 | §8.2 reporting-skeleton note: feasibility ladder + honest `NOT_CALIBRATED` reporting implemented ahead of any fit (sprint item 1.3); committed cohort measures F-1 failing (3 positives < 10), F-2/F-3 passing, F-4 owner data-feasibility (`passed=None`, O-1); slot statuses fixed to the snapshot contract vocabulary; no fitting performed |
