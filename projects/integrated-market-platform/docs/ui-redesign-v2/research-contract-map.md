# Research contract map — UIR-01F

> Landed increment: `ui/operator-redesign-research` (UIR-01F). This is the
> authoritative current-contract map for the Research surface. The older page
> spec ([pages/research.md](pages/research.md)) remains the *plan*; where it
> assumed endpoints or object classes that do not exist, this map wins.
> Rule: current contracts are authoritative; old plans are guidance.

## What Research is for

Research answers: **what do we currently know, why do we think it, what evidence
supports or contradicts it, and how does it relate to decisions elsewhere in
IMP.** It is interpretation-first: claims and their state lead; methodology,
hashes, and raw timestamps live behind disclosure.

Research is **not**: a generic document browser, a raw DB viewer, a second
Radar, a giant table, a Diagnostics replacement, or an execution surface.
`EVIDENCE_NOT_PREDICTION` semantics are preserved end-to-end: nothing on this
surface implies prediction, ranked opportunity, execution authority, or proof.

## Backend contract inventory (current, verified against `ui_api/server.py`
## and `ui_api/projections.py`)

### 1. Research evidence panels — `GET /research/analytics`

Schema: `ResearchAnalyticsResponseSchema` (`ui/src/api/schemas.ts`).

| Field | Type | Notes |
|---|---|---|
| `as_of_context` | `AsOfContext` | mode, `as_of_time`, `replay_session_id`, `data_mode`, timezone |
| `authority_boundary` | string | always `READ_ONLY_RESEARCH_VISUALIZATION` |
| `epistemic_class` | string | always `RESEARCH_PROJECTION` |
| `disclaimer` | string | backend-authored human sentence |
| `panels` | 5 keyed panels | stable ID = panel key (no per-row IDs exist) |

Panel shape: `{ available: boolean, provenance: { source, method?, ... },
series: [{ label, count }], reason?, cohort_metadata?, signal_timeline? }`.

| Panel key | Measures | Provenance (backend) | Evidence class | Nullable/unavailable |
|---|---|---|---|---|
| `attention_tiers` | Attention tier distribution at cutoff | replay attention feed · `build_attention_page tier aggregation` | Replay | empty series when no attention rows |
| `squeeze_outcomes` | Donor squeeze screener outcome mix | donor bridge (`short-squeeze-project`) · outcome aggregation | Historical (donor bridge) | `available:false` + `reason` when donor bridge unavailable |
| `squeeze_historical_cohort` | Historical squeeze cohort calibration summary | cohort fixture · historical cohort projection | Historical | empty series; `cohort_metadata` passthrough |
| `strategy_outcomes` | Walk-forward strategy interpretation outcomes (`signal` / `abstention`) + cumulative `signal_timeline` | phase 5R walk-forward + phase 6 strategy | Backtest (walk-forward, replay-bound) | empty when no interpretations ≤ cutoff |
| `risk_decisions` | Risk simulation decision mix at cutoff | phase 7 risk simulation | Simulated | empty when no risk rows ≤ cutoff |

### 2. Strategy/model validation — `GET /research/models`

Schema: `ResearchModelsResponseSchema`. `authority_boundary`:
`READ_ONLY_RESEARCH`; `epistemic_class`: `RESEARCH_PROJECTION`.

| Field | Type | Operator relevance |
|---|---|---|
| `model_summary.model_family` | string (`naive_last_value.v1`) | which model produced the research |
| `model_summary.alignment_type` / `strategy_spec.alignment_type` | string (`FORECAST_MOMENTUM` / `WHALE_ALIGNED` / `WHALE_CONTRARIAN`) | strategy alignment |
| `model_summary.strategy_identity_hash`, `model_summary.dataset_fingerprint` | hash strings | L4 audit only (CopyableIdentifier) |
| `walk_forward_fold_count` | number | validation degree (contract-legit) |
| `preregistration_status` | `PASS` / `FAIL` / `ABSENT` (may be absent) | validation gate state |
| `preregistration`, `strategy_spec`, `dataset_manifest` | records | L4 methodology |
| `interpretation_summary` | `{ signal_count, abstention_count, total_at_cutoff }` | L1 synthesis |
| `interpretations[]` | rows: `observation_time` (epoch ns), `prediction_cutoff` (epoch ns), `outcome` (`signal` / `abstention`), `abstention_reason_codes[]`, `alignment_type`, `direction` | per-observation record |

