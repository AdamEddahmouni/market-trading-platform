# Short Squeeze Lane — Next Full Sprint Plan

| Field | Value |
|---|---|
| Created | 2026-09-06 |
| Scope | Finish the causal Short Squeeze lane end-to-end (roadmap Phases 4–7) plus repo close-out |
| Source | [SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md](SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md), [SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md](SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md) |
| Product version | 0.16.0 (current) |
| Status | Open — 3/26 items closed (0.3, 0.4, 1.2); 1.3 reporting half implemented (fit gated on O-2/O-3/O-4/O-6 confirmations) |
| Ownership | Short-squeeze child repo (`short-squeeze-project`); platform-facing items coordinated through the parent monorepo (guarded import) |

**How to use:** tick `[ ]` → `[x]` as items close. Work that lands in the child repo follows
its own commit/PR conventions; parent snapshot refresh happens through the guarded monorepo
import (`docs/MONOREPO_WORKFLOW.md`), never by editing the snapshot directly.

## Verified starting state (2026-09-05)

| Area | State |
|---|---|
| Product | Short Squeeze Research Screener v0.16.0, read-only (no orders, no recommendations) |
| Causal evaluator | `squeeze_causal_baseline.v4` — evidence-gated state machine, fail-closed `UNEVALUABLE`, mechanism labels, separated confidence, `RESEARCH_ONLY` horizon slots |
| Phase 3F cohort | 29 IBKR frozen-boundary symbols; 48-entry registry (36 historical case boundaries incl. batch 05 / 34 symbols / 11 SYN / 1 AACP evaluation-only / 1 KLOS blocked); 35 evaluable Stage-2 outcome labels; 1 permanent exclusion (AACP) |
| Calibration harness | `tools/run_calibration_suite.py` (Phase 3D outcome/detection counterfactuals) — exists |
| Horizon contract | `HorizonModelSnapshot` + evaluator consumption (`_horizon_probabilities_from_model`) — **consumer exists, producer does not** |
| Exhaustion | `fuel.py::estimate_exhaustion_risk`, `EXHAUSTION` state assignment — implemented; exit evidence package + cooldown spec missing |
| Child repo | `fix/frozen-followups` carries the doc-link checker + doc fixes (`7e63c78`); **not merged to `main`, parent snapshot not re-synced** |
| Suite health | Batch08/09 + intelligence green; **11 operation-readiness tests blocked** by missing `batch07/synthetic-batch05/raw/` fixture data |

The 11 operation-readiness failures are a **cohort-expansion fixture drift**, not a code
defect: commit `0b40834` (Phase 3E) expanded `FROZEN_COHORT` to 15 symbols (added KLRS,
SG) and updated `test_operation_readiness.py` to expect 15 cases, but the
`tests/fixtures/acquisition/batch07/synthetic-batch05/` manifests and the committed golden
report (`operation-readiness-report.{json,md}`) still describe the **original 13-symbol
Batch 01** freeze — the generator was never re-run for the expanded cohort. The tests read
only manifests (raw OHLCV is deliberately unreadable), so the fix is: add the KLRS and SG
rows to the batch07 request/artifact manifests, then regenerate the golden report via
`build_report` and confirm byte-identical output. KLRS/SG rows already exist in the
batch08 29-symbol synthetic mirror.

---

## 0. Close-out and suite health (do first — unblocks everything)

### 0.1 — Land the pending child branch

- **Problem:** `fix/frozen-followups` (`7e63c78`) holds the doc-link checker, its tests,
  the new doc-links CI workflow, and the docs fixes, but `main` is at `78b7467`.
- **Fix:** push the branch, open the PR, merge per the child repo's workflow.
- **Acceptance:** `main` includes the checker; the parent snapshot records the new
  `source_commit` after the guarded import below.

### 0.2 — Re-sync the parent snapshot

- **Fix:** parent branch off `main` → `python tools/monorepo_guard.py import short-squeeze-project`
  (plain-file sync per the established pattern) → regenerate the history ledger → validate →
  PR → merge.
- **Acceptance:** `workspace-manifest.json` `source_commit` points at the merged child
  commit; `monorepo_guard.py validate` passes; whole-repo doc-link scan exits 0.

### 0.3 — ✅ Close the operation-readiness fixture gap

