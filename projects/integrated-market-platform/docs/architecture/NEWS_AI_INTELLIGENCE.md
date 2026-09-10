# News AI Intelligence Boundary

**Status:** Accepted — professor-directed post-G15 increment (AI intelligence stage only)

## Purpose

This document describes the canonical IMP **analysis-only** intelligence layer over curated deterministic news events. It implements the professor-directed sequence stage:

```
deterministic collection → normalization → observability → recency → source → catalyst
→ curated AI intelligence → strategy evaluation → (later) Paper forward testing
```

This document covers **only** the curated AI intelligence stage. Strategy evaluation is documented in [NEWS_STRATEGY_EVALUATION.md](NEWS_STRATEGY_EVALUATION.md).

## Architecture flow

```mermaid
flowchart LR
  A[Curated NewsArticleEvents] --> B[IntelligenceInputPacket]
  B --> C[Versioned Prompt]
  C --> D[InferenceProvider]
  D --> E[StructuredIntelligenceOutput]
  E --> F[InferenceRecord]
```

Package: `src/market_platform_foundation/intelligence/inference/`

| Component | Role |
|-----------|------|
| `NewsIntelligenceAnalyzer` | Orchestrates as-of safety, input limits, prompt selection, provider call, validation |
| `IntelligenceInputPacket` | Self-contained curated input — no external retrieval |
| `PromptRegistry` | Governed prompt IDs, versions, deterministic hashes |
| `InferenceProvider` | Provider-neutral boundary (`FixtureInferenceProvider`, `AnthropicInferenceProvider`) |
| `IntelligenceResult` | Structured analysis output — not orders |
| `InferenceRecord` | Replay-safe audit linkage |
| `IntelligenceReplayHarness` | Fixture replay through news filter + inference |

## Intelligence input contract

`IntelligenceInputPacket` preserves:

- **Identity:** `input_id`, source `NewsArticleEvent` IDs
- **Time:** `as_of`, per-article publication/retrieval times
- **Provenance:** source IDs, catalyst matches, policy versions, source trust tier
- **Market context:** canonical instrument IDs (multi-asset; not MES-specific)
- **Content:** headline, normalized summary, deterministic catalyst IDs
- **Policy:** prompt ID/version/hash, task type, model policy, output schema version
- **Limits:** candidate vs supplied counts, truncation flag/reason
- **Reproducibility:** deterministic `input_hash`

## Structured output contract

`StructuredIntelligenceOutput` / `IntelligenceResult`:

| Field | Semantics |
|-------|-----------|
| `sentiment_label` | Bounded enum: `VERY_BEARISH` … `VERY_BULLISH` |
| `sentiment_score` | Optional float in `[-1.0, +1.0]` |
| `catalyst_interpretation` | Model interpretation — does not overwrite deterministic matches |
| `market_impact_level` | `NONE`, `LOW`, `MODERATE`, `HIGH` — non-executable |
| `impact_horizon` | `INTRADAY`, `SHORT_TERM`, `MEDIUM_TERM`, `UNKNOWN` |
| `model_confidence` | `ConfidenceKind.MODEL_REPORTED_CONFIDENCE` — **not** calibrated probability |
| `rationale`, `warnings` | Concise explanation and flags |

Schema version: `intelligence/inference/output/1.0.0`

## Task types

| Task | Purpose |
|------|---------|
| `NEWS_SENTIMENT` | Aggregate sentiment from curated articles |
| `NEWS_CATALYST_ANALYSIS` | Higher-level catalyst interpretation |
| `NEWS_MARKET_IMPACT` | Non-executable impact classification |

Explicitly excluded: `TRADE_DECISION`, `ORDER_DECISION`, position sizing, execution fields.

## Prompt governance

- Prompts live in `prompts.py` / `PromptRegistry` — not scattered in services
- Each prompt has `prompt_id`, `version`, `template`, `content_hash`
- Content changes require explicit version bump (hash changes)
- Prompts instruct: no web search, no trading authority, respect as-of, structured JSON only

