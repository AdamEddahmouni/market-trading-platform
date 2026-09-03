# PLATFORMIZATION P6 — Shadow observation and forward-validation infrastructure (design spec)

**Status:** Infrastructure landed — fixture/replay validated only
**Spec date:** 2026-08-22
**Scope:** Platformization **P6** machinery: immutable shadow prediction records,
delayed outcome labeling, post-hoc join metrics, and deterministic shadow-run
lifecycle over admitted fixtures/replay data. **No production trading, no live
execution path, no network I/O.**
**Prerequisites:** P3 durable local state, P4 reconciliation patterns
(content-derived report ids, append-only recording), DECISION-RESEARCH-001
(decision cards / PIT gate — composed with, minimally).

---

## 0. Evidence terminology (READ THIS BEFORE QUOTING ANY NUMBER)

> **Fixture tests prove infrastructure only — they are NOT forward-validation
> evidence.**

Every number this package produces comes from fixtures, replay slices, or
synthetic sequences chosen by the author of the test/run. They demonstrate that
the *machinery* works: records are immutable, labels cannot leak, metrics are
computed correctly, runs reproduce byte-for-byte. They say **nothing** about
whether any strategy predicts real markets well. Specifically:

| Term | Meaning here |
|---|---|
| **Infrastructure proof** | A fixture test passes: immutability, causality, determinism, restart-safety hold. |
| **Shadow-run metric** | A statistic (hit rate, Brier, calibration) computed over recorded predictions and labels **on fixture/replay data**. Descriptive of that data window only. |
| **Forward-validation evidence** | Does **not exist** until a shadow run has recorded predictions *before* their outcomes were observable, over live-admitted PIT data, across an out-of-sample window no participant could retro-select, and the labeling chain is verified intact. |

Nothing in `src/market_platform_foundation/shadow/**` may be presented,
exported, or summarized as forward-validation evidence while its data sources
are fixtures/replay. Any consumer quoting these metrics MUST carry the
qualification "fixture/replay infrastructure validation — not forward-validation
evidence."

## 1. Definitions

- **Shadow run** — a recorded observational exercise: a manifest binds a
  `strategy_version`, `prediction_version`, universe, data-window references,
  and pre-declared walk-forward window boundaries (`train_window_end_ns`,
  `eval_window_start_ns`, `eval_window_end_ns`). A run observes and records;
  it never executes orders. There is no code path from `shadow/` to any
  execution surface.
- **Prediction record** — an immutable point-in-time assertion written
  **before** the outcome is observable: instrument, `decision_time_ns`,
  `horizon_ns`, `predicted_probability ∈ [0,1]`, derived
  `predicted_positive` (= `probability >= 0.5`), optional `regime_tag`
  (passthrough segmentation tag), an **opaque payload**, and a
  `pit_snapshot_ref` pointing at whatever point-in-time evidence the predictor
  consumed. Identity is content-addressed (§2).
- **Abstention** — a prediction may explicitly abstain (`abstained=True`) with a
  mandatory machine-readable `abstain_reason` and `probability=None`.
  Abstentions are first-class: they are counted, rate-tracked, and excluded
  from scored metrics (hit rate, Brier, calibration) — never coerced to a
  neutral guess.
- **Outcome label** — an immutable, delayed annotation joined to a prediction
  by `(run_id, prediction_id)`: `observed_positive`, optional
  `observed_return_bps`, `label_time_ns` (when the outcome resolved in the
  data), and `available_time_ns` (when the label became usable downstream).
  Labels are written strictly after the fact; they never mutate predictions.
- **Regime tag** — an uninterpreted string carried on predictions and used
  purely as a segmentation key in metrics. It is never merged into scores.

## 2. Immutability rules

1. **Write-before-outcome:** predictions are appended to the store before any
   label referencing them exists. The store is append-only: there is no UPDATE
   or DELETE statement anywhere in `shadow/store.py`.
2. **Content-addressed identity:** every record id is a SHA-256 content hash
   over its canonical JSON body (repo-wide `canonical_bytes` /
   `sha256_bytes` convention):
   - `prediction_id = "SHPRD-" + sha256(body)` where body covers run_id,
     instrument, decision_time_ns, horizon_ns, probability/direction,
     abstention fields, regime_tag, **payload**, **pit_snapshot_ref**, and
     `created_at_ns`.
   - `label_id = "SHLBL-" + sha256(body)` covering the join keys
     `(run_id, prediction_id)` plus the full label content.
   - `run_id = "SHRUN-" + sha256(manifest body)`;
     `report_id = "SHREP-" + sha256(report body)`.
3. **Tamper evidence:** each stored row carries its content hash alongside the
   JSON. `verify_prediction` / verification at labeling time recomputes the
   hash from the stored body; any divergence raises
   `ShadowIntegrityError("PREDICTION_HASH_MISMATCH")`. Retrospective mutation
   is therefore detected, not just prevented at the API layer.
4. **Insert-once:** appending a record whose id already exists is a no-op that
   returns the existing row (`inserted=False`). Identical content is
   idempotent; conflicting content under the same id is impossible by
   construction (the id is the content hash).
5. **No retrospective mutation of computed values:** all timestamps entering
   identities and computations (`created_at_ns`, `decision_time_ns`,
   `label_time_ns`, `available_time_ns`) are injected parameters. No wall
   clock participates in computed values, so identical inputs reproduce
   identical bytes end-to-end.