- **Fix:** extend the batch07 synthetic manifests to the full 15-symbol `FROZEN_COHORT`
  (add KLRS + SG rows from the batch08 mirror), then regenerate
  `operation-readiness-report.{json,md}` via `build_report` and verify byte-identical output.
- **Acceptance:** `pytest tests/acquisition/test_operation_readiness.py` — 0 failed, 0 errors
  (all 11 unblocked); full suite green except the CI-baseline and live-IB-Gateway buckets.

### 0.4 — ✅ Suite greenness baseline check

- **Fix:** run the full suite after 0.3 and record the remaining environmental buckets
  (compatibility tests need CI baseline history; IBKR collector tests need a live gateway).
- **Acceptance:** roadmap track D statement is current and accurate in the roadmap doc.

---

## 1. Phase 4 — Walk-forward horizon probability calibration

**Closes spec §19 limitation 1.** Goal: `HorizonModelSnapshot(status=CALIBRATED,
pit_verified=True, hazard_by_horizon)` entries that flip the evaluator's horizon slots to
`CALIBRATED` with model-version provenance. This is the single largest remaining milestone.

**Dataset decision (recorded):** Phase 4 calibrates on the **35 evaluable Stage-2 outcome
labels that exist and are owned** (48-entry registry as context; reconciled accounting in
[COHORT_EXPANSION_PROGRESS.md](../calibration/COHORT_EXPANSION_PROGRESS.md)), accepting the ADR-0067
detection-evaluability limitation explicitly in the preregistration. Mechanism-class
adjudication (spec §21) is a **separate, optional extension**, not a hard Phase-4 gate —
gated on its own item (1.7) so calibration work starts from a stable registry now.
Interpretability requirement: a validated logistic/hazard baseline is the deliverable;
trees only if data justifies them.

### 1.1 — Phase-4 preregistration

- **Fix:** `docs/phase-4-calibration-preregistration.md` naming (1) the dataset (35 evaluable
  labels, 48-entry registry context, dependent-observation rule per ADR-0054), (2) outcome definition
  (detection predicate at ±25%/24h — no mechanism claim), (3) the model sequence
  (logistic/hazard baseline first), (4) regime slices (pre-2020, meme regime, high-rate),
  (5) embargo/purging rule, (6) the metric set (Brier, PR-AUC, precision@K, calibration
  curves, log loss, EV under explicit costs — never raw accuracy), (7) GameStop
  non-dominance rule, (8) the pre-registered success/failure thresholds.
- **Draft added 2026-09-05:** [phase-4-calibration-preregistration.md](../phase-4-calibration-preregistration.md)
  (v0.1-draft) — dataset counts measured from committed fixtures, 24h-horizon data
  limitation recorded, O-1..O-4 and O-6 open items listed (O-5 resolved 2026-09-05;
  O-2 addendum drafted 2026-09-05 — pending reviewer confirmation; O-3 feature-table
  addendum drafted 2026-09-05 — pending reviewer confirmation; O-4 cost-set addendum
  drafted 2026-09-05 — pending owner confirmation).
  **Not owner-reviewed; do not start fitting until the remaining open items are locked**
  (item not self-closed).
- **Acceptance:** a reviewer can tell exactly what will be fit, on what data, and what
  counts as success before any fitting happens. Modeled on the Phase 3F preregistration
  pattern.

### 1.2 — ✅ Walk-forward harness scaffold

- **Problem:** no chronological walk-forward machinery existed;
  `run_calibration_suite.py` is Phase 3D counterfactual-only.
- **Fix:** `src/squeeze_core/calibration/walkforward.py` orders boundaries
  chronologically, groups repeated symbol boundaries as dependent (ADR-0054),
  applies the O-2 purge/embargo windows (30/15 calendar days), slices regimes,
  and enforces the §7 degeneracy gate — structure only, outcome-blind, no
  fitting. Runner: `tools/run_walk_forward_plan.py` (plan + diagnostics JSON/MD
  under `reports/calibration/`). Tests:
  `tests/calibration/test_walkforward.py` (20 unit/fixture tests).
