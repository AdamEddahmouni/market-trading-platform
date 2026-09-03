# Controlled Adaptation & Governed Research Re-Entry (BUILD 24)

> **BUILD 24 closes the learning loop by converting durable operational evidence into governed research re-entry. It never changes weights, prompts, routing, calibration, policies, champions, or runtime directly.**

> **Live learns evidence, not weights.**

## Core principle

Operational monitoring (BUILD 23) may detect drift, health degradation, fail-safe events, and rollbacks. BUILD 24 qualifies that evidence and, when policy thresholds are met, emits a `ResearchTriggerV1` that re-enters the BUILD 17 research pipeline. No production mutation occurs in BUILD 24.

## Complete governed loop

```text
observe → predict → record → settle → measure → monitor → detect
  → qualify (BUILD 24) → trigger research → register observation (BUILD 17)
  → hypothesize → pre-register experiment → build candidate (BUILD 18)
  → independently validate (BUILD 19) → promotion gate (BUILD 20)
  → activate (BUILD 23) → monitor again
```

## What BUILD 24 owns

- `AdaptationPolicyV1` — immutable trigger policy (thresholds, cooldowns, dedup)
- Evidence qualification from BUILD 23 artifacts (no recomputation)
- Batching, recurrence, distinct-window counting
- Exact and semantic deduplication
- Cooldown enforcement with explicit caller-supplied time
- Open-research suppression
- `AdaptationAssessmentV1` — disposition per evidence batch
- `ResearchTriggerV1` — observation routing artifact for BUILD 17
- Optional `AdaptationCampaignV1` lineage container
- Append-only `AdaptationEventV1` audit trail

## What BUILD 24 does NOT do

- Train models or call `partial_fit`
- Fit calibrators
- Access holdout data
- Promote candidates
- Activate or rollback runtime
- Submit paper or live orders
- Auto-generate causal hypotheses or experiments
- Mutate frozen `ExperimentManifestV1`

## One-prediction rule

One forecast, one outcome, or one losing paper trade does **not** authorize adaptation. Statistical evidence requires configured minimum sample, recurrence, and distinct monitoring windows unless policy classifies the event as structural integrity evidence.

## Structural vs statistical evidence

| Class | Examples | Policy |
| --- | --- | --- |
| Structural | schema incompatibility, rollback | May trigger immediately |
| Statistical | calibration drift, performance drift, provider degradation | Requires sample + recurrence + distinct windows |

## Policy identity

`ADAPTPOL-{sha256}` from semantic policy fields only. No wall clock. Policy never self-modifies.

## Assessment identity

`ADAPT-{sha256}` from policy, scope, canonical evidence refs, window, dedup key, and open-research state.

## Research trigger identity

`RTRIG-{sha256}` from policy, scope, evidence refs (order-independent), window, and dedup key.

## Deduplication

- **Exact duplicate**: same evidence refs already consumed → `SUPPRESS_DUPLICATE`
- **Semantic duplicate**: same dedup key with open research → `SUPPRESS_EXISTING_RESEARCH`
- Distinct issues (calibration vs provider vs schema) remain separate unless policy groups them

Dedup key dimensions: scope, evidence class, primary drift type, champion/runtime lineage.

## Cooldown

After a trigger for a semantic issue, `cooldown_ns` suppresses repeat triggers until `reference_time_ns >= last_trigger_time + cooldown_ns`. Higher-severity structural events may bypass cooldown only when `allow_cooldown_bypass_for_structural` is enabled.

## Batching

Evidence within the caller-supplied batch window is grouped by issue class. Correlated telemetry from one incident counts distinct monitoring windows, not raw alert volume.

## BUILD 17 handoff

`register_finding_from_trigger()` creates a `ResearchFindingV1` with type `MONITORING_OBSERVATION`, preserving trigger refs and source evidence. No automatic `ResearchHypothesisV1` or `ExperimentManifestV1`.

## Epistemic ladder

```text
OBSERVATION ≠ EXPLANATION ≠ HYPOTHESIS ≠ EVIDENCE ≠ VALIDATED STRATEGY
```

`ResearchTriggerV1` is an observation routing artifact, not hypothesis, experiment, or training authorization.

## Persistence

Immutable collections (no TTL, no update/delete):

- `adaptation_policies`
- `adaptation_assessments`
- `research_triggers`
- `adaptation_campaigns`
- `adaptation_events`

## Continual adaptation definition

Continual adaptation means continual evidence accumulation plus periodic governed offline research — **not** continuous gradient updates or online weight changes.

## Rollback relation

Rollback may produce a high-priority research trigger. Research does not trigger rollback.

## Provider and execution evidence

- Provider degradation → `DATA_SOURCE` / `QUALITY_POLICY` research class by default
- Paper execution anomalies → `EXECUTION_POLICY` research class
- Neither defaults to model retraining

## Feedback-loop protection

Adaptation control artifacts (`ResearchTriggerV1`, `AdaptationAssessmentV1`, `AdaptationEventV1`) are excluded from eligible evidence. Trigger creation cannot recursively trigger itself.