## 3. Delayed labeling rules

Labeling (`shadow/labeling.py`) fails closed. A label is refused unless:

1. **Causality:** `label_time_ns > decision_time_ns` (a violation raises
   `LABEL_TIME_NOT_AFTER_DECISION`).
2. **Leakage prevention:** `available_time_ns > decision_time_ns +
   horizon_ns` — the label becomes available **strictly after** the full
   decision horizon has elapsed (`LABEL_LEAKS_DECISION_WINDOW` otherwise).
   This makes it structurally impossible for a label to inform any decision
   made within its own prediction window.
3. **Resolution ordering:** `available_time_ns >= label_time_ns` — nothing is
   "available" before it resolved (`LABEL_AVAILABLE_BEFORE_RESOLVED`).
4. **Unmutated referent:** the referenced prediction is re-verified against its
   stored hash at labeling time; a mutated prediction refuses new labels
   (`PREDICTION_HASH_MISMATCH`).
5. **Join uniqueness:** one label per `(run_id, prediction_id)`; a second label
   for the same pair is an insert-once no-op returning the existing label.

## 4. Abstention accounting

- `abstention_rate = abstained_predictions / total_predictions` (per whole run
  and per regime segment).
- Scored metrics use only labeled, non-abstaining records as denominators;
  unlabeled records (horizon not yet elapsed) are tracked separately as
  `pending`. Nothing silently drops out of the denominator map — counts
  reconcile explicitly as `total = scored + pending + abstained`, where
  `scored` excludes abstentions entirely.

## 5. Calibration tracking and metric definitions

All metrics are **post-hoc joins**: computed only from appended predictions and
labels; nothing is estimated at write time.

- **Hit rate** — fraction of scored records where
  `predicted_positive == observed_positive`.
- **Brier score** — mean squared error `mean((p − y)²)` over scored records
  (`y ∈ {0,1}`), the standard probabilistic scoring rule.
- **Calibration buckets** — scored records sorted by predicted probability
  (ties by `prediction_id`, mirroring harness determinism) and split into
  `k` equal-count positional buckets (default `k = 10`); each bucket reports
  `n`, `mean_predicted_probability`, `observed_frequency`, and the gap.
  Positional bucketing keeps the computation deterministic without bin-edge
  conventions.
- **Per-regime segmentation** — every observed metric is additionally grouped
  by `regime_tag` (`"UNTAGGED"` when absent). Tags pass through untouched.
- **Walk-forward split evaluation** — windows come from the run manifest.
  Records are assigned by `decision_time_ns` to train (`< train_window_end_ns`)
  and eval (`>= eval_window_start_ns`) sides. The split refuses to construct
  when `eval_window_start_ns < train_window_end_ns`
  (`WalkForwardLeakageError`) — eval start **>=** train end is the minimum
  non-peeking contract; equality is permitted (boundary-exclusive train side).
  The train side reports coverage counts only; reported quality metrics come
  from the eval side.
- **Assumption overlays (strictly separated):** slippage/cost-model overlays
  are hypothetical what-if computations, never observations. They live in a
  disjoint output namespace `"overlay"` with their own `cost_model_version`,
  and never appear inside, blend into, or reweight the `"observed"` namespace.
  Consumers must never quote overlay numbers as outcomes.

## 6. Store schema (SQLite, append-only)

Follows the `local_state` patterns (WAL, busy timeout, fail-closed integrity
check, minimal versioned migration):

```sql
CREATE TABLE IF NOT EXISTS shadow_meta (
    key TEXT PRIMARY KEY, value TEXT NOT NULL);           -- schema_version
CREATE TABLE IF NOT EXISTS shadow_runs (
    run_id TEXT PRIMARY KEY,
    manifest_json TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    created_at_ns INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS shadow_predictions (
    prediction_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    decision_time_ns INTEGER NOT NULL,
    created_at_ns INTEGER NOT NULL,
    record_json TEXT NOT NULL,
    record_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS shadow_labels (
    label_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    prediction_id TEXT NOT NULL,
    label_json TEXT NOT NULL,
    label_hash TEXT NOT NULL,
    UNIQUE(run_id, prediction_id));
```

Restart-safe: reopening the store re-applies only `CREATE TABLE IF NOT EXISTS`
and integrity verification; runs continue appending. No UPDATE/DELETE exists.

## 7. Composition with DECISION-RESEARCH-001

Minimal, one-directional, lossless: `prediction_payload_from_decision_example`
passes a decision-research example dict **verbatim** into the opaque prediction
payload (`{"decision_research": <example>}`). No card registry, harness, or
example-builder types are imported; neither side's contracts change. Deep
coupling is deliberately deferred until a real predictor consumes cards.

## 8. Deliberate exclusions

- No execution path, order creation, or `operating_modes` change; shadow runs
  carry no execution authority concept at all (observation ≠ execution).
- No live/network I/O of any kind; fixture/replay inputs only.
- No model fitting, training loop, or strategy promotion — walk-forward
  "training" side is coverage bookkeeping only.
- No UI/API surfacing (a later sub-milestone may project read-only views).
- No `tests/shadow` entry in `tools/validation_manifest.json` (governed file);
  tests run directly via `unittest` until a principal adds the suite.
- Fixture metrics are never persisted as evidence artifacts; reports are
  in-memory/returned values with the §0 qualification embedded in the spec,
  not in runtime payloads (payloads stay pure data).
