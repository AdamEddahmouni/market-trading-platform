# ADR 0003: Deterministic Replay

## Context

Point-in-time behavior cannot be tested when execution depends on provider state, wall time, sleep, or unstable ordering.

## Decision

Replay validated JSONL through a simulated clock using effective time, source time, sequence, and ID ordering. Strict mode rejects disorder; normalized mode records corrections. Results are canonically serialized and hashed.

## Consequences

Fixtures become stable regression evidence. Consumers are intentionally in-memory and synchronous in Phase 1A.

## Rejected alternatives

Wall-clock pacing adds nondeterminism. File order alone cannot normalize mixed sources. Silently sorting would hide fixture defects.

