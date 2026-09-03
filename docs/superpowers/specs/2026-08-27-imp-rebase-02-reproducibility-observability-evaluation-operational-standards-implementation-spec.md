# IMP-REBASE-02 Reproducibility, Observability, Evaluation & Operational Standards — Final Implementation Specification

| Field | Value |
|---|---|
| Document ID | `IMP-REBASE-02-SPEC` |
| Classification | `ACTIVE_SUPPORTING` |
| Truth class | `APPROVED_FUTURE_DESIGN` |
| Status | `APPROVED_FOR_IMPLEMENTATION` |
| Version | `1.0` |
| Last verified | `2026-08-27` |
| Establishing milestone | `IMP-REBASE-02 written-spec review` |
| Supersedes | `2026-08-27-imp-rebase-02-reproducibility-observability-evaluation-operational-standards-design.md` as the implementation contract only |
| Superseded by | None |

This specification is the sole implementation contract for IMP-REBASE-02. The
accepted design at `bc04d5ec344162dcc91ddbe8a41be918f6ed7e69` remains preserved
as design history. Where the design and this specification differ, this
specification controls implementation scope, canonical prose, and acceptance.
Its approval is an implementation-readiness judgment; it is not principal
approval of runtime infrastructure, provider behavior, model promotion,
qualification, release authorization, or trading authority.

## Purpose

IMP-REBASE-02 converts the accepted design into three non-overlapping canonical
program standards that define how consequential work is identified, attributed,
observed, evaluated, reproduced where possible, retained, and accepted across
IMP. The milestone is documentation-only. It generalizes strong existing
patterns without replacing subsystem contracts, inventing a Universal Run
Ledger, or modifying EVIDENCE semantics.

The written-spec review verified repository foundations, challenged semantic
boundaries against repository reality, and resolved the remaining ambiguities
listed in the review report. Implementation agents must use this document alone;
they must not combine the design, chat commentary, and this specification at
runtime.

## Governing precedence

Use this order when sources conflict:

1. current executable repository truth;
2. accepted `docs/platform/` canonical program truth from IMP-REBASE-01;
3. accepted REBASE-01 implementation and `artifacts/imp-rebase/REBASE01/**`
   acceptance evidence;
4. accepted REBASE-02 design at `bc04d5e`;
5. accepted REBASE-00 audit evidence;
6. this specification.

If repository reality contradicts the design, this specification already
incorporates the correction. If this review prompt contradicted the accepted
design without repository justification, the design was preserved.

## Verified starting state

The written-spec review recovered this state on 2026-08-27:

| Item | Verified value |
|---|---|
| Repository | `C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform` |
| Original worktree branch / HEAD | `cloud/build-35-release-governance-operational-acceptance` / `44800d2e210e58ff5759c44cc343dd4578c0b821` |
| Original dirty state | 9 tracked modifications + untracked work; preserved untouched |
| Accepted REBASE-01 branch / HEAD | `docs/imp-rebase-01-canonical` / `9c7ea456cadc9d9b381447640e0bda506e779f0a` |
| Design branch / commit | `docs/imp-rebase-02-design` / `bc04d5ec344162dcc91ddbe8a41be918f6ed7e69` |
| Design worktree | `.worktrees/imp-rebase-02-design` |
| Review branch | `docs/imp-rebase-02-spec-review` |
| Review starting HEAD | `bc04d5ec344162dcc91ddbe8a41be918f6ed7e69` |
| Design document SHA-256 | `691053CB730319AE2C8C17EE8DEC52D8A799488CCD2A0FDF8C239D6BFFCC8054` (matches expected) |
| Design document lines | 1,479 |
| Later legitimate design commits | None found on `docs/imp-rebase-02-design` |

No fetch, push, merge, reset, clean, stash, force-push, or unrelated-worktree
mutation was performed during review.

## Material corrections from written-spec review

