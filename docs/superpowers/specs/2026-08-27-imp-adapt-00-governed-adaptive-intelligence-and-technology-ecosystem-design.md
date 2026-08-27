# IMP-ADAPT-00 Governed Adaptive Intelligence & Technology Ecosystem — Design

| Field | Value |
|---|---|
| Document ID | `IMP-ADAPT-00-DESIGN` |
| Classification | `ACTIVE_SUPPORTING` |
| Primary Truth Class | `APPROVED_FUTURE_DESIGN` |
| Review State | `READY_FOR_PRINCIPAL_REVIEW` |
| Version | `1.0` |
| Last Verified | `2026-08-27` |
| Establishing Milestone | `IMP-ADAPT-00 architecture study` |
| Supersedes | None |
| Superseded By | None |

This document is a planning-only architecture and technology-ecosystem study.
It is not a runtime authority, not an implementation plan with executable
tasks, not a dependency-lock change, and not a grant of trading, risk, release,
qualification, or execution authority. It does not reopen IMP-REBASE-02.

```text
NO REBASE-02 AMENDMENT REQUIRED
REBASE-02 REMAINS APPROVED FOR IMPLEMENTATION
```

## Purpose

Determine, from repository truth plus pinned external research:

1. what IMP must own because it is domain authority;
2. which mature libraries to leverage rather than rebuild;
3. what must remain behind replaceable adapters;
4. which current IMP systems already solve the problem;
5. which external ideas improve architecture without becoming dependencies;
6. how IMP can learn from settled outcomes without becoming an uncontrolled
   self-modifying trading system.

This is research + repository audit + architecture + technology selection +
dependency strategy + roadmap design. No packages were installed. No external
source was copied. Canonical platform documents were not modified.

## Verified starting state

Examined date: `2026-08-27`.

| Item | Verified value |
|---|---|
| Original workspace | `C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform` |
| Original branch / HEAD | `cloud/build-35-release-governance-operational-acceptance` / `44800d2e210e58ff5759c44cc343dd4578c0b821` |
| Original dirty state | Preserved untouched (tracked + untracked work left in place) |
| REBASE-02 review commit | `d899e211475f4b9372539944f997e13acbe3b73a` (`docs/imp-rebase-02-spec-review`) |
| REBASE-02 implementation spec | `docs/superpowers/specs/2026-08-27-imp-rebase-02-reproducibility-observability-evaluation-operational-standards-implementation-spec.md` |
| Spec SHA-256 | `1BE15D0BE64A1C14446BCC80FBEEEA609BBD15316DC668B0C660FB36483148E0` (matches expected) |
| Disposition | `IMP_REBASE_02_SPEC_APPROVED_FOR_IMPLEMENTATION` |
| ADAPT-00 branch | `docs/imp-adapt-00-learning-ecosystem` |
| ADAPT-00 worktree | `.worktrees/imp-adapt-00-learning-ecosystem` |
| ADAPT-00 starting HEAD | `d899e211475f4b9372539944f997e13acbe3b73a` |
| Later legitimate planning commits after REBASE-02 | None used as base |
| Unrelated worktrees | Preserved exactly |

## Sequencing invariant

REBASE-02 already completed design → written-spec review → semantic hardening →
implementation approval. ADAPT-00 does not reopen it.

A useful library, a desirable future feature, or an implementation convenience
is not a standards-level semantic incompatibility. None was found.

## Mission and safety

Target loop (eventual, governed):

```text
SENSE → UNDERSTAND → HYPOTHESIZE → PREDICT
→ RECOMMEND / ACT WITHIN AUTHORITY
→ OBSERVE → SETTLE → EVALUATE → ATTRIBUTE ERROR
→ REFLECT → LEARN → DISCOVER PATTERNS
→ GENERATE HYPOTHESES / EXPERIMENTS / CHALLENGERS
→ TEST → BACKTEST / REPLAY → SHADOW → FORWARD EVALUATE
→ PROMOTE → REPEAT
```

Permanent separations:

```text
LEARNING ≠ PROMOTION
PROMOTION ≠ AUTHORITY
AUTHORITY ≠ EXECUTION
EXECUTION REQUEST ≠ BROKER FILL
```

```text
AI ≠ authority
Agent ≠ authority
Reflection ≠ truth
Lesson ≠ truth
Hypothesis ≠ truth
Narrative ≠ truth
Model output ≠ observed fact
Prediction ≠ permission
Qualification ≠ permission
Promotion ≠ trading authorization
Release approval ≠ trading authorization
Live provider connection ≠ execution transport
Session authorization ≠ order authorization
Order authorization ≠ broker fill
```

No adaptive architecture may bypass:

```text
INTELLIGENCE → RISK AUTHORITY → HUMAN LIVE-SESSION AUTHORIZATION
→ PER-ORDER CONFIRMATION → EXECUTION GATEWAY → BROKER → RECONCILIATION
```

Execution authority is unchanged by this milestone.

---

# 1. Current Python and technology inventory

## 1.1 Declared Python

| Surface | Value |
|---|---|
| `phase0-dependency-lock.json` | CPython `3.11`, `tested_patch` `3.11.15` |
| Cloud / AGENTS.md | uv-managed CPython 3.11.15; `tzdata` in venv on Windows |
| `pipelines/stock_data/pyproject.toml` | `requires-python = ">=3.11"` |
| UI | Node/Vite React app; not a Python runtime |

## 1.2 Foundation dependency lock (authoritative for `src/market_platform_foundation`)

Direct third-party allowed: `numpy`, `pymongo`, `scikit-learn`.

`tzdata` is a Windows zoneinfo companion, not a foundation import.

Prohibited patterns in the lock include `aiohttp`, `pandas`, `requests`,
`websocket`, `pickle`, broker SDKs (`ib_insync`, `ccxt`, …). `analysis.py`
additionally prohibits `requests` and `websocket` at the AST policy layer.
Provider HTTP in the foundation is stdlib `urllib` / `http.client`
(`finviz/http_client.py`, `sec_edgar/transport.py`, FRED/EIA/CFTC/FINRA
transports).

Cloud install (`.cursor/install-cloud-deps.sh`): `tzdata numpy pymongo scikit-learn`.

There is **no** root `pyproject.toml`, `requirements.txt`, `poetry.lock`, or
`uv.lock` for the foundation. Intelligence BUILD 04.5–09 additionally uses
numpy/pymongo/scikit-learn; that is already declared.

## 1.3 Pipeline extra (not foundation)

`pipelines/stock_data` is a separate package (`market-data-pipeline`) with
`pandas`, `numpy`, `requests`, `pyarrow`, `yfinance`, `sqlalchemy`,
BeautifulSoup/lxml, `rich`; optional `curl_cffi`, `matplotlib`, Jupyter;
tests via pytest. This is an acquisition/research pipeline, not the live
foundation hot path.

## 1.4 UI

`ui/package.json`: React 18, Vite, TanStack Query, lightweight-charts,
recharts, zod. Charts already exist in product UI; Python plotting libraries
must not duplicate execution-critical UI.

## 1.5 Test stack

Foundation tests: stdlib `unittest` via `tools/validate.py`. Pipeline tests:
pytest. UI: vitest. Hypothesis, pytest-asyncio, pytest-benchmark are **not**
foundation dependencies today.

## 1.6 Rust / Redis / extra DBs

No `Cargo.toml` in this repository. Mongo via `pymongo` behind
`IntelligenceRepository`. SQLite appears in tooling/checkpoints elsewhere in
the program story; Redis/PostgreSQL/DuckDB are not foundation runtime.

## 1.7 Import facts (must not be inferred from lock files alone)

