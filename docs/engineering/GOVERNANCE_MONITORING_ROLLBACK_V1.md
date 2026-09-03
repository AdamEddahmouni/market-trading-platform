# Governance, Monitoring, Runtime Activation & Rollback (BUILD 23)

> **BUILD 23 governs what is authorized to run, measures whether it remains healthy, detects drift and operational inconsistency, fails closed when critical evidence is unsafe, and can roll runtime activation back only to a previously governed known-good state. It does not train or promote new models.**

## Build boundaries

| Build | Responsibility |
| --- | --- |
| BUILD 20 | Champion governance (promotion truth) |
| BUILD 21 | Opportunity engine |
| BUILD 22 | Deterministic risk + paper execution |
| BUILD 23 | Runtime governance + monitoring + rollback |
| BUILD 24 | Controlled adaptation (future) |

## Champion vs runtime activation

`ChampionAssignmentV1` records BUILD 20 governance truth: which candidate is the governed champion.

`RuntimeActivationV1` records operational authorization: which artifact/config may run now.

These are **different**. A champion may exist without activation (`NOT_ACTIVATED`). Rollback creates a **new** runtime activation referencing a prior governed artifact; it does **not** rewrite promotion history.

Rollback may produce **active fallback divergence**: runtime-active artifact differs from latest promoted champion. This state is explicit in activation metadata and `RuntimeGovernanceState.active_fallback_divergence`.

## Paper-only safety

All activation policies require:

- `paper_execution_only = True`
- `live_execution_forbidden = True`

Live broker execution cannot be activated. Overrides cannot enable live execution or bypass risk.

## Runtime activation

`RuntimeActivationPolicyV1` defines preconditions (champion lineage, artifact integrity, paper-only modes).

`RuntimeActivationV1` binds:

- champion assignment reference
- candidate artifact hash (verified before activation)
- activation policy
- effective time range
- previous activation link

Activation identity is deterministic (`RTACT-{sha256}`).

## Health model

BUILD 23 health is **operational/system condition** over explicit windows — not BUILD 04 decision-level quality.

Health states: `HEALTHY`, `DEGRADED`, `UNHEALTHY`, `UNKNOWN`, `DISABLED`.

Snapshots:

- `ProviderHealthSnapshotV1`
- `DataQualityHealthSnapshotV1`
- `IntelligenceHealthSnapshotV1` (reuses BUILD 16 metrics)
- `ExecutionHealthSnapshotV1` (PAPER only)
- `OpportunityHealthSnapshotV1`
- `RuntimeHealthSnapshotV1` (aggregate)

Empty windows return `UNKNOWN` / `NO_OBSERVATIONS`, never fake zero-error health.

Performance monitoring respects `evaluation_as_of_ns`; future labels are excluded.

## Drift monitoring

`DriftPolicyV1` holds immutable thresholds (no auto-tuning).

`DriftAssessmentV1` is deterministic evidence of:

- schema drift
- feature / missingness drift
- forecast distribution drift
- performance drift
- calibration drift (ECE — **no calibrator fitting**)
- provider / quality / execution anomalies

Drift is **evidence**, not causal diagnosis and not permission to retrain.

## Alerts vs actions

`GovernanceAlertV1` recommends actions but does not mutate runtime unless `FailSafePolicyV1` maps the condition to a `FailSafeDecisionV1`.

## Fail-safe control

`FailSafeDecisionV1` values:

- `ALLOW`
- `DEGRADE`
- `DISABLE_NEW_OPPORTUNITIES`
- `DISABLE_NEW_PAPER_ORDERS`
- `DISABLE_SCOPE`
- `FAIL_CLOSED`

Fail-safe blocks **future** actions only; historical opportunities/orders/fills remain immutable.

## BUILD 21 / 22 integration

- `OpportunityEngine.assess(..., runtime_governance=...)` fails closed when scope disabled.
- `PreTradeRiskEngine.build_proposal(..., runtime_governance=...)` rejects when paper execution disabled.
- `PaperExecutionOrchestrator.execute_paper(..., runtime_governance=...)` passes gate through.

## Rollback

`RollbackPolicyV1` + `RollbackDecisionV1`:

- Target must be previously governed, same scope, integrity-valid.
- Unpromoted candidates are invalid targets.
- Decisions: `ROLLBACK`, `RETAIN`, `DISABLE_ONLY`, `INCONCLUSIVE`, `INVALID`.
- Rollback creates new activation; old activations and BUILD 20 history preserved.

## Audit trail

`GovernanceEventV1` append-only events: activation, drift, alerts, fail-safe, rollback, override.

## Persistence

Immutable collections (no TTL on canonical evidence):

- `runtime_activation_policies`, `runtime_activations`
- `drift_policies`, `drift_assessments`
- `governance_alerts`, `fail_safe_policies`, `fail_safe_decisions`
- `rollback_policies`, `rollback_decisions`, `governance_events`

InMemory and Mongo repositories implement parity.

## BUILD 24 handoff

BUILD 23 emits structured evidence (drift assessments, health snapshots, governance events, optional `ResearchTriggerV1`) for BUILD 17 research and the BUILD 24 controlled adaptation loop:

```text
monitoring evidence → BUILD 17 hypothesis/experiment
                 → BUILD 18 training
                 → BUILD 19 validation
                 → BUILD 20 promotion
                 → BUILD 23 activation/rollback
```

**Monitoring evidence ≠ permission to change weights.** BUILD 24 must not become per-prediction online learning.

## Explicit non-goals

- No model training or retraining in BUILD 23
- No calibrator fitting
- No automatic feature or routing changes
- No unpromoted activation
- No live broker execution
- No history rewrite
- No monitoring daemon or external metrics backend (v1)
