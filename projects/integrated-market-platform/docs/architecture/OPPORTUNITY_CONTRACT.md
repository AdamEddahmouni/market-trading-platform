# IMP Opportunity Contract

**Classification:** `CURRENT_CANONICAL_ARCHITECTURE`  
**Purpose:** define the common strategy-to-Opportunity-Engine boundary without forcing heterogeneous strategies into one simplistic score.

## Principle

Every admitted strategy/detector may preserve its own mechanism, feature set, horizon, uncertainty model and asset-specific expression. To participate in the common Opportunity Engine it emits a normalized Opportunity Contract that makes the candidate comparable, explainable, risk-aware and auditable.

A universal scalar score is **not** required. Ranking and portfolio logic may consume the normalized fields differently by horizon, asset class and strategy family.

## Required core fields

| Field | Meaning |
|---|---|
| `opportunity_id` | Stable candidate identity |
| `strategy_family` / `strategy_version` | Provenance of the detector/policy |
| `instrument_key` / `asset_class` | Canonical XA-01-compatible identity |
| `decision_time` | Time the opportunity was formed |
| `information_cutoff` | Latest legitimate input cutoff |
| `direction_or_expression` | Long/short/neutral/spread/volatility/etc. |
| `horizon` | Intended decision/holding/evaluation horizon |
| `mechanism` | Why the opportunity is expected to exist |
| `summary` | Concise operator-facing explanation |
| `evidence_class` | Current evidence level supporting the strategy/claim |
| `data_quality` | Freshness/source/coverage/entitlement state |
| `eligibility_state` | Whether the candidate can proceed and why |

## Expected-edge and uncertainty fields

Where the strategy supports them, include:

- expected return/edge or bounded outcome range;
- uncertainty/confidence interval or calibration bucket;
- probability/calibration information where meaningful;
- favorable/adverse excursion expectations;
- decay/half-life or time sensitivity;
- abstention/conflict state when evidence is insufficient.

Never fabricate precision a strategy cannot justify. Unknown is preferable to a false common score.

## Execution and liquidity fields

Include when executable or when implementation feasibility is part of ranking:

- expected spread/slippage/fees/cost range;
- liquidity/capacity estimate and evidence basis;
- required instrument/order expression;
- execution-model calibration state;
- session/venue constraints;
- market-impact/queue limitations if not modeled;
- comparator/calibration references where applicable.

## Risk and portfolio fields

Include when available:

- downside/tail-risk description;
- invalidation/exit condition;
- gross/net/sector/theme/factor/asset exposure impact;
- concentration/correlation conflicts;
- margin/collateral requirement;
- sizing eligibility or maximum safe size from the authoritative risk layer;
- portfolio conflict/hedge context.

Hard risk authority remains outside strategy ranking. A high-ranked opportunity cannot bypass a risk or mode gate.

## Context fields

Optional common context may include:

- catalyst/event identity and materiality;
- market regime/state;
- macro/cross-asset context;
- crowding/participant context;
- technical/microstructure confirmation;
- source disagreement or contradictory evidence.

Context fields must retain provenance and must not silently become independent execution authority.

## Evidence and provenance

Every material score, estimate or qualitative label should be traceable to either:

- a versioned strategy output;
- a canonical provider/source observation;
- a versioned research/evidence artifact;
- a portfolio/risk calculation;
- an execution/calibration record.

The Opportunity Engine may combine these facts, but it must preserve enough lineage to explain why the candidate exists and why it was ranked/filtered.

## Operator presentation

The operator-facing representation should prioritize:

1. what the opportunity is;
2. why it matters now;
3. expected edge/range and uncertainty;
4. key evidence and contradictions;
5. risk/downside and invalidation;
6. execution feasibility/cost;
7. portfolio impact;
8. the shortest safe next action.

## Lifecycle

Recommended states:

`DETECTED -> NORMALIZED -> ELIGIBLE/INELIGIBLE -> RANKED -> REVIEWED -> PAPER_PREVIEWED -> PAPER_SUBMITTED (optional) -> MONITORED -> OUTCOME_RECORDED`

A research candidate can stop before execution. Live authority is never implied by this lifecycle.
