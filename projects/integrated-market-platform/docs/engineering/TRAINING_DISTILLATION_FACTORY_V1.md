# Training & Distillation Factory (BUILD 18)

BUILD 18 creates reproducible **development candidates** from pre-registered `ExperimentManifestV1`
records. It does **not** validate candidates on locked holdouts, promote them, or change production.

## BUILD 17 → 18 boundary

| Build | Authority |
| --- | --- |
| BUILD 17 | What experiment is authorized |
| BUILD 18 | Generate candidate under that authorization |

`ExperimentManifestV1` is the authorization boundary. Training cannot exceed allowed mutations,
search bounds, seed policy, or resource budget.

## BUILD 18 → 19 boundary

| Build | Role |
| --- | --- |
| BUILD 18 | Candidate generation |
| BUILD 19 | Independent temporal validation |

BUILD 18 outputs unvalidated `CandidateArtifactV1` records with full lineage. BUILD 19 performs
walk-forward validation, purge/embargo, locked holdout evaluation, and Temporal Knowledge Firewall
enforcement.

## Core artifacts

- `TrainingDatasetManifestV1` — exact development dataset identity (`TRDS-*` fingerprint)
- `CandidateTrainingSpec` — deterministic spec identity (`CSP-*`)
- `TrainingRunManifestV1` — execution lineage (`TRN-*`)
- `CandidateArtifactV1` — unvalidated candidate (`CAND-*`)

## No holdout access

When `ValidationRequirements.requires_locked_holdout` is true, `holdout_start_ns` (from experiment
metadata or `decision_end_ns`) defines the forbidden boundary. BUILD 18 never loads, queries, or
scores locked holdout outcomes.

## Dataset semantics

- Training cutoff comes from authorized development specification (not wall clock)
- `label_available_time_ns <= training_cutoff_ns` (inclusive at equality)
- Duplicate examples deduplicated; conflicting labels are hard errors
- Missing features rejected; non-finite features rejected
- Dataset fingerprint is order-independent

## Candidate identity

Semantic candidate ID (`CAND-*`) is derived from experiment + dataset + spec + trainer + seed.
Artifact byte hash (`SHA-256`) verifies integrity but is not the semantic identity.
Parameter fingerprint (`BLPF-*`) diagnoses trainer nondeterminism.

## Artifact security

Logistic vertical slice uses structured JSON (`sklearn-json-v1`). Artifacts are verified by SHA-256
before load. Arbitrary untrusted pickle ingestion is prohibited.

## Search space

Finite deterministic grid expansion only. `max_candidates` and `max_training_runs` enforced before
training begins. No unbounded optimizers.

## Seeds

Explicit `SeedPolicy.fixed_seeds` required when search space is present. Trainers use explicit
`random_state`; no ambient RNG for scientific identity.

## Distillation

**Teacher output ≠ market ground truth.**

- Knowledge distillation: student learns authorized teacher behavior on development inputs
- SFT: manually authored examples without teacher-response matching
- True predictive labels come only from settled `OutcomeV1` records
- `FixtureTeacher` provides deterministic soft targets for tests; no external LLM required
- Historical frontier-teacher replay requiring Temporal Knowledge Firewall is blocked pending BUILD 19

## Trainers (v1)

| Kind | Deterministic | Artifact |
| --- | --- | --- |
| `LOGISTIC_REGRESSION` | Yes | JSON parameters |
| `GRADIENT_BOOSTING` | Yes | JSON parameters |
| `LORA_ADAPTER` | N/A | `TRAINER_UNAVAILABLE` |

## Production immutability

Candidates are `UNVALIDATED` / `DEVELOPMENT_CANDIDATE` only. No champion selection, promotion, or
production model mutation occurs in BUILD 18.

## BUILD 19 handoff

BUILD 19 receives: `ExperimentManifestV1`, `ResearchKnowledgeFootprint`, `TrainingDatasetManifestV1`,
`TrainingRunManifestV1`, `CandidateArtifactV1`, artifact hashes, and trainer/seed lineage to validate
independently without retraining unless desired.

## BUILD 20 handoff

Only BUILD 19-validated candidates may later enter champion/challenger (BUILD 20). BUILD 18
candidates cannot be promoted.
