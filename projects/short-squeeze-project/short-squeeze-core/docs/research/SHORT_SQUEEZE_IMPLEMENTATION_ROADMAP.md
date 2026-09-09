# Short Squeeze Implementation Roadmap

**Status:** Living implementation plan for the causal Short Squeeze lane redesign
**Spec:** [SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md](SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md) (`squeeze_causal_research_spec.v1`)
**Product version:** 0.16.0
**Last updated:** 2026-09-05

## 1. Purpose

This roadmap sequences the work required to move the Short Squeeze lane from its
current research-screener state to a validated causal implementation. It is the
implementation companion to the causal research spec: the spec defines *what* the
causal model is (mechanisms, state machine, evidence and calibration requirements);
this document defines *what has been built*, *what remains*, and *in what order*.

Reading rules:

- The [spec](SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md) is authoritative where the two
  conflict.
- Every completed item cites its artifact (doc, ADR, module, or test).
- Nothing in this roadmap authorizes live signal promotion, threshold changes, or
  trading capability. The product remains a read-only research screener
  ([LIMITATIONS.md](../LIMITATIONS.md)).

## 2. Current state (2026-09-05)

| Area | State |
|---|---|
| Product | Short Squeeze Research Screener **v0.16.0**, read-only research application (no orders, no recommendations, no predictive-validation claims) |
| Causal evaluator | `squeeze_core/intelligence/evaluator.py`, model `squeeze_causal_baseline.v4` — evidence-gated state machine with fail-closed `UNEVALUABLE`, mechanism labels, separated model/data/overall confidence, and `RESEARCH_ONLY` horizon slots |
| Causal intelligence layer | `intelligence/` modules: `evaluator.py`, `hysteresis.py`, `fuel.py`, `cross_lane.py`, `explanation.py`, `contracts.py` |
| Historical cohort | 29 IBKR frozen-boundary symbols; **48-entry registry** (36 historical case boundaries incl. batch 05 / 34 symbols / 11 SYN / 1 AACP evaluation-only / 1 KLOS blocked); 35 evaluable Stage 2 outcome labels; 1 permanent outcome exclusion (AACP) — reconciled accounting in [COHORT_EXPANSION_PROGRESS.md](../calibration/COHORT_EXPANSION_PROGRESS.md) |
| Calibration | Phase 3D n=30 policy threshold met (2026-08-17); ADRs 0067–0070 retain all production policies unchanged |
| Platform integration | `squeeze` is a first-class lane (workspace route, Demo/Paper/Live modes, donor bridge `squeeze_client.py`, execution simulation consuming `remaining_fuel` / `exhaustion_risk` / participation caps) |

## 3. Completed phases

| Phase | Deliverable | Artifacts |
|---|---|---|
| Phase 1 | Evidence contracts, point-in-time normalization, provider-adapter boundaries, and fixture foundations | ADRs 0001–0047; `tests/phase_1c..1i_fixture_builders.py` |
| Phase 2 | Provider/methodology comparison surfaces | Phase 2V comparison manifest (discovery source, exhausted) |
| Phase 3A | Transparent candidate evaluation — 25-rule outcome vector, no composite score | `phase_3a_transparent_candidate_policy.v1`; ADR-0048 |
| Phase 3B | Research detection and outcome labeling (TP/FP/TN/FN/UNEVALUABLE registry classification) | `phase_3b_research_detection_policy.v1`, `phase_3b_outcome_label_policy.v1`; ADRs 0049–0052 |
| Phase 3C | Descriptive analysis — Wilson intervals, sample-size bands, confusion descriptions | `phase_3c_descriptive_statistics_policy.v1`; ADRs 0053–0058 |
| Phase 3D | Acquisition pipeline, preregistered batches, leakage audits, counterfactual calibration layer | `squeeze_core.acquisition`; ADRs 0059–0065 |
| Phase 3E | Systematic historical evidence construction for 13 IBKR pilot symbols; Stage 2 forward-outcome acquisition | [phase-3e-design.md](../phase-3e-design.md), [phase-3e-stage2-acquisition-plan.md](../phase-3e-stage2-acquisition-plan.md); ADR-0066 |
| Phase 3F | Cohort expansion to 29 symbols / 48-entry registry; n=30 threshold met; calibration findings | [phase-3f-*.md](../phase-3f-external-discovery-preregistration.md); [COHORT_EXPANSION_PROGRESS.md](../calibration/COHORT_EXPANSION_PROGRESS.md); ADRs 0067–0070 |
| Causal intelligence (with 3E/3F) | State machine, hysteresis, fuel/exhaustion estimation, cross-lane evidence consumption, explanation graph | `tests/intelligence/test_causal_evaluator.py`, `tests/intelligence/test_hysteresis.py`; IMP `test_causal_squeeze_projection.py` |

## 4. Definition of done

The lane counts as "finished" when all of the following hold:

1. **Calibrated horizon probabilities exist** — P(squeeze within 1/3/5/10/20 trading
   days) emitted from a walk-forward-validated model (Phase 4). The evaluator's
   `RESEARCH_ONLY` slots become `CALIBRATED`.
