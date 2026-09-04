# IMP test and evaluation standard

| Field | Value |
|---|---|
| Document ID | `IMP-TEST-EVALUATION-STANDARD` |
| Classification | `CANONICAL` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Validation, benchmarking, comparability, backtest, replay, simulation, provider smoke, model training and evaluation, experiment, research, and AI evaluation |
| Establishing Milestone | `IMP-REBASE-02` |
| Version | `1.0` |
| Last Verified | `2026-08-27` |
| Supersedes | Fragmented test, benchmark, and evaluation conventions across subsystems |
| Superseded By | None |

This standard defines how IMP represents, attributes, and judges tests,
validations, benchmarks, backtests, replays, simulations, provider smoke runs,
model training and evaluation, experiments, research, and AI operations. It is
semantics and governance only. It does not supersede executable validation
authority, implement benchmark gating, or create experiment or model registries.

Normative language governs future implementations and canonical prose. It does
not claim current repository-wide compliance.

## Scope and exclusions

This standard owns evaluation protocol semantics, benchmark comparability,
backtest and replay distinctions, provider smoke origin classes, model
evaluation ladder, experiment structure, research applicability, AI evaluation
attribution, and valid negative-result preservation.

This standard does **not** own:

- run lifecycle, attempt, or disposition definitions — see
  [Reproducibility and Run Standard](REPRODUCIBILITY_AND_RUN_STANDARD.md);
- log, metric, or trace envelopes — see
  [Observability Standard](OBSERVABILITY_STANDARD.md);
- EVIDENCE qualification policy or campaign semantics.

This standard references provenance and observability requirements from those
standards. It does not redefine them.

## Valid negative results

```text
EXECUTION SUCCESSFUL
+ EVIDENCE VALID
+ HYPOTHESIS REJECTED
```

is a valid result. Negative analytical outcomes MUST be preserved. A model that
validly underperforms, a benchmark that validly regresses, or a hypothesis that
is validly rejected MUST NOT be erased or relabeled as execution failure.

## Validation

Repository validation is governed by executable authority:

- [`tools/validation_manifest.json`](../../tools/validation_manifest.json)
- [`tools/validation_manifest.py`](../../tools/validation_manifest.py)
- [`tools/validate.py`](../../tools/validate.py)
- [`.github/workflows/imp-validate.yml`](../../.github/workflows/imp-validate.yml)

This standard standardizes attribution around that behavior. It does not
supersede it.

### Validation run semantics

A validation run is a consequential run when acceptance-bound (`C2` or `C3`).
At applicable consequence levels, validation runs SHOULD support:

| Field | Description |
|---|---|
| suite identity | Selected suite IDs from manifest |
| command | Invocation command and mode (`changed`, `full`, etc.) |
| source identity | Commit, branch, dirty-state attribution |
| environment | Material runtime and dependency context |
| attempts | Preserved attempt history |
| collected | Tests collected |
| passed | Tests passed |
| failed | Tests failed |
| skipped | Tests skipped |
| errors | Collection or environment errors |
| failed IDs | Identifiers of failed tests |
| duration | Elapsed time |
| artifacts | Report paths and hashes |
| outcome | Domain result under protocol |
| disposition | Governed decision |

### `full_suite_required`

`full_suite_required` is current executable validation behavior determined by
[`tools/validate.py`](../../tools/validate.py) selection logic and manifest
invalidators. This standard references it. It does not create an independent
standards-level selector.

When `full_suite_required=false`, changed-path validation is sufficient for
the applicable policy. When `full_suite_required=true`, full suite execution is
required.

### `PASS_WITH_RETRY`

When validation fails on attempt 1 due to environment failure and succeeds on
attempt 2, the disposition MUST be `PASS_WITH_RETRY`, not flattened `PASS`.
Both attempts MUST be retained.

Example:

```text
RUN: changed validation

ATTEMPT 1:
environment failure

ATTEMPT 2:
completed successfully

OUTCOME:
validation requirements satisfied

DISPOSITION:
PASS_WITH_RETRY
```

## Benchmarking

### Benchmark execution foundation

