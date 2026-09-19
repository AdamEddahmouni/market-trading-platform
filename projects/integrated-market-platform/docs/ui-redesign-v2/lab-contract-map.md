# Lab contract map — UIR-01H

> Authoritative current-contract map for the Lab workbench. Older page
> guidance ([pages/lab.md](pages/lab.md)) remains a *plan*; where it assumed
> runnable experiments, extra object classes, or a backend split, this map
> wins. Rule: current contracts are authoritative; old plans are guidance.
>
> Verified against `origin/main` @ `6a76e632123f6bb58c424d2a081e5984fb7df06b`:
> `ui_api/server.py`, `ui_api/projections.py`, `ui/src/api/schemas.ts`,
> `ui/src/api/endpoints.ts`, `ui/src/api/hooks.ts`.

## What Lab is for

Lab answers: **how do we test or investigate it?** It is the operator-facing
experimental workbench for configuring (where a contract accepts inputs),
inspecting, running *only where a safe operator mutation exists*, and
understanding governed research/testing workflows.

Lab is **not**: an execution cockpit, Workspace, Paper trading, Radar, a raw
developer console, a second Research detail page, FTEP campaign management
(no UI contract), or production-readiness authorization.

## Research vs Lab (landed boundary)

| Surface | Answers | Owns |
|---|---|---|
| **Research** | What do we know, why, and what evidence supports it? | Interpretation, findings, provenance, validation *results as evidence*, simulation *results as evidence*, relationships |
| **Lab** | How do we test or investigate it? | Workflow identity, methodological configuration (read model), run/result inspection, honest availability of actions, handoff *back* to Research |

The same two GET payloads are presented twice with different jobs. Endpoints
and `queryKeys` stay unchanged (`researchModels`, `researchSimulation`).
Research pages are not replaced or redesigned except for a Lab nav/handoff
link if needed.

## Object model (must stay distinct)

| Object | Current UI contract? | Where it appears |
|---|---|---|
| Hypothesis | **No** first-class object | Honest gap on Lab Overview |
| Strategy | Partial — identity/alignment/spec on `/research/models` | Lab Validation (target under test); not a production strategy |
| Experiment | **No** experiment ID or lifecycle | Simulated by workflow cards, not a CRUD object |
| Run | **No** run list, run ID, queue, or progress | Simulation payload is a *single current result snapshot*, not a run ledger |
| Simulation | Yes — `GET /research/simulation` | Lab Simulation workbench + Research interpretation |
| Validation | Yes — `GET /research/models` | Lab Validation workbench + Research interpretation |
| FTEP | **No** Lab/operator campaign contract | Gap. `/paper/forward-tests` is Paper/Workspace account-bound, not Lab |
| Result / evidence | Yes — interpretation rows, ledger, reconciliation | Lab L3 + Research |
| Research finding | Analytics panels on `/research/analytics` | Research only (Lab links out) |
| Production readiness | **No** | Must never be implied by a Lab result |

A simulation snapshot is not FTEP. A validation result is not production
readiness. Inspecting Lab is not trading authorization.

---

## Capability inventory

### Available now — inspectable / read-only

#### 1. Strategy/model validation workflow — `GET /research/models`

| | |
|---|---|
| **Endpoint** | `GET /research/models` |
| **Frontend schema** | `ResearchModelsResponseSchema` |
| **Query key** | `queryKeys.researchModels` |
| **Hook** | `useResearchModelsQuery()` |
| **Object identity** | No experiment/run ID. Identity is `strategy_spec.strategy_identity_hash` + `dataset_manifest.dataset_fingerprint` + `model_summary.model_family` (`naive_last_value.v1` from projection) |
| **Read vs mutate** | **Read-only** |
| **Inputs / configurable parameters** | None accepted by the UI API. Payload is a projection of the replay store strategy fixture at `prediction_cutoff()` |
| **Status** | `preregistration_status`: `PASS` / `FAIL` / `ABSENT` (optional). No queued/running/cancelled enum |
| **Result** | `interpretation_summary` + `interpretations[]` (`outcome` `signal`/`abstention`, times as epoch ns, abstention reason codes) |
| **Timestamps** | `as_of_context.as_of_time`; per-row `observation_time`, `prediction_cutoff` (epoch ns) |
| **Provenance** | `as_of_context`, `capability_states`, backend `disclaimer` |
| **Evidence class** | `epistemic_class`: `RESEARCH_PROJECTION`; `authority_boundary`: `READ_ONLY_RESEARCH` |
| **Safe operator actions** | Inspect; open methodology disclosure; copy hashes; navigate to Research Validation |
| **Unavailable states** | HTTP/schema failure; empty interpretations at cutoff |
| **Research** | Handoff: `/research/validation` (interpretation of the same payload) |
| **Strategy** | Shows family, alignment (`FORECAST_MOMENTUM` / `WHALE_ALIGNED` / `WHALE_CONTRARIAN`), spec as L4 JSON |
| **FTEP** | Unrelated. Walk-forward on admitted fixture is retrospective validation |
| **Paper/runtime** | No execution. Paper strategy-profitability stays on Research Validation (Paper mode) and Portfolio — Lab may *link*, not embed a second P&L cockpit |