2. **Exhaustion is a validated subsystem** with exit-logic evidence and hysteresis
   cooldowns (Phase 5, spec §18 P5).
3. **Live transitions are demonstrable** from a live-wired deployment, not only from
   frozen snapshots (Phase 6).
4. **Capability gaps are closed or explicitly de-scoped** with documented evidence
   (Phase 7).
5. **Test suite is green** everywhere except buckets that are impossible by
   construction on a given machine (CI history, live gateway, owner-only data) —
   see track D.
6. **Cross-lane provenance holds**: Order Flow owns CVD/aggressor, Options owns
   gamma/dealer positioning, Squeeze consumes normalized evidence only
   (spec §14).

## 5. Phase 4 — Walk-forward horizon probability calibration (next)

**Closes spec §19 limitation 1.** The evaluator already defines the calibrated
output contract — `HorizonModelSnapshot` (`status=CALIBRATED`, `pit_verified=True`,
`hazard_by_horizon`, optional `magnitude`) in
`squeeze_core/intelligence/contracts.py` — and `evaluate_squeeze_intelligence`
already consumes it via `_horizon_probabilities_from_model`. What does not exist yet
is the walk-forward harness that produces a validated snapshot. The 48-entry labeled
registry (36 historical case boundaries + synthetic controls) is the dataset this phase
unlocks.

**Prerequisites (gate):**

- **Preregistration (item 1.1):** [phase-4-calibration-preregistration.md](../phase-4-calibration-preregistration.md)
  fixes dataset, outcome, model sequence, regime slices, purge/embargo, metrics,
  non-dominance, and success/failure thresholds before any fitting. Open items
  O-1..O-6 must be locked before fits start.
