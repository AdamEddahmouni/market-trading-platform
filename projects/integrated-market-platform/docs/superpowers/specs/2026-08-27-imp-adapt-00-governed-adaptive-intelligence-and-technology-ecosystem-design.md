# IMP-ADAPT-00 Governed Adaptive Intelligence & Technology Ecosystem — Design

| Field | Value |
|---|---|
| Document ID | `IMP-ADAPT-00-DESIGN` |
| Classification | `ACTIVE_SUPPORTING` |
| Truth class | `APPROVED_FUTURE_DESIGN` (pending principal acceptance) |
| Status | `DESIGN_COMPLETE_NOT_IMPLEMENTED` |
| Version | `1.1` |
| Last verified | `2026-08-27` |
| Establishing milestone | `IMP-ADAPT-00` |
| Supersedes | None |
| Superseded by | None |

This document is planning only. It does not install packages, copy external
source, implement runtimes, modify canonical `docs/platform/` files, amend
approved REBASE-02, or change execution authority.

## Disposition

```text
NO REBASE-02 AMENDMENT REQUIRED
REBASE-02 REMAINS APPROVED FOR IMPLEMENTATION
EVIDENCE-01C REMAINS INDEPENDENT
```

## Purpose

Determine what IMP must own as domain authority, which mature libraries to
leverage behind adapters, which current systems already solve adaptive-loop
pieces, and how IMP can learn from settled outcomes without becoming an
uncontrolled self-modifying trading system.

This is not a library-shopping list. The governing constraint recovered from
repository truth is the **foundation dependency lock**: CPython 3.11.15 with
only `numpy`, `pymongo`, and `scikit-learn` as authorized third-party runtime
packages, plus Windows `tzdata`. `pandas`, `requests`, `aiohttp`, `websocket`,
`pickle`, `ib_insync`, and several broker SDKs are **prohibited patterns** in
`phase0-dependency-lock.json`. A nested collector (`pipelines/stock_data`) has
a separate, heavier stack. Adaptive architecture must respect that split.

---

# 1. Verified starting state

Examined date: `2026-08-27`.

| Item | Verified value |
|---|---|
| Primary repository | `C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform` |
| Original workspace branch / HEAD | `cloud/build-35-release-governance-operational-acceptance` / `44800d2e210e58ff5759c44cc343dd4578c0b821` |
| Original dirty state | preserved; not mutated |
| ADAPT-00 branch | `docs/imp-adapt-00-learning-ecosystem` |
| ADAPT-00 worktree | `.worktrees/imp-adapt-00-learning-ecosystem` |
| Starting HEAD (this worktree) | `d899e211475f4b9372539944f997e13acbe3b73a` |
| REBASE-02 review branch | `docs/imp-rebase-02-spec-review` |
| Approved REBASE-02 spec | `docs/superpowers/specs/2026-08-27-imp-rebase-02-reproducibility-observability-evaluation-operational-standards-implementation-spec.md` |
| Spec SHA-256 | `1BE15D0BE64A1C14446BCC80FBEEEA609BBD15316DC668B0C660FB36483148E0` |
| Spec disposition | `IMP_REBASE_02_SPEC_APPROVED_FOR_IMPLEMENTATION` |
| Later legitimate planning commit after `d899e21` | none used; ADAPT-00 branched from that commit |
| Packages installed during ADAPT-00 | none |
| External source copied | none |

Unrelated worktrees (`imp-rebase-02-design`, `imp-rebase-01-canonical`,
`mode-launcher`, `mixed-live-screener`, and sibling-repo worktrees) were left
untouched.

---

# 2. Sequencing invariant

REBASE-02 already completed DESIGN → WRITTEN-SPEC REVIEW → SEMANTIC HARDENING
→ IMPLEMENTATION APPROVAL.

Useful libraries, desirable adaptive features, and implementation convenience
are **not** standards-level semantic conflicts. ADAPT-00 found **no**
incompatibility that would make a future adaptive architecture impossible or
internally contradictory with the approved run/attempt/outcome/disposition/
artifact/checkpoint/AI-attribution model.

Canonical platform docs remain frozen until a later integration milestone after
REBASE-02 implementation.

---

# 3. Mission and safety

Target loop (future, not now):

```text
SENSE → UNDERSTAND → HYPOTHESIZE → PREDICT → RECOMMEND/ACT WITHIN AUTHORITY
→ OBSERVE → SETTLE → EVALUATE → ATTRIBUTE ERROR → REFLECT → LEARN
→ DISCOVER PATTERNS → GENERATE HYPOTHESES/EXPERIMENTS/CHALLENGERS
→ TEST → BACKTEST/REPLAY → SHADOW → FORWARD EVALUATE → PROMOTE → REPEAT
```

Permanent separations:

```text
LEARNING ≠ PROMOTION ≠ AUTHORITY ≠ EXECUTION
EXECUTION REQUEST ≠ BROKER FILL
AI ≠ authority    Agent ≠ authority    Reflection ≠ truth
Lesson ≠ truth    Hypothesis ≠ truth   Narrative ≠ truth
Model output ≠ observed fact           Prediction ≠ permission
Qualification ≠ permission             Promotion ≠ trading authorization
```

No adaptive path may bypass:

```text
INTELLIGENCE → RISK AUTHORITY → HUMAN LIVE-SESSION AUTHORIZATION
→ PER-ORDER CONFIRMATION → EXECUTION GATEWAY → BROKER → RECONCILIATION
```

Hot-path prohibition: no synchronous LLM reflection, vector reindex,
hyperparameter search, training, graph search, or experiment generation inside
latency-critical opportunity/execution.

---

# 4. Current Python / technology inventory

## 4.1 Runtime

| Source | Fact |
|---|---|
| `phase0-dependency-lock.json` | CPython 3.11, `tested_patch` 3.11.15 |
| CI | `.github/workflows/imp-validate.yml` uses `python-version: "3.11"` |
| Cloud | `.cursor/install-cloud-deps.sh` installs `tzdata numpy pymongo scikit-learn` |
| Foundation third-party | **unpinned names only**: `numpy`, `pymongo`, `scikit-learn` |
| Foundation tests | stdlib `unittest` (primary) |
| Rust | no `Cargo.toml` |
| UI | Node/Vite React app (`ui/package.json`) |

## 4.2 Two Python regimes

**A. Governed foundation (`src/market_platform_foundation`)**

Lock-authorized: numpy, pymongo, scikit-learn. HTTP via stdlib `urllib`. Local
state via stdlib `sqlite3`. Intelligence persistence: in-memory repository or
optional Mongo.

**B. Nested collector (`pipelines/stock_data`)**

Own `pyproject.toml`: `yfinance`, `pandas>=2`, `numpy>=1.24`, `requests>=2.28`,
`sqlalchemy`, `beautifulsoup4`, `lxml`, `pyarrow>=12` (used via
`DataFrame.to_parquet`, no direct `import pyarrow`), `rich`; optional
`curl_cffi`, unused extra `matplotlib`/`jupyter`; pytest for that subtree.

These regimes must not be collapsed. Expanding pandas/requests into the
foundation lock would be a governed dependency-policy change, not a silent
import.

## 4.3 Import-verified library facts (foundation vs pipeline)

| Library | Already in IMP | Import evidence |
|---|---|---|
| NumPy | Yes | intelligence trainers, baselines, fusion calibrators; pipeline scrapers |
| scikit-learn | Yes | LogisticRegression, GradientBoosting, IsotonicRegression, Pipeline, StandardScaler |
| pymongo | Yes (lazy) | `intelligence/persistence/mongo/repository.py` |
| pandas | Pipeline only | `pipelines/stock_data/**`; **prohibited** in foundation lock |
| requests | Pipeline only | pipeline scrapers; **prohibited** in foundation lock |
| pyarrow | Pipeline declared | parquet export engine; no `import pyarrow` |
| matplotlib | Declared extra only | **zero Python imports** |
| seaborn, openpyxl | No | zero imports |
| scipy, polars, duckdb, numba, statsmodels, arch | No | zero imports |
| xgboost, lightgbm, catboost, torch | No | zero imports |
| river, optuna, cvxpy, pydantic, pandera | No | zero imports |
| httpx, aiohttp, websockets | No | zero imports; aiohttp/websocket prohibited in lock |
| orjson, msgspec | No | stdlib `json` used |
| hypothesis (PyPI) | No | name collision with domain `HypothesisV1` only |
| pytest | Pipeline tests | foundation uses unittest |

