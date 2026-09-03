# Integrated Market Platform: Canonical Foundation Design and Roadmap Revision 3

**Logical ID:** `foundation.canonical_specification.revision_3`

**Status:** `PROPOSED_PENDING_EXACT_HASH_APPROVAL`

**Date:** 2026-08-14

**Scope:** Donor-repository integration, research-model architecture, historical-dataset architecture, institutional evidence, provider-neutral research assistance, and roadmap clarification

**Implementation authority:** None

**Phase transition authority:** None

## 1. Decision and effectivity

This revision proposes a governed expansion of the Integrated Market Platform's
long-term architecture. It formally recognizes two additional donor/reference
projects and adopts **Swim With the Whales** as a project-wide research
philosophy without weakening point-in-time correctness, provenance, capability
honesty, risk independence, reproducibility, or the no-live boundary.

This document is not effective merely because it exists in the repository. It
becomes the sole forward-looking canonical foundation authority only after an
attributable approval names both:

- logical ID `foundation.canonical_specification.revision_3`; and
- the exact SHA-256 of these bytes as freshly verified after review.

Until that approval, Revision 2 remains the controlling Phase 0 authority and
this document is a proposal. Vague approval, approval of a prior draft, or
approval without the exact hash has no governance effect.

Upon exact-hash approval:

1. Revision 3 supersedes Revision 1 for forward-looking architecture and roadmap
   interpretation.
2. Revision 2 remains incorporated by exact reference and continues to control
   the authorized Phase 0 structural/evidence subject wherever Revision 3 does
   not impose a stricter rule.
3. Existing candidate evidence roots remain immutable historical artifacts for
   their bound repository subject. They are not rewritten, deleted, or presented
   as evidence for the new repository HEAD.
4. A new candidate evidence root may be produced only through a separately
   reviewed evidence transition that binds Revision 3, the new subject manifest,
   all applicable authorities, and a fresh assertion run.
5. Phase 0 remains formally unaccepted until its existing postroot review,
   approval, acceptance-index, and deterministic-final-gate requirements pass.
6. Phase 0A, provider connections, paper-broker submission, live trading, model
   implementation, whale ingestion, and AI integration do not become authorized.

No previously approved artifact is edited in place. Any correction to this
proposal creates another immutable revision.

### 1.1 Immutable authority bindings

This proposal relies on the following exact existing artifacts:

| Logical ID | Repository-relative path | SHA-256 | Relationship |
|---|---|---|---|
| `foundation.canonical_specification.revision_1` | `docs/superpowers/specs/2026-08-13-integrated-market-platform-foundation-design.md` | `B4EAE3240F6F968A6B393263D849013259A00187E209C8632E38DE890996D04D` | Superseded for forward-looking interpretation only upon Revision 3 effectivity |
| `foundation.canonical_specification.revision_2` | `docs/superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-2.md` | `56F6C424EF83BE6042E06D716F3BBE87A1E1B7FE7EBEB15B7EECD875131BC06A` | Incorporated Phase 0 safety and authorization boundary |
| `phase0.governance_plan` | `docs/superpowers/plans/2026-08-13-phase-0-governance-and-no-live-safety.md` | `EE22C688167F5016D7ED1953BB1DAE516BC6AB343655A7D96535C6605D37E904` | Continues to control Phase 0 acceptance procedure |

If any bound bytes do not match, Revision 3 remains `BLOCKED` from effectivity
until a new immutable proposal resolves the difference. No inferred latest file,
path alias, or mutable link may replace these bindings.

## 2. Controlling boundaries

The workspace root is a collection directory, not the canonical Git repository.
The canonical future platform remains `integrated-market-platform/`. Donor
projects remain physical siblings outside that Git boundary.

The platform transfers validated knowledge, not repositories. A donor may
contribute concepts, algorithms, abstractions, test oracles, interface patterns,
or deliberately ported techniques only after provenance, licensing, semantic,
phase, and verification gates are satisfied.

The following remain non-negotiable:

- provider independence and capability-specific interfaces;
- canonical internal contracts before provider, API, UI, model, or LLM DTOs;
- explicit `event_time`, publication, observability, receipt, ingestion,
  correction, and availability semantics;
- deterministic replay with no hidden network access;
- immutable raw evidence and traceable derived evidence;
- explicit missing, stale, conflicting, inferred, and unavailable states;
- separation of measurement, forecast, strategy, risk, execution, and accounting;
- no universal opaque buy score or universal whale score;
- no unsupported identity, intent, market-microstructure, calibration,
  profitability, or predictive claim;
- no live provider or broker path until separately authorized.