## Model provider boundary

`InferenceProvider.infer(packet, rendered_prompt, config) -> ProviderInferenceResponse`

Implementations:

| Provider | ID | Network |
|----------|-----|---------|
| `FixtureInferenceProvider` | `inference.fixture` | None — required for tests/replay |
| `AnthropicInferenceProvider` | `anthropic.messages` | Live only when credentials configured |

Configuration via `IntelligenceInferenceConfig` and environment (`ANTHROPIC_API_KEY`, `ANTHROPIC_NEWS_MODEL` / `ANTHROPIC_MODEL`).

**No silent fallback to fabricated analysis on provider failure.**

## Event-time / as-of safety

Inherits news foundation observability:

- `NewsIntelligenceAnalyzer` rejects events where `retrieved_time > as_of`
- Uses `is_observable_at()` — same semantics as `NewsReplayHarness`
- Invariant: `INTELLIGENCE_INPUT_EVENTS ⊆ EVENTS_OBSERVABLE_AT_AS_OF_TIME`

## Input-size governance

- `max_articles`, `max_content_chars` in config
- Deterministic prioritization via `stable_event_order_key` (recency, source, event ID)
- Truncation recorded on input packet (`truncated`, `truncation_reason`)

## Replay and provenance

`IntelligenceReplayHarness`:

```
fixture events + as_of + pipeline config + fixture provider → InferenceRecord
```

Records link: article IDs, as-of, prompt hash/version, provider/model, input hash, structured result, raw response hash (not full payload).

Idempotency: `InMemoryInferenceRecordRepository` caches by input hash + prompt hash + provider + model + config hash.

Durable persistence deferred — clean repository interface provided.

## Observability

`InferenceObservability` tracks (non-sensitive): task type, provider, latency, tokens, parse success/failure, cache hits.

Does not log API keys, auth headers, or full prompts/responses by default.

## Safety boundary

| Authority | Status |
|-----------|--------|
| Raw news collection by AI | **NONE** |
| Market data fetch by AI | **NONE** |
| Broker execution | **NONE** |
| Paper order submission | **NONE** |
| Live order submission | **NONE** |
| MODE_AUTHORITY changes | **NONE** |
| Strategy signals | **NONE** (inference increment; see strategy evaluation doc) |

## Donor traceability

| Donor concept | Audit verdict | Canonical treatment |
|---------------|---------------|---------------------|
| Direct Anthropic from strategy | REJECT | Provider behind `intelligence/inference/` |
| Donor prompts | REFERENCE ONLY | Reimplemented governed prompts |
| Single daily Claude call | ADAPT | Task-oriented requests with provenance |
| Manual prompt A/B | ADAPT | Replay-safe input/prompt/model records |

## Known limitations

- Live Claude validation requires external credentials (`CLAUDE_LIVE_VALIDATION_NOT_RUN_EXTERNAL_CREDENTIAL_BLOCKER` when absent)
- No empirical calibration of model confidence
- Strategy evaluation implemented in separate increment; Paper forward testing still deferred
- No durable inference persistence (in-memory repository only)
- Software validation does **not** prove predictive alpha

## INT-012 status

**PARTIALLY_INTEGRATED** — canonical concepts adapted (deterministic filtering, curated AI boundary, Claude evaluation path). Donor trading system (Tradovate/CDP/MES executor) remains **NOT integrated**.

## Related

- [NEWS_EVENT_FOUNDATION.md](NEWS_EVENT_FOUNDATION.md)
- [ADR-0010](adr/0010-news-catalyst-deterministic-foundation.md)
- [ADR-0011](adr/0011-news-ai-intelligence-boundary.md)
- [CCN forensic audit](../audits/post-g15-professor-directed/CCN_FORENSIC_AUDIT_2026-09-09.md)
