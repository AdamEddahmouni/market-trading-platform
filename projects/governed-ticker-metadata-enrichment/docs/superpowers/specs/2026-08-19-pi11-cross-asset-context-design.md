# PI11 — Cross-Asset Participant Context (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Fuse PI10 equity participant crowding with F4 COT category positioning to classify cross-asset alignment on admitted fixtures  
**Prerequisites:** PI10 IMPLEMENTED, F4 COT IMPLEMENTED (fixture), Platform P0 PIT

## 1. Purpose

Answer whether equity-side institutional participant positioning (PI10) and futures-side COT category positioning (F4) align or diverge. Resolves PI-D06 (whale ledger `futures_positioning` is L2 depth, not COT) and feeds PI-Q5 (participant crowding → liquidation prediction) research tracks.

F4 owns COT semantics and `FUTURES_POSITIONING_CROWDED_*` signals. PI10 owns equity crowding signals. PI11 owns cross-asset alignment classification only.

## 2. Scoring model (`cross_asset_v1`)

### Inputs

| Input | Source |
|---|---|
| Equity institutional direction + crowding regime | PI10 `ParticipantCrowdingEvidence` |
| COT crowding regime + net percentile | F4 `positioning_payload` via `FixtureFuturesPositioningProvider` |
| Instrument mapping | `biya_cross_asset_slice.json` (BIYA ↔ ES) |
| `prediction_cutoff` / `futures_decision_time` | Fixture slice |

### Alignment classification (`CrossAssetAlignmentRegime`)

| Regime | Condition |
|---|---|
| `ALIGNED_BULLISH` | PI10 `institutional_direction=BULLISH` AND F4 `crowding_regime=CROWDED_LONG` |
| `ALIGNED_BEARISH` | PI10 `institutional_direction=BEARISH` AND F4 `crowding_regime=CROWDED_SHORT` |
| `DIVERGENT` | Opposing directional signals (equity bullish + COT crowded short, or bearish + crowded long) |
| `MIXED` | One side directional, other neutral |
| `INSUFFICIENT_DATA` | Either PI10 or F4 unavailable / PIT-ineligible / quality-blocked |

### Alignment score

`1.0` when fully aligned; `0.0` when fully divergent; `0.5` when mixed; `None` when insufficient data.

### PIT rules

- COT: `cot_point_in_time_valid` via F4 `filter_pit_reports` — `publication_time <= futures_decision_time`
- Equity: PI10 lookback + `available_time <= prediction_cutoff`
- Propagate `COT_STALE`, `COT_PUBLICATION_PENDING`, `CROWDING_DATA_STALE`; fail-closed to `INSUFFICIENT_DATA` when F4 quality blocks interpretation

### Cross-lane signals

| Signal | Condition |
|---|---|
| `PARTICIPANT_CROSS_ASSET_ALIGNED` | `ALIGNED_BULLISH` or `ALIGNED_BEARISH` with both sides available |
| `PARTICIPANT_CROSS_ASSET_DIVERGENT` | `DIVERGENT` with both sides available |

No signal when `INSUFFICIENT_DATA` or `MIXED`. PI11 does not emit `FUTURES_POSITIONING_CROWDED_*` or PI10 crowding signals.

## 3. Fixtures

| Fixture | Scope |
|---|---|
| `biya_cross_asset_slice.json` | BIYA→ES mapping, cutoffs, fixture paths |
| `biya_cross_asset_expected.json` | Golden PI11 regression (aligned scenario) |
| `es_cot_positioning_divergent_slice.json` | COT crowded-short variant for divergent tests |

Reuses `es_cot_positioning_slice.json`, `biya_institutional_crowding.json`, `biya_crowding_slice.json`.

## 4. Out of scope

- Live COT feed wiring
- PI-Q5 experiment runner
- UI cross-asset panel
- Renaming whale ledger `futures_positioning` family (document-only in PI-D06)
- Reimplementing COT percentile / crowding math

## 5. Completion definition

PI11 complete when fixture history produces deterministic `CrossAssetParticipantContextEvidence`, PIT adversarial tests pass, F4 consumption verified (no duplicate COT logic), cross-lane aligned/divergent signals publish without F4/PI10 signal collision, and full test suite remains green.