## 3. Workspace donor/reference inventory

Seven projects are recognized as external donor/reference/oracle sources:

| # | Observed collection path | Primary reference value | Canonical status |
|---|---|---|---|
| 1 | `Eric_futuresX-main` | Futures, depth, session, contract, replay, and execution experiments | External donor/reference |
| 2 | `tradingCVDBubble-main (1)` | CVD, OFI, aggressor classification, depth measurements, and visual patterns | External donor/reference |
| 3 | `short-squeeze-project` | Evidence provenance, freshness, missingness, readiness gates, and squeeze research | External donor/reference |
| 4 | `internship-project-main` | News/options workflow, audit concepts, liquidity gates, and paper evaluation | External donor/reference |
| 5 | `L1VolumeBubble-main (1)` | Volume-anomaly and absorption visualization heuristics | External donor/reference |
| 6 | `DS-340W-Fantasy-Football-Prediction-main/DS-340W-Fantasy-Football-Prediction-main` | Time-series model comparison and robustness research patterns | External donor/reference |
| 7 | `DS-440-CAPSTONE-GridIQ-main/DS-440-CAPSTONE-GridIQ-main` | Dataset, cache, API, frontend, persistence, and grounded-chat patterns | External donor/reference |

The two new donors are extracted snapshots without observed `.git` metadata.
Their branch, HEAD, upstream, and remote therefore resolve to `UNAVAILABLE`, not
to guessed GitHub state. Their nested folder spelling is recorded exactly as
observed. They must not be renamed, modified, staged, imported, or treated as
clean-clone dependencies under this revision.

## 4. Donor reuse policy

Every meaningful donor component receives one reuse classification:

- `DIRECTLY_REUSABLE`: byte reuse may be considered only after complete rights,
  provenance, dependency, security, and semantic verification. This designation
  does not itself authorize copying.
- `PORT_ADAPT`: re-express the validated behavior behind canonical contracts,
  with parity or intentional-divergence tests.
- `CONCEPT_ONLY`: retain the architectural or methodological lesson; implement
  independently.
- `REFERENCE_ONLY`: consult for requirements, user experience, failure modes, or
  test design; do not port implementation.
- `DO_NOT_USE`: exclude because of domain baggage, leakage, unsafe behavior,
  secrets/private data, unclear rights, misleading semantics, or unsupported
  claims.

Default classification is `CONCEPT_ONLY` when licensing or provenance is
ambiguous. Direct copying is prohibited until an accepted donor-reuse decision
records exact source paths and commits, copyright ownership, third-party origin,
allowed use, redistribution/publication rights, dependency obligations, and the
canonical destination.

Donor code never defines canonical semantics. API payloads, dataframes, database
tables, model outputs, UI types, and LLM prompts from a donor are evidence about a
possible design, not platform contracts.

## 5. DS-340W donor assessment

### 5.1 Useful knowledge

DS-340W contributes candidate research patterns:

- common-target comparison across univariate ARIMA, ARIMAX, and neural models;
- entity-level forecasting and parallel work scheduling;
- explicit train/holdout splits and forecast-error summaries;
- exogenous/contextual design matrices;
- zero-variance column removal;
- QR-based rank-deficiency reduction;
- scaling parameters derived from the fitted design matrix;
- primary-model failure handling and simpler fallback models;
- model-specific outputs, diagnostics, and comparison artifacts.

These are future research inputs, not production dependencies or validated
financial methods.

### 5.2 Point-in-time defect

The comparison scripts explicitly construct holdout ARIMAX and neural inputs from
actual future context rows. Those rows include realized game-context quantities
such as rush and pass attempts. This is acceptable only for a conditional
scenario experiment that clearly assumes known future covariates; it is not a
point-in-time forecast comparison.

Therefore:

- bundled backtest summaries and win rates are `DO_NOT_USE` as evidence of model
  superiority for the market platform;
- the scripts are not financial evaluation oracles;
- future covariates must be labeled by their own availability semantics;
- a market experiment may use only values available at its prediction cutoff or
  a separately versioned forecast/scenario for each future covariate;
- actual holdout values must never be silently substituted for forecast-time
  inputs.

### 5.3 Reproducibility and data limits

The donor has no observed repository-level license, dependency lock, automated
test suite, deterministic seed contract, or immutable source-data manifest.
Some scripts install R packages dynamically and query nflverse/nflfastR sources
at runtime. Package versions and source revisions are not pinned.

