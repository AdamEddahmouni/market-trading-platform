# PI5 — Participant Walk-Forward Skill (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Outcome-linked walk-forward skill estimation with Bayesian shrinkage, PIT-safe aggregation, cross-lane publish  
**Prerequisites:** PI3 IMPLEMENTED, PI4 IMPLEMENTED

## 1. Purpose

Estimate conditional participant skill from admitted disclosure actions and price outcomes. Skill at time `t` uses only actions with `available_time < t`. Never label permanently "smart money."

## 2. Skill dimensions

| Dimension | Source actions | Outcome window |
|---|---|---|
| `buy_skill` | Discretionary Form 4 `OPEN_MARKET_BUY` | 20d post-`available_time` |
| `sell_skill` | Form 4 `OPEN_MARKET_SELL` | 20d post-`available_time` (positive = favorable sell timing) |
| `activism_success` | 13D `ACTIVIST_STAKE_INITIATED` | 60d post-`available_time` |

## 3. Temporal rules (mandatory)

- Skill aggregation at `prediction_cutoff` includes only actions with `available_time <= prediction_cutoff`
- Outcome windows require price data through `available_time + window`; incomplete → `OUTCOME_WINDOW_INCOMPLETE` (excluded from sample)
- Walk-forward folds use `research/walk_forward.py`; train actions must have `available_time <= train_end_cutoff`
- Future actions must not affect past skill estimates (adversarial tests required)

## 4. Shrinkage and gates

```text
shrunk = (n / (n + k)) * raw_mean + (k / (n + k)) * prior
```

- Default `prior = 0.0`, `k = 5`, `min_sample = 3`
- Below `min_sample`: emit snapshot with `SKILL_INSUFFICIENT_SAMPLE`; no directional cross-lane signal

## 5. Grouping

Named regulatory filers group by normalized `display_name` for walk-forward history. Anonymous flows remain per `participant_id`.

## 6. Cross-lane signals

| Signal | Condition |
|---|---|
| `PARTICIPANT_SKILL_ELEVATED` | `buy_skill` shrunk > 0.05, sample ≥ 3, no insufficient-sample flag |
| `PARTICIPANT_SKILL_BELOW_BASELINE` | `buy_skill` shrunk < -0.02, sample ≥ 3 |

Ambiguous or insufficient → no skill directional signal.

## 7. Out of scope

- Live price feeds
- Permanent smart-money labels
- Per-lane duplicate skill engines
- Entity graph merge across filer aliases (future PI entity resolution)

## 8. Completion definition

PI5 complete when fixture history + price outcomes produce deterministic skill snapshots, PIT adversarial tests pass, cross-lane skill signals publish, institutional ignition cards consume skill summary when sample sufficient, and full test suite remains green.