## 4.4 HTTP / provider truth

| Boundary | Transport |
|---|---|
| FRED, EIA, CFTC, weather, CBOE, FINRA, RegSHO, SEC EDGAR | stdlib `urllib` transports |
| Finviz governed client | stdlib urllib |
| Finviz login tool | optional `curl_cffi` |
| Anthropic assistant | stdlib urlopen |
| IBKR | stdlib HTTPS to **local Client Portal Gateway** (not `ib_insync`) |
| Moomoo | `moomoo-api==10.10.7008` **outside** the foundation lock; foundation consumes JSONL |
| UI API | stdlib `http.server` |

Synchronous `requests` is **not** the live-streaming architecture and is not
used on the foundation path. Do not default future streaming to `requests`.

## 4.5 UI stack (not Python research)

React 18, react-router, TanStack Query, lightweight-charts, recharts, zod.
Product charting already exists; Plotly/Matplotlib must not duplicate operator
UI on the hot path.

---

# 5. Existing IMP adaptive foundation audit

Classification: `EXISTING_STRONG` | `EXISTING_PARTIAL` | `EXPERIMENTAL` |
`HISTORICAL` | `ABSENT`.

**Material correction (v1.1):** IMP already implements a **governed offline
research re-entry loop**, not a missing learning scaffold. Slogan from
`docs/engineering/CONTROLLED_ADAPTATION_V1.md`: *Live learns evidence, not
weights.* Encoded forbidden shortcuts include
`FORBIDDEN_AUTHORITY_PATHS` in
`intelligence/system_acceptance/inventory.py`
(`outcome→model_update`, `drift→model_fit`, `research_trigger→training`,
`llm→order`, and related edges).

Canonical existing loop:

```text
observe → predict → record → settle → measure → monitor → detect
  → qualify (BUILD 24) → trigger research → finding (BUILD 17)
  → experiment → train (BUILD 18) → validate (BUILD 19)
  → promote (BUILD 20) → activate (BUILD 23) → monitor
```

BUILD 24 emits `ResearchTriggerV1` only. It does **not** train, calibrate,
promote, activate, auto-generate hypotheses/experiments, or mutate
`ExperimentManifestV1`.

| Capability | Class | Evidence | Gap vs governed learning loop |
|---|---|---|---|
| Prediction identity | EXISTING_STRONG | `PredictionLedgerEntryV1` | Experience record not first-class; ledger does not retrain |
| Outcome settlement | EXISTING_STRONG | `outcomes/` including `COUNTERFACTUAL` + `scenario_id` | Needs forward data volume; keep modes disjoint |
| Temporal eligibility | EXISTING_STRONG | `available_time_ns <= decision_time_ns` | Keep as law |
| Evaluation / calibration diagnostics | EXISTING_STRONG | `intelligence/evaluation/` | Regime slice unsupported; true-prediction coverage unavailable |
| Research experiments (BUILD 17) | EXISTING_STRONG | `research_experiments/`; finding → frozen `ExperimentManifestV1` | Trigger ≠ auto-hypothesis; humans/policy climb the ladder |
| Training / distillation (BUILD 18) | EXISTING_STRONG | `training/` sklearn JSON artifacts | No `partial_fit`; not auto-invoked from adaptation |
| Independent validation (BUILD 19) | EXISTING_STRONG | `validation/` firewall, embargo, walk-forward | Separate from live runtime |
| Champion–challenger promotion (BUILD 20) | EXISTING_STRONG | `promotion/` | Needs sufficient forward shadow evidence; ≠ deploy |
| Runtime governance / drift / rollback (BUILD 23) | EXISTING_STRONG | `governance/` | Monitoring ≠ weight change |
| Controlled adaptation (BUILD 24) | EXISTING_STRONG | `adaptation/`; `ResearchTriggerV1`; cooldown/dedup | Explicitly does not mutate runtime |
| Baselines / control forecasts | EXISTING_STRONG | `baselines/` logistic/GBM/naive | Tagged `CONTROL`; excluded from production fusion by default |
| Event detector + router | EXISTING_STRONG | `routing/` | `REGIME_SHIFT` consumes **external** keys only |
| Replay runtime | EXISTING_STRONG | `replay/` | Science/proof, not self-learning |
| Release / canary / pilot | EXISTING_STRONG | `live_canary/` + BUILD 35 | Human-gated; not autonomous trading |
| Specialists | EXISTING_PARTIAL | production `MicrostructureSpecialist`; council registry | Only one production domain specialist; no production **probabilistic** forecast specialist |
| Expert blackboard / Blind Council | EXISTING_PARTIAL | infrastructure strong; multi-expert often synthetic in tests | Blackboard ≠ agent memory |
| Fusion / calibration | EXISTING_PARTIAL | machinery + sklearn calibrators; **static** weights | Production fusion **abstains** without eligible PRODUCTION probabilistic contributors |
| Hypotheses | EXISTING_PARTIAL | `HypothesisV1` + BUILD 17 hypotheses | Not validated lessons; not auto-generated from BUILD 24 |
| Forward qualification / EVIDENCE | EXISTING_PARTIAL | campaigns exist; historical insufficiency | Operational bottleneck; independent of ADAPT |
| Assistant / AI | EXISTING_PARTIAL | read-only assistant; `llm→order` forbidden | Not a trading/learning agent; AI-01 still required |
| Checkpoint / resume | EXISTING_PARTIAL | ops/pilot/EVIDENCE resume | Not ML/experience-buffer resume; graph identity absent |
| Regime generator | ABSENT | router/priors consume keys | Evaluation regime dimension unsupported |
| Online `partial_fit` / live weight learning | ABSENT (correct) | deferred in adaptation + baseline docs | Continual adaptation ≠ continual gradients |
| Reflection / episodic memory / vector retrieval | ABSENT | `persistence/memory.py` is in-memory **repository** | ADAPT-02; do not confuse with Mongo/in-memory store |
| Agent graph orchestration library | ABSENT | no LangGraph/MAF | Optional adapter later |
| Self-promotion / autonomous agent | ABSENT (correct) | forbidden authority paths | Keep absent |
| Decision-research / squeeze / distribution | EXPERIMENTAL | `research/decision_research/` etc. | Parallel harness, not BUILD 24 control plane |
| P6 shadow labeling | HISTORICAL | `shadow/` + `outcomes/p6_compat.py` | Promoted into BUILD 15; not current control plane |

**Reuse before inventing:** do **not** rebuild BUILD 15–24, specialists, council,
blackboard, fusion, EVIDENCE, or risk/execution gates as generic agent-framework
features. ADAPT-* extends this loop (experience records, validated lessons,
optional River **research**, graph identity). External libraries must not
become a second promotion or training authority.

Largest practical gaps to **closing the intended loop** are production
probabilistic forecast contributors and forward-evidence sufficiency — **not**
missing online gradient machinery.

---

# 6. Build vs buy (commodity vs domain)

IMP **should use mature libraries** for commodity algorithms: linear algebra,
optimization, statistics, HTTP clients, serialization, plotting, standard ML.

IMP **must own** domain authority: canonical market state, temporal eligibility,
prediction identity, settlement, quality admission, risk authority, execution
authority, qualification, learning/promotion governance, and canonical IDs
(`run_id`, `attempt_id`, `correlation_id`, `event_id`, forecast/ledger IDs).

External IDs (MLflow run, LangGraph thread, Qdrant point, Dagster asset,
Temporal workflow, RLlib worker) may exist only behind adapter maps.

---

# 7. Three-fabric architecture

Canonical REBASE-01 already defines Real-Time Opportunity Fabric and Operating
Fabric. ADAPT-00 proposes a **third** fabric as future canonical language
(integration into `MASTER_ARCHITECTURE.md` is **not** this milestone).