The bundled workbook contains one 4,401-row, 35-column annual fantasy-stat sheet;
its columns include `Year` but no weekly availability field. The active modeling
scripts instead fetch player stats, schedules, and play-by-play remotely. Bundled
CSV files are derived forecasts and summaries, not authoritative source data.
Football data, fantasy weights, player identities, results, and outputs remain
donor-only and are not financial training data.

### 5.4 Canonical reuse conclusion

| Component | Classification | Reason |
|---|---|---|
| Train-derived scaling, variance removal, and rank handling | `PORT_ADAPT` | Useful robustness behavior; requires deterministic contracts and tests |
| Fallback sequence | `PORT_ADAPT` | Useful failure design; fallback identity and diagnostics must be explicit |
| ARIMA/ARIMAX/NN family comparison | `CONCEPT_ONLY` | Useful common harness; donor results are not PIT-valid market evidence |
| Per-entity parallel modeling | `CONCEPT_ONLY` | Useful scheduling pattern; determinism and resource bounds are unresolved |
| Actual-future-xreg backtest | `DO_NOT_USE` | Look-ahead for forecast claims |
| Dynamic package installation | `DO_NOT_USE` | Hidden network and mutable dependency state |
| Football datasets, weights, and forecasts | `DO_NOT_USE` | Wrong domain, unclear rights/provenance, no financial meaning |

## 6. GridIQ donor assessment

### 6.1 Useful knowledge

GridIQ contributes candidate patterns:

- Parquet column projection and schema inspection;
- predictable dataframe column ordering and missing-column accommodation;
- in-memory and disk caching;
- FastAPI routers, Pydantic schemas, and SQLAlchemy persistence;
- backend transformation of source data to frontend-oriented DTOs;
- typed frontend API access, React Query lifecycle state, Zod parsing, Zustand
  state, chart composition, and explicit loading/error views;
- conversation and message persistence;
- contextual dataset injection, model identity, token accounting, and grounded
  prompt instructions.

### 6.2 Dataset/cache limits

The Parquet reader downloads an entire remote object into memory, optionally
projects columns, and fills absent requested columns with `NA`. The schedule
loader attempts remote access before disk fallback and stores a derived frame
under a fixed cache path. The play-by-play cache is bounded by season count, not
bytes, and downcasts some values. The cache lacks content hashes, immutable
dataset identity, source/version manifests, deterministic invalidation, explicit
license binding, correction policy, offline replay isolation, and proof that
caching does not change semantics.

Accordingly, these implementations are not canonical dataset infrastructure.
Missing columns must not be silently interpreted as supported capabilities, and
remote-first fallback is prohibited during deterministic replay.

### 6.3 API, frontend, and AI limits

The FastAPI transformation layer and frontend state patterns are references, but
football DTOs cannot become market contracts. GridIQ is hardwired to Gemini and
its runtime context is not a provider-neutral inference interface. Future market
AI must cite canonical evidence and remain outside strategy, risk, execution, and
position mutation authority.

The frontend's observed `LICENSE` file contains only an MIT title and copyright
line, not the complete MIT grant and disclaimer. The repository root has no
observed license file despite the README link. This does not establish that the
repository or backend is MIT-licensed.

The bundled SQLite database contains user records, password hashes, conversation
records, and message content. It is private/derived donor state, not a reusable
dataset, fixture, or publication artifact. Its values must not be inspected,
copied, committed, or redistributed by the canonical platform.

### 6.4 Canonical reuse conclusion

| Component | Classification | Reason |
|---|---|---|
| Column projection and schema inspection | `PORT_ADAPT` | Useful performance/compatibility behavior with stricter manifests |
| Missing-column fill | `CONCEPT_ONLY` | Must preserve explicit `UNAVAILABLE`; never imply capability |
| Remote Parquet loader | `REFERENCE_ONLY` | Unbounded memory and hidden network behavior |
| In-memory/disk dataframe cache | `CONCEPT_ONLY` | Requires identity, hashes, byte bounds, and deterministic invalidation |
| Generic JSON TTL cache | `REFERENCE_ONLY` | Operational cache is not a canonical dataset store |
| FastAPI router/DTO organization | `CONCEPT_ONLY` | Useful boundary pattern after core contracts stabilize |
| React Query/Zod/Zustand/chart patterns | `CONCEPT_ONLY` | Useful UI lifecycle patterns; football UI and types are excluded |
| Conversation/message/model/token persistence | `PORT_ADAPT` | Useful audit shape with privacy, evidence, and provider-neutral redesign |
| Gemini-specific invocation and fallback list | `DO_NOT_USE` | Hidden provider coupling and insufficient research-safety contract |
| Bundled SQLite contents | `DO_NOT_USE` | Private user/auth/conversation data |
| Football analytics, playbook, and mascot components | `DO_NOT_USE` | Domain-specific baggage |

