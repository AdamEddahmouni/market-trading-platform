# Short Squeeze Causal Research Specification

**Status:** AUTHORITATIVE for Short Squeeze lane redesign (Revision 4 causal model)  
**Version:** `squeeze_causal_research_spec.v1`  
**Supersedes:** Heuristic screener semantics where they conflict

## 1. Definition

A **short squeeze** is a reflexive price dynamic where urgent incremental buying meets insufficient immediately available selling liquidity, forcing short sellers (and optionally dealers) to buy stock they previously sold short.

This is **not** equivalent to:
- high short interest alone
- a large one-day rally
- high call volume alone
- FINRA daily short-sale volume
- fails-to-deliver balances

## 2. Mechanism taxonomy

| Mechanism | Primary drivers | Distinct from |
|---|---|---|
| **Market squeeze** | SI, turnover, float, attention, catalyst, retail demand, options amplification | Pure momentum |
| **Lender squeeze** | utilization, lendable inventory, borrow fee, recalls, HTB | Market squeeze without lending stress |
| **Gamma amplification** | dealer delta/gamma positioning + price momentum | Short squeeze without positioning evidence |
| **Attention amplification** | social/search/news velocity | Fundamental catalyst |

Multiple labels may apply to one event.

## 3. Causal model

```text
SQUEEZE RISK ≈ FUEL × CONSTRAINT × IGNITION × REFLEXIVITY

Short Squeeze ≈ Urgent Incremental Buying / Immediately Available Selling Liquidity
```

Dimensions (never collapsed into one opaque score):

| Dimension | Meaning |
|---|---|
| vulnerability | latent short-pressure structure |
| constraint_pressure | securities-lending scarcity |
| short_stress | estimated adverse return / crowding stress |
| ignition_strength | catalyst + price/volume forcing |
| reflexivity_strength | live feedback loop evidence |
| remaining_fuel | estimated uncovered short demand |
| exhaustion_risk | declining incremental forced demand |

## 4. State machine

```text
BASELINE → VULNERABLE → ARMED → IGNITION_WATCH → LIVE_CONFIRMATION
    → ACTIVE_SQUEEZE → EXHAUSTION → POST_SQUEEZE
```

Backward transitions are allowed when evidence deteriorates. States require **multiple evidence classes** — never a single threshold.

Implementation: `squeeze_core/intelligence/evaluator.py` (`squeeze_causal_baseline.v1`).

## 5. Feature taxonomy

See causal groups A–I in platform audit brief. Level / change / velocity / acceleration / percentile / z-score must be distinguished.

**Forbidden conflations:**
- `daily_short_volume` ≠ `outstanding_short_interest`
- `FTD balance` ≠ naked short count
- `threshold list` ≠ forced-cover countdown

## 6. Raw data requirements

Point-in-time fields: `event_time`, `available_time`, `ingested_time`, source, provider, quality, revision status.

Publication lag rules (non-negotiable):
- published SI available only after exchange publication date
- options OI after exchange reporting cycle
- revised float only after revision available_time

## 7. Provider capability matrix

See `docs/research/SHORT_SQUEEZE_CAPABILITY_GAP_ANALYSIS.md`.

## 8. Labeling methodology

Research labels (not live states):

`MARKET_SQUEEZE`, `LENDER_SQUEEZE`, `GAMMA_AMPLIFIED`, `ATTENTION_AMPLIFIED`, `COMBINED_REFLEXIVE`, `NON_SQUEEZE_MOMENTUM`, `UNKNOWN`

Phase 3B outcome policy (±25%/24h) is a **detection research predicate**, not a squeeze mechanism label.

## 9. Prediction horizons

Target outputs (when calibrated):

P(squeeze within 1/3/5/10/20 trading days)

Baseline evaluator emits `RESEARCH_ONLY` null probabilities until walk-forward calibration exists.

## 10. Candidate models (sequence)

1. Interpretable logistic / hazard baselines
2. Calibrated gradient-boosted trees
3. Temporal models only if justified by data

## 11. Calibration requirements

Separate calibration for occurrence vs magnitude. Report Brier, PR-AUC, precision@K — not raw accuracy.

## 12. Validation strategy

Chronological walk-forward with purging/embargo. Regime slices required (pre-2020, meme regime, high-rate, etc.). GameStop must not dominate weights.

## 13. Evaluation metrics

precision, recall, PR-AUC, precision@K, Brier, calibration curve, log loss, expected trading value under explicit costs.

## 14. Cross-lane dependencies

Order Flow **owns** CVD/aggressor. Options **owns** gamma/dealer positioning. Short Squeeze **consumes** normalized evidence via `cross_lane/evidence.py`.

## 15. UI semantics

Primary card answers: WHAT / WHY / WHAT NEXT / HOW CERTAIN / WHAT MISSING. No opaque 87/100 score.

## 16. Confidence semantics

`model_confidence` ≠ `data_confidence`. Stale SI → lower data confidence even if model structure is sound.

## 17. Expected-value integration

`EV = P(win)×E[win] − P(loss)×E[loss] − costs`. Signal ≠ decision ≠ execution.

## 18. Exhaustion detection

Dedicated subsystem (P5). Required for exit logic.

## 19. Known limitations (current)

- No calibrated horizon probabilities
- No utilization / shares-on-loan velocity in baseline
- No ShortPainDistribution without entry-price inference data
- Frozen snapshots cannot prove live transitions

## 20. Open research questions

- Short entry price distribution inference
- Recall observability
- Cross-exchange crypto liquidation mapping

## 21. Dataset plan

Phase 3F n=30 cohort + expansion batches; separate label adjudication for mechanism class.

## 22. Test plan

See `tests/intelligence/test_causal_evaluator.py` and IMP `test_causal_squeeze_projection.py`.

## 23. Implementation roadmap

See `docs/research/SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md`.
