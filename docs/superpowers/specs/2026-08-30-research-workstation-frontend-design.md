# Research Workstation Frontend Design

**Date:** 2026-08-30

**Status:** Approved design, pending written-spec review

**Scope:** Research-mode information architecture, visual system, automated research workflow, Research-to-Demo qualification presentation, and the first functional Research frontend prototype

**Base:** `3a4188b6fb0bac7cd836b168a3c6d6b0ec0ed6d0` (`build/imp-xa-05-strategic-state` final head)

## 1. Purpose

The platform needs a professional Research workstation that makes the most
important information visible first, minimizes workflow and input latency, and
keeps automated reasoning understandable and reproducible. The workstation is
the complete laboratory for market investigation, strategy and model creation,
historical evaluation, simulation, replay, stress testing, shadow prediction,
comparison, and improvement.

This design establishes the complete product direction and decomposes it into
implementation stages. The first implementation milestone is a functional,
fixture-backed Research frontend prototype. It does not add paper, live, broker,
or execution authority.

## 2. Relationship to earlier UI designs

This specification extends the read-only capability honesty, deterministic
replay, point-in-time context, and epistemic metadata established by UI-001 and
UI-002.

It intentionally supersedes the mode names and responsibilities in
`2026-08-26-mode-launcher-design.md`:

- the startup launcher becomes **Research / Demo / Live**;
- the earlier Demo historical exploration responsibilities move into Research;
- the earlier Paper destination becomes Demo;
- Live remains a separately guarded environment whose launcher selection does
  not grant execution authority.

All unaffected launcher requirements remain: honest readiness progress, no
persisted default mode, explicit mode identity, accessible controls, responsive
layout, reduced-motion support, failure recovery, and a persistent Switch mode
control.

## 3. Operating-mode boundaries

### Research

Research discovers and explains markets; creates hypotheses, strategies, and
models; runs backtests, simulations, historical replay, stress tests, and
timestamped shadow predictions; compares candidates; diagnoses failure; and
qualifies immutable candidate versions for Demo.

Research creates no paper or live orders and holds no broker authority.

### Demo

Demo is the forward-testing proving ground. It runs Research-qualified packages
in paper-trading environments with simulated orders, fills, positions, fees,
slippage, latency assumptions, risk controls, exits, and P&L. It is not a second
research laboratory, although its observed failures and deviations feed new
inquiries back into Research.

### Live

Live is the environment in which separately approved packages may eventually
operate with real capital. Entering the Live workstation does not itself connect
a broker, authorize a session, enable a strategy, or permit an order. Existing
independent risk, live-safety, session authorization, confirmation, broker, and
reconciliation boundaries remain controlling.

### Promotion

- A candidate version may move from Research to Demo automatically only after
  all configured qualification gates pass and a governed backend capability
  exists to perform that handoff.
- Demo-to-Live promotion always requires explicit human approval and all
  independent live authority checks.
- Until the governed Research-to-Demo handoff exists, the frontend presents
  qualification status and a non-mutating package preview; it must not simulate
  a successful promotion.

## 4. Experience principles

1. **Priority before density.** The first viewport states what matters, why it
   matters, the main uncertainty, and the next useful action before exposing
   detailed tables.
2. **Fast paths remain traceable.** Search, keyboard commands, automatic jobs,
   and prepared actions reduce input time without hiding inputs, versions, or
   evidence.
3. **Automation explains itself.** Every material automated action exposes what
   ran, why it ran, its inputs, its result, and its authority boundary.
4. **Missing is not zero.** Missing, insufficient, stale, and conflicting
   evidence are first-class visible states.
5. **Color has semantic ownership.** Intelligence color is separate from
   outcome color; decorative treatment cannot imply profit, safety, or support.
6. **Graphs earn their space.** A graph is included only when it answers a named
   decision question better than a number, sentence, or table.
7. **Progressive disclosure.** The default view is understandable; technical
   detail, provenance, and reproduction controls are one action away.

## 5. Visual system

The approved direction is a dark-first professional trading terminal:

- graphite and near-black application surfaces;
- restrained frosted matte layers with thin, quiet borders;
- cyan-to-purple accents for intelligence, selection, model activity, regime
  context, and automated workflow state;
- neon green only for favorable observed or evaluated outcomes;
- neon red only for adverse observed or evaluated outcomes;
- amber for caution, incomplete validation, and authority boundaries;
- compact operational typography paired with clear plain-language summaries;
- minimal glow and animation, used only to communicate focus or state change;
- a persistent left Research sidebar on desktop.