## 7. Long-term canonical architecture

The future logical flow is:

```text
lawful provider / public / research sources
  -> source-specific adapters
  -> canonical normalization
  -> canonical events and disclosures
  -> point-in-time quality and capability engine
  -> immutable dataset publication
  -> deterministic replay
  -> versioned feature snapshots
  -> research datasets
  -> model forecasts and uncertainty
  -> strategy interpretation or abstention
  -> order intent
  -> independent risk
  -> authorized execution simulation
  -> fills
  -> positions, cash, P&L, and accounting
  -> attribution and reporting
  -> read-only research API, UI, and AI explanation surfaces
```

Institutional/whale evidence is a versioned evidence and feature family. It does
not form an execution shortcut. The AI surface is a read/explain/propose
consumer. It does not form an execution shortcut.

## 8. Point-in-time and availability architecture

Every source fact and derived feature must answer:

1. What happened or was reported?
2. When did the underlying event occur or become effective?
3. When did the publisher release it?
4. When could the platform lawfully and technically observe it?
5. When did the platform receive or ingest it?
6. Was it revised, corrected, canceled, or amended later?
7. Which source, source version, parser, and feature definition produced it?
8. Which capability and quality state applied at the decision cutoff?

No new contract may collapse these questions into a generic `timestamp`.
Existing canonical envelope semantics remain the minimum. Research-domain
extensions may include:

- `effective_at` for the market-valid or reporting-period state;
- `published_at` or canonical `source_publish_time`;
- `available_at` or canonical `available_time`;
- `received_at` for a live collector boundary;
- `ingested_at` for operational historical lineage only;
- `revised_at`, `amended_at`, or supersession identity where applicable.

Training cutoffs and replay visibility are governed by `available_time`, not by
event time, reporting-period end, file modification time, or ingestion time.
Reference data, constituents, corporate actions, earnings, filings, economic
series, short-interest records, options open interest, and news must preserve
revision and publication history sufficient for the intended claim.

Explicit guards are required against look-ahead, survivorship, revised-data,
corporate-action, future-constituent, future-earnings, future-news, and mislabeled
timestamp leakage.

## 9. Historical dataset architecture

Future abstractions may include `DatasetStore`, `HistoricalDataSource`,
`CanonicalDatasetReader`, `ColumnProjection`, `DatasetManifest`,
`DatasetFingerprint`, and `DatasetCache`. Names remain provisional until the
applicable ADR is accepted.

A published dataset manifest must bind at minimum:

- dataset ID and immutable version;
- content and manifest hashes;
- provider/source, publisher, venue, entitlement, and license;
- instrument mapping and mapping version;
- schema and parser versions;
- timestamp and correction semantics;
- coverage, row count, first/last event, and partitions;
- capability claims with evidence rather than column-name inference;
- quality state and known defects;
- retention, redistribution, and reproducibility requirements.

Canonical reads are immutable and hash-verified. Caches are explicitly derived,
byte-bounded, version-aware, and disposable. Cache hit or eviction may change
latency but not canonical results. Replay performs no hidden network access. A
missing requested column produces a schema/capability result such as
`UNAVAILABLE`, `REJECTED`, or an explicitly permitted nullable projection; it is
never silently converted into claimed source capability.

## 10. Model Research Layer

The long-term architecture adds a gated Model Research Layer:

```text
canonical events
  -> point-in-time FeatureSnapshot
  -> ResearchDataset
  -> ForecastModel
  -> Prediction and uncertainty
  -> ModelEvaluation and CalibrationReport
  -> separately inspectable strategy evidence
```

Candidate abstractions are `ResearchDataset`, `FeatureSnapshot`,
`FeatureProvenance`, `ForecastTarget`, `ForecastModel`, `ModelSpec`,
`TrainingManifest`, `ModelArtifact`, `Prediction`, `PredictionInterval`,
`ModelEvaluation`, `WalkForwardRun`, and `CalibrationReport`.

Models consume canonical, point-in-time feature snapshots, never raw provider
objects. Targets are explicit and versioned by definition, horizon, sampling,
label time, availability rule, neutral/missing behavior, and economic meaning.
Possible research targets include return, excess return, realized volatility,
volatility expansion, breakout/reversal probability, squeeze ignition, future
order-flow imbalance, liquidity withdrawal, spread widening, adverse selection,
range, volume, catalyst reaction, or regime transition. Raw price is not the
default target.

Every prediction binds model ID/version, code hash, training manifest, training
dataset hashes, feature/target definitions, hyperparameters, random seed,
inference cutoff, horizon, uncertainty, and source-data cutoff. A prediction
without this reproducibility metadata is not canonical research evidence.

