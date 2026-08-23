# Platformization P6 - Shadow Run 1: prospective forward-validation kickoff (design spec)

**Status:** Design - not implemented; no run opened
**Date:** 2026-08-23
**Prerequisites:** P6 shadow infrastructure (`shadow/**`, landed 2026-08-22), live observational runtime (`market_data/live_runtime.py`, P2/P2.1), DECISION-RESEARCH-001 terminology
**Scope guard:** offline code paths only during development. Run operation uses the already-authorized observational Moomoo path (`IMP_LIVE_OBSERVATIONAL`). No execution-path contact of any kind. No network calls added by this increment.

---

## 1. Objectives (narrow, ordered)

1. **Primary objective:** prove the integrity and operability of IMP's live prospective
   forward-validation machinery: immutable preregistered manifests, decision opportunities
   derived solely from data admitted and available at decision time, durable recording of
   every opportunity outcome, delayed labeling without lookahead, and tamper-evident storage.
2. **Secondary objective:** obtain the first **descriptive** out-of-sample evidence for whether
   5-minute signed order-flow imbalance (NSS) contains information about BIYA's 30-minute
   forward direction.

Run 1 does **not** establish that NSS is a validated market predictor. See section 16.

## 2. Evidence terminology

Inherits P6 spec section 0 verbatim. Additionally:

- **Forward-validation evidence** exists only for the primary-integrity claim once Run 1
  completes with zero integrity violations. Predictive statistics are **descriptive
  forward-validation evidence**: valid as out-of-sample observation of one instrument,
  one regime, one date range, clustered observations - never trading-performance or
  execution evidence.
- The data source is **observational market data without execution authority**. That
  provenance is carried into the manifest and every report; shadow results never acquire
  authoritative-dataset or tradability semantics by having been collected prospectively.

## 3. Architecture

New modules (all stdlib-only):

| Module | Role |
|---|---|
| `shadow/predictor.py` | Pure function: `(trade window snapshot, config) -> prediction params \| model abstention`. No I/O, no clock. |
| `shadow/experiment.py` | `ShadowExperimentStore`: runs, decision-opportunity ledger, recorder-error log. Composes `ShadowStore` for predictions/labels. |
| `tools/research/run_shadow_run.py` | Operator CLI: `open` / `status` / `close` / `label-due` / `report`. |

Modified module:

- `market_data/live_runtime.py` gains a **minimal adapter attachment**: after successful
  admission, invoke the recorder if enabled. All shadow logic stays outside the runtime
  module. The attachment is inert unless `IMP_SHADOW_RECORDING=1`; recorder failures are
  caught, counted, and surfaced in `health_payload()`, never propagated into admission.

Unchanged governed subjects: `shadow/records.py`, `shadow/store.py`, `shadow/labeling.py`,
`shadow/metrics.py`, `shadow/runs.py` contracts are consumed as-is. Predictions and labels
are written through the existing `open_shadow_run` / `record_prediction` / `attach_label`
APIs. The experiment store adds the opportunity ledger around them.

## 4. Decision opportunities and cadence

Deterministic event-time buckets replace wall-clock throttling:

```text
bucket = floor(decision_event_time_ns / 60_000_000_000)   # 60-second buckets
```

- At most one decision opportunity per `(run_id, instrument_id, bucket)`.
- The opportunity triggers on the **first qualifying admitted trade** whose event time
  enters a bucket not yet decided for that symbol.
- Restart-safe and idempotent: `UNIQUE(run_id, instrument_id, decision_bucket)` in the
  ledger makes duplicate processing a no-op (`DUPLICATE_BUCKET` skip, recorded).
- Missed windows are visible: buckets with admitted trades but no ledger row are
  classified at report time as `UNRECONCILED_GAP` in the integrity section (a report-time
  classification, never a fabricated ledger row).

## 5. Input eligibility (availability-time discipline)

A trade enters the predictor window iff **both** hold:

```text
event_time            <= decision_time
available/receive_time <= decision_time
```

`decision_time` is the trade's own `event_time` (first qualifying trade of the bucket).
This reuses the admission pipeline's existing `live_received_time` discipline; no new
availability definition is invented. A trade that arrived late is excluded from windows
whose decision preceded its arrival, even if its exchange timestamp precedes the decision.