- **Honest structural finding (recorded 2026-09-05):** the committed 35-boundary
  historical cohort has exactly **2 non-empty evaluation folds** (the §7
  minimum) and **0 admissible training boundaries in both folds** — the two
  boundary instants sit inside each other's purge/embargo gap, and all 35
  boundaries are `POST_NORMALIZATION` (3 empty regimes reported as empty).
  Item 1.3 must report this structure as-is (`NOT_CALIBRATED`,
  `RESEARCH_ONLY` retained); the outcome-blind windows are not relaxed to
  manufacture a fit.
- **Acceptance (met):** the harness partitions the 35-boundary outcome set into
  folds and emits per-fold + aggregate diagnostics; unit tests cover the
  purge/embargo and dependent-observation logic.
- **Doc:** [phase-4-walk-forward-harness.md](../phase-4-walk-forward-harness.md)

### 1.3 — Logistic/hazard baseline fit

- **Fix:** fit the interpretable baseline on the preregistered features with honest
  missingness (features the evaluator treats as `UNKNOWN` stay out or are explicitly
  modeled as missing); produce `hazard_by_horizon` for (1, 3, 5, 10, 20).
- **Acceptance:** diagnostics from 1.2 pass the preregistered thresholds or the result is
  honestly reported as not-yet-calibrated (`RESEARCH_ONLY` retained — no forced flip).
- **Progress (2026-09-05):** the reporting half is implemented ahead of any fit
  (`src/squeeze_core/calibration/fit_report.py`, runner
  `tools/run_fit_report_skeleton.py`, tests `tests/calibration/test_fit_report.py`):
  the preregistered F-1..F-4 feasibility ladder runs over committed inputs, and the
  honest `NOT_CALIBRATED` report is committed with the failing gate named — **F-1**
  (3 positives < 10; F-2 27, F-3 2-fold pass, F-4 owner data-feasibility recorded as
  `passed=None` under O-1). Slot statuses use the `HorizonModelSnapshot` contract
  vocabulary; `RESEARCH_ONLY` retained; `fit_attempted=false` with §10 blockers
  (O-2/O-3/O-4/O-6 + F-1) carried on the report. The fit itself stays blocked until
  O-2/O-3/O-4/O-6 are confirmed; once they are, the fit runs into this prepared
  ladder and the report is re-issued — either keeping `NOT_CALIBRATED` or, if every
  gate passes, as a fit result. Report:
  `reports/calibration/phase_4_fit_report_skeleton.{json,md}`;
  doc: [phase-4-fit-report-skeleton.md](../phase-4-fit-report-skeleton.md).
  Item 1.3 remains **open** until the fit attempt itself is made (or the honest
  NOT_CALIBRATED result stands as the final Phase 4 outcome).

### 1.4 — Calibrated `HorizonModelSnapshot` wiring

- **Fix:** when (and only when) diagnostics pass, emit `HorizonModelSnapshot` entries with
  `pit_verified=True`, model-version provenance, and the required interpretation language;
  wire through `evaluate_squeeze_intelligence` (already consumes the contract).
- **Acceptance:** a replay shows `CALIBRATED` horizon slots carrying `model_version`; the
  UI renders them with the interpretation language (no predictive-validation claim, no
  threshold optimization); `explanation.py` gains the calibrated-probability evidence node.

### 1.5 — Magnitude calibration

- **Fix:** calibrate magnitude separately from occurrence (spec §11); wire the estimate
  into `MagnitudeEstimateSnapshot`.
- **Acceptance:** magnitude reports carry their own status/method/model_version and are
  never conflated with occurrence probability.

### 1.6 — ADR + roadmap update

- **Fix:** new ADR recording the Phase-4 findings and any policy deltas; update
  `SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md` Phase-4 section to closed with artifacts;
  update `SHORT_SQUEEZE_CAPABILITY_GAP_ANALYSIS.md` gap G4 row.
- **Acceptance:** a reader of the roadmap can see what was fit, on what, and what the
  calibrated slots mean — and what they do **not** authorize (no live promotion).

### 1.7 — Mechanism-class adjudication (optional extension, separately gated)

- **Problem:** outcome labels are a detection predicate; mechanism labels
  (`MARKET_SQUEEZE`, `LENDER_SQUEEZE`, `GAMMA_AMPLIFIED`, …) need separate adjudication
  (spec §8, §21).
- **Fix:** a documented labeling/adjudication process applied to the registry, with
  adjudicator instructions and an inter-rater check where feasible.
