# IMP-REBASE-02 Reproducibility, Observability, Evaluation & Operational Standards — Design

| Field | Value |
|---|---|
| Document ID | `IMP-REBASE-02-DESIGN` |
| Classification | `ACTIVE_SUPPORTING` |
| Primary Truth Class | `APPROVED_FUTURE_DESIGN` |
| Review State | `READY_FOR_WRITTEN_SPEC_REVIEW` |
| Version | `1.0` |
| Last Verified | `2026-08-27` |
| Establishing Milestone | `IMP-REBASE-02 design` |
| Supersedes | None |
| Superseded By | None |

This document is the design input to one final written-spec review. It is not a
runtime authority, an accepted canonical standard, an implementation plan, or
evidence that the standards have been implemented. Executable sources and
frozen evidence named by the canonical truth map continue to control their
current scopes.

## Purpose

IMP-REBASE-02 defines the program semantics by which consequential work is
identified, attributed, observed, evaluated, reproduced where possible,
retained, and accepted. It closes the standards gap between strong but
subsystem-specific IMP records without replacing those records or pretending a
Universal Run Ledger already exists.

The design makes five separations foundational:

1. A logical run is not an individual process attempt.
2. Technical execution is not analytical or operational outcome.
3. Outcome is not the platform's final disposition.
4. A run is not a trace, event, span, workflow, or artifact.
5. Attribution is useful even when bit-for-bit reproduction is impossible.

The resulting standards must let OF-01, OF-02, RT-01, XA-01, OF-03, and AI-01
implement compatible contracts without modifying EVIDENCE-01C or inventing
parallel meanings for run, retry, provenance, trace, benchmark, or acceptance.

## Normative language

`MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, and `MAY` express requirements for
the future canonical standards and their downstream implementations. They do
not assert that the current repository already satisfies the requirement.

An implementation may use different physical schema or enum names only when it
provides a documented, lossless mapping to the semantics in this design. This
design deliberately does not freeze names such as `RunRecordV1`,
`AttemptRecordV1`, `ArtifactManifestV1`, or `TraceV1`.

## Verified starting state

The design recovered repository state on 2026-08-27 before drafting.

| Item | Verified value |
|---|---|
| Repository | `C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform` |
| Original branch / HEAD | `cloud/build-35-release-governance-operational-acceptance` / `44800d2e210e58ff5759c44cc343dd4578c0b821` |
| Original upstream | `origin/cloud/build-35-release-governance-operational-acceptance` at `020b64377393c3af1e085b9906e74552a2ca08b9` |
| Original ahead / behind | `5 / 0` against the locally configured upstream ref |
| Original dirty state | 9 tracked modifications and 7 untracked paths; preserved untouched |
| Accepted REBASE-01 branch / HEAD | `docs/imp-rebase-01-canonical` / `9c7ea456cadc9d9b381447640e0bda506e779f0a` |
| Accepted REBASE-01 upstream | None configured; no remote branch named `docs/imp-rebase-01-canonical` was observed by `git ls-remote` |
| Superseding accepted descendant | None found; only the accepted branch and this design branch contain `9c7ea456...` |
| Design branch | `docs/imp-rebase-02-design` |
| Design worktree | `C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform/.worktrees/imp-rebase-02-design` |
| Design starting HEAD | `9c7ea456cadc9d9b381447640e0bda506e779f0a` |
| Design upstream | None configured |
| Isolation | Dedicated clean worktree; the dirty original and accepted REBASE-01 worktree remain untouched |

The remote observation branch remains at `020b643...`; remote `main` was
observed at `c2c0a719255117fe6f28b03cdf18734a2178ab9`. Neither ref supersedes the
accepted REBASE-01 documentation commit. No fetch, push, merge, reset, clean,
stash, force-push, or `main` update was performed.

The stale original checkout at `44800d2...` is not the planning base. The
premature REBASE-01 worktree at `6d365031d36a4d1b2f14a80d2690c28cff9c9713`
was not used.

The clean baseline command:

```powershell
$env:PYTHONPATH='src'
..\..\.venv\Scripts\python.exe tools\validate.py changed --explain
```

returned `PASSED changed: 0 tests, 0 skipped, 0 failures, 0 errors`, with
`full_suite_required=false`.

## Governing inputs reviewed

The design uses this precedence:

1. current executable repository truth;
2. accepted `docs/platform/` canonical program truth;
3. accepted REBASE-01 specification and acceptance evidence;
4. accepted REBASE-00 audit evidence;
5. the REBASE-02 design prompt.

The review included all ten canonical `docs/platform/` documents, both
REBASE-01 specifications, the complete REBASE-01 acceptance package, all
REBASE-00 narrative reports, validation code/manifest/CI, and representative
runtime contracts named below. Mutable thresholds, identities, suite lists,
and provider states remain in their executable or frozen sources and are not
copied here as current policy.

## Scope

REBASE-02 may define:

- logical run, attempt, execution, outcome, disposition, relationship, trigger,
  resume, checkpoint, and partial-output semantics;
- consequence profiles and hot-path recording expectations;
- reproducibility classes and attribution requirements for source, code,
  configuration, data, model, policy, environment, time, inputs, and outputs;
- artifact identity, mutability, storage role, retention, redaction, and secret
  handling;
- structured-log, metric, trace, correlation, clock, and latency semantics;
- test, validation, benchmark, replay, simulation, backtest, provider-smoke,
  model, experiment, research, and AI evaluation semantics;
- failure, interruption, cancellation, idempotency, retry, resume, incident,
  problem, limitation, and corrective-action linking;
- consequence-based change validation, documentation validation, acceptance
  evidence, and future drift-detection requirements;
- the minimum non-overlapping canonical standards set and exact downstream
  milestone handoffs.

## Out of scope

REBASE-02 MUST NOT implement or alter:

- the Universal Run Ledger, run/attempt runtime schemas, artifact registry,
  workflow engine, capability registry, skill registry, SOP registry, incident
  registry, or debt registry;
- logging, metrics, tracing, message-bus, OpenTelemetry, benchmark, data,
  model, configuration, or AI orchestration infrastructure;
- providers, adapters, cross-asset runtime, model behavior, training behavior,
  prediction, settlement, qualification, risk, execution, release, broker
  transport, or reconciliation;
- EVIDENCE policy, campaign origin, session/checkpoint semantics, qualification
  thresholds, settlement behavior, source admission, or historical records;
- production live broker transport, autonomous execution, or automatic broker
  failover;
- canonical `docs/platform/` files or `PROGRAM_STATUS.md` during this design
  task.

## Current reusable foundations

### Validation

`tools/validation_manifest.json` is the current suite inventory. It declares
64 suites across offline, live, and intentionally absent classifications, ten
domains, 21 ordered mandatory invariants, ownership globs, neighbors, safety
classes, and full invalidators. The counts are verified current facts for this
design cutoff, not values for future canonical prose.

`tools/validate.py` already provides:

- deterministic FAST, CHANGED, DOMAIN, FULL, LIVE, EXTENDED, and informational
  BENCHMARK modes;
- changed-path selection, reasons, omitted domains, cheap documentation and
  evidence checks, `full_suite_required`, process isolation, sanitized worker
  diagnostics, interruption handling, and atomic JSON report replacement;
- explicit `passed`, `failed`, `error`, and `interrupted` invocation results;
- exact test/pass/skip/failure/error counts, skip/failure details, per-worker
  timing, suites not run, and selection metadata.

It does not record a universal run identity, source SHA, branch/dirty state,
exact parent invocation, configuration fingerprint, environment manifest,
attempt history, or append-only prior reports. Reusing one output path can
replace a prior invocation report. REBASE-02 therefore generalizes its strong
selection/result semantics but does not call current validation universally
attributable.

The current CI runs FAST plus CHANGED on pull requests and pushes to `main`.
FULL remains the authoritative offline checkpoint when repository policy
requires it. BENCHMARK results are already available but informational and
non-gating; the gap is accepted comparability and provenance, not total absence
of benchmark code.

### Run and lineage contracts

`RunManifestV1` is an immutable intelligence configuration manifest with a run
ID, creation time, optional window, data/execution modes, execution authority,
code revision, configuration identity, provider/feature/model/calibration/
strategy/prediction references, environment, quality, component lineage, and
metadata. It is reusable as one operation-specific manifest.

It does not currently supply universal attempt history, lifecycle transitions,
actor/trigger, exact command, dirty-source attribution, input/output artifact
links, parent/root relationships, stdout/stderr, final outcome/disposition, or
global durable indexing. OF-01 must index or adapt it; REBASE-02 must not
replace it.

### EVIDENCE

EVIDENCE-01A/B provide the strongest operational provenance patterns:

- content-derived campaign, session, observation, checkpoint, report, and
  configuration identities;
- frozen source SHA, policy, provider, universe, observation/execution modes,
  persistence, calendar, continuity, quality, predictor, and settlement refs;
- canonical JSON configuration fingerprints and semantic drift checks;
- distinct campaign, session, observation, checkpoint, health, heartbeat,
  shakedown, and operational-event concepts;
- append-and-fsync JSONL observations/events plus separate mutable current
  runtime/heartbeat/metric surfaces;
- explicit evidence origin (`LIVE_FORWARD`, fixture, replay, synthetic),
  termination reasons, cutoffs, health degradations, remaining requirements,
  and final qualification dispositions.

The audit found an important qualification: not every EVIDENCE file is
physically append-only. Runtime aggregates and sessions are atomically
rewritten, while observations, operational events, intelligence records, and
identity-addressed checkpoints preserve history differently. Future standards
MUST distinguish physical append-only records from logically append-preserving
mutable aggregates.

### Prediction, settlement, and temporal integrity

`PredictionLedgerEntryV1` freezes forecast identity, target/horizon, instrument,
decision time, anchor, target window, availability cutoff, settlement policy,
source policy, mode, registration time, and lineage. `OutcomeSettlementService`
checks maturity, refuses policy mismatch, returns `NOT_DUE`, and treats an
idempotently existing result as `ALREADY_SETTLED` instead of creating a second
outcome.

`EventV1`, `ProviderProvenance`, and the temporal kernel separate event,
provider, receipt, availability, and decision clocks. The governing
anti-lookahead law is:

```text
available_time_ns <= decision_time_ns
```

Replay uses the same law as live observation. Revisions and late arrivals do
not retroactively rewrite earlier decisions. REBASE-02 generalizes these
principles to run attribution without redefining their domain contracts.

### Models, validation, and research

Training and independent validation already provide deterministic dataset,
candidate-spec, training-run, model-artifact, holdout-commitment, validation-
dataset, and report identities. Reusable fields include dataset and feature
fingerprints, source artifacts, cutoffs, hyperparameters, seed, trainer/model
version, artifact hash, candidate/control refs, walk-forward/holdout design,
purge/embargo, temporal knowledge policy, contamination disposition, metrics,
and final validation disposition.

Research contracts distinguish finding, hypothesis, experiment manifest, and
lifecycle event. They preserve baseline/treatment/control, primary and
secondary metrics, guardrails, falsification, evidence tier, knowledge
footprint, search/seed/resource budget, allowed and forbidden changes, and
negative or inconclusive lifecycle states. These are strong domain contracts,
not a universal registry.

### Data and artifacts

Governed lanes already use source manifests, raw references/hashes, provider
and adapter identity, source revision, dataset fingerprints, time coverage,
cutoffs, feature-schema identity, artifact hashes, and lineage references.
Acceptance packages use committed manifests and SHA-256 inventories. Runtime
and local-only outputs also exist under `evidence/`, `reports/`, local stores,
and ignored paths.

Path alone is not reliable artifact identity. Git is suitable for canonical
documents, policies, manifests, and selected acceptance evidence; it is not a
universal runtime database.

### Logging, metrics, correlation, and clocks

Current patterns include standard Python diagnostics, redacted JSON/JSONL
journals, EVIDENCE operational events, health/heartbeat state, validation
results, domain events, paper-ledger correlation IDs, BUILD32 health/SLO/
recovery snapshots, bounded-queue counters, Moomoo callback and processing lag,
and exact reference-based forecast-to-fill lineage views.

These are not one program contract. `trace_id` and `span_id` propagation are
not program-wide, and a BUILD31 lineage view is not a distributed trace. The
shared `monotonic_wall_ns()` protects in-process wall-time identity ordering;
`time.monotonic()`/`perf_counter()` remains the correct elapsed-duration clock.
Cross-process clock comparability and uniqueness require additional context.

### AI attribution

The assistant records provider/model, token counts, citations, abstention,
message content, and a read-only/no-execution boundary. Evidence packs and
grounded citations exist. Current gaps include per-operation source/code/config
identity, prompt/template version/hash, inference settings, tool invocation,
evidence-pack hash, request/response ID, latency, retry, and raw response hash.
The JSON arrays are rewritten and retention can delete conversations, so the
store supplies logical audit history but not immutable/WORM evidence.

### Provider smoke and redaction

Provider probes already distinguish observed, untested, unavailable, and error
states; preserve provider/symbol/capability/session context; and apply bounded
redaction. Moomoo smoke currently prints a process result with environment,
connection, data, counters, and metrics but lacks universal run/attempt/source
identity. Real provider tests and mocks are not always expressed through one
common origin field.

The strongest reusable redaction pattern is conservative key/text redaction
before append, with request/response captures explicitly marked
`CAPTURED_NOT_ADMITTED`. REBASE-02 adopts the principle, not a single current
redactor as universal implementation.

## Design alternatives and decision

Three structures were evaluated:

1. **One monolithic standard.** This minimizes file count but makes run
   semantics, high-volume observability, and evaluation protocols hard to own
   independently and invites a large unreviewable document.
2. **Four standards, including a separate operational standard.** This gives
   failure/retry/resume a dedicated home but duplicates run lifecycle,
   disposition, artifacts, retention, and incident links.
3. **Three standards.** Run/reproducibility owns identity and operational
   lifecycle; observability owns emitted diagnostics and timing; evaluation
   owns validity/comparison protocols.

The design selects option 3. It is the smallest split with non-overlapping
subjects.

## Common semantic model

### Consequential operation

A consequential operation is work whose result, failure, timing, or side
effect may affect accepted evidence, canonical or operational state, a model or
dataset decision, a provider assessment, a release, an authority decision, or
a material research conclusion. Consequence is determined by contract, not by
process duration or whether a human watches the process.

Routine function calls, individual log statements, cache hits, UI renders, and
high-volume market events are not automatically consequential operations.

### Run

A run is one durable logical invocation of a declared consequential objective
under a stable identity and evaluation intent. A run answers: “what work did we
intend to perform and judge as one unit?” It is not defined by one operating-
system process.

A run MUST have:

- stable run identity and operation class;
- objective or invocation reference;
- consequence profile;
- creation time and lifecycle;
- initiator class and trigger context;
- applicable source/config/data/model/policy/time/environment attribution;
- zero or more attempts;
- typed relationships;
- terminal outcome and disposition, or an explicit reason neither exists;
- artifact/log/trace references required by its profile;
- provenance completeness and reproducibility classification.

A run is created before its first attempt when the consequence profile requires
durable pre-execution identity. For lower profiles it MAY be materialized from a
buffered start event, provided identity/order loss stays within declared loss
tolerance. A run begins active execution when its first attempt starts. It
closes only when a terminal disposition is appended; process exit alone does
not close it.

A workflow MAY be a parent run when the workflow itself has one durable
objective and disposition. Its material steps MAY be child runs. An individual
model inference is a run only when it is independently consequential or needs
durable evaluation/review; hot-path inferences MAY remain spans/events within a
larger run or session. Individual ticks MUST NOT be promoted to full runs solely
for observability.

### Run lifecycle

The common lifecycle vocabulary is intentionally small:

| State | Meaning |
|---|---|
| `REGISTERED` | Identity and intent exist; no attempt has started. |
| `ACTIVE` | At least one attempt or continuation is executing. |
| `SUSPENDED` | Work is intentionally paused and may resume under compatibility rules. |
| `CLOSED` | A terminal disposition has been appended. No new attempt may mutate this run. |

Operation-specific states MAY exist separately. These run states MUST NOT be
reused as program maturity, qualification, or authority states.

### Attempt

An attempt is one bounded technical execution of a run. It answers: “what did
the platform try this time?” Every attempt has an immutable identity unique
within the run, a one-based sequence, start/end times, invocation/environment
context, technical execution result, reason codes, artifacts, and any retry
relationship to the preceding attempt.

Attempt history MUST be append-preserving. A later pass MUST NOT overwrite an
earlier failure. An attempt MAY create continuation segments/checkpoints, but a
segment is not a new attempt unless execution was re-entered after a technical
termination or explicit retry boundary.

Attempt phase and terminal technical result are separate:

| Dimension | Common values |
|---|---|
| Attempt phase | `PENDING`, `RUNNING`, `TERMINAL` |
| Terminal technical result | `COMPLETED`, `FAILED`, `TIMED_OUT`, `CANCELLED`, `INTERRUPTED`, `LOST`, `NOT_STARTED` |

`FAILED` means the execution reported a technical failure. `INTERRUPTED` means
continuity ended unexpectedly with known evidence, such as provider disconnect
or machine shutdown. `LOST` means expected termination evidence was not
recorded and a later reconciler inferred loss. `CANCELLED` requires an actor or
policy cause. Unknown causes MUST remain unknown rather than being guessed.

### Outcome

Outcome describes what the completed or partially completed work found or
produced under its domain contract. It is a typed result, not one universal
pass/fail enum. Examples include validation criteria satisfied, model below
baseline, insufficient sample, provider unavailable, benchmark measurements,
or temporal leakage detected.

Every outcome MUST declare validity separately from its domain result:

- `VALID`: the result can be interpreted under the declared protocol;
- `INVALID`: a protocol, temporal, provenance, contamination, or integrity
  defect prevents interpretation;
- `INDETERMINATE`: available evidence cannot establish validity;
- `NOT_EVALUATED`: no outcome evaluation occurred.

A valid negative or inconclusive analytical result is still a technically
successful run result.

### Disposition

Disposition is the governed decision made about an outcome. It MUST be appended
after considering execution and outcome and MUST carry decision time, decision
authority/reference where applicable, reason code, and limitations.

To avoid a giant cross-domain enum, every disposition has a common action
category and a domain-specific code:

| Action category | Meaning |
|---|---|
| `ACCEPT` | Accept the result for its declared scope. |
| `REJECT` | Preserve the valid result but reject the candidate/proposition/action. |
| `DEFER` | No final judgment; a declared condition or evidence is pending. |
| `RETRY` | A new attempt is authorized under retry/idempotency policy. |
| `INVALIDATE` | The result cannot be used under the declared protocol. |
| `CANCEL` | Intentionally stop and close the run. |
| `ABANDON` | Close without completion after the intent is no longer being pursued. |
| `SUPERSEDE` | Replace this run's relevance with a linked successor without rewriting it. |
| `NO_ACTION` | Preserve the result without promotion, rejection, or immediate follow-up. |

Domain codes include, but are not globally limited to, `PASS`,
`PASS_WITH_RETRY`, `VALID_RESULT_REJECTED`, `INCONCLUSIVE`,
`NOT_RUN_MARKET_CLOSED`, or `INVALID_TEMPORAL_LEAKAGE`. Existing domain
vocabularies such as `ValidationDisposition` and EVIDENCE qualification states
retain their authority and map to the common category only for indexing.

### Retry

A retry is a new attempt within the same open run when objective, evaluation
intent, semantically effective inputs, and identity-defining cutoffs remain
compatible. A retry MUST reference the preceding attempt, retry reason,
retry-policy reference, idempotency declaration, and changed execution context.

If source/config/data/model/cutoff or intended judgment changes materially, the
work MUST become a new linked run, not another attempt. A passing retry does not
prove the earlier failure was flaky. `FLAKY_FAILURE` may be recorded only when
independent evidence supports that classification.

### Resume

Resume behavior is selected by semantics:

| Situation | Required representation |
|---|---|
| Process remains alive and continues from an internal checkpoint | Same attempt, new continuation segment. |
| Technical execution ended, then restarts with compatible checkpoint and unchanged intent | Same run, new attempt with `resumed_from_checkpoint`. |
| A parent workflow launches recovery work with its own outcome | New child run linked by `TRIGGERED_BY` and checkpoint refs. |
| Identity-defining source/config/data/model/cutoff changes, or predecessor is already closed | New run linked by `RESUMES_FROM` or `SUPERSEDES`; never mutate the predecessor. |

A checkpoint MUST identify run and attempt, content/state hash, production
time, compatibility dimensions, resume eligibility, and invalidation reason if
no longer eligible.

### Relationships

Relationships are typed because containment, causation, replacement, and
association are not interchangeable.

| Relationship | Meaning |
|---|---|
| `PARENT_OF` / `parent_run` | Structural containment; a parent owns the child step. |
| `root_run` | Stable root of a containment tree. |
| `TRIGGERED_BY` | Causal invocation; does not imply ownership. |
| `RESUMES_FROM` | New run continues eligible predecessor state. |
| `SUPERSEDES` | New run replaces predecessor relevance without erasing it. |
| `RELATED_TO` | Non-causal association requiring a relation reason. |

Retries are attempt relationships and MUST NOT use a `retries_run` link. A
cross-run recovery caused by changed semantics uses `RESUMES_FROM` or
`SUPERSEDES` and explains why it could not remain the same run.

The ledger implementation SHOULD support a DAG, not assume every relationship
is a strict tree. Structural parenthood MUST remain acyclic.

### Trigger and initiator

Every consequential run MUST record an initiator class from a stable common
set: `HUMAN`, `CI`, `SCHEDULER`, `SYSTEM`, `WORKFLOW`, `AGENT`, or
`PROVIDER_EVENT`. It MAY record a scoped pseudonymous or governed initiator
reference. It MUST NOT persist personal data merely to improve provenance.

Trigger context is separate and may reference an event, schedule, pull request,
workflow run, policy decision, prior run, or operator request. An AI/model-
triggered investigation uses initiator `AGENT` or `SYSTEM` plus the triggering
model/run reference; that does not grant authority.

### Event, trace, span, run, workflow, and artifact

| Concept | Identity question |
|---|---|
| Event | What discrete observation or domain fact occurred? |
| Trace | What causal path did one event/request take through stages? |
| Span/stage | What bounded segment of that causal path executed? |
| Run | What consequential objective was executed and judged as one unit? |
| Workflow | What declared orchestration related multiple operations? |
| Artifact | What durable or referenced content was produced or consumed? |

`event_id`, `trace_id`, `span_id`, `correlation_id`, and `run_id` MUST NOT be
treated as aliases. A market event can carry event/trace/correlation identity
and pass through many spans within one longer-lived session run. A trace MAY
cross run boundaries, and a run MAY contain many traces. A correlation ID
groups related facts when strict causal parentage is unavailable; it is not
proof of causality.

## Disposition examples

| Case | Technical execution | Outcome validity and domain result | Disposition |
|---|---|---|---|
| Validation passes first attempt | Attempt 1 `COMPLETED` | `VALID`; criteria satisfied | `ACCEPT / PASS` |
| Validation passes after environment retry | Attempt 1 `FAILED` with `ENVIRONMENT_FAILURE`; attempt 2 `COMPLETED` | `VALID`; criteria satisfied | `ACCEPT / PASS_WITH_RETRY`; both attempts retained |
| Model experiment underperforms | `COMPLETED` | `VALID`; candidate below baseline | `REJECT / VALID_RESULT_REJECTED` |
| Provider smoke during market closure | Preflight attempt `COMPLETED`; provider observation `NOT_STARTED` | `NOT_EVALUATED`; expected market state | `DEFER / NOT_RUN_MARKET_CLOSED` |
| Live observation loses provider | `INTERRUPTED` with captured partial inputs | `INDETERMINATE` until continuity policy review | `RETRY`, `DEFER`, or `INVALIDATE` under the governing policy; never automatic `FAILED` |
| Backtest detects hindsight leakage | `COMPLETED` | `INVALID`; temporal leakage | `INVALIDATE / INVALID_TEMPORAL_LEAKAGE` |
| Research run is inconclusive | `COMPLETED` | `VALID`; inconclusive evidence | `NO_ACTION / INCONCLUSIVE` |
| AI investigation yields attributable structured output | `COMPLETED` | `VALID` for read-only research review, not factual or execution authority | `ACCEPT / ACCEPTED_FOR_REVIEW` |
| Benchmark is measured but baseline-incompatible | `COMPLETED` | `VALID`; comparability `NOT_COMPARABLE` | `NO_ACTION / VALID_RESULT_NOT_COMPARABLE` |
| Operator intentionally cancels | `CANCELLED`, actor/policy recorded | `NOT_EVALUATED` or clearly marked partial outcome | `CANCEL / OPERATOR_CANCELLED` |

## Consequence and recording profiles

Consequence profile is orthogonal to the existing HOT/WARM/COLD workload
classification. HOT/WARM/COLD describes latency/storage shape; consequence
describes the cost of losing or misattributing a record.

| Profile | Typical use | Minimum durability | Loss/sampling | Recording failure behavior | Retention baseline |
|---|---|---|---|---|---|
| `C0_EPHEMERAL` | Debug events, high-volume stage telemetry | Best effort, asynchronous | Sampling/drop permitted with loss counters | Continue degraded | Ephemeral/bounded |
| `C1_OPERATIONAL` | Routine jobs, local validation, health and provider diagnostics | Durable by run close; buffered/asynchronous permitted | Bounded declared loss only | Continue degraded or invalidate observability claims | Bounded operational |
| `C2_GOVERNED` | Material research, data transforms, provider smoke, model/AI work | Run/attempt/outcome/artifact refs durable before disposition | No silent loss of required records | Required-record loss invalidates the result or defers disposition | Reproducibility horizon |
| `C3_EVIDENCE_CRITICAL` | Qualification, release acceptance, model promotion evidence, accepted milestone evidence | Append-preserving record and artifact hashes durable before acceptance | Required records never sampled/dropped | Fail closed for acceptance; runtime may stop safely under its authority | Long-lived/historical |
| `C4_AUTHORITY_CRITICAL` | Future execution, risk/authority changes, settlement with side effects | Idempotent durable intent/audit boundary before effect; reconciliation required | Zero tolerance for authority-record loss | Fail closed where current authority requires; uncertain external effects trigger reconciliation, not blind retry | Authority-policy controlled |

A system MUST declare the profile and the required-record failure policy for
each operation class. A debug metric sink may fail without invalidating a C2
result when required evidence remains available. A failed research artifact
write invalidates or defers that research result. A C3 acceptance record cannot
be accepted without durable evidence. A C4 audit/persistence failure cannot be
silently downgraded to diagnostic loss.

Hot-path emission MAY use bounded in-memory buffers, batch/asynchronous flush,
sampling, aggregation, and compact envelopes. It MUST expose dropped/sample/
overflow counts and policy. Authority-critical records MUST travel through a
separate durability boundary when best-effort hot telemetry cannot satisfy
their contract.

## Reproducibility taxonomy

Every consequential run MUST claim one primary reproducibility class. The class
describes what can truthfully be repeated, not how desirable the operation is.

| Class | Claim |
|---|---|
| `R5_BIT_EXACT` | Same captured inputs, source, config, dependencies, environment, and declared hardware reproduce byte-identical declared outputs. |
| `R4_DETERMINISTIC_REPLAY` | Same inputs and semantic environment reproduce the same declared result/invariants; incidental bytes or timing may differ. |
| `R3_INPUT_REPLAYABLE` | Captured inputs can be replayed, but external timing or nondeterminism may change output. Actual output is retained. |
| `R2_ATTRIBUTABLE_NONDETERMINISTIC` | Inputs, source, config, model/tools, environment, and actual output are attributable, but replay is not guaranteed. |
| `R1_OBSERVATION_ONLY` | The operation truthfully records what was observed and when; sufficient inputs for replay were not captured. |
| `R0_NON_REPRODUCIBLE_DECLARED` | Required provenance is unavailable; the reason and consequence are explicit. C2+ results cannot be accepted unless a governing exception permits this class. |

Qualifiers MAY add `ENVIRONMENT_RECONSTRUCTABLE`, `OUTPUT_RETAINED`,
`EXTERNAL_TIMING_DEPENDENT`, `HARDWARE_SENSITIVE`, `LEGACY_PARTIAL`, or
`RETROSPECTIVE_INDEX`. Qualifiers MUST NOT silently promote the primary claim.

Examples:

| Operation | Expected truthful classification |
|---|---|
| Deterministic unit test | `R4_DETERMINISTIC_REPLAY`; `R5` only if byte identity is actually verified |
| Historical event replay | `R4` when inputs/order/timing policy and transformation are deterministic; otherwise `R3` |
| Live provider session | `R3` when raw received inputs are captured; otherwise `R1` |
| AI research run | `R2`, optionally `R3` when complete replayable inputs/tool outputs are retained |
| Performance benchmark | Usually `R2` with `HARDWARE_SENSITIVE`; never comparable solely because it reruns |
| GPU model training with nondeterministic kernels | `R2` with seed, environment, hardware, framework, inputs, and actual artifact retained |

## Attribution requirements

### Source and code identity

Consequential source attribution MUST include repository identity, commit SHA,
and source-state classification:

- `CLEAN_COMMITTED`: declared source is the committed tree;
- `DIRTY_ATTRIBUTABLE`: relevant modifications/untracked source are captured by
  a content-addressed source capsule or diff manifest;
- `UNATTRIBUTABLE`: relevant source cannot be reconstructed or explained.

Branch is useful context but not immutable identity. Dirty source is not
automatically invalid. C2 work MAY use `DIRTY_ATTRIBUTABLE`; C3/C4 acceptance
SHOULD require `CLEAN_COMMITTED` or an explicitly accepted immutable source
capsule. An unrelated dirty path need not invalidate a run when the source
scope and closure method prove it cannot affect execution.

Changed-path hashes alone are sufficient only when the operation records the
source closure method and proves the declared paths contain all relevant code,
configuration, generated modules, and untracked inputs. Otherwise capture the
full relevant patch/content manifest. Secret-bearing paths and secret values
MUST NOT enter a source capsule.

### Environment and dependency identity

Environment attribution is applicability-based. C2+ runs MUST record OS and
architecture, relevant runtime versions, dependency/lock identity, and active
feature/provider modes. Hardware, CPU/GPU class, container image digest,
drivers, thread/concurrency settings, locale/timezone, and installed dependency
manifest become mandatory when they can materially affect the result.

The environment record MUST distinguish declared configuration from observed
runtime facts. It MUST NOT capture arbitrary environment variables.

### Configuration identity

Semantically effective configuration MUST use a stable reference and/or hash of
canonicalized non-secret fields. It includes applicable policy IDs, provider
mode/config ref, feature flags, calendars, universe, thresholds by reference,
and retry/idempotency policy. A mutable config name without version/hash is not
sufficient for C2+ work.

Secret values MUST be omitted, not copied or hashed. Record a non-sensitive
credential-provider class/reference or key-version identifier only when needed
to explain capability/entitlement. Hashing a low-entropy secret can itself leak
information and is prohibited.

### Data identity

Consequential input data MUST be identified by dataset/snapshot/source manifest
and content hashes where available, source/provider, time coverage,
availability/evaluation cutoff, revision/vintage, admission/quality policy, and
transformation lineage. A filename alone is insufficient.

Live input capture MUST state completeness, loss/overflow, capture window, raw
versus normalized role, ordering, provider/source time, local receive time, and
whether the capture is admitted or only observed. Captured-but-not-admitted data
MUST remain labeled as such.

### Model, predictor, feature, calibration, prompt, and policy identity

Runs MUST reference the identities applicable to their result: model or
candidate, artifact hash, model/provider version where exposed, predictor,
feature schema, calibration, strategy, prompt/template, evaluation policy, and
authority mode. Existing canonical IDs remain authoritative. REBASE-02 creates
no model, data, prompt, or policy registry.

When a provider does not expose an exact model build, record the exposed model
alias plus provider, request time, parameters, and the limitation. Do not invent
a version.

### Temporal cutoff

Every hindsight-sensitive run MUST declare the decision/evaluation cutoff and
the applicable event, publication, provider, receipt, availability, ingest,
revision, training, holdout, settlement, or observation cutoffs. It MUST use the
existing temporal authority for domain interpretation and MUST enforce
`available_time_ns <= decision_time_ns` wherever information is selected for a
decision.

Not every timestamp belongs on every run. The run records a named cutoff bundle
and links domain records that carry detailed clocks. Unknown or approximate
clocks remain explicit with source precision/confidence.

## Artifact standard

An artifact is attributable only when the record includes:

- stable artifact reference;
- producer run and, when relevant, producer attempt;
- semantic role (`INPUT`, `OUTPUT`, `LOG`, `EVIDENCE`, `CHECKPOINT`,
  `REPORT`, `MODEL`, `DATASET`, or domain extension);
- storage path/URI as a locator, not identity;
- SHA-256 for immutable byte content, or a declared hash/checkpoint strategy for
  append-only content;
- byte size and media/content type where available;
- creation/observation time;
- completeness and acceptance state;
- mutability and retention classes;
- redaction/sensitivity classification.

### Artifact mutability

| Class | Rule |
|---|---|
| `IMMUTABLE_EVIDENCE` | Bytes/hash are frozen; replacement creates a new artifact. |
| `APPEND_ONLY_JOURNAL` | Entries are append-preserving; checkpoints/ranges receive hashes. |
| `REGENERABLE_OUTPUT` | Generator and complete source inputs are identified; output is not independently editable authority. |
| `MUTABLE_STATUS` | Current projection may change; historical accepted versions remain recoverable through Git or the owning store. |
| `EPHEMERAL_SCRATCH` | Not acceptance evidence; deletion is expected. |
| `CACHE` | Reconstructable and never an authority. |

Logical append behavior implemented by rewriting an aggregate file MUST be
labeled `MUTABLE_STATUS` or `REGENERABLE_OUTPUT`, not physical
`APPEND_ONLY_JOURNAL`, unless the storage implementation proves append-only
durability.

Two persistence semantics MUST remain distinct:

| Term | Meaning |
|---|---|
| `LOGICAL_APPEND_ONLY` | Prior records remain represented and recoverable through the owning contract; consumers can reconstruct history without overwriting earlier facts. |
| `PHYSICAL_APPEND_ONLY` | Storage only appends bytes; prior file content is never rewritten in place. |

A store may be logically append-only without being physically append-only.
Labeling MUST reflect the weaker durable guarantee actually provided.

### Logical vs physical append-only example

EVIDENCE campaign storage in
`src/market_platform_foundation/intelligence/forward_qualification/evidence01a/store.py`
and `evidence01b/store.py` demonstrates both semantics in one subsystem:

| Artifact | Persistence semantics | Mutability class | Why |
|---|---|---|---|
| `OBSERVATIONS.jsonl`, `intelligence_records.jsonl`, `OPERATIONAL_EVENTS.jsonl` | `PHYSICAL_APPEND_ONLY` | `APPEND_ONLY_JOURNAL` | Each record is appended with flush/fsync; prior lines are never rewritten. |
| `CAMPAIGN_RUNTIME_STATE.json`, `CAMPAIGN_METRICS.json`, `RUNTIME_HEARTBEAT.json` | `LOGICAL_APPEND_ONLY` via aggregate rewrite | `MUTABLE_STATUS` | The file is atomically replaced with a current projection; logical history remains in the JSONL journals and immutable per-id session/checkpoint files. |
| `sessions/SESSION_*.json`, `checkpoints/CHECKPOINT_*.json` | Write-once immutable artifacts | `IMMUTABLE_EVIDENCE` | Identity-addressed records are not updated after creation. |

`tools/validate.py` shows the same split for validation: `write_json_atomic()`
replaces a summary report under `reports/`, while sibling assertion bundles
preserve per-run detail. The assistant audit store
(`src/market_platform_foundation/assistant/audit_store.py`) grows
`conversations.json` and `messages.json` by rewriting whole arrays; that is
logically append-preserving but neither physically append-only nor atomically
replaced and MUST NOT be described as `PHYSICAL_APPEND_ONLY`.

OF-01 MUST NOT assume every IMP “append-only” store is physically append-only
merely because logical history can be reconstructed elsewhere.

### Storage roles

The standard distinguishes Git-committed canonical/evidence content, runtime
durable storage, warm operational storage, cold archive, and local temporary
scratch. It does not select a database or object store. Git MUST NOT become the
Universal Run Ledger.

### Retention classes

Exact durations remain policy-defined. The common classes are:

| Class | Meaning |
|---|---|
| `RET_EPHEMERAL` | Discardable scratch/cache after the local need ends. |
| `RET_BOUNDED_DIAGNOSTIC` | Time/volume-bounded diagnostics and high-volume telemetry. |
| `RET_OPERATIONAL` | Retained through the operational investigation/recovery horizon. |
| `RET_REPRODUCIBILITY` | Retained long enough to reproduce, review, or compare the result. |
| `RET_HISTORICAL_EVIDENCE` | Long-lived accepted evidence and negative-result history. |
| `RET_AUTHORITY_POLICY` | Retention governed by the owning authority, safety, or external policy. |

Prediction, settlement, qualification, model promotion, release acceptance,
and future execution/risk authority records normally require the strongest
owning policy. REBASE-02 does not invent legal durations.

### Redaction and secrets

Logs, traces, artifacts, prompts, source capsules, and environment records MUST
NOT persist API keys, passwords, bearer/session tokens, cookies, private keys,
raw credentials, recovery codes, or secret environment values. Sensitive
broker account identifiers and personal information MUST be minimized,
pseudonymized, redacted, or omitted under the owning policy.

Redaction MUST occur before durable emission. A later scrub is not sufficient
for C2+. Records MAY state `credential_provider`, `credential_class`, or a
non-sensitive key/version reference. Error details MUST use stable codes and
bounded sanitized context. Secret scanning is defense in depth, not permission
to persist first and clean later.

## Observability standard

### Record-kind separation

| Kind | Purpose | Canonical evidence by default? |
|---|---|---|
| Diagnostic log | Explain runtime behavior to operators/developers | No |
| Audit record | Record a governed actor/decision/state transition | Only within its owning contract |
| Domain event | Represent market/business/system fact | Only within its domain authority |
| Evidence artifact | Support an accepted claim at a cutoff | Yes for its declared scope |
| Metric | Aggregate measurements over a population/window | No; may support evidence when protocol-bound |
| Trace span | Causal timing/processing segment | No; may support benchmark/incident evidence when retained |
| Health state | Mutable assessment/projection at an as-of time | No unless snapshotted as evidence |
| Test result | Structured validation outcome | Yes only when bound to source/run/acceptance protocol |

A debug log MUST NOT silently become acceptance evidence. An evidence decision
MUST NOT depend solely on unstructured logs.

### Structured logs

Material structured logs SHOULD carry UTC wall timestamp, severity, component,
event type/code, message template or safe message, run/attempt refs when
applicable, trace/correlation/span refs when applicable, source/provider, state
transition, safe error code, artifact refs, and structured attributes.

Serialization is not frozen. JSONL is a strong current pattern but is not
mandated where another format preserves the semantics. Log events MUST declare
schema/version when they are durable or consumed across component boundaries.

### Metrics

Every metric definition MUST include name, kind (counter, gauge, histogram/
distribution), unit, population, aggregation/window, labels with bounded
cardinality, sampling policy, and clock source. Duration/latency metrics MUST
state start/end stage semantics and whether they measure provider-to-receipt,
queue wait, processing, end-to-end age, or another interval.

Quantiles MUST state the population/window and calculation method. Means or
percentiles without sample count are insufficient for C2 benchmark evidence.
Dropped metric events, queue overflows, telemetry backpressure, and context loss
MUST themselves be observable.

### Trace and correlation

- `trace_id` identifies one causal processing path.
- `span_id` identifies a timed/staged unit within a trace and carries parent
  context where known.
- `correlation_id` groups related records without asserting a strict span tree.
- `event_id` identifies a discrete event/domain record.
- `run_id` identifies the consequential logical objective.

Trace/correlation context SHOULD survive process, thread, task, queue, and
service boundaries. A receiving stage MUST detect and record missing/invalid
context rather than silently inventing causal parentage. Locally generated new
trace roots are permitted when context is absent but MUST declare the break.

The future provider-to-opportunity path can correlate provider event,
normalization, feature, model, opportunity, risk, order, broker, and
reconciliation stages without creating a run per stage. Exact domain lineage
references remain separate from telemetry trace identity.

### Clocks

Observability uses three clock roles:

1. UTC wall time for cross-record placement and persisted timestamps;
2. monotonic elapsed-time clocks for durations, deadlines, and stage latency;
3. provider/domain clocks for event/publication/exchange/source time.

Duration MUST NOT be computed from a wall clock when a monotonic clock is
available. Cross-process comparisons MUST record host/process clock context and
known drift/uncertainty. Timestamp timezone is UTC; precision and source are
declared. The existing IMP temporal model remains authoritative for knowledge
eligibility.

### Latency stages

RT-01 MUST define and measure only applicable named stages from provider/source,
transport/network, adapter/callback, queue wait, normalization, state update,
feature, model, opportunity, risk, persistence, publish/UI, human decision,
order construction, broker request/ack/fill, and reconciliation. Stage names
MUST have exact boundaries and units. “Provider latency” MUST NOT be used for
event-to-local-receipt lag unless provider/network components are actually
separable.

## Evaluation standards

### Common evaluation declaration

Every C2+ evaluation MUST declare evaluation kind, subject/candidate, baseline
or reason none exists, protocol/policy ref, data/input scope, temporal cutoff,
metrics and units, success/rejection/invalidation criteria, environment,
attempts, result validity, limitations, and disposition. Evaluation category
MUST be explicit and MUST NOT masquerade as a stronger category.

### Test and validation runs

Material validation records MUST include suite/manifest identity, selection
mode and reasons, source identity, exact invocation, start/end, environment,
worker/concurrency configuration, attempts, selected/collected/pass/fail/skip/
error counts, failed/error/skip IDs and reasons, artifacts, interruption/not-run
state, `full_suite_required`, and final disposition.

`PASS_WITH_RETRY` is valid only when the final criteria pass and at least one
prior attempt did not. The record MUST retain every attempt and MUST NOT label
the cause flaky without evidence. Test assertion failures, infrastructure
failure, environment failure, timeout, interruption, validator failure, and
unclassified failure remain distinct.

A skipped test is neither passed nor failed. Acceptance must state whether the
skip is expected, permitted, or blocking. CHANGED passing with
`full_suite_required=true` remains preliminary until FULL passes.

### Performance benchmarks

A material benchmark record MUST include benchmark/workload identity, source,
configuration, fixture/input/data identity, environment and hardware,
warmup, sample count, iterations, concurrency/load, measurement window, clock,
raw/aggregated samples, p50/p95/p99 where meaningful, throughput/resource
measures where meaningful, baseline ref, result validity, and disposition.

The current `tools/benchmark.py` output is a reusable informational starting
point. It records platform, Python version, CPU count, configuration, fixed
fixture refs, samples, medians/means/min/max, return codes, and production
operation timings. It does not yet establish accepted environment identity,
p95/p99 for relevant workloads, resource use, baseline compatibility, or a
gating budget.

Comparability is a separate result:

| Value | Meaning |
|---|---|
| `COMPARABLE` | All declared material dimensions match or are normalized by the protocol. |
| `CONDITIONALLY_COMPARABLE` | Known differences exist; the protocol defines the limited comparison that remains valid. |
| `NOT_COMPARABLE` | A material environment, source, workload, data, config, provider, load, or measurement difference prevents direct comparison. |

A valid measurement can be `NOT_COMPARABLE`. REBASE-02 sets no performance
budget. RT-01 measures a baseline before RT-02 optimization.

### Backtest

A backtest evaluates a strategy/model against historical data and execution
assumptions. It MUST record strategy/model/policy identity, source, data
snapshot, universe/time range, availability/lookahead rules, fees/slippage,
execution/fill assumptions, corporate actions/revisions as applicable,
randomness, metrics, baseline, artifacts, and temporal validation.

Detected lookahead, contamination, or unavailable-at-decision data invalidates
the result even when the process completes.

### Replay

A replay reprocesses recorded inputs. It MUST record capture identity and
completeness, event ordering, deduplication/revision rules, cutoff, expected
invariants/outputs, and timing mode: `REAL_TIME_PRESERVED`, `ACCELERATED`, or
`LOGICAL_ORDER_ONLY`. Replay is not automatically a backtest and does not
convert recorded observations into live evidence.

### Simulation

A simulation models behavior or a scenario. It MUST label input origin as
synthetic, historical-derived, counterfactual, or paper/sandbox and state the
model/assumptions. Synthetic, counterfactual, paper, fixture, and real-provider
observations MUST remain distinguishable. Paper execution does not create live
broker reality.

### Provider smoke

Provider smoke records MUST include provider, capability/endpoint class,
environment, connection mode, entitlement/capability state, symbol/universe,
market session/calendar, observation time, quality, attempts, sanitized
request/response evidence or shape, limitations, and outcome/disposition.

Origin MUST be one of `REAL_PROVIDER_OBSERVED`, `SANDBOX_OR_PAPER`, `MOCK`,
`FIXTURE`, or `REPLAY`. A real-provider attempt blocked by market closure,
missing entitlement, configuration, or credentials is not a passing mock and
must not be silently retried as another origin.

### Model training

Consequential training MUST record experiment/hypothesis, model family,
candidate spec, source, dataset/feature fingerprints, training cutoff,
hyperparameters, seed, trainer/framework/environment/hardware, nondeterminism
settings, attempts, diagnostics, output artifact/hash, and validation links.
The result remains an unvalidated candidate unless the owning promotion and
validation authorities say otherwise.

### Model evaluation and promotion evidence

Evaluation category MUST be one of the owning domain's explicit forms, at least
distinguishing in-sample, walk-forward, locked holdout, historical backtest,
replay, paper, shadow, forward, and live canary. Results from one category MUST
NOT be relabeled as another.

Promotion evidence SHOULD reference candidate/model and baseline identities,
evaluation runs, data/cutoffs, limitations, approval authority, effective time,
and rollback/revocation plan. REBASE-02 does not authorize promotion or change
current promotion policy.

### Experiment and negative results

An experiment is a governed research object that may own several runs. It MUST
state question, hypothesis, baseline/control, treatment, allowed/forbidden
changes, data/time scope, metrics, guardrails, falsification, success/rejection
criteria, resource/seed policy, runs, interpretation, decision, and follow-up.

Valid negative and inconclusive results MUST remain discoverable. A technically
completed experiment whose feature degrades performance is `VALID` and can be
`REJECT / VALID_RESULT_REJECTED`; it is not rewritten as execution failure.

### Research

Consequential research MUST record question, initiator, source references and
availability/cutoff, epistemic roles, tools, models when AI-assisted, claims,
contradictions/limitations, structured conclusion, output artifact, and review
state. Hidden reasoning or chain-of-thought is neither required nor retained.
Store source-grounded inputs, declared method, structured rationale, evidence,
and conclusions sufficient for review.

### AI operations

Consequential AI operations MUST record run/attempt, provider/model and exposed
version, prompt/template/version reference, inference parameters, tool/
capability references, source/evidence-pack refs and hashes, input cutoff,
sanitized tool inputs/outputs or hashes, actual structured output artifact,
citations, token/resource accounting where available, request/response refs
where exposed, authority mode, and evaluation/review disposition.

AI reproducibility is normally `R2_ATTRIBUTABLE_NONDETERMINISTIC` and MAY be
`R3_INPUT_REPLAYABLE`; it MUST NOT promise identical output. Chain-of-thought
MUST NOT be stored. Authority mode MUST be explicit, using read-only meanings
such as `RESEARCH_ONLY`, `ADVISORY`, `STRUCTURED_ANALYSIS`, or
`WORKFLOW_ORCHESTRATION`. None grants risk, release, session, order, broker,
reconciliation, provider-admission, prediction, settlement, or qualification
authority.

## Operational semantics

### Failure and interruption taxonomy

The common reason families are `DOMAIN_FAILURE`, `TEST_FAILURE`,
`INFRASTRUCTURE_FAILURE`, `ENVIRONMENT_FAILURE`, `PROVIDER_FAILURE`,
`PERSISTENCE_FAILURE`, `DATA_QUALITY_FAILURE`, `MODEL_FAILURE`,
`TEMPORAL_INTEGRITY_FAILURE`, `TIMEOUT`, `PROCESS_CRASH`, `NETWORK_INTERRUPTION`,
`OPERATOR_CANCEL`, `POLICY_CANCEL`, and `UNCLASSIFIED_FAILURE`.

Reason family does not replace domain detail. A provider disconnect can yield
technical `INTERRUPTED`, a partial live-observation outcome, and a policy-driven
`DEFER`, `RETRY`, or `INVALIDATE` disposition. Unknown cause stays
`UNCLASSIFIED_FAILURE`.

Cancellation by a human, policy, scheduler, or superseding run MUST identify
the actor class/cause. Abandonment is an explicit terminal decision after work
is no longer pursued; it is not inferred from silence. Lost runs are detected
by reconciliation/heartbeat policy and never rewritten as ordinary failure.

### Idempotency and retryability

Every consequential side-effecting operation MUST declare one idempotency
class:

- `IDEMPOTENT`;
- `IDEMPOTENT_WITH_KEY`;
- `CONDITIONALLY_IDEMPOTENT` with stated preconditions;
- `NON_IDEMPOTENT`.

It MUST also declare retryable conditions, permanent-failure conditions,
maximum-attempt/backoff policy reference, and reconciliation requirement.
There is no global retry count. Settlement, checkpoints, promotion, workflow
actions, and future execution require their owning idempotency authorities.
Uncertain external side effects MUST reconcile before retry; blind resubmission
is prohibited.

### Partial artifacts

Artifacts from failed, interrupted, timed-out, cancelled, or lost attempts MAY
be retained for diagnosis or recovery. They MUST carry producer attempt,
terminal execution state, completeness (`PARTIAL`, `COMPLETE`, or `UNKNOWN`),
validation state, and use restriction. A partial artifact MUST NOT satisfy an
accepted-output requirement unless a separate review explicitly validates and
accepts it for a narrowed role.

Temporary writes SHOULD use atomic publication so incomplete bytes do not
masquerade as complete content. Checkpoint and journal formats MAY retain valid
prefixes while marking the unclosed tail.

### Incident, defect, debt, limitation, and corrective action links

A run MAY link typed references to an incident, defect, technical-debt item,
known limitation, corrective action, or resolution evidence. Each link MUST
state relation (`DETECTED`, `CAUSED_BY`, `AFFECTED_BY`, `MITIGATES`, `RESOLVES`,
or `VERIFIES_RESOLUTION`) and time. REBASE-02 does not require one physical
registry. OF-03 owns future indexing and lifecycle consolidation.

## Documentation and acceptance standard

### Change-to-acceptance flow

```text
change intent
  -> consequence and affected-authority classification
  -> applicable validation/evaluation
  -> preserved attempt records and artifacts
  -> documentation impact review
  -> evidence package proportional to consequence
  -> governed disposition/acceptance