| Library | In lock? | Imported in foundation `src/`? | Imported in `pipelines/stock_data`? |
|---|---|---|---|
| NumPy | Yes (direct) | Yes — trainers, baselines, fusion calibrators | Yes |
| scikit-learn | Yes (direct) | Yes — logistic, GBM, isotonic/logistic calibration | No |
| PyMongo | Yes (direct) | Yes — `intelligence/persistence/mongo/repository.py` | No |
| pandas | **Prohibited** in foundation lock | **No** | Yes |
| requests | **Prohibited** | **No** (stdlib urllib instead) | Yes |
| matplotlib | No | No | Optional extra `full` |
| seaborn | No | No | No |
| openpyxl | No | No | No |
| SciPy, Polars, DuckDB, Numba, statsmodels, arch, XGBoost, LightGBM, CatBoost, PyTorch, River, Optuna, Pydantic, HTTPX, aiohttp, websockets, orjson, msgspec, LangGraph, MLflow | No | No | PyArrow yes (pipeline) |

NumPy is **not** a ubiquitous hot-path array layer today. Verified uses are
ML training/calibration (`sklearn_*`, `fusion/calibrators.py`,
`baselines/controls/*`). Most market, risk, replay, and feature code is
stdlib/dataclass oriented. Do not pretentiously “accelerate NumPy loops”
until RT-01 measures them.

---

# 2. Existing IMP adaptive foundation

Classification: `EXISTING_STRONG` | `EXISTING_PARTIAL` | `EXPERIMENTAL` | `HISTORICAL` | `ABSENT`.

| Capability | Classification | Evidence |
|---|---|---|
| Prediction identity + frozen settlement plan | EXISTING_STRONG | `PredictionLedgerEntryV1` |
| Outcome settlement | EXISTING_STRONG | `OutcomeSettlementService` / `outcomes/` |
| Temporal eligibility | EXISTING_STRONG | `available_time_ns <= decision_time_ns`; late registration handling |
| Specialists + evidence blackboard | EXISTING_STRONG | BUILD 12 `council/` |
| Blind Council + deliberation gate | EXISTING_STRONG | `BlindCouncilOrchestrator`, `DeliberationGate`, round limits |
| Fusion / calibration | EXISTING_STRONG | `fusion/calibrators.py` (sklearn isotonic + logistic) |
| Counterfactual vs observed replay | EXISTING_STRONG | `replay/scenario.py`; qualification scenarios F02/P12 forbid masquerading |
| Forward / paper qualification | EXISTING_STRONG | `forward_qualification/`, `paper_execution_qualification/` |
| EVIDENCE campaigns | EXISTING_STRONG | independent semantic track; content-derived IDs |
| Training / candidate artifacts | EXISTING_PARTIAL | BUILD 18 trainers + identity/hashes; no universal challenger factory |
| Release governance | EXISTING_PARTIAL | BUILD 35 + REBASE-02 standards (not yet implemented as docs) |
| Benchmark runner | EXISTING_PARTIAL | `tools/benchmark.py` informational; comparability standard missing (REBASE-02) |
| Assistant / AI | EXISTING_PARTIAL | read-only assistant; AI-01 attribution still future |
| Regime / routing / expert weights as governed adaptation | EXISTING_PARTIAL | fusion/council exist; no bounded online policy object |
| Experience records after settlement | ABSENT | settlement ≠ experience kernel |
| Validated lessons with falsifiers | ABSENT | |
| Retrieval index for lessons | ABSENT | |
| Agent-graph identity / checkpoint compatibility | ABSENT as IMP contract | REBASE-02 defines generic checkpoint rules; no graph ID yet |
| Automatic hypothesis/experiment generation | ABSENT | |
| Vector DB | ABSENT | |
| RL live exploration | ABSENT (correct) | |
| Adaptive Intelligence Fabric as named program family | ABSENT | this design proposes it as `APPROVED_FUTURE_DESIGN` |

**Do not rebuild** prediction, settlement, blind council, blackboard,
qualification, or EVIDENCE as generic LangGraph “memory” features.

---

# 3. What IMP must own vs leverage vs adapter

## 3.1 IMP domain authority (build / keep inside IMP)

Market canonical state; temporal eligibility; prediction identity; settlement;
quality admission; risk authority; execution authority; qualification;
learning/promotion governance; run/artifact/outcome/disposition identity
(REBASE-02 / OF-01); graph identity; experience/lesson epistemics.

## 3.2 Commodity algorithms (prefer mature libraries)

Linear algebra, optimization primitives, statistics, HTTP, serialization,
plotting, standard ML estimators, columnar IO.

## 3.3 Replaceable adapters

Agent orchestration engine; experiment-store backend; workflow engine;
vector index; telemetry export; optional dataframe engine for cold analytics.

```text
IMP CANONICAL CONTRACTS
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

External IDs (MLflow run, LangGraph thread, Qdrant point, Dagster asset,
Temporal workflow, RLlib worker) **never** become canonical IMP IDs.

```text
IMP canonical ID ↔ adapter mapping ↔ external ID
```

---

# 4. Three fabrics

MASTER_ARCHITECTURE currently names two fabrics. ADAPT-00 proposes a third
**as future canonical language**, not as an edit to `docs/platform/` in this
milestone.

## Real-Time Opportunity Fabric

Fast events, state, features, signals, opportunities, action preparation.
Hot path. No synchronous reflection, LLM lesson generation, vector reindex,
hyperparameter search, training, graph search, or experiment generation.

## Operating Fabric

Runs, artifacts, workflow, registries, SOPs, audit, reproducibility
(REBASE-02, OF-01..03).

## Adaptive Intelligence Fabric

Experience, evaluation, error analysis, reflection, lesson validation, memory,
pattern discovery, hypotheses, experiments, challengers, graph learning,
promotion **evidence**. Output is eligible intelligence candidates — never
broker orders.

```text
OUTCOME → ADAPTIVE FABRIC → LESSONS / EXPERIMENTS / CHALLENGERS
        → EVALUATION → PROMOTION → ELIGIBLE INTELLIGENCE

ELIGIBLE INTELLIGENCE → RISK → HUMAN AUTHORITY → EXECUTION
```

No `ADAPTIVE FABRIC → BROKER`.

---

# 5. Adaptive learning taxonomy

## MEMORY LEARNING

Changes future retrieved context (experiences, validated lessons, retrieval
policy version). Does not change model code.

## STRUCTURAL / MODEL LEARNING

Creates **candidates** for models, features, strategies, prompts, weights,
routing, retrieval policy.

## META / GRAPH LEARNING

Creates **candidates** for agent graph topology, specialists, ordering, tools,
debate depth, routing.

## BOUNDED ONLINE ADAPTATION

Updates values explicitly permitted by a pre-approved adaptive policy
(e.g. rolling volatility, regime posterior within bounds).

```text
STATE UPDATE ≠ MODEL REDEFINITION
```

Volatility estimate updates may be state. Volatility-model architecture
changes are structural and require challenger/promotion.

### Fast vs slow

**Fast (policy-bounded):** rolling state, posteriors, volatility, liquidity,
confidence, bounded expert weights.

**Slow (evidence + promotion):** new features, models, prompts, routing,
graph, data, risk method.

---

# 6. Outcome-grounded experience, reflection, lessons

## 6.1 Experience kernel (future ADAPT-01)

```text
PREDICTION / HYPOTHESIS + CONTEXT + CONTRIBUTORS + EVIDENCE + CUT-OFF
        ↓
SETTLEMENT
        ↓
OUTCOME
        ↓
