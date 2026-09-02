# IMP Equity Paper Profitability Loop

## Goal

Implement one deterministic, persisted U.S. equity-like Paper runtime loop
from `StrategyDefinition` through StrategyMatch, ForecastV1, canonical
opportunity economics, ranking/allocation, risk, Paper fills, authoritative
P&L, cumulative strategy attribution, later forecast outcomes, and governed
learning handoff.

## Phases

- [x] Phase 1: Add durable allocation decision contract, serialization, and
  IntelligenceRepository memory/Mongo persistence.
- [x] Phase 2: Add allocation-to-proposal lineage and prepared Paper
  execution seam while preserving existing authorities.
- [x] Phase 3: Add fill-set cumulative attribution materialization and
  authoritative accounting reconciliation.
- [x] Phase 4: Add strategy runtime orchestration, reconstruction, diagnostics,
  and asynchronous settlement/learning handoff.
- [x] Phase 5: Add end-to-end and failure-path tests, update validation/docs,
  and verify focused plus global suites.

## Current status

Implementation and focused validation are complete. Task 7 documentation and
handoff updates are complete. The global validation gates are blocked by the
pre-existing dirty-tree baseline; see the validation receipt below.

## Task 7 handoff

- **Status:** `FOCUSED CLOSED / GLOBAL VALIDATION BLOCKED`
- **Implemented path:** backend-only StrategyDefinition → StrategyMatch →
  ForecastV1 → canonical opportunity/economics → clustering/comparison →
  persisted allocation decision set → proposal/risk → Paper fills →
  authoritative account P&L → cumulative fill-set attribution → independent
  outcome settlement and governed learning handoff.
- **Authority result:** allocation, attribution, and runtime receipts remain
  sidecars/projections. StrategyMatch, ForecastV1, OpportunityV1,
  RiskDecisionV1, Paper ledger, portfolio accounting, settlement, and learning
  authorities remain distinct.
- **Focused suites:** pass — strategy/match `9`, baseline forecasts `5`,
  opportunity/cluster/comparison/allocation `31`, Paper execution `18`,
  runtime `11`, attribution `12`, accounting `7`, outcomes `15`, and learning
  `8`.
- **Compile/whitespace:** `python -m compileall -q src tests` passed.
  `git diff --check` passed with Git's non-failing CRLF normalization warning
  for the pre-existing `artifacts/shadow-run-1/P6_ACCEPTANCE_MATRIX.json`.
- **Global status:** `tools/validate.py changed` reported `1232 tests,
  9 skipped, 1 failure, 91 errors in 530.542s` across `finviz`, `platform`,
  `intelligence`, `ui1`, and `validation`. `tools/validate.py full` reported
  `2209 tests, 9 skipped, 1 failure, 92 errors in 734.902s` across `finviz`,
  `platform`, `intelligence`, `ui1`, `ui2`, and `validation`. Therefore the
  final status is `FOCUSED CLOSED / GLOBAL VALIDATION BLOCKED`.
- **UI status:** `npm test -- --reporter=dot --maxWorkers=1` passed with exit
  code `0` (Vitest completed all discovered UI tests); `npm run build` passed
  with 1085 modules transformed and the bundle-budget check reporting
  `201.18 KiB gzip` initial JS.
- **Safety:** no commit, push, deploy, reset, clean, or plan-file edit.

## Errors encountered

- Outer workspace directory is not the Git root; the repository is nested at
  `integrated-market-platform`.
- Broad suite discovery and direct-script invocation can fail on the existing
  namespace-style `tests.intelligence` imports; exact Task 7 selectors were
  run through the repository worker or with an in-memory namespace shim, with
  no test files changed.
- The aggregate `tools/validate.py changed` baseline remains non-green after
  the preceding phases: `1232 tests, 9 skipped, 1 failure, 91 errors`.