## Real-Time Opportunity Fabric

Fast events, state, features, signals, opportunities, action preparation.
Workload: HOT / WARM. No learning side-effects on this path unless a
pre-approved bounded online policy is proven safe (ADAPT-08).

## Operating Fabric

Runs, artifacts, workflow, registries, SOPs, audit, reproducibility.
Owners: REBASE-02 standards → OF-01 ledger → OF-02 adapters → OF-03 registry.

## Adaptive Intelligence Fabric

Indexes and extends BUILDs 15–24 rather than replacing them: experience records,
LLM reflection (labeled `MODEL_OUTPUT`), validated lessons, retrieval, optional
River **research**, graph-challenger identity, and promotion **evidence
packaging**. Never a broker path. BUILD 24 remains the only path from
monitoring/drift to research re-entry.

```text
OUTCOME → ADAPTIVE FABRIC → LESSONS / EXPERIMENTS / CHALLENGERS
        → EVALUATION → PROMOTION → ELIGIBLE INTELLIGENCE
ELIGIBLE INTELLIGENCE → RISK → HUMAN AUTHORITY → EXECUTION
```

Forbidden: `ADAPTIVE FABRIC → BROKER`.

---

# 8. Adaptive learning taxonomy

## MEMORY LEARNING

Changes future retrieved context (experiences, validated lessons, retrieval
index). Does not change model code.

## STRUCTURAL / MODEL LEARNING

Creates **candidates** for models, features, strategies, prompts, weights,
routing, retrieval policy.

## META / GRAPH LEARNING

Creates **candidates** for agent-graph topology, specialists, ordering, tools,
debate depth, routing.

## BOUNDED ONLINE ADAPTATION

Updates values explicitly permitted by a pre-approved adaptive policy
(e.g. rolling volatility, bounded expert weights). State update ≠ model
redefinition.

```text
STATE UPDATE ≠ MODEL REDEFINITION
volatility estimate updates     → may be state (if policy-bounded)
volatility-model architecture   → structural challenger
```

---

# 9. Outcome-grounded experience (ADAPT-01 kernel)

Conceptual (schema not frozen):

```text
PREDICTION / HYPOTHESIS + CONTEXT + CONTRIBUTORS + EVIDENCE + CUT-OFF
        ↓
   SETTLEMENT (existing OutcomeSettlementService)
        ↓
   OUTCOME
        ↓
   EXPERIENCE RECORD
```

Experience fields (illustrative): prediction refs, future run refs, contributors
(specialists/fusion), regime, confidence, outcome, performance,
counterfactual refs, quality, error attribution.

Epistemics:

```text
SETTLED OUTCOME        = EVIDENCE
DETERMINISTIC METRIC   = DERIVED EVIDENCE
AI REFLECTION          = MODEL_OUTPUT
LESSON                 = HYPOTHESIS / KNOWLEDGE CANDIDATE
```

Memory layers (never collapsed):

```text
HISTORICAL EVIDENCE ≠ EXPERIENCE ≠ REFLECTION ≠ LESSON
≠ RETRIEVAL INDEX ≠ WORKING CONTEXT
```

Vector DB belongs only at RETRIEVAL INDEX. `VECTOR INDEX ≠ CANONICAL EVIDENCE`.

Retrieval should return supporting **and** contradicting cases where feasible.
Consequential AI runs should later cite retrieval policy/version/cutoff, lesson
IDs, experience IDs, and index snapshot.

Self-reinforcing loop mitigation: independent outcomes, holdout, counterexamples,
fresh evidence, regime bounds, decay, revalidation.

Lesson object (future): claim, regime, instrument applicability, support,
contradictions, sample size, effect, confidence, falsifier, source, last
validation. One losing trade cannot become global truth.

---

# 10. Agent graph identity and checkpoints

Graph candidate identity must include topology, nodes/versions, edges, routing,
models, tools, prompts, budgets, debate limits, configuration. Material change
⇒ new graph identity.

Hard rule: a checkpoint MUST NOT silently resume under an incompatible graph
identity. This is compatible with REBASE-02 retry/resume/checkpoint tables
(`resumed_from_checkpoint`, material-change ⇒ new run) and with TradingAgents’
`_run_signature` practice (analysts + debate + risk + asset folded into thread
id) — IMP must own the identity contract, not LangGraph `thread_id`.

Graph challenger lifecycle:

```text
CURRENT GRAPH → OUTCOMES → ERROR ANALYSIS → GRAPH CANDIDATE
→ CONTROLLED COMPARISON → REPLAY → SHADOW → FORWARD → PROMOTION
```

---

# 11. TradingAgents source-level audit

| Field | Value |
|---|---|
| Name | TradingAgents |
| URL | https://github.com/TauricResearch/TradingAgents |
| Owner | TauricResearch |
| Examined commit | `a33fd4c0f134485a43553a2c23a63cb14adbd88f` (2026-07-18, `main`) |
| Examined date | 2026-08-27 |
| License | Apache-2.0 (`PERMISSIVE_COMPATIBLE`) |
| Reuse class | `CONCEPTUAL_REUSE` / disposition `REFERENCE_ARCHITECTURE` |
| Maintenance | Active in 2026; large community; not IMP-grade governance |

Inspected paths (not README-only): `tradingagents/graph/trading_graph.py`,
`graph/reflection.py`, `graph/checkpointer.py`, `agents/utils/memory.py`.

### Recovered loop (verified)

```text
DECISION → PENDING RECORD → REALIZED OUTCOME (yfinance, holding_days default 5)
→ RAW RETURN → BENCHMARK-RELATIVE RETURN (suffix map / explicit benchmark)
→ LLM REFLECTION (2–4 sentences) → MARKDOWN MEMORY LOG → PROMPT RETRIEVAL
```

| Concern | Verified behavior |
|---|---|
| Decision identity | ticker + trade_date tag; not a content-addressed IMP ID |
| Outcome window | `holding_days` (default 5) vs Yahoo bars; weekends buffered |
| Benchmark | `benchmark_ticker` or suffix map; default SPY / empty suffix |
| Retry | pending skipped if prices missing; resolved next same-ticker run |
| Duplicate prevention | pending tag scan for `[date \| ticker \| … \| pending]` |
| Memory rotation | optional `memory_log_max_entries` drops oldest **resolved** only |
| Retrieval | last 5 same-ticker full entries + 3 cross-ticker reflection-only |
| Reflection inputs | final decision text + raw/alpha; **no** independent feature snapshot |
| Lesson representation | unstructured LLM prose |
| Checkpoint | optional LangGraph `SqliteSaver` per ticker; thread id hashes ticker+date+graph signature |
| Cross-ticker pending | **not** resolved until that ticker is run again |

Roles/graph (from graph setup usage): market/social/news/fundamentals analysts,
tool nodes, bull/bear investment debate, risk debate
(aggressive/conservative/neutral), manager/judge, trader plan, signal processor.

### Verified weaknesses relative to IMP (present, not assumed)

| Weakness | Verification |
|---|---|
| Reflection treated as knowledge | Prompt injects reflections verbatim; no statistical validation |
| Hindsight bias | Reflection sees realized return before writing the “lesson” |
| Overgeneralization | Cross-ticker lessons are reflection-only snippets without regime/instrument guards |
| Cross-instrument contamination | Explicit `n_cross=3` injection |
| Regime blindness | No regime object in memory schema |
| Limited provenance | Markdown log, not hashed evidence |
| No qualification/promotion split | Decision text is the product |
| Outcome ≠ IMP settlement | Yahoo close-to-close vs preregistered `PredictionLedgerEntryV1` |
| yfinance as truth | Fragile vs IMP provider envelopes |

### Useful patterns mapped to IMP (reuse concepts, not code)

