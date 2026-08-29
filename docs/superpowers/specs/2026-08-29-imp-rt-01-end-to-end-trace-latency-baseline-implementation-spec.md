# IMP-RT-01 implementation spec (2026-08-29)

## Stage map (executable today)

| Stage | Status | Entry | Clock |
|---|---|---|---|
| provider_event / provider_receive | REQUIRED | `push_feed._enqueue_from_payload`, fixture `feed_fixture_path` | event_time_ns, received_time_ns |
| queue | REQUIRED | `BoundedIngestQueue`, `instrument_queue_*` | process monotonic |
| normalize | REQUIRED | `live_admission.evaluate_record` | monotonic_wall_ns |
| quality | REQUIRED | admission quality observations | monotonic_wall_ns |
| canonical_state | REQUIRED | `ObservationalStateStore.apply_admitted` | event/available/received |
| feature | OPTIONAL | inline book features on depth admit | event ns |
| signal | NOT_EXECUTABLE on live ingest | intelligence replay pipeline | replay decision time |
| opportunity | OPTIONAL | shadow hook only | wall ns |
| risk / order_ready / broker | NOT_EXECUTABLE on ingest | paper submit path only | — |
| reconciliation | DEFER | offline engine | — |

## Trace model

- `trace_id`, `span_id`, `parent_span_id`, `correlation_id` distinct from `run_id` / `attempt_id`.
- Spans stored in bounded in-memory collector; export JSONL-compatible dicts.
- Structural validation before acceptance.

## Sampling

`OFF`, `FULL`, `DETERMINISTIC_SAMPLE` — domain output must remain equivalent (proven in tests).

## Baseline profiles

`receive_to_canonical_state`, `receive_to_quality`, `receive_to_feature`, `queue_wait` — all `MEASURED_BASELINE`, not SLA.

## OF-03

RT01 operator capabilities registered; snapshot hash updated in `config/of03/manifest.json`.

## Tests

`tests/rt01/test_rt01_core.py` covers vertical slice, validation faults, baseline, overhead, equivalence.
