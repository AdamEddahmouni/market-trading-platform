# Market Context / Information Intelligence — Current State Audit (Deliverable 1)

**Status:** Baseline audit for Information Intelligence redesign  
**Date:** 2026-08-19  
**Scope:** Monorepo donors + `integrated-market-platform` canonical subject

---

## Executive summary

There is **no unified Market Context lane** in the canonical platform today. Sentiment and news exist as **donor-local implementations** with incompatible semantics:

| Location | Role | Research admissible? |
|---|---|---|
| `short-squeeze-core` FinBERT | Per-headline semantic sentiment, display-only | **No** (`DISPLAY_ONLY_EXPERIMENTAL_SENTIMENT`) |
| `news_momentum_agent` Claude scorer | LLM news score → paper trades | Separate internship system |
| IMP Catalyst Lane (Phase 15) | Fixture `public_catalyst` on BOXL | Research context only |
| IMP disclosure (Phase 9) | EDGAR fixture on BIYA | Filing events, not sentiment |
| IMP `AttentionFeature` / `CatalystStrength` | SS P2 contracts | Interfaces exist; runtime UNAVAILABLE |
| Futures `macro_events.py` | Macro calendar surprise (F7) | Futures-owned interpretation |
| Options O7 `event_vol.py` | Earnings event vol / IV crush | Options-owned pricing |

Estimated completion vs. target Market Context architecture: **~5–8%** (contracts + fixture catalyst bridge; no entity resolution, event clustering, surprise engine, or reaction fusion).

---

## 1. News ingestion

### Short Squeeze screener (IMPLEMENTED — donor)

| Component | Path | Notes |
|---|---|---|
| News orchestrator | `apps/research_screener/news_live.py` | Finviz, Finnhub, NewsAPI, dedup, TTL cache |
| RSS collector | `collectors/rss_news.py` | Evidence collector |
| News adapter | `src/squeeze_core/adapters/news/` | Offline `NEWS_ITEM_V1` normalization |
| SEC RSS | `collectors/sec_rss.py` | Filing metadata for catalyst path |

**Semantics:** `NEWS_ITEM` observations carry headline, publisher, `published_at` — **explicitly no sentiment** in observation contract.

### Internship agent (IMPLEMENTED — separate)

| Component | Path | Notes |
|---|---|---|
| Aggregator | `news_momentum_agent/news/news_aggregator.py` | Multi-source per ticker |
| RSS monitor | `news/rss_monitor.py` | Wire + dedupe |
| Web scraper | `news/web_scraper.py` | Yahoo/Benzinga fallbacks |
| EDGAR client | `news/edgar_client.py` | Filing atom helpers |

### IMP (NOT IMPLEMENTED)

No native news ingest lane. Catalyst bridge reads internship `state/*.json` as proxy rows.

---

## 2. FinBERT / sentiment

### Implementation (Short Squeeze only)

| Item | Detail |
|---|---|
| Module | `apps/research_screener/sentiment_live.py` |
| Models | `LocalFinbertProvider` (`ProsusAI/finbert`), `KeywordSentimentProvider`, `NullSentimentProvider` |
| Training | **None in repo** — inference only |
| Labels | Per-headline: `positive`, `negative`, `neutral`; aggregate: `MIXED`, `UNKNOWN` |
| Tests | `tests/app/test_sentiment_finbert_wiring.py` |

### Downstream consumers (display only)

- `session_state.py` — catalyst fields block
- `server.py` — `/api/sentiment/*`
- `scanner.js`, `app.js` — UI column/sort/filter
- `export.py`, `data_logger.py` — session logs

### Explicitly NOT consuming sentiment

- `evaluation/rules/catalyst.py` — news **presence** only
- Phase 3A research detection
- IMP Options / Futures / Order Flow lanes
- Squeeze causal evaluator / Adam PRIME rules

### Internship LLM sentiment (separate)

- `claude_scorer.py` — score ∈ [-1, 1]
- `keyword_boost.py`, `news_decay.py`
- `decision_engine.py` — drives paper trades

**Incompatible** with FinBERT scale and not integrated with squeeze research pipeline.

---

## 3. Catalyst / attention in IMP