- **Acceptance:** mechanism labels exist for the adjudicated subset with a documented
  process; nothing claims mechanism labels where only detection labels exist.
- **Gate:** only start if 1.1–1.6 land cleanly; otherwise carry to the next sprint.

---

## 2. Phase 5 — Exhaustion subsystem

**Closes spec §18 (P5).** The evaluator already computes `exhaustion_risk` and assigns
`EXHAUSTION`; the work is exit-evidence validation and cooldown wiring.

### 2.1 — Exhaustion exit-evidence package

- **Fix:** define and test the exit-evidence package (borrow normalization + options gamma
  decay + CVD divergence + fuel depletion) against the labeled registry, mirroring the
  existing `fuel.py::estimate_exhaustion_risk` inputs.
- **Acceptance:** a replay assigns exhaustion with supporting evidence per case; the package
  is documented and tested, not anecdotal.

### 2.2 — Hysteresis cooldown specification

- **Fix:** specify cooldowns for `EXHAUSTION → POST_SQUEEZE` and the backward-transition
  rules (sustained evidence before retreat per `hysteresis.py`).
- **Acceptance:** cooldown behavior is unit-tested; the evaluator's transition note
  (currently a docstring warning) becomes enforced behavior with tests.

### 2.3 — Platform execution-simulation wiring

- **Fix:** confirm the platform execution simulation consumes the validated exhaustion
  signal (`remaining_fuel` / `exhaustion_risk` / participation caps already exist) and add
  the missing seam tests on the platform side.
- **Acceptance:** an integration test shows exhaustion caps participation; documented in the
  platform work log per its conventions.

---

## 3. Phase 6 — Live transition evidence

**Closes spec §19 limitation 4.** Frozen snapshots cannot prove live transitions.

### 3.1 — Persistent point-in-time state

- **Fix:** persistent `previous_state` feeding `fuel_history` and hysteresis — the piece
  frozen mode cannot provide (currently `FROZEN_SNAPSHOT_NO_LIVE_TRANSITIONS`).
- **Acceptance:** a replayable PIT stream demonstrates forward and backward transitions with
  hysteresis and per-transition evidence, not a frozen-snapshot state read.

### 3.2 — Live-wired deployment (coordinate with owner/platform)

- **Problem:** requires `CLOUD_PROVIDER_MODE` deployment and the donor bridge
  `squeeze_client.py` pointed at the deployed server instead of fixtures. Deployment
  credentials/infra are owner-side.
- **Fix:** document the exact deployment prerequisites and produce the transition-evidence
  replay once a live or replayable PIT stream exists.
- **Acceptance:** a transition-evidence replay artifact exists; otherwise this item stays
  open with the precise blocker listed (mirroring platform P0-1 checklist style).

---

## 4. Phase 7 — Capability and data expansion

**Closes spec §19 limitations 2–3 and §20 open questions.** Only items with a feasible
owner-side path are in-sprint; the rest stay registered gaps.

### 4.1 — Lending-data gap (G1)

- **Fix:** identify and verify a governed lending feed (IBKR borrow mechanism or commercial
  lending-data provider) with PIT semantics; admit the fields through the existing
  admissibility pipeline. The evaluator already flips the missing keys off when a governed
  snapshot supplies the fields.
- **Acceptance:** either the fields are admitted with real evidence (gap G1 closed in the
  matrix, closure artifact noted) or the search is documented as attempted with the blocker
  named. Probe registry updated to match.

### 4.2 — Cross-lane live evidence (G2/G3)

- **Fix:** depends on Order Flow and Options lanes publishing normalized CVD / dealer
  positioning — platform live-wiring work outside the child repo.
- **Acceptance:** when the lanes publish, the squeeze lane consumes through
  `cross_lane.py` only; a platform-side integration test proves provenance. If the lanes
  are not publishing, this item documents the dependency and stays open.

### 4.3 — Recall observability (G6)

- **Fix:** define the recall window and a labeling pipeline so missed events are
  observable. This is a research-track item (no new providers).
- **Acceptance:** a documented recall definition plus a mechanism for missed-event
  labeling; no claim of recall before it exists.

### 4.4 — Explicit de-scope record (G5, G7, G8)

