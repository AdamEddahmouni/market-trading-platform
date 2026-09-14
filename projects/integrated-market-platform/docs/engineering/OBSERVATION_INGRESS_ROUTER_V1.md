# Observation Ingress Router V1

> Deterministic in-process fan-out from normalized `EventV1` to typed production consumers — without a competing observation envelope or broker side effects.

## Related documents

- [REPLAY_RUNTIME_V1.md](./REPLAY_RUNTIME_V1.md) — downstream replay and visibility
- [INTELLIGENCE_PERSISTENCE_ARCHITECTURE_V1.md](./INTELLIGENCE_PERSISTENCE_ARCHITECTURE_V1.md) — `put_event` store lane
- [EVENT_DETECTOR_SMART_ROUTER_V1.md](./EVENT_DETECTOR_SMART_ROUTER_V1.md) — BUILD 09 detection/routing (downstream of ingress)

## Problem statement

BUILD 03 normalization already produces canonical `EventV1` records with PIT clocks and provider provenance. Production today still **couples** each source to ad-hoc persistence and side effects (replay pipeline, capture bridges, attribution materializers). There is no shared, governed **ingress dispatch** layer between “event exists” and “multiple consumers may react.”

## What is genuinely missing

| Gap | Why it blocks multi-consumer production |
|-----|----------------------------------------|
| Typed consumer registry | No stable, bounded set of lanes (`STORE`, `DETECTOR`, `OE_EVIDENCE`, `AUDIT_REPLAY`, `ENRICHMENT_TRIGGER`) with explicit required/optional semantics |
| Idempotent dispatch key | `EventV1.event_id` is stable, but callers do not share a single idempotency boundary across consumers |
| Deterministic fan-out order | Consumer invocation order must be stable for replay parity |
| Fail-closed orchestration | One required consumer failure must not leave siblings silently skipped without a receipt |
| Ingress audit journal | Replay needs an ordered dispatch receipt log separate from raw `ProviderEnvelope` capture |
| Hot-path vs async enrichment | Enrichment must schedule tokens synchronously; must not await LLM/Grok on the hot path |
| Broker-action exclusion | No subscriber may submit orders; forbidden kinds are rejected at registration |
| Observability surface | Metrics/receipts per dispatch, not only per-repository `put_event` |

This router **does not** replace `EventV1`, `ProviderEnvelope`, PIT policies, replay delivery envelopes, or BUILD 09 `SmartRouter` (detection → expert domain). It sits immediately after normalization (or replay-visible normalization) and before domain pipelines.

## Architecture

```text
ProviderEnvelope / adapter input
        │
        ▼
BUILD 03 normalization → EventV1
        │
        ▼
ObservationIngressRouter (this document)
   ├─ STORE → IntelligenceRepository.put_event
   ├─ DETECTOR → detector engine (stub or wired later)
   ├─ OE_EVIDENCE → operational evidence sink
   ├─ AUDIT_REPLAY → bounded dispatch journal
   └─ ENRICHMENT_TRIGGER → bounded trigger tokens (no await)
        │
        ▼
BUILD 05/06/09 pipelines (existing)
```

## Non-goals (V1)

- No Kafka/NATS/Redis or external broker
- No new canonical envelope type
- No automatic wiring into FTEP / OpenD capture ledger (Lane A)
- No live Grok/LLM calls on the dispatch hot path

## Contracts (implementation)

Package: `market_platform_foundation.intelligence.observation_ingress`

- `ObservationIngressRouter` — bounded idempotency cache + journal + deterministic consumer order (sorted `consumer_id`)
- `IngressDispatchReceiptV1` — per-dispatch receipt (`ING-…` identity)
- `dispatch_normalization_result` — bridge from `NormalizationResult`

## Safety

- Rejects `QualityState.INVALID` events
- Rejects forbidden consumer kinds (`BROKER_ACTION`, `EXECUTION`, `ORDER_SUBMIT`)
- `fail_closed=True` default: required consumer `FAILED` raises `IngressDispatchError`
- Journal and enrichment trigger buffers are bounded (`IngressRouterPolicyV1`)

## Proof path (V1)

`dispatch_normalization_result` + Moomoo capture normalization (existing BUILD 03 adapter) demonstrates end-to-end dispatch into store and audit lanes in unit tests.
