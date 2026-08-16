# Epistemic States & Visual Taxonomy

**Status:** `PROPOSED`  
**Platform alignment:** Swim With the Whales semantic separation; Phase 5 institutional vocabulary

## Classification taxonomy

| Class | Definition | Examples | Metadata to show |
|---|---|---|---|
| **OBSERVED** | Directly reported source data | Trade, quote, filing, price, on-chain tx, social post at first observation | Source, time, freshness, quality |
| **DERIVED** | Deterministic transformation | CVD, OFI, rel volume, calculated Greeks | Method, version, inputs, source quality |
| **INFERRED** | Heuristic/interpretive | Absorption, accumulation evidence, squeeze state | Supporting/conflicting evidence, confidence when meaningful |
| **MODEL** | Statistical/ML prediction | Forecast, probability | Target, horizon, model ID, calibration, uncertainty |
| **STRATEGY** | Decision state | WATCH, LONG candidate, ABSTAIN | Strategy, rule, evidence consumed, rejection reason |
| **RISK** | Independent authorization | PASS/REJECT | Violated constraint, budget, rule version |
| **EXECUTION** | Order/fill state | Simulated/live fill | Intent, venue, fees, latency |

## Visual distinction (without overwhelming)

### Epistemic badge
Compact label on every nontrivial value: `OBS` `DER` `INF` `MDL` `STR` `RSK` `EXE`

### Layer strip (decision contexts)
Vertical or horizontal strip showing active layer — never let MODEL visually imply EXECUTION:

```
OBSERVATION → DERIVATION → INFERENCE → MODEL → STRATEGY → RISK → EXECUTION
                              ▲ you are here
```

## Direction states (not scores)

| State | Display | Color semantics |
|---|---|---|
| Supports LONG | `↑ LONG` + strength | Accessible green tint + text |
| Supports SHORT | `↓ SHORT` + strength | Accessible red tint + text |
| Neutral | `— NEUTRAL` | Muted |
| Ambiguous | `? AMBIGUOUS` | Amber |
| Conflicting | `↕ CONFLICTED` | Distinct pattern (not red/green) |
| Stale | `⏱ STALE` | Muted + timestamp |
| Unavailable | `⊘ UNAVAILABLE` | Explicit empty state |

**Strength** (when used): `Weak` | `Moderate` | `Strong` — not numeric unless calibrated.

## Evidence alignment panel (preferred over buy score)

```
Evidence Alignment — NVDA — as of 10:42 ET

Order Flow         ↑ LONG       Strong
Options            — AMBIGUOUS
Squeeze            — NEUTRAL
Institutional      ↑ LONG       Moderate
Catalysts          ↑ LONG       Strong
Model (1d)         ↓ SHORT      Weak
Market Regime      ↑ LONG       Moderate

Conflict: Short-horizon model disagrees with current order flow.
```

## Confidence rules

| Class | Show confidence? |
|---|---|
| OBSERVED price | No — show freshness/quality instead |
| DERIVED (deterministic) | Quality, not confidence |
| INFERRED | Confidence when methodology supports it |
| MODEL | Probability/interval only if calibrated and defined |
| STRATEGY | Show rule satisfaction, not "confidence" |
| RISK | PASS/REJECT + constraint detail |

Avoid false numerical precision. Deeper precision via inspector only.

## Abstention as first-class

| State | Meaning | Visual |
|---|---|---|
| `ABSTAIN` | Evidence conflicting / insufficient | Distinct from error — neutral slate |
| `UNAVAILABLE` | Required capability absent | Capability explanation path |
| `WATCH` | Monitoring, no action | Informational |

Examples:
- `ABSTAIN — evidence conflicting`
- `ABSTAIN — liquidity insufficient`
- `UNAVAILABLE — depth capability not entitled`

## Crypto and influence examples

| Display | Class | Notes |
|---|---|---|
| `Elon posted X` (verified actor) | OBSERVED | Link to raw post; first_observed_at |
| `DOGE mentions +800% (5m)` | DERIVED | Snapshot-based velocity, not final engagement |
| `Influence regime elevated` | INFERRED | Supporting/conflicting evidence listed |
| `P(+return 5m)=0.64` | MODEL | Calibration required; not a buy score |
| `MOMENTUM WATCH` | STRATEGY | Rule satisfaction explicit |
| `REJECT — spread too wide` | RISK | Independent of strategy |
| `Large exchange inflow` | OBSERVED/DERIVED | Flow observation vs normalized size |
| `Wallet labeled: exchange` | INFERRED | Label confidence + source in inspector |
| `Funding extremely positive` | DERIVED | May conflict with price action — show both |

## Quality states (orthogonal to epistemic class)

`GOOD` | `PARTIAL` | `DEGRADED` | `STALE` | `UNAVAILABLE` | `CORRECTED` | `QUARANTINED` | `DISCONNECTED`

Always visible when not `GOOD`. Never hidden in Focus mode.

## Capability states (module level)

`AVAILABLE` | `UNSUPPORTED` | `NOT_ENTITLED` | `NOT_COLLECTED` | `LOADING` | `DEGRADED`

Missing data must look intentional — not broken empty charts.