- **Fix:** one doc section recording the deliberate de-scope of ShortPainDistribution (no
  entry-price inference method), FTD/threshold list (no source decision), and crypto
  liquidation mapping (post-Phase-4), each with its re-open condition.
- **Acceptance:** the gap register and roadmap Phase-7 table list these as explicitly
  de-scoped with re-open conditions, not as silently missing work.

---

## 5. Cross-cutting: docs that must stay truthful

- **5.1** After each phase closes, update `SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md`
  (state table + phase sections + track D) and `SHORT_SQUEEZE_CAPABILITY_GAP_ANALYSIS.md`
  (matrix + register) in the same change as the code, per the roadmap's update rule.
- **5.2** Every claim that ships carries the required interpretation language; nothing
  grants live signal promotion, threshold changes, or trading capability
  ([LIMITATIONS.md](../LIMITATIONS.md), ADR-0047, spec §17).
- **5.3** `tools/check_doc_links.py` stays green on every commit; new docs link only to
  real files with real heading slugs.

---

## Definition of done (the roadmap's §4 checklist)

1. Calibrated horizon probabilities exist (1, 3, 5, 10, 20d) from a walk-forward-validated
   model — or are honestly reported not-yet-calibrated with the blocker named.
2. Exhaustion is a validated subsystem with exit-evidence and hysteresis cooldowns.
3. Live transitions are demonstrable from a live or replayable PIT stream (or the exact
   deployment blocker is documented).
4. Capability gaps are closed or explicitly de-scoped with documented evidence.
5. Suite is green except buckets impossible by construction (CI history, live gateway,
   owner-only data).
6. Cross-lane provenance holds (Order Flow owns CVD, Options owns gamma; Squeeze consumes
   only normalized evidence through `cross_lane.py`).

---

## Suggested execution order

1. **Close-out:** 0.1 → 0.2 → 0.3 → 0.4 (land the branch, sync the snapshot, unblock the
   suite). Quick, mechanical, unblocks everything.
2. **Phase 4:** 1.1 preregistration → 1.2 harness → 1.3 baseline fit → 1.4 wiring → 1.5
   magnitude → 1.6 ADR/roadmap. Gate 1.7 on a clean landing.
3. **Phase 5:** 2.1 → 2.2 → 2.3.
4. **Phase 7 research items:** 4.1 (owner-feed search) and 4.3 can run in parallel with 2.x
   since they touch different modules; 4.2 tracks platform wiring; 4.4 is a short doc pass.
5. **Phase 6:** 3.1 (PIT state) first; 3.2 blocks on owner deployment and runs last.
6. **Close:** 5.1–5.3 doc sweep, full-suite run, child PRs, parent snapshot re-sync.

## Revision history

| Date | Change |
|---|---|
| 2026-09-06 | 1.2 closed: walk-forward scaffold committed (grouped folds, purge/embargo per O-2, regime slices, degeneracy gate, diagnostics); committed-cohort structure recorded honestly — 2 evaluation folds, 0 admissible training boundaries, 3 empty regimes |
| 2026-09-06 | Initial sprint plan; dataset decision recorded (34-label path, mechanism adjudication separately gated); fixture-gap root cause identified |
| 2026-09-05 | 0.3 closed: batch07 manifests extended to the 29-symbol `FROZEN_COHORT` (KLRS/SG/BATCH3F0x mirror rows), golden report regenerated, test asserts against the cohort constant — `test_operation_readiness.py` 37/37 green. 0.4 closed: full suite re-run; remaining failures are only the two environmental buckets (26 compatibility/CI-baseline, 6 live-IB-Gateway), 0 errors |
| 2026-09-05 | Registry accounting reconciled (O-5, part 1): authoritative counts measured from committed fixtures — 43-entry registry = 31 historical case boundaries / 29 unique symbols / 11 SYN / 1 KLOS; 35 outcome-observation files; 36 pipeline boundaries incl. batch 05; 35 evaluable labels; 1 AACP exclusion. See [COHORT_EXPANSION_PROGRESS.md](../calibration/COHORT_EXPANSION_PROGRESS.md) |
| 2026-09-05 | O-5 part 2: registry fixture regenerated to include batch-05 (48 entries = 36 historical boundaries / 34 symbols / 11 SYN / 1 AACP evaluation-only / 1 KLOS); Phase 3B/3C fixtures + analysis-test constants updated in the same change |
