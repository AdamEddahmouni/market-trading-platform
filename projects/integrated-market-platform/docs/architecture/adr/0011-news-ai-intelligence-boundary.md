# ADR-0011: News AI Intelligence Boundary

*Status: Accepted — professor-directed post-G15 increment*

## Context

ADR-0010 established deterministic news collection, filtering, and read-only `NewsIntelligenceService`. The CCN donor audit (SRC-006) rejected direct strategy-to-Anthropic coupling and required:

- Deterministic preprocessing before AI
- Curated inputs only
- Versioned prompts and structured outputs
- Claude evaluation behind canonical boundaries
- Zero execution authority

IMP already had:

- `intelligence/` routing with `NEWS_EVENT → NARRATIVE_SENTIMENT` (inactive detector)
- `assistant/anthropic_inference.py` for MRA research (free-text, separate plane)
- No intelligence-plane prompt registry or structured news inference contracts

## Decision

Add `src/market_platform_foundation/intelligence/inference/` with:

1. `IntelligenceInputPacket` — self-contained curated news input with deterministic hash
2. `IntelligenceResult` / `StructuredIntelligenceOutput` — bounded sentiment, impact, catalyst interpretation
3. `PromptRegistry` — versioned prompts with content hashes
4. `InferenceProvider` protocol — `FixtureInferenceProvider` (required) + `AnthropicInferenceProvider`
5. `NewsIntelligenceAnalyzer` — analysis-only orchestration
6. `InferenceRecord` + `InMemoryInferenceRecordRepository` — replay-safe provenance
7. `IntelligenceReplayHarness` — deterministic fixture replay

Do **not**:

- Copy donor Anthropic architecture or prompts
- Add broker/Paper/Live execution paths
- Introduce strategy signal contracts
- Accept unstructured model text as canonical truth

## Consequences

### Positive

- Professor-directed AI analysis stage complete over curated news
- Provider-neutral boundary enables future OpenAI/Gemini/local adapters
- Replay-safe records enable later calibration and prompt comparison
- Tests run without external AI credentials

### Negative / deferred

- Durable inference persistence not implemented (interface only)
- BUILD 09 `NEWS_EVENT` detector still inactive (separate wiring increment)
- No empirical confidence calibration
- Live Claude smoke test blocked without configured credentials

## Safety

- MODE_AUTHORITY unchanged
- `IntelligenceResult.execution_authority = False` always
- Malformed provider responses fail explicitly — no fabricated success
- Model confidence labeled `MODEL_REPORTED_CONFIDENCE` only

## INT-012

Governed status: **PARTIALLY_INTEGRATED** (concepts only; donor executor not integrated).

## References

- [NEWS_AI_INTELLIGENCE.md](../NEWS_AI_INTELLIGENCE.md)
- [ADR-0010](0010-news-catalyst-deterministic-foundation.md)
- [CCN forensic audit](../../audits/post-g15-professor-directed/CCN_FORENSIC_AUDIT_2026-09-09.md)
