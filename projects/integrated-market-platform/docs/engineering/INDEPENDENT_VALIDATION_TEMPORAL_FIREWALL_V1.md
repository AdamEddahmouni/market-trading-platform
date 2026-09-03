# Independent Validation, Locked Holdouts & Temporal Knowledge Firewall (BUILD 19)

> BUILD 19 is the independent scientific firewall between development candidates and promotion consideration. It validates frozen candidate artifacts on temporally isolated evidence under pre-registered metrics, purge/embargo rules, locked-holdout commitments, contamination tracking, and explicit model-knowledge controls.

## Build boundaries

| Build | Authority |
| --- | --- |
| BUILD 17 | Experiment specification |
| BUILD 18 | Candidate generation |
| BUILD 19 | Independent validation |
| BUILD 20 | Promotion decision |

`MEETS_PRE_REGISTERED_CRITERIA` ≠ `PROMOTED`.

## Core artifacts

- `ValidationPlanV1` — pre-registered validation design (`VALPLAN-{sha256}`)
- `HoldoutCommitmentV1` — frozen candidate/metric/holdout binding before outcome access (`HOLD-{sha256}`)
- `HoldoutUnlockReceiptV1` — immutable authorization to read holdout outcomes
- `ContaminationRecordV1` — append-only contamination ledger
- `TemporalKnowledgePolicyV1` / `KnowledgeProfileV1` — model knowledge provenance
- `ValidationReportV1` — immutable validation evidence (`VALRPT-{sha256}`)

## Walk-forward

Supports `EXPANDING` and `ROLLING` modes via explicit fold boundary timestamps. Fold-specific candidates must be supplied by BUILD 18; BUILD 19 returns `MISSING_FOLD_CANDIDATE` when absent. **BUILD 19 does not retrain.**

## Purge

Training example label/information must satisfy:

```text
label_available_time_ns < validation_start_ns - purge_ns
```

Equality is excluded (conservative). Purge violations invalidate the fold candidate; leaked rows cannot be repaired post-training.

## Embargo

Embargo excludes the post-validation interval from subsequent fold training eligibility. `embargo_ns = 0` is supported when pre-registered.

## Locked holdout

1. Freeze validation plan, candidate set, artifact hashes, control, metrics, guardrails, statistical policy, and knowledge policy.
2. Create `HoldoutCommitmentV1`.
3. Unlock holdout via `ValidationDataAccessGuard`.
4. Access outcomes only through the guard in the canonical path.

### Physical vs logical isolation

The canonical validation path enforces holdout locking and records contamination. If the underlying repository exposes outcomes through unrelated low-level interfaces, the framework cannot retroactively guarantee a human never manually inspected them. Such exposure must be recorded as contamination.

## Contamination ledger

Detects:

- development knowledge overlap (`ResearchKnowledgeFootprint`)
- training dataset overlap
- prior holdout access
- unknown provenance (fail closed)

Records are append-only with no TTL.

## Temporal Knowledge Firewall

Historical LLM validation requires declared bounded knowledge:

```text
knowledge_cutoff <= decision_time
```

- Unknown/unbounded cutoffs fail closed (`BLOCKED_UNKNOWN_KNOWLEDGE_CUTOFF`).
- **Instructing a model to "pretend it is an earlier date" is not a Temporal Knowledge Firewall.**
- Retrieved sources must satisfy `available_time_ns <= decision_time_ns` (BUILD 02 PIT semantics).
- Tool classes: `PIT_SAFE`, `CURRENT_ONLY`, `UNSAFE_UNBOUNDED`. Historical validation allows only `PIT_SAFE`.
- Default network policy: `DENIED`.
- Teacher/distillation knowledge propagates to student provenance.

Statistical BUILD 18 candidates: `NOT_APPLICABLE`.

## BUILD 16 metric reuse

Validation uses `compute_brier_contribution`, `compute_log_loss_contribution`, and matched-control semantics from BUILD 16. No duplicate metric implementations.

## Statistical validation

Deterministic moving-block bootstrap over paired candidate-minus-control losses:

- `block_length`, `replicate_count`, `seed`, `confidence_level` frozen in `StatisticalPlan`
- Pre-registered criterion example: upper CI bound for Brier delta `< 0`
- Below `minimum_paired_sample`: `INCONCLUSIVE_INSUFFICIENT_SAMPLE`

No multi-comparison correction in v1; candidate family size is disclosed.

## Validation dispositions

- `MEETS_PRE_REGISTERED_CRITERIA`
- `DOES_NOT_MEET_PRE_REGISTERED_CRITERIA`
- `INCONCLUSIVE` / `INCONCLUSIVE_INSUFFICIENT_SAMPLE`
- `INVALID_CONTAMINATED`
- `INVALID_TEMPORAL_LEAKAGE`
- `INVALID_KNOWLEDGE_FIREWALL`
- `INVALID_PLAN_DEVIATION`

## BUILD 20 handoff

BUILD 20 receives `ValidationReportV1` with candidate artifact hashes, walk-forward fold results, locked holdout metrics, paired deltas, bootstrap CI, guardrails, contamination status, and knowledge-firewall status.

BUILD 20 must refuse: contaminated validation, knowledge-firewall-invalid historical claims, insufficient sample, missing guardrails, artifact hash mismatch, plan deviation.

## Module layout

```text
intelligence/validation/
  types.py, identity.py, planning.py, folds.py, purge.py, embargo.py
  holdout.py, contamination.py, artifacts.py, inference.py, metrics.py
  statistics.py, engine.py, serialization.py
  temporal_knowledge/{policy,firewall}.py
```

Persistence collections: `validation_plans`, `holdout_commitments`, `holdout_unlock_receipts`, `contamination_records`, `validation_reports`.