### 10.1 Evaluation rules

- Use expanding or rolling walk-forward evaluation with explicit embargo or
  purging where label overlap requires it.
- Fit imputation, category handling, scaling, variance selection, and rank
  handling only on the training window.
- Populate validation/test features only with information available at each
  historical prediction cutoff.
- Treat a forecasted future covariate as its own versioned prediction with
  provenance and uncertainty.
- Record fallback model identity and failure diagnostics; do not silently report
  fallback output as primary-model output.
- Pin seeds, dependencies, thread/process configuration, and serialization.
- Compare predictive accuracy separately from simulated trading performance.

### 10.2 Baselines before complexity

**Complex models must beat simple baselines.** Depending on target semantics,
the comparison set includes naive persistence, unconditional mean, rolling mean,
simple/regularized linear models, ARIMA, and ARIMAX where future covariates are
legitimate. Tree and neural models are research candidates, not mandatory
dependencies.

Predictive evaluation may use MAE, RMSE, log loss, Brier score, calibration
error, precision/recall, ROC-AUC where appropriate, and rank correlation.
Return, Sharpe, Sortino, drawdown, expectancy, turnover, slippage/fee sensitivity,
exposure, and tail loss are strategy/execution-simulation results only. Forecast
accuracy is not trading profitability.

## 11. Forecast, strategy, risk, and execution separation

The canonical path remains:

```text
model forecast
  -> strategy interpretation
  -> signal or abstention
  -> order intent
  -> independent risk decision
  -> authorized execution simulator
  -> fill
  -> portfolio/accounting
  -> attribution
```

A model estimates a target. A strategy decides how selected evidence affects a
preregistered hypothesis. Risk independently approves, rejects, or resizes an
intent. Execution simulates or, only in a later separately authorized system,
routes an approved order. No forecast-error backtest substitutes for execution
simulation.

## 12. Swim With the Whales doctrine

> **Swim With the Whales:** The platform should seek to understand where large,
> informed, institutional, or structurally important market participants are
> likely exerting measurable influence, and where evidence supports it, prefer
> to align research and trade hypotheses with those flows rather than blindly
> fighting them.

The operational philosophy is:

```text
observe -> verify -> contextualize -> align when justified
```

It is not:

```text
see a big trade -> invent an identity or intent -> blindly follow it
```

The platform studies footprints. It does not claim anonymous participant
identity, hidden motivation, informed status, manipulation, or future intent
unless a source can actually establish the claim.

Observed fact, derived measurement, hypothesis, strategy interpretation, risk
decision, and execution result are separate provenance layers.

## 13. Institutional/whale evidence taxonomy

Future evidence families remain separately inspectable:

1. **Regulatory/disclosure:** Form 4, Schedule 13D/G, Form 13F, amendments,
   insider transactions, beneficial ownership, and institutional holdings.
   Reporting period, filing/acceptance/availability time, filer, issuer, form,
   amendment, accession, shares/value, and source are retained. Delayed filings
   are never described as live positions.
2. **Large transactions:** unusually large equity, futures, or options trades,
   repeated aggressive executions, sweeps, or clustered size anomalies when
   supported. Size is normalized to the relevant distribution, ADV, rolling
   volume, float, open interest, market capitalization, contract liquidity, or
   visible depth. A fixed share count is not a universal whale threshold.
3. **Order-book:** persistent visible liquidity, replenishment, withdrawal,
   multi-level imbalance, consumption, absorption, or exhaustion when actual
   depth supports it. Anonymous book events receive no invented identity;
   iceberg/hidden-liquidity claims require an accepted inference method.
4. **Order flow:** CVD, signed volume, trade-size distribution, aggressive-large-
   trade concentration, quote depletion, liquidity consumption, OFI, and
   persistent pressure. Aggressor provenance distinguishes native, quote-rule,
   tick-rule, other inferred, and unknown classification.
5. **Options:** unusual volume, volume/open-interest relationships, open-interest
   change, premium, strike/term concentration, skew, IV, liquidity, and exposure
   estimates. Direction and trader intent remain ambiguous unless established;
   unusual calls are not automatically bullish whale trades.
6. **Futures positioning:** CFTC public aggregates, relevant trader categories,
   volume/open-interest changes, roll behavior, basis, and multi-market context.
   Delayed aggregate reports remain distinct from live order flow.
7. **Fund/ETF/cross-asset:** flows or proxies, creations/redemptions, index
   rebalance, sector/rates/volatility context, correlations, and regime state.
