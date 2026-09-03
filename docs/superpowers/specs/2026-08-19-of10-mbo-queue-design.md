# OF10 — MBO / Queue Semantics (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Capability-gated MBO contracts, FIFO queue reconstruction, queue-position estimates, execution-forecast queue upgrade  
**Prerequisites:** OF9 IMPLEMENTED

## 1. Purpose

Model displayed order-queue semantics from admitted MBO fixture data. Upgrade execution forecasts from `queue_model_version: "none"` when MBO is available. Fail closed when MBO is absent — never claim exact queue position without sequence numbers.

## 2. Contracts

| Contract | Role |
|---|---|
| `MboOrder` | Individual resting order with `order_id`, `price`, `size`, `side`, `sequence`, `timestamp` |
| `QueueSnapshot` | Per-price FIFO queues at one `event_time` |
| `QueuePositionEstimate` | Heuristic position for a hypothetical passive order |

`capability_tier` must be `MBO` when MBO data drives the feature.

## 3. Queue method

- Method: `fifo_displayed_mbo_v1`
- Version: `1`
- FIFO ordering within each price level by `sequence`
- No exact queue claim when `sequence` missing on any order at level → `SEQUENCE_INCOMPLETE` quality flag

## 4. Execution forecast integration

When MBO snapshot present:

- `queue_model_version = fifo_displayed_mbo_v1`
- Passive fill probability adjusted by queue depth ahead at touch
- L2-only path retains `queue_model_version: none` + `MBO_UNAVAILABLE` quality flag

## 5. Fixture

`ADMITTED-MBO-ES-001` — synthetic ES MBO orders aligned to `ADMITTED-L2-ES-001` snapshot times. `snapshot_provenance: fixture_synthetic`.

## 6. Out of scope

- Live MBO vendor feeds
- Hidden liquidity / iceberg confirmation
- Cross-venue queue consolidation

## 7. Completion definition

OF10 complete when MBO fixture ingests deterministically, queue module passes capability/PIT tests, execution forecast reports versioned queue model when MBO present, ES workspace exposes queue summary fields, and full test suite remains green.