Aggressor classification per eligible trade, in priority order:

1. Prevailing admitted quote at or before the trade's event time (freshness <= 2 s):
   buy-initiated if `price >= mid`, sell if `price < mid`.
2. Tick-rule fallback versus previous eligible trade price.
3. Otherwise `unknown_side` (counted, excluded from signed volume).

Staleness: if the newest eligible trade is older than 60 s at decision time, or the
quote subscription is active but no quote has been admitted in the prior 30 s, the
opportunity resolves `ABSTAINED_MODEL(STALE_INPUT)`.

## 6. Predictor v1 (frozen before open)

Inputs: eligible trades over the trailing 5 minutes ending at `decision_time`.

```text
signed_volume = buy_volume - seller_volume          # unknown-side volume excluded
total_volume  = buy_volume + seller_volume
nss           = signed_volume / total_volume        # undefined if total_volume == 0
```

Direction and probability (preregistered transform - explicitly **not** a calibrated
probability model):

```text
direction = UP   if nss >= +0.15
          = DOWN if nss <= -0.15
          = ABSTAIN(FLAT_BAND) otherwise

p_up        = clip(0.5 + 0.5 * nss, 0.1, 0.9)       # P(30-min outcome is UP)
p_selected  = p_up if UP else (1 - p_up) if DOWN    # confidence in selected direction
```

`p_up` is the probabilistic prediction used for Brier/calibration against `Y_up`.
`raw_nss` is stored beside the mapped values and never overwritten by them.
Additional model abstention: `INSUFFICIENT_TRADES` (< 10 eligible trades in window).
Quality rejection (recorder-level): `SKIPPED_QUALITY` when the runtime marks the
admission stream degraded for the interval.

Model-level outputs are exactly: `PREDICTED`, `ABSTAINED_MODEL(FLAT_BAND |
INSUFFICIENT_TRADES | STALE_INPUT)`. Recorder/system-level outcomes are exactly:
`SKIPPED_QUALITY`, `SKIPPED_SYSTEM`, `DUPLICATE_BUCKET`, `NO_OPEN_RUN`,
`RECORDING_DISABLED`, `OUTSIDE_RUN_WINDOW`. Model abstentions and system skips are never
merged; coverage reporting depends on the distinction.

## 7. Target variable (frozen before open)

```text
T0          = decision_time
target      = T0 + 30 min (horizon)
P0          = last eligible admitted trade price at or before T0
              (persisted at prediction time with its event_time and capture record id)
P30         = first eligible admitted trade price with
              target <= event_time <= target + 5 min tolerance
r30         = P30 / P0 - 1
Y_up        = 1 if r30 > 0;  0 if r30 < 0
```

Labelability policy (no silent substitution, ever):

| Outcome code | Condition |
|---|---|
| `LABELED_UP` / `LABELED_DOWN` | P30 found within tolerance, `r30 != 0` |
| `ZERO_RETURN` | P30 found within tolerance, `r30 == 0` (excluded from scored sets, counted) |
| `UNLABELABLE_NO_REFERENCE_PRICE` | no eligible trade existed at/before T0 |
| `UNLABELABLE_NO_HORIZON_TRADE` | no eligible trade within `[target, target + 5 min]` |
| `UNLABELABLE_CAPTURE_GAP` | capture manifest shows a coverage gap spanning the lookup |
| `UNLABELABLE_PROVIDER_GAP` | runtime reports disconnect/degraded spanning the lookup |

The maximum horizon tolerance is 5 minutes. A trade 45 minutes late is never used.

## 8. Run manifest (the scientific contract)

`open` fails unless: git worktree is clean, HEAD SHA is resolvable, and the named
instrument/provider checks pass. Bound at open, immutable thereafter (insert-once;
`open` on an existing `run_id` never rewrites - it verifies and returns the stored row):