The system must not use green or red as decorative brand accents. Color is never
the sole carrier of meaning.

## 6. Research information architecture

The primary left navigation uses workflow language:

1. **Command** — automatic briefing, ranked priorities, active work, warnings,
   and recommended actions.
2. **Explore** — market scanner, instruments, catalysts, cross-asset regimes,
   and deeper market intelligence.
3. **Build** — hypotheses, strategies, features, models, entry logic, exit logic,
   and risk rules.
4. **Test** — point-in-time backtests, historical replay, simulations, stress
   tests, regime cohorts, cost sensitivity, and shadow predictions.
5. **Evaluate** — baseline comparison, profitability, drawdown, failure analysis,
   explainability, evidence quality, and drift.
6. **Promote** — candidates approaching or satisfying Demo qualification.

The sidebar also contains recent inquiries, pinned work, compact watchlists,
active-job counts, and items needing attention. Models, datasets, experiments,
and comparisons remain addressable objects but appear contextually within the
workflow rather than competing as top-level navigation.

On narrower layouts, the sidebar becomes a drawer without changing navigation
order or removing functionality.

## 7. Research Command home

The first viewport answers, in order:

1. What matters now?
2. Where is the earliest credible opportunity to investigate?
3. Why did it rank highly?
4. What could invalidate it?
5. What is running or blocked?
6. What should happen next?
7. Is anything nearing Demo qualification?

The home surface contains:

- a compact market and cross-asset context strip;
- a **Most important now** briefing;
- an opportunity queue ranked by decision value;
- active research jobs with real progress or honest indeterminate state;
- missing, conflicting, stale, leakage, overfitting, and drift warnings;
- a Demo qualification summary;
- automatically prepared next actions.

An opportunity summary shows instrument and investigated direction, why it
appeared now, its timing window, evidence strength, estimated advantage versus a
declared baseline, primary risk, invalidation condition, uncertainty, and current
research state. It is a research candidate, not an instruction to trade.

## 8. Command and interaction model

The global command bar accepts instruments, saved objects, natural-language
questions, and explicit research commands. Example:

`Compare NVDA ignition models during stressed liquidity`

Results first show the parsed scope, cutoff, inputs, baseline, and proposed
action. Read-only searches run immediately. Resource-consuming tests use a brief
review step before launch. Destructive or authority-bearing actions are absent
from Research.

Keyboard navigation supports opening Command, Explore, Build, Test, Evaluate,
and Promote; selecting a ticker; comparing candidates; running a reviewed test;
pinning work; and opening an explanation. All shortcuts have discoverable menu
equivalents.

## 9. Unified Research detail workspace

Selecting an opportunity, hypothesis, candidate, or result opens a consistent
workspace:

`Summary → Market context → Evidence → Reasoning → Risks → Test history → Verdict → Next action`

The workspace may show:

- instrument identity, relevant market state, price, volume, and freshness;
- proposed opportunity and invalidation windows;
- entry and exit reasoning;
- evidence references and epistemic categories;
- declared baseline and evaluated deltas;
- regime dependence and failure cohorts;
- costs, drawdown, tail loss, and concentration;
- related hypotheses, versions, models, datasets, and experiments;
- a plain-language interpretation;
- reproducibility and provenance details in an expandable inspector.

The right evidence rail keeps explanation, gaps, risk, and the next action visible
while the central content changes.

## 10. Meaningful-chart policy

Every chart must declare the question it answers in its title or accessible
description. Approved chart families are:

- price and volume with relevant entry, exit, invalidation, and regime context;
- candidate versus declared baseline;
- drawdown and tail-risk history;
- performance by regime or cohort;
- calibration and prediction accuracy;
- drift through time;
- expected Research behavior versus observed Demo behavior.

Ticker strips use numbers and compact status by default. They receive sparklines
only when recent shape materially changes the decision. Decorative chart walls,
unlabeled gradients, and redundant plots are excluded.

## 11. Research lifecycle and versioning

The canonical user-visible lifecycle is:

`Signal → Inquiry → Hypothesis → Candidate → Experiments → Verdict → Demo Package`

- A signal is an automatically detected or manually entered market condition.
- An inquiry records the question being investigated.
- A hypothesis is explicit, falsifiable, and includes invalidation criteria.
- A candidate freezes strategy or model behavior, including entries, exits,
  eligible markets, risk rules, and assumptions.