EXPERIENCE RECORD
```

Potential fields (not frozen schema): prediction refs, run refs, contributors,
context, regime, confidence, outcome, performance, counterfactual refs,
quality, error attribution.

Three evidence categories remain separate:

```text
ACTUAL OBSERVED OUTCOME
COUNTERFACTUAL ESTIMATE
SIMULATED OUTCOME
```

Never merge. Existing replay/qualification already treats masquerading as a
failure mode — reuse that law.

## 6.2 Epistemics

```text
SETTLED OUTCOME     = EVIDENCE
DETERMINISTIC METRIC = DERIVED EVIDENCE
AI REFLECTION       = MODEL_OUTPUT
LESSON              = HYPOTHESIS / KNOWLEDGE CANDIDATE
```

A future lesson may include: claim, regime, instrument applicability,
supporting examples, contradictions, sample size, effect estimate, confidence,
falsifier, source, last validation. One losing trade cannot create global truth.

## 6.3 Memory layers

```text
RAW EVIDENCE → EXPERIENCE → REFLECTION → LESSON → VALIDATION
→ RETRIEVAL INDEX → AGENT CONTEXT
```

```text
HISTORICAL EVIDENCE ≠ EXPERIENCE ≠ REFLECTION ≠ LESSON
≠ RETRIEVAL INDEX ≠ WORKING CONTEXT
```

```text
VECTOR INDEX ≠ CANONICAL EVIDENCE
```

Retrieval should fetch supporting **and** contradicting cases. Detect
self-reinforcing loops (lesson → prompt → decision → apparent confirmation)
via independent outcomes, holdouts, counterexamples, regime bounds, decay,
revalidation.

Consequential AI runs should eventually cite retrieval policy, version,
cutoff, lesson IDs, experience IDs, index snapshot.

## 6.4 Graph identity and checkpoints

Graph candidate identity includes topology, nodes, versions, edges, routing,
models, tools, prompts, budgets, debate limits, configuration. Material change
creates a new graph identity.

Hard rule: a checkpoint may not silently resume under an incompatible graph
identity. This is compatible with REBASE-02 retry/resume/checkpoint rules and
does not require a REBASE-02 amendment; ADAPT-06 will specialize graph
identity under those rules.

Graph challenger lifecycle:

```text
CURRENT GRAPH → OUTCOMES → ERROR ANALYSIS → GRAPH CANDIDATE
→ CONTROLLED COMPARISON → REPLAY → SHADOW → FORWARD → PROMOTION
```

## 6.5 Challenger-only principle

Adaptive systems may auto-create feature, model, prompt, lesson, routing,
graph, and experiment **candidates**. Never automatic production replacement.

Promotion gates scale with consequence class. A prompt wording change is not
the same gate as a risk algorithm. Frozen forward evaluation requires stable
evaluated identity (model, policy, feature set, prompt, graph, retrieval
policy). Structural change means a new candidate identity.

Optimizer output = challenger, not production.

---

# 7. TradingAgents source-level audit

| Field | Value |
|---|---|
| Name | TradingAgents |
| URL | https://github.com/TauricResearch/TradingAgents |
| Owner | TauricResearch |
| Examined commit | `a33fd4c0f134485a43553a2c23a63cb14adbd88f` (main, 2026-07-18) |
| Examined date | 2026-08-27 |
| Latest release | `v0.3.1` |
| License | Apache-2.0 → `PERMISSIVE_COMPATIBLE` / `REFERENCE_ARCHITECTURE` |
| Maintenance | Active through 2026-07; 386 open issues at audit time |

### Actual loop (verified)

README + `tradingagents/graph/reflection.py` at examined commit:

```text
DECISION → PENDING / DECISION LOG
→ REALIZED OUTCOME (raw return + alpha vs market benchmark)
→ LLM REFLECTION (2–4 sentences)
→ MEMORY FILE (~/.tradingagents/memory/trading_memory.md)
→ RETRIEVAL (same-ticker recent + recent cross-ticker)
→ FUTURE PORTFOLIO-MANAGER PROMPT
```

Checkpointing is opt-in LangGraph per-node SQLite
(`~/.tradingagents/cache/checkpoints/`). v0.3.1 added graph-shape-aware
checkpoint resume after they hit incompatible-graph resume failures.

### Verified weaknesses relative to IMP

| Weakness | Verdict |
|---|---|
| Reflection treated as knowledge | **Present.** Reflection stored verbatim and re-injected. Class is MODEL_OUTPUT, not evidence. |
| Limited statistical lesson validation | **Present.** No sample-size, CI, regime, or falsifier object. |
| Hindsight bias | **Present by construction.** Outcome is known before the lesson is written. |
| Lesson overgeneralization | **Risk present.** One-paragraph lessons without applicability bounds. |
| Cross-instrument contamination | **Present as a feature.** Cross-ticker lessons are injected. |
| Regime blindness | **Not disproven.** No regime object in the reflection prompt. |
| Memory rotation | **Present.** Compact prose to avoid context bloat; no validated retirement. |
| Prompt-context drift | **Present.** Memory path and log shape can change retrieval content. |
| Limited provenance | **Present.** Markdown home-dir log, not content-addressed evidence. |
| Limited qualification / promotion | **Present.** Research CLI; not IMP qualification. |
| Duplicate prevention / decision identity | Weaker than IMP prediction ledger. |

### Useful patterns mapped to IMP (do not import LangGraph to get them)

| Pattern | IMP mapping |
|---|---|
| Specialized agents | Specialists + council participants |
| Bounded debate | `DeliberationGate` + round limits |
| Separate bull/bear evidence | Relation types on blackboard; do not require LLM debate |
| Risk-specific debate | Risk authority is **not** an LLM; keep separate |
| Manager arbitration | Council orchestrator; not Portfolio-Manager-as-broker |
| Reflection after realized outcomes | Future Adaptive Fabric **after** `OutcomeSettlementService` |
| Retrievable past lessons | Future validated lesson store; not markdown injection |
| Graph checkpointing | REBASE-02 checkpoint rules + future graph identity |
| Config-sensitive resume | Same: incompatible identity must not resume |

Disposition: `REFERENCE_ARCHITECTURE`. Not a dependency. Not source reuse.

---

# 8. Quant-Finance-Resources and finance-courses

## 8.1 Quant-Finance-Resources

| Field | Value |
|---|---|
| URL | https://github.com/PyPatel/Quant-Finance-Resources |
| Examined commit | `a281bb7c446b51301d1566e30e50f54facc3d4af` (2021-09-13) |
| License | **No license file** → `NO_LICENSE` / `REFERENCE_ONLY` |
| Maintenance | Stale (last push 2021-12) |

Treat as a reading list, not a codebase. High-value study areas mapped:

| Study area | IMP subsystem | Research question | Baseline | Experiment type | Priority | Dependencies |
|---|---|---|---|---|---|---|
| Probability / statistics | Evaluation, Risk | Are specialist scores calibrated? | sklearn calibration + IMP metrics | Offline | High | SciPy/statsmodels later |
| Linear algebra / numerical | Features, Risk | Vectorize feature/risk kernels? | Current stdlib/numpy | RT-01 profile first | Medium | NumPy; Numba only if measured |
| Time series | Intelligence, Regime | Volatility/mean reversion without leakage | IMP settlement windows | Walk-forward | High | statsmodels/`arch` research extra |
| Microstructure / order books | RT, XA | Does LOB state beat bar features? | Existing order-flow fixtures | Replay | High | IMP data; not LEAN |
| HFT / cross-market | XA, RT | Cross-venue lag vs alpha | Event timestamps | Research | Medium | XA-01 |
| Financial ML | Training | Do GBMs beat logistic? | sklearn logistic/GBM already | Challenger ladder | High | sklearn; maybe one booster |
| RL | Research only | Execution/hedging in sim | Random / heuristic | Sim only | Low | Gymnasium later |
| Deep hedging | Options/futures research | Hedge error vs delta | Classical hedge | Research | Low | PyTorch later |
| Derivatives | Options | Pricing vs IMP options features | Internal models | Research | Medium | SciPy |
| Optimization | Portfolio/Risk | Constrained allocation | Current risk limits | Offline | Medium | CVXPY research |
| Game theory | Narrative/Motive | Adversarial liquidity | Heuristic | Research | Low | None |

## 8.2 finance-courses (EDHEC notes)

| Field | Value |
|---|---|
| URL | https://github.com/z4ir3/finance-courses |
| Examined commit | `1466799ecf3ac3d32bd7119de74eb61d5150192b` (2023-12-11) |
| License | **No license** → `NO_LICENSE` / `REFERENCE_ONLY` |

| Topic | Map into |
|---|---|
| VaR | Risk |
| Portfolio optimization | Portfolio / Cross-Asset |
| Factor models | Intelligence / XA |
| Robust covariance | Risk research |
| Expected returns | Portfolio research (never auto-trade) |
| Diversification | Portfolio |
| ALM | Deferred (not IMP core) |
| Regime detection / crash classification | Macro Regime / Adaptive Intelligence |
| Feature selection / ML AM | Adaptive Intelligence / Evaluation |

---

# 9. User-supplied seven libraries (mandatory conclusions)

## pandas

- Already installed? Foundation **no** (prohibited). Pipeline **yes** (`>=2.0.0`).
- Already imported? Pipeline yes; foundation no.
- Purpose today: historical scrape/clean/export in `pipelines/stock_data`.
- Runtime class: `OFFLINE_RESEARCH` / `COLD_PATH` only.
- **Remain** in the pipeline extra. **Do not** add to foundation lock.
- **Replace for some workloads:** large scans / feature warehouses → evaluate
  Polars/DuckDB/Arrow in research pilots, with benchmarks on actual IMP
  datasets. **Never** per-tick hot loops or low-latency state mutation.

## NumPy

- Foundation **yes**, used in ML trainers/calibration.
- Runtime class: `WARM_PATH` / `OFFLINE_RESEARCH` today; `HOT_PATH` only if
  RT-01 shows array kernels on the opportunity path.
- **Expand** as the shared numerical array layer for features/stats/models
  **when those modules actually need arrays**. Not a substitute for profiling.
- Vectorization before Numba; Numba/Rust only after measurement.

## Matplotlib

- Not in foundation. Optional pipeline `full` extra.
- Runtime class: `OFFLINE_RESEARCH`.
- **Research-only.** Diagnostics, evaluation charts, acceptance **evidence
  figures** — never execution-critical runtime.
- Product UI already has recharts/lightweight-charts.

## Seaborn

- Not installed, not imported.
- Runtime class: `OFFLINE_RESEARCH`.
- **Optional** higher-level viz on top of Matplotlib. Do not add unless a
  research report stream needs it. Value is convenience, not architecture.

## openpyxl

- Not installed.
- Useful for explicit Excel import/export/operator reports.
- Runtime class: `OPTIONAL_OPERATOR_TOOL` / `COLD_PATH`.
- **Constrained:** interchange/report only.
- Hard rule: `EXCEL ≠ CANONICAL IMP DATA STORE`. `.xlsx` is never provenance
  or market-state authority.

## scikit-learn

- Foundation **yes**. Logistic, GradientBoosting, pipelines, scalers,
  isotonic/logistic calibration.
- Runtime class: `WARM_PATH` (training/eval) / inference if a candidate is
  promoted through existing training identity — still not execution authority.
- **Keep and expand** as the **baseline** framework. Sophisticated models must
  beat these baselines. Do not replace with XGBoost/PyTorch by default.

## Requests

- Foundation **prohibited**. Pipeline **yes**.
- Foundation providers: stdlib urllib (correct for lock).
- Suitable: cold research APIs, batch downloads, pipeline scrapers,
  bootstrap. **Not** latency-sensitive streaming.
- **Constrain** to pipeline/research extras. Live/provider paths compare
  stdlib vs provider-native SDKs vs (future) HTTPX/`websockets` **behind
  adapters**. Do not make `requests` the live architecture. Do not add
  aiohttp to the foundation (already prohibited) without a governed lock
  revision and a concrete streaming need.

---

# 10. Technology dispositions

Licensing classes used: `PERMISSIVE_COMPATIBLE`,
`WEAK_COPYLEFT_REVIEW_REQUIRED`, `STRONG_COPYLEFT_REVIEW_REQUIRED`,
`SOURCE_AVAILABLE_RESTRICTED`, `NO_LICENSE`, `UNKNOWN`.

Use classes: `REFERENCE_ONLY`, `CONCEPTUAL_REUSE`, `RESEARCH_BASELINE`,
`DEPENDENCY_CANDIDATE`, `SOURCE_REUSE_CANDIDATE`, `LICENSE_REVIEW_REQUIRED`,
`LICENSE_BLOCKED`.

Disposition rubric: `ADOPT_CANDIDATE` | `PILOT_CANDIDATE` |
`REFERENCE_ARCHITECTURE` | `RESEARCH_BASELINE` | `REFERENCE_ONLY` |
`DUPLICATIVE` | `TOO_HEAVY` | `LICENSE_REVIEW_REQUIRED` | `LICENSE_BLOCKED` |
`STALE_OR_SUPERSEDED` | `REJECT`.

**No adoption in ADAPT-00.** “ADOPT_CANDIDATE” means future governed extra
after a real gap is proven.

## 10.1 Required inventory table

Examined date `2026-08-27`. GitHub SHAs recorded where API quota allowed;
remaining licenses from project SPDX/docs. Incomplete SHA pins are listed
under Known limitations.

| Library | Already in IMP | Current Use | Candidate Use | Runtime Class | Disposition |
|---|---|---|---|---|---|
| pandas | Pipeline only | Scrapes, SQL bulk, CSV | Research frames; not foundation | COLD / OFFLINE_RESEARCH | Keep pipeline; **constrain** foundation |
| NumPy | Yes | sklearn trainers/calibration | Array layer for features/stats | WARM / research; HOT only if measured | **KEEP / EXPAND** |
| Matplotlib | Pipeline optional | Unused in foundation | Research/acceptance plots | OFFLINE_RESEARCH | Research-only |
| Seaborn | No | — | Optional research viz | OFFLINE_RESEARCH | Optional / not required |
| openpyxl | No | — | Excel interchange | OPTIONAL_OPERATOR_TOOL | Constrained interchange |
| scikit-learn | Yes | Baselines, calibration, GBM | Remain baseline ladder | WARM / OFFLINE | **KEEP / EXPAND** |
| requests | Pipeline; prohibited in foundation | Pipeline HTTP | Cold research only | COLD | **Constrain**; not live default |
| SciPy | No | — | Stats, optimize, signal, sparse | OFFLINE / WARM research | **PILOT_CANDIDATE** (research extra) |
| Polars | No | — | Large historical/feature frames | COLD analytics | **PILOT_CANDIDATE** (benchmark first) |
| PyArrow | Pipeline | Parquet/Arrow in pipeline | Snapshots, experiment datasets | COLD | **PILOT_CANDIDATE** for cold artifacts |
| DuckDB | No | — | Embedded analytical SQL on Parquet | COLD / OFFLINE_RESEARCH | **PILOT_CANDIDATE** |
| Numba | No | — | Measured numerical hot spots | HOT only after profile | **REFERENCE_ONLY** until RT-01 |
| statsmodels | No | — | TS, regression diagnostics | OFFLINE_RESEARCH | **PILOT_CANDIDATE** |
| arch | No | — | GARCH/vol, unit roots | OFFLINE_RESEARCH | **PILOT_CANDIDATE** |
| XGBoost | No | — | Tabular challenger | OFFLINE training | Pick **at most one** booster later |
| LightGBM | No | — | Tabular challenger | OFFLINE | Compare vs XGB; don't take all three |
| CatBoost | No | — | Tabular challenger | OFFLINE | Likely **DUPLICATIVE** if one booster exists |
| PyTorch | No | — | DL/RL/deep hedging research | OFFLINE_RESEARCH | **RESEARCH_BASELINE**; not default |
| River | No | — | Streaming metrics, drift, online models | WARM research; never silent live learn | **PILOT_CANDIDATE** |
| Optuna | No | — | HPO as challenger factory | OFFLINE | **PILOT_CANDIDATE** |
| CVXPY | No | — | Portfolio/risk research | OFFLINE | **RESEARCH_BASELINE** |
| Pydantic | No | dataclasses today | Adapter/config/AI structured IO | WARM/COLD; not ultra-hot | **PILOT_CANDIDATE** at boundaries |
| Pandera | No | — | DataFrame schema checks | COLD/WARM | **PILOT_CANDIDATE** for research frames |
| HTTPX | No | — | Sync+async REST adapter | WARM/COLD | **PILOT_CANDIDATE** vs stdlib |
| aiohttp | Prohibited in lock | — | High-concurrency HTTP | WARM | **DUPLICATIVE** if HTTPX chosen |
| websockets | `websocket` prohibited | Provider-native / stdlib | Streaming feeds | WARM/HOT adapter | Compare native SDKs first |
| orjson | No | stdlib json | JSON-heavy warm logs | WARM | Benchmark-gated **PILOT** |
| msgspec | No | dataclasses | Typed serdes at runtime edges | WARM | **PILOT** vs Pydantic |
| LangGraph | No | — | Optional agent graph engine | COLD/WARM AI | **REFERENCE_ARCHITECTURE**; at most one orchestrator |
| Microsoft Agent Framework | No | — | Graph/HITL/checkpoint Python/.NET | COLD/WARM AI | **REFERENCE_ARCHITECTURE**; compare at AI-02 |
| PydanticAI | No | — | Typed agents/structured out | COLD/WARM | **REFERENCE** / possible later adapter |
| DSPy | No | — | Prompt challenger factory | OFFLINE | **RESEARCH_BASELINE**; candidates only |
| MLflow | No | IMP run/training manifests | Optional experiment backend | COLD | **INTEGRATION_CANDIDATE** under IMP IDs |
| Dagster | No | — | Research data assets | COLD OF | **OPTIONAL FUTURE** OF-03 complement |
| Temporal | No | — | Durable COLD/WARM workflows | COLD/WARM OF | **OPTIONAL FUTURE**; not hot path |
| OpenTelemetry | No | planned RT-01 | Export traces/metrics/logs | WARM/COLD | **REFERENCE** + later exporter |
| FAISS | No | — | Local lesson retrieval index | COLD/WARM | **PILOT** when memory exists |
| Qdrant | No | — | Service retrieval + filters | COLD | Later scale; **not now** |
| Qlib | No | IMP snapshots/features/models | Concept reference | OFFLINE | **REFERENCE_ARCHITECTURE** |
| LEAN | No | IMP replay/backtest | External cross-check engine | OFFLINE | **REFERENCE** / optional validation engine |
| NautilusTrader | No | — | Event-driven/Rust reference | HOT architecture study | **REFERENCE_ARCHITECTURE**; LGPL review if ever linked |
| vectorbt | No | — | Vectorized sweeps | OFFLINE | **LICENSE_REVIEW_REQUIRED** |
| FinRL | No | — | RL research scaffold | OFFLINE | **RESEARCH_BASELINE** |
| Stable-Baselines3 | No | — | RL algorithms in sim | OFFLINE | **RESEARCH_BASELINE** |
| Gymnasium | No | — | RL env API | OFFLINE | **RESEARCH_BASELINE** |
| PettingZoo | No | — | Multi-agent RL | OFFLINE | Deferred |
| PyPortfolioOpt | No | — | Classical portfolio research | OFFLINE | **RESEARCH_BASELINE** |
| Riskfolio-Lib | No | — | Risk-parity/CVaR research | OFFLINE | **RESEARCH_BASELINE** |
| Hypothesis | No | unittest | Contract/property tests | DEV_TOOLING | **PILOT_CANDIDATE** |
| pyperf / pytest-benchmark | No | `tools/benchmark.py` | Strengthen measurement | DEV_TOOLING | Complement runner; don't replace identity |
| CrewAI / LlamaIndex / AutoGen | No | — | Extra agent stacks | — | **REJECT** stacking |
| TensorFlow / JAX | No | — | Overlapping DL | — | **REJECT** unless proven unique need |
| Redis | No | in-process / Mongo | Cache/pubsub | WARM | **REFERENCE_ONLY**; no adoption now |
| Vowpal Wabbit / Avalanche | No | — | Alt online/continual | OFFLINE | River first |
| Alibi Detect / Evidently / NannyML | No | finance regimes | Generic drift dashboards | COLD | Supplement only; not regime authority |
| Great Expectations | No | quality contracts | Dataset checks | COLD | Pandera first if DF checks needed |
| tsfresh / Darts / sktime | No | IMP features | Auto features / TS | OFFLINE | **tsfresh leakage risk**; not auto-promote |
| DoWhy / EconML / CausalML | No | — | Causal hypotheses | OFFLINE | Never auto-truth |
| Plotly / Jinja2 | UI has charts | — | Interactive research / reports | COLD | Optional; no exec path |
| RLlib / CleanRL | No | — | Scale RL | OFFLINE | Too heavy / research only |
| Weights & Biases / Aim / DVC | No | IMP artifacts | Duplicate provenance risk | COLD | Adapter-only if ever |
| Ray Tune / Nevergrad | No | Optuna | Extra HPO | OFFLINE | **DUPLICATIVE** if Optuna |
| Bottleneck / NumExpr | No | — | pandas accelerators | — | N/A without pandas hot path |

### External SHAs recorded (GitHub, 2026-08-27)

| Project | SHA | License | Release |
|---|---|---|---|
| TradingAgents | `a33fd4c0f134485a43553a2c23a63cb14adbd88f` | Apache-2.0 | v0.3.1 |
| Quant-Finance-Resources | `a281bb7c446b51301d1566e30e50f54facc3d4af` | none | — |
| finance-courses | `1466799ecf3ac3d32bd7119de74eb61d5150192b` | none | — |
| LangGraph | `bdb8a9c7a4aa1390af225f6a5d292e5088659bd5` | MIT | sdk==0.4.3 |
| microsoft/agent-framework | `947d933f2385b3f38ff40bef5b0c0245acdf3798` | MIT | dotnet-1.19.0 |
| Qlib | `79633dd9506ea689e5400dea0197717b5b3d74b7` | MIT | v0.9.7 |
| LEAN | `07fb0182bfe229edd9445cf675ac6509d0069539` | Apache-2.0 | v2.4.0.1 |
| NautilusTrader | `f2b2addb99527e3c9465573a596284f47b9edf10` | LGPL-3.0 | v1.231.0 |
| vectorbt | `34b6d5935e3ea3eccd549e2592bc0f455b8045f5` | Apache-2.0 + Commons Clause | v1.1.0 |
| FinRL | `2334a5fe6d30629157f13c3b0319e1637e15e123` | MIT | v0.3.8 |
| River | `64285b9dd6c606804753235fe992bcf25b9856ee` | BSD-3-Clause | 0.26.1 |
| Optuna | `f6898dab5bba804dd2bdb6ce7cc06b41b51506e4` | MIT | v4.9.0 |
| MLflow | `9dfea31cb82744a2d3d5ea1a2222b93df629edff` | Apache-2.0 | v3.15.2 |
| Pydantic | `965c23dd93bd5ca7b86224ba39ccbe79399f117b` | MIT | v2.13.4 |
| Pandera | `9777c23b4bbc146c115a479b7551d0671c76ebcd` | MIT | v0.32.1 |
| HTTPX | `b5addb64f0161ff6bfe94c124ef76f6a1fba5254` | BSD-3-Clause | 0.28.1 |
| aiohttp | `58899272ce81abbae535eba108e2dca6ec87b4b1` | Apache-2.0 | v3.14.3 |
| websockets | `bd83f2393017cceabb88f125073af74124ae5fbf` | BSD-3-Clause | 17.1 |
| orjson | `6737895a1a4e3e26df0569a40147893a786f9a58` | Apache-2.0 | 3.12.0 |

NautilusTrader: `WEAK_COPYLEFT_REVIEW_REQUIRED` if ever dynamically linked;
default disposition remains reference-only.

vectorbt: `SOURCE_AVAILABLE_RESTRICTED` — Commons Clause restricts selling
products that are primarily the software. IMP must not take it as a product
dependency without legal review. Research-only until then.

Hypothesis (MPL-2.0): `WEAK_COPYLEFT_REVIEW_REQUIRED` for shipping the test
dependency in distributions; typically acceptable for `DEV_TOOLING`.

---

# 11. Recommended architectures by layer

## Numerical / data

Foundation stays NumPy + stdlib. Pandas stays pipeline/research.
Pilot **SciPy** (do not hand-roll standard algorithms), **PyArrow/Parquet**
for cold immutable snapshots, **DuckDB** for local analytical SQL, **Polars**
only if benchmarks beat pandas/stdlib on actual IMP historical sets.
Arrow identity does not replace IMP IDs. DuckDB does not replace Mongo /
`IntelligenceRepository`.

## Statistics / econometrics

Pilot SciPy stats + statsmodels + `arch` as a **research extra** for
volatility, unit roots, GARCH, bootstrap. Map into volatility intelligence,
risk, regime research, options/futures, benchmark validation — outputs are
hypotheses/challengers.

## ML

Keep sklearn as mandatory baselines. At most one gradient-boosted library
later (LightGBM vs XGBoost; Windows + determinism + serialization matter).
PyTorch is research for sequence/RL/hedging — not default. No TF+JAX+Torch
stack.

## Online / adaptive learning

River is the highest-value **research** library for incremental metrics,
drift detectors, bounded online models. sklearn incremental estimators are
a lighter alternative for a subset. **No online production learning** in
ADAPT-00–07. ADAPT-08 is bounded, pre-approved policy only.

## Drift

Finance-specific regime logic remains authority. River drift (and later
optional Evidently-style reports) **supplement**. Monitor feature, target,
relationship, calibration, performance, regime, and source-quality drift.
Lessons get applicability windows, decay, and retirement.

## HTTP / providers

Keep stdlib urllib in foundation until a governed extra exists.
HTTPX is the leading modern REST candidate (sync+async, HTTP/2) **behind
provider adapters**. Do not add aiohttp as well without a distinct server
or concurrency need. `websockets` vs provider-native sockets: prefer native
SDKs when they already exist; generic websockets only for feeds that lack
them. `requests` remains pipeline-only.

## Serialization

Canonical semantics over speed. stdlib json remains default. orjson/msgspec
only after measured JSON-heavy warm paths. Never pickle in foundation.

## Agent ecosystem

**One** orchestration framework **or** IMP-owned workflow with optional
adapter. Reject IMP→LangGraph→CrewAI→LlamaIndex→AutoGen.

Default: **IMP-owned graph contract** (specialists, council, tools, HITL
already conceptually present). LangGraph and Microsoft Agent Framework are
the two serious references (graphs, checkpoints, HITL). Choose at most one
at AI-02 if IMP-owned graphs become costly. PydanticAI is attractive for
typed boundaries. DSPy = prompt **challenger** factory only.

TradingAgents is conceptual reuse only.

## Quant frameworks

| Framework | Class |
|---|---|
| Qlib | REFERENCE_ARCHITECTURE (data/model/experiment concepts; not authority) |
| LEAN | REFERENCE / optional EXTERNAL CROSS-CHECK |
| NautilusTrader | High-priority REFERENCE for event core, clocks, live/backtest symmetry, Rust boundary (RT-03 decision still measurement-gated) |
| vectorbt | LICENSE_CONSTRAINED research |
| Backtrader / Zipline-reloaded | STALE_OR_SUPERSEDED relative to Nautilus/LEAN for IMP's aims |
| FinRL | RESEARCH_BASELINE |

Do not replace IMP.

## Portfolio / risk

PyPortfolioOpt, Riskfolio-Lib, CVXPY = research baselines for mean-variance,
HRP, risk parity, CVaR. IMP risk **authority** stays IMP. Optimizer output
is a challenger allocation, not an order.

## MLOps / provenance

```text
IMP CANONICAL CONTRACT → OPTIONAL TOOL ADAPTER
```

REBASE-02 run/attempt/artifact/disposition is sufficient. MLflow may be a
**backend** under adapters; W&B/DVC/Aim must not become parallel truth.
No duplicate ID spaces pretending to be canonical.

## Workflow

Dagster (data assets/lineage) and Temporal (durable state machines) are
optional **COLD/WARM Operating Fabric** later (OF-03). Off the hot market
path. Prefect similar. Do not pick all three.

## Vector memory

FAISS for local-first retrieval when Adaptive Fabric exists. Qdrant if
metadata filter/scale requires a service. Index ≠ evidence.

## Observability / testing / profiling

OpenTelemetry: export `trace_id`/`span_id`/metrics/logs **without** letting
OTEL redefine `run_id`/`attempt_id`/`correlation_id`/`event_id`.
Phoenix/Langfuse/Ragas/DeepEval/TruLens: optional AI eval adapters; avoid
overlap with RT-01 and Run Ledger.

Testing: keep unittest + `validate.py`. Pilot Hypothesis for contracts,
temporal edges, serdes, numerical properties. pytest-asyncio only if async
providers land.

Profiling: preserve `tools/benchmark.py`. pyperf / pytest-benchmark may
**strengthen measurement** under RT-01. cProfile/py-spy/Scalene/Memray as
operator tools — do not add all as dependencies. No benchmark gating in
REBASE-02 scope.

Formats by workload: JSONL for evidence-like journals; Parquet/Arrow for
columnar research sets; MessagePack only behind adapters; provider binary
as-is.

---

# 12. Shortlist

## KEEP / EXPAND CURRENT USE

NumPy, scikit-learn, PyMongo, stdlib urllib/json/unittest, `tools/benchmark.py`,
existing prediction/settlement/council/qualification/EVIDENCE, UI chart stack.

## HIGH-PRIORITY PILOT CANDIDATES

SciPy; River; Optuna; statsmodels/`arch`; PyArrow+DuckDB (cold); HTTPX at
provider/research adapters; Hypothesis; OpenTelemetry exporter (with RT-01);
Pydantic at adapter/AI boundaries; FAISS when lessons exist.

## HIGH-PRIORITY REFERENCE ARCHITECTURES

TradingAgents (patterns), LangGraph, Microsoft Agent Framework, Qlib,
NautilusTrader, LEAN (cross-check), OpenTelemetry.

## RESEARCH BASELINES

FinRL, Stable-Baselines3, Gymnasium, PyPortfolioOpt, Riskfolio-Lib, CVXPY,
PyTorch, DSPy, vectorbt (license-constrained).

## OPTIONAL FUTURE INFRASTRUCTURE

MLflow adapter, Dagster, Temporal, Qdrant, Pandera, orjson/msgspec,
Polars (if benchmarks win), LightGBM **or** XGBoost (one).

## DUPLICATIVE / UNNECESSARY

aiohttp+HTTPX together; CatBoost+XGB+LightGBM together; CrewAI/LlamaIndex
stacking; TF+JAX+Torch; Ray Tune if Optuna; W&B+MLflow+DVC as triple truth;
Seaborn unless report volume justifies it.

## LICENSE-CONSTRAINED

vectorbt (Commons Clause); NautilusTrader if linked (LGPL-3.0);
Hypothesis MPL for distribution review; unlicensed resource repos
(Quant-Finance-Resources, finance-courses) — reading only.

## REJECTED

Automatic production self-modification; Excel-as-store; requests as live
streaming default; pandas on tick hot path; RL live exploration;
framework stacking; reopening REBASE-02 for library convenience.

---

# 13. Build-vs-integrate matrix

| Concern | Current IMP | Build | Integrate | Hybrid | Reference only |
|---|---|---|---|---|---|
| Numerical computation | NumPy islands | — | Expand NumPy/SciPy | Yes | — |
| Dataframes | Pipeline pandas | Keep foundation free | Polars/DuckDB pilots | Yes | — |
| Large analytical data | JSON/fixtures | Artifact contracts | Arrow/Parquet/DuckDB | Yes | — |
| Feature computation | IMP features | Own semantics | NumPy/Polars engines | Hybrid | — |
| Statistics | Partial | Own metrics identity | SciPy/statsmodels | Hybrid | — |
| Econometrics | Absent | — | `arch`/statsmodels | Research extra | — |
| ML | sklearn | Own candidate identity | sklearn + one booster | Hybrid | — |
| Online learning | Absent | Bounded policy | River research | Hybrid | — |
| Drift | Regime partial | Own regime authority | River detectors | Hybrid | — |
| Optimization | Risk limits | Own constraints | Optuna/CVXPY | Hybrid | — |
| Agent orchestration | Council/assistant | IMP graph contract | Optional one framework | Hybrid | LangGraph/MS AF |
| Experiment tracking | Manifests | OF-01 ledger | MLflow adapter | Hybrid | — |
| Workflow orchestration | Partial | OF-03 | Temporal/Dagster | Later | — |
| Vector retrieval | Absent | Experience/lesson store | FAISS/Qdrant index | Hybrid | — |
| RL environments | Absent | — | Gymnasium | — | FinRL |
| RL algorithms | Absent | — | SB3 in sim | — | RLlib |
| Backtesting | IMP replay | Own temporal law | LEAN/Nautilus cross-check | Hybrid | vectorbt |
| Portfolio optimization | Risk | Own authority | PyPortfolioOpt/CVXPY | Research | — |
| Distributed tracing | Partial logs | RT-01 semantics | OTEL export | Hybrid | — |
| AI evaluation | Partial | AI-01 | Phoenix/Ragas adapters | Later | — |
| Dataset versioning | Hashes/manifests | Own | DVC adapter only | Hybrid | — |
| Reporting | UI + JSON | — | Matplotlib/openpyxl | Research/ops | Plotly |

Every actual adoption still needs: clear problem, IMP gap, library superiority,
narrow adapter, license, maintenance, performance, security, exit strategy.

---

# 14. Required matrices

## 14.1 Adaptive primitive reuse

| Primitive | Existing IMP Foundation | Missing Gap | External Help | Owner |
|---|---|---|---|---|
| experience | Settlement + ledger ids | Experience record after outcome | None required | Adaptive Fabric |
| error attribution | Qualification + council diagnostics | Unified taxonomy expansion | None | IMP eval |
| reflection | Absent | Epistemic wrapper | LLM via AI-01 | Adaptive Fabric |
| lesson | Absent | Validated lesson object | None | Adaptive Fabric |
| memory | Assistant audit files | Layered stores | — | Adaptive Fabric |
| retrieval | Absent | Index + contradiction query | FAISS later | Adapter |
| drift | Regime fragments | Drift monitors | River | IMP + River research |
| pattern detection | Evaluation cohorts | Grouping + stats gate | sklearn/SciPy | Adaptive Fabric |
| hypothesis | `hypotheses/` service | Auto-generation | LLM advisory | IMP |
| experiment | Training manifests | Experiment generator | Optuna/MLflow adapters | OF + Adaptive |
| model challenger | BUILD 18 trainers | Factory + ladder | sklearn/boosters | IMP |
| prompt challenger | Absent | Candidate prompts | DSPy optional | AI + Adaptive |
| graph challenger | Council topology implicit | Graph identity + compare | LangGraph concepts | IMP |
| promotion | Release/qualification | Adaptive promotion gov | REBASE-02 dispositions | IMP humans |
| bounded online learning | Calibration updates | Policy object + bounds | River | IMP |

## 14.2 Learning-authority

| Output | Auto-create | Auto-test | Auto-promote | Trading Authority |
|---|---:|---:|---:|---:|
| reflection | YES | NO | NO | NO |
| lesson | YES | YES (validation tests) | NO | NO |
| experiment | YES | YES | NO | NO |
| feature | YES | YES | NO | NO |
| model | YES | YES | NO | NO |
| prompt | YES | YES | NO | NO |
| routing | YES | YES | NO | NO |
| graph | YES | YES | NO | NO |
| promotion recommendation | YES | YES | NO | NO |

## 14.3 Adaptation

| Adaptation | State Update | Structural Change | Promotion Required | Online Candidate |
|---|---:|---:|---:|---:|
| volatility | YES | if model form changes | structural only | YES bounded |
| regime posterior | YES | if taxonomy changes | structural only | YES bounded |
| source confidence | YES | if formula changes | structural only | YES bounded |
| calibration | YES (isotonic fit freeze) | new calibrator class | YES if structural | LIMITED |
| expert weights | YES if policy allows | new fusion | YES if structural | YES bounded |
| model parameters | NO (new candidate) | YES | YES | NO |
| feature set | NO | YES | YES | NO |
| prompt | NO | YES | YES (light gate) | NO |
| routing | NO | YES | YES | NO |
| graph | NO | YES | YES | NO |
| risk policy | NO | YES | YES (heavy) | NO |
| execution policy | NO | YES | YES (heavy) | NO |

## 14.4 Qualification contamination

| Mode | May adapt | Must freeze | New candidate identity if |
|---|---|---|---|
| training | dataset pipeline per spec | labeled cutoff | feature/model/prompt/graph change |
| holdout | nothing under test | model+features+policy | any structural tweak |
| backtest | nothing under test | same | leakage or spec change |
| replay | visibility overlay per scenario type | scenario identity | mixing observed/counterfactual |
| paper | bounded state if declared | evaluated identity | undeclared structural change |
| shadow | same | same | same |
| forward | same | campaign definition | same |
| EVIDENCE | per campaign authority | frozen campaign semantics | independent track |
| canary | live **authority** path only | authorized identity | any undeclared change |

---

# 15. Expert adaptation and RL

Bayesian model averaging / mixture-of-experts / online expert algorithms /
contextual bandits / stacking / regime-conditioned weights:

| Method | Class |
|---|---|
| Regime-conditioned weights within approved simplex | BOUNDED_ONLINE_CANDIDATE |
| Stacking / new fusion architecture | OFFLINE_CHALLENGER |
| Bandits for tool/graph choice | RESEARCH_ONLY until sim safety |
| Unbounded online GBM retrain | REJECT |

Preserve expert diversity: accuracy, calibration, alpha, abstention, cost,
latency, failure rate, diversity, correlation, false-consensus risk.

RL (FinRL, SB3, Gymnasium, PettingZoo, RLlib, CleanRL): research for
execution, hedging, allocation, routing, tool selection **in simulation**.
Risks: reward hacking, nonstationarity, sim-to-real, tail risk, costs,
liquidity, unsafe exploration, shift, instability. No uncontrolled live
exploration. Simulated ≠ observed.

---

# 16. ADAPT roadmap (evaluated)

Numbering preserved; dependencies corrected.

| ID | Name | Intent |
|---|---|---|
| ADAPT-00 | This study | Architecture + ecosystem |
| ADAPT-01 | Outcome-Grounded Experience Kernel | Experience records on settlement; no LLM required |
| ADAPT-02 | Reflection + Validated Learning Memory | Epistemics + lesson validation + layered memory |
| ADAPT-03 | Adaptive Evaluation + Drift + Pattern Discovery | Drift monitors + statistical patterns |
| ADAPT-04 | Hypothesis & Experiment Generator | Competing hypotheses; frozen experiment contracts |
| ADAPT-05 | Feature / Model / Prompt / Routing Challenger Factory | Candidates only |
| ADAPT-06 | Agent-Graph Challenger System | Graph identity + incompatible checkpoint rule |
| ADAPT-07 | Adaptive Promotion Governance | Consequence-class gates; still not trading authority |
| ADAPT-08 | Bounded Online Adaptation | Pre-approved state updates only |

Do not implement ADAPT-01 before REBASE-02 standards exist as documents
(implementation of those docs is a separate milestone). Experience records
**later-integrate** to OF-01 run IDs; they can be designed against REBASE-02
semantics immediately.

---

# 17. Master dependency graph

```text
REBASE-01
    HARD → REBASE-02 (approved, unchanged)
                HARD → OF-01
                HARD → RT-01 contract (runtime later-integrates OF-01)
                HARD → XA-01 contract prep
                PARALLEL_SAFE after REBASE-02: OF-01, RT-01 prep, XA-01 prep, ADAPT-00 (done)