- Mechanism-class label adjudication for the registry (spec §21: "separate label
  adjudication for mechanism class") — outcome labels alone (`±25%/24h`) are a
  detection predicate, not a mechanism label (spec §8).
- A fixture-freeze decision for the batch08/09 cohort-constant assertions (the
  canonical 13-case Batch 01 freeze; see track D) so calibration work starts from a
  stable registry.
- Detection-evaluability expansion or explicit acceptance of the small evaluable
  subset (ADR-0067: 28 of 30 boundaries were detection-unevaluable under baseline
  due to Batch 07 price-level blocking; see track B).

**Steps:**

1. Build the chronological walk-forward harness with purging/embargo; treat repeated
   symbol boundaries as dependent observations (ADR-0054) and slice regimes
   (pre-2020, meme regime, high-rate) per spec §12.
2. Fit the interpretable logistic / hazard baseline first (spec §10 sequence); only
   if data justifies it, proceed to calibrated gradient-boosted trees. Temporal
   models require explicit justification.
3. Produce `HorizonModelSnapshot` entries with `pit_verified=True` and
   `hazard_by_horizon` populated for (1, 3, 5, 10, 20).
4. Calibrate occurrence *and* magnitude separately (spec §11); wire the magnitude
   estimate into `MagnitudeEstimateSnapshot`.
5. Extend `tools/run_calibration_suite.py` (the existing harness used at n=30/n=35)
   rather than forking it; update ADRs only if findings change materially.
6. Report Brier, PR-AUC, precision@K, calibration curves, log loss, and expected
   trading value under explicit costs (spec §13, §17).

**Acceptance / gates:**

- `pit_verified` plus calibration diagnostics pass; the evaluator's horizon slots
  flip to `CALIBRATED` with model-version provenance.
- Results publish only with the required interpretation language — no predictive
  validation claim, no threshold optimization, GameStop must not dominate weights.
- No promotion to live signal status: calibration is a research result, not a
  decision (spec §17: signal ≠ decision ≠ execution).

**Non-goals:** changing Phase 3A/B/C policies or thresholds; emitting probabilities
without walk-forward validation; backtesting or P&L claims.

## 6. Phase 5 — Exhaustion subsystem

**Closes spec §18 (P5).** The evaluator already computes `exhaustion_risk` and
assigns the `EXHAUSTION` state; `fuel.py::estimate_exhaustion_risk` consumes CVD
divergence, borrow normalization, options gamma decay, and flow reversal. The
subsystem work is validation and exit wiring:

- Define the exit-evidence package (borrow normalization + options gamma decay +
  CVD divergence + fuel depletion) and test it against the labeled registry.
- Specify hysteresis cooldowns for `EXHAUSTION → POST_SQUEEZE` (backward
  transitions require sustained evidence per `hysteresis.py` and the evaluator's
  transition notes).
- Wire the validated exhaustion signal into the platform execution simulation
  (participation caps already consume `remaining_fuel` / `exhaustion_risk`).

**Acceptance:** a replay of the registry shows exhaustion assignments with
supporting evidence and cooldown behavior; exit logic is documented and tested, not
anecdotal.

## 7. Phase 6 — Live transition evidence

**Closes spec §19 limitation 4.** Frozen snapshots cannot prove live transitions.
Moving `BASELINE → … → ACTIVE_SQUEEZE → EXHAUSTION → POST_SQUEEZE` with backward
transitions requires:

- Persistent point-in-time state (`previous_state` feeding `fuel_history` and
  hysteresis), which frozen mode cannot provide.
- A live-wired deployment: the screener running in `CLOUD_PROVIDER_MODE`, the donor
  bridge `squeeze_client.py` pointed at the deployed server instead of degrading to
  fixtures.
- Per-lane doctrine verification on the platform side (no composite score, no
  fabricated synthesis; see platform P2-5) and the lane/module/family mapping
  (platform P1-4) so `squeeze` lane evidence keeps provenance.

**Acceptance:** a transition-evidence replay from a live or replayable PIT stream
demonstrates forward and backward transitions with hysteresis and per-transition
evidence — not a frozen-snapshot state read.

## 8. Phase 7 — Capability and data expansion

**Closes spec §19 limitations 2–3 and spec §20 open questions.**

| Gap | Work | Spec ref |
|---|---|---|
| Utilization / shares-on-loan velocity in baseline | Data-capability phase: the evaluator already removes `borrow_utilization_velocity` / `shares_on_loan_delta` from `missing_capabilities` when a governed lending snapshot supplies them — acquire and admit those fields per the provider capability matrix ([SHORT_SQUEEZE_CAPABILITY_GAP_ANALYSIS.md](SHORT_SQUEEZE_CAPABILITY_GAP_ANALYSIS.md), gap G1) | §19.2 |
| ShortPainDistribution | Entry-price distribution inference track — needs an entry-price inference method plus adjudication before it can be a baseline input | §19.3, §20 |
| Recall observability | Define the recall window and a labeling/adjudication pipeline so missed events are observable, not just hits | §20 |
| Cross-exchange crypto liquidation mapping | New market surface; explicitly out of scope until the US-equity baseline is calibrated (Phase 4 complete) | §20 |

Each item ships with honest missingness (`UNKNOWN`, never fabricated) per
[LIMITATIONS.md](../LIMITATIONS.md) and ADR-0047.

## 9. Cross-cutting tracks

**A. Cohort growth.** In-repo US-equity discovery is exhausted. Further growth uses
the preregistered external lanes ([phase-3f-external-discovery-preregistration.md](../phase-3f-external-discovery-preregistration.md)):
live IBKR broad-mover scan, fresh Finviz Elite export, or a third-party case list —
each batch preregistered before acquisition (ADR-0063). Cohort counting and
detection-evaluability are separate tracks.

**B. Detection-evaluability.** Batch 07 `PRICE_RANGE` blocking keeps most
artifact-discovery symbols detection-unevaluable under baseline policy (ADR-0067)
regardless of cohort size. Resolving bar/price semantics (ADR-0066 style) is the
binding constraint on expanding evaluable positives for Phase 4 — it is not solved
by adding more symbols.

**C. Platform live-wiring.** Deploy the screener and point `squeeze_client.py` at it
in `CLOUD_PROVIDER_MODE` so the lane's live surfaces consume real evidence rather
than fixtures; keep cross-lane evidence flowing only through
`squeeze_core/intelligence/cross_lane.py` (spec §14 ownership rules).

**D. Test and CI health.** The full suite is green except two environmental
buckets: 26 `tests/compatibility/*` tests need the full git baseline history (pass
on CI, exit 128 in shallow clones); 6
`tests/tools/ibkr_historical_export/test_collector.py` tests need a live IB
Gateway. The Batch 07 operation-readiness tests (previously blocked) and the
batch08/09 cohort-constant assertions were aligned to the committed 29-symbol
synthetic mirror (`FROZEN_COHORT`), so they no longer depend on the data owner
regenerating `batch07/synthetic-batch05/raw` (Batch 07 reads manifests only, never
raw OHLCV). None of these block research conclusions; all block "green
everywhere".

## 10. Validation and calibration discipline

Applies to every phase above:

- Chronological walk-forward with purging/embargo; repeated symbol boundaries are
  not independent observations (ADR-0054).
- Occurrence and magnitude calibrated separately; report Brier, PR-AUC,
  precision@K — not raw accuracy (spec §11, §13).
- Regime slices required (pre-2020, meme regime, high-rate); GameStop must not
  dominate weights (spec §12).
- Counterfactual and calibration results remain
  `COUNTERFACTUAL_EXPLORATION_ONLY` / `SMALL_SAMPLE_WARNING` until sample size and
  forward evidence justify otherwise (ADR-0067); no variant is auto-promoted to
  production policy.
- `model_confidence` stays distinct from `data_confidence` (spec §16); stale or
  missing evidence lowers data confidence even when model structure is sound.

## Revision history

| Date | Change |
|---|---|
| 2026-09-05 | Initial roadmap; closes the link from [SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md](SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md) §23 |
| 2026-09-05 | Track D updated: Batch 07 operation-readiness and batch08/09 buckets closed by the 29-symbol synthetic-mirror alignment; remaining buckets are CI-baseline history and live IB Gateway |