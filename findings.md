# Findings

## Repository and baseline

- Git root: `C:\Users\adame\Desktop\market-trading-platform\integrated-market-platform`.
- Current branch: `feat/p6-shadow-run-1-forward-validation`, ahead of origin by
  one commit.
- The worktree was already dirty before this increment: 44 tracked
  modifications and 47 untracked files.
- Baseline `tools/validate.py changed` result before implementation:
  `1206 tests, 9 skipped, 1 failure, 91 errors`.
- The aggregate touched `finviz`, `platform`, `intelligence`, `ui1`, and
  `validation`; exact selector ownership is unknown because no detailed
  traceback was retained.
- Existing package import smoke checks do not reproduce an application import
  cycle.

## Existing authorities

- `strategy/scanning.py`: `UniversalStrategyScanner` persists immutable
  `StrategyMatch` records.
- `intelligence/baselines/engine.py`: `BaselinePredictionEngine` produces the
  existing `ForecastV1`; forecast production stays outside the new runtime.
- `intelligence/opportunity/bridge.py`: validates StrategyMatch/Forecast
  lineage and delegates canonical creation to `OpportunityEngine`.
- `intelligence/opportunity/clustering.py`: non-authoritative thesis
  clustering projection.
- `intelligence/opportunity/comparison.py`: `GlobalOpportunityComparator`
  and `CapitalAllocator`; allocation intents are now additionally materialized
  by the durable Task 1 allocation-decision sidecar.
- `intelligence/execution/engine.py`: `PreTradeRiskEngine`,
  `RiskDecisionV1`, and `PaperExecutionOrchestrator`.
- `paper/ledger.py` and `paper/execution.py`: append-only Paper events,
  internal simulation, idempotent orders, and projections.
- `portfolio/ledger.py`: authoritative fill-driven equity accounting.
- `portfolio/attribution.py`: immutable strategy allocation slice and
  shared-style realized P&L calculation, currently requiring event-driven
  materialization.
- `intelligence/outcomes/service.py`: prediction registration and separate
  due-time settlement.
- `strategy/learning.py`: reference-only joins, independent prediction/trading
  quality, minimum evidence/sample gates, and non-promotional research
  handoffs.
- `intelligence/persistence/repository.py`, memory, and Mongo implementations
  support immutable sidecars and need allocation-decision methods.

## Approved design decisions

- Add a durable allocation decision sidecar through IntelligenceRepository,
  with memory and Mongo support; Paper/local state remains authoritative only
  for execution events and portfolio state.
- Inject a deterministic ForecastV1 resolver keyed from StrategyMatch.
- Persist a lightweight deterministic decision-set ID shared by candidates
  evaluated together.
- Persist only candidates actually evaluated by CapitalAllocator; do not
  duplicate scanner/comparator rejection semantics.
- Keep `SELECTED`, `NOT_SELECTED`, and `NO_ALLOCATION` distinct.
- Preserve desired allocation, requested proposal, approved/reduced risk,
  submitted order, and actual filled quantities independently.
- Materialize attribution from actual fill facts as immutable cumulative
  fill-set snapshots; never sum cumulative snapshots.
- Keep forecast settlement independently owned and tolerate a closed trade
  with a not-yet-due forecast.
- Use a separately governed canonical SELL opportunity only for the bounded
  deterministic exit test, without defining all future close semantics.

## Task 7 implementation and validation findings

- The delivered runtime path is backend-only. It persists allocation decision
  sets through the IntelligenceRepository, carries generic allocation →
  proposal → risk → Paper lineage, and reconstructs from authoritative
  records/projections rather than persisting a narrative runtime object.
- Quantity semantics are preserved as distinct facts: allocation desired,
  proposal requested, risk approved/reduced, submitted order, and actual
  filled quantities. Attribution is materialized only from backend-lineaged
  Paper fills as immutable cumulative fill-set snapshots; cumulative records
  are not summed.
- Forecast registration and settlement remain independent. A closed trade may
  be `NOT_DUE`; only the existing due settlement service and governed learning
  boundary may produce prediction/trading quality or a non-promotional
  research handoff.
- Focused validation passed: phase-6 strategy definitions `7/7`; strategy
  scanning/match `9/9`; baseline forecasts `5/5`; universal
  opportunity/bridge, clustering, comparison/allocation, and allocation
  persistence `31/31`; Paper execution governance `18/18`; runtime
  integration `11/11`; strategy attribution `12/12`; portfolio accounting
  `7/7`; outcome settlement `15/15`; and strategy learning `8/8`.
- `compileall -q src tests` passed. `git diff --check` passed with a
  non-failing CRLF normalization warning for the pre-existing
  `artifacts/shadow-run-1/P6_ACCEPTANCE_MATRIX.json`.
- The changed validation aggregate is not a green signal: `tools/validate.py
  changed` reported `1232 tests, 9 skipped, 1 failure, 91 errors in 530.542s`,
  with failures in `finviz`, `platform`, `intelligence`, `ui1`, and
  `validation`. These are preserved as dirty-baseline/global results, not
  attributed to the documentation-only Task 7 edits.
- `tools/validate.py full` reported `2209 tests, 9 skipped, 1 failure, 92
  errors in 734.902s`, with failures in `finviz`, `platform`, `intelligence`,
  `ui1`, `ui2`, and `validation`; global status remains
  `FOCUSED CLOSED / GLOBAL VALIDATION BLOCKED`.
- UI validation passed: `npm test -- --reporter=dot --maxWorkers=1` exited
  `0`, and `npm run build` transformed 1085 modules and passed the bundle
  budget at `201.18 KiB gzip` initial JS. Documentation links also passed:
  `check_docs_links.py` checked 134 governance markdown files.