8. **Public catalyst:** earnings, guidance, filings, offerings, buybacks, M&A,
   activist filings, insider purchases, macro releases, sector catalysts, and
   breaking news, each with source and availability semantics.

## 14. Evidence bundles without score collapse

A future `WhaleEvidenceBundle`, `InstitutionalFlowContext`, or similarly named
object may group facts for one instrument and as-of cutoff. Naming requires an
ADR. The object preserves evidence items, family, supported directionality,
magnitude and normalization, source, provenance, freshness, confidence, quality,
contradictions, and missing capabilities.

States may describe no evidence, passive/aggressive accumulation or distribution
evidence, liquidity support/withdrawal, disclosure accumulation/distribution,
mixed/conflicted, stale, or unavailable. They do not claim motivation.

Options, Level-2 imbalance, filings, CVD, short interest, news, and large prints
must not be averaged into one opaque universal whale or buy score. Strategies may
define transparent confluence over selected dimensions. A rigorously specified
and calibrated model output may be a score, but its target, version, calibration,
inputs, uncertainty, and limitations must remain explicit.

Contradiction is information. Evidence supports states such as `supports_long`,
`supports_short`, `neutral`, `ambiguous`, `conflicting`, `stale`, and
`unavailable`; strategies may abstain rather than force agreement.

## 15. Strategy relationship to whale evidence

Every future strategy specification declares itself `WHALE_ALIGNED`,
`WHALE_NEUTRAL`, or `WHALE_CONTRARIAN`.

A whale-aligned strategy documents qualifying evidence, freshness, required
agreement, contradiction policy, timing, invalidation, and risk implications. A
whale-contrarian strategy documents why measurable pressure is expected to
reverse. Evidence presence never automatically authorizes entry.

Whale evidence remains strategy input. It cannot create order intent by itself,
override risk, bypass execution authorization, or mutate portfolio/accounting.

## 16. Evidence and model provenance chains

Every institutional claim must resolve through a complete chain, for example:

```text
SEC filing -> accession/raw filing -> parser version -> canonical disclosure
  -> derived ownership delta -> research feature -> strategy decision
```

or:

```text
raw trade -> provider/source -> canonical trade -> aggressor classification
  -> normalized large-trade classifier -> evidence item -> strategy context
```

The platform must be able to explain why it described accumulation,
distribution, conflict, or unavailability, including the source limitations.

## 17. Research API and UI

Stable domain APIs may be designed only after canonical internal contracts are
accepted. Candidate families include market instruments/sessions/events/trades/
quotes/depth/features/order flow/options/catalysts/disclosures/whales, research
models/backtests, simulation runs, portfolio, and reports.

API DTOs are projections, not sources of truth. Source-specific shapes do not
leak into core semantics.

Future UI surfaces may include instrument, order-flow, futures, squeeze,
options, catalysts/news, institutional/whale, model research, deterministic
replay, simulation, decision explanation, portfolio/risk, and AI research views.
GridIQ's typed access, query lifecycle, validation, state, chart, and error-state
patterns are design references. Football components are excluded.

## 18. Market Research Assistant boundary

The future assistant uses a provider-neutral `InferenceProvider` or
`LLMProvider` boundary. OpenAI, Anthropic, Gemini, local models, and future
providers are adapters, not architecture.

The assistant may explain signals, evidence, quality flags, market state, model
comparisons, institutional activity, strategy abstention, risk rejection, and
deterministic simulation. Every factual answer cites canonical evidence or marks
the information unavailable/uncertain.

It must not invent market data or sources, bypass missing-data rules, claim
unsupported intent, override risk, mutate positions, silently place orders, or
become the broker. Any future proposal follows:

```text
AI analysis/proposal
  -> structured decision contract
  -> preregistered strategy/rules
  -> independent risk
  -> execution authorization
  -> broker adapter, if a later phase separately permits one
```

The LLM is never the broker.

## 19. Licensing, permission, and donor data

The principal reports that Lucas authorized use of his GitHub materials by
email. That is a user-supplied repository-permission assertion until the exact
message, parties, scope, date, and retained evidence are entered into a private
permission record. It does not establish third-party dependency, dataset,
redistribution, publication, or sublicensing rights.

For each donor, governance distinguishes repository permission, contributor
copyright, dependency licenses, dataset rights, code-copy permission,
redistribution rights, and publication rights.

No donor dataset moves into the canonical repository by default. Each candidate
dataset requires origin, copyright/license, redistribution permission, size,
format, schema, synthetic/public status, immutability, reproducibility, and
financial-research relevance. Football datasets remain donor-only references.