Abstention reason vocabulary (`strategy/abstention.py` — real contract):
`ABSTAIN_NO_PREREGISTRATION`, `ABSTAIN_INSTITUTIONAL_UNAVAILABLE`,
`ABSTAIN_FORECAST_INVALID`, `ABSTAIN_FUTURE_INPUT`,
`ABSTAIN_CONFLICTING_EVIDENCE`, `ABSTAIN_COPYABILITY_UNAVAILABLE`.
`ABSTAIN_CONFLICTING_EVIDENCE` is the **only** contract-backed
"evidence conflicted" signal anywhere in the research payloads; it is rendered
as such and never generalized into a contradiction score.

### 3. Deterministic simulation run — `GET /research/simulation`

Schema: `ResearchSimulationResponseSchema`. `authority_boundary`:
`READ_ONLY_SIMULATION`; `epistemic_class`: `SIMULATION_PROJECTION`;
`mode_label`: `SIMULATION`.

| Field | Type | Notes |
|---|---|---|
| `ledger_summary` | `{ cash_minor, position_shares, realized_pnl_minor, entry_count }` | minor units; no currency field in contract — rendered honestly as minor units |
| `risk_decisions[]` | rows: `decision`, `constraint_detail` / `reason_code`, `signal_prediction_cutoff`, `intent_id`, `risk_decision_id` | decision values map onto the shared risk/authority vocabulary (APPROVE / RESIZE / REJECT …) |
| `fills[]` | `fill_id`, `fill_time`, `direction`, `fill_quantity`, `fill_price_minor` | |
| `orders[]`, `intents[]`, `attributions[]` | records | L3/L4 tables |
| `reconciliation` | record with `status` | e.g. `PASS` |
| `fill_audit` | record with `status` | optional |
| `risk_policy_id` | string \| null | L4 audit |

This is the only experiment-run contract. It is a **deterministic bar-
conservative simulation**, not a governed FTEP campaign and not production
readiness; the UI keeps those three ideas visually distinct.

### 4. Opportunity → Research bridge — `GET /opportunities/{id}` and
### `GET /opportunities/{id}/evidence`

`research_artifact_evidence` overlay (`ui_api/research_artifact_evidence.py`):

| Field | Type | Notes |
|---|---|---|
| `authority_class` | string | `EVIDENCE_NOT_PREDICTION` — never rank, never execution |
| `readiness` | string | attachment readiness |
| `attachments[]` | records | `status: UNRESOLVED` (catalog lookup failed — fixture/replay only), or resolved `historical_statistical_context` (Edge Stats: `sample_n`, `estimate`, `confidence_interval`, `stability_status`) / `options_flow_transparent_context` (replay prints, `live_feed_claim=NOT_CLAIMED`) |

Presentation lives in
`ui/src/components/opportunity/researchArtifactEvidenceProjection.ts` and the
Radar opportunity detail L3 disclosure. Research links back to Radar; the
summary feed has **no** list-level "has research evidence" field, so Research
does not fabricate per-opportunity relations.

### 5. Strategy outcomes in Paper — `GET /paper/strategy-profitability`