```text
benchmark execution foundation = EXISTING
universal benchmark provenance/comparability standard = ESTABLISHED BY REBASE-02
```

[`tools/benchmark.py`](../../tools/benchmark.py) is an **existing**
informational runner. Verified behavior includes:

- workloads: Python startup, tiny unittest worker, optional FAST validation
  command, and production fixture operations;
- fields recorded: `schema_version`, `report_type`, `generated_at`,
  `repository_root`, `platform`, `python_version`, `logical_cpu_count`,
  `configuration`, per-workload fixture refs, `iterations_per_sample`,
  `repeat`, sample seconds, min/median/mean/max, return codes, stdout/stderr
  byte counts, availability reasons;
- persistence: only when `--output` is supplied; atomic replace via temp file
  and `fsync`;
- gating: none; interpretation explicitly informational.

Benchmark gating and performance budgets are out of scope for REBASE-02.

### Universal benchmark semantics

Benchmark runs at `C2` SHOULD declare:

| Dimension | Requirement |
|---|---|
| benchmark identity | Stable identity for the benchmark invocation |
| workload | Named workload and fixture references |
| environment | Hardware, OS, runtime, load context |
| source | Source identity and dirty-state attribution |
| config | Semantically effective configuration |
| input | Input or fixture manifest |
| sample count | Iterations and repeats preserved |
| measurement window | Declared timing scope |
| distribution summaries | min, median, mean, max; p95/p99 only when justified |
| resource usage | Where captured |
| baseline | Reference baseline run when comparability claimed |
| comparability | `COMPARABLE`, `CONDITIONALLY_COMPARABLE`, or `NOT_COMPARABLE` |
| outcome | Domain measurement result |
| disposition | Governed decision about use of result |

### Benchmark comparability

| State | Meaning |
|---|---|
| `COMPARABLE` | All mandatory equality dimensions match within declared tolerance |
| `CONDITIONALLY_COMPARABLE` | Comparable only under stated limitations |
| `NOT_COMPARABLE` | Differences prevent valid comparison |

Differences in hardware, software version, provider, dataset, configuration, or
load MUST remain visible. A measured benchmark with `NOT_COMPARABLE` remains a
`VALID` outcome; disposition may be `VALID_RESULT_NOT_COMPARABLE`.

## Backtest

A **backtest** evaluates a strategy or model against historical data under
declared assumptions. Minimum provenance:

- strategy or model identity;
- source identity;
- data snapshot and historical availability semantics;
- time range and universe;
- fees, slippage, and execution assumptions;
- randomness controls;
- metrics and baseline;
- temporal cutoff bundle.

Lookahead contamination or temporal leakage invalidates the result (`INVALID`
outcome validity). Poor performance does not.

## Replay

A **replay** reprocesses captured or historical events under a declared timing
or order mode. Replay is distinct from backtest.

Potential timing modes:

| Mode | Meaning |
|---|---|
| original timing | Preserve inter-event timing where captured |
| accelerated timing | Compress time while preserving order |
| logical ordering only | Process in declared order without timing fidelity |

The mode MUST be declared. Replay provenance references the capture manifest and
timing mode.

## Simulation

**Simulation** uses synthetic input, counterfactual environment, or modeled
behavior. Simulation is distinct from historical replay and from paper
execution.

| Kind | Origin class |
|---|---|
| Synthetic input | Generated or fixture data |
| Counterfactual environment | Modeled external conditions |
| Historical replay | Captured event stream |
| Paper execution | Guarded simulated or sandbox execution |

Synthetic output MUST NOT masquerade as real provider evidence.

## Provider smoke

Provider smoke runs evaluate provider connectivity, capability, and data
quality under declared origin class. Record where applicable:

- provider identity;
- origin class: `REAL_PROVIDER_OBSERVED`, `MOCK`, `FIXTURE`, or `REPLAY`;
- capability and entitlement;
- symbol or universe;
- market session;
- timestamps;
- quality assessment;
- connection mode;
- limitations.

`MARKET_CLOSED` or equivalent external unavailability is not automatically a
failed provider. Use domain-aware outcome and disposition (for example,
`NOT_RUN_MARKET_CLOSED`).