When rights are incomplete, architectural reimplementation is preferred. No
copied donor code or data is published until rights are clear.

## 20. Roadmap revision

The serial foundation sequence remains intact.

### Phase 0 — governance and structural no-live safety

No scope or authorization change. Existing implementation/candidate evidence is
not final acceptance. Revision 3 requires its own exact-hash approval and a fresh
evidence transition before it can participate in current acceptance.

### Phase 0A — data feasibility and donor characterization

Still required and separately authorized. Extend characterization planning to
the two new donors, but do not run their remote fetches or import their code/data.

### Phase 1 — foundational decisions

Add decisions for research dataset identity, point-in-time feature semantics,
model artifact identity and reproducibility, historical cache semantics,
institutional evidence semantics, donor reuse policy, and provider-neutral LLM
boundaries.

### Phase 2 — canonical contracts and replay

No model implementation. Establish reliable canonical data, availability,
revision, quality, identity, and replay contracts first.

### Phase 3 — verified historical adapter

Still required before market model evaluation. Dataset manifests and capability
evidence must establish what the source actually supports.

### Phase 4 — runtime quality and state

Still required before meaningful feature claims. Cache behavior may not weaken
runtime or replay determinism.

### Phase 5 — capability-supported features

Add future interfaces for institutional evidence dimensions without claiming
capabilities absent from the admitted data.

### Phase 5R — research/model infrastructure

After Phases 1 through 5 provide the required contracts, data, replay, quality,
and features, a separately authorized research phase may implement research
datasets, targets, model interfaces, baseline models, manifests, walk-forward
evaluation, artifact identity, PIT guards, calibration, and serialization.

### Phase 6 — preregistered strategy

Forecasts and whale evidence may supply explicit evidence but do not replace
preregistration, abstention rules, or strategy semantics.

### Phase 7 — risk, simulation, and accounting

No change. Independent risk, conservative simulation, position/cash/P&L
reconciliation, and attribution remain mandatory.

### Phase 8 — deterministic end-to-end acceptance

No change. Acceptance remains evidence-bound and makes no unsupported edge claim.

### Later separately authorized research tracks

- Institutional/Whale Intelligence: filings, public positioning, large-print,
  options-flow, fund/ETF-flow, and cross-asset context.
- Market Research Assistant: grounded retrieval, evidence citation, model and
  market-state explanation, abstention/risk explanation, and simulation analysis.
- Research UI: multi-domain dashboards, model comparison, replay inspection, and
  institutional evidence workspaces.

These tracks do not run in parallel ahead of their foundation prerequisites.

## 21. Proposed ADR register

The following decisions are proposed, not accepted:

| ADR candidate | Decision needed | Blocking point |
|---|---|---|
| `ADR-DONOR-001` | Concept, port/adapt, direct-copy, or exclusion policy per component | Before donor code/data reuse |
| `ADR-RDATA-001` | Immutable research dataset identity and fingerprint | Before Phase 5R dataset publication |
| `ADR-PIT-001` | Feature/label availability and leakage-prevention semantics | Before any market model evaluation |
| `ADR-MODEL-001` | Model spec/artifact/prediction identity and reproduction | Before canonical model evidence |
| `ADR-FCAST-001` | Forecast model interface and fallback reporting | Before multiple model families |
| `ADR-DCACHE-001` | Dataset cache identity, byte bounds, invalidation, and replay rules | Before historical dataset caching |
| `ADR-WHALE-001` | Institutional evidence vocabulary and allowed claims | Before whale feature implementation |
| `ADR-LLM-001` | Provider-neutral inference and no-execution authority | Before AI integration |

An ADR cannot authorize its own implementation or mark itself accepted.

## 22. Future verification requirements

### Model tests

- deterministic preprocessing and seed behavior;
- training rows and preprocessing cutoffs never exceed the prediction cutoff;
- scaler/category/variance/rank state derives only from training data;
- no future metadata or revised-data leakage;
- future covariates retain availability and prediction provenance;
- missing-feature and fallback behavior is explicit;
- serialization/reload predictions are equal under the contract.

### Dataset tests

- schema and column projection;
- missing-column capability handling;
- content/manifest hash verification;
- immutable reads and deterministic repeated replay;
- corrupted, duplicate, corrected, and revised data;
- cache invalidation, eviction, and byte limits;
- no network access during offline replay.

### Institutional evidence tests

- delayed filings remain delayed in replay;
- amendment ordering and duplicate filing identity;
- size normalization against the declared reference distribution;
- anonymous trades and book events receive no invented identity;
- unknown aggressor stays unknown;
- stale evidence stays stale;
- conflicting evidence stays conflicting.