```

Documentation-only changes do not require a BUILD-sized package by default.
Acceptance depth is proportional to changed runtime behavior, security,
authority, evidence, schema, provider boundary, performance claim, historical
surface, and canonical-document impact.

Material milestone acceptance SHOULD include base and final candidate identity,
scope, exact changed paths, validation run/attempt refs and results, hash
manifest for the accepted surface, known limitations, documentation impact,
protected-history result where relevant, and Git disposition. C3/C4 changes
require immutable or append-preserving evidence before acceptance.

`full_suite_required` remains a governing validation signal. Documentation-only
CHANGED validation may be sufficient when no other authority or acceptance
contract requires more. A performance claim requires benchmark evidence;
historical protection requires exact diff/path evidence; provider changes may
require the applicable offline and live smoke boundaries.

### Documentation validation

Future automation SHOULD detect broken local links/fragments, invalid authority
references, missing canonical metadata, inconsistent supersession, stale
commands, generated-view drift, glossary conflicts, and canonical/executable
contradictions. A broken critical link to a controlling authority blocks
acceptance. REBASE-02 defines the requirement but implements no automation.

### Canonical, generated, status, and historical documents

Generated documents MUST identify source authority, generation mechanism,
generator version, input refs/hashes, and generated-at time when temporally
material. They remain generated views and MUST NOT become independently edited
canonical authority.

`docs/platform/PROGRAM_STATUS.md` is intentionally mutable canonical current
truth. It is not an immutable evidence artifact; accepted historical versions
remain recoverable through Git. It MUST NOT be bound into permanent policy
semantics as though current status could never change.

Historical BUILD, Phase, closure, EVIDENCE, and prior validation artifacts
remain authoritative at their own cutoffs. New standards apply prospectively.

## Applicability matrix

Legend: `M` = mandatory; `C` = mandatory when applicable/material; `R` =
reference existing domain authority rather than duplicate it; `—` = normally
not required. `Src` includes dirty-state attribution. `Obs` means required
structured logs/metrics/trace according to the profile, not every telemetry
kind.

| Operation | Profile | Run / attempts | Src | Config | Data | Model/policy | Time cutoff | Env | Obs | Durable artifacts | Baseline reproducibility |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Unit/integration validation | C1; C2 when acceptance-bound | M | M | C | C | C | C | M | C | M report | `R4` |
| Full validation | C2/C3 | M | M | M | C | C | C | M | M | M report/log refs | `R4` |
| Provider smoke | C2 | M | M | M | C | M | M | M | M | M redacted report | `R1` or `R3` |
| Data ingest | C2; C3 when admitted evidence | M | M | M | M source manifest | R admission/quality | M | M | M | M raw/normalized manifests | `R3`/`R4` |
| Data transform | C2 | M | M | M | M | C | M | M | C | M outputs/lineage | `R4` preferred |
| Model training | C2 | M | M | M | M | M | M | M incl. hardware | M | M candidate/diagnostics | `R2` or `R4` |
| Model inference | C0 span for hot path; C2 when consequential | C | C | C | M input ref | M | M | C | C/M | M actual output when C2 | `R2`/`R3` |
| Backtest | C2 | M | M | M | M | M | M | M | M | M report/equity/diagnostics | `R4` preferred |
| Replay | C1/C2 | M | M | M | M capture | C | M | M | M | M replay report | `R3`/`R4` |
| Simulation/paper | C2 | M | M | M | M origin | M assumptions | M | M | M | M ledger/report | `R2`/`R4` |
| Performance benchmark | C2 | M | M | M | M workload | C | C | M hardware/load | M | M samples/report | `R2` |
| Research | C2 | M | M | M | M sources | C | M | C | C | M conclusion/evidence | `R2`-`R4` |
| AI research | C2 | M | M | M | M evidence pack | M model/prompt/tools | M | M | M | M prompt/output/citations | `R2`/`R3` |
| EVIDENCE campaign | Existing C3 authority | R existing IDs/records | R | R | R | R | R | R | R | R frozen records | Existing contract; future indexing only |
| Release acceptance | C3 | M | M clean/capsule | M | C | M policy/evidence | M | M | M | M accepted bundle/hashes | `R4` where applicable |
| Future execution-critical action | C4 | M before effect | M | M | M state/input | M risk/authority | M | M | M plus reconciliation | M intent/audit/response | `R1`/`R3`; attribution mandatory |

The matrix does not force irrelevant fields. A row may strengthen under its
own authority; it may not weaken temporal integrity, evidence origin, safety,
or consequence requirements.

## Consequence matrix

The applicability matrix selects *what* must be attributed. The consequence
matrix selects *how strongly* each profile must be recorded, retained, and
protected. Profiles are orthogonal to HOT/WARM/COLD workload shape.

| Dimension | `C0_EPHEMERAL` | `C1_OPERATIONAL` | `C2_GOVERNED` | `C3_EVIDENCE_CRITICAL` | `C4_AUTHORITY_CRITICAL` |
|---|---|---|---|---|---|
| Durability | Best effort | Durable by run close | Required records durable before disposition | Append-preserving evidence durable before acceptance | Idempotent durable intent/audit before side effect |
| Recording timing | Async/batched; sampling allowed | Buffered/async permitted with bounded loss | Required run/attempt/artifact refs before disposition | Required evidence before acceptance | Synchronous or equivalent pre-effect boundary |
| Loss tolerance | High; explicit counters required | Bounded declared loss only | No silent loss of required records | Required records never sampled/dropped | Zero tolerance for authority-record loss |
| Retention baseline | `RET_EPHEMERAL` / `RET_BOUNDED_DIAGNOSTIC` | `RET_BOUNDED_DIAGNOSTIC` / `RET_OPERATIONAL` | `RET_REPRODUCIBILITY` | `RET_HISTORICAL_EVIDENCE` | `RET_AUTHORITY_POLICY` |
| Redaction strength | Secrets never persisted; minimal fields | Secrets never persisted; bounded diagnostic context | Full secret omission plus sensitive-field policy | Evidence-grade redaction before durable write | Authority-grade redaction; credential refs only when needed |
| Audit strength | Diagnostic only | Operational attribution | Governed review/reproducibility | Acceptance evidence | Authority/execution audit and reconciliation |

Representative operation-class expectations:

| Operation class | Profile | Recording failure default | Hot-path note |
|---|---|---|---|
| Hot model inference span | `C0` | Continue degraded | Trace/metric emission MAY be sampled and asynchronous |
| Changed/local validation | `C1` | Continue degraded or invalidate observability claims | Report replacement is acceptable; attempt history SHOULD be preserved when material |
| Provider smoke / research / benchmark | `C2` | Invalidate or defer result if required artifact missing | Structured report durable before disposition |
| Release / promotion / qualification evidence | `C3` | Fail closed for acceptance | No acceptance without durable hashes/records |
| Future execution / risk side effect | `C4` | Fail closed; reconcile uncertain external effects | Telemetry delay permitted only outside authority boundary |

## Proposed canonical standards structure

Implementation after written-spec approval should create exactly these three
new canonical standards:

| File | Subject | Why separate | Overlap avoided |
|---|---|---|---|
| `docs/platform/REPRODUCIBILITY_AND_RUN_STANDARD.md` | Consequential operation, run/attempt/execution/outcome/disposition, relationships, source/config/data/model/environment/time identity, artifacts, retention/redaction, failure/retry/resume/checkpoint/partial-output semantics | Identity and operational lifecycle form one indivisible contract | Does not define log/metric/trace envelopes or evaluation protocols |
| `docs/platform/OBSERVABILITY_STANDARD.md` | Consequence-aware logging, audit/domain/evidence distinctions, metrics, trace/correlation, clocks, latency stages, context propagation, loss/degraded/fail-closed recording behavior | Hot-path and cross-process concerns require an independently reviewable contract | References run IDs/profiles but does not own run lifecycle or evaluation criteria |
| `docs/platform/TEST_AND_EVALUATION_STANDARD.md` | Tests/validation, benchmarks/comparability, replay/simulation/backtest, provider smoke, models, experiments, research, AI evaluation, negative results | Evaluation validity and comparability share one method across domains | References provenance/observability requirements but does not redefine them |

No separate operational standard is created; retry, idempotency, resume,
checkpoint, cancellation, partial output, and incident links belong with run
lifecycle and provenance.

### Narrow existing-document updates during standards implementation

The implementation specification should permit only evidence-backed, narrow
updates:

- `docs/platform/README.md`: add the three standard navigation entries;
- `MASTER_ARCHITECTURE.md`: replace the “REBASE-02 next” statement with the
  accepted standards and retain Operating Fabric `PARTIAL` until OF-01;
- `PROGRAM_STATUS.md`: mark REBASE-02 complete only after canonical standards
  implementation is validated/accepted; do not mark OF/RT capabilities
  implemented;
- `MASTER_ROADMAP.md`: advance ownership from REBASE-02 to OF-01/parallel-safe
  RT-01/XA-01 work without changing EVIDENCE independence;
- `CANONICAL_TRUTH_MAP.md`: route the three new subjects to their standards and
  keep executable/domain authorities controlling their current scopes;
- `DOCUMENTATION_STANDARD.md`: reference consequence-based acceptance,
  generated-document provenance, and future drift checks without duplicating
  the run/evaluation standards;
- `GLOSSARY.md`: add controlled run, attempt, technical execution, outcome,
  disposition, trace, correlation, consequence profile, reproducibility, and
  artifact terms.

`SYSTEM_BOUNDARIES.md`, `AUTHORITY_MODEL.md`, and
`DATA_AND_EPISTEMIC_MODEL.md` require no semantic redesign. They MAY receive a
link only if written-spec review proves navigation otherwise breaks. The final
implementation specification must enumerate the exact allowed path set.

## Current implementation, standard, and downstream contract

| Layer | Meaning in this design |
|---|---|
| Current implementation | Existing validation, EVIDENCE, run manifests, ledgers, models, data, research, provider, assistant, telemetry, and artifact patterns. They remain subsystem-specific. |
| REBASE-02 standard | The required cross-platform semantics described here and later accepted in canonical prose. It creates no runtime. |
| Downstream implementation contract | OF/RT/XA/AI milestones build durable storage, adapters, instrumentation, or domain capabilities using the accepted semantics. |

No future standard may be presented as current executable truth before its
owning implementation is accepted.

## Downstream milestone contracts

### IMP-OF-01 — Append-Only Run and Artifact Ledger

Implement durable run identity, attempt history, technical results, typed
outcomes/dispositions, relationships, initiator/trigger attribution, source/
config/data/model/environment refs, artifact association, checkpoint links,
provenance completeness, and consequence-aware durability. Preserve history;
do not overwrite earlier attempts or domain records. Physical schemas/names
remain an OF-01 decision constrained by lossless mapping to the standards.

### IMP-OF-02 — Operation Adapters

Adapt validation first, then bounded provider-smoke, research, model/data, and
EVIDENCE references as justified. Adapters index existing immutable or
subsystem records and preserve domain identity. They MUST NOT rewrite frozen
history or fabricate missing original metadata.

### IMP-RT-01 — End-to-End Instrumentation

Implement trace/correlation propagation, stage definitions, context-loss
detection, clock/latency attribution, loss counters, and an accepted comparable
benchmark baseline. It may prepare contracts in parallel after REBASE-02 but
runtime stages later attach to OF-01 durable identity. Measure before RT-02
optimization.

### IMP-XA-01 — Cross-Asset Kernel

Use the provenance, temporal cutoff, evaluation, provider-origin, and
documentation standards when defining extension/source contracts. XA-01 may
prepare contracts after REBASE-02; first admitted runtime/source runs integrate
with OF-01 through later milestones. It creates no EVIDENCE dependency.

### IMP-OF-03 — Workflow and Control Registry

Index workflow definitions, SOPs, capabilities, incidents, problems, defects,
debt, limitations, and corrective actions using typed run links. Per operation
class, an OF-02 adapter remains a prerequisite to accepted registry entry. One
physical database is not required.

### IMP-AI-01 — Attributable Read-Only AI Research

Depend on OF-01 durable attribution. Implement source-aware, prompt/tool/model/
evidence/output attributable research and evaluation under read-only/no-
execution authority. It MUST NOT grant trading, risk, provider admission,
prediction, settlement, qualification, release, or canonical-state mutation
authority.

## EVIDENCE isolation

EVIDENCE-01C remains semantically independent from REBASE-02, OF-01, OF-02,
RT-01, XA-01, OF-03, AI-01, and Narrative work. REBASE-02 introduces no hard or
soft dependency and changes no EVIDENCE policy, threshold, campaign state,
origin, session, checkpoint, continuity, prediction, settlement, qualification,
or provider-admission behavior.

Future OF-02 adapters MAY reference frozen EVIDENCE campaign/session/
checkpoint/observation/configuration/assessment records. They MUST NOT rewrite
them, change their hashes, or imply that future universal metadata existed at
record creation.

## Historical compatibility and migration

Historical records remain valid within the evidence they actually captured.
Missing future fields do not retroactively invalidate BUILD, Phase, closure,
EVIDENCE, provider, model, or validation history.

Future adapters use:

- `LEGACY_PARTIAL` when original provenance is incomplete under the new
  standard;
- `RETROSPECTIVE_INDEX` when a new index identity is assigned after the fact;
- explicit unknown/null fields with source evidence for every derived value.

They MAY derive metadata that is mechanically provable from frozen bytes/Git
history and record the derivation method. They MUST NOT invent an original
run ID, environment, actor, attempt count, command, or cutoff; present a
retrospective index as an original identity; alter frozen hashes; or rewrite
the original artifact.

## Validation plan for the design and later implementation

### This design task

Before committing this design:

1. verify every referenced repository path;
2. check terminology against `GLOSSARY.md`, `AUTHORITY_MODEL.md`, and
   `DOCUMENTATION_STANDARD.md`;
3. search for placeholders, schema-name freezing, false implementation claims,
   EVIDENCE dependencies, and authority expansion;
4. verify every acceptance criterion below is explicitly covered;
5. run `git diff --check`;
6. run manifest-driven CHANGED validation and inspect
   `full_suite_required`;
7. stage only this specification, inspect the full staged diff and
   `git diff --cached --check`, then commit one documentation-only change;
8. verify post-commit parent, subject, exact path list, and cleanliness.

No full runtime or live-provider suite is required unless the validation
manifest says otherwise. The design does not add acceptance artifacts or alter
canonical status.

### Later canonical-standards implementation

The implementation specification must require exact-path/link checks,
canonical metadata and terminology checks, protected-history checks, JSON/hash
checks for any acceptance package, CHANGED validation, FULL only when requested
by policy, staged-diff review, and post-commit verification. Failed validation
attempts and later retries remain separate evidence rows.

## Git and worktree strategy

This design is isolated on `docs/imp-rebase-02-design` from accepted parent
`9c7ea456...`. It stages and commits only this specification. It does not push
or merge.

Written-spec review occurs after this commit. Canonical standards
implementation must use a new clean implementation worktree from the accepted
written-spec review commit. It must not implement directly from this first
draft, reuse the dirty original checkout, or mix EVIDENCE/runtime work.

## Acceptance criteria

The design is ready for written-spec review only when all are true:

1. Existing reusable validation, EVIDENCE, artifact, model, data, logging,
   temporal, research, AI, provider, and benchmark foundations are mapped.
2. A run is one consequential logical objective, not a process/event/span.
3. Attempt and retry semantics preserve every technical execution.
4. Technical execution, outcome validity/result, and disposition are distinct.
5. Failure, interruption, timeout, cancellation, loss, abandonment, and
   supersession remain distinguishable.
6. Parent/root, trigger, resume, supersession, and related-run semantics are
   typed.
7. Initiator class and trigger context are defined without unnecessary personal
   data.
8. Consequence profiles are orthogonal to HOT/WARM/COLD and protect hot paths.
9. Required-record loss, continue-degraded, invalidate-result, and fail-closed
   behavior are explicit by profile.
10. Reproducibility classes cover bit-exact, deterministic replay, captured
    input replay, nondeterministic attribution, observation-only, and declared
    non-reproducibility.
11. Source SHA, dirty-state, environment, dependency, config, data, model,
    policy, prompt/tool, and temporal attribution are applicability-based and
    explicit.
12. Dirty attributable source is practical but cannot silently support a clean
    source claim.
13. The existing availability/decision-time law remains universal where
    hindsight matters.
14. Artifact identity does not rely on path and distinguishes mutability,
    completeness, storage, and retention.
15. Secrets are omitted/redacted before persistence and never retained for
    reproducibility.
16. Logs, audit records, domain events, evidence, metrics, traces, health, and
    test results remain distinct.
17. Trace, span, correlation, event, run, and workflow identities are not
    interchangeable.
18. Clock and latency standards distinguish wall, monotonic elapsed, and
    provider/domain time.
19. Benchmark comparability is tri-state and a valid result can be non-
    comparable.
20. Test retries preserve prior failures and do not infer flakiness.
21. Backtest, replay, simulation, paper, shadow, forward, and live/provider
    categories cannot masquerade as one another.
22. Provider smoke distinguishes real provider, sandbox/paper, mock, fixture,
    and replay origins.
23. Model training/evaluation/promotion evidence is attributable without
    creating a registry or promotion authority.
24. Experiments preserve valid negative and inconclusive results.
25. Research/AI attribution requires reviewable inputs/evidence/output but not
    chain-of-thought or deterministic AI output.
26. Idempotency, retryability, reconciliation, resume, checkpoint, and partial
    artifacts are explicit.
27. Incident/problem/debt/limitation linking is typed without requiring one
    registry.
28. Documentation/evidence workflow, generated/current-status behavior, and
    consequence-based acceptance depth are defined.
29. Historical compatibility and retrospective indexing prohibit fabricated
    provenance.
30. EVIDENCE-01C remains independent and no runtime system is implemented.
31. OF-01, OF-02, RT-01, XA-01, OF-03, and AI-01 handoffs are exact.
32. Three proposed canonical standards are minimal and non-overlapping.
33. The design is self-contained and leaves only implementation-detail choices
    to written-spec review and downstream milestones.
34. Applicability and consequence matrices are present and latency-safe.
35. Logical and physical append-only semantics are distinguished with a
    repository-grounded example.

## Written-spec review handoff

The next gate is **IMP-REBASE-02 Written-Spec Review & Hardening**. Reviewers
should verify terminology against `docs/platform/GLOSSARY.md`, authority against
`AUTHORITY_MODEL.md`, documentation rules against `DOCUMENTATION_STANDARD.md`,
and EVIDENCE independence against frozen campaign contracts. No runtime
implementation, canonical `docs/platform/` rewrite, or EVIDENCE policy change
belongs in that review unless explicitly approved as a separate governed task.

## Known design limitations

These are unresolved implementation choices, not semantic gaps:

1. OF-01 must choose physical storage, transaction, schema/versioning, and
   concurrency mechanisms while preserving the common semantics.
2. RT-01 must choose trace propagation format/backend and exact measured stage
   boundaries after examining the deployed topology.
3. Retention durations, encryption/access controls, and legal/privacy deletion
   rules require owning policies; this design defines classes only.
4. Benchmark budgets and SLOs require measured baselines and governing
   acceptance decisions; none are invented here.
5. Dirty-source closure tooling and source-capsule format remain implementation
   choices; the truthfulness requirements are fixed.
6. Historical adapters will expose varying provenance completeness and must be
   designed per source family without rewriting history.

No limitation blocks written-spec review. The design intentionally leaves no
unresolved meaning for run, attempt, execution, outcome, disposition, retry,
resume, consequence, reproducibility, artifact, trace/correlation, evaluation
origin, or historical provenance.

## Design readiness

```text
IMP_REBASE_02_DESIGN_READY_FOR_WRITTEN_SPEC_REVIEW
```