Strategy allocation lineage, attributed P&L, settlement state. Rendered on the
Paper Validation section as strategy context ("does the strategy lineage hold
up in Paper?"). Read-only reconstruction; the portfolio ledger stays
authoritative.

### 6. Explanation channels — `GET /explain/{ref}`, `GET /inspect/{ref}`

Drawer/inspector payloads used by Radar and Workspace. Research does not mint
new refs in this increment.

## Concepts with NO current contract (honest gaps)

These operator concepts are **not** exposed by any current UI API contract.
The Overview states this plainly instead of fabricating structure:

- **Hypotheses** as first-class trackable objects with lifecycle states — no
  endpoint. The closest contract truth is per-observation interpretation
  outcomes + abstention reasons on `/research/models`.
- **Research domains / taxonomy** — no endpoint (mandate domains live in
  program docs, not in a runtime contract).
- **Source catalog** — no endpoint; per-panel `provenance.source`/`method` is
  the only source disclosure and is shown per finding.
- **Supporting vs contradictory evidence flags** — no contract marks
  contradiction. Only `ABSTAIN_CONFLICTING_EVIDENCE` (above) carries conflict
  semantics. No synthetic confidence or contradiction score is invented.
- **Experiment / FTEP campaign state** — no UI contract. Governed forward-test
  campaigns (FTEP-V1-001/002) are tracked in program docs and Paper forward
  tests (`/paper/forward-tests`, account-bound, rendered in the Paper
  Workspace); Research links out rather than duplicating.

## Object model (kept distinct)

Opportunity, Signal (attention item), Hypothesis, Strategy, Research finding,
Experiment, Evidence are **not interchangeable**. On current contracts the
Research surface renders exactly three first-class object families:

1. **Research finding** — an analytics panel (distribution + provenance).
2. **Validation record** — the strategy/model walk-forward evaluation.
3. **Experiment run** — the deterministic simulation ledger.

Opportunities and Signals are *linked* (Radar bridges), never embedded as
research objects. Strategy appears as validation context, never as full
strategy config.

## Information architecture (landed)

Routable sections under `/research` (real links, deep-linkable, per-section
fetch — the old eager triple-fetch tab widget is removed):

| Route | Section | Fetches | Answers |
|---|---|---|---|
| `/research` | Overview | analytics + models + simulation | Claim graph scoped to one analytics finding via `?claim=<panel_key>`: source, hypothesis, strategy, experiment, evidence, contradiction, implementation, forward-test. Off-path nodes stay visible. Synthesis sentences deep-link. |
| `/research/evidence` | Evidence | analytics only | Findings + follow-this-claim hops. `?panel=<key>` deep-links + highlights one finding. |
| `/research/validation` | Validation | models only (+ Paper strategy-profitability in Paper mode) | Strategy/model validation. `?conflict=1` shows only `ABSTAIN_CONFLICTING_EVIDENCE` rows. |
| `/research/simulation` | Simulation | simulation only | Deterministic simulation experiment — not FTEP, not a prospective forward test. |
| `/research/vela-chart-lab` | (redirect) | none | Compatibility alias → `/lab/chart-lab` |

The Overview claim graph is the operator path through a **selected finding**.
`?claim=` must be a real analytics panel key; unknown values are ignored.
Source and evidence deep-link to that panel's provenance. Hypothesis and
FTEP remain **not first-class**; those nodes stay `NOT_EXPOSED` / Not on this
surface and proxy to Validation interpretations or Paper Workspace. Research
does not fetch `/paper/forward-tests`. Choosing a finding is navigation, not
actionability.

`/lab` is a real Lab workbench (UIR-01H). Nav includes Lab. Chart Lab lives at
`/lab/chart-lab`.

### Layering inside a finding/record

- **L1 interpretation** — claim in words, state pill, why it matters.
- **L2 evidence** — chart + mandatory tabular summary, availability/reason.
- **L3 relationships/methodology** — provenance, cross-links to Radar /
  Workspace / Portfolio.
- **L4 technical audit** — `TechnicalDetails`-style `<details>` disclosures:
  raw enums, hashes (CopyableIdentifier), raw epoch timestamps, raw JSON
  (JsonDetailPanel).

## Research vs Lab boundary

Lab is landed as UIR-01H. Research remains the *interpretation* layer
(findings, validation results as evidence, simulation results as evidence).
Lab is the *process* layer (workflow identity, recorded configuration, honest
runnability, current snapshot, Research handoff). Endpoints and queryKeys stay
`/research/models` and `/research/simulation`. `/lab` is a real workbench;
`/research/validation` and `/research/simulation` are **not** removed.

## Presentation adapter additions

`ui/src/state/semanticState.ts` `research` domain gains only real backend
values: epistemic classes (`RESEARCH_PROJECTION`, `SIMULATION_PROJECTION`),
authority boundaries (`READ_ONLY_RESEARCH_VISUALIZATION`, `READ_ONLY_RESEARCH`,
`READ_ONLY_SIMULATION`), preregistration states (`PASS` / `FAIL` / `ABSENT`),
and interpretation outcomes (`signal` / `abstention`). Unknown values keep the
canonical neutral fallback. Abstention reason codes humanize in
`researchPresentation.ts` (pure presentation module), raw codes preserved for
L4.
