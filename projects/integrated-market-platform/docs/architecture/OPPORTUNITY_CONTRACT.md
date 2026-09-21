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

### Decision provenance (operator audit contract)

Admitted opportunities carry a versioned `decision_provenance` record
(`opportunity/decision_provenance/1.0.0`) under OpportunityV1 metadata and on
`GET /opportunities/{id}/evidence`. It answers:

| Operator question | Field |
|---|---|
| Where did this originate? | `origin_kind` + `origin_refs` |
| Which strategy generated it? | `strategy_id` / `strategy_family` / `strategy_version` |
| What thesis is asserted? | `thesis.statement` + `thesis.mechanism` (honesty never `OBSERVED`) |
| What would invalidate it? | `thesis.invalidation_criteria` |
| Which observations support it? | `evidence_bindings[]` with `honesty` (`OBSERVED`/`DERIVED`/`INFERRED`/`UNKNOWN`) |
| What freshness window applies? | `freshness_window` |
| Why still / no longer actionable? | `actionability` + `state_changes[]` |

Discover/Radar candidates use `route_discovery_candidate_to_oe` for a deterministic
provenance route that does **not** mint OpportunityV1 and remains
`DISCOVER_INVESTIGATE_ONLY`. AI-assisted notes stay on `ai_assisted_notes` and
never authorize state changes. `lineage_status` distinguishes `MISSING` from
`MISMATCH` (compatible with RT-01 order_ready lineage honesty).

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

Goal 001 projects that presentation onto the operator **review row** (`OpportunitySummary` 1.1 / `GET /opportunities/summary`), not a second persist type. Demo/Paper NOW renders it as the Opportunity Review Card. Missing fields are `UNAVAILABLE`. Ranking is a named vector plus 1-based `rank_order`; HTTP omits `rank_score`. Live NOW does not query or rank. An empty or unready queue is valid when no `OpportunityV1` has been minted.

HTTP serialization (`ui_api/opportunity_projections.py`) lifts already-computed review-row facts to first-class JSON: `evidence_class`, `evidence_promotion_reason`, family admission, duplicates/supersession reason, and `instrument_key` (same identity as `instrument_id`). Persist `OpportunityV1.created_at_ns` (BUILD 21 decision time) and expected-edge fields are read at GET time from the repository; they are **not** copied onto review-row metadata, so temporal supersession remains fail-closed unless tests inject timestamps. `GET /opportunities/{id}/evidence` projects those evidence fields and keeps `items` as lineage refs. Attention rows stay `identity_kind=NOT_OPPORTUNITY_V1` with `evidence_class` null.

Operator lifecycle (`DETECTED` → `NORMALIZED` → `ELIGIBLE`/`INELIGIBLE` → `RANKED` → `REVIEWED`/`WATCHED`/`DISMISSED`) lives on the review row only. It does not mutate frozen `OpportunityV1`.

## Lifecycle

Recommended states:

`DETECTED -> NORMALIZED -> ELIGIBLE/INELIGIBLE -> RANKED -> REVIEWED -> PAPER_PREVIEWED -> PAPER_SUBMITTED (optional) -> MONITORED -> OUTCOME_RECORDED`

A research candidate can stop before execution. Live authority is never implied by this lifecycle.