- Experiments declare point-in-time inputs, costs, baselines, cohorts, and
  evaluation criteria before execution.
- A verdict is promising, inconclusive, rejected, or Demo-qualified and includes
  plain-language reasons.
- A Demo package is an immutable, versioned bundle of the candidate, required
  inputs, constraints, evidence, and expected behavior.

Automation cannot silently rewrite history. Any material change creates a new
version linked to its predecessor.

## 12. Automation behavior

Within available governed capabilities, Research may automatically scan markets,
rank investigations, create inquiries, prepare hypotheses, launch safe tests,
maintain shadow predictions, detect drift or conflicts, recommend follow-up work,
reject failed candidates, and qualify candidate versions.

The frontend must never claim an automated action occurred unless backed by a
real run or an explicitly labeled deterministic fixture. Each run exposes:

- trigger and reason;
- status and timing;
- cutoff and admitted inputs;
- candidate, model, and policy versions;
- baseline and evaluation rules;
- result, errors, and warnings;
- provenance or trace reference;
- permitted next actions.

Background jobs do not block unrelated Research use.

## 13. Research-to-Demo qualification

Automatic qualification requires the candidate's configured mandatory gates to
pass. The gate set covers:

- point-in-time integrity and leakage prevention;
- deterministic reproducibility;
- declared-baseline advantage;
- out-of-sample performance;
- profitability after realistic costs;
- sufficient samples and market coverage;
- regime robustness;
- drawdown, loss-streak, concentration, and tail-risk limits;
- parameter stability;
- independent exit and invalidation proof;
- stress-test survival;
- evidence completeness;
- Demo operational compatibility.

Thresholds are versioned and strategy-specific. The UI references their owning
policy rather than duplicating mutable values as canonical truth. A failing
candidate displays the weakest blocking gate and the highest-value follow-up
experiment. It does not reduce failure to a generic score.

Demo deviations—such as unexpected fills, excessive slippage, timing mismatch,
loss-limit breaches, drift, or degraded profitability—create linked Research
inquiries when the owning backend workflow exists.

## 14. Data, capability, and epistemic honesty

Every data-bearing surface carries or inherits an as-of context, data mode,
freshness, quality, and capability state. The UI preserves the distinction among
observed facts, reported claims, model outputs, and reference metadata.

The first prototype uses deterministic representative fixtures behind the same
frontend adapter interfaces intended for real APIs. Fixture and replay content
is visibly labeled and cannot appear live. Unsupported capabilities render an
honest unavailable state rather than invented values, rows, charts, or progress.

The frontend consumes canonical DTOs and does not mutate foundation contracts,
promote reference metadata into causal truth, or grant authority from a model,
qualification result, mode flag, or assistant output.

## 15. Loading, empty, stale, and failure behavior

- Startup and background jobs report actual readiness stages.
- Unknown-duration work is indeterminate and never displays fabricated percent
  completion.
- Slow local sections use skeletons without blocking the workstation.
- Empty states explain whether nothing matched, no data exists, or a capability
  is unavailable.
- Stale data remains visible only with an unmistakable stale marker and cutoff.
- Conflicting evidence shows the conflict rather than collapsing to a single
  answer.
- Test failure identifies the failed stage, preserves completed evidence, and
  offers safe retry or revision actions.
- Unknown errors use stable language and do not reveal secrets or raw provider
  payloads.

## 16. Component boundaries

The first implementation should evolve the existing React application through
small, independently testable units:

- `ModeLauncher`
- `ResearchShell`
- `ResearchSidebar`
- `GlobalCommandBar`
- `MarketContextBar`
- `PriorityBriefing`
- `OpportunityQueue`
- `ResearchWorkspace`
- `InstrumentChart`
- `EvidenceRail`
- `ResearchJobActivity`
- `ComparisonPanel`
- `QualificationGatePanel`
- `DemoPackagePreview`
- `ExplanationDrawer`
- `ProvenanceDrawer`

Data acquisition and normalization live behind adapters and validated DTO
schemas. Components receive presentation-ready typed state and do not perform
authority decisions. Large screens compose these units rather than accumulating
all behavior in `ResearchPage.tsx`.

## 17. Implementation stages

### Stage 1 — Foundation

- establish theme and semantic-color tokens;
- revise the launcher to Research / Demo / Live while preserving safety;
- build the Research shell, persistent sidebar, command-bar foundation, and
  responsive layout.

