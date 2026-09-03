# PI9 — Copyability / Entry Quality (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Score whether public followers can profitably copy participant actions after `available_time` on admitted BIYA fixtures  
**Prerequisites:** PI3 IMPLEMENTED, PI5 IMPLEMENTED, Platform P0 PIT

## 1. Purpose

Answer whether a public follower entering at regulatory `available_time` retains positive edge after costs. Resolves PI-D04 (13F lookahead) and PI-D08 (`WHALE_ALIGNED` without mechanism/copyability gate) at fixture scope.

## 2. Scoring model (`copyability_v1`)

### Inputs

| Input | Source |
|---|---|
| Action + `available_time` | PI3 disclosure bridge |
| Forward returns | `biya_price_outcomes.json` (PI5) |
| Mechanism | PI2 action semantics; PI7 stub when absent |
| 13F lag | `QUARTER_END_NOT_COPYABLE` quality flag |
| Cost assumptions | `biya_copyability_slice.json` |

### Outputs per action

- `participant_gross_return` — return from `action_time` (research only)
- `follower_return_at_available` — return from `available_time`
- `cost_adjusted_follower_return` — follower return minus fixture spread/slippage bps
- `copyability_score` (0..1 or None) — `clamp01(cost_adjusted / 0.10)` when COPYABLE
- `copyability_class` — `COPYABLE`, `STALE`, `NOT_COPYABLE`, `INSUFFICIENT_DATA`

### PIT rules

- Score only when `available_time <= prediction_cutoff`
- 13F actions with `QUARTER_END_NOT_COPYABLE` → `NOT_COPYABLE`
- Never use `action_time` as public copy entry for regulatory disclosures

### Cross-lane signals

| Signal | Condition |
|---|---|
| `PARTICIPANT_COPYABILITY_HIGH` | `copyability_class=COPYABLE`, score ≥ 0.5, copyable mechanism |
| `PARTICIPANT_COPYABILITY_LOW` | `NOT_COPYABLE` or `STALE` with negative cost-adjusted return |

No signal when `INSUFFICIENT_DATA` or mechanism unknown.

### WHALE_ALIGNED gate

`WHALE_ALIGNED` abstains when no copyable participant evidence with qualifying mechanism exists at fixture scope.

## 3. Fixtures

| Fixture | Scope |
|---|---|
| `biya_copyability_slice.json` | Default cost bps + copy window |
| `biya_copyability_expected.json` | Golden PI9 regression |

## 4. Out of scope

- Live spread/slippage feeds
- Per-lane duplicate copyability engines
- Crypto / prediction-market copyability (PI14/PI15)