## Model training

Training runs at `C2` SHOULD declare:

- model identity or family;
- source identity;
- dataset and features;
- hyperparameters and seed;
- environment including hardware;
- training cutoff;
- metrics;
- output artifacts.

This standard does not implement a Model Registry.

## Model evaluation

Evaluation categories MUST remain distinct. One evaluation type MUST NOT imply
another:

| Category | Meaning |
|---|---|
| in-sample | Training or fitting set evaluation |
| holdout | Held-out split evaluation |
| historical backtest | Historical simulation per backtest rules |
| replay | Captured event replay |
| paper | Forward paper execution |
| shadow | Parallel non-submitting observation |
| forward | Live forward observation |
| canary | Bounded live canary under authorization |

## Model promotion

REBASE-02 MAY define evidence references for promotion. It MUST NOT modify
promotion authority. Future promotion MAY reference candidate, baseline,
evaluation runs, limitations, approval, effective time, and rollback. Benchmark
or evaluation success does not grant release or trading authority.

## Experiment

One experiment MAY have multiple runs. An experiment SHOULD capture:

- question and hypothesis;
- baseline;
- planned change;
- metrics;
- success or rejection criteria;
- linked runs;
- interpretation;
- decision;
- follow-up.

This standard does not implement an Experiment Registry.

## Research

Distinguish:

| Class | Attribution requirement |
|---|---|
| informal scratch research | Minimal; not cited by system decisions |
| consequential cited research | Full governed attribution per consequence rules when cited by decisions or evidence |

Only consequential research cited by system decisions or evidence needs full
governed attribution according to applicability and consequence rules.

## AI operations and evaluation

At applicable consequence levels (`C2`), AI operations SHOULD declare:

- model and provider identity;
- model version when exposed;
- prompt or template reference;
- source and input references;
- tools and capabilities;
- temporal cutoff;
- actual output artifact;
- authority mode.

AI attribution is not AI reproducibility. A repeat MAY produce different
output. Preserve inputs, model and tool attribution, and actual produced output.
Do not claim bit-exact reproducibility unless actually supported. No
chain-of-thought capture is required.

Authority modes remain read-only. **AI output does not grant trading
authority.**

## Evaluation applicability (summary)

Detailed operation-class requirements appear in the applicability matrix in the
[Reproducibility and Run Standard](REPRODUCIBILITY_AND_RUN_STANDARD.md). Key
evaluation-specific notes:

| Operation | Evaluation notes |
|---|---|
| Unit/integration validation | `C1` routine; `C2` when acceptance-bound |
| Full validation | `C2`/`C3`; report and attempt history |
| Provider smoke | `C2`; origin class mandatory |
| Backtest | `C2`; temporal integrity mandatory |
| Replay | `C1`/`C2`; timing mode mandatory |
| Simulation/paper | `C2`; origin class mandatory |
| Performance benchmark | `C2`; comparability tri-state mandatory |
| Research / AI research | `C2`; negative results preserved |
| EVIDENCE campaign | Reference existing authority only; no retrofit |

## Downstream handoffs

| Milestone | Contract from this standard |
|---|---|
| `IMP-OF-01` | Durable evaluation run records with outcome, validity, disposition |
| `IMP-OF-02` | Adapters for validation, smoke, research without rewriting frozen records |
| `IMP-RT-01` | Benchmark baseline and measured latency for evaluation context |
| `IMP-AI-01` | Attributable non-authoritative AI evaluation under run identity |

## EVIDENCE isolation

```text
EVIDENCE-01C new dependency introduced: NO
EVIDENCE semantics changed: NO
```

EVIDENCE campaign evaluation remains under existing EVIDENCE authority. Future
indexing MAY reference EVIDENCE records without rewriting them.

## ADAPT compatibility

Future adaptive evaluation (Experience, Reflection, Lesson Candidate,
Experiment, Model Challenger, Prompt Challenger, Graph Challenger) MAY be
represented using generic experiment, run, outcome, and disposition semantics
without implementing ADAPT-specific schemas here.