### Stage 2 — Functional Research prototype

- implement Research Command against deterministic representative fixtures;
- add the priority briefing, opportunity queue, job activity, evidence rail,
  qualification summary, and prepared next action;
- include one meaningful instrument chart and one baseline-comparison chart;
- demonstrate loading, empty, stale, conflicting, unsupported, and failed states.

### Stage 3 — Workflow workspaces

- implement Explore, Build, Test, Evaluate, and Promote;
- implement the unified detail workspace and version history;
- add backtest, replay, stress, cohort, and shadow-prediction result views.

### Stage 4 — Real API integration

- connect frontend adapters to existing and newly governed DTOs;
- preserve fixture mode for deterministic UI tests;
- add polling or event updates only where supported by real platform state.

### Stage 5 — Governed automation and handoff

- surface real automated run records and trace links;
- bind qualification presentation to owning policies and results;
- enable immutable Demo-package creation and automatic Research-to-Demo handoff
  only after the backend capability is separately implemented and accepted;
- surface Demo-to-Research feedback when available.

### Stage 6 — Production polish

- refine density, spacing, motion, chart interaction, responsive behavior, and
  multi-monitor ergonomics;
- complete accessibility and performance audits;
- validate long-running sessions and large result sets.

## 18. First implementation milestone

The first milestone is a functional **Research-mode frontend prototype**, not the
platform's Demo mode. It includes:

- the revised three-mode launcher;
- Research shell and persistent sidebar;
- Research Command home;
- opportunity selection and detail workspace;
- instrument, evidence, explanation, jobs, and qualification panels;
- one instrument chart and one baseline-comparison chart;
- realistic deterministic fixture data;
- visible Research-only authority boundaries.

It excludes paper orders, broker integration, live execution, backend promotion
mutation, autonomous production strategy mutation, and ungoverned model training.

## 19. Accessibility and responsive requirements

- All navigation and actions are keyboard operable with visible focus.
- The sidebar preserves order and functionality when converted to a drawer.
- Drawers and dialogs manage and restore focus correctly.
- Dynamic status uses appropriately polite live regions.
- Tables expose headers and meaningful accessible names.
- Charts provide text summaries and accessible descriptions of the question,
  period, key result, and risk.
- Color is never the only status indicator.
- Reduced-motion mode removes nonessential transforms and ambient effects.
- Narrow layouts avoid horizontal page scrolling; dense tables may use contained
  horizontal scrolling with labeled context.

## 20. Testing and validation

Frontend tests cover:

- Research / Demo / Live launcher behavior and authority copy;
- first-viewport information priority;
- opportunity ranking and selection from controlled fixtures;
- command parsing preview and safe launch flow;
- point-in-time, fixture, freshness, and capability labels;
- observed-fact, reported-claim, and model-output rendering;
- meaningful-chart titles and accessible summaries;
- active, completed, failed, stale, missing, conflicting, and unsupported states;
- qualification gate pass, block, and weakest-gate explanation;
- absence of paper, broker, and live-order actions in Research;
- keyboard navigation, focus behavior, responsive sidebar, and reduced motion.

Implementation follows test-driven development. Repository validation follows
`AGENTS.md`: focused UI tests during red-green cycles, manifest-driven changed
validation after edits, relevant milestone validation, and full offline validation
at the final major checkpoint when required.

## 21. Acceptance criteria

The Research prototype is acceptable when:

1. A new operator can identify the highest-priority investigation and its main
   risk within the first viewport.
2. The interface matches the approved graphite, matte-frost, cyan-to-purple
   professional terminal direction.
3. The persistent Research sidebar and recent inquiries remain available on
   desktop.
4. Every graph answers a named decision question and has an accessible summary.
5. Every important conclusion resolves to evidence, epistemic category, cutoff,
   and reproducible research context.
6. The common paths to search, compare, explain, and run a reviewed test are
   short and keyboard accessible.
7. Missing, conflicting, stale, failed, and unsupported states are honest and
   understandable.
8. Research exposes no paper, broker, or live-order authority.
9. Research-to-Demo qualification is understandable without inventing a runtime
   handoff that does not yet exist.
10. Existing XA-01 through XA-05 semantics, OF/RT authority boundaries,
    EVIDENCE isolation, prediction authority, settlement, risk, execution, and
    broker transport remain unchanged.