```text
run_id, created_at_ns, state
git_commit_sha, repository_clean (=true)
predictor_version, labeler_version, manifest_schema_version
provider_identity ("moomoo-observational"), instrument_id, venue_note
window_seconds (300), minimum_trades (10),
band_upper (+0.15), band_lower (-0.15),
probability_transform ("p_up=clip(0.5+0.5*nss,0.1,0.9)"),
bucket_seconds (60)
horizon_seconds (1800), horizon_tolerance_seconds (300),
P0_rule, P30_rule, zero_return_policy
stale_input_seconds (60), quote_staleness_seconds (30),
session_hours_rule ("US equities regular session, America/New_York"),
halt_policy ("no opportunities during halted/non-regular states"),
eligibility_rule (section 5 verbatim)
primary_grid_rule (non-overlapping 30-minute grid anchored at session open),
stopping_rule (section 13),
evaluation_window_start_ns, evaluation_window_end_ns (optional; else stopping rule governs)
primary_metrics, secondary_metrics, baseline_definitions (section 12)
manifest_content_hash
```

Binding into the governed `ShadowRunManifest` (required integer window fields):
`train_window_end_ns = evaluation_window_start_ns` (train side empty - coverage
bookkeeping only, per the P6 metrics contract) and
`evaluation_window_end_ns` = the preregistered 8-session upper bound, both knowable at
open. Run 1's report does **not** use the walk-forward machinery; it composes sections
via `join_pairs` / `observed_metrics` / calibration directly, with the primary-grid
subset computed from decision buckets.

Any predictor, labeling, configuration, or threshold change after `open` requires a new
run id. There is no mutation path.

Lifecycle: `CREATED -> OPEN -> CLOSED -> LABELING -> FULLY_LABELED -> REPORTED`
(`close` is explicit via CLI or automatic at the frozen boundary; `report` may run
provisionally before `FULLY_LABELED` and must then say so).

## 9. Opportunity ledger (every eligible outcome durably recorded)

Each eligible `(run_id, instrument_id, bucket)` resolves to exactly one row:

```text
outcome: PREDICTED | ABSTAINED_MODEL(reason) | SKIPPED_QUALITY | SKIPPED_SYSTEM(code)
         | DUPLICATE_BUCKET | NO_OPEN_RUN | RECORDING_DISABLED | OUTSIDE_RUN_WINDOW
decision_time, window_start, window_end,
eligible_trade_count, buyer_count, seller_count, unknown_count,
buyer_volume, seller_volume, total_volume, raw_nss,
direction, p_up, p_selected,
reference_price (P0), reference_price_time, reference_capture_record_id,
quality_state, classification_provenance,
capture_id, provider_identity, predictor_version, manifest_hash, git_sha, created_at_ns
```

Principle: the future report never reruns today's predictor to learn what today's
predictor saw. When `PREDICTED`, the same content also lands in `ShadowStore` via
`record_prediction` (payload embeds the ledger snapshot under
`{"shadow_run1": {...}}` plus the DECISION-RESEARCH passthrough key retained for
composition compatibility).

`ShadowExperimentStore` tables (WAL, busy timeout, fail-closed integrity check,
append-only inserts only - no UPDATE/DELETE anywhere):

```sql
runs(run_id PRIMARY KEY, manifest_json, manifest_hash, state, created_at_ns, closed_at_ns)
decisions(id PRIMARY KEY, run_id, instrument_id, decision_bucket, outcome,
          prediction_id NULL REFERENCES ShadowStore predictions, detail_json,
          record_hash, created_at_ns,
          UNIQUE(run_id, instrument_id, decision_bucket))
recorder_errors(id PRIMARY KEY, run_id, occurred_at_ns, error_code, detail_json)
```

`prediction_id` is set exactly when `outcome = 'PREDICTED'` and joins to the
`ShadowStore` prediction; labels remain in `ShadowStore` (insert-once per
`(run_id, prediction_id)`) and join through it.

## 10. Failure isolation and degradation surfacing

Recorder exceptions never break admission. Beyond counting, the runtime health payload
exposes: `shadow_recording_enabled`, `shadow_run_id`, `shadow_run_state`,
`shadow_last_success_ns`, `shadow_last_error_code`, `shadow_error_count`,
`shadow_consecutive_errors`, `shadow_predictions_written`,
`shadow_abstentions_written`. `report` lists degraded periods (consecutive-error spans,
capture gaps) prominently in the integrity section; a run with unexplained degraded
spans cannot claim full integrity in its report header.

## 11. Labeling

`label-due` scans `CLOSED` (or later) runs for matured horizons: for each `PREDICTED`
decision lacking a label, compute section-7 rules from persisted admitted capture JSONL
(`ObservationalRecorder` output referenced by `capture_id`), attach via existing
`attach_label` with `label_source="LIVE_ADMITTED_CAPTURE"`, and write the outcome code
back as a **new immutable decision-detail annotation** (never an update of the original
row). Unlabelable outcomes are recorded as annotations, not labels.