| Issue | Risk | Correction | Implementation effect |
|---|---|---|---|
| Run granularity left partly discretionary | Inconsistent run creation across OF-01 adapters | Added explicit run-required decision rule and anti-patterns | Canonical run standard must include the rule verbatim |
| Zero-attempt runs under-specified | Ambiguous lifecycle and acceptance | Zero attempts allowed only when run never reached `ACTIVE`; closure requires explicit reason | Run standard lifecycle section updated |
| Attempt concurrency unspecified | Lost ordering, double-counted retries | Default: attempts are strictly sequential; parallel technical executions require explicit operation contract and distinct attempt identities | Run standard attempt section updated |
| Config retry vs new-run boundary underspecified | Retries silently change the experiment | Added material-change criteria and immutable run-defining field table | Run standard identity-boundary section added |
| `LOGICAL_APPEND_ONLY` could be misread as aggregate rewrite | OF-01 assumes durable journals that do not exist | Logical append-only requires an authoritative recoverable history source; aggregate alone is insufficient | Run standard artifact section updated |
| `PHYSICAL_APPEND_ONLY` too strict for segmented logs | Term unusable or falsely claimed | Segment-based append-only permitted when prior committed segments are immutable and contract declares rotation/compaction semantics | Run standard artifact section updated |
| Durability conflated with append pattern | Overpromised crash safety | Separated write pattern, acknowledged durability, and crash-consistency dimensions | Run standard storage section added |
| Artifact identity conflated logical role and content version | Same bytes/different roles or mutable status files mishandled | Split logical artifact identity from content/version identity | Run standard artifact section updated |
| Fail-closed language too broad for C3 | Nonessential telemetry failure blocks valid acceptance | Fail-closed applies to the declared required-record set for acceptance, not all C3 observability | Consequence and observability sections narrowed |
| Reproducibility rank could imply evidence quality | `R5` misread as “better evidence” | Added orthogonal evidence-strength dimension separate from reproducibility class | All three standards must state the separation |
| `LEGACY_PARTIAL` / `RETROSPECTIVE_INDEX` category ambiguity | Mixed migration and reproducibility semantics | Classified as provenance qualifiers, not reproducibility classes | Run standard legacy section updated |
| `CLOSED` reopening and `SUPERSEDED` placement unclear | Mutable history or lifecycle overload | `CLOSED` is terminal; reopening forbidden; `SUPERSEDED` is disposition/relationship, not lifecycle | Run standard terminality section updated |
| Global DAG assumption for all relationships | Impossible graphs for association edges | Only structural containment edges must be acyclic; `RELATED_TO` may form cycles | Run standard relationships section updated |
| Initiator enum overloaded causal chain | Wrong attribution for scheduler→workflow→agent chains | Require initiator, trigger context, and parent/root context as separate fields | Run standard initiator section updated |
| Benchmark foundation understated in places | False “benchmark absent” claims downstream | Benchmark execution foundation = `EXISTING`; universal comparability standard = `MISSING` | Evaluation standard must cite `tools/benchmark.py` accurately |
| Secret hashing risk under-emphasized | Low-entropy secret leakage via env hashes | Prohibit hashing low-entropy secrets; allowlist non-secret env capture | Run standard environment section updated |
| p95/p99 implied without sample policy | Meaningless quantiles on tiny samples | Require sample count preservation; p95/p99 only when sample count and protocol justify them | Evaluation benchmark section updated |

All other major design decisions were confirmed and are carried forward below.

## Confirmed repository foundations

The review verified and preserved these conclusions unless repository state
materially changes:

- manifest-driven validation via `tools/validation_manifest.json` and
  `tools/validate.py`;
- EVIDENCE content-derived IDs and JSONL append/fsync patterns in
  `src/market_platform_foundation/intelligence/forward_qualification/evidence01a/store.py`
  and `evidence01b/store.py`;
- immutable prediction/settlement identities and
  `available_time_ns <= decision_time_ns` temporal law;
- artifact hashes/manifests and model/data provenance patterns;
- existing logging/health primitives;
- informational benchmark runner at `tools/benchmark.py`;
- assistant audit logical history via whole-file rewrite in
  `src/market_platform_foundation/assistant/audit_store.py`;
- validation atomic report replacement without universal run identity.

### Benchmark reality

`tools/benchmark.py` is an **existing** informational runner. Verified behavior:

- workloads: Python startup, tiny unittest worker, optional FAST validation
  command, and production fixture operations (macro state, energy context, short
  pressure, CFTC mapping, representative simulation, and related fixture-bound
  APIs);
- fields recorded: `schema_version`, `report_type`, `generated_at`,
  `repository_root`, `platform`, `python_version`, `logical_cpu_count`,
  `configuration`, per-workload `fixture_refs`, `iterations_per_sample`,
  `repeat`, sample seconds, min/median/mean/max, return codes for commands,
  stdout/stderr byte counts, availability/unavailability reasons;
- persistence: only when `--output` is supplied; atomic replace via temp file +
  `fsync`;
- gating: none; interpretation explicitly informational;
- missing for universal standard: accepted environment identity contract,
  baseline compatibility, comparability state, resource use, and gating budget.

The implementation spec therefore states:

```text
benchmark execution foundation = EXISTING
universal benchmark provenance/comparability standard = MISSING
```

## Normative language

`MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, and `MAY` govern the canonical
standards and future implementations. They do not claim current repository
compliance. Physical schema names may differ when a documented lossless mapping
to these semantics exists.

## Common semantic model

### Consequential operation

A consequential operation is work whose result, failure, timing, or side effect
may affect accepted evidence, canonical or operational state, a model or dataset
decision, a provider assessment, a release, an authority decision, or a
material research conclusion. Consequence is determined by contract and
operation class, not by process duration or human attention.

Routine function calls, individual log lines, cache hits, UI renders, and
high-volume market ticks are not automatically consequential operations.

### When a durable run identity is required

A durable run identity is required when one or more of the following apply:

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
- hot-path model inferences that remain spans/events inside a parent run unless
  an operation contract elevates them to C2;
- debug-only telemetry with no governed consequence.

The operation class and consequence profile determine requirement; discretion
without contract is prohibited for C2+ work.

#### Representative granularity examples

| Work unit | Run required? | Reason |
|---|---|---|
| `validate.py changed` when acceptance-bound | Yes | governed evidence, disposition, artifacts |
| one model inference on hot path | Usually no | span/event inside larger run unless C2 contract |
| one million inferences in batch evaluation job | Yes for the job | one consequential objective and disposition |
| EVIDENCE campaign | Reference existing authority | R row in applicability matrix; no retrofit |
| provider smoke with report | Yes | C2 governed evaluation |
| individual unittest inside suite | No | child test result inside validation run |
| workflow orchestrating releases | Yes parent; child steps may be child runs | durable objective + disposition |
| benchmark invocation with `--output` | Yes when material | C2 evaluation record |

### Run

A run is one durable logical invocation of a declared consequential objective
under a stable identity and evaluation intent. It answers: “what work did we
intend to perform and judge as one unit?” It is not defined by one OS process,
one event, one span, or one workflow tick.

#### Immutable run-defining fields

These fields are fixed at run registration and MUST NOT change across attempts
within the same run:

- `run_id`;
- operation class;
- declared objective or invocation reference;
- evaluation intent and protocol reference;
- consequence profile;
- semantically effective inputs identity bundle (source/config/data/model/policy
  references that define the question being judged);
- applicable temporal cutoff bundle for hindsight-sensitive work;
- root/parent structural context when declared at registration.

If any immutable field would change materially, the work MUST become a new run
linked by `RESUMES_FROM`, `SUPERSEDES`, or `TRIGGERED_BY`, not a new attempt.

#### Material change boundary (retry vs new run)

A new attempt within the same run is permitted only when all immutable
run-defining fields remain compatible. The following changes are **material**
and require a **new run**:

- change to committed source identity or dirty-source capsule beyond declared
  retry tolerance;
- change to semantically effective configuration hash/reference;
- change to dataset/snapshot/input manifest or evaluation cutoff;
- change to model/candidate/policy identity being evaluated;
- change to evaluation question, success criteria, or baseline reference;
- change to provider origin class for smoke/evaluation (`REAL_PROVIDER_OBSERVED`
  vs `MOCK` vs `FIXTURE`, etc.);
- change intended after the predecessor run is `CLOSED`.

The following may vary per attempt without creating a new run:

- execution host/process;
- transient environment detail not in the immutable bundle;
- retry ordinal and retry reason;
- stdout/stderr captures;
- technical failure class;
- checkpoint segment within the same attempt when process remains alive.

#### Run lifecycle

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

C2+ runs MUST be registered before the first attempt starts. C0/C1 runs MAY
materialize from a buffered start event when loss tolerance permits, but MUST NOT
lose ordering required by their contract.

#### Terminality and reopening

`CLOSED` is terminal. A closed run MUST NOT be reopened. Correction requires a
new run linked by `RESUMES_FROM` or `SUPERSEDES`. `SUPERSEDED` is a disposition
action category and/or typed relationship; it is not a lifecycle state.

`SUSPENDED` MAY survive process death only when a durable suspension record and
eligible checkpoint exist under the owning contract.

Cancellation MAY produce a valid partial outcome only when the evaluation
protocol explicitly permits partial evidence and marks completeness accordingly.

### Attempt

An attempt is one bounded technical execution of a run. It answers: “what did the
platform try this time?”

#### Attempt rules

- every attempt has immutable `attempt_id`, one-based `attempt_sequence`, start
  and end times, invocation/environment context, terminal technical result,
  reason codes, artifacts, and optional retry link to the preceding attempt;
- attempt history MUST be append-preserving; later success MUST NOT overwrite
  earlier failure;
- default: attempts within a run are strictly sequential; concurrent attempts
  are forbidden unless the operation contract explicitly allows parallel
  technical executions, in which case each parallel execution is a distinct
  attempt with its own identity and no shared mutable attempt state;
- overlapping attempts without explicit contract are a specification violation.

#### Attempt phase and technical result

| Dimension | Values |
|---|---|
| Attempt phase | `PENDING`, `RUNNING`, `TERMINAL` |
| Terminal technical result | `COMPLETED`, `FAILED`, `TIMED_OUT`, `CANCELLED`, `INTERRUPTED`, `LOST`, `NOT_STARTED` |

`FAILED` = execution reported technical failure. `INTERRUPTED` = continuity
ended unexpectedly with known evidence. `LOST` = termination evidence missing
and later reconciler inferred loss. `CANCELLED` requires actor/policy cause.
Unknown causes remain `UNCLASSIFIED_FAILURE`; they MUST NOT be guessed.

Technical completion is not analytical success.

### Outcome

Outcome is the typed domain result after execution under the declared protocol.
It is separate from technical execution and from disposition.

#### Outcome validity

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

### Disposition

Disposition is the governed decision about an outcome. It is appended after
considering execution and outcome and MUST record decision time, authority
reference where applicable, action category, domain code, and limitations.

#### Action categories (common)

| Category | Meaning |
|---|---|
| `ACCEPT` | Accept for declared scope |
| `REJECT` | Preserve valid result but reject candidate/proposition/action |
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
remain historical truth.

### Retry, resume, checkpoint

#### Retry

Retry = new attempt within the same **open** run when immutable run-defining
fields remain compatible. Retry MUST record preceding attempt, reason, policy
reference, idempotency declaration, and changed execution context. Passing retry
does not prove flakiness; `FLAKY_FAILURE` requires independent evidence.

Changing source/config/data/model/cutoff/question after failure creates a **new
run**, not a retry.

#### Resume matrix

| Situation | Representation |
|---|---|
| Alive process continues from internal checkpoint | Same attempt, new continuation segment |
| Execution ended; restarts with compatible checkpoint and unchanged intent | Same run, new attempt with `resumed_from_checkpoint` |
| Parent workflow launches recovery with its own outcome | New child run `TRIGGERED_BY` + checkpoint refs |
| Immutable field changes or predecessor `CLOSED` | New run `RESUMES_FROM` or `SUPERSEDES`; never mutate predecessor |

Checkpoints MUST identify run/attempt, content/state hash, production time,
compatibility dimensions, resume eligibility, and invalidation reason.
Checkpoint resume under incompatible code/config/data/model/policy/schema is
forbidden unless explicit migration semantics exist.

### Relationships

| Relationship | Meaning | Acyclic required? |
|---|---|---|
| `PARENT_OF` / `parent_run` | Structural containment | Yes |
| `root_run` | Stable root of containment tree | Yes |
| `TRIGGERED_BY` | Causal invocation without ownership | Yes (no causal cycles) |
| `RESUMES_FROM` | New run continues eligible predecessor state | Yes |
| `SUPERSEDES` | New run replaces predecessor relevance | Yes |
| `RELATED_TO` | Non-causal association with reason | No; cycles permitted |

Retries are attempt-scoped links, not `retries_run`. Fan-in and fan-out are
supported via multiple `TRIGGERED_BY` or `PARENT_OF` edges; a strict single
trace tree is not required globally.

### Initiator, trigger, and parent context

These are separate concepts:

- **initiator class**: `HUMAN`, `CI`, `SCHEDULER`, `SYSTEM`, `WORKFLOW`,
  `AGENT`, `PROVIDER_EVENT`;
- **trigger context**: schedule, PR, workflow run, policy decision, prior run,
  operator request, provider event reference;
- **parent/root context**: structural containment for orchestration.

Example: scheduler triggers workflow (`initiator=WORKFLOW`,
`trigger=schedule_ref`, `parent=workflow_run`). Agent invoked by workflow keeps
workflow as parent while agent may be initiator of the child run. One enum MUST
NOT encode the full causal chain.

### Event, trace, span, correlation, run

| ID | Meaning |
|---|---|
| `run_id` | Consequential logical objective |
| `attempt_id` | Bounded technical execution within run |
| `event_id` | Discrete domain/business/system fact |
| `trace_id` | One causal processing path |
| `span_id` | Timed segment within a trace |
| `correlation_id` | Groups related records without asserting strict causality |

These MUST NOT be aliases. Traces MAY cross run boundaries; runs MAY contain
many traces. Correlation does not prove causality. Fan-out/fan-in MUST be
representable without forcing one global tree.

## Consequence and recording profiles

Consequence profile (`C0`–`C4`) is orthogonal to HOT/WARM/COLD latency/storage
shape.

### Assignment criteria

| Profile | Assign when | Objective criteria |
|---|---|---|
| `C0_EPHEMERAL` | debug/high-volume telemetry with no governed consequence | loss does not affect evidence, authority, or governed state |
| `C1_OPERATIONAL` | routine jobs, local validation, health diagnostics | attribution useful; failure should not rewrite history |
| `C2_GOVERNED` | material research, transforms, smoke, benchmarks, training | governed review/reproducibility required before trusting result |
| `C3_EVIDENCE_CRITICAL` | qualification, release acceptance, promotion evidence | acceptance requires durable append-preserving evidence |
| `C4_AUTHORITY_CRITICAL` | future execution/risk side effects | authority records and reconciliation before effect |

Assignment MUST be justified by the criteria above, not subjective importance.

### Monotonicity

Higher consequence generally implies a superset of required-record durability,
audit strength, and retention expectations. Exceptions exist: some C3 scientific
evidence may require longer retention than some C4 operational audit snippets.
Retention therefore also uses owning policy classes; consequence alone does not
encode every retention duration.

### Required-record fail-closed semantics

Failure policy applies to the **declared required-record set** for the
operation class and profile, not to all telemetry.

| Profile | Required-record failure default |
|---|---|
| `C0` | Continue degraded; count loss |
| `C1` | Continue degraded or invalidate observability claims |
| `C2` | Invalidate or defer result if required artifact/record missing |
| `C3` | Fail closed **for acceptance** if required evidence records missing; runtime may complete but acceptance MUST be withheld |
| `C4` | Fail closed for authority effect; reconcile uncertain external effects |

Nonessential metric/log sink failure MUST NOT automatically invalidate a C3 run
when required evidence artifacts and hashes are durably present. Secret
protection is universal across profiles; lower consequence does not permit
secret persistence.

## Reproducibility and evidence strength

### Reproducibility classes `R5`–`R0`

| Class | Permitted claim | Does not permit | Minimum evidence |
|---|---|---|---|
| `R5_BIT_EXACT` | Byte-identical declared outputs under captured inputs/environment | Claim when only logical equality verified | Captured inputs, source, config, deps, environment, hardware declaration, byte comparison record |
| `R4_DETERMINISTIC_REPLAY` | Same declared invariants/results under replay | Bit-identical incidental output unless verified | Same as R5 minus byte identity proof |
| `R3_INPUT_REPLAYABLE` | Captured inputs can be replayed; actual output retained | Identical output guarantee | Input capture manifest, output artifact, timing mode |
| `R2_ATTRIBUTABLE_NONDETERMINISTIC` | Attribution to source/config/model/tools/environment/output | Deterministic replay promise | Attribution bundle + actual output/model artifact |
| `R1_OBSERVATION_ONLY` | Truthful record of observation/time | Input replay | Observation record with declared capture limits |
| `R0_NON_REPRODUCIBLE_DECLARED` | Explicit non-reproducibility reason | C2+ acceptance unless governed exception | Declared reason and consequence |

Qualifiers (`ENVIRONMENT_RECONSTRUCTABLE`, `OUTPUT_RETAINED`,
`EXTERNAL_TIMING_DEPENDENT`, `HARDWARE_SENSITIVE`, `LEGACY_PARTIAL`,
`RETROSPECTIVE_INDEX`) MAY refine claims. `LEGACY_PARTIAL` and
`RETROSPECTIVE_INDEX` are provenance qualifiers, not primary reproducibility
classes.

### Evidence strength (orthogonal)

Reproducibility describes repeatability, not real-world evidential value. The
standards MUST treat evidence strength separately, for example:

| Evidence strength | Meaning |
|---|---|
| `E3_DOMAIN_ADMITTED` | Admitted under domain authority (e.g., live forward observation) |
| `E2_GOVERNED_SYNTHETIC` | Governed fixture/synthetic with known limitations |
| `E1_DIAGNOSTIC` | Useful diagnostic/supporting record, not acceptance-grade |
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
| GPU training with nondeterministic kernels | `R2` + `HARDWARE_SENSITIVE` | `E2` until validated |
| AI research output | `R2`/`R3` | `E1`–`E3` by protocol |

Live provider reproducibility covers captured sequence, received timestamps,
provider payload, and derived internal computation. It does not recreate
external market reality, future provider responses, network timing, or exchange
state.

## Attribution requirements

### Source and code identity

Required: repository identity, commit SHA, `CLEAN_COMMITTED`,
`DIRTY_ATTRIBUTABLE`, or `UNATTRIBUTABLE`.

`DIRTY_ATTRIBUTABLE` requires all of:

1. base revision known;
2. relevant changed paths identified by scope declaration;
3. relevant content captured or hash-addressable via capsule/diff manifest;
4. proof unrelated dirty paths are outside declared scope.

“We remember what changed” is not attributable. Unrelated dirty files MUST NOT
force `UNATTRIBUTABLE` when scope closure proves non-impact.

Multiple source roots MAY be recorded when operation spans repositories or
packages. A single Git SHA is not required when multi-root attribution is
complete.

### Environment identity

Capture only fields material to result or required by policy: OS/architecture,
runtime versions, lock hash, container digest, hardware class, drivers,
concurrency, locale/timezone, feature/provider modes when material.

Environment records MUST distinguish declared configuration from observed
runtime facts. Arbitrary environment variables MUST NOT be captured. Secret
values MUST NOT be serialized. Low-entropy secrets MUST NOT be hashed.
Allowlisted non-secret fields and credential-provider class references are
permitted.

### Configuration, data, model, temporal

- configuration: stable canonicalized hash/reference of semantically effective
  non-secret fields; mutable name alone insufficient for C2+;
- data: dataset/snapshot/manifest, hashes, coverage, cutoff, revision,
  lineage; filename alone insufficient;
- model/policy: canonical IDs, artifact hash, exposed version or declared
  limitation, prompt/template reference, authority mode;
- temporal: reuse `available_time_ns <= decision_time_ns` for decision
  eligibility; record named cutoff bundle (observation, training, evaluation,
  settlement, etc.) without conflating clocks.

## Artifact model

### Logical identity vs content version

- **logical artifact identity** (`artifact_ref`): stable role + producer run
  (+ optional logical name) across versions;
- **content version identity** (`content_hash` or version sequence): immutable
  bytes for a specific version.

Same bytes used in two roles require two logical artifact records. Mutable
status files (`PROGRAM_STATUS.md`, heartbeat, aggregates) use logical identity
with changing content versions.

### Mutability classes

| Class | Rule |
|---|---|
| `IMMUTABLE_EVIDENCE` | Bytes/hash frozen; replacement => new artifact version |
| `APPEND_ONLY_JOURNAL` | Entries append-preserving; range/checkpoint hashes |
| `REGENERABLE_OUTPUT` | Generator + inputs identified |
| `MUTABLE_STATUS` | Current projection may change; historical accepted versions recoverable |
| `EPHEMERAL_SCRATCH` | Not acceptance evidence |
| `CACHE` | Reconstructable only |

### Append semantics

| Term | Definition |
|---|---|
| `PHYSICAL_APPEND_ONLY` | Storage only appends bytes within the active segment; prior committed bytes are not rewritten in place; truncation/compaction of active segment forbidden; rotation to immutable segments permitted when contract declares segment immutability |
| `LOGICAL_APPEND_ONLY` | Prior records remain recoverable from an authoritative history source; consumers can reconstruct history without overwriting earlier facts |

A mutable aggregate alone is **not** `LOGICAL_APPEND_ONLY`. EVIDENCE
`CAMPAIGN_RUNTIME_STATE.json` is `MUTABLE_STATUS` backed by physically
append-only journals. Assistant `conversations.json` is neither physically nor
durably logically append-only.

### Durability dimensions (orthogonal)

| Dimension | Question |
|---|---|
| Write pattern | append, replace, journal+aggregate |
| Acknowledged durability | fsync/flush/replica ack where claimed |
| Crash consistency | atomic rename, valid prefix, tail unclosed |

`fsync` on a writer does not by itself guarantee cross-host durability or
survive all failure modes unless the contract says so.

### Partial artifacts

Mark `PARTIAL`, `COMPLETE`, or `UNKNOWN` completeness; producer attempt;
terminal execution state; validation state; use restriction. Partial artifacts
MUST NOT satisfy accepted-output requirements without explicit narrowed
acceptance review.

### Retention classes

`RET_EPHEMERAL`, `RET_BOUNDED_DIAGNOSTIC`, `RET_OPERATIONAL`,
`RET_REPRODUCIBILITY`, `RET_HISTORICAL_EVIDENCE`, `RET_AUTHORITY_POLICY`.
Durations are policy-owned; this milestone defines classes only.

### Redaction

Secret-sensitive data MUST NOT reach unauthorized durable logs/artifacts.
Redaction MUST occur before durable write for C2+. In-memory handling before
durable emission is permitted. Later scrub is insufficient for governed
evidence.

## Observability requirements for canonical standard

The `OBSERVABILITY_STANDARD.md` must define, without overlapping run lifecycle
ownership:

- record kinds: diagnostic log, audit record, domain event, evidence artifact,
  metric, trace span, health state, test result;
- structured log minimum envelope: UTC timestamp, severity, component,
  event code, safe message, run/attempt/trace/correlation refs when applicable;
- metrics: kind, unit, window, bounded labels, sample count, loss counters;
- trace propagation requirements across process/thread/queue with missing-context
  detection;
- clocks: UTC wall, monotonic duration, provider/domain time; no wall-clock
  durations when monotonic available;
- latency stages for RT-01 applicability list with exact boundaries;
- consequence-aware recording behavior referencing run profiles.

Logs are not automatically evidence.

## Evaluation requirements for canonical standard

The `TEST_AND_EVALUATION_STANDARD.md` must define:

- validation runs referencing `tools/validation_manifest.json` and
  `tools/validate.py` including `full_suite_required`, selection mode, pass/fail/
  skip/error counts, attempts, and `PASS_WITH_RETRY` semantics;
- benchmarks: existing runner foundation, comparability tri-state
  (`COMPARABLE`, `CONDITIONALLY_COMPARABLE`, `NOT_COMPARABLE`), mandatory
  equality dimensions, sample count, median/mean/min/max from current runner,
  p95/p99 only when justified;
- backtest, replay (with timing mode), simulation, paper, provider smoke origins,
  training, model evaluation ladder, experiment, research, AI evaluation;
- valid negative result preservation;
- research applicability: informal scratch vs consequential cited research.

Benchmark gating and performance budgets are out of scope.

## Operational semantics (owned by run standard)

- failure reason families as in design;
- idempotency classes: `IDEMPOTENT`, `IDEMPOTENT_WITH_KEY`,
  `CONDITIONALLY_IDEMPOTENT`, `NON_IDEMPOTENT`; retryable ≠ idempotent;
- retry policy owned by operation authority; no global max attempts;
- typed incident/defect/debt/limitation links without requiring one registry;
- documentation/acceptance flow proportional to consequence.

## AI operations constraints

AI attribution ≠ AI reproducibility. Record provider/model, template/version
reference, tools, sources, cutoff, actual structured output, authority mode.
No hidden chain-of-thought. Authority modes are read-only (`RESEARCH_ONLY`,
`ADVISORY`, `STRUCTURED_ANALYSIS`, `WORKFLOW_ORCHESTRATION`). No AI trading,
risk, release, qualification, or execution authority.

## Disposition examples

These examples are normative for canonical prose and MUST remain consistent with
the outcome/disposition model above.

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

## Applicability matrix

Legend: `M` mandatory; `C` mandatory when applicable/material; `R` reference
existing domain authority; `—` normally not required. `Src` includes dirty-state
attribution. `Obs` = required structured logs/metrics/trace per profile, not
every telemetry kind.

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

## Consequence matrix

| Dimension | `C0` | `C1` | `C2` | `C3` | `C4` |
|---|---|---|---|---|---|
| Durability | Best effort | Durable by run close | Required records before disposition | Append-preserving evidence before acceptance | Idempotent durable intent/audit before side effect |
| Recording timing | Async/batched; sampling allowed | Buffered/async with bounded loss | Required refs before disposition | Required evidence before acceptance | Pre-effect boundary |
| Loss tolerance | High; counters required | Bounded declared loss | No silent loss of required records | Required records never sampled/dropped | Zero tolerance for authority-record loss |
| Retention baseline | `RET_EPHEMERAL` / `RET_BOUNDED_DIAGNOSTIC` | `RET_BOUNDED_DIAGNOSTIC` / `RET_OPERATIONAL` | `RET_REPRODUCIBILITY` | `RET_HISTORICAL_EVIDENCE` | `RET_AUTHORITY_POLICY` |
| Redaction | Secrets never persisted | Secrets never persisted | Full omission + sensitive-field policy | Evidence-grade before durable write | Authority-grade; credential refs only when needed |
| Audit strength | Diagnostic | Operational attribution | Governed review/reproducibility | Acceptance evidence | Authority/execution audit + reconciliation |

Representative failure defaults:

| Operation class | Profile | Recording failure default | Hot-path note |
|---|---|---|---|
| Hot model inference span | `C0` | Continue degraded | Sampling/async permitted |
| Changed/local validation | `C1` | Continue degraded or invalidate observability claims | Report replacement acceptable; preserve attempts when material |
| Provider smoke / research / benchmark | `C2` | Invalidate or defer if required artifact missing | Report durable before disposition |
| Release / promotion / qualification evidence | `C3` | Fail closed for acceptance | No acceptance without durable hashes/records |
| Future execution / risk side effect | `C4` | Fail closed; reconcile uncertain external effects | Telemetry delay only outside authority boundary |

Implementation MUST embed these matrices in canonical standards with the review
corrections above. EVIDENCE row remains `R` reference only.

## Three canonical standards to create

Implementation creates exactly:

### `docs/platform/REPRODUCIBILITY_AND_RUN_STANDARD.md`

| Attribute | Value |
|---|---|
| Canonical subject | Run, attempt, execution, outcome, disposition, relationships, identity, artifacts, retention/redaction, retry/resume/checkpoint/cancellation, consequence profiles |
| Excludes | Log/metric/trace envelopes; evaluation protocols |
| Must include | All hardened semantics in this specification under run/artifact/operational headings |

### `docs/platform/OBSERVABILITY_STANDARD.md`

| Attribute | Value |
|---|---|
| Canonical subject | Logs, audit/events, metrics, traces/correlation, clocks, latency stages, propagation, loss/degraded behavior |
| Excludes | Run lifecycle; evaluation validity |
| References | Run IDs and consequence profiles from run standard |

### `docs/platform/TEST_AND_EVALUATION_STANDARD.md`

| Attribute | Value |
|---|---|
| Canonical subject | Validation, benchmark comparability, replay/simulation/backtest, provider smoke, model evaluation, experiment, research, AI evaluation |
| Excludes | Redefining provenance or trace identity |
| References | Provenance and observability requirements |

No fourth operational standard.

## Narrow existing-document updates allowed

| File | Permitted change |
|---|---|
| `docs/platform/README.md` | Add navigation entries for three standards |
| `docs/platform/MASTER_ARCHITECTURE.md` | Reference accepted standards; keep Operating Fabric `PARTIAL` until OF-01 |
| `docs/platform/PROGRAM_STATUS.md` | Mark REBASE-02 complete only after implementation acceptance |
| `docs/platform/MASTER_ROADMAP.md` | Advance ownership to OF-01 / parallel-safe RT-01/XA-01 |
| `docs/platform/CANONICAL_TRUTH_MAP.md` | Route subjects to new standards |
| `docs/platform/DOCUMENTATION_STANDARD.md` | Reference consequence-based acceptance and drift expectations |
| `docs/platform/GLOSSARY.md` | Add controlled terms from this specification |

`SYSTEM_BOUNDARIES.md`, `AUTHORITY_MODEL.md`, and
`DATA_AND_EPISTEMIC_MODEL.md` MUST NOT receive semantic redesign. Link-only
updates are permitted only if navigation otherwise breaks.

`MASTER_ARCHITECTURE.md` does not require structural rewrite; navigation/reference
update is sufficient.

## EVIDENCE isolation

```text
EVIDENCE-01C new dependency introduced: NO
EVIDENCE semantics changed: NO
```

No retrofit of universal run IDs into frozen EVIDENCE artifacts. Future OF-02 may
index/reference without rewriting.

## Downstream handoffs

| Milestone | Depends on REBASE-02 | Contract |
|---|---|---|
| IMP-OF-01 | Yes | Durable run/attempt/outcome/disposition + artifact linking |
| IMP-OF-02 | Yes (via OF-01 indexing) | Adapters; no history rewrite |
| IMP-RT-01 | Yes (parallel-safe after REBASE-02) | Trace/latency/baseline; attaches to OF-01 identity |
| IMP-XA-01 | Yes (parallel-safe after REBASE-02) | Provenance/temporal/evaluation contracts |
| IMP-OF-03 | Yes | Workflow/SOP/capability/incident/debt links |
| IMP-AI-01 | Yes (OF-01 attribution) | Non-authoritative attributable AI |

REBASE-02 implementation is not a prerequisite for EVIDENCE-01C execution.

## Implementation scope

### Create

```text
docs/platform/REPRODUCIBILITY_AND_RUN_STANDARD.md
docs/platform/OBSERVABILITY_STANDARD.md
docs/platform/TEST_AND_EVALUATION_STANDARD.md
artifacts/imp-rebase/REBASE02/README.md
artifacts/imp-rebase/REBASE02/REBASE02_ACCEPTANCE_REPORT.md
artifacts/imp-rebase/REBASE02/REBASE02_KNOWN_LIMITATIONS.md
artifacts/imp-rebase/REBASE02/REBASE02_FILE_HASHES.json
```

### Modify (only)

```text
docs/platform/README.md
docs/platform/MASTER_ARCHITECTURE.md
docs/platform/PROGRAM_STATUS.md
docs/platform/MASTER_ROADMAP.md
docs/platform/CANONICAL_TRUTH_MAP.md
docs/platform/DOCUMENTATION_STANDARD.md
docs/platform/GLOSSARY.md
```

### Protected (no modifications)

```text
artifacts/imp-rebase/REBASE00/**
artifacts/imp-rebase/REBASE01/**
accepted BUILD/Phase/closure/EVIDENCE frozen artifacts and policies
prediction/settlement/risk/execution/release-governance authorities
src/** (runtime)
tools/validation_manifest.json semantics
EVIDENCE campaign code semantics and frozen records
```

### Explicitly forbidden

```text
Run Ledger runtime
database schema
artifact registry runtime
trace backend / OpenTelemetry integration
structured logging backend
benchmark gating
workflow engine
SOP/incident/debt registry implementation
data/model registry implementation
cross-asset runtime
AI runtime
provider/execution/risk changes
EVIDENCE semantic changes
overwrite of accepted REBASE-02 design file
```

## Acceptance evidence

Create only:

```text
artifacts/imp-rebase/REBASE02/README.md
artifacts/imp-rebase/REBASE02/REBASE02_ACCEPTANCE_REPORT.md
artifacts/imp-rebase/REBASE02/REBASE02_KNOWN_LIMITATIONS.md
artifacts/imp-rebase/REBASE02/REBASE02_FILE_HASHES.json
```

Package contracts:

- `README.md`: scope, non-authority statement, navigation;
- `REBASE02_ACCEPTANCE_REPORT.md`: implementation-base identity, document map,
  canonical non-overlap matrix, protected-history result, terminology
  consistency result, EVIDENCE independence confirmation, validation attempt
  history, hash verification, Git disposition, final milestone state
  `IMP_REBASE_02_COMPLETE` or `IMP_REBASE_02_COMPLETE_WITH_LIMITATIONS`;
- `REBASE02_KNOWN_LIMITATIONS.md`: program limitations vs milestone execution
  limitations;
- `REBASE02_FILE_HASHES.json`: SHA-256 manifest excluding itself.

Hash manifest covers:

- three new canonical standards;
- seven modified `docs/platform/` files;
- this implementation specification;
- three other REBASE02 acceptance files (not the manifest).

Sort by repository-relative POSIX path; include path, byte length, lowercase
SHA-256.

## Validation for implementation

Run in order; record every attempt in the acceptance report:

1. allowed-path check vs implementation-base commit;
2. local Markdown link/path check from all new/modified docs;
3. JSON parse and hash-schema check for acceptance manifest;
4. terminology consistency check across three standards and glossary;
5. canonical non-overlap check (run vs observability vs evaluation ownership);
6. EVIDENCE dependency scan (no new dependency, no semantic drift);
7. protected-history diff check;
8. mutable-value shadowing scan for copied thresholds/counts/policy IDs;
9. `git diff --check` before staging and `git diff --cached --check` after;
10. repository validation:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py changed --explain
```

Run `full` only when `full_suite_required=true` or policy requires it. No live
provider tests unless changed-path policy requires them.

## Worktree and Git discipline

Implementation MUST:

1. start from the review-complete HEAD on a new clean branch/worktree;
2. not reuse the dirty original checkout or stale `docs/imp-rebase-01`
   premature worktree;
3. stage explicit paths only; never `git add .`;
4. make one coherent documentation-only commit;
5. not push, merge, or amend design/review commits.

Review commit subject:

```text
docs(architecture): finalize IMP-REBASE-02 implementation spec
```

## Deferred implementation choices (not semantic gaps)

1. OF-01 storage/schema/transaction/concurrency;
2. RT-01 propagation backend and exact stage wiring;
3. retention durations and legal deletion rules;
4. benchmark budgets/SLOs;
5. dirty-source capsule storage format;
6. per-source-family historical adapters.

## Acceptance criteria

IMP-REBASE-02 implementation is accepted only when all are true:

1. Three canonical standards exist with non-overlapping ownership.
2. Run boundaries, attempt rules, and material-change identity rules are explicit.
3. Outcome validity is distinct from negative analytical results.
4. Disposition append-only semantics are explicit.
5. Lifecycle terminality and `SUPERSEDED` placement are correct.
6. Relationship DAG rules match this specification.
7. Initiator/trigger/parent context separation is explicit.
8. Consequence assignment uses objective criteria; latency orthogonality preserved.
9. Fail-closed semantics apply to required-record sets only.
10. Reproducibility and evidence strength are separate dimensions.
11. Dirty-source attribution is testable and scope-aware.
12. Environment capture cannot leak secrets.
13. Artifact logical vs content identity and append/durability distinctions are explicit.
14. Benchmark foundation accurately described as existing.
15. Validation semantics reference current `validate.py` authority.
16. EVIDENCE-01C remains independent.
17. Downstream handoffs match this specification.
18. Protected paths unchanged; no runtime implementation.
19. Acceptance package and hash manifest complete.
20. Applicable validation passes with attempt history recorded.

Use `IMP_REBASE_02_COMPLETE` when all pass. Use
`IMP_REBASE_02_COMPLETE_WITH_LIMITATIONS` only for explicit nonblocking
milestone-execution limitations. Otherwise `IMP_REBASE_02_NOT_COMPLETE`.

## Implementation base for downstream work

```text
The REBASE-02 standards implementation MUST use a new clean worktree from:
<review-complete final HEAD of docs/imp-rebase-02-spec-review>
```

Do not implement from `bc04d5e` design-only state or the dirty original
checkout.

## Review readiness

```text
IMP_REBASE_02_SPEC_APPROVED_FOR_IMPLEMENTATION
```

## Next gate

```text
IMP-REBASE-02 Clean-Worktree Standards Implementation
```
