# EVIDENCE-01 — Longer Forward Qualification

> Operational-evidence maturation milestone extending BUILD 26 forward shadow qualification without changing BUILD 35 acceptance semantics.

## Objective

Determine mechanically whether stored forward observations satisfy explicit evidence-sufficiency requirements sufficient to close, reduce, or precisely bound the outstanding `INSUFFICIENT_FORWARD_EVIDENCE` limitation from BUILD 26.

EVIDENCE-01 evaluates **evidence sufficiency only**. It does not evaluate model performance and does not grant execution authority.

## Historical BUILD 26 limitation

At BUILD 26 cutoff, disposition was:

```text
INSUFFICIENT_FORWARD_EVIDENCE
```

Canonical artifact: `artifacts/forward-qualification/BUILD26_QUALIFICATION_REPORT.json`

BUILD 26 concluded insufficiency because no live forward observation cohort met the frozen `ForwardQualificationSpecV1` minimum sample (`minimum_prediction_count=10`, `minimum_labelable_count=5`) outside fixture validation. The BUILD 26 runner intentionally returns `INSUFFICIENT_FORWARD_EVIDENCE` once integrity fixtures pass.

Historical BUILD 26 artifacts are immutable. EVIDENCE-01 produces new assessments at new cutoffs.

## Policy

Implementation: `src/market_platform_foundation/intelligence/forward_qualification/evidence01/`

Canonical policy artifact: `artifacts/forward-qualification/EVIDENCE01_POLICY.json`

### Threshold rationale

| Requirement | EVIDENCE-01 value | Rationale |
| --- | --- | --- |
| Minimum eligible predictions | 50 | 5× BUILD 26 `minimum_prediction_count` (10) |
| Minimum settled predictions | 25 | 5× BUILD 26 `minimum_labelable_count` (5) |
| Minimum settlement rate | 0.80 | Conservative operational floor |
| Minimum qualifying duration | 5 calendar days | Extends BUILD 26 1-hour floor for longer observation |
| Minimum distinct trading days | 5 | P6 shadow-run session precedent (`complete_sessions >= 5`) |
| Minimum distinct sessions | 5 | Same P6 precedent; prevents burst concentration |
| Minimum class support (UP/DOWN) | 3 each | Typed limitation when asymmetric; not fabricated balance |
| Maximum admissible gap | 24 hours | Continuity guard for provider/runtime fragments |
| Required quality states | `GOOD`, `DEGRADED` | Inherited from BUILD 26 spec |
| Outcome horizon maturity | `target_time_ns <= settlement_cutoff_ns` | BUILD 15 settlement semantics |

## Deterministic evidence semantics

- Assessment identity: `FEASM-<sha256>`
- Policy identity: `FEPOL-<sha256>`
- Report identity: `FEREP-<sha256>`
- Source fingerprint binds receipt IDs + cutoffs
- `generated_at` is non-identity metadata only
- Late observations after a fixed cutoff do not mutate prior assessment identity

## Exclusion rules

Observations are excluded when:

- duplicate `forecast_id`
- evidence class is not `ACTUAL_FORWARD`
- forward integrity is invalid
- decision time is after observation cutoff
- quality state is outside required states
- anchor `event_time_ns` or `available_time_ns` is after decision time
- target horizon is unresolved at settlement cutoff
- provider disconnected (when flagged)

## Current evidence summary

At EVIDENCE-01 implementation time, the repository contains BUILD 26 fixture-validated machinery but no committed live forward observation cohort meeting EVIDENCE-01 thresholds. The generated assessment over an empty observation set remains `INSUFFICIENT_FORWARD_EVIDENCE` with exact remaining requirements in `EVIDENCE01_ASSESSMENT.json`.

Regenerate artifacts:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools/forward_qualification/generate_evidence01_forward_qualification.py
```

## Safety invariants

- Autonomous live trading: **DISABLED**
- Human session authorization: **REQUIRED**
- Per-order confirmation: **REQUIRED**
- EVIDENCE-01 submits orders: **0**
- Model promotion / retraining: **NONE**
- Historical evidence rewrite: **NO**

## Validation evidence

Focused tests: `tests/intelligence/test_evidence01_forward_qualification.py`

BUILD 26 regression: `tests/intelligence/test_forward_qualification.py`
