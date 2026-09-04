# RT-01 Operations

| Field | Value |
|---|---|
| Document ID | `OPS-RT01-README` |
| Version | `1.0` |
| Status | `NORMATIVE` |
| System | `IMP-RT-01` |

IMP-RT-01 provides causal tracing and measured latency baselines for executable
runtime paths. It is observability only — not authority, not a ledger, and not
a workflow executor.

Runtime package: `src/market_platform_foundation/rt01/`.

Operator capabilities (registered in OF-03):

- `RT01.OP.STATUS`
- `RT01.OP.VALIDATE_TRACE`
- `RT01.OP.SHOW_TRACE`
- `RT01.OP.BASELINE`
- `RT01.OP.COMPARE`
- `RT01.OP.SAMPLING_STATUS`
- `RT01.OP.EXPORT`
- `RT01.OP.OVERHEAD`

```text
python -m market_platform_foundation.rt01 status --json
```

## Paper pipeline

Paper traces use one causal `TRACE_ROOT` per strategy or UI order attempt.
Child stages are `QUEUE`, `SIGNAL`, `OPPORTUNITY`, `RISK`, `ORDER_READY`,
`BROKER`, and `RECONCILIATION`. Spans carry bounded references to persisted
`signal_id`, `opportunity_id`, `risk_decision_id`, `order_id`,
`broker_order_id`, fill IDs, and reconciliation report IDs; they never carry
credentials or raw provider payloads.

The named Paper latency profiles are:

- `queue_wait`: enqueue-to-dequeue monotonic wait.
- `queue_to_signal`: queue stage to signal completion.
- `signal_to_decision`: signal stage to risk decision.
- `decision_to_submission`: risk decision to order-ready submission.
- `submission_to_broker`: order-ready to broker admission.
- `broker_to_reconciliation`: broker operation to reconciliation.
- `paper_end_to_end`: root to reconciliation terminal stage.

Run a deterministic, offline workload and baseline with:

```text
python -c "from market_platform_foundation.rt01.baseline import run_baseline; from market_platform_foundation.rt01.workloads import run_paper_trace_workload; print(run_baseline(profile_id='paper_end_to_end', workload_fn=run_paper_trace_workload, iterations=5, warmup_iterations=1))"
```

Baseline output must include the profile version, workload, sampling mode,
clock basis, iteration counts, terminal stages, and a non-zero sample count
before it is treated as measured. `NOT_EXERCISED` is the correct result when
no terminal pair was observed. Latency uses process monotonic time; provider
event, receipt, and availability timestamps remain separate metadata.

Tracing is diagnostic-only. If the collector is disabled, full, sampled, or
overflowing, Paper authority and ledger behavior remain unchanged. Broker
polling and reconciliation fail closed on unavailable or ambiguous provider
results, and read-only projections never initiate those operations.
