# PI12 — Large Derivatives Participant Research (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Bridge anonymous large options flow (O5 signed-flow semantics) into Participant Intelligence without inventing identity  
**Prerequisites:** O5 IMPLEMENTED (fixture), PI6 IMPLEMENTED (fixture), Platform P0 PIT

## 1. Purpose

Classify large anonymous derivatives/options activity at institutional scale for conditional Swim With the Whales research. Resolves PI-D09 (options whale family without participant identity bridge) and feeds PI-Q2 (metaorder continuation) and PI-Q4 (participant disagreement → IV) research tracks.

Options owns O5 signed-flow classification. PI12 owns participant-scale interpretation and cross-lane publish only.

## 2. Scoring model (`derivatives_participant_v1`)

### Inputs

| Input | Source |
|---|---|
| PIT-eligible options activities | Whale ledger `query_options_summaries` or fixture path |
| Signed-flow classification | O5 `classify_signed_flow` per activity |
| Aggregated flow | O5 `aggregate_signed_flow` |
| Scale thresholds | `nvda_derivatives_participant_slice.json` |
| Optional corroboration | PI6 `MetaorderEvidence` on same instrument (flag only) |

### Flow regime (`DerivativeFlowRegime`)

| Regime | Condition |
|---|---|
| `CONFIRMED_DIRECTIONAL` | Confirmed signed flow above scale threshold with dominant buy/sell initiation |
| `SCALE_ELEVATED_AMBIGUOUS` | Elevated activity but O5 direction blocked or dominant direction tied |
| `INSUFFICIENT_DATA` | Below scale threshold, no PIT-eligible activities, or all trades uncertain |

### Identity policy

- `participant_id = participant:anonymous:large_options`
- `participant_type = UNKNOWN_LARGE_PARTICIPANT`
- `identity_confidence = ANONYMOUS_INSTITUTIONAL_SCALE`
- Never infer direction from `direction_label` or volume alone
- Large call flow ≠ informed bullish whale — mechanism stays conservative (`FLOW_DRIVEN`, `HEDGING`, or unknown)

### PIT rules

- Include activities only when `available_time <= prediction_cutoff` (fallback: `event_time`)
- Propagate O5 `OPEN_CLOSE_UNKNOWN` and `FLOW_DIRECTION_UNCERTAIN` into quality flags
- Fail-closed to `INSUFFICIENT_DATA` when signed direction unavailable

### Cross-lane signals

| Signal | Condition |
|---|---|
| `LARGE_DERIVATIVE_FLOW_CONFIRMED` | `CONFIRMED_DIRECTIONAL` with scale gates passed |
| `LARGE_DERIVATIVE_FLOW_AMBIGUOUS` | `SCALE_ELEVATED_AMBIGUOUS` |
| No signal | `INSUFFICIENT_DATA` or below scale threshold |

PI12 does not emit `OPTION_FLOW_DIRECTION`, dealer gamma, or PI10 crowding signals.

## 3. Fixtures

| Fixture | Scope |
|---|---|
| `nvda_derivatives_participant_slice.json` | Scale thresholds, cutoff, signed-flow fixture path |
| `nvda_derivatives_participant_expected.json` | Golden PI12 regression (confirmed directional scenario) |
| `nvda_signed_flow_slice.json` | O5 input (reused) |
| `biya_options_slice.json` | Fail-closed regression (no `flow_side`) |

## 4. Out of scope

- Live Unusual Whales / commercial options flow vendor wiring
- Form PF, CFTC named-participant filings, dealer/customer attribution
- Reimplementing O5/O6 dealer or gamma semantics
- PI7 mechanism inference beyond conservative defaults
- PI9 copyability for anonymous sub-second flow
- Dedicated UI panel

## 5. Completion definition

PI12 complete when fixture history produces deterministic `DerivativeParticipantEvidence`, PIT adversarial tests pass, O5 consumption verified (no duplicate classification logic), PI-D09 resolved at fixture scope, cross-lane signals publish without Options/PI10 signal collision, and full test suite remains green.
