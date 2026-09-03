# Sentiment Dataset Audit (Deliverable 8)

**Date:** 2026-08-19  
**Scope:** FinBERT path + labeled data references in monorepo

---

## Summary disposition

| Asset | Disposition | Rationale |
|---|---|---|
| `ProsusAI/finbert` pretrained weights | **KEEP** as `BaselineFinancialSentiment/FinBERT` | Standard financial semantic baseline |
| Local `finbert_finetuned` path refs | **RESEARCH_FIRST** | No checkpoint in repo |
| Phase 3d dropped `sentiment_label` fields | **ARCHIVE** — do not relabel as market direction | Prediction fields explicitly dropped |
| Internship LLM-scored session logs | **RESEARCH_ONLY** | No schema versioning; not semantic labels |
| Screener session JSONL `sentiment` dominant label | **DISPLAY_ONLY** | Not training labels |

---

## FinBERT labeled training dataset

**Result:** **No in-repo labeled headline dataset for FinBERT training or evaluation.**

Searches found:
- No CSV/JSONL with human-labeled `positive/neutral/negative` for fine-tuning
- No training scripts (`Trainer`, fine-tune notebooks)
- No evaluation logs (precision/recall/F1) for FinBERT in CI

---

## Legacy references

### Phase 3d intake (`batch01_discovery_rows.json`)

Fields **dropped** during normalization:
- `sentiment_label`
- `sentiment_confidence`
- Plus prediction fields (`squeeze_score`, `setup_tier`, etc.)

**Interpretation:** Legacy discovery rows contained model predictions — correctly excluded from Phase 3d calibration intake. Not a semantic sentiment gold dataset.

### Observation contract (`NEWS_ITEM`)

Headlines in fixtures (e.g. `biya_news.jsonl`) have **no sentiment labels** — correct raw layer.

---

## Class balance / leakage / concentration

| Check | Status |
|---|---|
| Label consistency | **N/A** — no training set |
| Class balance | **N/A** |
| Duplicates | News dedup in orchestrator; no ML dataset dedup |
| Temporal leakage | FinBERT runtime only; no historical backtest harness |
| Source concentration | NewsAPI/Finviz dependent in live screener |
| Ticker concentration | Screener universe-driven |
| Event concentration | Not measured |

---

## Recommended actions

1. **KEEP** FinBERT for M2 baseline semantic sentiment with explicit `BaselineFinancialSentiment` contract  
2. **BUILD** small gold evaluation set (manual spans) for entity-targeted sentiment — separate from market outcomes  
3. **DO NOT** relabel price moves as sentiment  
4. If fine-tuning: create `dataset_version`, `label_schema_version`, chronological splits  
5. **AUDIT** internship logs separately if used for research — mark `RETROSPECTIVE_KNOWLEDGE_RISK`

---

## Evaluation targets (when dataset exists)

| Target type | Metrics |
|---|---|
| Semantic sentiment | Precision, recall, F1, calibration |
| Event extraction | Entity/event F1, span accuracy |
| Surprise | MAE vs realized abnormal return (separate from semantic) |
| Catalyst | Incremental EV, precision at top-ranked events |

Break down by event class, source type, and regime — never report aggregate-only.
