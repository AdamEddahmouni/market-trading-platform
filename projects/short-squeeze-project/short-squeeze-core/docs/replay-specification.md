# Replay Specification

## Loading and validation

The loader reads UTF-8 JSONL with one observation per nonblank line. Every line is parsed through schema `1.0.0`; errors identify the line. Duplicate observation IDs always fail. No network, database, credential, environment path, or current time is consulted.

## Ordering

The canonical ascending key is:

1. effective timestamp;
2. source timestamp;
3. sequence number when present (records with a sequence sort before otherwise tied records without one);
4. observation ID as the final deterministic tie-breaker.

Sequence never outranks either timestamp. Equal timestamps are allowed, and the simulated clock may remain at the same instant.

## Modes

`STRICT` accepts only input already in canonical order. It rejects invalid chronology, duplicate IDs, schema failures, and unsupported versions.

`NORMALIZED` applies the canonical sort to otherwise valid records. If the input order changes, the result contains an `INPUT_ORDER_NORMALIZED` diagnostic with the original and normalized ID sequences. Corrections are never silent. Duplicate IDs and schema errors remain fatal.

## Clock and consumers

Each replay creates a new clock with no initial time. Before emitting an observation, the engine advances the clock to its effective timestamp. Backward movement raises `ReplayValidationError`. Registered consumers receive the observation and read-only clock interface synchronously in the exact recorded order. Phase 1A consumers are in-memory only.

## Result and determinism

The result contains mode, fully ordered observations, emitted IDs, clock timestamps, and diagnostics. Canonical result bytes use sorted JSON keys, stable UTC/decimal formatting, explicit nulls, UTF-8, and no random/environment values. `result_hash` is SHA-256 over those bytes.

Given the same fixture, configuration (currently mode), and schema version, repeated replay produces the same observation order, times, diagnostics, serialization, and hash. Replay performs no sleep and does not read the wall clock.