**Availability class:** inspectable / read-only. **Not runnable** from the UI.

#### 2. Deterministic simulation workflow — `GET /research/simulation`

| | |
|---|---|
| **Endpoint** | `GET /research/simulation` |
| **Frontend schema** | `ResearchSimulationResponseSchema` |
| **Query key** | `queryKeys.researchSimulation` |
| **Hook** | `useResearchSimulationQuery()` |
| **Object identity** | No run ID. Closest identifiers: `risk_policy_id`, per-row `intent_id` / `fill_id` / `risk_decision_id` |
| **Read vs mutate** | **Read-only** |
| **Inputs / configurable parameters** | None accepted by the UI API. Projection of `store.evaluation` PIT-filtered to cutoff |
| **Status** | `reconciliation.status`, optional `fill_audit.status` (e.g. `PASS`). `mode_label`: `SIMULATION`. No queued/running/progress |
| **Result** | `ledger_summary` (minor units), `risk_decisions[]`, `fills[]`, `orders[]`, `intents[]`, `attributions[]` |
| **Timestamps** | `as_of_context`; fill/decision times on rows (PIT-filtered) |
| **Provenance** | disclaimer: deterministic bar-conservative simulator; no execution authority |
| **Evidence class** | `epistemic_class`: `SIMULATION_PROJECTION`; `authority_boundary`: `READ_ONLY_SIMULATION` |
| **Safe operator actions** | Inspect; methodology/audit disclosure; copy IDs; navigate to Research Simulation |
| **Unavailable states** | HTTP/schema failure; empty ledger |
| **Research** | Handoff: `/research/simulation` |
| **Strategy** | Indirect via evaluation; not a strategy editor |
| **FTEP** | **Must not be labeled forward test** |
| **Paper/runtime** | Simulated ledger only. Does not place Paper/Live orders |

**Availability class:** inspectable / read-only. **Not runnable** from the UI.
History: **one current snapshot**, not a run list. Do not fabricate a run ledger.

#### 3. Chart Lab — local synthetic Vela playground

| | |
|---|---|
| **Endpoint** | None |
| **Object identity** | Local React state only |
| **Read vs mutate** | Local UI state (tick-sim / backfill buttons). **Not a backend mutation.** Does not create research evidence |
| **Evidence class** | None — adapter playground, not an experiment result |
| **Current route** | `/research/vela-chart-lab` (lazy `ImpVelaChartLabPage`) |
| **Lab target** | `/lab/chart-lab` with redirect from `/research/vela-chart-lab` |
| **Research** | Not an evidence record; keep wording that this is tooling, not a finding |
| **FTEP / Paper** | Unrelated |

**Availability class:** local-only tooling. Do not present Chart Lab as a
governed experiment or as evidence.

### Read-only adjacent (do not absorb as Lab workflows)

| Contract | Why it is not a Lab workflow |
|---|---|
| `GET /research/analytics` | Research findings. Lab Overview may *link* to Research Evidence |
| `GET /paper/strategy-profitability` | Paper attribution; Portfolio + Research Validation (Paper) |
| `GET /paper/forward-tests` | Account-bound Paper forward-test list; Workspace/Paper, not Lab campaign control |
| Opportunity evidence overlay | Radar/Research bridge |
| Paper order preview/submit | Workspace only |

### Planned / absent — no current Lab contract

Do **not** render enabled controls for these. Show as documented gaps.

| Gap | Missing contract | UI treatment |
|---|---|---|
| Start / cancel / retry validation | No POST for models | "Read-only · produced by replay/research projection" |
| Start / cancel / retry simulation | No POST for simulation | Same |
| Experiment CRUD / experiment IDs | No experiment resource | Do not mint fake IDs |
| Run history / run IDs / queue / progress % | Single snapshot GETs | Current-result state only |
| Configurable date range, dataset, folds, parameters | Projection has no request body | Methodology shows *recorded* config, not an editor that posts |
| Hypothesis objects | None | Overview gap |
| FTEP campaign manager | None on UI API | Overview gap; do not relabel simulation |
| Benchmark Protocol UI | Not a Lab operator contract | Out of scope |
| Evidence-class upgrade / overwrite | Forbidden | UI must not offer it |

---

## Mutations

**NO LAB MUTATIONS ADDED.**