| Pattern | IMP mapping |
|---|---|
| Specialized agents | Existing specialists + council participants |
| Bounded debate | Existing Blind Council / deliberation rounds |
| Separate bull/bear evidence | Comparable to relation types / competing hypotheses — optional prompt pattern only |
| Risk-specific debate | Must remain **non-authoritative**; IMP risk authorities stay executable contracts |
| Manager arbitration | Council deliberation gate — already exists |
| Reflection after realized outcomes | ADAPT-02, after settlement, labeled MODEL_OUTPUT |
| Retrievable past lessons | ADAPT-02 validated memory, not markdown |
| Graph checkpointing | OF-01 + REBASE-02 checkpoint rules + IMP graph identity |
| Config-sensitive resume | `_run_signature` analogue owned by IMP |

**Do not adopt TradingAgents as a dependency.** Apache-2.0 permits study; IMP
already has stronger prediction/settlement/council primitives.

---

# 12. Curriculum repositories

## Quant-Finance-Resources

| Field | Value |
|---|---|
| URL | https://github.com/PyPatel/Quant-Finance-Resources |
| Owner | PyPatel |
| Examined commit | `a281bb7c446b51301d1566e30e50f54facc3d4af` (2021-09-13) |
| Last push | 2021-12-17 |
| License | `NO_LICENSE` on GitHub API |
| Disposition | `REFERENCE_ONLY` / `STALE_OR_SUPERSEDED` as a living catalog |
| Reuse | `CONCEPTUAL_REUSE` of topic list only; no source copy |

High-value study areas → IMP mapping (priority = research backlog rank later):

| Area | IMP subsystem | Research question | Baseline | Experiment type | Priority | Deps |
|---|---|---|---|---|---|---|
| Probability / stats | Evaluation, Risk | Are current metrics calibrated? | sklearn metrics + settlement | offline | P1 | SciPy/statsmodels later |
| Linear algebra / numerical | Features, RT | Vectorize vs Numba vs Rust | NumPy | RT-01 measure first | P2 | NumPy |
| Time series | Intelligence | Volatility/regime baselines | rolling IMP features | research | P1 | arch/statsmodels |
| Microstructure / order book | RT, whale/order-flow | Does LOB add alpha after costs? | existing order-flow BUILD | replay | P1 | none new |
| HFT | RT-03 | Event bus needed? | RT-01/02 evidence | measurement | P3 | Nautilus ref only |
| Cross-market | XA | Lead-lag vs leakage | XA-01 contracts | research | P1 | none |
| Financial ML | Training | GBDT vs sklearn GBM | sklearn GBM | challenger | P2 | LightGBM later |
| RL | Research only | Unsafe live? | FinRL/SB3 sims | research | P3 | Gymnasium |
| Deep hedging | Options | Hedge error vs rules | existing options | research | P3 | PyTorch later |
| Derivatives | Options/futures | Pricing vs IMP contracts | IMP options | research | P2 | SciPy |
| Optimization | Portfolio/risk | Constrained allocation | current risk caps | research | P2 | CVXPY later |
| Game theory | Council | Debate as cheap talk | Blind Council | research | P3 | none |

## finance-courses

| Field | Value |
|---|---|
| URL | https://github.com/z4ir3/finance-courses |
| Owner | z4ir3 |
| Examined commit | `1466799ecf3ac3d32bd7119de74eb61d5150192b` (2023-12-11) |
| License | `NO_LICENSE` |
| Disposition | `REFERENCE_ONLY` (EDHEC-style portfolio notebooks) |

| Topic | Map into |
|---|---|
| VaR, robust covariance, CVaR, drawdown | Risk |
| Mean-variance, HRP, Black-Litterman, diversification | Portfolio |
| Factor models, ALM | Cross-Asset / Portfolio |
| Regime / crash classification | Macro Regime + Adaptive Intelligence |
| Feature selection / ML AM | Evaluation + Adaptive Intelligence |

Do not copy notebooks. Re-implement experiments under IMP contracts and future
Run Ledger.

---

# 13. User-supplied seven libraries (required conclusions)

### NumPy — KEEP / EXPAND (foundation)

Already installed and imported. Foundational array layer for trainers,
baselines, calibrators. Runtime class: HOT_PATH-capable numerically, but current
use is WARM/COLD intelligence. Expand use in features/signals/statistics where
stdlib lists are the bottleneck **after** RT-01 profiling. Not a substitute for
measurement. Numba/Rust only after measured hot loops. Do not replace.

### pandas — CONSTRAIN to pipeline + offline research extras

Already used in `pipelines/stock_data` only. **Must not** enter foundation lock
without a separate governed decision. Best-fit: OFFLINE_RESEARCH / COLD_PATH
dataset manipulation, reports, collector DB. **Must not** appear in per-tick
hot loops or canonical market-state mutation. Alternatives for large scans:
Polars / Arrow / DuckDB as **pilots**, not automatic replacement. Excel/CSV
interchange may use pandas in operator tools only.

### Matplotlib — RESEARCH-ONLY if introduced

Not imported. Declared unused extra on the pipeline. Class: OFFLINE_RESEARCH.
Use for diagnostic plots, evaluation charts, acceptance evidence. Never on
execution path. Product UI already has recharts/lightweight-charts.

### Seaborn — OPTIONAL RESEARCH-ONLY

Not present. Higher-level Matplotlib wrapper. Class: OFFLINE_RESEARCH. Adopt
only if Matplotlib burden is real in research notebooks; otherwise skip to
avoid a second viz dependency. Not justified for foundation.

### openpyxl — OPTIONAL OPERATOR TOOL, never canonical store

Not present. Class: OPTIONAL_OPERATOR_TOOL / COLD_PATH. Allowed for explicit
Excel import/export/stakeholder reports. Hard rule: `EXCEL ≠ CANONICAL IMP DATA STORE`.
`.xlsx` must never be provenance or market-state authority.

### scikit-learn — KEEP / EXPAND as baseline authority

Already core intelligence. Pipelines, preprocessing, logistic, GBM, isotonic,
metrics, CV, clustering, feature selection are in-scope **as baselines**. A
sophisticated model must beat these. Expand disciplined use (calibration,
feature selection, dummy/linear baselines) inside the existing lock. Do not
replace with PyTorch by default.

### Requests — CONSTRAIN to pipeline; do not promote to foundation live path

Used in stock_data scrapers. Prohibited in foundation lock. Suitable: cold
research APIs, batch downloads, simple REST in isolated tools. Live/provider
paths should remain stdlib urllib **or** future adapter using HTTPX/async
**behind provider contracts**, not a global `requests` default. Compare
HTTPX (sync+async+HTTP/2) vs aiohttp vs `websockets` vs provider-native SDKs
(Moomoo already native). Do not add both HTTPX and aiohttp without a purpose.

---

# 14. Numerical / data stack recommendations

| Library | Runtime class | Disposition | Notes |
|---|---|---|---|
| NumPy | HOT/WARM/COLD | KEEP / EXPAND | Foundation numerical layer |
| SciPy | OFFLINE_RESEARCH → later WARM | **HIGH-PRIORITY PILOT** | Optimization, stats, signal, sparse; BSD-new; do not hand-roll |
| pandas | COLD / pipeline | CONSTRAIN | Not hot path |
| Polars | COLD analytics | **PILOT_CANDIDATE** | Lazy/parallel vs pandas on actual IMP historical scans; MIT |
| PyArrow | COLD interchange | **PILOT_CANDIDATE** (pipeline already depends) | Parquet snapshots, interchange; Apache-2.0; IDs stay IMP’s |
| DuckDB | OFFLINE_RESEARCH | **PILOT_CANDIDATE** | Embedded SQL over Parquet; MIT; do not replace Mongo/repository |
| Numba | HOT only if measured | RESEARCH_ONLY until RT-01 | vs vectorization / Polars / future Rust |
| Bottleneck / NumExpr | — | DUPLICATIVE unless profiled | Do not add now |

Arrow/Parquet may become a **representation** for large immutable research
snapshots. They do not replace canonical IMP identities or JSON evidence
contracts.

---

# 15. Statistics / econometrics

| Library | Disposition |
|---|---|
| SciPy stats | PILOT with SciPy |
| statsmodels | PILOT_CANDIDATE (research extra) for regression diagnostics, ARIMA/state-space, cointegration |
| arch | PILOT_CANDIDATE for GARCH/EGARCH/volatility, unit roots — map to volatility intelligence, risk, regime, options |
| linearmodels | RESEARCH_ONLY if panel work appears |

