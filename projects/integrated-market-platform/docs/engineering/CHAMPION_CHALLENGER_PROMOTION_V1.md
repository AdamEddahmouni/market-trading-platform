# Champion-Challenger Promotion Governance (BUILD 20)

> **BUILD 20 promotes evidence, not optimism.** A candidate becomes champion only through an immutable, pre-registered promotion policy applied to exact independently validated and, where required, forward shadow evidence. Promotion does not itself deploy or execute the candidate.

## Build boundaries

| Build | Responsibility |
| --- | --- |
| BUILD 18 | Candidate generation |
| BUILD 19 | Independent validation |
| BUILD 20 | Promotion governance |
| BUILD 21 | Opportunity generation |
| BUILD 22 | Paper execution / risk |
| BUILD 23 | Runtime governance / monitoring / rollback |

## Core principle

```text
validated candidate ≠ challenger automatically
challenger ≠ champion
ChampionAssignmentV1 ≠ runtime hot-swap
promotion ≠ broker execution
```

## Champion scope

Champions are scoped — not global platform winners. Scope dimensions:

- `component` (e.g. `baseline-prediction`, `final-fusion`)
- `target_kind`
- `horizon_ns`
- `mode`
- `scenario_id` (optional)

Identity: `CHSCOPE-{sha256(canonical scope fields)}`.

## PromotionPolicyV1

Frozen before any promotion evaluation. Identity: `PROMPOL-{sha256}` over semantic fields only (results excluded).

Key fields:

- `required_validation_dispositions` — default `MEETS_PRE_REGISTERED_CRITERIA` only
- `require_clean_contamination` — `CLEAN` required; `UNKNOWN` fails closed
- `require_temporal_knowledge_pass` — BUILD 19 knowledge status authoritative
- `require_artifact_integrity` — exact candidate hash verification
- `primary_metric` / `primary_metric_direction` / `required_improvement`
- `guardrails` — pre-registered secondary metric limits
- `minimum_holdout_samples`, `minimum_shadow_samples`, `minimum_shadow_duration_ns`
- `require_shadow_evidence`, `require_forward_shadow_evidence`
- `allowed_shadow_evidence_tiers` — counterfactual cannot satisfy forward requirement unless policy allows
- `statistical_requirement` — reuses BUILD 19 paired CI evidence
- `complexity_policy` — tiered margin for higher complexity challengers

## Eligibility gate

Hard gates before challenger registration:

1. Validation disposition in policy allow-list
2. Contamination `CLEAN` (not `CONTAMINATED` or `UNKNOWN`)
3. Knowledge firewall `PASS` or `NOT_APPLICABLE`
4. Artifact hash matches validation report
5. Holdout sample ≥ policy minimum
6. Scope compatible with champion slot

## Challenger registration

`ChallengerRegistrationV1` identity: `CHREG-{sha256(candidate, policy, champion assignment, scope)}`.

Registration authorizes shadow evidence collection — **not** promotion.

## Shadow evidence

Observational only:

- Matched champion/challenger forecasts on same opportunities
- Canonical outcome settlement
- Zero execution authority
- `ShadowEvidenceManifestV1` identity from sorted matched observations

Counterfactual replay does not satisfy `require_forward_shadow_evidence`.

## Promotion decision

`PromotionDecisionV1` outcomes:

- `PROMOTE` — all gates pass
- `RETAIN_CHAMPION` — metric/guardrail/complexity failure
- `INCONCLUSIVE` — insufficient shadow sample/duration or missing guardrail data
- `INVALID` — eligibility/contamination/knowledge/champion-basis failure

Identity: `PROMDEC-{sha256}` from policy, champion, challenger, evidence refs (decision output excluded).

## Champion assignment

`ChampionAssignmentV1` is governance truth:

- References promotion decision and previous champion
- Append-only history
- `BOOTSTRAP` path for initial champion (explicit, no metric scan)
- **Does not** hot-swap runtime, reload models, or change broker authority

## Complexity penalty

Uses BUILD 17 `ComplexityBudget`:

- `SAME_COMPLEXITY` — base improvement margin
- `MINOR_COMPLEXITY_INCREASE` — additional margin
- `MAJOR_COMPLEXITY_INCREASE` — larger additional margin

Added complexity must earn its keep via policy-defined margins.

## Persistence

Immutable collections via `IntelligenceRepository`:

- `promotion_policies`
- `promotion_eligibility_assessments`
- `challenger_registrations`
- `shadow_evidence_manifests`
- `promotion_decisions`
- `champion_assignments`
- `challenger_lifecycle_events`

No TTL, no overwrite, idempotent insert on identical content.

## BUILD 21 handoff

BUILD 21 should consume `get_current_champion_assignment(scope, as_of_ns)` for governed champion lookup and `ForecastV1` from that champion path — not re-rank historical candidates.

## BUILD 23 handoff

BUILD 23 can consume champion assignment history, promotion decisions, shadow evidence, and challenger lifecycle for monitoring, drift, rollback, and governed override — without rewriting BUILD 20 records.
