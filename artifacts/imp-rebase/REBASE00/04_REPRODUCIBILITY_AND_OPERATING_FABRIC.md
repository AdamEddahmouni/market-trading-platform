# Reproducibility and Operating Fabric Baseline

## Reproducibility grades

| Area | Grade | Evidence and gap |
|---|---|---|
| Tests | `STRONG` correctness / `PARTIAL` run provenance | Manifest has 64 suites (49 offline, 12 live, 3 intentionally absent), 10 domains, 21 invariants; reports lack SHA/branch/dirty/command/config/attempt history |
| Models | `STRONG` in BUILD18/19 lanes | Candidate, trainer, hyperparameters, seed, model/artifact hashes, validation plan/holdout fingerprints exist; no global registry |
| Data | `STRONG` in training/evidence lanes / `PARTIAL` globally | Dataset fingerprints, cutoffs, feature schema and source refs exist; source admission and dataset identity remain subsystem-scoped |
| Experiments/research | `PARTIAL` | Research orchestrators/cards/fixtures exist, but no universal experiment/run linkage or disposition history |
| AI/research | `WEAK` for live inference reproducibility | Provider/model/tokens/citations are stored; exact system prompt/version, evidence-pack hash/content, request parameters, response ID, code/config/run identity are not |
| Evidence campaigns | `STRONG` in EVIDENCE-01A/B | Frozen policy/config fingerprint, append-only observations/sessions/checkpoints, source manifest, settlement authority; operational shakedown still pending |
| Provider smoke tests | `PARTIAL` | Probes and provider-specific reports exist; no universal run record/environment/attempt model |
| Performance benchmarks | `WEAK` | Local feed percentiles and validation timings exist; no accepted end-to-end benchmark protocol or ledger |

## Run manifest and missing universal ledger

`VERIFIED` `RunManifestV1` captures run ID/window, data and execution modes/authority, code revision, configuration identity, provider config refs, feature schema refs, model/fusion/calibration/strategy/prediction versions, environment, and component lineage.

`VERIFIED` It does not require branch/dirty state, exact command, data/artifact refs, stdout/stderr refs, attempts/retries, status transitions, actor, parent run, or durable global indexing. Validation JSON similarly omits these fields and has no retry model. Reusing the same output path can erase evidence of an earlier failed invocation.

`PROPOSED` Create one append-only run envelope around existing operation-specific records:

| Operation class | Existing anchor | First ledger integration |
|---|---|---|
| `TEST`, `VALIDATION` | validation manifest/report | Source state, command, selected suites, worker attempts, report hash |
| `MODEL_TRAIN`, `MODEL_INFERENCE` | training run/candidate/model refs | Dataset/config/model/prompt hashes, parent/child run |
| `BACKTEST`, `REPLAY`, `SIMULATION` | replay/shadow/research pipelines | Input snapshot/data refs, cost model, result/disposition |
| `DATA_INGEST`, `DATA_TRANSFORM` | provider envelopes/captures/dataset pipeline | Provider capability/probe, admission policy, raw/normalized hashes |
| `RESEARCH`, `AI_AGENT` | research orchestrator/assistant audit | Hypothesis/task, prompt/evidence pack/tool refs, outcome and approval |
| `PROVIDER_SMOKE` | provider probes/tools | Environment, endpoint class, attempt history, redacted evidence |
| `EVIDENCE_CAMPAIGN` | EVIDENCE campaign store | Reference frozen session/checkpoint records without modifying them |
| `PERFORMANCE_BENCHMARK` | feed/validation timing | Benchmark definition, samples, percentiles, environment |
| `RELEASE` | deployment/release manifests | Candidate/source/evidence/deployment refs and approvals |

Status must distinguish at least `PASS`, `PASS_WITH_RETRY`, `FAIL`, `INFRASTRUCTURE_FAILURE`, `ABORTED`, and `NOT_RUN`.

## Existing Operating Fabric

`PARTIAL`, with reusable components:

- Manifest-driven test selection and parallel execution.
- Semantic detection, routing templates, inference scheduling, callbacks, and outcome scheduling.
- Research, training, validation, promotion, adaptation, deployment, release, forward-campaign, and live-canary orchestrators.
- Canonical JSON/JSONL writers, immutable IDs/hashes, ledgers, local state repositories, evidence checkpoints, and manifests.
- Live operational health/SLO evaluation, alerts, incidents, recovery, backups, control plane, and 20 BUILD33 exercised runbook entries.
- Provider capability probes, subscriptions, bounded queues, reconnect generations, and rate/pacing controls.

`ABSENT` as program-wide authorities:

- Universal operation type and lifecycle.
- Durable workflow definition/registry with input/output contracts, idempotency key, retry/compensation policy, ownership, and parent/child runs.
- Global capability registry joining source support, entitlement, implementation, runtime evidence, freshness, admission, and environment.
- Universal artifact/run index and retention policy.
- Skill/tool registry for AI or operator actions.
- Program-wide structured logging, trace/span propagation, and correlation across provider → feature → inference → risk → UI → broker.
- Consolidated incident/problem/debt register across domains.

## Workflows, SOPs, incidents, and debt

`VERIFIED` Many `tools/**/run_*_pipeline.py` scripts are deterministic milestone pipelines. Intelligence schedulers and orchestrators have stronger lifecycle contracts. They should be registered as distinct workflow implementations, not forced behind one engine immediately.

`VERIFIED` Runbooks and incident types are strongest in BUILD30–33 supervised-live operations. Their evidence is fixture/single-host scoped. Provider docs contain additional operating procedures, but there is no global SOP registry or ownership/effectivity model.

`VERIFIED` Known limitations are distributed across BUILD25–35, EVIDENCE, provider, and engineering docs. There is no single technical-debt/problem register with owner, severity, dependency, disposition, and evidence of closure.

`PROPOSED` First Operating Fabric slice: operation taxonomy + append-only run ledger + artifact links + adapter for validation. Add workflow registry only after the ledger proves the common lifecycle. Add an AI skill registry only when multiple durable agent/tool workflows require governance.

## Observability

`VERIFIED` BUILD32 supplies health, SLO, alert, backup/recovery, persistence, and dependency status for supervised live operations. Moomoo supplies queue, callback, processing, drop, duplicate, and sequence metrics. Execution records use correlation IDs in selected paper paths.

`PARTIAL` Standard Python logging/tracing is not a program-wide contract; `trace_id`/`span_id` propagation was not found. The BUILD32 observability inventory is historical and single-host/fixture qualified, with local/console alert delivery by default.

`PROPOSED` Define event/log schema only after the operation/run IDs are canonical. Require timestamp, severity, operation/run, correlation, component, event type, state transition, source/provider, safe error code, and artifact refs; add trace/span IDs for causal paths and explicit secret/redaction rules.
