# Market Context Target Architecture (Deliverable 5)

**Status:** Canonical architecture specification  
**Date:** 2026-08-19  
**Code anchor:** `src/market_platform_foundation/contracts/market_context.py`

---

## Lane identity

**Market Context owns:** What information entered the market, why it matters, and how it is being incorporated.

**Market Context does not own:** Squeeze state, option fair value, futures carry, order flow calculations, or trade EV.

---

## Processing pipeline

```text
RAW INFORMATION (filings, news, social, calendars)
        ↓
SOURCE / PROVENANCE (InformationSource)
        ↓
RAW DOCUMENT (RawDocument + revision lineage)
        ↓
ENTITY RESOLUTION (EntityResolution)
        ↓
DEDUPLICATION + EVENT CLUSTERING (InformationEvent)
        ↓
FACT / EVENT EXTRACTION (typed events + spans)
        ↓
NUMERIC EXTRACTION (ExtractedMetric — deterministic math)
        ↓
BASELINE SENTIMENT + UNCERTAINTY (BaselineFinancialSentiment, TargetedSentiment)
        ↓
ECONOMIC CHANNELS (EconomicChannel mapping)
        ↓
EXPECTATION COMPARISON (ExpectationSnapshot)
        ↓
SURPRISE (SurpriseEvidence — fail-closed)
        ↓
NOVELTY + MATERIALITY + CREDIBILITY
        ↓
CATALYST (CatalystEvidence — componentized)
        ↓
ATTENTION + NARRATIVE + MACRO CONTEXT
        ↓
MARKET REACTION (consume cross-lane; MarketReactionEvidence)
        ↓
REACTION CONFIRMATION / CONTRADICTION
        ↓
CONTEXT EVIDENCE ENVELOPE → cross-lane consumers
```

---

## Core equation (research)

```text
Information Impact = f(
    Event, Novelty, Surprise, Materiality, Relevance,
    Credibility, Expectations, Attention, Narrative,
    Regime, Positioning, Market Reaction
)
```

Not implemented as a single score — components exposed individually.

---

## Layer separation

| Layer | Examples | Mutable? |
|---|---|---|
| RAW_SOURCE | Headline, filing body, social post | Never overwrite |
| EXTRACTED_FACT | Event type, entities, metrics | Versioned extraction |
| DERIVED_METRIC | Surprise %, materiality ratio | Deterministic formulas |
| MODEL_INTERPRETATION | FinBERT label, LLM channel map | ModelVersionRef required |
| CROSS_LANE_EVIDENCE | CatalystEvidence, ReactionEvidence | Published envelopes |

---

## Cross-lane evidence types

| Type | Consumers |
|---|---|
| `CatalystEvidence` | Short Squeeze, Options, Futures |
| `SurpriseEvidence` | Options O7, Futures F7 |
| `ShortThesisInvalidationEvidence` | Short Squeeze |
| `AttentionEvidence` | Short Squeeze, reflexive research |
| `NarrativeEvidence` | Options vol, experimental |
| `MacroContextEvidence` | Futures, Options |
| `MarketReactionEvidence` | All lanes (interpretation) |
| `ContextEvidenceEnvelope` | Fusion layer |

All include: `event_time`, `available_time`, `producer`, `producer_version`, `confidence`, `quality_flags`, `provenance_class`.

---

## Modeling ladder (M0–M11)

| Level | Features |
|---|---|
| M0 | No text |
| M1 | Lexicon sentiment |
| M2 | FinBERT baseline (`BaselineFinancialSentiment`) |
| M3 | Targeted entity sentiment |
| M4 | Sentiment + event type |
| M5 | + novelty |
| M6 | + surprise |
| M7 | + materiality / credibility |
| M8 | + attention |
| M9 | + macro regime |
| M10 | + observed market reaction |
| M11 | + narrative/thesis state |

Advanced models must beat simpler baselines out of sample.

---

## LLM role boundary

**Permitted:** schema-bound extraction with `EvidenceSpan`  
**Forbidden:** free-form return forecasts as calibrated probabilities  
**Required:** `RETROSPECTIVE_KNOWLEDGE_RISK` flag when historical LLM backtests cannot guarantee point-in-time knowledge exclusion

---

## UI principles

Expose separately: sentiment, uncertainty, event type, surprise, materiality, novelty, credibility, attention, narrative, macro context, market reaction, remaining information — **no universal news score**.

Surface contradictions (semantic positive + market negative) explicitly.

---

## Implementation status labels

`RESEARCHED` | `IMPLEMENTED` | `VALIDATED` | `EXPERIMENTAL` | `UNAVAILABLE`

Current code: **MC1–MC15 IMPLEMENTED** (contracts + fixture entity resolution + event clustering + baseline sentiment + event extraction + expectations/surprise + impact components + catalyst/thesis + attention/diffusion + narrative + macro + reaction + information decay + social/author intelligence + cross-entity propagation); **MC16 DESIGN COMPLETE** (multi-document LLM synthesis spec — fixture-precomputed cluster fields, separate theme agreement / contradiction flags, no universal news score; implementation deferred). Catalyst bridge uses MC8 workspace output; attention uses MC9 `AttentionEvidence` on BOXL fixtures; MC14 keeps influence and accuracy as separate fields; MC15 publishes separate `propagated_*` fields on BOXL/NVDA graph fixtures.