No production econometric engine until experiments beat current feature/risk
baselines under Run Ledger provenance (after OF-01).

---

# 16. Machine-learning stack

| Library | Disposition | Rationale |
|---|---|---|
| scikit-learn | KEEP / EXPAND | Mandatory baseline |
| LightGBM | **PILOT_CANDIDATE** (single GBDT) | Fast tabular; Windows wheels exist; pick **one** GBDT |
| XGBoost | DUPLICATIVE if LightGBM piloted | Strong but overlapping |
| CatBoost | RESEARCH_ONLY | Categorical strengths; third overlapping stack |
| PyTorch | RESEARCH_BASELINE | Sequences, representation, RL, deep hedging — not default |
| TensorFlow / JAX | REJECT for now | No repo use; overlapping DL |

Challengers must beat sklearn logistic/GBM under frozen cutoffs.

---

# 17. Online learning, drift, experts

| Library | Disposition |
|---|---|
| River | **HIGH-PRIORITY PILOT** (research extra, BSD-3) commit `64285b9dd6c606804753235fe992bcf25b9856ee` (2026-08-21) |
| sklearn incremental | USE what exists (partial_fit) before new deps |
| Vowpal Wabbit | TOO_HEAVY / RESEARCH_ONLY |
| Avalanche | RESEARCH_ONLY (continual learning) |
| Alibi Detect / Evidently / NannyML | OPTIONAL later; finance-specific regime logic stays IMP-owned |

River mapping: streaming stats, drift detectors, progressive validation,
adaptive ensembles → regime adaptation, source reliability, calibration drift,
expert weighting, signal-quality. **No online production learning in ADAPT-00.**

Expert methods: Bayesian averaging / mixture-of-experts / online experts /
contextual bandits / stacking / regime-conditioned weights.

| Method | Class |
|---|---|
| Bounded rolling / posterior / source confidence | BOUNDED_ONLINE_CANDIDATE |
| Bandits / stacking / MoE architecture | OFFLINE_CHALLENGER |
| Unrestricted live exploration | RESEARCH_ONLY (forbidden live) |

Preserve expert diversity: accuracy, calibration, alpha, abstention, cost,
latency, failure rate, correlation, false-consensus risk.

---

# 18. Optimization

| Library | Disposition |
|---|---|
| SciPy optimize | PILOT with SciPy |
| Optuna | **HIGH-PRIORITY PILOT** for HPO; studies inherit future Run Ledger; output = CHALLENGER |
| CVXPY | PILOT later for portfolio/risk research |
| Ray Tune / Nevergrad | TOO_HEAVY now |

`OPTIMIZER OUTPUT = CHALLENGER`, never production promotion.

---

# 19. Schema / validation

| Library | Disposition |
|---|---|
| dataclasses + IMP contracts | KEEP (canonical) |
| Pydantic | PILOT at **adapter boundaries** (AI structured output, external payloads), not ultra-hot loops |
| Pandera | PILOT for research DataFrames (COLD/WARM) |
| Great Expectations | TOO_HEAVY / DUPLICATIVE vs quality authorities |
| zod (UI) | KEEP on frontend |

Do not create a second canonical quality authority.

---

# 20. HTTP / serialization

| Library | Disposition |
|---|---|
| stdlib urllib | KEEP for current foundation providers |
| HTTPX | PILOT behind **new** research/provider adapters (sync+async) |
| aiohttp | DUPLICATIVE vs HTTPX unless server-side streaming needs it |
| websockets | Compare to Moomoo native push; PILOT only if IMP-owned WS needed |
| stdlib json | KEEP as semantic default |
| orjson / msgspec | PILOT after measured JSON volume; never sacrifice canonical semantics |
| MessagePack / Arrow IPC | workload-specific |

---

# 21. Storage (roles only — no redesign)

| Store | Role |
|---|---|
| IMP repositories / Mongo | Operational intelligence documents |
| sqlite3 | Local state, shadow experiments (existing) |
| Parquet/Arrow | Cold analytical snapshots |
| DuckDB | Ad-hoc research SQL |
| PostgreSQL | Not required now |
| Redis | OPTIONAL FUTURE (cache/pubsub); compare in-process/NATS/ZMQ first; **no adoption now** |

---

# 22. Quant frameworks

Examined 2026-08-27.

| Project | Commit / license | Disposition |
|---|---|---|
| Qlib | `79633dd9506ea689e5400dea0197717b5b3d74b7` MIT | REFERENCE_ARCHITECTURE — data/feature/model/experiment ideas; do not duplicate IMP ledgers |
| LEAN | `07fb0182bfe229edd9445cf675ac6509d0069539` Apache-2.0 | RESEARCH_BASELINE / EXTERNAL CROSS-CHECK ENGINE; C# core; do not replace IMP |
| NautilusTrader | `f2b2addb99527e3c9465573a596284f47b9edf10` **LGPL-3.0** | REFERENCE_ARCHITECTURE for event-driven Rust+Python, clocks, live/backtest symmetry; `WEAK_COPYLEFT_REVIEW_REQUIRED`; **not** a dependency |
| vectorbt | Apache-2.0 **+ Commons Clause** | `LICENSE_REVIEW_REQUIRED` / `SOURCE_AVAILABLE_RESTRICTED`; research sweeps only, not productized service wrapping |
| Backtrader | — | STALE_OR_SUPERSEDED relative to Nautilus/LEAN |
| Zipline-reloaded | — | RESEARCH_ONLY |
| FinRL | — | RESEARCH_BASELINE for RL; not live |

Nautilus maps to future RT event-bus **study**, measured Rust boundary, and
simulation fidelity — after RT-01. LGPL linking requires legal review before
any binary distribution.

---

# 23. Portfolio / risk / time series / causal

| Library | Disposition |
|---|---|
| PyPortfolioOpt | RESEARCH_BASELINE |
| Riskfolio-Lib | RESEARCH_BASELINE (check copyleft/deps before any install) |
| CVXPY | PILOT later |
| sktime / Darts / PyTorch Forecasting | RESEARCH_ONLY; do not stack |
| tsfresh | RESEARCH_ONLY; `AUTO FEATURES ≠ AUTO PROMOTION`; leakage/explosion guards |
| DoWhy / EconML / CausalML | RESEARCH_ONLY; never auto-truth |

---

# 24. Agent ecosystem (pick at most one orchestrator later)

Score emphasis: IMP already has specialists, council, tools-as-Python, and
read-only assistant. Need: durable graph, HITL, typed outputs, checkpoints
**mapped to IMP IDs**.

| Framework | Examined | License | Disposition |
|---|---|---|---|
| LangGraph | `bdb8a9c7a4aa1390af225f6a5d292e5088659bd5` MIT | PILOT adapter candidate **or** reference; TradingAgents uses it; lock-in + LangSmith gravity |
| Microsoft Agent Framework | `947d933f2385b3f38ff40bef5b0c0245acdf3798` MIT; 1.0 GA 2026 | PILOT adapter candidate; graphs, checkpointing, HITL, A2A/MCP, Python/.NET |
| PydanticAI | — MIT | Attractive for typed structured outputs; consider with Pydantic boundary |
| DSPy | — | RESEARCH; **PROMPT CHALLENGER FACTORY** only; never silent prompt mutation |
| CrewAI / LlamaIndex | — | DUPLICATIVE if stacking |
| AutoGen | historically relevant | SUPERSEDED by MAF for Microsoft lineage |

**Reject** `IMP → LangGraph → CrewAI → LlamaIndex → AutoGen`.

Prefer:

```text
IMP-owned workflow + graph identity
        optional single adapter (LangGraph XOR MAF)
```

Decision deferred to IMP-AI-01/AI-02 after OF-01 attribution. ADAPT-06 is the
graph-challenger system, not “install LangGraph now.”

---

# 25. Workflow / MLOps / vectors / observability / testing

