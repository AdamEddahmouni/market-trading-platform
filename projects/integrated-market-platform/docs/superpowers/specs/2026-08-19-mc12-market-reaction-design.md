# MC12 — Market Reaction Engine (fixture-first)

**Status:** Implemented  
**Spec date:** 2026-08-19  
**Scope:** Per-event `MarketReactionEvidence` with confirmation/contradiction against semantic direction and admitted cross-lane donor signals  
**Prerequisites:** MC6 IMPLEMENTED, MC8 IMPLEMENTED, SHARED P3, Platform P0 PIT

## 1. Purpose

Classify whether observed market reaction confirms or contradicts semantic/predicted economic direction. Resolves MC-D12 (no reaction confirmation). **Consumer-only** — does not reimplement CVD, IV, or curve calculations.

## 2. Scoring model (`market_reaction_v1`)

### Inputs (consume, do not recalculate)

| Input | Source |
|---|---|
| `semantic_direction` | MC8 `CatalystSummary.lean` |
| `predicted_economic_direction` | MC6 surprise sign when available; else MC8 lean |
| `abnormal_return`, `volume_multiple`, `horizon` | `boxl_reaction_slice.json` |
| Cross-lane donor signals | Fixture `cross_lane_refs[]` per event (references only) |

### Observed direction (from fixture abnormal return)

| Condition | Direction |
|---|---|
| `abnormal_return >= +0.005` | BULLISH |
| `abnormal_return <= -0.005` | BEARISH |
| otherwise | NEUTRAL |

### Confirmation state (deterministic priority)

| State | Condition |
|---|---|
| `INSUFFICIENT_DATA` | No fixture row for event |
| `CONTRADICTED` | Semantic and observed both non-NEUTRAL and disagree |
| `CONFIRMED` | Semantic and observed both non-NEUTRAL and agree |
| `MIXED` | Cross-lane refs split bullish/bearish |
| `PARTIALLY_CONFIRMED` | Semantic non-NEUTRAL, observed NEUTRAL, cross-lane vote supports semantic |
| `NO_MEANINGFUL_REACTION` | `|abnormal_return| < 0.005` and no confirming cross-lane vote |

`reaction_mismatch = True` when semantic and observed both non-NEUTRAL and disagree.

### Deferred (MC13)

`priced_in_probability` and `remaining_information_edge` remain `None` on fixture scope.

## 3. PIT rules

- Score only gated catalyst events with `available_time <= prediction_cutoff`
- Missing fixture rows fail-closed with `MARKET_REACTION_DATA_MISSING`

## 4. Cross-lane boundary

- Publishes `REACTION_CONFIRMED` for `CONFIRMED` and `PARTIALLY_CONFIRMED`
- Publishes `REACTION_CONTRADICTED` for `CONTRADICTED`
- Does not fuse into SHARED P4 directly

## 5. Fixtures

| Fixture | Scope |
|---|---|
| `boxl_catalyst_expected.json` | MC8 semantic direction |
| `boxl_reaction_slice.json` | Admitted observed returns + cross-lane refs |
| `boxl_reaction_expected.json` | Golden MC12 regression |

## 6. Workspace

- `reaction_evidence`, `reaction_summaries`, `reaction_available`
- `reaction_contradictions` — rows where `reaction_mismatch == true`
- `reaction_producer_id`, `reaction_producer_version`

## 7. Out of scope

- Internal CVD / IV / futures curve reimplementation
- Priced-in probability (MC13)
- Live multi-lane reaction ingest beyond fixture refs
