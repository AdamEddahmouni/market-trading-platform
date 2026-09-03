# PI13 — Forced-Flow / Dislocation Engine (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Fuse PI6 metaorder completion, Order Flow exhaustion/reversal, Futures leverage stress, and Market Context catalyst absence into governed forced-flow research evidence  
**Prerequisites:** PI6 IMPLEMENTED (fixture), OF7/OF8 IMPLEMENTED (fixture), F8 IMPLEMENTED (fixture), MC8 catalyst contracts, Platform P0 PIT

## 1. Purpose

Detect dislocation / forced-flow conditions for conditional fade research (FD-FORCE-01). PI13 interprets cross-lane inputs; it does not reimplement Order Flow impact, microstructure forecasts, futures leverage math, or catalyst extraction.

Participant Intelligence owns forced-flow semantics and cross-lane publish only.

## 2. Scoring model (`forced_flow_v1`)

### Inputs

| Input | Source | Consumed field |
|---|---|---|
| Metaorder lifecycle | PI6 `MetaorderEvidence` or fixture `lane_inputs.metaorder` | `lifecycle_state == LIKELY_COMPLETE` |
| Microstructure stress | OF7/OF8 summaries or fixture `lane_inputs.microstructure` | `reversal_probability`, `exhaustion_score`, `impact_regime` |
| Leverage stress | F8 snapshot or fixture `lane_inputs.leverage` | `long_liquidation_risk`, `short_liquidation_risk`, `stress_regime` |
| Catalyst registry | MC8 fixture or `lane_inputs.catalyst_registry` | `registry_available`, `active_catalyst_at_cutoff` |

Optional path references in slice JSON recompute PI6 metaorder from `metaorder_fixture_path`.

### Regime (`ForcedFlowRegime`)

| Regime | Condition |
|---|---|
| `FORCED_FLOW_LIKELY` | Catalyst registry available, no active catalyst at cutoff, metaorder `LIKELY_COMPLETE`, exhaustion/reversal elevated, liquidation stress elevated |
| `DISLOCATION_AMBIGUOUS` | Partial gate satisfaction (e.g. stress without complete metaorder, or complete metaorder without liquidation corroboration) |
| `INSUFFICIENT_DATA` | Catalyst registry missing, active catalyst at cutoff, or insufficient PIT-eligible inputs |

### Identity policy

- `participant_id = participant:anonymous:forced_flow`
- `participant_type = UNKNOWN_LARGE_PARTICIPANT`
- `identity_confidence = ANONYMOUS_INSTITUTIONAL_SCALE`
- Mechanism defaults to `FORCED_LIQUIDATION` when liquidation risk flags set, else `LIQUIDITY_NEED`
- Never infer named participant from flow dislocation

### PIT rules

- Every input row included only when `available_time <= prediction_cutoff`
- Missing catalyst registry → `INSUFFICIENT_DATA` with `CATALYST_CONTEXT_MISSING` (never assume no catalyst)
- Active catalyst at cutoff → `INSUFFICIENT_DATA` (move may be explained by catalyst)
- Future-dated inputs excluded before scoring

### Cross-lane signals

| Signal | Condition |
|---|---|
| `FORCED_FLOW_PROBABILITY_ELEVATED` | `FORCED_FLOW_LIKELY` only |
| No signal | `DISLOCATION_AMBIGUOUS`, `INSUFFICIENT_DATA`, or catalyst gate failed |

PI13 does not emit OF exhaustion, F8 liquidation, or MC catalyst signals directly.

## 3. Fixtures

| Fixture | Scope |
|---|---|
| `nvda_forced_flow_slice.json` | Positive forced-flow scenario with embedded lane inputs + metaorder path |
| `nvda_forced_flow_expected.json` | Golden PI13 regression (`FORCED_FLOW_LIKELY`) |
| `nvda_forced_flow_catalyst_present_slice.json` | Fail-closed when catalyst active at cutoff |
| `nvda_forced_flow_ambiguous_slice.json` | Partial inputs → `DISLOCATION_AMBIGUOUS` |

## 4. Out of scope

- Live broker / vendor forced-liquidation feeds
- Dedicated UI panel (PI12 precedent)
- Auto-trading or universal fade score
- Reimplementing OF7/OF8/F8/MC8 modules

## 5. Completion definition

PI13 complete when fixture history produces deterministic `ForcedFlowEvidence`, PIT adversarial tests pass, catalyst fail-closed tests pass, cross-lane `FORCED_FLOW_PROBABILITY_ELEVATED` publishes without OF/F8 signal collision, and full test suite remains green.