| Artifact | Status |
|---|---|
| `donor_patterns/catalyst_lane.py` | Confidence/lean/gate patterns from internship |
| `fixture_catalyst.py` | BOXL admitted fixture |
| `CATALYST_LANE.md` | Read-only integration spec |
| `squeeze_structural.py` | `AttentionFeature`, `CatalystStrength`, `ShortThesisInvalidation` |
| UI catalyst workspace | BOXL fixture cards |
| UI attention feed | `NowPage.tsx`, `attention_item.schema.json` |
| Cross-lane signals | `CATALYST_STRENGTH`, `ATTENTION_ACCELERATION` |

**Gap:** No semantic event model, novelty, surprise, or credibility decomposition.

---

## 4. Filings / SEC

| System | Scope |
|---|---|
| IMP Phase 9 | `edgar_disclosure.py` — BIYA fixture |
| Squeeze SEC adapter | `adapters/sec/` — offline normalization |
| UI | `DisclosureWorkspacePanel.tsx` |

No filing-delta analysis, form-specific extractors, or linkage to event clusters.

---

## 5. Expectations / surprise / earnings

| Capability | Owner | Status |
|---|---|---|
| Analyst consensus PIT store | Market Context (target) | **Missing** |
| Earnings surprise | Market Context (target) | **Missing** |
| Event volatility / IV crush | Options O7 | Fixture (NVDA) |
| Macro calendar surprise | Futures F7 | Fixture (ES) |
| Corporate event registry | Platform P1 | **PLANNED** |

---

## 6. Entity resolution

| System | Path | Scope |
|---|---|---|
| Squeeze acquisition | `identity_resolution.py` | Symbol/issuer/exchange conflicts |
| IMP crypto ADRs | Entity attribution for on-chain | Not equity news |
| Market Context target | Platform-wide `entity_id` | **Not implemented** |

---

## 7. UI

| Surface | Content |
|---|---|
| Catalyst workspace | Fixture catalyst cards (BOXL) |
| Disclosure workspace | SEC events (BIYA) |
| Command center | Attention feed (tiered) |
| Explore | Internship catalyst bridge rows |
| Squeeze donor UI | Sentiment column (experimental) |

**Missing:** Unified Market Context cockpit answering novelty, surprise, thesis impact, reaction confirmation, contradictions.

---

## 8. Tests

| Area | IMP tests | Donor tests |
|---|---|---|
| Catalyst lane acceptance | `test_catalyst_lane_acceptance.py` | `test_news_catalyst.py` |
| FinBERT wiring | — | `test_sentiment_finbert_wiring.py` |
| News normalizer | — | `test_normalizer.py`, `test_news_orchestrator.py` |
| Market Context contracts | `test_market_context_contract.py` | — |

---

## 9. Classification matrix (KEEP / EXTEND / REFACTOR / DEPRECATE)

| Component | Action | Rationale |
|---|---|---|
| FinBERT inference (`sentiment_live.py`) | **KEEP → EXTEND** as `BaselineFinancialSentiment` | Valid semantic baseline; not catalyst model |
| Keyword sentiment fallback | **KEEP** | Cloud/deploy fallback |
| `NEWS_ITEM` observation contract | **KEEP** | Correct raw layer |
| Screener sentiment UI column | **REFACTOR** | Label as semantic sentiment, not bullish signal |
| Internship Claude scorer | **RESEARCH_FIRST** | Separate system; schema-bound extraction target |
| `catalyst_lane.py` patterns | **REFACTOR** | Decompose into CatalystEvidence components |
| `CATALYST`/`ATTENTION` LaneId | **EXTEND** | Add `MARKET_CONTEXT`; legacy ids retained |
| Generic news age catalyst (D-13) | **DEPRECATE** | Replace with thesis invalidation evidence |
| Universal sentiment score UX | **REMOVE** from product direction | Per UX ADRs |
| Futures macro_events | **KEEP** | Futures owns interpretation |
| Options event_vol | **KEEP** | Options owns Q/P impact |

---

## 10. Deficiencies (priority)

1. No canonical `InformationSource` / `InformationEvent` in runtime pipeline  
2. No deduplication / event clustering (10 articles → 10 catalysts risk)  
3. Semantic sentiment conflated with catalyst in UI  
4. No point-in-time expectations / surprise engine  
5. No novelty, materiality, credibility as separate dimensions  
6. No market reaction fusion from Order Flow / Options  
7. Dual incompatible sentiment systems (FinBERT vs Claude)  
8. No FinBERT training dataset or evaluation in repo  
9. LLM extraction ungoverned (no schema versioning in internship path)  
10. Missing data silently becomes neutral in internship decision engine  
