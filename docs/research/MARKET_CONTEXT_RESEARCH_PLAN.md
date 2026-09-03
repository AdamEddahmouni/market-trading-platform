# Market Context Research Plan (Deliverable 9)

**Date:** 2026-08-19  
**Status:** Research program for Information Intelligence lane

---

## Research questions (hypotheses)

| ID | Question | Baseline | Target feature | Lanes |
|---|---|---|---|---|
| MC-Q1 | Does FinBERT add value over no-text? | M0 | M2 | All |
| MC-Q2 | Does event type beat sentiment alone? | M2 | M4 | Options, SS |
| MC-Q3 | Does novelty improve catalyst prediction? | M4 | M5 | SS |
| MC-Q4 | Does surprise beat sentiment at earnings? | M2 | M6 | Options O7 |
| MC-Q5 | Does materiality improve magnitude forecast? | M4 | M7 | Options |
| MC-Q6 | Does attention acceleration improve ignition? | Structural only | M8 | SS P4 |
| MC-Q7 | Does thesis invalidation beat positive sentiment? | Sentiment | MC8 evidence | SS |
| MC-Q8 | Does narrative shift predict vol/returns? | M9 | M11 | Options |
| MC-Q9 | Does reaction mismatch predict reversal? | — | MC12 | Options, OF |
| MC-Q10 | Does source informativeness decay? | Static tiers | Learned coeffs | MC14 |
| MC-Q11 | Does macro regime condition CPI reaction? | Unconditional | MC11 | Futures F7 |
| MC-Q12 | Does social influence predict reflexive move independent of accuracy? | — | MC14 | SS, future crypto |

---

## Datasets

| Dataset | Purpose | Versioning |
|---|---|---|
| Admitted NEWS_ITEM fixtures | Raw layer tests | Fixture ID |
| BOXL catalyst fixture | Catalyst bridge | ADMITTED-CATALYST-BOXL-001 |
| NVDA earnings slice | Surprise + O7 joint tests | Provider slice version |
| ES macro slice | Macro surprise tests | F7 fixture |
| FinBERT eval set (to build) | Semantic sentiment | `label_schema_version` |
| Expectation snapshots (to acquire) | Surprise PIT | `available_time` per row |

---

## Modeling ladder experiments

Walk-forward chronological validation only. Report incremental lift at each M-level.

---

## Cross-lane experiments

1. Context unavailable → SS/Options/Futures still run (degraded confidence)  
2. Stale Context evidence rejected by consumers  
3. No same-timestamp Context→Options→Context cycle  
4. Order Flow reaction lag Context event by Δt  
5. SurpriseEvidence vs Options IV crush joint calibration  

---

## Metrics

| Category | Metrics |
|---|---|
| NLP extraction | Entity/event F1, span accuracy, numeric accuracy |
| Semantic sentiment | Precision, recall, F1, calibration |
| Market prediction | Brier, log loss, IC, abnormal return MAE |
| Economic usefulness | Incremental EV, precision@k events, cost-adjusted |
| Reaction | Confirmation rate, contradiction detection accuracy |

---

## Validation protocol

- Event-class breakdown (earnings, FDA, M&A, macro, social)  
- Source breakdown (SEC, wire, media, social)  
- Regime breakdown (vol, risk-on/off, meme)  
- Monitor model/source/narrative drift  

---

## LLM research boundary

Mark each capability: `IMPLEMENTED` | `VALIDATED` | `EXPERIMENTAL` | `RESEARCH_ONLY` | `UNAVAILABLE`

LLM historical backtests must flag `RETROSPECTIVE_KNOWLEDGE_RISK` unless grounded-only with evidence spans.
