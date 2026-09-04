# IMP reproducibility and run standard

| Field | Value |
|---|---|
| Document ID | `IMP-REPRODUCIBILITY-RUN-STANDARD` |
| Classification | `CANONICAL` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Run, attempt, execution, outcome, disposition, relationships, identity, artifacts, retention, redaction, retry, resume, checkpoint, cancellation, and consequence profiles |
| Establishing Milestone | `IMP-REBASE-02` |
| Version | `1.0` |
| Last Verified | `2026-08-27` |
| Supersedes | Fragmented run, artifact, and reproducibility conventions across subsystems |
| Superseded By | None |

This standard defines how consequential work is identified, attributed, executed,
judged, retained, and reproduced across IMP. It is semantics and governance
only. It does not implement the Universal Run Ledger, artifact registry,
workflow engine, trace backend, or any runtime infrastructure.

Normative language (`MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, `MAY`) governs
future implementations and canonical prose. It does not claim current
repository-wide compliance. Executable authorities listed in the
[Canonical Truth Map](CANONICAL_TRUTH_MAP.md) remain controlling within their
scope until future milestones implement common run attribution.

## Scope and exclusions

This standard owns run identity, attempt history, lifecycle, outcome validity,
disposition, typed relationships, source/environment/configuration/data/model
attribution, artifact identity and mutability, reproducibility classes,
consequence profiles, retry/resume/checkpoint semantics, retention and redaction
requirements, and operational failure/idempotency semantics.

This standard does **not** own:

- diagnostic log, metric, or trace envelope definitions — see
  [Observability Standard](OBSERVABILITY_STANDARD.md);
- validation, benchmark, backtest, or evaluation protocol details — see
  [Test and Evaluation Standard](TEST_AND_EVALUATION_STANDARD.md);
- EVIDENCE qualification policy, campaign semantics, or frozen-record meaning;
- risk, execution, release, or trading authority.

## Consequential operation

A **consequential operation** is work whose result, failure, timing, or side
effect may affect accepted evidence, canonical or operational state, a model or
dataset decision, a provider assessment, a release, an authority decision, or a
material research conclusion. Consequence is determined by contract and
operation class, not by process duration or human attention.

Routine function calls, individual log lines, cache hits, UI renders, and
high-volume market ticks are not automatically consequential operations.

## When a durable run identity is required

A durable **run identity** is required when one or more of the following apply:

1. the operation produces or consumes consequential durable artifacts;
2. the operation has a governed outcome or disposition;
3. the operation is independently retryable under policy;
4. the operation is independently auditable as one unit;
5. the operation changes governed state;
6. the operation is used as evaluation or acceptance evidence;
7. the operation is cited by another governed record;
8. the operation is a root or node in a declared workflow;
9. the operation must later be reproduced or attributed.

A durable run identity is **not** required for:

- every function call, tick, span, log line, or metric emission;
- hot-path model inferences that remain spans or events inside a parent run
  unless an operation contract elevates them to `C2`;
- debug-only telemetry with no governed consequence.

The operation class and consequence profile determine requirement; discretion
without contract is prohibited for `C2+` work.

### Representative granularity examples

| Work unit | Run required? | Reason |
|---|---|---|
| `validate.py changed` when acceptance-bound | Yes | governed evidence, disposition, artifacts |
| one model inference on hot path | Usually no | span or event inside larger run unless `C2` contract |
| one million inferences in batch evaluation job | Yes for the job | one consequential objective and disposition |
| EVIDENCE campaign | Reference existing authority | applicability matrix row; no retrofit |
| provider smoke with report | Yes | `C2` governed evaluation |
| individual unittest inside suite | No | child test result inside validation run |
| workflow orchestrating releases | Yes parent; child steps may be child runs | durable objective and disposition |
| benchmark invocation with `--output` | Yes when material | `C2` evaluation record |

## Run

A **run** is one durable logical invocation of a declared consequential objective
under a stable identity and evaluation intent. It answers: what work did we
intend to perform and judge as one unit?

A run is **not** defined by one OS process, one event, one span, or one
workflow tick. A run represents one durable logical consequential objective.

### Immutable run-defining fields

These fields are fixed at run registration and MUST NOT change across attempts
within the same run:

- `run_id`;
- operation class;
- declared objective or invocation reference;
- evaluation intent and protocol reference;
- consequence profile;
- semantically effective inputs identity bundle (source, configuration, data,
  model, and policy references that define the question being judged);
- applicable temporal cutoff bundle for hindsight-sensitive work;
- root or parent structural context when declared at registration.

If any immutable field would change materially, the work MUST become a new run
linked by `RESUMES_FROM`, `SUPERSEDES`, or `TRIGGERED_BY`, not a new attempt.

### Material change boundary (retry vs new run)

A new attempt within the same run is permitted only when all immutable
run-defining fields remain compatible.

The following changes are **material** and require a **new run**:

- change to committed source identity or dirty-source capsule beyond declared
  retry tolerance;
- change to semantically effective configuration hash or reference;
- change to dataset, snapshot, input manifest, or evaluation cutoff;
- change to model, candidate, or policy identity being evaluated;
- change to evaluation question, success criteria, or baseline reference;
- change to provider origin class for smoke or evaluation (`REAL_PROVIDER_OBSERVED`
  vs `MOCK` vs `FIXTURE`, etc.);
- change intended after the predecessor run is `CLOSED`.

The following may vary per attempt without creating a new run:

- execution host or process;
- transient environment detail not in the immutable bundle;
- retry ordinal and retry reason;
- stdout or stderr captures;
- technical failure class;
- checkpoint segment within the same attempt when the process remains alive.

### Run lifecycle

| State | Meaning |
|---|---|
| `REGISTERED` | Identity and intent exist; no attempt has started. |
| `ACTIVE` | At least one attempt has started and the run is not closed. |
| `SUSPENDED` | Intentionally paused; may resume under compatibility rules. |
| `CLOSED` | Terminal disposition appended; no new attempts permitted. |

Operation-specific states MAY exist separately. These states MUST NOT encode
program maturity, qualification, or authority.

#### Zero attempts

A run MAY remain in `REGISTERED` with zero attempts only when work is cancelled,
superseded, or abandoned before first execution starts. Such a run MUST close
with explicit disposition and `NOT_EVALUATED` or declared partial state. A run
that reached `ACTIVE` MUST have at least one attempt record.

#### Registration timing

`C2+` runs MUST be registered before the first attempt starts. `C0` and `C1`
runs MAY materialize from a buffered start event when loss tolerance permits,
but MUST NOT lose ordering required by their contract.

#### Terminality and reopening

`CLOSED` is terminal. A closed run MUST NOT be reopened. Correction requires a
new run linked by `RESUMES_FROM` or `SUPERSEDES`. `SUPERSEDED` is a disposition
action category and/or typed relationship; it is not a lifecycle state.

`SUSPENDED` MAY survive process death only when a durable suspension record and
eligible checkpoint exist under the owning contract.

Cancellation MAY produce a valid partial outcome only when the evaluation
protocol explicitly permits partial evidence and marks completeness accordingly.

## Attempt

An **attempt** is one bounded technical execution of a run. It answers: what did
the platform try this time?

### Attempt rules

- every attempt has immutable `attempt_id`, one-based `attempt_sequence`, start
  and end times, invocation and environment context, terminal technical result,
  reason codes, artifacts, and optional retry link to the preceding attempt;
- attempt history MUST be append-preserving; later success MUST NOT overwrite
  earlier failure;
- default: attempts within a run are strictly sequential; concurrent attempts
  are forbidden unless the operation contract explicitly allows parallel
  technical executions, in which case each parallel execution is a distinct
  attempt with its own identity and no shared mutable attempt state;
- overlapping attempts without explicit contract are a specification violation.

### Attempt phase and technical result

| Dimension | Values |
|---|---|
| Attempt phase | `PENDING`, `RUNNING`, `TERMINAL` |
| Terminal technical result | `COMPLETED`, `FAILED`, `TIMED_OUT`, `CANCELLED`, `INTERRUPTED`, `LOST`, `NOT_STARTED` |

`FAILED` means execution reported technical failure. `INTERRUPTED` means
continuity ended unexpectedly with known evidence. `LOST` means termination
evidence is missing and a later reconciler inferred loss. `CANCELLED` requires
actor or policy cause. Unknown causes remain `UNCLASSIFIED_FAILURE`; they MUST
NOT be guessed.

Technical completion is not analytical success.

### Attempt structure

```text
RUN
├── ATTEMPT 1
├── ATTEMPT 2
└── ...
```

Failed attempts are preserved. Attempt history MUST NOT be overwritten.

## Outcome

**Outcome** is the typed domain result after execution under the declared
protocol. It is separate from technical execution and from disposition.

### Outcome validity

| Validity | Meaning |
|---|---|
| `VALID` | Result interpretable under declared protocol |
| `INVALID` | Protocol, temporal, provenance, contamination, or integrity defect prevents interpretation |
| `INDETERMINATE` | Available evidence cannot establish validity |
| `NOT_EVALUATED` | No outcome evaluation occurred |

`INVALID` means invalid **evidence** or protocol violation. It does **not**
mean negative analytical outcome. A model that validly underperforms, a
benchmark that validly regresses, or a hypothesis that is validly rejected
remain `VALID` outcomes.

A negative result is not automatically invalid.

## Disposition

**Disposition** is the governed decision about an outcome. It is appended after
considering execution and outcome and MUST record decision time, authority
reference where applicable, action category, domain code, and limitations.

### Action categories (common)

| Category | Meaning |
|---|---|
| `ACCEPT` | Accept for declared scope |
| `REJECT` | Preserve valid result but reject candidate, proposition, or action |
| `DEFER` | No final judgment; condition pending |
| `RETRY` | New attempt authorized under policy |
| `INVALIDATE` | Result cannot be used under protocol |
| `CANCEL` | Intentionally stop and close |
| `ABANDON` | Close without completion after intent abandoned |
| `SUPERSEDE` | Successor replaces relevance without erasing predecessor |
| `NO_ACTION` | Preserve without promotion or rejection |

Domain codes remain domain-owned (`PASS`, `PASS_WITH_RETRY`,
`VALID_RESULT_REJECTED`, `INVALID_TEMPORAL_LEAKAGE`, `NOT_RUN_MARKET_CLOSED`,
etc.). Vocabularies such as `ValidationDisposition` and EVIDENCE qualification
states retain domain authority.

Disposition changes over time MUST be append-only decisions; prior dispositions
remain historical truth. There is no single cross-domain result enum.

### Normative disposition examples

| Case | Technical execution | Outcome validity and domain result | Disposition |
|---|---|---|---|
| Validation passes first attempt | Attempt 1 `COMPLETED` | `VALID`; criteria satisfied | `ACCEPT / PASS` |
| Validation passes after environment retry | Attempt 1 `FAILED` `ENVIRONMENT_FAILURE`; attempt 2 `COMPLETED` | `VALID`; criteria satisfied | `ACCEPT / PASS_WITH_RETRY`; both attempts retained |
| Model experiment underperforms | `COMPLETED` | `VALID`; candidate below baseline | `REJECT / VALID_RESULT_REJECTED` |
| Provider smoke during market closure | Preflight `COMPLETED`; observation `NOT_STARTED` | `NOT_EVALUATED`; expected external state | `DEFER / NOT_RUN_MARKET_CLOSED` |
| Live observation loses provider | `INTERRUPTED` with partial inputs | `INDETERMINATE` until continuity review | `RETRY`, `DEFER`, or `INVALIDATE` per policy |
| Backtest detects hindsight leakage | `COMPLETED` | `INVALID`; temporal leakage | `INVALIDATE / INVALID_TEMPORAL_LEAKAGE` |
| Research inconclusive | `COMPLETED` | `VALID`; inconclusive evidence | `NO_ACTION / INCONCLUSIVE` |
| AI investigation attributable | `COMPLETED` | `VALID` for read-only review only | `ACCEPT / ACCEPTED_FOR_REVIEW` |
| Benchmark measured but not comparable | `COMPLETED` | `VALID`; comparability `NOT_COMPARABLE` | `NO_ACTION / VALID_RESULT_NOT_COMPARABLE` |
| Operator cancel | `CANCELLED` | `NOT_EVALUATED` or marked partial | `CANCEL / OPERATOR_CANCELLED` |

## Retry, resume, and checkpoint

### Retry

**Retry** is a new attempt within the same **open** run when immutable
run-defining fields remain compatible. Retry MUST record preceding attempt,
reason, policy reference, idempotency declaration, and changed execution
context. Passing retry does not prove flakiness; `FLAKY_FAILURE` requires
independent evidence.

Changing source, configuration, data, model, cutoff, or question after failure
creates a **new run**, not a retry.

A retry cannot silently change the semantic experiment.

### Resume matrix

| Situation | Representation |
|---|---|
| Alive process continues from internal checkpoint | Same attempt, new continuation segment |
| Execution ended; restarts with compatible checkpoint and unchanged intent | Same run, new attempt with `resumed_from_checkpoint` |
| Parent workflow launches recovery with its own outcome | New child run `TRIGGERED_BY` plus checkpoint refs |
| Immutable field changes or predecessor `CLOSED` | New run `RESUMES_FROM` or `SUPERSEDES`; never mutate predecessor |

Checkpoints MUST identify run and attempt, content or state hash, production
time, compatibility dimensions, resume eligibility, and invalidation reason.
Checkpoint resume under incompatible code, configuration, data, model, policy,
or schema is forbidden unless explicit migration semantics exist.

### Retryability vs idempotency

`RETRYABLE` and `IDEMPOTENT` are distinct concepts.

| Idempotency class | Meaning |
|---|---|
| `IDEMPOTENT` | Repeated execution with same inputs has no additional side effect |
| `IDEMPOTENT_WITH_KEY` | Idempotent only when a declared idempotency key is reused |
| `CONDITIONALLY_IDEMPOTENT` | Idempotent only under stated conditions |
| `NON_IDEMPOTENT` | Repeated execution may change governed state |

Retry policy (conditions, max attempts, backoff, permanent-failure conditions)
is owned by operation authority. This standard records what happened.

## Typed run relationships

| Relationship | Meaning | Acyclic required? |
|---|---|---|
| `PARENT_OF` / `parent_run` | Structural containment | Yes |
| `root_run` | Stable root of containment tree | Yes |
| `TRIGGERED_BY` | Causal invocation without ownership | Yes (no causal cycles) |
| `RESUMES_FROM` | New run continues eligible predecessor state | Yes |
| `SUPERSEDES` | New run replaces predecessor relevance | Yes |
| `RELATED_TO` | Non-causal association with reason | No; cycles permitted |

Retries are attempt-scoped links, not `retries_run`. Fan-in and fan-out are
supported via multiple `TRIGGERED_BY` or `PARENT_OF` edges. A strict single
trace tree is not required globally. Only structural containment edges must be
acyclic.

## Initiator, trigger, and parent context

These are separate concepts:

- **initiator class**: `HUMAN`, `CI`, `SCHEDULER`, `SYSTEM`, `WORKFLOW`,
  `AGENT`, `PROVIDER_EVENT`;
- **trigger context**: schedule, PR, workflow run, policy decision, prior run,
  operator request, provider event reference;
- **parent or root context**: structural containment for orchestration.

Example: scheduler triggers workflow (`initiator=WORKFLOW`, `trigger=schedule_ref`,
`parent=workflow_run`). An agent invoked by workflow keeps workflow as parent
while the agent may be initiator of the child run. One enum MUST NOT encode the
full causal chain.

## Identifier distinctions (run layer)

| ID | Meaning |
|---|---|
| `run_id` | Consequential logical objective |
| `attempt_id` | Bounded technical execution within run |

`trace_id`, `correlation_id`, `event_id`, and `span_id` are defined in the
[Observability Standard](OBSERVABILITY_STANDARD.md). These MUST NOT be aliases.

## Consequence profiles

Consequence profile (`C0`–`C4`) is orthogonal to `HOT`, `WARM`, and `COLD`
latency or storage shape. All combinations are permitted: hot plus low
consequence, hot plus authority critical, cold plus evidence critical, and cold
plus low-consequence research.

### Assignment criteria

| Profile | Assign when | Objective criteria |
|---|---|---|
| `C0_EPHEMERAL` | debug or high-volume telemetry with no governed consequence | loss does not affect evidence, authority, or governed state |
| `C1_OPERATIONAL` | routine jobs, local validation, health diagnostics | attribution useful; failure should not rewrite history |
| `C2_GOVERNED` | material research, transforms, smoke, benchmarks, training | governed review and reproducibility required before trusting result |
| `C3_EVIDENCE_CRITICAL` | qualification, release acceptance, promotion evidence | acceptance requires durable append-preserving evidence |
| `C4_AUTHORITY_CRITICAL` | future execution or risk side effects | authority records and reconciliation before effect |

Assignment MUST be justified by the criteria above, not subjective importance.

### Consequence matrix

| Dimension | `C0` | `C1` | `C2` | `C3` | `C4` |
|---|---|---|---|---|---|
| Durability | Best effort | Durable by run close | Required records before disposition | Append-preserving evidence before acceptance | Idempotent durable intent and audit before side effect |
| Recording timing | Async or batched; sampling allowed | Buffered or async with bounded loss | Required refs before disposition | Required evidence before acceptance | Pre-effect boundary |
| Loss tolerance | High; counters required | Bounded declared loss | No silent loss of required records | Required records never sampled or dropped | Zero tolerance for authority-record loss |
| Retention baseline | `RET_EPHEMERAL` / `RET_BOUNDED_DIAGNOSTIC` | `RET_BOUNDED_DIAGNOSTIC` / `RET_OPERATIONAL` | `RET_REPRODUCIBILITY` | `RET_HISTORICAL_EVIDENCE` | `RET_AUTHORITY_POLICY` |
| Redaction | Secrets never persisted | Secrets never persisted | Full omission plus sensitive-field policy | Evidence-grade before durable write | Authority-grade; credential refs only when needed |
| Audit strength | Diagnostic | Operational attribution | Governed review and reproducibility | Acceptance evidence | Authority and execution audit plus reconciliation |

### Required-record fail-closed semantics

Failure policy applies to the **declared required-record set** for the operation
class and profile, not to all telemetry.

| Profile | Required-record failure default |
|---|---|
| `C0` | Continue degraded; count loss |
| `C1` | Continue degraded or invalidate observability claims |
| `C2` | Invalidate or defer result if required artifact or record missing |
| `C3` | Fail closed **for acceptance** if required evidence records missing; runtime may complete but acceptance MUST be withheld |
| `C4` | Fail closed for authority effect; reconcile uncertain external effects |

Nonessential metric or log sink failure MUST NOT automatically invalidate a `C3`
run when required evidence artifacts and hashes are durably present. Secret
protection is universal across profiles; lower consequence does not permit
secret persistence.

### Hot-path protection

This standard MUST NOT require synchronous giant provenance writes per tick,
database roundtrips per span, or full artifact manifests per event. Lightweight
event or trace emission, bounded buffering, asynchronous persistence, and
stronger durability for required evidence or authority records are supported.
Implementation details remain downstream.

## Reproducibility and evidence strength

Reproducibility describes repeatability. Evidence strength describes real-world
evidential value. **Reproducibility is not evidence quality.**

### Reproducibility classes `R5`–`R0`

| Class | Permitted claim | Does not permit | Minimum evidence |
|---|---|---|---|
| `R5_BIT_EXACT` | Byte-identical declared outputs under captured inputs and environment | Claim when only logical equality verified | Captured inputs, source, config, deps, environment, hardware declaration, byte comparison record |
| `R4_DETERMINISTIC_REPLAY` | Same declared invariants and results under replay | Bit-identical incidental output unless verified | Same as `R5` minus byte identity proof |
| `R3_INPUT_REPLAYABLE` | Captured inputs can be replayed; actual output retained | Identical output guarantee | Input capture manifest, output artifact, timing mode |
| `R2_ATTRIBUTABLE_NONDETERMINISTIC` | Attribution to source, config, model, tools, environment, output | Deterministic replay promise | Attribution bundle plus actual output or model artifact |
| `R1_OBSERVATION_ONLY` | Truthful record of observation and time | Input replay | Observation record with declared capture limits |
| `R0_NON_REPRODUCIBLE_DECLARED` | Explicit non-reproducibility reason | `C2+` acceptance unless governed exception | Declared reason and consequence |

Qualifiers (`ENVIRONMENT_RECONSTRUCTABLE`, `OUTPUT_RETAINED`,
`EXTERNAL_TIMING_DEPENDENT`, `HARDWARE_SENSITIVE`, `LEGACY_PARTIAL`,
`RETROSPECTIVE_INDEX`) MAY refine claims. `LEGACY_PARTIAL` and
`RETROSPECTIVE_INDEX` are provenance qualifiers, not primary reproducibility
classes.

### Evidence strength (orthogonal)

| Evidence strength | Meaning |
|---|---|
| `E3_DOMAIN_ADMITTED` | Admitted under domain authority (e.g., live forward observation) |
| `E2_GOVERNED_SYNTHETIC` | Governed fixture or synthetic with known limitations |
| `E1_DIAGNOSTIC` | Useful diagnostic or supporting record, not acceptance-grade |
| `E0_UNDECLARED` | Not evaluated for evidence strength |

A live provider observation may be `E3` with `R1` or `R3`. A deterministic
fixture may be `R4` with only `E2`.

### Classification examples

| Case | Reproducibility | Evidence strength |
|---|---|---|
| pinned-env unit test | `R4` | `E2` |
| unit test on dirty attributable source | `R4` with `DIRTY_ATTRIBUTABLE` | `E2` |
| test using wall clock without capture | `R2` or `R1` | `E1` |
| randomized property test with logged seed | `R2` | `E2` |
| historical replay logical-order only | `R3` or `R4` depending on timing mode | depends on origin |
| live provider session with raw capture | `R3` | `E3` when admitted |
| GPU training with nondeterministic kernels | `R2` plus `HARDWARE_SENSITIVE` | `E2` until validated |
| AI research output | `R2` or `R3` | `E1`–`E3` by protocol |

### Live reproducibility

Live provider reproducibility covers captured sequence, received timestamps,
provider payload, and derived internal computation. It does **not** recreate
external market reality, future provider responses, network timing, or exchange
state.

### AI reproducibility

AI runs may be attributable, input-replayable, and actual-output-preserved
without being bit-exact reproducible. No chain-of-thought capture is required.

## Attribution requirements

### Source and code identity

Required: repository identity, commit SHA, `CLEAN_COMMITTED`,
`DIRTY_ATTRIBUTABLE`, or `UNATTRIBUTABLE`.

`DIRTY_ATTRIBUTABLE` requires all of:

1. base revision known;
2. relevant changed paths identified by scope declaration;
3. relevant content captured or hash-addressable via capsule or diff manifest;
4. proof unrelated dirty paths are outside declared scope.

“We remember what changed” is not attributable. Unrelated dirty files MUST NOT
force `UNATTRIBUTABLE` when scope closure proves non-impact.

Multiple source roots MAY be recorded when an operation spans repositories or
packages. A single Git SHA is not required when multi-root attribution is
complete.

### Environment identity

Capture only fields material to result or required by policy: OS and
architecture, runtime versions, lock hash, container digest, hardware class,
drivers, concurrency, locale and timezone, feature or provider modes when
material.

Environment records MUST distinguish declared configuration from observed
runtime facts. Arbitrary environment variables MUST NOT be captured.

**Secrets:** API keys, passwords, tokens, private keys, and raw credentials
MUST NOT be persisted for reproducibility. Low-entropy secrets MUST NOT be
hashed. Use secret reference, credential-provider identity, or redacted
indicator when necessary.

### Configuration, data, model, and temporal identity

- **configuration**: stable canonicalized hash or reference of semantically
  effective non-secret fields; mutable name alone is insufficient for `C2+`;
- **data**: dataset, snapshot, manifest, hashes, coverage, cutoff, revision,
  lineage; filename alone is insufficient;
- **model or policy**: canonical IDs, artifact hash, exposed version or declared
  limitation, prompt or template reference, authority mode;
- **temporal**: reuse `available_time_ns <= decision_time_ns` for decision
  eligibility per existing temporal contracts; record named cutoff bundle
  (observation, training, evaluation, settlement, etc.) without conflating
  clocks.

## Artifact model

Path is a locator, not sufficient identity.

### Logical identity vs content version

- **logical artifact identity** (`artifact_ref`): stable role plus producer run
  (plus optional logical name) across versions;
- **content version identity** (`content_hash` or version sequence): immutable
  bytes for a specific version.

Same bytes used in two roles require two logical artifact records. Mutable
status files (`PROGRAM_STATUS.md`, heartbeat files, aggregates) use logical
identity with changing content versions.

### Mutability classes

| Class | Rule |
|---|---|
| `IMMUTABLE_EVIDENCE` | Bytes or hash frozen; replacement creates new artifact version |
| `APPEND_ONLY_JOURNAL` | Entries append-preserving; range or checkpoint hashes |
| `REGENERABLE_OUTPUT` | Generator plus inputs identified |
| `MUTABLE_STATUS` | Current projection may change; historical accepted versions recoverable |
| `EPHEMERAL_SCRATCH` | Not acceptance evidence |
| `CACHE` | Reconstructable only |

### Append semantics

| Term | Definition |
|---|---|
| `PHYSICAL_APPEND_ONLY` | Storage only appends bytes within the active segment; prior committed bytes are not rewritten in place; truncation or compaction of active segment forbidden; rotation to immutable segments permitted when contract declares segment immutability |
| `LOGICAL_APPEND_ONLY` | Prior records remain recoverable from an authoritative history source; consumers can reconstruct history without overwriting earlier facts |

A mutable aggregate alone is **not** `LOGICAL_APPEND_ONLY`. There must be an
authoritative history source from which history remains recoverable.

**Repository examples (verified foundations, not universal claims):**

- EVIDENCE `OBSERVATIONS.jsonl` and `OPERATIONAL_EVENTS.jsonl` use physical
  append-style journal storage under campaign contracts;
- EVIDENCE `CAMPAIGN_RUNTIME_STATE.json` and `CAMPAIGN_METRICS.json` are
  `MUTABLE_STATUS` aggregates whose history is represented elsewhere;
- assistant `conversations.json` uses whole-file rewrite and is neither
  physically nor durably logically append-only.

### Durability dimensions (orthogonal)

| Dimension | Question |
|---|---|
| Write pattern | append, replace, journal plus aggregate |
| Acknowledged durability | fsync, flush, replica ack where claimed |
| Crash consistency | atomic rename, valid prefix, tail unclosed |

**Append pattern is not durability.** A non-fsynced append may be lost. An
atomic replacement may have strong crash-consistency characteristics.

### Partial artifacts

Mark `PARTIAL`, `COMPLETE`, or `UNKNOWN` completeness; producer attempt;
terminal execution state; validation state; use restriction. Partial artifacts
from failed, cancelled, timed-out, or interrupted runs MAY be retained if
useful. They MUST be explicitly marked incomplete or partial. They MUST NOT
satisfy accepted-output requirements without explicit narrowed acceptance
review.

### Retention classes

`RET_EPHEMERAL`, `RET_BOUNDED_DIAGNOSTIC`, `RET_OPERATIONAL`,
`RET_REPRODUCIBILITY`, `RET_HISTORICAL_EVIDENCE`, `RET_AUTHORITY_POLICY`.
Durations are policy-owned; this standard defines classes only.

### Redaction

Secret-sensitive data MUST NOT reach unauthorized durable logs or artifacts.
Redaction MUST occur before durable write for `C2+`. In-memory handling before
durable emission is permitted. Later scrub is insufficient for governed
evidence.

## Failure and operational semantics

Failure reason families include environment failure, timeout, cancellation,
interruption, provider unavailability, integrity defect, policy block, and
unclassified failure. Technical execution success is distinct from outcome
validity and disposition.

Typed links to incident, defect, technical debt, known limitation, and
corrective action MAY be recorded without requiring one combined registry.
`IMP-OF-03` owns future consolidation.

## Historical compatibility and retrospective identity

Older accepted history remains authoritative within what it actually captured.
Future adapters MAY index historical records. They MUST NOT fabricate missing
facts.

If future `IMP-OF-02` creates indexing IDs for old evidence, `RETROSPECTIVE_INDEX`
MUST remain distinguishable from `ORIGINAL_HISTORICAL_IDENTITY`. Never claim a
retrospective run ID existed at the original cutoff if it did not.

## Applicability matrix

Legend: `M` mandatory; `C` mandatory when applicable or material; `R` reference
existing domain authority; `—` normally not required. `Src` includes dirty-state
attribution. `Obs` means required structured logs, metrics, or trace per profile,
not every telemetry kind.

| Operation | Profile | Run / attempts | Src | Config | Data | Model/policy | Time cutoff | Env | Obs | Durable artifacts | Baseline reproducibility |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Unit/integration validation | C1; C2 when acceptance-bound | M | M | C | C | C | C | M | C | M report | `R4` |
| Full validation | C2/C3 | M | M | M | C | C | C | M | M | M report/log refs | `R4` |
| Provider smoke | C2 | M | M | M | C | M | M | M | M | M redacted report | `R1` or `R3` |
| Data ingest | C2; C3 when admitted evidence | M | M | M | M source manifest | R admission/quality | M | M | M | M raw/normalized manifests | `R3`/`R4` |
| Data transform | C2 | M | M | M | M | C | M | M | C | M outputs/lineage | `R4` preferred |
| Model training | C2 | M | M | M | M | M | M | M incl. hardware | M | M candidate/diagnostics | `R2` or `R4` |
| Model inference | C0 span hot path; C2 when consequential | C | C | C | M input ref | M | M | C | C/M | M output when C2 | `R2`/`R3` |
| Backtest | C2 | M | M | M | M | M | M | M | M | M report/diagnostics | `R4` preferred |
| Replay | C1/C2 | M | M | M | M capture | C | M | M | M | M replay report | `R3`/`R4` |
| Simulation/paper | C2 | M | M | M | M origin | M assumptions | M | M | M | M ledger/report | `R2`/`R4` |
| Performance benchmark | C2 | M | M | M | M workload | C | C | M hardware/load | M | M samples/report | `R2` |
| Research | C2 | M | M | M | M sources | C | M | C | C | M conclusion/evidence | `R2`–`R4` |
| AI research | C2 | M | M | M | M evidence pack | M model/prompt/tools | M | M | M | M prompt/output/citations | `R2`/`R3` |
| EVIDENCE campaign | Existing C3 authority | R existing IDs/records | R | R | R | R | R | R | R | R frozen records | Existing contract; future indexing only |
| Release acceptance | C3 | M | M clean/capsule | M | C | M policy/evidence | M | M | M | M accepted bundle/hashes | `R4` where applicable |
| Future execution-critical action | C4 | M before effect | M | M | M state/input | M risk/authority | M | M | M + reconciliation | M intent/audit/response | `R1`/`R3`; attribution mandatory |

Rows may strengthen under owning authority; they MUST NOT weaken temporal
integrity, evidence origin, safety, or consequence requirements.

## AI operations constraints (run layer)

AI attribution is not AI reproducibility. Record provider and model,
template or version reference, tools, sources, cutoff, actual structured
output, and authority mode. No hidden chain-of-thought.

Authority modes are read-only (`RESEARCH_ONLY`, `ADVISORY`,
`STRUCTURED_ANALYSIS`, `WORKFLOW_ORCHESTRATION`). **AI output does not grant
trading authority.** No AI run grants risk, release, qualification, or
execution authority.

## Downstream handoffs

| Milestone | Contract from this standard |
|---|---|
| `IMP-OF-01` | Durable run and attempt identity, outcome, validity, disposition, artifact linking, source/config/data/model attribution, append-preserving history |
| `IMP-OF-02` | Adapters; index immutable records; no history rewrite |
| `IMP-RT-01` | Trace and correlation attach to run identity; does not redefine run lifecycle |
| `IMP-XA-01` | Provenance, temporal integrity, evaluation, artifact identity inheritance |
| `IMP-OF-03` | Typed run relationships for workflow, SOP, incident, and debt linkage |
| `IMP-AI-01` | Non-authoritative attributable AI operations using OF-01 run attribution |

## EVIDENCE isolation

```text
EVIDENCE-01C new dependency introduced: NO
EVIDENCE semantics changed: NO
```

No retrofit of universal run IDs into frozen EVIDENCE artifacts. Future `IMP-OF-02`
may index or reference without rewriting.

## ADAPT compatibility

Future adaptive concepts (Experience, Reflection, Lesson Candidate, Experiment,
Model Challenger, Prompt Challenger, Graph Challenger, Adaptive Evaluation)
MAY be represented under generic run, artifact, experiment, AI attribution,
outcome, disposition, checkpoint, and reproducibility semantics without
implementing ADAPT-specific schemas in this standard.