| System | Disposition |
|---|---|
| Temporal | OPTIONAL FUTURE COLD/WARM fabric; not hot path |
| Dagster | OPTIONAL for research asset lineage; not IMP runtime |
| Prefect | DUPLICATIVE vs Dagster/Temporal choice later |
| MLflow | INTEGRATION_CANDIDATE **backend** after OF-01; IMP run_id canonical |
| DVC / W&B / Aim | OPTIONAL; never duplicate truth |
| FAISS | PILOT for local lesson retrieval |
| Qdrant | OPTIONAL FUTURE service; not now |
| Chroma / pgvector | DUPLICATIVE now |
| OpenTelemetry | HIGH-PRIORITY **export** reference for RT-01; OTEL must not redefine domain IDs |
| Phoenix / Langfuse / Ragas / DeepEval / TruLens | OPTIONAL AI eval adapters; avoid overlap with Run Ledger |
| unittest | KEEP |
| Hypothesis | **HIGH-PRIORITY PILOT** for contracts, temporal edges, serialization |
| pytest-asyncio/xdist/timeout | OPTIONAL for adapter tests; do not replace validate.py |
| tools/benchmark.py | KEEP; pyperf/pytest-benchmark may **strengthen measurement** under RT-01 without replacing IMP benchmark identity |
| cProfile / py-spy | DEV_TOOLING; Scalene/Memray optional |
| Plotly / Jinja2 | OPTIONAL research/report; not execution |

No duplicate truth stores:

```text
IMP RUN ID → ADAPTER MAPPING → external tool ID
```

---

# 26. RL risk (mandatory)

Gymnasium / PettingZoo / Stable-Baselines3 / CleanRL / RLlib / FinRL:
RESEARCH_BASELINE only.

Risks: reward hacking, nonstationarity, sim-to-real, tail risk, costs,
liquidity, unsafe exploration, distribution shift, policy instability.

No uncontrolled live exploration. Simulated outcome ≠ observed outcome.

Counterfactual categories remain:

```text
ACTUAL OBSERVED OUTCOME | COUNTERFACTUAL ESTIMATE | SIMULATED OUTCOME
```

Never merge.

---

# 27. Required library inventory table

Runtime classes: HOT_PATH, WARM_PATH, COLD_PATH, OFFLINE_RESEARCH,
DEV_TOOLING, OPTIONAL_OPERATOR_TOOL.

| Library | Already in IMP | Current use | Candidate use | Runtime class | Disposition |
|---|---|---|---|---|---|
| pandas | pipeline | collector DataFrames | research/export only | COLD / OFFLINE_RESEARCH | CONSTRAIN |
| NumPy | foundation+pipeline | ML arrays, scrapers | features/stats | HOT/WARM/COLD | KEEP/EXPAND |
| Matplotlib | extra unused | none | research plots | OFFLINE_RESEARCH | RESEARCH_ONLY |
| Seaborn | no | none | optional plots | OFFLINE_RESEARCH | RESEARCH_ONLY |
| openpyxl | no | none | Excel I/O | OPTIONAL_OPERATOR_TOOL | PILOT if needed |
| scikit-learn | foundation | baselines, calibration | expand baselines | WARM/COLD | KEEP/EXPAND |
| requests | pipeline | scrapers | isolated REST | COLD | CONSTRAIN |
| SciPy | no | none | stats/optimize | OFFLINE_RESEARCH→WARM | PILOT_CANDIDATE |
| Polars | no | none | large scans | COLD | PILOT_CANDIDATE |
| PyArrow | pipeline declared | parquet export | snapshots | COLD | PILOT_CANDIDATE |
| DuckDB | no | none | analytical SQL | OFFLINE_RESEARCH | PILOT_CANDIDATE |
| Numba | no | none | measured loops | HOT if proven | RESEARCH_ONLY |
| statsmodels | no | none | econometrics | OFFLINE_RESEARCH | PILOT_CANDIDATE |
| arch | no | none | volatility | OFFLINE_RESEARCH | PILOT_CANDIDATE |
| XGBoost | no | none | tabular | COLD train | DUPLICATIVE vs LightGBM |
| LightGBM | no | none | GBDT challenger | COLD train | PILOT_CANDIDATE |
| CatBoost | no | none | tabular | COLD train | RESEARCH_ONLY |
| PyTorch | no | none | deep/RL | OFFLINE_RESEARCH | RESEARCH_BASELINE |
| River | no | none | drift/online research | WARM research | PILOT_CANDIDATE |
| Optuna | no | none | HPO challengers | OFFLINE_RESEARCH | PILOT_CANDIDATE |
| CVXPY | no | none | portfolio/risk | OFFLINE_RESEARCH | PILOT later |
| Pydantic | no | none | adapter IO | WARM boundary | PILOT_CANDIDATE |
| Pandera | no | none | frame schemas | COLD | PILOT_CANDIDATE |
| HTTPX | no | none | adapter HTTP | WARM | PILOT_CANDIDATE |
| aiohttp | no | none | — | — | DUPLICATIVE |
| websockets | no | none | IMP WS if needed | WARM | RESEARCH/PILOT |
| orjson | no | none | fast JSON | WARM | PILOT if measured |
| msgspec | no | none | typed serdes | WARM | PILOT if measured |
| LangGraph | no | none | optional graph adapter | COLD/WARM AI | REFERENCE / later XOR |
| Microsoft Agent Framework | no | none | optional graph adapter | COLD/WARM AI | REFERENCE / later XOR |
| PydanticAI | no | none | typed agents | COLD/WARM | RESEARCH/PILOT |
| DSPy | no | none | prompt challengers | OFFLINE_RESEARCH | RESEARCH_BASELINE |
| MLflow | no | none | experiment backend | COLD | INTEGRATION later |
| Dagster | no | none | research pipelines | COLD | OPTIONAL FUTURE |
| Temporal | no | none | durable OF workflows | COLD/WARM | OPTIONAL FUTURE |
| OpenTelemetry | no | none | export traces | WARM | REFERENCE / RT-01 |
| FAISS | no | none | local retrieval | COLD | PILOT later |
| Qdrant | no | none | filtered retrieval | COLD | OPTIONAL FUTURE |
| Qlib | no | none | research ideas | — | REFERENCE_ARCHITECTURE |
| LEAN | no | none | cross-check engine | — | RESEARCH_BASELINE |
| NautilusTrader | no | none | event-core study | — | REFERENCE_ARCHITECTURE + LICENSE_REVIEW |
| vectorbt | no | none | vectorized sweeps | OFFLINE_RESEARCH | LICENSE_REVIEW_REQUIRED |
| FinRL | no | none | RL research | OFFLINE_RESEARCH | RESEARCH_BASELINE |
| Stable-Baselines3 | no | none | RL algos | OFFLINE_RESEARCH | RESEARCH_BASELINE |
| Gymnasium | no | none | RL env API | OFFLINE_RESEARCH | RESEARCH_BASELINE |
| PettingZoo | no | none | multi-agent RL | OFFLINE_RESEARCH | RESEARCH_ONLY |
| PyPortfolioOpt | no | none | portfolio research | OFFLINE_RESEARCH | RESEARCH_BASELINE |
| Riskfolio-Lib | no | none | risk research | OFFLINE_RESEARCH | RESEARCH_BASELINE |
| Hypothesis | no | none | property tests | DEV_TOOLING | PILOT_CANDIDATE |
| pyperf / pytest-benchmark | no | none | microbench | DEV_TOOLING | OPTIONAL under RT-01 |

---

# 28. Shortlist

## KEEP / EXPAND CURRENT USE

NumPy, scikit-learn, pymongo (optional), stdlib urllib/json/unittest/sqlite3,
`tools/benchmark.py`, UI React/zod/charts, pipeline pandas/requests/pyarrow
**inside the collector only**, Moomoo/IBKR existing transports.

## HIGH-PRIORITY PILOT CANDIDATES

SciPy; River; Optuna; PyArrow/DuckDB/Polars (analytical extras, not lock
expansion without governance); HTTPX (adapters); Hypothesis; LightGBM (one
GBDT); Pydantic/Pandera at boundaries.