There is no UI API mutation that creates experimental evidence, alters
governed experiment state, or starts a validation/simulation run. Chart Lab
buttons mutate local component state only.

Do not wire buttons to developer CLIs, `IMP_PAPER_EXECUTION`, or
non-canonical endpoints.

Mode behavior: Lab availability does **not** depend on Demo/Paper/Live
execution mode. Live data mode must not imply Live experiment authority.
Demo remains read-only; Paper mutations stay in Workspace; Live stays
observational.

---

## Information architecture (supported by contracts)

Do not create tabs for nonexistent objects.

| Route | Section | Fetches | Role |
|---|---|---|---|
| `/lab` | Overview | models + simulation (summaries) + read-only `GET /operator/diagnostics` | What can be done, what is read-only, current result state, Item 9/Live honesty, gaps, Research handoff |
| `/lab/validation` | Validation workbench | models only | Process: target, methodology, recorded config, result summary, Research link |
| `/lab/simulation` | Simulation workbench | simulation + shared operator diagnostics | Process: assumptions, ledger, reconciliation, Item 9/Live honesty, Research link |
| `/lab/chart-lab` | Chart Lab | none | Existing synthetic playground, re-homed |

Methodology is a **disclosure on Validation (and Simulation audit)**, not an
empty fifth module. FTEP and Hypothesis appear as Overview gaps, not tabs.

Deep-link compatibility:

- Remove `/lab` → `/research` only when `/lab` is coherent.
- `/research/vela-chart-lab` → `/lab/chart-lab`.
- `/research/validation` and `/research/simulation` **stay** as Research
  interpretation surfaces.

Primary nav: add **Lab** → `/lab` between Research and Control. Today Lab is
absent from `NavShell` (only a redirect existed).

---

## Evidence integrity

- Preserve `epistemic_class` and `authority_boundary` via `semanticState`
  adapters; raw values remain in L4.
- Do not overwrite, relabel, or upgrade evidence class in the UI.
- Do not convert retrospective walk-forward / simulation into prospective
  FTEP language.
- Do not invent progress, extra timestamps, or run identities.
- Hashes and fingerprints: CopyableIdentifier in methodology, never silent
  truncation as the only identity.
- Missing recorded fields stay `UNKNOWN`. Fetch failures stay `UNAVAILABLE`.
- Experiment ID, run ID, benchmark comparison, FTEP, and hypothesis objects
  are `UNKNOWN` / unsupported — never synthesized.
- Item 9 corpus progress (e.g. 2/3), `IDLE` vs `DEGRADED`, Live OFF, and
  `NOT CALIBRATED` come from `GET /operator/diagnostics` (same `queryKeys.operatorDiagnostics`
  as Control). Lab does not mint 2/3, calibrate, or treat Full30 as a Lab action.
  Overview dual-failure and Simulation snapshot errors still mount the honesty
  panel (diagnostics is a separate query). Failed diagnostics stay `UNAVAILABLE`.
  Summary pills expose accessible names (`Item 9 date-gate: IDLE`,
  `Item 9 calibration: NOT CALIBRATED`, `Live real-money execution: Live OFF`).
- `fill_audit.status` is an audit check, not fill-price realism, cost, or
  slippage. Those remain `UNKNOWN`/`UNAVAILABLE` until dedicated fields exist.

## Backend / API issues

### Required blocker

None for a coherent inspectable workbench. Essential Lab increment can land
as read-only workflow inspection + honest “not runnable” + Research handoff.

### Optional future capability

| Missing | Suggested shape | Why backend |
|---|---|---|
| Start validation/simulation | Explicit POST with input identity, producing an immutable run ID + evidence class | UI must not mint evidence |
| Run list | `GET` collection with workflow, state enum, started/completed, evidence class | History cannot be honest without it |
| FTEP operator contract | Campaign identity, prospective window, status distinct from `SIMULATION_PROJECTION` | Prevents conflation |
| Configurable parameters | Request schema of accepted fields only | Frontend knobs that do not POST are fake |

---

## Implementation constraints

- Reuse `queryKeys.researchModels` / `queryKeys.researchSimulation`.
- Reuse `queryKeys.operatorDiagnostics` for Item 9 / Live honesty; do not add a second diagnostics key.
- Lazy-load the Lab route chunk; do not raise the 200 KiB gzip entry budget.
- Import Lab CSS from the lazy Lab surface, not `App.tsx` static imports.
- Keep `@luxalgo/vela` off App and Lab overview static imports (Chart Lab
  remains its own lazy page).
- No new form/graph/JSON-viewer libraries.
- Item 7 / `IMP_PAPER_EXECUTION` / execution gates: untouched.
- Research redesign: no reopen except minimal shared-component / nav /
  handoff integration.
