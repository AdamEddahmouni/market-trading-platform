# MC4 — Baseline Financial Sentiment (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** MC4 baseline semantic sentiment on admitted BOXL raw-document fixtures  
**Prerequisites:** MC2–MC3 IMPLEMENTED, Platform P0 PIT

## 1. Purpose

Bridge donor FinBERT semantics and a stdlib keyword baseline into canonical `BaselineFinancialSentiment` contracts. Semantic sentiment is an intermediate feature — not economic surprise, catalyst strength, or trade direction.

## 2. Models

| Model | Runtime | `BaselineSentimentModel` |
|---|---|---|
| Keyword lexicon | Stdlib in IMP (`keyword-v1`) | `KEYWORD_BASELINE` |
| FinBERT labels | Fixture-only (precomputed offline) | `FINBERT_BASELINE` |

Live FinBERT inference (`ProsusAI/finbert`) remains in the donor screener only. IMP CI has no transformers/torch dependency.

## 3. Keyword baseline (`keyword-v1`)

PORT_ADAPT from donor `KeywordSentimentProvider`:

- Positive/negative lexicon hit counting on normalized `title + body`
- `pos_hits > neg_hits` → `POSITIVE`
- `neg_hits > pos_hits` → `NEGATIVE`
- `pos_hits == neg_hits` (including both zero) → `MIXED` (not `NEUTRAL`; resolves MC-D03)
- Confidence: `min(0.99, 0.51 + abs(pos - neg) * 0.05)`; `0.5` when tied

## 4. FinBERT fixture labels

Fixture: `tests/fixtures/market_context/boxl_finbert_labels_slice.json`

| Field | Required |
|---|---|
| `document_id` | Yes |
| `label` | `positive` / `negative` / `neutral` / `mixed` |
| `confidence` | 0–1 |
| `model_id` | `ProsusAI/finbert` |
| `label_schema_version` | e.g. `finbert_semantic_v1` |

Labels are generated offline (donor `LocalFinbertProvider` or manual curation) and committed as golden replay truth.

## 5. PIT rules

- Score document only when `available_time <= prediction_cutoff`
- Excluded documents produce no `BaselineFinancialSentiment` row (not neutral defaults)
- Missing title and body → `UNKNOWN` + `SENTIMENT_TEXT_MISSING` quality flag

## 6. Entity targeting

- `target_entity_id` from MC2 `entity_resolution.entity_id`
- `TargetedSentiment` emitted when entity resolved (fixture scope: BOXL symbol)

## 7. Event aggregation

For each MC3 `InformationEvent` cluster:

- Aggregate keyword labels across member documents (PIT-visible only)
- Unanimous label → that label; disagreement → `MIXED`
- FinBERT aggregation uses same majority/disagreement rule on fixture labels

## 8. Cross-lane boundary

- Publish `SEMANTIC_SENTIMENT_POSITIVE` / `SEMANTIC_SENTIMENT_NEGATIVE` / `SEMANTIC_SENTIMENT_MIXED` with `EvidenceProvenanceClass.MODEL_OUTPUT`
- **Display-only** — no SHARED P4 EV fusion, no squeeze state mutation (MC-D01, MC-D05)

## 9. Fixture outcome

`boxl_raw_documents_slice.json` (8 documents) → per-document keyword + FinBERT baselines; 5 event-cluster aggregates.

## 10. Out of scope

- Live FinBERT runtime in IMP
- LLM extraction (MC5)
- Catalyst provider refactor (MC8)
- Trade-signal mapping

## 11. Completion definition

MC4 complete when fixture pipeline produces deterministic `BaselineFinancialSentiment` per document and per event cluster, PIT adversarial tests pass, workspace projection available for BOXL, and full test suite remains green.

## Appendix A — Offline FinBERT label generation

```text
1. Load boxl_raw_documents_slice.json document titles/bodies
2. Run donor LocalFinbertProvider.analyze_headlines() per document
3. Map donor labels to SemanticSentimentLabel enum values
4. Commit rows to boxl_finbert_labels_slice.json with model_id and label_schema_version
```

Not executed in IMP CI.