## HIGH-PRIORITY REFERENCE ARCHITECTURES

TradingAgents (loop/debate/checkpoint patterns); LangGraph; Microsoft Agent
Framework; Qlib; NautilusTrader; LEAN (cross-check).

## RESEARCH BASELINES

FinRL, SB3, Gymnasium, vectorbt (license-constrained), PyPortfolioOpt,
Riskfolio-Lib, PyTorch, statsmodels/arch, DSPy, tsfresh.

## OPTIONAL FUTURE INFRASTRUCTURE

Temporal, Dagster, MLflow adapter, FAISS then Qdrant, OTEL exporter, Redis,
orjson/msgspec.

## DUPLICATIVE / UNNECESSARY

aiohttp+HTTPX together; XGBoost+LightGBM+CatBoost together; CrewAI+LlamaIndex
stacking; W&B+MLflow+DVC all canonical; Seaborn if Matplotlib unused;
TensorFlow+JAX+PyTorch.

## LICENSE-CONSTRAINED

NautilusTrader LGPL-3.0 (`WEAK_COPYLEFT_REVIEW_REQUIRED`); vectorbt Commons
Clause (`SOURCE_AVAILABLE_RESTRICTED`); curriculum repos `NO_LICENSE`.

## REJECTED (for adoption now)

Installing the entire list; AutoGen as primary; Redis/Qdrant/Temporal in
ADAPT-00; live RL; pandas/requests in foundation lock; Excel as evidence
store; LangGraph as canonical authority; MLflow IDs as IMP run IDs.

---

# 29. Adaptive primitive reuse matrix

| Primitive | Existing IMP foundation | Missing gap | External help | Owner |
|---|---|---|---|---|
| experience | ledger + settlement + evaluation reports | first-class experience object citing those IDs | — | IMP ADAPT-01 |
| error attribution | evaluation diagnostics | taxonomy expansion | — | IMP |
| reflection | absent as LLM post-outcome memory | post-settlement MODEL_OUTPUT | LLM via AI-01 | IMP ADAPT-02 |
| lesson | HypothesisV1 / research findings | validation, decay, contradiction retrieval | — | IMP ADAPT-02 |
| memory | evidence stores, adaptation events, in-memory **repo** | layered lesson/experience memory | FAISS later | IMP |
| retrieval | none for lessons | policy + contradictions | FAISS/Qdrant | IMP + adapter |
| drift | BUILD 23 assessments + BUILD 24 qualification | finance-specific vs generic detectors | River research only | IMP + optional River |
| pattern detection | evaluation cohorts / slices | grouping + stats | SciPy | IMP |
| hypothesis | BUILD 17 hypotheses (not auto from trigger) | optional competing-candidate drafts | DSPy optional | IMP; must enter BUILD 17 |
| experiment | frozen `ExperimentManifestV1` | auto-draft **candidates** only | Optuna | IMP BUILD 17; ADAPT-04 must not skip ladder |
| model challenger | BUILD 18 sklearn factory + BUILD 20 | additional GBDT behind same gates | LightGBM later | IMP |
| prompt challenger | assistant templates | candidate-only | DSPy | IMP-AI |
| graph challenger | council topology implicit | identity + lifecycle | LangGraph/MAF adapter | IMP ADAPT-06 |
| promotion | BUILD 20 + live release governance | graph/prompt consequence classes; Run Ledger cites | — | IMP ADAPT-07 wraps BUILD 20 |
| bounded online | static fusion weights; BUILD 24 forbids live fit | approved **state** envelope only | River | IMP ADAPT-08; still not `partial_fit` by default |

---

# 30. Learning-authority matrix

| Output | Auto-create | Auto-test | Auto-promote | Trading authority |
|---|---|---|---|---|
| reflection | YES (after settlement) | YES (schema) | NO | NO |
| lesson | YES (candidate) | YES (stats gates) | NO | NO |
| experiment | Draft candidate only; frozen `ExperimentManifestV1` **NO** unless BUILD 17 policy/human climb | YES (defined protocol) | NO | NO |
| feature | YES (candidate) | YES | NO | NO |
| model | YES (candidate) | YES | NO | NO |
| prompt | YES (candidate) | YES | NO | NO |
| routing | YES (candidate) | YES | NO | NO |
| graph | YES (candidate) | YES | NO | NO |
| promotion recommendation | YES | YES | NO | NO |

---

# 31. Adaptation matrix

| Adaptation | State update | Structural change | Promotion required | Online candidate |
|---|---|---|---|---|
| volatility | YES (bounded) | if model family changes | if structural | YES if policy |
| regime posterior | YES (bounded) | if taxonomy changes | if structural | YES if policy |
| source confidence | YES (bounded) | if formula changes | if structural | YES if policy |
| calibration | map update vs new method | new method | method: YES | map: maybe |
| expert weights | bounded mix | new mixer | mixer: YES | bounded YES |
| model parameters | refit under identity | architecture | architecture YES | NO live |
| feature set | no | YES | YES | NO |
| prompt | no | YES | YES (lighter gate) | NO |
| routing | policy params vs graph | graph/policy class | class YES | params maybe |
| graph | no | YES | YES | NO |
| risk policy | no | YES | YES (heavy) | NO |
| execution policy | no | YES | YES (heavy) | NO |

Use consequence classes: prompt wording ≠ risk algorithm gates.

---

# 32. Qualification contamination matrix

| Stage | What may adapt | What must freeze | New candidate identity if… |
|---|---|---|---|
| training | fit params inside declared model identity | feature set, cutoff, labels | architecture/feature/prompt/graph/retrieval policy change |
| holdout | nothing structural | all evaluated identity | any structural change |
| backtest | nothing structural | policy + data cutoff | identity fields change |
| replay | nothing structural | recorded inputs | graph/model mismatch vs checkpoint |
| paper | bounded state only if campaign allows | campaign identity | undeclared structural change |
| shadow | same | same | same |
| forward | **none structural** | MODEL, POLICY, FEATURES, PROMPT, GRAPH, RETRIEVAL | any of those change |
| EVIDENCE | campaign rules only | EVIDENCE semantics | never silently |
| canary | bounded operational params per live policy | execution authority chain | risk/execution policy change |

---

# 33. Fast vs slow adaptation

**FAST (policy-bounded state):** rolling stats, posteriors, volatility,
liquidity, confidence, bounded expert weights.

**SLOW (challenger + evidence):** new features, models, prompts, routing,
graphs, datasets, risk methods.

---

# 34. External-tool architecture

```text
              IMP CANONICAL CONTRACTS
                     │
       ┌─────────────┼──────────────┐
       ▼             ▼              ▼
  Agent Adapter   ML Adapter    Workflow Adapter
       ▼             ▼              ▼
 optional graph    sklearn/HPO/   Temporal/Dagster
 framework         MLflow export
                     │
                     ▼
               Retrieval Adapter → optional vector DB
                     │
                     ▼
               Telemetry exporter → OTEL (non-canonical IDs)
```

```text
IMP DOMAIN AUTHORITY
      │
      ├── numerical libraries
      ├── data libraries
      ├── model libraries
      ├── agent adapters
      ├── workflow adapters
      ├── experiment adapters
      ├── telemetry exporters
      └── retrieval adapters

EXTERNAL TECHNOLOGY = IMPLEMENTATION DETAIL / OPTIONAL CAPABILITY
NOT CANONICAL IMP AUTHORITY
```

---

# 35. Build-vs-integrate matrix

