# IMP observability standard

| Field | Value |
|---|---|
| Document ID | `IMP-OBSERVABILITY-STANDARD` |
| Classification | `CANONICAL` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Diagnostic logs, audit records, domain events, metrics, traces, correlation, clocks, latency stages, propagation, and observability degradation |
| Establishing Milestone | `IMP-REBASE-02` |
| Version | `1.0` |
| Last Verified | `2026-08-27` |
| Supersedes | Fragmented logging, metrics, and trace conventions across subsystems |
| Superseded By | None |

This standard defines how IMP represents diagnostic and operational visibility
without conflating observability records with run lifecycle, evaluation
validity, or authority. It is semantics and governance only. It does not
implement a trace backend, OpenTelemetry exporter, structured logging backend,
or metrics platform.

Normative language governs future implementations and canonical prose. It does
not claim current repository-wide compliance.

## Scope and exclusions

This standard owns record-kind definitions, structured log minimum envelope,
metric semantics, trace and span identity, correlation identity, clock and
latency semantics, cross-process context propagation requirements, and
consequence-aware observability degradation behavior.

This standard does **not** own:

- run lifecycle, attempt history, outcome, or disposition — see
  [Reproducibility and Run Standard](REPRODUCIBILITY_AND_RUN_STANDARD.md);
- validation, benchmark, or evaluation protocol success — see
  [Test and Evaluation Standard](TEST_AND_EVALUATION_STANDARD.md);
- EVIDENCE qualification or campaign semantics.

This standard references `run_id`, `attempt_id`, and consequence profiles from
the run standard. It does not redefine them.

## Record kinds

These kinds MUST remain distinct. They MUST NOT collapse into one generic
“event” type.

| Kind | Purpose | Is automatically evidence? |
|---|---|---|
| Diagnostic log | Troubleshooting and operator context | No |
| Audit record | Evidence of consequential governed action | Only when declared by owning authority |
| Domain event | Market, system, or business fact | No |
| Evidence record or artifact | Supports an evaluation or acceptance claim | Yes when accepted under protocol |
| Metric | Aggregated quantitative observation | No |
| Trace span | Timed segment within a causal processing path | No |
| Health state | Current component or service health projection | No |
| Test result | Outcome of a named test within a validation run | Governed by evaluation standard |

**Logs are not automatically evidence.** An audit record is not a metric. A
trace is not a run. A domain event is not automatically a disposition.

## Identifier distinctions

| ID | Meaning |
|---|---|
| `run_id` | Consequential logical objective (defined in run standard) |
| `attempt_id` | Bounded technical execution within run (defined in run standard) |
| `event_id` | Discrete domain, business, or system fact |
| `trace_id` | One causal processing path |
| `span_id` | Timed segment within a trace |
| `correlation_id` | Groups related records without asserting strict causality |

These MUST NOT be aliases.

### Trace

A **trace** represents one causal processing path. It MAY fan out to child spans
and MAY later contribute to fan-in downstream state. Not every stage MUST
become a run. Traces MAY cross run boundaries; runs MAY contain many traces.

### Correlation

A **correlation identity** MAY group related events, runs, traces, orders, and
predictions that are not necessarily one strict causal trace. Correlation does
not prove causality. Fan-out and fan-in MUST be representable without forcing
one global tree.

## Structured diagnostic logs

Minimum semantic envelope (serialization format is not frozen):

| Field | Requirement |
|---|---|
| time | UTC timestamp with declared precision |
| component | Emitting subsystem or service identity |
| severity or category | Declared severity or category |
| message or event code | Stable code preferred over free text alone |
| structured attributes | Safe key-value context |
| run or attempt refs | When applicable and known |
| trace refs | `trace_id`, `span_id`, `correlation_id` when applicable |

Secrets, tokens, passwords, and raw credentials MUST NOT appear in durable
diagnostic logs for `C2+` work. Redaction MUST occur before durable write.

## Audit records

An **audit record** documents a consequential governed action: who or what
initiated it, what action occurred, what authority applied, and what durable
effect or decision resulted. Audit records MAY be required evidence at `C3` or
`C4` depending on operation class. Audit record failure policy follows the
required-record set for the consequence profile in the run standard.

## Domain events

A **domain event** is a typed market, system, or business fact (for example,
session open, observation received, order submitted, reconciliation mismatch).
Domain events MAY reference `run_id`, `trace_id`, and `correlation_id` but are
not runs themselves.

## Metrics

Metrics MUST declare where applicable:

| Dimension | Requirement |
|---|---|
| kind | counter, gauge, histogram, or declared equivalent |
| unit | canonical unit or dimensionless declaration |
| aggregation | how values are combined |
| sample or window | time window or population scope |
| clock | wall, monotonic, or provider time as applicable |
| population | what is included and excluded |
| sample count | preserved for distribution summaries |
| loss counters | when sampling or drop occurs |