### AI tests

- no fabricated evidence or citation;
- citations resolve to canonical evidence;
- missing data produces explicit uncertainty;
- no direct order, position, or accounting mutation;
- risk rejection cannot be overridden;
- provider failure and context overflow fail safely.

## 23. Security and privacy

Donors are scanned by location and classification without publishing secret
values. Credentials are never copied. Future adapters and inference providers
receive secrets through private injection, not committed configuration.

Bundled databases, conversation histories, user identifiers, password hashes,
tokens, API keys, and account information are excluded from canonical fixtures
and publication. A donor's public example configuration is not a production
credential contract.

## 24. Claim policy

Permitted research language includes `historically associated with`,
`predictive in this tested sample`, `outperformed the named baseline under this
experiment`, and `showed evidence of`, with the relevant scope and limitations.

Claims such as `predicts the market`, `tracks smart money perfectly`, `follows
insiders`, `profitable`, or `beats the market` require evidence under the
platform's accepted research, simulation, and acceptance framework. No donor
output supplies that evidence.

## 25. Risks and required mitigations

| Risk | Current state | Required mitigation |
|---|---|---|
| Revision 3 creates a new repository subject | Certain after commit | Preserve old roots; generate a new bound root only after approval |
| Two canonical authorities | Prevented while proposal remains pending | Exact supersession and approval record before effectivity |
| DS-340W actual-future xregs | Observed | Exclude results; implement PIT walk-forward guards |
| Unpinned donor dependencies/network fetches | Observed | Independent locked implementation and offline fixtures |
| Ambiguous donor/dataset licensing | Open | Private permission evidence and dataset/license review |
| GridIQ private SQLite content | Observed | Exclude from inspection beyond schema/counts, copying, fixtures, and publication |
| Cache semantic drift | Open | Hash-bound immutable datasets and disposable deterministic cache |
| Opaque whale-score collapse | Prohibited | Preserve typed evidence dimensions and transparent strategy logic |
| Unsupported participant identity/intent | Prohibited | Fact/measurement/hypothesis separation and claim tests |
| LLM provider/execution coupling | Prohibited | Provider-neutral adapter and no-authority boundary |
| Premature model/whale/AI implementation | Prohibited | Phase and ADR gates |

## 26. Documentation and traceability deliverables

After this proposal is reviewed, the implementation plan may create or update the
minimal authoritative set:

- collection project index recognizing seven donors;
- dedicated DS-340W and GridIQ descriptive notes;
- donor-to-canonical reuse and verification matrix;
- donor permissions/licensing record;
- canonical README links and status warning;
- proposed ADR register and roadmap traceability;
- new evidence-transition configuration and tests only after Revision 3 approval.

Traceability rows bind:

```text
donor component -> reuse classification -> canonical destination -> phase
  -> preconditions -> verification -> rights/provenance state -> risk
```

## 27. Acceptance conditions for this revision

Revision 3 is correctly integrated only when:

1. both new donors are inventoried without modification or blind merge;
2. every meaningful donor component has a reuse classification and destination;
3. DS-340W informs a future model layer while its leaky evaluation is excluded;
4. GridIQ informs dataset/API/UI/AI design without importing football semantics,
   private database content, hidden network behavior, or Gemini coupling;
5. Swim With the Whales is explicit, evidence-based, and incapable of bypassing
   strategy, risk, or execution;
6. no universal whale/buy score, identity invention, profitability claim, or
   hidden look-ahead is introduced;
7. licensing and dataset rights remain explicit and conservative;
8. prior evidence bytes remain unchanged;
9. the new repository subject receives fresh evidence rather than inheriting an
   old root claim; and
10. Phase 0 remains formally unaccepted until its complete acceptance sequence
    passes, with no automatic Phase 0A transition.

## 28. Canonical philosophy

> **Observe deeply. Preserve provenance. Know what was knowable at the time.
> Measure what the data can actually support. Swim with the whales when their
> footprints are genuinely visible. Never pretend to know more than the evidence
> does. Separate forecasts from strategies, strategies from risk, risk from
> execution, and execution from accounting. Research first, validate second,
> trade last.**

In shorter form:

> **Swim with the whales—but only when you can actually see their wake.**

## 29. Next governed action

The next action is review of these exact bytes. If the specification is accepted,
the principal supplies attributable approval naming the logical ID and freshly
verified SHA-256. Only then may a separate implementation plan update supporting
documentation and prepare a new evidence transition. That work still cannot
begin Phase 0A, connect a provider or broker, implement model/whale/AI subsystems,
or place any order.