| Concern | Current IMP | Build | Integrate | Hybrid | Reference only |
|---|---|---|---|---|---|
| numerical computation | NumPy | — | SciPy later | NumPy+SciPy | — |
| dataframes | pipeline pandas; foundation lists | keep contracts | Polars pilot | pandas research / native hot | — |
| large analytical data | JSON/sqlite | — | Arrow/DuckDB | Parquet artifacts | — |
| feature computation | IMP features | keep | optional tsfresh research | — | — |
| statistics | partial | domain metrics | SciPy/statsmodels | — | — |
| econometrics | absent | — | arch/statsmodels | — | — |
| ML | sklearn | keep baselines | LightGBM | — | PyTorch |
| online learning | absent by design (BUILD 24) | keep prohibition | River research extra | — | VW |
| drift | BUILD 23/24 | keep qualification owner | River detectors research | — | Evidently |
| optimization | absent | — | Optuna/SciPy/CVXPY | — | Ray Tune |
| agent orchestration | council/specialists | graph identity | one adapter | IMP+adapter | TradingAgents |
| experiment tracking | BUILD 17 manifests + future OF-01 | keep IMP ids | MLflow adapter | IMP id + export | W&B |
| workflow orchestration | runbooks | OF-03 | Temporal/Dagster later | — | — |
| vector retrieval | absent | policy | FAISS | — | Qdrant later |
| RL env/algos | absent | — | Gymnasium/SB3 | — | FinRL |
| backtesting | IMP replay/sim | keep | LEAN cross-check | — | Nautilus/vectorbt |
| portfolio optimization | risk caps | IMP risk | CVXPY/PyPortfolioOpt | — | Riskfolio |
| distributed tracing | partial logs | RT-01 contract | OTEL export | IMP+OTEL | Langfuse |
| AI evaluation | assistant audit | AI-01 | optional Ragas | — | — |
| dataset versioning | hashes/manifests | keep | optional DVC | — | — |
| reporting | JSON/UI | keep | Matplotlib/openpyxl | — | Plotly |

---

# 36. REBASE-02 compatibility (verified sufficient)

Approved spec already covers: run identity, attempt identity, experiment
attribution (initiator/trigger/parent; material-change vs retry), outcome
validity vs disposition, artifacts, reproducibility ranks vs evidence strength,
AI attribution ≠ AI reproducibility, checkpoint/resume compatibility,
historical/legacy indexing as provenance qualifiers.

Adaptive experience/lesson/graph objects can **cite** future `run_id` without
amending the spec. No standards-level blocker.

```text
NO REBASE-02 AMENDMENT REQUIRED
REBASE-02 REMAINS APPROVED FOR IMPLEMENTATION
```

---

# 37. Proposed ADAPT roadmap (adjusted numbering retained; meaning tightened)

| ID | Name | Depends |
|---|---|---|
| ADAPT-00 | this architecture/ecosystem study | done (this document) |
| ADAPT-01 | Outcome-Grounded Experience Kernel | Wrap BUILD 15–16; OF-01 HARD for durable run cites |
| ADAPT-02 | Reflection + Validated Learning Memory | ADAPT-01; AI-01 SOFT for LLM reflection |
| ADAPT-03 | Pattern discovery + optional River **research** beside BUILD 23 drift | Must not bypass BUILD 24 qualification |
| ADAPT-04 | Candidate hypothesis/experiment **drafts** into BUILD 17 | Must not auto-freeze `ExperimentManifestV1` |
| ADAPT-05 | Extra challenger types on BUILD 18/20 | sklearn/LightGBM behind existing factory |
| ADAPT-06 | Agent-Graph Challenger System | ADAPT-05; AI-02 LATER; single orchestrator adapter |
| ADAPT-07 | Promotion evidence packaging | Extends BUILD 20; does not replace it |
| ADAPT-08 | Bounded Online Adaptation | Explicit policy exception to “evidence not weights”; RT-01 first |

Do not implement ADAPT-01 runtime before OF-01 if experience records must cite
canonical runs. Conceptual design of ADAPT-01 may proceed in parallel after
REBASE-02.

---

# 38. Master dependency graph

```text
REBASE-01
    HARD → REBASE-02 (approved, unchanged)
                HARD → OF-01
                PARALLEL_SAFE → RT-01 contract work, XA-01 contract work
                PARALLEL_SAFE → ADAPT-00 (this)

OF-01 HARD → OF-02 → (per-op) OF-03 HARD → AI-02
OF-01 HARD → AI-01
OF-01 LATER_INTEGRATION → ADAPT-01 durable cites
RT-01 HARD → RT-02 HARD → RT-03
XA-01 HARD → XA-02
AI-01 SOFT → ADAPT-02 LLM reflection
ADAPT-00 SOFT → ADAPT-01…08 (sequence above)
EVIDENCE-01C INDEPENDENT of all of the above
```

Edges: HARD / SOFT / PARALLEL_SAFE / LATER_INTEGRATION / INDEPENDENT as above.

---

# 39. Quant research backlog (ranked)

| Priority | Question | Source | Baseline | Candidate | Dataset | Evaluation | Risk | Deps |
|---|---|---|---|---|---|---|---|---|
| P1 | Does GARCH beat IMP vol features for risk? | arch docs / finance-courses | rolling vol | EGARCH | frozen bars | settlement + calibration | leakage | arch |
| P1 | Cross-asset lead-lag vs leakage | XA + QFR | naive corr | lagged tests | multi-source | PIT law | look-ahead | none |
| P1 | Microstructure features after cost | order-flow BUILD | mid-only | LOB imbalance | replay | net alpha | capacity | none |
| P1 | Expert weight vs static fusion | council | equal/static | bounded online mix | ledgers | diversity+score | consensus | River |
| P2 | LightGBM vs sklearn GBM | sklearn | GBM | LightGBM | training sets | beats baseline | overfit | LightGBM |
| P2 | Drift detectors vs IMP regimes | River | regime labels | ADWIN etc. | streams | false alarm | chasing noise | River |
| P2 | Portfolio CVaR vs current caps | finance-courses | notional caps | CVXPY | returns | drawdown | model risk | CVXPY |
| P2 | Optuna thresholds as challengers | Optuna | manual | TPE | frozen | Run Ledger | p-hacking | Optuna |
| P3 | Deep hedging | PyTorch literature | rules | NN hedge | options | sim P&L | sim-to-real | PyTorch |
| P3 | Causal cross-asset | DoWhy | Granger-like | CATE | macro | holdout | spurious | DoWhy |
| P3 | RL execution | FinRL | TWAP | SB3 | sim | slippage | unsafe explore | Gymnasium |
| P3 | Graph debate depth | TradingAgents | current council | extra round | AI eval | cost vs accuracy | prompt drift | adapter |
| P3 | Agent/tool routing bandits | literature | static tools | contextual bandit | traces | regret vs freeze | nonstat. | River |

---

# 40. Adoption gate (every future install)

Prove: clear problem, IMP gap, library materially superior, narrow adapter,
acceptable license/maintenance/performance/security, exit strategy. Do not
install because popular.

Dependency restraint: **do not** expand `phase0-dependency-lock.json` in
ADAPT-00. Future extras belong in isolated research/optional groups with
principal approval.

---

# 41. Known limitations of ADAPT-00

- Microsoft Agent Framework was examined via GitHub `main` commit
  `947d933f2385b3f38ff40bef5b0c0245acdf3798` and public 1.0 GA notes; Python
  package internals were not fully tree-walked.
- QFR and finance-courses are unlicensed catalogs/notebooks; topic extraction
  is conceptual.
- vectorbt Commons Clause commercial-redistribution boundary needs counsel
  before any product wrapping.
- Nautilus LGPL linking needs counsel before any binary ship.
- No workload benchmarks were run (planning-only; Numba/Polars/orjson remain
  unmeasured).
- PyPI latest version pins for SciPy/River/Optuna were not frozen into a lock
  (no installs).
- BUILD 17–24 audit was completed after the first design draft; v1.1
  incorporates it. Remaining limitation: production fusion abstention and
  forward-evidence volume were not re-measured in this milestone.

---

# 42. Recommended next step

```text
Proceed with:
IMP-REBASE-02 Clean-Worktree Standards Implementation

Then perform canonical integration of the
accepted ADAPT-00 architecture and roadmap.
```

Do not create `docs/platform/REPRODUCIBILITY_AND_RUN_STANDARD.md` (etc.) in
this milestone. Do not build Run Ledger, Artifact Registry, trace backend,
workflow engine, AI/adaptive runtimes, vector DB, RL env, drift engine, or
model registry here.

---

# 43. Final status

```text
IMP_ADAPT_00_COMPLETE_WITH_LIMITATIONS
```