## 12. Reporting - three separated sections

`report` emits one canonical JSON document with three namespaces:

**A. Experimental integrity:** manifest valid/hash matched, `git_commit_sha`, clean-tree
flag, causality violations (must be 0), duplicate decisions (0), label violations (0),
recorder error count, degraded spans, capture gaps.

**B. Operational behavior:** eligible opportunities, predictions, model abstentions by
reason, quality skips, system skips, coverage ratio, labelability rate by outcome code.

**C. Predictive results (descriptive):** Brier score and directional accuracy against
preregistered baselines - uniform-null `p_up = 0.5` (Brier 0.25), direction prevalence
baseline computed from the same labeled set, mean forward return by forecast class,
raw-NSS-vs-outcome relationship (secondary/exploratory). Calibration curves use the
**full observational set**; the **primary inferential set** is the preregistered
non-overlapping grid (one observation per 30 minutes, anchored at session open) because
60-second cadence with 30-minute horizons yields ~30 overlapping, highly correlated
horizons. Naive independent-sample inference on the dense set is prohibited. Headline
Brier/accuracy numbers come from the primary grid; dense-set statistics are labeled
descriptive.

Every report carries: the section-2 terminology block, the observational-source/no-
execution-authority provenance statement, and - unless state is `FULLY_LABELED` - an
explicit provisional-results banner.

## 13. Stopping rule (frozen before open)

Run 1 closes at whichever comes first:

- **5 complete regular US trading sessions** with the recorder enabled, or
- **65 primary-grid observations**, i.e. 65 labeled non-overlapping grid decisions, or
- an absolute maximum of **8 elapsed regular sessions** (guards halts/holidays).

No extension is permitted based on observed results (optional-stopping bias). The rule
is bound in the manifest at open.

## 14. Kickoff sequence (order is mandatory)

1. OpenD started; observational runtime health confirmed with `IMP_SHADOW_RECORDING`
   **off**.
2. Final authoritative validation run green (`validate.py full`).
3. Git worktree verified clean; HEAD SHA recorded.
4. `run_shadow_run.py open --instrument BIYA ...` - manifest created and verified.
5. Runtime restarted with `IMP_LIVE_OBSERVATIONAL=1 IMP_SHADOW_RECORDING=1`.
6. First decision opportunity observed in `status`.
7. Run proceeds to the frozen boundary; `close`; `label-due` until matured; `report`.

The experiment exists before the first forecast.

## 15. Claim boundaries and follow-on sequence

Run 1 proves pipeline integrity and operability; its NSS statistics are single-instrument
descriptive evidence. Planned sequence, each a separate preregistered run:

```text
Run 1: prospective pipeline/integrity proof (this design)
Run 2: frozen identical predictor, longer BIYA temporal replication
Run 3: frozen predictor, preregistered multi-symbol validation
Run 4+: alternative hypotheses/models (incl. decision-research card predictors)
```

No post-run threshold adjustment (e.g., moving +-0.15) may be combined with Run 1
observations; a changed constant is a new run.

## 16. Testing and validation

unittest suites under `tests/shadow/`: predictor purity, band/mapping edges (nss exactly
+-0.15, clip bounds, zero volume), all abstain/skip taxonomy separation, availability-time
eligibility (late-arrival exclusion), bucket determinism/idempotence across restarts,
ledger uniqueness enforcement, runtime inertness when disabled, recorder-failure isolation
and health fields, labeler tolerance/zero/unlabelable policies, causality interplay with
`attach_label`, CLI smoke (open/status/close/label-due/report), manifest immutability
(open-twice verification), stopping-rule boundary logic. Validation ladder per AGENTS.md:
`validate.py changed` after edits, `full` at the pre-open checkpoint (step 14.2). No
`validation_manifest.json` edit.

## 17. Deliberate exclusions

No execution authority concept, order path, or operating-modes change; no UI surfacing
(later sub-milestone); no card-based predictor (deferred per P6 spec section 7); no new
network I/O; no validation-manifest edit; no multi-symbol universe in Run 1; no
inferential significance testing on the dense observation set.