OF-01 HARD → OF-02
OF-01 HARD → AI-01
OF-02 per-operation HARD → OF-03
OF-03 HARD → AI-02
RT-01 HARD → RT-02 HARD → RT-03
XA-01 HARD → XA-02
REBASE-02 SOFT/LATER → ADAPT-01 (uses run/outcome semantics)
OF-01 LATER_INTEGRATION → ADAPT-01 implementation (run_id linkage)
ADAPT-01 HARD → ADAPT-02 → ADAPT-03
ADAPT-03 SOFT → ADAPT-04
ADAPT-01 SOFT → ADAPT-05 (challengers need experience)
ADAPT-05 / AI-01 LATER → ADAPT-06
ADAPT-05 + ADAPT-06 HARD → ADAPT-07
ADAPT-07 HARD → ADAPT-08
AI-01 SOFT → ADAPT-02 reflection (LLM)
EVIDENCE-01C INDEPENDENT of all of the above
```

Canonical `docs/platform/MASTER_*` are **not** edited in ADAPT-00. Integrate
this graph after REBASE-02 documentation implementation or a dedicated
canonical-doc milestone.

---

# 18. REBASE-02 compatibility (verified)

| Concern | REBASE-02 coverage | Adaptive need | Verdict |
|---|---|---|---|
| run identity | `run_id` required rules | experience/experiment parent | SUFFICIENT |
| attempt identity | sequential default, `attempt_id` | retries of eval jobs | SUFFICIENT |
| experiment attribution | evaluation standard + AI ops | challenger studies | SUFFICIENT |
| outcome validity | VALID/INVALID/INDETERMINATE/… | settlement vs learning | SUFFICIENT |
| disposition | ACCEPT/REJECT/…; not lifecycle | promotion recommendations | SUFFICIENT |
| artifacts | logical vs content identity | experience/lesson artifacts | SUFFICIENT |
| reproducibility | R classes + evidence strength | learning runs | SUFFICIENT |
| AI attribution | provider/model/template/tools/cutoff | reflection provenance | SUFFICIENT |
| checkpoint compatibility | resume vs new attempt vs new run | graph identity specializes later | SUFFICIENT |
| historical indexing | LEGACY_PARTIAL / relations | lesson retrieval | SUFFICIENT |

No blocking semantic gap. Graph identity is an Adaptive Fabric specialization,
not a contradiction.

---

# 19. Quant research backlog (ranked)

| Priority | Question | Source | Baseline | Candidate | Dataset | Evaluation | Risk | Deps |
|---|---|---|---|---|---|---|---|---|
| 1 | Calibration drift of fusion vs settled direction | IMP fusion + ledger | sklearn calibrators | River drift + re-cal challenger | settled forecasts | Brier/ECE by regime | leakage | ADAPT-01, sklearn |
| 2 | Specialist diversity vs false consensus | Blind Council | current fusion | correlation/abstention metrics | blackboard snapshots | eval cohorts | overfit weights | council |
| 3 | Volatility state vs GARCH challenger | Risk/intel | rolling std | `arch` GARCH | bars with cutoff | forecast log-score | structural vs state | research extra |
| 4 | Cross-asset lag features | XA | univariate | event-time joins | multi-domain fixtures | replay | identity mix | XA-01 |
| 5 | Microstructure vs bar features | order flow | existing LOB fixtures | IMP features | replay | leakage | data |
| 6 | Tabular booster vs sklearn GBM | training | sklearn GBM | LightGBM **or** XGB | training sets | challenger ladder | dep weight | ADAPT-05 |
| 7 | Online expert weights in bounds | fusion | static weights | bounded mixing | settled | regret vs freeze | live learn | ADAPT-08 |
| 8 | Retrieval of contradicting lessons | memory | none | FAISS + filters | experiences | retrieval eval | confirmation bias | ADAPT-02 |
| 9 | Prompt challengers | AI-01 | frozen templates | DSPy candidates | AI eval sets | AI-01 metrics | silent mutate | AI-01 |
| 10 | Execution RL in sim | research | heuristics | SB3 + costs | sim | tail + cost | sim-to-real | never live |
| 11 | Deep hedging | options | delta | PyTorch research | options fixtures | hedge error | complexity | research |
| 12 | Causal cross-asset | XA | correlations | DoWhy hypotheses | observational | never auto-causal | confounds | research |
| 13 | Graph debate depth | council | max rounds | graph challenger | replay | eval | checkpoint clash | ADAPT-06 |
| 14 | Portfolio CVaR research | risk | current limits | CVXPY/Riskfolio | returns | research only | authority bypass | research |

---

# 20. Governing principles (normative for future work)

Use mature libraries for commodity infrastructure. Keep IMP domain authority
inside IMP. Reuse before inventing. Benchmark before replacing. Do not add
dependencies because they are popular. External framework IDs never become
canonical IMP IDs. Avoid overlapping frameworks and duplicate provenance.
pandas is not automatically the best engine for every workload. NumPy is
foundational but not a substitute for profiling. Matplotlib/Seaborn belong
off the hot path. Excel is interchange, not storage. sklearn baselines remain
valuable. Synchronous HTTP is not a live-streaming architecture. Reflection
and lessons are not truth. Memory learning is not structural learning. State
adaptation is not model mutation. A candidate is not production. Promotion is
not trading authority. Vector search is not evidence. RL simulation is not
live evidence. Counterfactuals are not observations. Concept drift is not
automatically model failure. Self-adjusting graphs remain versioned.
Checkpoints cannot cross incompatible graph identities. Online adaptation
stays within pre-approved bounds. Forward qualification requires stable
identity. Learning stays off the critical execution path unless proven safe.
Reproducibility precedes self-improvement. EVIDENCE-01C remains independent.
Do not reopen approved REBASE-02 without a demonstrated standards-level
conflict.

---

# 21. Known limitations of ADAPT-00

- GitHub unauthenticated API rate limit stopped live SHA pins after orjson;
  remaining licenses are from SPDX/project documentation, not a second SHA
  fetch.
- TradingAgents `memory.py` raw fetch timed out; memory path and injection
  behavior are taken from README + `reflection.py` at `a33fd4c0`.
- No runtime benchmarks of Polars/orjson/Numba were run (forbidden:
  planning only, no installs).
- Pipeline vs foundation split is architectural; a future governed extra
  system is recommended but not specified as lockfile edits.
- Canonical `docs/platform/MASTER_*` not updated (frozen by this milestone).

---

# 22. Recommended next step

```text
Proceed with:
IMP-REBASE-02 Clean-Worktree Standards Implementation

Then perform canonical integration of the
accepted ADAPT-00 architecture and roadmap.
```