`p95` and `p99` quantiles MUST be reported only when sample count and protocol
justify them. Tiny sample counts MUST NOT imply meaningful tail quantiles.

Metrics are aggregated observations. They do not by themselves establish run
outcome or disposition.

## Trace propagation

Future runtime implementation (`IMP-RT-01`) MUST preserve trace and correlation
context across threads, queues, processes, and message buses where applicable.
Context loss SHOULD be detectable (for example, missing parent span reference or
explicit `context_lost` marker).

No tracing backend is implemented by this milestone. Propagation requirements
are semantic contracts for downstream work.

## Clock semantics

Different clock kinds MUST NOT be conflated:

| Clock kind | Typical use |
|---|---|
| UTC wall clock | Human-readable timestamps, cross-system correlation |
| Monotonic clock | Durations and latency within one process |
| Provider timestamp | Source-declared event time |
| Received timestamp | Platform receipt time |
| Available time | Temporal eligibility per existing contracts |
| Processed timestamp | Completion or normalization time |

Use monotonic clocks for durations where possible. Reference existing clock-drift
authority where applicable. Wall-clock durations MUST NOT be used when monotonic
measurement is available for the same interval.

Existing temporal law `available_time_ns <= decision_time_ns` remains controlling
for decision-time eligibility. This standard does not invent a competing temporal
framework.

## Latency semantics

Latency attribution SHOULD support future stage labeling such as:

```text
provider
transport
queue
adapter
normalization
feature
model
opportunity
risk
order build
broker
UI/human
```

No pipeline needs every field. Stages are semantic labels for measurement, not
run identities. Exact wiring is owned by `IMP-RT-01`.

## Consequence class and latency orthogonality

Consequence profile (`C0`–`C4`) and latency or storage shape (`HOT`, `WARM`,
`COLD`) are orthogonal. All combinations are valid:

| Example | Consequence | Latency shape |
|---|---|---|
| Hot-path debug span | `C0` | `HOT` |
| Hot-path authority-critical pre-submit audit | `C4` | `HOT` |
| Cold evidence archive indexing | `C3` | `COLD` |
| Cold low-consequence research scratch | `C0` or `C1` | `COLD` |

## Consequence-aware recording behavior

Observability behavior MUST align with consequence profile from the run
standard:

| Profile | Diagnostic telemetry | Required audit or evidence records |
|---|---|---|
| `C0` | Sampling and async batching permitted; loss counted | Not required |
| `C1` | Buffered or async with bounded declared loss | Operational attribution when material |
| `C2` | Required structured context before disposition | Governed artifacts per operation class |
| `C3` | Must not block acceptance when required evidence is durably present elsewhere | Required evidence records before acceptance |
| `C4` | Telemetry delay permitted outside authority boundary | Authority records before side effect |

Failure to emit optional diagnostic telemetry MUST NOT automatically invalidate
a `C3` acceptance when required evidence artifacts and hashes are durably
present. Failure to persist required authority or evidence records follows the
fail-closed rules in the run standard.

## Hot-path protection

Observability MUST NOT require synchronous giant provenance writes per tick,
database roundtrips per span, or full artifact manifests per event on hot paths.
Supported patterns include lightweight event or trace emission, bounded
buffering, asynchronous persistence, and stronger durability only for required
evidence or authority records.

## Observability degradation

When sinks are unavailable or overloaded:

- `C0` and `C1`: continue degraded; increment loss counters;
- `C2`: MAY invalidate or defer result if required observability context for
  disposition is missing;
- `C3`: fail closed for acceptance if required evidence records are missing;
  nonessential telemetry loss alone does not block acceptance;
- `C4`: fail closed for authority effect; reconcile uncertain external effects.

Degradation behavior is declared per operation class. This standard defines
semantics, not universal runtime policy.

## Downstream handoffs

| Milestone | Contract from this standard |
|---|---|
| `IMP-RT-01` | Implement trace propagation, correlation, latency-stage instrumentation, benchmark baseline measurement |
| `IMP-OF-01` | Attach trace and correlation references to durable run records where required |
| `IMP-AI-01` | Attribute AI operations with structured context without chain-of-thought capture |

## EVIDENCE isolation

This standard does not change EVIDENCE semantics, qualification thresholds, or
frozen campaign record meaning. EVIDENCE observability remains under existing
EVIDENCE authority.

## Repository foundations (informational)

Existing logging and health primitives across subsystems provide partial
foundations. End-to-end trace propagation, accepted benchmark baseline, and
universal correlation contract remain future work under `IMP-RT-01`. This
standard describes target semantics; it does not claim a trace backend exists.
