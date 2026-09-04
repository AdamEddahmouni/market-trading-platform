# PI10 — Consensus / Disagreement / Crowding (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Aggregate PIT-safe PI3–PI5 participant actions per instrument to detect consensus, disagreement, and institutional crowding on admitted fixtures  
**Prerequisites:** PI3 IMPLEMENTED, PI4 IMPLEMENTED, PI5 IMPLEMENTED, Platform P0 PIT

## 1. Purpose

Answer whether independent participants align, disagree, or crowd into the same directional stance on an instrument. Resolves W11 cross-lane alignment in the Participant research ladder and feeds PI-Q3 (squeeze ignition), PI-Q4 (IV expansion), and PI-Q5 (liquidation prediction) research tracks.

PI8 owns `PARTICIPANT_ALIGNMENT_CANDIDATE` / `PARTICIPANT_CONTRARIAN_CANDIDATE` for **catalyst timing** only. PI10 uses separate cross-participant signals.

## 2. Scoring model (`crowding_v1`)

### Inputs

| Input | Source |
|---|---|
| PIT-eligible `ParticipantAction` list | PI3 disclosure bridge via adapter |
| Lookback window (days) | `biya_crowding_slice.json` (default 180) |
| Affiliation groups | fixture `affiliation_groups` map (fund display name → manager key) |
| Thresholds | `min_independent_participants`, `crowding_score_threshold` |

### Per-participant stance (most recent directional action in window)

| Cohort | Directional actions |
|---|---|
| Insider | discretionary `OPEN_MARKET_BUY` / `OPEN_MARKET_SELL` |
| Activist | `ACTIVIST_STAKE_INITIATED`, `ACTIVIST_STAKE_INCREASED` |
| Institutional | `POSITION_INITIATED`, `POSITION_INCREASED`, `POSITION_REDUCED`, `POSITION_EXITED` |

Non-directional actions (compensation, snapshots without QoQ change, ambiguous) excluded from stance vote.

### Regime classification (`ParticipantAlignmentRegime`)

| Regime | Condition |
|---|---|
| `CONSENSUS` | ≥2 independent participants with same directional stance and no opposing independent stance |
| `DISAGREEMENT` | ≥2 independent participants with opposing directional stances |
| `MIXED` | directional activity present but neither consensus nor disagreement thresholds met |
| `INSUFFICIENT_DATA` | < `min_independent_participants` with clear directional stance |

### Crowding score

Share of independent institutional participants with the same directional QoQ change in window (0..1). Affiliated funds deduplicated via fixture `affiliation_groups`.

### PIT rules

- Include only actions with `available_time <= prediction_cutoff`
- Restrict to lookback window ending at `prediction_cutoff`
- Propagate `CROWDING_DATA_STALE` when institutional inputs carry `POSITION_STALE`
- Never treat quarter-end snapshots without QoQ change as live crowding

### Cross-lane signals

| Signal | Condition |
|---|---|
| `PARTICIPANT_CROWDING_ELEVATED` | institutional `crowding_score` ≥ threshold AND ≥ min independent institutional participants |
| `PARTICIPANT_DISAGREEMENT_ELEVATED` | regime = `DISAGREEMENT` with ≥2 opposing independent stances |
| `PARTICIPANT_CONSENSUS_ELEVATED` | regime = `CONSENSUS` with ≥2 independent aligned stances |

No directional signal when `INSUFFICIENT_DATA`. PI10 never emits PI8 catalyst alignment/contrarian candidate signals.

## 3. Fixtures

| Fixture | Scope |
|---|---|
| `biya_crowding_slice.json` | Window, thresholds, affiliation_groups |
| `biya_crowding_expected.json` | Golden PI10 regression (disagreement scenario) |
| `biya_institutional_crowding.json` | Multi-fund 13F QoQ increases for crowding scenario |

## 4. Out of scope

- Live affiliation / entity graph resolution
- Skill-weighted consensus as default (optional fixture flag only)
- PI-Q4/Q5 experiment runners
- Futures COT crowding (F4) or MC analyst consensus (MC6)
- Replacing `summarize_participant_actions` — PI10 adds instrument-level aggregation alongside it

## 5. Completion definition

PI10 complete when fixture history produces deterministic `ParticipantCrowdingEvidence`, PIT adversarial tests pass, affiliation dedup verified, cross-lane crowding/disagreement/consensus signals publish without PI8 signal collision, and full test suite remains green.
