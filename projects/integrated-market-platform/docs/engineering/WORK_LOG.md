# IMP Work Log

> **Donor-era entries: SUPERSEDED — HISTORICAL · AUTHORIZATION BASIS SUPERSEDED**
>
> Entries from the donor era (2026-08-14 through the correction) predate the
> professor's donor-identity correction (2026-08-28): Lucas Heller's DS-340W
> and GridIQ materials were **not** intended donor sources for this platform.
> Any native IMP implementation independently reimplemented from a legitimate
> platform requirement remains valid. Donor-era entries are preserved for
> provenance only and must not be used as authorization for future
> implementation.

Chronological record of implementation work on the Integrated Market Platform. Agents and contributors **must append an entry here automatically** after completing substantive changes — no user prompt required (see [AGENTS.md](../../AGENTS.md) and `.cursor/rules/work-logging.mdc`, `alwaysApply: true`).

## How to add an entry

Append a new section at the **top** of [Entries](#entries) (newest first). Use this template:

```markdown
## YYYY-MM-DD — Short title

| Field | Value |
|-------|-------|
| **Status** | `complete` \| `in-progress` \| `planned` |
| **Area** | e.g. `ui/now`, `ui/portfolio`, `ui/workspace`, `backend`, `docs` |
| **Summary** | 1–3 sentences: what changed and why |
| **Key files** | Bullet list of created/modified/deleted paths |
| **Tests** | What was run and result (e.g. `ui: vitest 177 passed`, `build: pass`) |
| **Related** | Links to plans, specs, or prior log entries |
| **Notes** | Optional: follow-ups, known limits, deferred items |
```

For large features, also add or update a completion note under `docs/superpowers/plans/` when a formal plan exists.

---

## Entries

## 2026-09-11 — FTEP-V1 owner decision packet and activation manifest skeleton

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `forward-test` |
| **Summary** | Created FTEP-V1 owner decision packet and `FTEP-V1-001` activation manifest skeleton per Agent A re-run audit (`c4f6ca28`). Manifest is `PENDING_OWNER_DECISIONS` with 3 minimal-path owner choices (OD-01, ACT-01, ACT-03) and 17 pre-resolved safe/deterministic fields; no FROZEN status or empirical claims. |
| **Key files** | `docs/engineering/FTEP-V1_OWNER_DECISION_PACKET.md` (created), `artifacts/forward-test-campaigns/FTEP-V1-001/ACTIVATION_MANIFEST.json` (created), `artifacts/forward-test-campaigns/FTEP-V1-001/PROTOCOL_REF.json` (created), `docs/engineering/FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md` (header), `docs/engineering/WORK_LOG.md` |
| **Tests** | None (docs/artifacts only) |
| **Related** | [FTEP-V1_OWNER_DECISION_PACKET.md](FTEP-V1_OWNER_DECISION_PACKET.md), Agent A audit `c4f6ca28`, [FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md](FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md) |
| **Notes** | Next: owner signs minimal packet → manifest `FROZEN` → operator preflight → first lock. Not pushed. |

## 2026-09-10 — PD-09 verifier persistence follow-up

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence`, `docs` |
| **Summary** | Addressed independent PD-09 verifier follow-up: extracted shared `assert_observations_append_only` helper for SQLite and in-memory stores, added restart persistence tests for observation tamper rejection and durable evaluation-claim blocking, and updated closure validation counts. |
| **Key files** | `paper_forward_bridge/repository.py`, `paper_forward_bridge/store.py`, `paper_forward_bridge/sqlite_repository.py`, `tests/intelligence/test_forward_test_persistence.py`, `docs/audits/paper-forward-testing-bridge/CLOSURE.json` |
| **Tests** | `python tools/imp.py test focused` — 11/11 persistence tests passed |
| **Related** | [paper-forward-testing-bridge CLOSURE](../audits/paper-forward-testing-bridge/CLOSURE.json), verifier `5cebba20` |
| **Notes** | Artifact JSON under `artifacts/` intentionally excluded from commit. |

## 2026-09-11 — FTEP-V1 forward-test experimental protocol freeze

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `forward-test` |
| **Summary** | Froze the first Paper forward-test experimental protocol (`FTEP-V1/0.1.0-PREREG`) before any empirical evidence run. Document is explicitly PLANNED / PRE-REGISTERED / NOT YET EMPIRICAL EVIDENCE; defines hypothesis, baseline/AI arms, universe/session/cadence rules, Paper execution semantics, metrics, leakage controls, disposition criteria (KEEP/REJECT/REPEAT/MODIFY/BLOCKED), and evidence-class gates. Unresolved choices marked OPEN DECISION — no results invented. |
| **Key files** | `docs/engineering/FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md` (created), `docs/engineering/WORK_LOG.md` |
| **Tests** | `tools/check_docs_links.py`: 172 governance markdown files checked, pass |
| **Related** | [FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md](FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md), [PAPER_FORWARD_TESTING_BRIDGE.md](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md), coordinator goal §14-A (Next A) |
| **Notes** | Next: resolve OPEN DECISIONs in activation manifest; campaign artifacts path planned under `artifacts/forward-test-campaigns/`. EVIDENCE-01B auto-bridge still unwired. |

## 2026-09-10 — PD-09 forward-test durable persistence

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence`, `local_state`, `docs` |
| **Summary** | Added account-scoped durable forward-test persistence via local SQLite (`local_state` schema v2): `ForwardTestRepository` protocol with in-memory and SQLite implementations, restart recovery for sessions/decisions/observations/evaluations, locked-decision immutability, append-only observations, and durable paper-submission/evaluation claims. Wired through `forward_test_projections` when `IMP_PERSIST_STATE=1`. |
| **Key files** | `paper_forward_bridge/repository.py`, `paper_forward_bridge/sqlite_repository.py`, `local_state/schema.py`, `local_state/migrations.py`, `local_state/startup.py`, `ui_api/forward_test_projections.py`, `tests/intelligence/test_forward_test_persistence.py`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md` |
| **Tests** | Persistence 9/9 passed; affected 1812 passed, 28 skipped (intelligence suite included) |
| **Related** | [PAPER_FORWARD_TESTING_BRIDGE.md](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md), [paper-forward-testing-bridge audit](../audits/paper-forward-testing-bridge/README.md) |
| **Notes** | Local SQLite only (no MongoDB). Route-policy UI mutation wiring deferred. Branch rebased onto `origin/main` @ `0ac5c03`. |

## 2026-09-10 — Governed Paper forward-testing bridge

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `intelligence`, `paper`, `ui`, `docs` |
| **Summary** | Implemented professor-directed Paper forward-testing bridge on reconciled P2+P7 base: forward-test sessions/decisions with lifecycle and anti-look-ahead guards, governed Paper handoff via `forward_test_decision` snapshots, account-scoped API, Paper Workspace UI panel, tests, architecture doc, and evidence package. |
| **Key files** | `src/market_platform_foundation/intelligence/paper_forward_bridge/**`, `ui_api/forward_test_projections.py`, `paper/decision_source.py`, `ui/.../PaperForwardTestPanel.tsx`, `tests/intelligence/test_paper_forward_bridge.py`, `docs/architecture/PAPER_FORWARD_TESTING_BRIDGE.md` |
| **Tests** | Forward-test 11 passed; UI model 2 passed; FAST 21/0/0; changed 2915/32/0; FULL 4539/49/0; closure docs/typecheck/build green after TS fixes |
| **Related** | [PAPER_FORWARD_TESTING_BRIDGE.md](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md), [evidence package](../audits/paper-forward-testing-bridge/README.md) |
| **Notes** | Remote `main` not pushed/merged. Notion SYNC_PAYLOAD_READY. In-memory store scope; EVIDENCE-01B auto-bridge deferred. |

## 2026-09-10 — Performance Engineering P7 continuous budgets & telemetry

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `developer-tooling`, `validation` |
| **Summary** | Established P7 observe-only performance budgets with canonical manifest, deterministic classification, validation receipt telemetry, `imp env` performance summary, CI telemetry summary, and P2 scheduler integration. Re-measured FAST/domain/FULL local baselines with repeated-run evidence for affordable paths. |
| **Key files** | `manifests/performance_budget.json`, `tools/performance_budget.py`, `tools/performance_telemetry.py`, `tools/perf_baseline_measure.py`, `tools/validate.py`, `tools/imp.py`, `.github/workflows/imp-python.yml`, `tests/validation/test_performance_budget.py`, `docs/audits/performance-engineering-p7/` |
| **Tests** | P7 contract 30 passed; P2 scheduler 13 passed; repository closure passed; FAST 21 passed; FULL 4522 passed (48 skipped) |
| **Related** | `docs/audits/performance-engineering-p7/P7_CLOSURE.json`, P2 `docs/audits/performance-engineering-p2/` |
| **Notes** | Gating remains OBSERVE_ONLY; CI baselines REMOTE_UNMEASURED; changed-validation baseline inherited from P2 at LOW confidence |

## 2026-09-10 — Source-control preservation and P3 lane isolation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `source-control`, `developer-operating-system` |
| **Summary** | Preserved validated professor-directed IMP work and P0 audit/control-plane changes in two logical local commits on `work/professor-paper-forward-testing`, fixed checkpoint `checkpoint/post-g15-professor-p0-2026-09-09` at `cd145fc`, and created isolated performance lane `perf/p3-validation-selector` in sibling worktree `market-trading-platform-perf-p3`. Remote `main` unchanged; no push/merge/PR. |
| **Key files** | Local branches: `work/professor-paper-forward-testing`, `checkpoint/post-g15-professor-p0-2026-09-09`, `perf/p3-validation-selector`; worktree `../market-trading-platform-perf-p3`; commits `48d64f8`, `cd145fc` |
| **Tests** | Pre-commit: FAST 21 passed; news 26 passed; intelligence inference 24 passed; strategy evaluation 19 passed. FULL 4456/48/0 reused (exact functional equivalence — no post-validation code edits). |
| **Related** | [DEVELOPER_OPERATING_SYSTEM.md](DEVELOPER_OPERATING_SYSTEM.md), [P0 forensic audit](../audits/performance-engineering-p0/P0_FORENSIC_AUDIT_2026-09-09.md) |
| **Notes** | NOTION_SYNC_BLOCKED. P3 not started. Primary next product increment remains governed Paper forward-testing bridge. |

## 2026-09-09 — Performance Engineering P0 forensic audit

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `developer-operating-system`, `performance` |
| **Summary** | P0 measurement-first audit of IMP developer OS, validation tiers, selector behavior, and assurance map. Delivered baseline JSON, optimization ledger, invariant/parallel maps, Notion lifecycle spec, and forensic report. Fixed stale `core_checkpoint_required` terminology and authoritative-docs link. No broad optimization; professor-directed dirty tree preserved. |
| **Key files** | `docs/audits/performance-engineering-p0/*`, `docs/engineering/DEVELOPER_OPERATING_SYSTEM.md`, `.cursor/rules/developer-workflow.mdc`, `.cursor/rules/authoritative-docs.mdc`, `.cursor/skills/imp-testing/SKILL.md`, `.cursor/agents/testing.md`, `artifacts/p0-performance-baseline.json` |
| **Tests** | `validate fast`: 21 passed, 3.447s; `benchmark.py --include-fast`: pass; focused news 0.39s; intelligence news 1.23s; vitest 71.9s |
| **Related** | [P0 forensic audit](../audits/performance-engineering-p0/P0_FORENSIC_AUDIT_2026-09-09.md), [NOTION_DEVELOPMENT_LIFECYCLE.md](../audits/performance-engineering-p0/NOTION_DEVELOPMENT_LIFECYCLE.md) |
| **Notes** | NOTION_CONTEXT_BLOCKED / NOTION_SYNC_BLOCKED. Next performance increment: P3 selector + artifacts evidence classification (BL-0801). Primary lane remains Paper forward-testing bridge. |

## 2026-09-09 — News strategy evaluation laboratory (professor-directed increment 3)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs`, `tests` |
| **Summary** | Implemented event-time-safe news intelligence strategy evaluation and Paper-shadow laboratory: feature snapshots, baseline vs AI-enhanced policies, realized outcome measurement, calibration metrics, deterministic replay, and non-executable shadow records. Initial lane ES futures with multi-asset fixture proof. No execution authority. |
| **Key files** | `src/market_platform_foundation/intelligence/news_strategy_evaluation/*`, `tests/intelligence/test_news_strategy_evaluation.py`, `tests/fixtures/news_strategy_evaluation/evaluation_replay_pack.json`, `tools/research/evaluate_news_intelligence.py`, `docs/architecture/NEWS_STRATEGY_EVALUATION.md`, `docs/architecture/adr/0012-news-strategy-evaluation-laboratory.md` |
| **Tests** | `unittest tests.intelligence.test_news_strategy_evaluation` 19 passed; news+intelligence foundation 45 passed |
| **Related** | [NEWS_STRATEGY_EVALUATION.md](../architecture/NEWS_STRATEGY_EVALUATION.md), [ADR-0012](../architecture/adr/0012-news-strategy-evaluation-laboratory.md) |
| **Notes** | Empirical path SOFTWARE_FIXTURE_ONLY; MES deferred; Claude live validation still blocked; Paper forward bridge deferred |

## 2026-09-09 — Canonical news AI intelligence boundary (post-G15 increment 2)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/intelligence/inference`, `docs` |
| **Summary** | Implemented analysis-only AI intelligence layer over curated deterministic news: `IntelligenceInputPacket`, governed `PromptRegistry`, provider-neutral `InferenceProvider` (`FixtureInferenceProvider`, `AnthropicInferenceProvider`), structured `IntelligenceResult`, replay-safe `InferenceRecord`, `NewsIntelligenceAnalyzer`, and `IntelligenceReplayHarness`. Zero broker/Paper/Live execution authority. |
| **Key files** | `src/market_platform_foundation/intelligence/inference/*`; `tests/intelligence/test_news_inference.py`; `docs/architecture/NEWS_AI_INTELLIGENCE.md`, `adr/0011-news-ai-intelligence-boundary.md` |
| **Tests** | `tests/intelligence/test_news_inference.py` — 24 passed; `tests/news` — 26 passed |
| **Related** | ADR-0011, [NEWS_AI_INTELLIGENCE.md](../architecture/NEWS_AI_INTELLIGENCE.md), ADR-0010 |
| **Notes** | INT-012 → PARTIALLY_INTEGRATED. `CLAUDE_LIVE_VALIDATION_NOT_RUN_EXTERNAL_CREDENTIAL_BLOCKER`. Durable inference persistence deferred. Next: Paper strategy evaluation over recorded intelligence. |

## 2026-09-09 — Canonical news/event deterministic foundation (post-CCN audit)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/news`, `docs` |
| **Summary** | Extended `market_platform_foundation/news/` with canonical `NewsArticleEvent` contract, separate publication/retrieval timestamps, source-trust catalog, catalyst registry, composable filter chain (recency → source → catalyst), deduplication, event-time-safe replay harness, fixture provider, and read-only `NewsIntelligenceService`. No AI or broker execution. Converges with existing aggregator rather than duplicating architecture. |
| **Key files** | `src/market_platform_foundation/news/contracts.py`, `timestamps.py`, `sources.py`, `catalysts.py`, `dedupe.py`, `normalize.py`, `filters/*`, `pipeline.py`, `replay.py`, `observability.py`, `fixture_provider.py`, `service.py`; `tests/news/test_news_foundation.py`, `test_news_event_time.py`; `tests/fixtures/news/canonical_replay_pack.json`; `docs/architecture/NEWS_EVENT_FOUNDATION.md`, `adr/0010-news-catalyst-deterministic-foundation.md` |
| **Tests** | `python -m unittest discover -s tests/news -q` — 26 passed |
| **Related** | [CCN_FORENSIC_AUDIT_2026-09-09.md](../audits/post-g15-professor-directed/CCN_FORENSIC_AUDIT_2026-09-09.md), ADR-0010 |
| **Notes** | INT-012 remains NOT_YET_INTEGRATED. Live wire providers (PR Newswire, Benzinga, etc.) deferred. Next increment: AI intelligence boundary over curated output. |

## 2026-09-09 — Post-G15 professor-directed CCN forensic audit

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `research`, `donors` |
| **Summary** | Completed forensic audit of authorized Future donor `Claude Code News/` (SRC-006): full artifact inventory, architecture reconstruction, event-time and AI analysis, performance evidence classification, security review, IMP comparison, reuse matrix, and proposed canonical integration architecture. Donor tree left unchanged (gitignored). No IMP runtime code copied. |
| **Key files** | `docs/audits/post-g15-professor-directed/README.md`, `docs/audits/post-g15-professor-directed/CCN_FORENSIC_AUDIT_2026-09-09.md`, `docs/audits/post-g15-professor-directed/CCN_ARTIFACT_INVENTORY.json` |
| **Tests** | `git rev-parse HEAD` (baseline match); `node --check` on 4 donor entrypoints (pass). IMP suite not run — documentation-only increment. |
| **Related** | [CCN forensic audit](../audits/post-g15-professor-directed/CCN_FORENSIC_AUDIT_2026-09-09.md); SRC-006 in [01-source-registry](../audits/imp-reconciliation/01-source-registry.md) |
| **Notes** | Runtime logs absent locally; README P&L claims PARTIALLY VERIFIED only. Next increment: canonical deterministic news/event ingestion foundation (Paper-only). |

## 2026-09-09 — G15 product acceptance (browser E2E, validation perf, archive-first deprecation)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `e2e`, `validation`, `ui_api`, `docs` |
| **Summary** | Playwright product-acceptance harness (equity/derivative Paper, isolation, routing, live safety); `validate e2e` gate; route-ref resolver for product APIs; dead-route census + deprecation headers; FULL **4392/48/0/0**. |
| **Key files** | `tools/e2e/harness.py`, `e2e/tests/*.spec.ts`, `tools/validate.py`, `ui_api/instrument_selector.py`, `artifacts/g15-validation-performance.json`, `docs/audits/imp-reconciliation/14m-g15-current-state-matrix.md` |

## 2026-09-09 — G14 Wave 7 product convergence (selector, query keys, Options/Futures surfaces)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/api`, `ui/options`, `ui/futures`, `ui_api`, `cross_lane`, `docs/audits` |
| **Summary** | Delivered canonical multi-asset instrument selector (`/instruments/search`), deterministic route codec, G14 Options/Futures product API surfaces backed by G12 runtime + G13 CanonicalPortfolio truth, frontend query-key factory with isolation tests, and product UI layers on Options/Futures workspace routes. Legacy whale research lanes preserved; Live execution remains blocked. |
| **Key files** | `ui_api/instrument_selector.py`, `ui_api/g14_product_projections.py`, `ui_api/instrument_route_codec.py`, `ui/src/api/queryKeyFactory.ts`, `ui/src/components/instrument-selector/CanonicalInstrumentSelector.tsx`, `ui/src/components/options/OptionsProductSurface.tsx`, `ui/src/components/futures/FuturesProductSurface.tsx`, `tests/cross_lane/test_g14_product_convergence.py`, `docs/audits/imp-reconciliation/14l-g14-current-state-matrix.md` |
| **Tests** | Backend G14: 11/11; frontend G14 focused: 16/16; FAST 21/0/0/0; CHANGED 3856/48/0/0; FULL **4391**/48/0/0 (+11); UI typecheck pass; build pass (202.87 KiB gzip) |
| **Related** | G13 baseline; `14l-g14-current-state-matrix.md`; RC-010/RC-011 partial closure |
| **Notes** | Legacy `queryKeys.workspace*` symbol keys retained for equity lanes; G14 product keys use factory. Selector mounted on Options/Futures modules (lazy). Full audit doc sweep deferred to follow-up commit. |

## 2026-09-09 — G14 closure validation pass (query-key wiring, preview panel, audit sweep)

| Field | Value |
|-------|-------|
| **Status** | `complete_with_explicit_exception` |
| **Area** | `ui/api`, `ui/options`, `ui/futures`, `ui/shared`, `docs/audits` |
| **Summary** | Second pass: wired compact G14 query keys in hooks + invalidation; integrated `DerivativePaperPreviewPanel` on product surfaces; restored global lazy selector on `InstrumentSelectionEmpty`; route encoding fixes; audit doc sweep (00/12/15/16/18). |
| **Key files** | `ui/src/api/hooks.ts`, `ui/src/api/canonicalQueryKey.ts`, `ui/src/components/paper-derivative/DerivativePaperPreviewPanel.tsx`, `ui/src/components/shared/InstrumentSelectionEmpty.tsx`, `docs/audits/imp-reconciliation/{00-program-state,12-master-backlog,15-validation-evidence,16-root-cause-register,18-completion-scorecard}.md` |
| **Tests** | Backend G14 **11/11**; CHANGED **3856/48/0/0**; FULL **4391/48/0/0**; UI typecheck pass; build **202.91 KiB gzip** |
| **Related** | `14l-g14-current-state-matrix.md`; RC-011 partial (product keys only) |
| **Notes** | Workspace lane query keys remain legacy for bundle/equity parity. Live execution blocked. |

## 2026-09-09 — G14 final closure (FULL green, route codec sweep)

| Field | Value |
|-------|-------|
| **Status** | `complete_with_explicit_exception` |
| **Area** | `ui/discover`, `ui/live`, `ui/paper-now`, `ui/workspace-module-shared`, `docs/platform` |
| **Summary** | FULL **4391/48/0/0** confirmed; extended `workspacePathForInstrument` to primary shell navigation (Discover, Live, Paper Now, lane shells); classified G14 **COMPLETE_WITH_EXPLICIT_EXCEPTION** (legacy lane query keys + whale research lanes retained). |
| **Key files** | `DiscoverObservability.tsx`, `LiveSymbolLookup.tsx`, `LiveObservationalPanel.tsx`, `PaperNowPage.tsx`, `WorkspaceModuleModeShell.tsx`, `LaneModeContextPanel.tsx`, `buildLaneModeContent.ts`, `PROGRAM_STATUS.md`, `00-program-state.md` |
| **Tests** | Backend G14 **11/11**; frontend G14 **24/24**; UI typecheck pass; build **202.92 KiB gzip** |
| **Related** | [14l-g14-current-state-matrix](../audits/imp-reconciliation/14l-g14-current-state-matrix.md) |
| **Notes** | RC-011 lane-key migration deferred (BL-0701). Live execution blocked. |

## 2026-09-09 — G13 closure validation (FULL green, Wave 7 readiness)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper`, `trading_correctness`, `docs/audits` |
| **Summary** | Closure pass: verified 25 G13 acceptance invariants against implementation; reran FAST/CHANGED/FULL and affected domain suites; reconciled test delta +25 (4355→4380); updated audit closure docs; classified margin authority (`MARGIN_INFRASTRUCTURE_COMPLETE` YES, `BROKER_MARGIN_MODEL_AVAILABLE` NO/LIMITED); decided **WAVE_7_READY**. |
| **Key files** | `docs/audits/imp-reconciliation/{00-program-state,14k-g13-current-state-matrix,15-validation-evidence}.md`, `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | G13 **25/0/0/0**; equity parity **7/0/0/0**; preview binding **10/0/0/0**; portfolio **136/0/0/0**; trading_correctness **147/0/0/0**; futures **65/0/0/0**; xa01 **72/0/0/0**; platform **474/2/0/0**; options domain **783/11/0/0**; FAST **21/0/0/0**; CHANGED **3845/48/0/0**; FULL **4380/48/0/0** |
| **Related** | [14k-g13-current-state-matrix](../audits/imp-reconciliation/14k-g13-current-state-matrix.md), [15-validation-evidence](../audits/imp-reconciliation/15-validation-evidence.md) G13 section |
| **Notes** | G14 not started. Performance artifact: `artifacts/g13-runtime-performance.json`. ES margin via `FixtureFuturesMarginProvider` — not live broker margin. |

## 2026-09-09 — G13 closure increment (futures lifecycle, margin preview binding)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper`, `trading_correctness`, `docs/audits` |
| **Summary** | Closed remaining G13 gaps: futures partial/replace/cancel lifecycle proven; `margin_facts_revision` bound into preview verify (`PREVIEW_MARGIN_STALE`); futures replace recheck uses margin facts not full notional; settlement-currency fail-closed tests for options/futures. |
| **Key files** | `paper/preview.py`, `paper/execution.py`, `tests/trading_correctness/test_g13_paper_derivatives.py`, `docs/audits/imp-reconciliation/14k-g13-current-state-matrix.md` |
| **Tests** | G13 focused **23/0/0/0**; CHANGED **3843/48/0/0**; FULL **4378/48/0/0** |
| **Related** | [14k-g13-current-state-matrix](../audits/imp-reconciliation/14k-g13-current-state-matrix.md) |
| **Notes** | UI `paper_projections` margin_facts wiring and performance evidence still deferred. Wave 7 NOT_READY. |

## 2026-09-09 — G13 canonical multi-asset Paper execution (options/futures)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `paper`, `portfolio`, `risk`, `trading_correctness`, `docs/audits` |
| **Summary** | Wired option and futures Paper fills through one canonical path (`portfolio/paper_fill.py` → `CanonicalPortfolio`) with explicit `MarginRequirementFacts` admission for futures (fail-closed without facts; no invented brokerage formulas). Option premium uses contracts×price×multiplier; futures debit margin not full notional. Legacy equity Paper ledger parity preserved; `options_ledger` remains non-authoritative. |
| **Key files** | `risk/margin_facts.py`, `portfolio/paper_fill.py`, `paper/ledger.py`, `paper/execution.py`, `risk/pretrade.py`, `tests/trading_correctness/test_g13_paper_derivatives.py`, `docs/audits/imp-reconciliation/14k-g13-current-state-matrix.md` |
| **Tests** | FAST 21/0/0/0; G13 focused 16/0/0/0; FINAL FULL **4371/48/0/0** (+16 from 4355); ibkr canary safety fixed (probe_loopback mock) |
| **Related** | [14k-g13-current-state-matrix](../audits/imp-reconciliation/14k-g13-current-state-matrix.md) |
| **Notes** | MARGIN_INFRASTRUCTURE_COMPLETE; BROKER_MARGIN_MODEL_UNAVAILABLE. Option partial/replace/cancel proven; futures replace/cancel deferred. Crypto secondary. Wave 7 NOT_READY. |

## 2026-09-09 — G12 post-IBKR multi-asset runtime completion

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `cross_lane`, `providers`, `docs/audits` |
| **Summary** | Closed G12 by isolating IBKR L2/TRADES entitlement limits from software backlog, correcting L1 delayed-vs-realtime capability wording, and adding one canonical multi-asset runtime projection path (`multi_asset_runtime.py`) over XA-01 identity, G7 observational lanes, G2/G4 valuation, and G3 fail-closed risk probes. Futures and options are first-priority runtime domains; crypto/bond/commodity semantics preserved. |
| **Key files** | `src/market_platform_foundation/cross_lane/runtime_status.py`, `cross_lane/multi_asset_runtime.py`, `tests/cross_lane/test_g12_multi_asset_runtime.py`, `tools/ibkr/canary.py`, `docs/audits/imp-reconciliation/14j-g12-current-state-matrix.md`, `g11-live-capability-evidence.json` |
| **Tests** | FAST 21/0/0/0; focused G12 25/0/0/0; CHANGED 3820/48/0/0; FULL **4355/48/0/0** (+25 from 4330) |
| **Related** | [14j-g12-current-state-matrix](../audits/imp-reconciliation/14j-g12-current-state-matrix.md), G11.1 live evidence |
| **Notes** | Frontend not touched; futures margin, crypto observational lane, bond execution, and Wave 7 instrument selector remain deferred. L2/TRADES are external entitlement limits only. |

## 2026-09-09 — G11.1 IBKR live Gateway verification and false-blocker correction

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `tools/ibkr`, `providers/live_evidence`, audits |
| **Summary** | Ran bounded read-only live canary against open loopback Gateway (`127.0.0.1:4001`); corrected conflation of `IMP_IBKR_LIVE` unset with `ENVIRONMENT_UNAVAILABLE`; added per-capability live evidence application to `RuntimeCapabilityRegistry`; verified contract/historical/account/L1 live; L2/TRADES `LIVE_CONNECTED_NOT_ENTITLED` (IBKR 10092/10189). Execution boundary unchanged. |
| **Key files** | `tools/ibkr/canary.py`, `src/.../providers/live_evidence.py`, `src/.../providers/runtime_capability.py`, `tests/providers/test_g111_live_evidence.py`, `tests/ibkr/test_g11_canary_safety.py`, `tests/ibkr/test_safety.py`, `docs/audits/imp-reconciliation/14i-g11-live-verification-matrix.md`, `g11-live-*-evidence.json` |
| **Tests** | G11.1 focused 7/0/0; starting FULL **4326/48/0/0**; final FULL **4330/48/0/0** (+4); CHANGED **3791/48/0/0** |
| **Related** | [14i-g11-live-verification-matrix.md](../audits/imp-reconciliation/14i-g11-live-verification-matrix.md) |
| **Notes** | Root cause: `SAFETY_GATE_STATE_MISCLASSIFIED_AS_PROVIDER_ENVIRONMENT_STATE`. Requires `ib_insync` in venv for live canary. L2 depth + tick-by-tick need IBKR market-data subscriptions. |

## 2026-09-09 — G11 IBKR read-only query surface convergence + verification harness

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers/ibkr_observational`, `market_data`, `tools/ibkr`, `tests`, `docs/audits` |
| **Summary** | G11 converged IBKR read-only query surfaces through injected outer provider boundary: `IbkrReadOnlyQueryProvider` protocol + `IbkrObservationalQueryService` (contract/secdef, historical bars, read-only account observation) with XA-01 admission, capability gating, capture/replay, and composition attach via `ibkr_query_bridge.py`. Outer `tools/ibkr/query_provider.py` adapts REST/TWS clients; registration via `runtime_bootstrap.py` only (G8 boundary fix removing foundation import from query_provider). Bounded live canary harness (`tools/ibkr/canary.py`) fail-closed. G10 depth TTL + G9 CVD preserved. LIVE_PROVIDER_UNVERIFIED retained. |
| **Key files** | `src/.../providers/ibkr_observational/query_provider.py`; `market_data/ibkr_query_bridge.py`, `runtime_composition.py`, `live_runtime.py`; `tools/ibkr/{query_provider,canary,runtime_bootstrap}.py`; `tests/**/test_g11_*.py`; `docs/audits/imp-reconciliation/14h-g11-current-state-matrix.md` |
| **Tests** | Starting FAST 21/0/0/0; starting FULL 4326/48/2/0 (boundary violation); focused G11 46/0/0/0; final FAST 21/0/0/0; CHANGED 3791/48/0/0; FULL 4326/48/0/0 |
| **Related** | G10 baseline; BL-0301 IMPLEMENTATION_COMPLETE/LIVE_VERIFICATION_PENDING; BL-0305 IMPLEMENTATION_COMPLETE/BLOCKED_BY_LIVE_EVIDENCE; `14h-g11-current-state-matrix.md` |
| **Notes** | No formula ledger bump. No execution enablement. Provider account facts remain READ_ONLY_OBSERVATIONAL. Live canary not executed in this environment. |

## 2026-09-08 — G10 IBKR provider convergence + depth TTL admission

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers/ibkr_observational`, `market_data`, `tests`, `docs/audits` |
| **Summary** | G10 converged canonical depth runtime admissibility (BL-0303) via `depth_admission.py`, wired DEPTH TTL into live admission and observational lanes (stale depth cannot yield authoritative OFI/book features), added read-only historical bar and account observation normalization contracts, registered IBKR_HISTORICAL_BARS/ACCOUNT_READ capabilities, hardened adapter/composition shutdown (idempotent, no reconnect after shutdown), and added 30 focused G10 tests. Live provider remains `LIVE_PROVIDER_UNVERIFIED`. |
| **Key files** | `src/.../market_data/depth_admission.py`; `live_admission.py`, `live_config.py`, `observational_lanes.py`, `observational_state.py`, `runtime_composition.py`; `providers/ibkr_observational/{historical_bars,account_observation,capability,adapter,diagnostics}.py`; `providers/runtime_capability.py`; `tests/**/test_g10_*.py`; `docs/audits/imp-reconciliation/14g-g10-current-state-matrix.md` |
| **Tests** | Starting FULL 4250/48/0/0; G10 focused 30/0/0/0; FAST 21/0/0/0 post-change |
| **Related** | G9 baseline; BL-0301/0303/0304/0305; `14g-g10-current-state-matrix.md` |
| **Notes** | BL-0301 still PARTIAL (REST historical/account fetch not live-wired). BL-0305 blocked by live evidence. No formula ledger bump (plumbing only). |

## 2026-09-08 — G9: IBKR tick-by-tick trade tape → CVD + entitlement readiness

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `providers/ibkr_observational`, `tools/ibkr`, `market_data`, `order_flow` |
| **Summary** | Added canonical IBKR tick-by-tick observational path (`IBKR_TRADES` / `subscribe_trades` → `TradePrintFacts` → Lee-Ready classification with L1 context → `apply_classified_trade` → G3 CVD). Extended outer transport with `req_tick_by_tick_data` / `tickByTickAllLast` bridge. Capture/replay TRADE kind, entitlement TRADES readiness, offline gate preserved. LIVE_PROVIDER_UNVERIFIED retained — no live canary run. BL-0304 closed for offline/replay path; BL-0305 partial/blocked by live evidence. |
| **Key files** | `providers/ibkr_observational/trades.py`, `adapter.py`, `contracts.py`, `capability.py`, `capture.py`, `tools/ibkr/observational_transport.py`, `market_data/observational_state.py`, G9 test modules, `docs/audits/imp-reconciliation/14f-g9-current-state-matrix.md` |
| **Tests** | Baseline FULL **4221/48/0/0**; focused G9 **29/0/0/0**; CHANGED **3715/48/0/0**; FULL **4250/48/0/0** (+29) |
| **Related** | [14f-g9-current-state-matrix](../audits/imp-reconciliation/14f-g9-current-state-matrix.md) |
| **Notes** | No native IB aggressor side claimed. Dedup limited to replay composite key. BL-0301/0303 remain PARTIAL. |

## 2026-09-08 — G8 closure correction: remove src→tools/ibkr inversion

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted) |
| **Area** | `tools/ibkr/runtime_bootstrap.py`, `market_data/{live_runtime,ibkr_runtime_bridge}.py`, G8 structural/performance tests, canonical G8 docs |
| **Summary** | Moved concrete `IbkrObservationalTransport` construction to outer `tools/ibkr/runtime_bootstrap.py`. Canonical `live_runtime` now accepts an injected transport or `IbkrObservationalTransportProvider`; it no longer imports `tools.ibkr`. Added AST boundary scan and four runtime-overhead measurements. Moomoo path unchanged. BL-0301/0304 PARTIAL; BL-0305 PARTIAL/BLOCKED_BY_LIVE_EVIDENCE; LIVE_PROVIDER_UNVERIFIED retained. G9 not started. |
| **Key files** | `tools/ibkr/runtime_bootstrap.py`, `src/.../market_data/live_runtime.py`, `ibkr_runtime_bridge.py`, `tools/ui1/run_ui_api.py`, `tests/market_data/test_g8_src_tools_boundary.py`, `tests/market_data/test_g8_runtime_performance.py`, `tests/ibkr/test_runtime_bootstrap.py`, `docs/audits/imp-reconciliation/14e-g8-current-state-matrix.md` |
| **Tests** | Focused G8 **74** OK; ibkr 63; providers 257; market_data 104; order_flow 148; xa01 72; trading_correctness 122; G5 82; G6 91; G7 39; FAST 21/0/0/0; CHANGED **3686/48/0/0**; FULL 4209/48/0 reused (+12 in CHANGED vs prior G8 3674) |
| **Related** | Prior G8 entry below; [14e-g8-current-state-matrix.md](../audits/imp-reconciliation/14e-g8-current-state-matrix.md) |
| **Notes** | Dynamic import of `tools.ibkr` from src is still inversion; correction uses protocol injection only. |

## 2026-09-08 — G7 closure evidence reconciliation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | audit docs / test-count accounting |
| **Summary** | Reconciled G7 closure test-count evidence: authoritative FULL/CHANGED delta is **+39** (4107→4146 FULL; 3572→3611 CHANGED). Prior informal per-file listing summed **41** because `test_g7_runtime_composition.py` was recorded as **11**; authoritative count is **9**. No G6→G7 test removals or weakening. Documented capability authority hierarchy: `ProviderRegistry` (metadata) → `RuntimeCapabilityRegistry` (runtime facade) + `VerifiedCapabilityRegistry` (Moomoo probe evidence only). |
| **Key files** | `docs/audits/imp-reconciliation/{15-validation-evidence.md,14d-g7-current-state-matrix.md,00-program-state.md}`, `docs/platform/{PROGRAM_STATUS.md,MASTER_ARCHITECTURE.md}` |
| **Tests** | G7 inventory verified via unittest discover on four `test_g7_*.py` modules: **39/0** (14+14+9+2). No FULL rerun required — existing **4146/48/0** evidence unchanged. |
| **Related** | G7 entry below; [14d-g7-current-state-matrix.md](../audits/imp-reconciliation/14d-g7-current-state-matrix.md) test inventory + capability hierarchy sections |
| **Notes** | Documentation-only reconciliation; no runtime or test semantics changed. G8 may proceed. |

## 2026-09-08 — G8 IBKR runtime convergence / live provider wiring

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted) |
| **Area** | `tools/ibkr/observational_transport.py`, `market_data/{live_runtime,ibkr_runtime_bridge,runtime_composition}.py`, `providers/ibkr_observational/contract_resolution.py`, G8 tests, `docs/audits/imp-reconciliation/14e-g8-current-state-matrix.md` |
| **Summary** | Converged G6 IBKR adapter + G7 runtime composition with outer TWS transport and `live_runtime.configure()` startup path. Added stdlib-only `IbkrObservationalTransport` callback bridge (operation 0 / side 0 preserved), src-side contract resolution + runtime bridge (no src→tools inversion), capability-state sync from adapter diagnostics, Moomoo path preserved. CVD remains explicit UNAVAILABLE from L1-only (no fabricated trades). LIVE_PROVIDER_UNVERIFIED retained (no live canary in closure environment). |
| **Key files** | See summary paths + `tests/ibkr/test_observational_transport.py`, `tests/providers/test_g8_*.py`, `tests/market_data/test_g8_*.py` |
| **Tests** | G8 focused **63** OK; CHANGED **3674/48/0** (+63 vs G7 3611); FAST 21/0/0 |
| **Related** | `docs/audits/imp-reconciliation/14e-g8-current-state-matrix.md` |
| **Notes** | BL-0301/0304/0305 PARTIAL — observational runtime wired offline; broader adapter scope, tick-by-tick CVD, and live entitlement canary remain open per backlog wording. |

## 2026-09-08 — G7 Runtime wiring / provider capability convergence

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | `providers/runtime_capability.py`, `providers/runtime_selection.py`, `market_data/{lane_requirements,observational_lanes,runtime_composition}.py`, `cross_lane/runtime_inputs.py`, G7 tests, docs/evidence |
| **Summary** | Converged provider capability truth and observational runtime wiring: multi-axis `RuntimeCapabilityRegistry` facade over `ProviderRegistry` + runtime state (implemented vs entitlement vs timeliness vs health; execution forbidden); deterministic fail-closed `ObservationalProviderSelector`; lane requirement graph; `ObservationalLaneRuntime` wiring canonical `ObservationalStateStore` → L1/CVD/price-aligned OFI/book-features/options/futures analytics with provenance; `ObservationalRuntimeComposition` transport-injection boundary (no src→tools/ibkr); cross-lane `runtime_inputs` bridge; 39 focused G7 tests; LIVE_PROVIDER_UNVERIFIED retained. |
| **Key files** | See summary paths + `tests/providers/test_g7_runtime_capability.py`, `tests/market_data/test_g7_{observational_lanes,runtime_composition}.py`, `tests/cross_lane/test_g7_runtime_inputs.py`, `docs/audits/imp-reconciliation/14d-g7-current-state-matrix.md` |
| **Tests** | G7 focused **39** OK (14+14+9+2 per-file); providers 232 OK; market_data 74 OK; trading_correctness 122 OK; FAST 21/0/0; CHANGED **3611/48/0**; FULL **4146/48/0** — zero failures |
| **Related** | `docs/audits/imp-reconciliation/{14d-g7-current-state-matrix.md, 15-validation-evidence.md G7 section, 00-program-state.md}`; G6 entry below |
| **Notes** | BL-0301 (broader IBKR adapter with account/secdef/bars) NOT closed — G7 is runtime convergence only. Performance: RUNTIME_PERFORMANCE_MEASURED (capability resolution smoke). Live provider LIVE_PROVIDER_UNVERIFIED. |

## 2026-09-08 — G6 IBKR observational L1/L2 provider adapter (BL-0213)

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | `providers/ibkr_observational/*` (new canonical runtime), `market_data/observational_state.py`, `tests/providers/test_ibkr_observational_*.py` (new), docs/evidence |
| **Summary** | Delivered the canonical provider-neutral IBKR observational adapter: IBKR callback facts → XA-01 identity → L1 quote accumulation and/or L2 `DepthUpdate` → `ObservationalStateStore` → G5 `IncrementalOrderBook`. Verified operation/side mapping (0=INSERT/1=UPDATE/2=DELETE; 0=ASK/1=BID); rank/position→price-keyed translation with price-changing UPDATE and rank-resolved DELETE; no fabricated depth sequence; subscription generation/reconnect/cancel/pacing; entitlement/delayed L1 truthfulness; evidence-backed error normalization; memory-only capture by default with deterministic replay through the adapter path; diagnostics/readiness; no execution capability; offline fail-closed; runtime `src` independent of `tools/ibkr` implementation. |
| **Key files** | `src/market_platform_foundation/providers/ibkr_observational/{adapter,capability,capture,constants,contracts,diagnostics,errors,identity,l1,lifecycle,mapping,pacing,rank,__init__}.py` (new), `src/market_platform_foundation/market_data/observational_state.py`, `tests/providers/test_ibkr_observational_{l1,l2,lifecycle,safety,capture_replay,performance}.py` (new), `tests/providers/ibkr_observational_support.py` (new) |
| **Tests** | ibkr_observational 91 OK, providers 216 OK, market_data 49 OK, order_book 87 OK, trading_correctness 122 OK; FAST 21/0/0; CHANGED **3572/48/0**; FULL **4107/48/0** — zero failures |
| **Related** | `docs/audits/imp-reconciliation/{12-master-backlog.md BL-0213, 14c-g6-current-state-matrix.md, 15-validation-evidence.md G6 section, 00-program-state.md}`; G5 entry below |
| **Notes** | Adapter throughput measured on dev machine (L1 ~33.9k/s, L2 normalize ~29.4k/s, L2→book ~18.6k/s) — ADAPTER_PERFORMANCE_MEASURED, not production IBKR. Live provider LIVE_PROVIDER_UNVERIFIED. G7 (runtime wiring / capability convergence) is next per mandate — not started. |

## 2026-09-08 — G5 canonical incremental L2 order-book engine (BL-0212)

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | `order_flow/order_book/*` (new canonical domain), `order_flow/{ofi,cvd,contracts,__init__}.py`, `market_data/observational_state.py`, `ui_api/live_projections.py`, `tests/order_flow/test_order_book_*.py` (new), `tests/market_data/test_canonical_book_integration.py` (new), docs |
| **Summary** | Built the one canonical provider-neutral incremental market-by-price book engine resolving AB-003/ARCH-003 (snapshot-only L2), ARCH-006 (rank-pair OFI mis-pairing) and ARCH-009 (hardcoded `book_state_valid: True`). New `order_flow/order_book/` package: `contracts.py` — provider-neutral `DepthUpdate` vocabulary (INSERT/UPDATE/DELETE/RESET × BID/ASK; instrument_id, price/size Decimal-exact via `Decimal(str(v))` boundary normalization, advisory position rank metadata, source/source_time_ns/received_time_ns, optional sequence, subscription identity, provider event id, schema version, provenance) + explicit `ApplyResult` contract (APPLIED/NOOP/DUPLICATE/REJECTED/INVALIDATED/RESET_APPLIED with reason, sequence_state, validity, generation, update_count); `engine.py` — `IncrementalOrderBook` with price-keyed side-ordered levels, explicit insert/update/delete/reset semantics (conflicting duplicate insert invalidates; update-of-missing fails closed; delete can never remove an unrelated rank; RESET is not DELETE — clears levels, advances generation, clears sequence continuity, marks RESET_PENDING), 5-state sequence machine (NO_SEQUENCE/BASE/CONTIGUOUS/DUPLICATE/GAP/REGRESSION — gap/regression fail closed INVALID with recovery required), subscription-generation gate rejecting late old-generation events, derived `book_state_valid`, deterministic `state_hash()`, no wall clock; `freshness.py` — pure `evaluate_book_freshness(book, as_of_time_ns, policy)` → FRESH/STALE/INVALID/UNAVAILABLE (thresholds in policy; INVALID beats STALE; stale never silently collapsed); `projection.py` — deterministic legacy snapshot dict projection with additive `book_status`/`book_status_reason`/`sequence_status`/`generation`/timestamps + `replace_from_snapshot`/`ingest_snapshot_dict` explicit compatibility ingestion (RESET-then-load, never blind UPDATE); `replay.py` — `replay(events)`/`replay_state_hash`/`measure_replay_throughput`, duplicates never double-apply, RESET/gap boundaries replay identically. Order-flow: `ofi.py` adds versioned price-aligned multi-level OFI (`compute_multilevel_ofi_price_aligned`) keyed by exact price — INSERT/DELETE rank shifts can no longer fabricate rank-paired events; legacy rank-sum v1 retained unchanged; formula_ledger entry `of.multilevel_ofi_price_aligned` (96→97). Store/API: `observational_state.py` keeps per-instrument canonical engines, full-book pushes enter via `replace_from_snapshot`, and stored book payloads + `ui_api/live_projections.py` expose derived `book_state_valid` + status/sequence/generation fields (ARCH-009 hardcoded True removed). CVD session authority untouched (BL-0208 anchor/reset metadata preserved with tests). |
| **Key files** | `src/market_platform_foundation/order_flow/order_book/{contracts,engine,freshness,projection,replay,__init__}.py` (new), `src/market_platform_foundation/order_flow/{ofi,cvd,contracts,__init__}.py`, `src/market_platform_foundation/market_data/observational_state.py`, `src/market_platform_foundation/ui_api/live_projections.py`, `tests/order_flow/test_order_book_{basic,operations,sequence,reset_generation,freshness,snapshot,replay,ofi_integration}.py` (new), `tests/market_data/test_canonical_book_integration.py` (new) |
| **Tests** | order_book 82 OK, canonical-book store integration 5 OK, order_flow 66 OK, trading_correctness 122 OK, CVD session 8 OK; FAST 21/0/0; CHANGED **3481/48/0**; FULL **4016/48/0** — zero failures |
| **Related** | `docs/audits/imp-reconciliation/{12-master-backlog.md BL-0212, 14b-g5-current-state-matrix.md, 15-validation-evidence.md G5 section, g5-order-book-replay-evidence.json}`; G4 entry below |
| **Notes** | Replay throughput measured on representative synthetic depth (10/50/100 levels): ~93k/45k/23k events/sec — PERFORMANCE_MEASURED, no production-throughput claim. IBKR `reqMktDepth` mapping is documented for G6 only; no runtime IBKR work here. G6 (IBKR observational L1/L2 provider adapter) is the next increment per current mandate — not started. |

---

## 2026-09-08 — G4 multi-asset accounting kernel (BL-0211)

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | `portfolio/*` (accounting kernel), `options/execution.py`, `risk/{financial,pretrade}.py`, `paper/*` gates, `tests/trading_correctness/*`, docs |
| **Summary** | Built the canonical multi-asset accounting foundation on the G3.1 baseline. New `portfolio/instrument_economics.py` is a fail-closed economics contract derived from XA-01 identity (quantity unit kind-driven; derivative multipliers explicit and positive; missing multiplier/currency/unknown kind fail closed; multiplier=1 only for equity/ETF). New `portfolio/accounting.py` centralizes exact-Decimal money/notional/P&L/reservation formulas and rejects binary float at the kernel boundary. The canonical portfolio mutation boundary now rejects derivative positions without CONTRACTS unit + positive multiplier. The independent float options ledger (`portfolio/options_ledger.py`) was rewritten Decimal-exact and marked NON-AUTHORITATIVE compatibility over the O9 simulation lane, with a canonical position adapter that aggregates same-identity partial fills (contract quantity truth, exact premium cost basis); `options/execution.py` converts to float only at the JSON presentation boundary (O9 goldens unchanged). Futures exactness (1/multi-contract, long/short sign, no drift, replay) is proven through the kernel + canonical valuation; family/continuous identities remain non-executable. Per-currency working obligations (`working_order_obligations_by_currency`, `currency_available_cash_minor`) and a per-currency financial gate + pretrade context (`currency_cash_minor`) make cash currency-aware; a missing currency bucket fails closed INSUFFICIENT_SETTLEMENT_CURRENCY — never 1:1. Also repaired the G3.1 precondition: three callers of the already-landed fail-closed `register_future_contract` supplied explicit multipliers, plus a spec-less-future fail-closed test. |
| **Key files** | `src/market_platform_foundation/portfolio/{accounting,instrument_economics,canonical,options_ledger}.py`, `src/market_platform_foundation/options/execution.py`, `src/market_platform_foundation/risk/{financial,pretrade}.py`, `src/market_platform_foundation/paper/{execution,broker_paper}.py`, `tests/portfolio/test_instrument_economics.py` (new), `tests/trading_correctness/test_multi_asset_accounting.py` (new), `tests/xa01/test_xa01_derivatives.py` (+2), 3 precondition-test fixes |
| **Tests** | portfolio 136 OK, trading_correctness 122 OK, options 147 OK, platform 474 OK (2 skipped), ui1 13 OK, ui2 5 OK, xa01 72 OK; FAST 21/0/0; CHANGED **3347/48/0**; FULL **3929/48/0** — zero failures |
| **Related** | `docs/audits/imp-reconciliation/{12-master-backlog.md BL-0211, 14a-g4-current-state-matrix.md, 15-validation-evidence.md G4 section}`; G2 portfolio spec; G3.1 entry below |
| **Notes** | Options execution lane stays a non-authoritative simulation projection over the same fills (removal condition documented in the module). Futures gate still fails closed UNSUPPORTED_RISK_MODEL — no margin model invented. Auto-FX settlement and futures margin methodology remain explicit product decisions for later increments. |

---

## 2026-09-08 — G3.1 cross_lane golden-blocker reconciliation (BL-0210)

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | `cross_lane/fusion.py`, `tests/cross_lane/*`, docs |
| **Summary** | Closed the last known FULL failure — the pre-existing dirty-tree `cross_lane` golden. Hardened `_occurrence_weight` in `fuse_opportunity_v1` so a squeeze-aligned template with no hazard and no occurrence model output fails closed to UNAVAILABLE (`OCCURRENCE_UNAVAILABLE`) instead of silently weighting 1.0; non-squeeze-aligned paths carry an explicit `OCCURRENCE_UNAVAILABLE` quality flag with factor 1.0; named `PAYOFF_ALREADY_NET_TOLERANCE`; bumped formula_ledger + SHARED_P4_EV_OPPORTUNITY_SPEC to fusion v2; regenerated the golden fixture with hash forensics (`.local/g31-hash-forensics.py`) proving the V1→V2 snapshot delta is the intended semantic change. |
| **Key files** | `src/market_platform_foundation/cross_lane/{fusion,opportunity,portfolio}.py`, `tests/cross_lane/test_{opportunity_fusion,portfolio_p5}.py`, `tests/fixtures/providers/opportunity/nvda_opportunity_fusion_expected.json`, `docs/research/{formula_ledger.json,SHARED_P4_EV_OPPORTUNITY_SPEC.md}` |
| **Tests** | tests/cross_lane +9 (6 opportunity-fusion, 3 portfolio-p5); FAST 21 passed; CHANGED 3233/48/0; FULL **3870/48/0** — zero failures, no excluded baseline remains |
| **Related** | `docs/audits/imp-reconciliation/15-validation-evidence.md` (G3.1 section); backlog BL-0210; G3 entry (2026-09-07) |
| **Notes** | No production gate weakened; research-lane honesty only. G4 (multi-asset accounting kernel) is the next structural increment per current mandate. |

---

## 2026-09-07 — G3 trading-correctness increment (BL-0201..BL-0209)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `risk`, `tests`, `docs` |
| **Summary** | Finished the G3 trading-correctness increment on the working tree: BL-0201 server preview binding + strategy prepared-decision authority (server-side PreviewStore with fail-closed verify; prepared idempotency-key binding; prepared risk-reference-price handoff into the final financial recheck), BL-0202 internal + broker-paper cash gates (fail-closed REQUIRED_PRICE_MISSING, conservative bar/live-mark reference, trusted strategy reference price that cannot bypass insufficient cash, currency from canonical metadata, partial-fill/replace reservation recompute), BL-0203 canonical identity admission with closed arbitrary-equity fallback (BIYA/AAPL fixtures canonical), BL-0204 working-remainder projection corrections, BL-0205 replace lifecycle with persisted replace_revision + idempotent retries, BL-0206 cancel-time late-fill reconciliation, BL-0207 per-ledger RLock atomic idempotency+creation boundary (release before broker network call) with thread-barrier proofs, BL-0208 deterministic CVD session semantics, BL-0209 typed `evaluate_pretrade` wired into both executable BUY gates. Completed the last pending change (threading the approved risk-decision reference price through `_submit_prepared`) and added 4 dedicated regression tests (no-bars prepared submit succeeds via risk reference price; no bars + no reference fails closed; reference price cannot bypass insufficient cash; prepared quantity/reference price server-authoritative). |
| **Key files** | Modified: `src/market_platform_foundation/paper/{execution,broker_paper,ledger,contracts,preview}.py`, `src/market_platform_foundation/risk/{pretrade,financial}.py`, `src/market_platform_foundation/intelligence/execution/engine.py`, `src/market_platform_foundation/order_flow/cvd.py`, `src/market_platform_foundation/ui_api/{server,store,paper_projections}.py`, `src/market_platform_foundation/xa01/*`, `tests/trading_correctness/` (10 suites), platform broker fixtures (live marks, CancelDispatch `events=()`, E5 preview-first submit), `tools/validation_manifest.{json,py}`, `tests/validation/test_validation_manifest.py` (offline count 62); workspace evidence: `docs/audits/imp-reconciliation/{12-master-backlog,15-validation-evidence}.md`, `docs/platform/PROGRAM_STATUS.md` |
| **Tests** | `tests/trading_correctness` 91 passed (87 baseline + 4 new); governed intelligence flow green with `bars=[]`; platform broker P4/P44/P4C/reconciliation/status-apply 93 passed; operator surface fixes 16 passed; validation suite 82 passed; FAST **21 passed**; CHANGED **3224 tests, 1 failure** (known pre-existing cross_lane golden baseline only); FULL **3861 tests, 1 failure** (same baseline). |
| **Related** | [15-validation-evidence G3 section](../audits/imp-reconciliation/15-validation-evidence.md); [master backlog BL-0201..BL-0209](../audits/imp-reconciliation/12-master-backlog.md); G2 entry below |
| **Notes** | Production gates never weakened: broker test fixtures now supply live marks (UI-path parity), CancelDispatch fake returns an empty `events` stream, and the E5 parallel test uses preview-first submit with PREVIEW_PORTFOLIO_STALE refresh-retry (never bypasses preview authority, still genuinely concurrent). Cross_lane golden failure is unrelated pre-existing dirty work (occurrence-weight hardening), not caused by G3. |

## 2026-09-06 — Q-H3-usage: stamp q_method on O3 and BL

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Stamp `q_method` on log-normal O3 (`log_normal_moment_approx`) and discrete BL (`breeden_litzenberger`) payloads so P−Q consumers can see which Q they compared. Default `infer_risk_neutral_distribution` is unchanged. `donor_bridge/projections` and `providers/projections` still call log-normal O3 (no auto-BL). No trade authority. |
| **Key files** | Modified: `src/market_platform_foundation/options/risk_neutral.py`, `src/market_platform_foundation/options/breeden_litzenberger.py`, `tests/options/test_options_o3.py`, `tests/options/test_options_o3_bl.py`, `tests/formulas/test_heuristic_pin_drift.py`, `docs/research/formula_ledger.json`, `docs/research/FORMULA_LEDGER.md`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md` |
| **Tests** | Python 3.13. `pytest tests/options/test_options_o3.py tests/options/test_options_o3_bl.py tests/formulas/test_heuristic_pin_drift.py tests/formulas/test_formula_goldens.py tests/options/test_options_o4.py`: 41 passed. `imp.py validate domain options`: 583 passed, 11 skipped, 0 failures, 0 errors. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-H3-usage; Q-H3 PR |
| **Notes** | G1–G6 stay closed. Not a default Q switch. |

## 2026-09-06 — Q-H1-futures-rate: unused carry r and DTE fallback

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Spot carry is `ln(F/S)/days×365` and does not use `r`. Dropped silent `risk_free_rate=0.05` and stopped stamping unused r in assumptions. Missing observation date fail-closes (no `"2025-01-01"` DTE fallback). Does not reopen Q-H1 calibration; `CARRY_SCALE=0.05` stays an unfitted tanh pin. Canonical trees only. |
| **Key files** | Modified: `src/market_platform_foundation/futures/carry.py`, `tests/futures/test_f3_basis_carry.py`, `tests/formulas/test_heuristic_pin_drift.py`, `docs/research/formula_ledger.json`, `docs/research/FORMULA_LEDGER.md`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md` |
| **Tests** | Python 3.13. `pytest tests/futures/test_f3_basis_carry.py tests/futures/test_baselines_engine.py tests/formulas/test_heuristic_pin_drift.py`: 26 passed. `imp.py validate domain futures`: 526 passed, 11 skipped, 0 failures, 0 errors. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-H1-futures-rate; Q-H3 PR |
| **Notes** | G1–G6 stay closed. No fusion/GARCH/HAR/ADAM/logistic calibration. |

## 2026-09-06 — Q-H3: discrete Breeden–Litzenberger Q (additive)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Closed Q-H3 with an additive fail-closed discrete Breeden–Litzenberger path (`infer_risk_neutral_breeden_litzenberger`, `risk_neutral_breeden_litzenberger_v1`) on the IV-reconstructed call curve. Default O3 stays `risk_neutral_log_normal_moment_approx_v1`; no average-IV log-normal fallback; no silent `rate=0.05`. Ledger 88→89 (`options.risk_neutral_q_bl`, `research_baseline`). `donor_bridge/projections` and `providers/projections` still call `infer_risk_neutral_distribution`. G1–G6 stay closed; no trade authority. |
| **Key files** | Created: `src/market_platform_foundation/options/breeden_litzenberger.py`, `tests/options/test_options_o3_bl.py`. Modified: `src/market_platform_foundation/options/risk_neutral.py`, `options/__init__.py`, `tests/formulas/test_heuristic_pin_drift.py`, `docs/research/formula_ledger.json`, `docs/research/FORMULA_LEDGER.md`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md`, `docs/reviews/2026-09-05-formula-correctness-review.md` |
| **Tests** | Python 3.13. Scoped pytest (`test_options_o3.py`, `test_options_o3_bl.py`, `test_heuristic_pin_drift.py`, `test_formula_goldens.py`): 35 passed. `imp.py validate domain options`: 581 passed, 11 skipped, 0 failures. `imp.py validate full`: 3575 passed, 48 skipped, 0 failures, 0 errors. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-H3; [formula correctness review](../../../../docs/reviews/2026-09-05-formula-correctness-review.md) |
| **Notes** | Q-H1 remains open (unfitted scalars). Q-H4 / `SUPPORTED` stay closed. 2-strike O3 fixtures fail BL (`BL_INSUFFICIENT_STRIKES`). Do not treat discrete BL as a trade signal. |

## 2026-09-06 — Pin-drift ADAM import uses canonical squeeze tree

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend` |
| **Summary** | `test_heuristic_pin_drift` imported ADAM from a repo-root `short-squeeze-project` path. CI sparse-checks that location without `apps/`, so `validate changed` collected an ImportError after PR #12. Point the test at `projects/short-squeeze-project` like donor-bridge tests. |
| **Key files** | Modified: `tests/formulas/test_heuristic_pin_drift.py` |
| **Tests** | Python 3.13. `pytest tests/formulas/test_heuristic_pin_drift.py`: 7 passed. |
| **Related** | [PR #12](https://github.com/AdamEddahmouni/market-trading-platform/pull/12) |
| **Notes** | Fast IMP Validation passed on #12; only `validate-python-changed` failed. G1–G6 stay closed. |

## 2026-09-05 — Q-H1-O10-rate: O10 / R-O6 fail-closed rate

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Closed Q-H1-O10-rate: `delta_hedged_research_snapshot` and `compose_r_o6_research_snapshot` no longer default `rate=0.05`. Missing positive rate (explicit kwarg, else P/Q dict) fail-closes with `RATE_ASSUMPTION_MISSING`. Successful O10 snapshots stamp resolved `rate`. Versions `delta_hedged_research_v2` / `r_o6_research_v2`. Ledger 86→88 with `options.delta_hedged` and `options.r_o6`. Q-H1 stays open for unfitted fusion/GARCH/HAR/ADAM/logistic only. G1–G6 stay closed; no trade authority. |
| **Key files** | Modified: `src/market_platform_foundation/options/delta_hedged.py`, `r_o6.py`, `tests/options/test_options_o10.py`, `tests/formulas/test_heuristic_pin_drift.py`, `docs/research/FORMULA_LEDGER.md`, `docs/research/formula_ledger.json`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md`, `docs/reviews/2026-09-05-formula-correctness-review.md` |
| **Tests** | Python 3.13. Scoped pytest: 52 passed. `imp.py validate domain options`: 575 passed, 11 skipped, 0 failures. `imp.py validate full`: 3569 passed, 48 skipped, 0 failures, 0 errors (after classifying `src/market_platform_foundation/lanes` in the repository-closure audit). |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-H1 / Q-H1-O10-rate; [formula correctness review](../../../../docs/reviews/2026-09-05-formula-correctness-review.md) |
| **Notes** | Q-H1 remains open (unfitted scalars). O10/R-O6 no longer pin 0.05. Do not treat delta-hedged path or R-O6 correlation as a trade signal. |

## 2026-09-05 — Q-H1-rate close + P1-3 / P1-6 / P2-1 / P2-2 docs-verify

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Closed Q-H1-rate (dealer/O2/O3 no silent `rate=0.05`) leftover: O10 inline chain and cross-lane dealer inline rows stamp tape `rate` 0.04; option-chain builder and activity envelopes copy tape `rate` onto contract dicts so workspace dealer snapshots still build. Closed P1-3, P1-6, P2-1, P2-2 in the hardening plan. Q-H1 stays open for unfitted fusion/GARCH/HAR/ADAM/logistic only. G1–G6 stay closed; no trade authority. |
| **Key files** | Modified: `tests/options/test_options_o10_surface_baseline.py`, `src/market_platform_foundation/providers/adapters/option_contract_builder.py`, `fixture_options.py`, `tests/donor_bridge/test_cross_lane_adapter.py`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md`, `docs/reviews/2026-09-05-formula-correctness-review.md` |
| **Tests** | Python 3.13. Scoped pytest (O2/O3/O5/O6/O10 + goldens + pin-drift + acquisition guard + broker wiring + paper trace): 77 passed. `imp.py validate domain options`: 561 passed, 11 skipped, 0 failures. Full `validate full` not run. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-H1 / Q-H1-rate / P1-3 / P1-6 / P2-1 / P2-2; [formula correctness review](../../../../docs/reviews/2026-09-05-formula-correctness-review.md) |
| **Notes** | Q-H1 remains open (unfitted scalars). Q-H1-rate is closed. Dealer/O2/O3 0.05 leftover is not a Q-H1 pin. Do not treat dealer gamma or surface IV as a trade signal. |

## 2026-09-05 — Q-H1 pin + O5 vol/rate fail-closed + O2 strict underlying

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Named unfitted Q-H1 fusion/GARCH/HAR/logistic constants and added a ledger drift golden (ADAM weights assert-only; no calibration). O5 greeks fail closed without positive vol and rate (`options_signed_flow_v3`). O2 no longer uses strike×1.02/0.98; surface points are skipped and stamped with `underlying_price` (`sigma_kt_v2`); O3/dealer/strategy/event_vol share that fail-closed infer. G1–G6 stay closed; Q-H1 remains open for calibration; no trade authority. |
| **Key files** | Modified: `src/market_platform_foundation/options/{flow,surface,risk_neutral,dealer,strategy,event_vol,edge}.py`, `cross_lane/fusion.py`, `research/distribution/{garch,har_rv}.py`, `research/squeeze_models/logistic_hazard.py`, options O2/O3/O5 tests + goldens, signed-flow fixture, `docs/research/FORMULA_LEDGER.md`, `docs/research/formula_ledger.json`; created: `tests/formulas/test_heuristic_pin_drift.py`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md`, `docs/reviews/2026-09-05-formula-correctness-review.md` |
| **Tests** | Python 3.13. `pytest tests/options/test_options_o{2,3,5,6}.py tests/formulas/test_formula_goldens.py tests/formulas/test_heuristic_pin_drift.py`: 48 passed. Extra O7/O8: 21 passed (69 combined). `imp.py validate domain options`: 565 passed, 11 skipped. Full `validate full` not run. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-H1 / Q-H1-O5 / O2; [formula correctness review](../../../../docs/reviews/2026-09-05-formula-correctness-review.md) |
| **Notes** | Dealer `DEFAULT_RATE=0.05` and O3/O2 IV `rate=0.05` remain Q-H1 pins. Do not treat signed flow or surface IV as a trade signal. |

## 2026-09-05 — Q-H2: O5 signed-flow fail-closed without underlying spot

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Options O5 greeks-equivalent signed flow no longer defaults spot to 100.0. Spot is explicit or inferred from `underlying_price` (same strict helper as Q7 friction). Missing spot leaves volume/direction intact and sets greeks to `None` with `UNDERLYING_PRICE_ASSUMPTION_MISSING`. `DEFAULT_VOL`/`DEFAULT_RATE` remain unfitted. G1–G6 stay closed; no trade authority. |
| **Key files** | Modified: `src/market_platform_foundation/options/flow.py`, `src/market_platform_foundation/options/edge.py`, `tests/options/test_options_o5.py`, `tests/formulas/test_formula_goldens.py`, `tests/fixtures/providers/options/nvda_signed_flow_slice.json`, `docs/research/FORMULA_LEDGER.md`, `docs/research/formula_ledger.json`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md`, `docs/reviews/2026-09-05-formula-correctness-review.md` |
| **Tests** | Python 3.13. `pytest tests/options/test_options_o5.py tests/formulas/test_formula_goldens.py`: 21 passed. `imp.py validate domain options`: 550 passed, 11 skipped. Full `validate full` not run. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-H2; [formula correctness review](../../../../docs/reviews/2026-09-05-formula-correctness-review.md) |
| **Notes** | Surface O2 `strike * 1.02/0.98` fallback was not changed. Do not treat signed flow as a trade signal. |

## 2026-09-05 — Phase 4: formula correctness verification and reporting

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `docs` |
| **Summary** | Verified Phase 1–3 formula and path work; aligned the 86-row formula ledger so Q is `risk_neutral_log_normal_moment_approx_v1` and options friction has no silent 100.0 underlying. Registered `tests/formulas` in the validation manifest (was unclassified and blocked `validate.py`). Wrote Q-series notes and a correctness review. G1–G6 remain closed; no LIVE-001, shadow, canary, or broker wires; no `SUPPORTED` claim. |
| **Key files** | Modified: `docs/research/FORMULA_LEDGER.md`, `docs/research/formula_ledger.json`, `tools/validation_manifest.json`, `tests/validation/test_validation_manifest.py`; workspace: `docs/reviews/2026-09-04-hardening-task-plan.md`, `docs/reviews/2026-09-05-formula-correctness-review.md` |
| **Tests** | Python 3.13. Targeted pytest 63 passed; broader campaign slice 1881 passed / 27 skipped; `imp.py validate domain options` 545 passed / 11 skipped; `domain order-flow` 525 passed / 11 skipped; squeeze metric/ADAM 49 passed; UI `laneRegistry.test.ts` 9 passed. Monorepo `validate changed` only 21 mandatory tests (path-prefix under-select). Full `validate full` not run. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) Q-series, P1-2, P1-4, P1-5, P2-4; [formula correctness review](../../../../docs/reviews/2026-09-05-formula-correctness-review.md) |
| **Notes** | O5 signed-flow still pins `DEFAULT_SPOT=100.0` when spot is omitted; that is not the friction path. Heuristic GARCH/HAR/fusion/ADAM/logistic weights remain unfitted. |

## 2026-09-05 — P1-2 / P1-4 / P1-5 / P2-4: lane and engine path invariants

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `ui`, `docs` |
| **Summary** | Canonical opportunity mint is StrategyMatch → `bridge.py` → OpportunityEngine; older constructions are deprecated and two paths conflict on persist. One tested discovery/workspace/`LaneId` map; `MARKET_CONTEXT` routes to workspace `catalyst` (not `order-book`). Execution-intent runtimes that omit `strategy_eligibility` fail closed; research-only scanners do not construct OrderReadyV1. Unadmitted captures and donor execution entry points cannot reach training, promotion, or OrderReady. LIVE/paper campaign gates remain closed. |
| **Key files** | Created: `src/market_platform_foundation/lanes/vocabulary.py`, `src/market_platform_foundation/intelligence/dataset_admission.py`, `tests/platform/test_lane_vocabulary.py`, `tests/platform/test_unadmitted_and_donor_isolation.py`; modified: opportunity engine/bridge/P4/economic sidecar, `strategy/runtime.py`, `strategy/eligibility.py`, `strategy/scanning.py`, training factory, promotion engine, `PAPER_DECISION_LIFECYCLE.md`, `paperDecisionSemantics.ts`, `laneRegistry.test.ts` |
| **Tests** | Targeted pytest: 41 passed (`test_universal_opportunity.py`, `test_equity_paper_runtime.py`, `test_lane_vocabulary.py`, `test_unadmitted_and_donor_isolation.py`). UI vitest: `laneRegistry.test.ts` 9 passed. Full `validate.py` not run. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) P1-2, P1-4, P1-5, P2-4 |
| **Notes** | Did not open LIVE-001, P6 Shadow Run 1, or paper campaign gates. Full `validate.py` not run (targeted only). |

## 2026-09-05 — Monorepo embedding: provenance root resolution (release/qualification gates)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend` |
| **Summary** | When the platform tree is embedded in the parent monorepo (`projects/integrated-market-platform`), git-root resolution climbed to the monorepo root, so release/qualification provenance could not find `phase0-dependency-lock.json` or `artifacts/system-acceptance/*` and ~30 change-control / release-governance / forward-qualification tests errored. `git_ref.repo_root()` and `deployment/source_provenance.get_repository_root()` now prefer the platform-tree root (marker-bounded by `phase0-dependency-lock.json`, never above the git root) when resolved from inside the platform package; in the platform's own repository the anchor is exactly the git root, so behavior is unchanged. First platform-source PR to run `imp.py validate changed` surfaced this. |
| **Key files** | Modified: `src/market_platform_foundation/git_ref.py`, `src/market_platform_foundation/intelligence/live_canary/deployment/source_provenance.py` |
| **Tests** | `imp.py validate changed`: 1691 tests, 27 skipped, 0 failures, 0 errors; change-control/release-governance/forward-qualification/paper-execution-qualification files: 130 passed |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) |

## 2026-09-05 — P0-4: attribution parity enforced as a fail-closed invariant

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend` |
| **Summary** | `portfolio/attribution_materializer.py` now enforces attribution parity with the authoritative fill-driven ledger: before persisting, a recomputation is compared against every already-persisted attribution for the same allocation. Any fill it already covers that changed accounting, or any coverage regression, records an immutable `ATTRIBUTION_PARITY_VIOLATION` event (`EventV1`, deterministic `ATTR-PARITY-*` id) and raises `AttributionMaterializationError` — the divergence is never silently absorbed. Identical recomputations (dedup path) and legitimate CUMULATIVE coverage growth (later fills appended) remain silent. |
| **Key files** | Modified: `src/market_platform_foundation/portfolio/attribution_materializer.py`; created/extended tests: `tests/platform/test_strategy_attribution.py` (parity fake repo + `AttributionParityInvariantTests`) |
| **Tests** | `tests/platform`: 14 passed, 3 subtests; combined platform/intelligence run 518 passed, 2 skipped |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) P0-4; [PAPER_DECISION_LIFECYCLE.md](../architecture/PAPER_DECISION_LIFECYCLE.md) |

## 2026-09-05 — P1-1: explicit strategy eligibility gate before OrderReadyV1 execution intent

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend` |
| **Summary** | Added the single checkable predicate — preregistered (identity match on the order path) + promotion state (ACTIVE champion reached through the promotion engine, carrying a promotion decision) + forward-evidence class (evidence tier that reflects post-registration observation) — in `strategy/eligibility.py`. `StrategyPaperRuntime` enforces it on the order-ready path when an execution-eligibility configuration is supplied: unknown/unpromoted strategies cannot reach execution intent — the persisted OrderReadyV1 is stamped BLOCKED with `STRATEGY_EXECUTION_ELIGIBILITY_BLOCKED` plus a `strategy_eligibility` lineage ref to the deterministic record, no paper mutation occurs, and a `STRATEGY_BLOCKED` result is returned. Research/paper runtimes without the configuration keep today's behavior; campaign wiring that claims execution intent must supply it (fail closed by construction). |
| **Key files** | Created: `src/market_platform_foundation/strategy/eligibility.py`; modified: `src/market_platform_foundation/strategy/runtime.py`, `tests/intelligence/test_equity_paper_runtime.py` (`StrategyExecutionEligibilityGateTests`) |
| **Tests** | `StrategyExecutionEligibilityGateTests`: 4 passed; runtime + learning regression 26 passed |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) P1-1 |

## 2026-09-05 — P0-2: promotion dry-run harness (champion/challenger machinery proof)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend` |
| **Summary** | Fixture-driven promotion dry run (`intelligence/promotion/dry_run.py`) that replays recorded shadow observations through the promotion engine and emits an immutable `PROMOTED` / `NOT_PROMOTED` / `INVALID` decision record referencing the exact preregistration + evidence manifest — proving the ladder end-to-end without claiming an edge or granting execution authority (P1-1's eligibility gate is what separates a dry run from a real promotion). |
| **Key files** | Created: `src/market_platform_foundation/intelligence/promotion/dry_run.py`, `tests/intelligence/test_promotion_dry_run.py` |
| **Tests** | `test_promotion_dry_run.py`: 6 passed |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) P0-2; [CHAMPION_CHALLENGER_PROMOTION_V1.md](CHAMPION_CHALLENGER_PROMOTION_V1.md) |

## 2026-09-05 — P0-1 / P2-3 / P2-5: readiness checklist and lane-docs hygiene

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Added the one-page forward-validation readiness checklist (`docs/engineering/FORWARD_VALIDATION_READINESS_CHECKLIST.md`) listing per-campaign blockers and required acceptance artifacts to reopen P6 Shadow Run 1, EVIDENCE-01C, the live canary, Tradier sandbox, and Moomoo OpenD; superseded headers on the three lane-reconciliation roadmaps plus README pointer fix; per-lane doctrine checklist (no composite score / no fabricated synthesis / cross-lane provenance) added to the cooperative master roadmap conflict section. |
| **Key files** | Created: `docs/engineering/FORWARD_VALIDATION_READINESS_CHECKLIST.md`; modified: `docs/research/THREE_LANE_ROADMAP_RECONCILIATION.md`, `docs/research/FOUR_LANE_ROADMAP_RECONCILIATION.md`, `docs/research/FIVE_LANE_ROADMAP_RECONCILIATION.md`, `docs/research/PLATFORM_COOPERATIVE_MASTER_ROADMAP.md`, `README.md` |
| **Tests** | Platform doc-link check passed |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) P0-1, P2-3, P2-5 |

## 2026-09-04 — P0-3: canonical lane-module identity (single registry, no drift)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/workspace`, `backend`, `docs` |
| **Summary** | Unified lane/module identity onto one canonical source: `WORKSPACE_LANE_REGISTRY` in `ui/src/components/workspace-module-shared/laneRegistry.ts`, which now also derives `WORKSPACE_LANE_MODULE_IDS` and `WORKSPACE_LANE_LABELS`. `paperOrderDraft.ts` exports (`LANE_MODULE_IDS`, `LaneModuleId`, `isKnownLaneModuleId`, `laneModuleLabel`) and `paperDecisionSemantics.ts` (`EVIDENCE_LANE_TO_MODULE_ID` typing, `MODULES_WITHOUT_EVIDENCE_LANE` complement) now read from the registry instead of hand-written literals. Removed the dead backend `KNOWN_LANE_MODULES` frozenset in `paper/decision_source.py` (defined, never imported): backend workspace-lane provenance is validated structurally, so it deliberately never enumerates lane modules. Added `laneRegistry.test.ts` equality/closure tests that fail if the derived lists or the evidence map drift from the registry. |
| **Key files** | Modified: `ui/src/components/workspace-module-shared/laneRegistry.ts`, `ui/src/components/paper-now/paperOrderDraft.ts`, `ui/src/components/paper-workspace/paperDecisionSemantics.ts`, `src/market_platform_foundation/paper/decision_source.py`, `docs/architecture/DATA_CONTRACTS.md`, `docs/engineering/sops/ADD_WORKSPACE_LANE.md`, `docs/engineering/FRONTEND_GUIDE.md`; created: `ui/src/components/workspace-module-shared/laneRegistry.test.ts` |
| **Tests** | `ui`: `npm run typecheck` clean; `npm test` — 85 files / 436 tests passed (incl. new `laneRegistry.test.ts`, 7 tests). Backend: `py_compile` of `decision_source.py` OK; grep confirms zero references to removed `KNOWN_LANE_MODULES` in `src`/`tests` (only stale `.pyc`). Full manifest validation (`tools/imp.py validate`) runs in CI on push — local Python 3.10 cannot collect the suite (repo requires 3.11 `StrEnum`/tz db) and the project `.venv` is not test-equipped. |
| **Related** | [Hardening task plan](../../../../docs/reviews/2026-09-04-hardening-task-plan.md) P0-3; [ADD_WORKSPACE_LANE.md](sops/ADD_WORKSPACE_LANE.md) |
| **Notes** | Adding a lane now edits exactly one identity source (`laneRegistry.ts`) plus its per-lane feature surfaces (route component, content builder, backend projection only when a new API is needed). Zero behavior change: derived lists are identical to the prior literals; order of `MODULES_WITHOUT_EVIDENCE_LANE` follows registry nav order (no consumer depends on the old ordering). |


## 2026-09-04 — Full validation green receipt and closure-audit cleanup

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `validation`, `repository` |
| **Summary** | Removed the stray empty untracked directories `src/market_platform_foundation/tests/providers` (created 2026-09-01, empty, unreferenced) that the frozen `POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json` does not classify; the canonical repository-closure audit fails closed on any unclassified path. The prior feature branch had classified the path in an unmerged edit; upstream `main` does not, and the frozen artifact must not be rewritten. With the dirs removed, the closure audit passes and the full validation ladder is green. |
| **Key files** | Deleted (empty dirs only): `src/market_platform_foundation/tests/`, `src/market_platform_foundation/tests/providers/`; receipt: `artifacts/developer-workflow/full-validation-receipt-20260904.json`; `docs/engineering/WORK_LOG.md` (this entry) |
| **Tests** | `tools/validate.py full`: `PASSED — 3487 tests, 43 skipped, 0 failures, 0 errors in 437.328s` across 59 suites (receipt JSON saved). Repository-closure audit (`load_closure_audit` on `POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json`) passes. Assistant-audit evidence files stayed clean through the entire full run, confirming the churn fix holds under the full ladder. |
| **Related** | [Repository closure audit](../engineering/POST_BUILD35_REPOSITORY_CLOSURE_AUDIT.md); prior entries this date (validation unblock, evidence churn fix) |
| **Notes** | No commit, push, deploy, or authority change. The removal is cleanup of untracked empty directories only; tracked content is unchanged. |

## 2026-09-04 — Stop tests from dirtying assistant-audit evidence

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/ui_api`, `tests`, `evidence` |
| **Summary** | Fixed the recurring dirt on `evidence/ui1/assistant-audit/{conversations,messages}.json`. Root cause: `ReplayStore.load()` defaulted `assistant_audit_root` to the tracked evidence path, so any test constructing a `ReplayStore` (e.g. `test_ui_api.py` "UI test session", the mra001 pipeline invoked by `test_mra001_api.py`) appended fresh time-stamped conversations/messages on every run. `ReplayStore` now defaults to an ephemeral temp root; the intentionally persistent writers (UI API server via `tools/ui1/run_ui_api.py`, and the mra001 evidence pipeline CLI) pass the new `TRACKED_ASSISTANT_AUDIT_ROOT` explicitly, and `build_evidence(output_dir, *, assistant_audit_root=...)` lets tests isolate. Evidence files were restored to their committed form. |
| **Key files** | `src/market_platform_foundation/ui_api/store.py`; `tools/ui1/run_ui_api.py`; `tools/mra001/run_mra001_pipeline.py`; `tests/mra001/test_mra001_api.py`; `docs/engineering/WORK_LOG.md` (this entry) |
| **Tests** | Focused suites via worker: ui1 13, ui2 5, mra001 3, mra002 3, assistant 17, gridiq 11, platform 457, intelligence 1151 — all passed, evidence files clean after every run. Explicit-root persistence verified (write to tracked root works when opted in, then restored). `tools/validate.py changed`: `305 tests, 6 skipped, 0 failures, 0 errors`; evidence clean after the run. `compileall` passed. |
| **Related** | [VALIDATION01 acceptance](../../artifacts/imp-rebase/VALIDATION01/VALIDATION01_ACCEPTANCE_REPORT.md) (prior "restore exactly" workaround); prior handoffs that preserved these files unstaged |
| **Notes** | No commit, push, deploy, or authority change. The server and mra001 CLI keep persisting to the tracked evidence path by explicit opt-in; ad-hoc/tests now use temp roots and never touch tracked evidence. |

## 2026-09-04 — Branch merged into main (paper profitability observability)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `governance`, `repository` |
| **Summary** | Finished `feat/paper-profitability-observability`: confirmed the branch was already merged upstream via the governed PR workflow (child-repo `origin/main` contains `a5506c1 feat(paper): add profitability observability (#11)` plus PRs #12–#14) and that the parent workspace snapshot under `projects/integrated-market-platform` already includes the full branch content. The stale local `main` ref (45a7b12) was fast-forwarded to the merged upstream state (`origin/main` = 3db07a5); the feature branch is now fully merged into `main`. No source files were changed and no new PR was needed. |
| **Key files** | `docs/engineering/WORK_LOG.md` (this entry); ref-only update: `git branch -f main origin/main` in the nested repository |
| **Tests** | `tools/monorepo_guard.py validate`: passed. Full validation baseline remains green (3462 tests, 0 failures/errors from the prior entry). |
| **Related** | [Monorepo workflow](../../../../docs/MONOREPO_WORKFLOW.md); PRs #11–#14 in the archived child repository |
| **Notes** | The child remote is archived (read-only), so the local `main` update is a tracking-sync, not a push. The parent repo requires no further change; its public snapshot intentionally excludes large artifacts per the publish policy. Local branches `feat/paper-profitability-observability`, `feat/rt01-paper-tracing`, and `feat/unify-paper-trading-chain` were subsequently deleted after confirming they are fully merged into `main`; their disposable worktrees were removed (unique regenerated evidence files preserved under `.local/_worktree-evidence-backup/`). |

## 2026-09-04 — Global validation baseline unblocked

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `validation`, `developer-tooling` |
| **Summary** | Cleared the standing dirty-tree/global validation blocker. Root cause was git's dubious-ownership safety check on the nested repository (owned by `CodexSandboxOffline` while validation runs as `adame`): `git rev-parse --show-toplevel` exited 128 inside `intelligence/live_canary` provenance code, erroring 28 deployment-change-control and release-governance tests. Applied git's documented remediation (`git config --global --add safe.directory` for this repository). No source, test, manifest, or authority files were changed. |
| **Key files** | `docs/engineering/WORK_LOG.md` (this entry); environment-only fix (`git config --global --add safe.directory C:/Users/adame/Desktop/market-trading-platform/integrated-market-platform`) |
| **Tests** | All 47 offline full-tier suites probed individually then orchestrated: `tools/validate.py full` passed with `3462 tests, 43 skipped, 0 failures, 0 errors in 591.442s`; `tools/validate.py changed` passed with `21 tests, 0 skipped, 0 failures, 0 errors`. Previously `intelligence` alone reported 28 errors from the git ownership failure. |
| **Related** | [Developer Operating System](DEVELOPER_OPERATING_SYSTEM.md); prior `GLOBAL VALIDATION BLOCKED` handoffs in this log |
| **Notes** | No commit, push, merge, deploy, or product behavior change. The safe.directory entry is machine-local and reversible (`git config --global --unset-all safe.directory`). |

## 2026-09-04 — RT-01 Paper pipeline tracing

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/paper`, `observability`, `tests`, `docs` |
| **Summary** | Added bounded Paper RT-01 trace handles and latency profiles, instrumented queue/signal/strategy/internal submission seams, and routed broker-paper submission, polling, cancellation, and reconciliation through the composed Paper provider. Broker partial-fill completion/cancel, restart/replay, idempotency, dry-run preview, and trace linkage are covered by fixture-driven tests. |
| **Key files** | `src/market_platform_foundation/rt01/instrumentation/paper.py`; `src/market_platform_foundation/rt01/{profiles.py,baseline.py,workloads.py,tracer.py}`; `src/market_platform_foundation/{market_data/bounded_queue.py,intelligence/signals/engine.py,intelligence/execution/engine.py,paper/{execution.py,broker_paper.py},strategy/runtime.py}`; `src/market_platform_foundation/ui_api/{paper_projections.py,broker_projections.py,server.py}` |
| **Tests** | Focused RT-01/Paper suites and broker/reconciliation regressions passed during implementation. Changed validation: 2,231 tests, 38 skipped, 0 failures/errors. UI: 428 tests passed, typecheck passed, production build and bundle budget passed at 202.26 KiB gzip. Full validation: 3,482 tests, 48 skipped, 1 pre-existing repository-closure error in the validation domain. |
| **Related** | RT-01 Paper tracing implementation plan (local read-only plan); [Paper decision lifecycle](../architecture/PAPER_DECISION_LIFECYCLE.md); [RT-01 operations](../operations/rt-01/README.md) |
| **Notes** | Work is isolated on the `feat/rt01-paper-tracing` child branch. The original child checkout’s unrelated dirty files remain untouched. The pre-existing `provider-composition` closure scope error (`src/market_platform_foundation/tests`, a nonexistent scope path) was subsequently fixed by removing the stale scope from `POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json`; full validation is no longer blocked by that error. |

## 2026-09-04 — Unified internal Paper trading chain

| Field | Value |
|-------|-------|
| **Area** | `backend/ui`, `paper`, `observability`, `tests` |
| **Summary** | Completed the canonical internal strategy Paper business chain by persisting an immutable order-ready decision, carrying one strategy decision correlation through Paper submission, and exposing a read-only trace that joins opportunity, allocation, risk, order-ready, fill-driven portfolio settlement, prediction settlement state, and cumulative attribution. Manual Paper trace anchors and execution authority boundaries remain backward-compatible. |
| **Key files** | `src/market_platform_foundation/intelligence/execution/{types,serialization}.py`; `src/market_platform_foundation/intelligence/persistence/{repository,memory}.py`; `src/market_platform_foundation/intelligence/persistence/mongo/{repository,schema}.py`; `src/market_platform_foundation/strategy/runtime.py`; `src/market_platform_foundation/ui_api/{paper_projections,strategy_runtime_projections,server}.py`; `ui/src/api/{schemas,endpoints,hooks}.ts`; `ui/src/components/paper/ExecutionTracePanel.tsx`; `tests/intelligence/test_equity_paper_runtime.py`; `tests/platform/test_strategy_runtime_observability.py` |
| **Tests** | Focused and expanded Paper/runtime suites: 113 passed; intelligence domain: 1,150 passed, 25 skipped; full UI suite: 429 passed; UI typecheck/build and Python compilation: pass. Corrected `artifacts/repository-closure/POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json` by removing its stale nonexistent scope path. Manifest domain-core validation: 2,727 tests, 48 skipped, 0 failures/errors; full validation: 3,467 tests, 48 skipped, 0 failures/errors. |
| **Related** | [Paper decision lifecycle](../architecture/PAPER_DECISION_LIFECYCLE.md); [Program status](../platform/PROGRAM_STATUS.md) |
| **Notes** | Broker-paper/live transport, OF-01 parent identity, RT-01 technical span persistence, and autonomous settlement remain deferred. The clean implementation worktree contains only this change set; the original checkout’s unrelated changes were preserved. |

## 2026-09-03 — Paper profitability observability

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/ui`, `observability`, `tests` |
| **Summary** | Exposed the existing strategy-to-Paper lineage through a read-only, Paper-account-scoped projection and GET API, then mounted a shared profitability observability surface in Paper Research and Paper Portfolio. Strategy attribution remains a non-authoritative cumulative P&L sidecar; settlement inspection does not mutate records and Workspace remains the only submission boundary. |
| **Key files** | `src/market_platform_foundation/ui_api/strategy_runtime_projections.py`; `src/market_platform_foundation/ui_api/server.py`; `src/market_platform_foundation/intelligence/persistence/{repository,memory}.py`; `src/market_platform_foundation/intelligence/persistence/mongo/repository.py`; `ui/src/api/{schemas,endpoints,hooks}.ts`; `ui/src/components/paper-strategy-profitability/`; `ui/src/components/paper-{research,portfolio}/`; `tests/platform/test_strategy_runtime_observability.py` |
| **Tests** | Focused backend observability: 8 passed. UI observability/API contracts: 11 passed. Full UI suite with the repository's lazy-route timeout allowance: 428 passed; typecheck and production build passed with 202.26 KiB initial gzip and bundle budget pass. Manifest-driven changed validation: 2,127 tests, 34 skipped, 0 failures/errors. |
| **Related** | `paper_profitability_observability_1ad70e43.plan.md` (local plan, not committed); [Paper decision lifecycle](../architecture/PAPER_DECISION_LIFECYCLE.md) |
| **Notes** | P6 Shadow Run and live provider campaigns were not run. The strategy repository is explicitly injectable on `ReplayStore`; an unbound repository fails closed in the API/UI. |

## 2026-09-03 — Program documentation reconciliation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `governance` |
| **Summary** | Reconciled the canonical program roadmap and architecture with accepted XA-04 and XA-05 milestones, removed stale “next” language, and recorded P6 Shadow Run 1 as deferred rather than active. Immutable P6 protocol and run artifacts were preserved; no runtime, ledger, or campaign state was changed. |
| **Key files** | `docs/platform/MASTER_ROADMAP.md`; `docs/platform/MASTER_ARCHITECTURE.md`; `docs/platform/PROGRAM_STATUS.md`; `docs/PROJECT_STATUS.md`; `docs/research/PLATFORMIZATION_ROADMAP.md`; `docs/engineering/WORK_LOG.md` |
| **Tests** | `tools/check_docs_links.py`: 161 governance markdown files checked, pass. `git diff --check`: pass. |
| **Related** | [XA-04 acceptance](../../artifacts/imp-rebase/XA04/XA04_ACCEPTANCE_REPORT.json); [XA-05 acceptance](../../artifacts/imp-rebase/XA05/XA05_ACCEPTANCE_REPORT.json); [P6 protocol](P6_SHADOW_RUN_1_PROTOCOL.md) |
| **Notes** | Historical P6 entries below remain unchanged. P6 is deferred until explicitly reactivated. |

## 2026-09-02 — Windows Operator Center and lifecycle UX

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `platform/lifecycle`, `platform/security`, `ui/control`, `developer-setup` |
| **Summary** | Added an idempotent Windows setup entry point, launcher-owned loopback supervisor, authorized lifecycle/configuration/readiness API contracts, guarded fast-forward update workflow, and canonical browser control center. Provider status remains independent and value-masked; Demo, Paper, Live-observational, and live-execution authority boundaries are unchanged. |
| **Key files** | `SETUP_PLATFORM.cmd`; `tools/platform/bootstrap.py`; `tools/platform/control_service.py`; `tools/platform/local_launcher.py`; `src/market_platform_foundation/ui_api/operator_config.py`; `src/market_platform_foundation/ui_api/operator_projections.py`; `ui/src/components/OperatorControlCenterPage.tsx` |
| **Tests** | Platform manifest worker: 436 tests, 434 passed, 2 expected skips, 0 failures/errors. Operator Control Center: 2/2 passed. UI typecheck and production build passed; bundle budget passed at 201.69 KiB gzip. The combined affected gate completed earlier with 2,222 tests, 34 expected skips, and 0 failures/errors. |
| **Related** | [Local development](LOCAL_DEVELOPMENT.md); [Provider readiness](PROVIDER_READINESS.md); [Mode authority](../architecture/MODE_AUTHORITY.md) |
| **Notes** | Supervisor binds to `127.0.0.1:8767`, verifies process identity before termination, and never resets, stashes, overwrites, or force-updates a dirty checkout. Provider secrets remain in the existing `.env`/`.private` stores with allowlisted atomic writes and masked responses. |

## 2026-09-02 — IMP Developer Operating System

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `developer-tooling`, `validation`, `governance`, `ci`, `docs` |
| **Summary** | Added a thin canonical `tools/imp.py` developer command router, explicit validation pyramid routing, merge-base affected-path support for clean CI checkouts, local telemetry, machine-readable repository metadata, closure-report generation, project hooks, scoped agent guidance, reusable skills, specialized subagent prompts, Bugbot safety instructions, and reusable cancellable CI validation. Existing manifest, worker, backend authority, and Demo/Paper/Live safety boundaries remain authoritative. |
| **Key files** | `tools/imp.py`; `tools/validate.py`; `tools/validation_manifest.json`; `.cursor/hooks.json`; `.cursor/rules/developer-workflow.mdc`; `.cursor/skills/`; `.cursor/agents/`; `.cursor/BUGBOT.md`; `manifests/developer-operating-system.json`; `.github/workflows/imp-python.yml`; `docs/engineering/DEVELOPER_OPERATING_SYSTEM.md`; `docs/engineering/DEVELOPER_OPERATING_SYSTEM_AUDIT.md`; `artifacts/developer-workflow/baseline.json` |
| **Tests** | Focused router/selection/hook tests: 16 passed; routed FAST: 21 passed; docs links: 136 governance markdown files checked; JSON manifests and GitHub workflow YAML parsed successfully; final affected validation: 2,176 tests, 34 skipped, 3 failures, 1 error in 425.317s; final closure FULL: 3,157 tests, 34 skipped, 3 failures, 1 error in 575.479s; UI closure: 421 tests passed, typecheck passed, build passed at 201.18 KiB gzip. Aggregate failures remain the dirty-tree baseline. |
| **Related** | [Developer Operating System](DEVELOPER_OPERATING_SYSTEM.md); [Current workflow audit](DEVELOPER_OPERATING_SYSTEM_AUDIT.md); [validation architecture](VALIDATION_ARCHITECTURE.md) |
| **Notes** | Closure report: `artifacts/developer-workflow/closure-report.json`, status `blocked_by_validation` because the pre-existing dirty tree retains three failures and one error. The first closure attempt exposed and then fixed Windows `npm.cmd` lookup; the final closure report was produced successfully. No commit, push, merge, deploy, reset, or product behavior change was performed. |

## 2026-09-02 — Equity Paper loop validation and handoff

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `architecture`, `observability`, `validation` |
| **Summary** | Completed the final Task 7 handoff for the deterministic equity-like Paper loop. Documented the backend-only persisted lineage path, separate allocation/proposal/risk/order/fill quantities, cumulative actual-fill attribution, independent forecast settlement, structured runtime diagnostics, and reconstruction from authoritative records without introducing UI or duplicate authority. |
| **Key files** | `docs/architecture/PAPER_DECISION_LIFECYCLE.md`; `docs/engineering/OBSERVABILITY.md`; `docs/engineering/WORK_LOG.md`; `task_plan.md`; `findings.md`; `progress.md` |
| **Tests** | Focused pass: phase-6 strategy definitions `7/7`; strategy scanning/match `9/9`; baseline forecasts `5/5`; opportunity/bridge, clustering, comparison/allocation, and allocation persistence `31/31`; Paper execution governance `18/18`; runtime integration `11/11` (including the `equity-paper-runtime-suite` validation worker); strategy attribution `12/12`; portfolio accounting `7/7`; outcome settlement `15/15`; strategy learning `8/8`. `PYTHONPATH=src .venv\Scripts\python.exe -m compileall -q src tests`: pass. `git diff --check`: pass, with a non-failing pre-existing CRLF normalization warning. `tools/check_docs_links.py`: 134 governance markdown files checked, pass. `ui`: `npm test -- --reporter=dot --maxWorkers=1` pass; `npm run build` pass, 1085 modules transformed, initial bundle `201.18 KiB gzip`. `tools/validate.py changed`: blocked by dirty baseline (`1232 tests, 9 skipped, 1 failure, 91 errors in 530.542s`). `tools/validate.py full`: blocked by dirty baseline (`2209 tests, 9 skipped, 1 failure, 92 errors in 734.902s`). |
| **Related** | `equity-paper-loop_5c6b4402.plan.md` (local plan, not committed); [Paper decision lifecycle](../architecture/PAPER_DECISION_LIFECYCLE.md); [Observability](OBSERVABILITY.md) |
| **Notes** | Final status is `FOCUSED CLOSED / GLOBAL VALIDATION BLOCKED`. Aggregate failures span `finviz`, `platform`, `intelligence`, `ui1`, `ui2`, and `validation` and are retained as the pre-existing dirty-tree/global validation classification. No commit, push, deploy, reset, clean, plan-file edit, secret, UI authority, allocation authority, attribution authority, or unfinished diagnostic was introduced. |

## 2026-09-02 — Bounded governed strategy learning boundary

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/strategy`, `tests` |
| **Summary** | Added an immutable, reference-preserving learning observation/join boundary over the existing StrategyDefinition identity, StrategyMatch, ForecastV1, OutcomeV1, and StrategyAttributionV1 records. Versioned policy gates enforce point-in-time lineage, settled/labelable prediction outcomes, evidence allow-lists, minimum samples, account/mode isolation, and optional attributed trading sidecars while preserving independent prediction and trading quality. |
| **Key files** | `src/market_platform_foundation/strategy/learning.py`; `src/market_platform_foundation/strategy/__init__.py`; `tests/intelligence/test_strategy_learning.py` |
| **Tests** | Focused learning boundary `8/8`; StrategyMatch `5/5`; StrategyDefinition `3/3`; StrategyAttribution `7/7`; compileall, package export, and new/modified-file whitespace checks passed. `tools/validate.py changed` completed with the dirty-tree aggregate result: `1206 tests, 9 skipped, 1 failure, 91 errors` across `finviz`, `platform`, `intelligence`, `ui1`, and `validation`. |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | Research handoffs are fixed non-promotional seeds requiring ResearchHypothesisV1, ExperimentManifestV1, validation, locked holdout, contamination, shadow, and PromotionEngine authorities; they cannot promote, execute, or change a champion. No frozen contract, PromotionEngine, plan, BUILD/TD record, UI, ranking, allocation, risk, broker, or unrelated dirty file was changed. |

## 2026-09-02 — Durable strategy attribution boundary

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/portfolio`, `backend/persistence`, `tests` |
| **Summary** | Added an immutable strategy-to-realized-P&L attribution sidecar that retains virtual allocation slices and explicit fill lineage independently of broker-netted positions, risk decisions, and the authoritative portfolio ledger. Deterministic canonical identity, integer cost-basis accounting, account/mode/PIT guards, explicitly labeled prediction/trading outcomes, and in-memory/Mongo persistence support durable joins without inferring attribution from net positions. |
| **Key files** | `src/market_platform_foundation/portfolio/attribution.py`; `src/market_platform_foundation/portfolio/__init__.py`; `src/market_platform_foundation/intelligence/persistence/{codec,memory,repository}.py`; `src/market_platform_foundation/intelligence/persistence/mongo/{repository,schema}.py`; `src/market_platform_foundation/intelligence/contracts/common.py`; `tests/platform/test_strategy_attribution.py` |
| **Tests** | Focused attribution `7/7`; authoritative portfolio ledger `6/6`; intelligence contracts `18/18`; Mongo schema bootstrap `8/8`; StrategyMatch `5/5`; compileall and tracked/new-file whitespace checks passed. `tools/validate.py changed` reached `1198 tests, 9 skipped` but reported `1 failure, 91 errors` from the pre-existing dirty repository baseline and direct-script package import assumptions. |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | No plan, BUILD/TD record, commit, reset, checkout, order/risk decision, authoritative ledger, or unrelated dirty file was changed. |

## 2026-09-02 — Account-scoped opportunity comparison and allocation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/intelligence/opportunity`, `tests` |
| **Summary** | Added immutable, bounded account/mode/PIT-scoped comparison inputs and explicit comparison vectors over OpportunityV1 plus required universal economic sidecars. Added deterministic one-expression-per-thesis comparison, duplicate/exclusion reasons, observability counters, and an independent capital allocator that emits capital intents only; risk and execution authorities remain unchanged. |
| **Key files** | `src/market_platform_foundation/intelligence/opportunity/comparison.py`; `src/market_platform_foundation/intelligence/opportunity/__init__.py`; `tests/intelligence/test_opportunity_comparison.py` |
| **Tests** | Focused comparison/allocation `8/8`; thesis clustering compatibility `8/8`; compileall passed; focused whitespace checks produced no diagnostics. `tools/validate.py changed` completed with the pre-existing dirty-tree baseline result: `1151 tests, 9 skipped, 1 failure, 102 errors`. |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | Changed validation remains blocked by the existing `portfolio.attribution` circular import and other dirty-tree suite failures. No frozen contracts, BUILD/TD records, plan files, UI, proposals, risk decisions, orders, broker calls, or unrelated dirty files were modified. |

## 2026-09-02 — Bounded opportunity thesis clustering

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/intelligence/opportunity`, `tests` |
| **Summary** | Added an immutable, account/mode/PIT-scoped thesis clustering projection over OpportunityV1, StrategyMatch, and optional universal economic sidecars. Deterministic explicit/fallback thesis identities group duplicate strategies and expressions while preserving lineage; the duplicate view only marks exposure and does not rank, allocate, or collapse opportunities. |
| **Key files** | `src/market_platform_foundation/intelligence/opportunity/clustering.py`; `src/market_platform_foundation/intelligence/opportunity/__init__.py`; `tests/intelligence/test_opportunity_clustering.py` |
| **Tests** | Focused clustering `8/8`; bridge/sidecar regressions `7/7`; StrategyMatch regressions `5/5`; compileall and changed-file whitespace checks passed. |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | No frozen V1 contracts, BUILD/TD records, plan files, persistence, ranking, allocation, UI, execution, or unrelated dirty files were changed. |

## 2026-09-02 — Universal economic sidecar and opportunity bridge

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/intelligence/opportunity`, `backend/persistence`, `tests` |
| **Summary** | Added an immutable, dimension-preserving universal economic-assessment sidecar with integer minor-unit money, explicit ns/bps/probability semantics, versioned assumptions, liquidity/capacity, uncertainty, factor exposure, and account actionability. Added a strict SHARED P4 adapter and a canonical MATCHED StrategyMatch bridge that delegates to the existing OpportunityEngine and preserves sidecar/match lineage without changing V1 authorities. |
| **Key files** | `src/market_platform_foundation/intelligence/opportunity/{economic_assessment,p4_adapter,bridge}.py`; `src/market_platform_foundation/intelligence/opportunity/{__init__,identity,serialization,types}.py`; `src/market_platform_foundation/intelligence/persistence/{memory,repository}.py`; `src/market_platform_foundation/intelligence/persistence/mongo/repository.py`; `tests/intelligence/test_universal_opportunity.py` |
| **Tests** | Focused universal sidecar/bridge `7/7`; opportunity and contract regression `54/54`; persistence/strategy regression `31/31`; compileall and bounded `git diff --check` passed. Full changed validation remains blocked by the pre-existing dirty-tree platform baseline (`437 tests, 3 skipped, 0 failures, 4 errors`). |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | No BUILD/TD records, plan file, commit, reset, checkout, clustering, ranking, allocation, UI, multi-asset accounting, or execution authority was changed. |

## 2026-09-02 — Bounded universal strategy scanning

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/strategy`, `tests` |
| **Summary** | Added a deterministic one-pass universal strategy scanner with explicit point-in-time universes, capability/context snapshots, Stage A eligibility, Stage B cheap screening, bounded evaluator budgets, trigger metadata, account/mode scope, and immutable StrategyMatch persistence. Coarse screen/evaluator failures remain diagnostics and counters without fabricating decision records. |
| **Key files** | `src/market_platform_foundation/strategy/scanning.py`; `src/market_platform_foundation/strategy/__init__.py`; `tests/intelligence/test_strategy_scanning.py` |
| **Tests** | Focused scanner `3/3`; StrategyMatch contract `5/5`; compileall and focused whitespace checks passed. Repository changed validation was run; final baseline result is reported in the handoff. |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | No BUILD/TD records, plan file, commit, reset, checkout, UI, economics, ranking, allocation, daemon, or execution behavior was changed. |

## 2026-09-02 — Immutable StrategyMatch contract

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/intelligence`, `tests` |
| **Summary** | Added an immutable typed `StrategyMatch` evaluation record with explicit MATCHED, REJECTED, ABSTAINED, UNAVAILABLE, and EXPIRED dispositions. Canonical identity/serialization and immutable repository persistence retain source references, condition outcomes, reasons, capability/quality state, context, validity, and lineage without adding scanner or execution behavior. |
| **Key files** | `src/market_platform_foundation/intelligence/contracts/strategy_match.py`; `src/market_platform_foundation/intelligence/contracts/{__init__,common}.py`; `src/market_platform_foundation/intelligence/persistence/{codec,memory,repository}.py`; `src/market_platform_foundation/intelligence/persistence/mongo/{repository,schema}.py`; `tests/intelligence/test_strategy_match.py`; `tests/intelligence/test_persistence_mongo_schema.py` |
| **Tests** | Focused StrategyMatch `5/5`; existing intelligence contracts `18/18`; Mongo schema `8/8`; validator worker persistence selector `1/1`; compileall and tracked-file whitespace check passed. `tools/validate.py changed` completed with `1170 tests, 9 skipped, 1 failure, 90 errors`; failures were across dirty-tree `finviz`, `platform`, `intelligence`, `ui1`, and `validation` suites. |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | No BUILD/TD records, plan files, commits, resets, checkouts, scanner orchestration, economics, ranking, allocation, UI, or execution behavior were changed. |

## 2026-09-02 — Portfolio fill accounting and settlement scheduler correctness

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/portfolio`, `backend/intelligence`, `tests` |
| **Summary** | Corrected authoritative fill accounting with signed net-position cost basis, including weighted scale-in/scale-out, long/short closes, and reversals. Due unsettled prediction entries now report `SettlementStatus.DUE` through the scheduler. |
| **Key files** | `src/market_platform_foundation/portfolio/ledger.py`; `src/market_platform_foundation/portfolio/reconciliation.py`; `src/market_platform_foundation/portfolio/__init__.py`; `src/market_platform_foundation/paper/ledger.py`; `src/market_platform_foundation/intelligence/outcomes/scheduler.py`; `tests/platform/test_portfolio_ledger_accounting.py` |
| **Tests** | Focused accounting/scheduler unittest `6/6`; paper compatibility `74/74`; ledger durability `9/9`; reconciliation `18/18`; compileall passed; phase7 validation worker `3/3`; focused manifest selectors `6/6`. `validate.py changed` and `validate.py domain core` remain blocked by unrelated dirty-tree import/auth failures (`1165 tests, 9 skipped, 1 failure, 90 errors`; `431 tests, 3 skipped, 4 errors`). |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | No BUILD/TD records or plan files were modified. Existing unrelated dirty-tree changes were preserved. |

## 2026-09-01 — Typed strategy identity/catalog boundary

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/strategy`, `tests` |
| **Summary** | Added an immutable, typed `StrategyDefinition` with versioned optional taxonomy fields for family, style, asset class, and timeframe. Legacy dictionary strategy specs retain their prior identity-hash and serialization behavior when taxonomy is absent, while preregistration, interpretation, and evaluation explicitly accept either representation. |
| **Key files** | `src/market_platform_foundation/strategy/{strategy_spec,preregistration,interpretation,evaluation,__init__}.py`; `tests/phase6/test_strategy_definition.py` |
| **Tests** | Focused typed strategy tests `3/3`; complete strategy subset `7/7`; strategy compile check passed. Repository `tools/validate.py changed` ran `953` tests with `1` failure and `7` errors in unrelated dirty-tree suites (`finviz`, `platform`, `ui1`, `validation`). |
| **Related** | `C:/Users/adame/.cursor/plans/imp_universal_opportunity_23f67055.plan.md` (read-only) |
| **Notes** | No BUILD/TD records, plan file, commit, reset, checkout, or unrelated changes were modified. |

## 2026-09-01 — Multi-source foundation extension and identity hardening

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `backend/providers`, `tests`, `docs` |
| **Summary** | Added bounded, structured, deeply immutable provider extensions across observations, envelopes, and normalization, and made raw content identity source-scoped by provider and source instance. Recognized credential patterns remain redacted; opaque strings without markers are documented as caller-prohibited secret input. |
| **Key files** | `src/market_platform_foundation/providers/{observations,raw_records}.py`; `tests/providers/test_multi_source_foundation.py`; foundation provider docs, ADR, and plan |
| **Tests** | Focused foundation `25/25`; complete providers `125/125` after this change. Full/changed validation remains blocked by unrelated dirty-tree suites; current counts are recorded in the plan. |
| **Related** | [implementation plan](../superpowers/plans/2026-09-01-multi-source-data-foundation.md), [ADR-0009](../architecture/adr/0009-multi-source-data-integration-foundation.md) |
| **Notes** | No commit, push, reset, checkout, stash, or unrelated-file overwrite performed. |

## 2026-09-01 — Multi-source foundation remediation

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `backend/providers`, `tests`, `docs` |
| **Summary** | Remediated foundation contract gaps without changing execution lifecycle or unrelated provider work. Envelopes now preserve explicit clocks/acquisition/revision lineage; mappings fail closed; raw and normalized records are deeply immutable; planner and reconciliation policies are operational and deterministic. |
| **Key files** | `src/market_platform_foundation/providers/{identity,observations,raw_records,planner,reconciliation,registry,storage}.py`; `tests/providers/test_multi_source_foundation.py`; foundation ADR/provider docs and implementation plan |
| **Tests** | Focused foundation `23/23`; complete providers `123/123`; IBKR `47/47`; news `5/5`; provider-readiness `6/6`; compileall and linter passed. Changed/full repository validation remains blocked by unrelated dirty-tree baseline failures documented in the plan. |
| **Related** | [implementation plan](../superpowers/plans/2026-09-01-multi-source-data-foundation.md), [ADR-0009](../architecture/adr/0009-multi-source-data-integration-foundation.md) |
| **Notes** | No commit, push, reset, checkout, deployment, or unrelated-file overwrite performed. |

## 2026-09-01 — Multi-source data integration foundation

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `backend/providers`, `docs`, `tests` |
| **Summary** | Added a stdlib-only provider foundation for operational capability registration, namespaced instrument identity, immutable raw lineage, explicit PIT observation clocks, deterministic planning, bounded storage boundaries, and multi-source reconciliation. Existing runtime composition, paper execution, mode authority, account isolation, and Live execution block were left unchanged. |
| **Key files** | `src/market_platform_foundation/providers/{registry,identity,observations,raw_records,planner,reconciliation,storage,testing}.py`; `tests/providers/test_multi_source_foundation.py`; `docs/providers/MULTI_SOURCE_DATA_FOUNDATION.md`; `docs/architecture/adr/0009-multi-source-data-integration-foundation.md`; `docs/superpowers/plans/2026-09-01-multi-source-data-foundation.md` |
| **Tests** | Focused foundation `13/13`; complete providers `111/111`; fast validation `21` passed; docs links `134` files checked; UI `421/421`, typecheck, and build passed. Full/changed validation remains blocked by existing adjacent dirty-tree finviz/platform/intelligence/ui1/ui2/validation failures; exact evidence is in the plan. |
| **Related** | [implementation plan](../superpowers/plans/2026-09-01-multi-source-data-foundation.md), [ADR-0009](../architecture/adr/0009-multi-source-data-integration-foundation.md) |
| **Notes** | No commit, push, deploy, reset, checkout, or unrelated user-change overwrite performed. Existing IBKR/news/Finviz/readiness/evidence work remains preserved. |

## 2026-09-01 — P6 Shadow Run 1 duplicate-bucket operational check

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `shadow`, `tools/research`, `artifacts/shadow-run-1` |
| **Summary** | Completed another 120-second live Moomoo/OpenD collection increment. No new decision rows were emitted because the observed buckets were already recorded; append-only deduplication held, with zero recorder errors. |
| **Key files** | `.local/shadow/experiment.sqlite3`, `.local/shadow/captures/CAP-BIYA-SR1-20260901.jsonl`, `artifacts/shadow-run-1/P6_ACCEPTANCE_MATRIX.json` |
| **Tests** | Acceptance refreshed with environment variables cleared: 15/15 pass; reconciliation 5/5, 0 unreconciled |
| **Related** | [completion](../superpowers/plans/2026-09-01-p6-shadow-run-1-forward-validation-completion.md), [SOP](sops/FORWARD_SHADOW_VALIDATION.md) |
| **Notes** | Stopping rule remains unmet at 12/65 scheduled grid opportunities. |

## 2026-09-01 — P6 acceptance source reproducibility hardening

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `shadow`, `tools/research`, `tests` |
| **Summary** | Acceptance now derives P6-AC-002 from the immutable run’s `live_observation` reference and non-empty sealed capture, rather than requiring live environment variables at evaluation time. This keeps acceptance reproducible and prevents a valid stored run from being incorrectly blocked offline. |
| **Key files** | `tools/research/run_shadow_run.py`, `tests/platform/test_shadow_run1_cli.py` |
| **Tests** | Complete `test_shadow_run1*.py` subset — 59 tests passed; acceptance regenerated with environment variables cleared — 15/15 pass |
| **Related** | [completion](../superpowers/plans/2026-09-01-p6-shadow-run-1-forward-validation-completion.md), [SOP](sops/FORWARD_SHADOW_VALIDATION.md) |
| **Notes** | P6 remains `IN_PROGRESS_EVIDENCE_COLLECTION`; stopping rule is not met. |

## 2026-09-01 — P6 Shadow Run 1 live forward evidence (additional bounded session)

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `shadow`, `tools/research`, `artifacts/shadow-run-1` |
| **Summary** | Completed an additional 120-second live Moomoo/OpenD observation session for BIYA on the existing preregistered run. The run now contains 10 ACTUAL_FORWARD model outcomes and 10/10 provenance-complete decisions with zero recorder errors; the stopping rule remains unmet. |
| **Key files** | `.local/shadow/experiment.sqlite3`, `.local/shadow/captures/CAP-BIYA-SR1-20260901.jsonl`, `artifacts/shadow-run-1/P6_ACCEPTANCE_MATRIX.json` |
| **Tests** | Complete `test_shadow_run1*.py` subset — 58 tests passed; `git diff --check` clean apart from CRLF normalization warning |
| **Related** | [completion](../superpowers/plans/2026-09-01-p6-shadow-run-1-forward-validation-completion.md), [SOP](sops/FORWARD_SHADOW_VALIDATION.md) |
| **Notes** | Acceptance remains `IN_PROGRESS_EVIDENCE_COLLECTION`; current scheduled grid count is 12/65. |

## 2026-09-01 — P6 legacy provenance reconciliation (P6-AC-005 closure)

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `shadow`, `tools/research` |
| **Summary** | Added `reconcile_shadow_provenance.py` to map 5 immutable pre-fix decisions to sealed capture buckets without mutating store rows. Wired acceptance to count reconciled IDs; fixed P6-AC-010 default matrix emission. Honest disposition remains `IN_PROGRESS_EVIDENCE_COLLECTION` (stopping rule not met). |
| **Key files** | `tools/research/reconcile_shadow_provenance.py`, `tools/research/run_shadow_run.py`, `artifacts/shadow-run-1/LEGACY_PROVENANCE_RECONCILIATION.json`, `tests/platform/test_shadow_run1_provenance_reconcile.py` |
| **Tests** | `test_shadow_run1_provenance_reconcile`, `test_shadow_run1_acceptance` — pass |
| **Related** | [completion](../superpowers/plans/2026-09-01-p6-shadow-run-1-forward-validation-completion.md), [SOP](sops/FORWARD_SHADOW_VALIDATION.md) |
| **Notes** | P6 not CLOSED until stopping rule + close/label/report cycle completes. |

## 2026-09-01 — P6 Shadow Run 1 forward-validation evidence phase (preregistration)

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `shadow`, `docs`, `tools/research` |
| **Summary** | Preregistered P6 Shadow Run 1 protocol, source availability audit, acceptance evaluator (`shadow/acceptance.py`, CLI `acceptance` subcommand), operator SOP, and reconciled project status docs. Initialized resumable run machinery on Build-35 baseline; forward observations **blocked** (Moomoo/OpenD not configured). Honest disposition: IN_PROGRESS_EVIDENCE_COLLECTION. |
| **Key files** | `artifacts/shadow-run-1/*`, `docs/engineering/P6_SHADOW_RUN_1_PROTOCOL.md`, `docs/engineering/sops/FORWARD_SHADOW_VALIDATION.md`, `src/market_platform_foundation/shadow/acceptance.py`, `tools/research/run_shadow_run.py`, `tests/platform/test_shadow_run1_acceptance.py`, `docs/PROJECT_STATUS.md`, `docs/product/PRODUCT_BACKLOG.md`, `docs/research/PLATFORMIZATION_ROADMAP.md` |
| **Tests** | `test_shadow_run1_acceptance`; targeted shadow suite; `validate.py changed` |
| **Related** | [P6 protocol](P6_SHADOW_RUN_1_PROTOCOL.md), [completion](../superpowers/plans/2026-09-01-p6-shadow-run-1-forward-validation-completion.md) |
| **Notes** | Do not mark P6 CLOSED until ACTUAL_FORWARD observation window completes. Fixture/replay remains infrastructure proof only. |

## 2026-09-01 — P6 Shadow Run 1 live forward evidence (session 1)

| Field | Value |
|-------|-------|
| **Status** | `in-progress` |
| **Area** | `shadow`, `tools/research`, `artifacts/shadow-run-1` |
| **Summary** | Live Moomoo/OpenD forward collection on default-store run `SHRUN-00C5…`: 5 `ABSTAINED_MODEL` decisions, 0 recorder errors. Pinned green `validate.py full` receipt (P6-AC-011), `PREFLIGHT_EVIDENCE.json`, acceptance matrix 15/15 with honest `IN_PROGRESS_EVIDENCE_COLLECTION`. Fixed SQLite thread safety, `event_type` envelope handling, validation flakes, and abstention provenance (`decision_time_ns` / `available_time_ns`) for grid counting. |
| **Key files** | `collect_shadow_observations.py`, `shadow/recording.py`, `shadow/experiment.py`, `PREFLIGHT_EVIDENCE.json`, `P6_VALIDATION_RECEIPT.json` |
| **Tests** | `test_shadow_run1_*`; `validate.py full` green |
| **Related** | [completion](../superpowers/plans/2026-09-01-p6-shadow-run-1-forward-validation-completion.md), [PR #8](https://github.com/AdamEddahmouni/integrated-market-intelligence-platform/pull/8) |
| **Notes** | Stopping rule not met (0 scheduled grid opportunities on legacy abstention rows; recorder fix applies to new decisions). |

## 2026-09-01 — TD-005 operator authentication and account-scoped authorization

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend/security`, `ui_api`, `ui/auth`, `docs` |
| **Summary** | Closed TD-005 by implementing LOOPBACK_TRUST (default) and ENFORCED auth modes, principal registry, session API, route capability + OperationalIdentity account ACL enforcement, security foundation wiring (redaction, leak audit), and frontend AuthProvider/login gate. ADR-0008 records topology and P0 decision 6 local amendment. |
| **Key files** | `platform/security/auth_config.py`, `principals.py`, `sessions.py`, `access_control.py`, `route_policy.py`, `ui_api/request_auth.py`, `ui_api/auth_projections.py`, `ui_api/server.py`, `ui/src/auth/*`, `fixtures/auth/principals.json`, `tests/platform/test_td005_auth_enforcement.py` |
| **Tests** | `test_td005_auth_enforcement`; `test_security_foundations_p5` updated; `validate-python`; `validate-ui` |
| **Related** | [ADR-0008](../architecture/adr/0008-operator-authentication-authorization.md), [ADR-0007](../architecture/adr/0007-operational-account-identity.md) |
| **Notes** | OIDC/hosted IdP deferred. Set `IMP_AUTH_ENFORCEMENT_MODE=ENFORCED` and `IMP_AUTH_PRINCIPALS_PATH` for local multi-user. |

## 2026-09-01 — TD-003 multi-account snapshot architecture and state isolation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend`, `ui/api`, `docs` |
| **Summary** | Closed TD-003 by introducing `OperationalIdentity`, account discovery (`GET /accounts`), account-scoped canary snapshots/reconciliation, `AccountSnapshotCache` with per-account refresh locks, demo/paper portfolio view isolation, and frontend account-aware query keys. ADR-0007 records the decision. |
| **Key files** | `operational_identity.py`, `account_registry.py`, `account_snapshot_cache.py`, `canary_projections.py`, `paper_projections.py`, `broker_projections.py`, `server.py`, `ui/src/api/hooks.ts`, `ui/src/api/liveCanary.ts`, `tests/platform/test_operational_identity.py`, `tests/platform/test_account_isolation.py` |
| **Tests** | `test_operational_identity 5 passed`; `test_account_isolation 5 passed`; `ui vitest`; `validate.py changed/full` |
| **Related** | [ADR-0007](../architecture/adr/0007-operational-account-identity.md), [completion](../superpowers/plans/2026-09-01-td-003-multi-account-snapshot-completion.md) |
| **Notes** | TD-004 unchanged (OpenD unavailable). No Live execution added. Moomoo adapter conforms to identity contract at interface level only. |

## 2026-09-01 — Operational hardening, data provenance, CI closure, repository consolidation

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `backend` (lane_provenance, server), `ui` (provenance, query keys, Live strip, primitives), `pipelines/stock_data`, `docs`, `ci` |
| **Summary** | Closed TD-002 (lane `lane_provenance` envelope on workspace APIs + `laneProvenance.ts` + ADR-0006), partially closed TD-003 (mode-scoped `liveCanarySnapshot` keys), closed TD-006 (CI typecheck+test+build). Renamed `pipelines/stock_data/src/ui` → `operator_console`. Fixed `WorkspaceModuleNav` circular type. Added smoke tests. |
| **Key files** | `lane_provenance.py`, `server.py`, `laneProvenance.ts`, `hooks.ts`, `LiveLaneOperationalStrip.tsx`, `LaneModeContextPanel.tsx`, `operator_console/`, `imp-validate.yml`, `tsconfig.typecheck.json`, ADR-0006, completion record |
| **Tests** | `ui: vitest 417 passed`; `ui: typecheck pass`; `ui: build pass (199.89 KiB gzip)`; `test_lane_provenance 4 passed`; `test_repository_closure OK` |
| **Related** | [completion](../superpowers/plans/2026-09-01-operational-hardening-completion.md) |
| **Notes** | TD-003 per-broker lane snapshots remain backend-blocked. TD-004 unchanged. Playwright E2E deferred — Vitest integration smoke sufficient. |

## 2026-09-01 — UI completion & productization pass

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui` (shared primitives, portfolio, settings, discover, trace, diagnostics, workspace routes), `backend` (paper order-history API), `docs` |
| **Summary** | Major UI productization: shared `LoadingState`/`EmptyState`/`PageHeader`/`JsonDetailPanel`/`InstrumentSelectionEmpty`; canonical lane + mode metadata registries; Paper order history server pagination (`GET /paper/order-history`) with infinite-scroll UI (TD-001 closed); instrument-selection dead-ends fixed; raw JSON operational surfaces structured; tests and validation updated. |
| **Key files** | Created: `ui/src/components/shared/*`, `ui/src/styles/shared-ui.css`, `workspace-module-shared/laneRegistry.ts`, `mode-session/modeMetadata.ts`, `ui/src/test/paperOrderHistoryQueryMock.ts`, completion record. Modified: `paper_projections.py`, `server.py`, `PaperOrderHistory*`, `OperatorSettingsPage`, `DiscoverObservability`, `ProviderHealthPanel`, `ExecutionTracePanel`, `WorkspaceEvidenceDrawer`, `WorkspaceIndex`, disclosure/institutional routes, `WorkspaceModuleNav`, `ModeLauncher`, `App.tsx`, tests, `PROJECT_STATUS.md`, `TECH_DEBT.md`. |
| **Tests** | `ui: vitest 407 passed`; `build: pass (199.83 KiB gzip initial)`; `validate.py changed: 860 passed`; `validate.py full: 2970 passed` |
| **Related** | [completion](../superpowers/plans/2026-09-01-ui-completion-productization-completion.md), TD-001 |
| **Notes** | InspectorPanel remains raw JSON (developer inspect). Full PageHeader migration across all routes optional follow-up. |

## 2026-09-01 — Project operating system / engineering governance upgrade

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs`, `AGENTS`, `.cursor/rules`, `tools`, `.github`, `README` |
| **Summary** | Comprehensive governance upgrade: authoritative doc map (`docs/README.md`), architecture (mode authority, Paper lifecycle, data contracts, ADRs), engineering handbook/guides/SOPs/checklists/templates/prompts, AI agent guidance, security/runbook/status/glossary, overhauled AGENTS.md + scoped agent files + Cursor rules, docs link checker, CI UI test/build job, fixed WORK_LOG broken links, completion record. |
| **Key files** | Created: `docs/README.md`, `docs/PROJECT_STATUS.md`, `docs/GLOSSARY.md`, `docs/architecture/*`, `docs/engineering/*` (handbook, guides, SOPs, etc.), `docs/operations/RUNBOOK.md`, `docs/product/PRODUCT_BACKLOG.md`, `ui/AGENTS.md`, `paper/AGENTS.md`, `tools/check_docs_links.py`, `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/*`, `.cursor/rules/*.mdc`. Modified: `AGENTS.md`, `README.md`, `WORK_LOG.md` (link fixes), `imp-validate.yml`, `validation_manifest.json`, `POST_BUILD35_SUBSYSTEM_CLASSIFICATION.json`, completion record headers. |
| **Tests** | `ui`: vitest **403 passed**; `npm run build` pass (**199.17 KiB gzip**); `check_docs_links.py` pass (126 files); closure audit test pass; `validate.py changed` **859 passed**; `validate.py full` **2969 passed** |
| **Related** | [OS completion](../superpowers/plans/2026-09-01-project-operating-system-completion.md), [source time completion](../superpowers/plans/2026-09-01-paper-decision-source-time-completion.md) |
| **Notes** | No CHANGELOG/CODEOWNERS. Historical BUILD specs and completion records preserved with forward links. MIGRATION SOP omitted (no migration framework). |

---

## 2026-09-01 — Paper decision source time provenance

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/paper`, `ui/paper-now`, `ui/paper-workspace`, `ui/paper-portfolio`, `backend/paper`, `backend/ui_api`, `ui/tests`, `docs` |
| **Summary** | Populated trustworthy `source_time` across the full Paper decision lifecycle: optional `AttentionItem.surfaced_time` (epoch ns) from backend projections; `resolvePaperDecisionSourceTime` helper; `sourceContext.source_time` set once at handoff; immutable through preview/submit/intent/projection; semantic labels in cockpit, Portfolio, and execution trace. Legacy records without source time remain valid. |
| **Key files** | Created: `resolvePaperDecisionSourceTime.ts`, `paperSourceTimestamp.ts`, tests, `docs/superpowers/plans/2026-09-01-paper-decision-source-time-completion.md`. Modified: `paperOrderDraft.ts`, `paperDecisionSourceSnapshot.ts`, `OrderTicket.tsx`, `buildPaperHandoffModel.ts`, `PaperHandoffPanel.tsx`, `PaperPersistedSourceContextPanel.tsx`, `schemas.ts`, `attention_item.schema.json`, `ui_api/projections.py`, `donor_bridge/projections.py`, `decision_source.py`, fixtures/tests, completion records. |
| **Tests** | `ui`: vitest **403 passed** (73 files); `npm run build` pass; initial bundle **199.17 KiB gzip**; `validate.py changed` **859 passed**; `validate.py full` **2969 passed** |
| **Related** | [Source time completion](../superpowers/plans/2026-09-01-paper-decision-source-time-completion.md), [Source snapshot completion](../superpowers/plans/2026-08-31-paper-decision-source-snapshot-completion.md) |
| **Notes** | Timestamp units: epoch ns (backend/`surfaced_time`); values ≤1e15 treated as ms in UI formatters. Handoff fallback only when canonical source time absent. No decay/expiry logic. Demo/Live unchanged. |

---

## 2026-08-31 — Paper decision-source snapshot persistence

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/paper-portfolio`, `ui/paper`, `backend/paper`, `ui/tests`, `docs` |
| **Summary** | Persisted bounded `decision_source_snapshot` on Paper order intents (attention headline/tier/reasons; lane module identity), projected through `project_orders()` into Portfolio history and execution trace. Draft `sourceContext` maps to validated request snapshot; correlation/provenance identity unchanged; mismatch fails closed on write and degrades safely on read. Historical UI labeled *Source context at decision handoff*. |
| **Key files** | Created: `paper/decision_source.py`, `paper/paperDecisionSourceSnapshot.ts`, `PaperPersistedSourceContextPanel.tsx`, tests, `docs/superpowers/plans/2026-08-31-paper-decision-source-snapshot-completion.md`. Modified: `contracts.py`, `execution.py`, `broker_paper.py`, `ledger.py`, `paper_projections.py`, `paperOrderDraft.ts`, `paperDecisionProvenance.ts`, `paperOrderHistoryModel.ts`, `PaperOrderHistoryRow.tsx`, `ExecutionTracePanel.tsx`, `schemas.ts`, `paper-portfolio.css`, completion records. |
| **Tests** | `ui`: vitest **387 passed** (71 files); `npm run build` pass; initial bundle **199.17 KiB gzip**; `validate.py changed` **858 passed**; `validate.py full` **2968 passed** |
| **Related** | [Source snapshot completion](../superpowers/plans/2026-08-31-paper-decision-source-snapshot-completion.md), [Portfolio history](../superpowers/plans/2026-08-31-paper-portfolio-decision-history-completion.md) |
| **Notes** | `source_time` reserved but not populated (AttentionItem lacks timestamp). Lane snapshots omit headline unless added to draft later. Manual/legacy orders unchanged. No analytics attribution. |

---

## 2026-08-31 — Paper Portfolio operational decision history

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/paper-portfolio`, `ui/paper`, `backend/paper`, `ui/tests`, `docs` |
| **Summary** | Turned Paper Portfolio into the operational review surface for simulated decisions: backend `project_orders()` now preserves optional `correlation_id` and intent fields; frontend adds persisted provenance parser (lane/attention/manual/unknown with client-order default semantics), operational order history tables with badges/filters/metrics/expandable details, and always-available trace navigation aligned with `ExecutionTracePanel`. Demo/Live portfolio unchanged. |
| **Key files** | Created: `paper-portfolio/paperDecisionProvenance.ts`, `paperOrderHistoryModel.ts`, `paperOrderStatusPresentation.ts`, `PaperOrderHistory*.tsx`, `PaperDecisionProvenanceBadge.tsx`, tests, `docs/superpowers/plans/2026-08-31-paper-portfolio-decision-history-completion.md`. Modified: `paper/ledger.py`, `PaperPortfolioPage.tsx`, `PaperPortfolioObservability.tsx`, `ExecutionTracePanel.tsx`, `paper-portfolio.css`, `test_paper_p1.py`. |
| **Tests** | `ui`: vitest **374 passed** (70 files); `npm run build` pass; initial bundle **199.15 KiB gzip**; `validate.py changed` **704 passed**; `validate.py full` **2957 passed** |
| **Related** | [Portfolio history completion](../superpowers/plans/2026-08-31-paper-portfolio-decision-history-completion.md), [Handoff completion](../superpowers/plans/2026-08-31-paper-command-workspace-handoff-completion.md) |
| **Notes** | `sourceContext` remains UI-only for historical rows. Arbitrary correlation strings degrade to UNKNOWN. Manual orders detected when `correlation_id === client_order_id`. |

---

## 2026-08-31 — Paper Command → Workspace unified handoff

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/paper-now`, `ui/paper-workspace`, `ui/paper`, `ui/tests`, `docs` |
| **Summary** | Unified Paper Command attention handoff with lane-style workspace cockpit: `parsePaperDraftProvenance`, `createAttentionPaperOrderDraft`, `PaperHandoffPanel` (lane/attention/unknown), optional `sourceContext` on version-1 drafts, `correlation_id` on preview/submit for valid provenance, execution trace provenance display. Paper Command navigates with placeholder draft + source context; workspace revalidates preview against current state. |
| **Key files** | Created: `buildPaperHandoffModel.ts`, `PaperHandoffPanel.tsx`, tests, `docs/superpowers/plans/2026-08-31-paper-command-workspace-handoff-completion.md`. Modified: `paperOrderDraft.ts`, `PaperNowPage.tsx`, `PaperCandidateQueue.tsx`, `ModeNowRoute.tsx`, `PaperDecisionCockpit.tsx`, `PaperDecisionSnapshot.tsx`, `OrderTicket.tsx`, `ExecutionTracePanel.tsx`, `paper-workspace.css`, plan docs, `App.test.tsx`. Deleted: `buildLaneHandoffModel.ts`, `LaneHandoffPanel.tsx` (replaced by unified handoff). |
| **Tests** | `ui`: vitest **352 passed** (66 files); `npm run build` pass; initial bundle **199.16 KiB gzip**; `validate.py changed` pass (283 tests) |
| **Related** | [Handoff completion](../superpowers/plans/2026-08-31-paper-command-workspace-handoff-completion.md), [Decision cockpit completion](../superpowers/plans/2026-08-31-paper-workspace-decision-cockpit-completion.md) |
| **Notes** | No backend schema changes. `correlation_id` uses existing Paper API contract (`sourceAttentionId` when valid). `sourceContext` remains UI-only. |

---

## 2026-08-31 — Paper workspace decision cockpit

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/paper-workspace`, `ui/paper`, `ui/tests`, `docs` |
| **Summary** | Transformed Paper Workspace Overview into a decision cockpit with lane handoff panel, cross-lane decision snapshot (supports/contradicts/unclear/gaps), What Matters Now summary, compact Paper risk context, and first-class preview status synchronized from OrderTicket. Pure view-model helpers classify workspace evidence by direction; all 10 lane IDs supported with safe unknown-lane degradation. Demo/Live unchanged. |
| **Key files** | Created: `paper-workspace/buildLaneHandoffModel.ts`, `paperDecisionSemantics.ts`, `buildPaperDecisionSnapshot.ts`, `buildPaperRiskContext.ts`, `paperPreviewPresentation.ts`, `PaperDecisionCockpit.tsx`, `LaneHandoffPanel.tsx`, `PaperDecisionSnapshot.tsx`, `PaperWhatMattersNow.tsx`, `PaperRiskContext.tsx`, `PaperPreviewStatus.tsx`, tests, `docs/superpowers/plans/2026-08-31-paper-workspace-decision-cockpit-completion.md`. Modified: `PaperWorkspacePage.tsx`, `OrderTicket.tsx`, `paperOrderDraft.ts`, `paper-workspace.css`, `App.test.tsx`, related plan docs. |
| **Tests** | `ui`: vitest **343 passed** (66 files); `npm run build` pass; initial bundle **199.18 KiB gzip** |
| **Related** | [Decision cockpit completion](../superpowers/plans/2026-08-31-paper-workspace-decision-cockpit-completion.md), [Lane content completion](../superpowers/plans/2026-08-31-mode-specific-lane-content-completion.md) |
| **Notes** | No backend changes. Evidence API has 8 lanes — large-transactions/fund-etf documented as data gaps. `sourceAttentionId` remains UI-only. Preview invalidation on edit clears to NOT_PREVIEWED (fail-closed). |

---

## 2026-08-31 — Workspace lane mode-specific product content (all 10 lanes)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/workspace-modules`, `ui/paper`, `ui/tests`, `docs` |
| **Summary** | Added shared `ModeAwareWorkspaceLane` composition with `buildLaneModeContent` view models and `LaneModeContextPanel` for all 10 workspace lanes. Demo/Paper/Live now render distinct product context from existing API fields—not just shell chrome. Live lanes share `LiveLaneOperationalStrip` (canary snapshot + provider health, `queryKey: ["canary-snapshot"]`). Improved Paper lane draft UX with explicit BUY×1 placeholder notes, lane provenance banners on workspace overview and order ticket. |
| **Key files** | Created: `buildLaneModeContent.ts`, `LaneModeContextPanel.tsx`, `LiveLaneOperationalStrip.tsx`, `ModeAwareWorkspaceLane.tsx`, `laneModeContentTypes.ts`, `laneQueryState.ts`, tests, `docs/superpowers/plans/2026-08-31-mode-specific-lane-content-completion.md`. Modified: all 10 `*WorkspaceObservability.tsx`, all 10 `Mode*WorkspaceRoute.tsx`, `WorkspaceModuleModeShell.tsx`, `paperOrderDraft.ts`, `OrderTicket.tsx`, `PaperWorkspacePage.tsx`, `workspace-module-mode.css`, `App.test.tsx`, `ModeWorkspaceRoutes.test.tsx`. |
| **Tests** | `ui`: vitest **298 passed**; `npm run build` pass; bundle budget pass |
| **Related** | [Lane content completion](../superpowers/plans/2026-08-31-mode-specific-lane-content-completion.md), [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md) |
| **Notes** | No backend changes. Institutional/catalyst builders use actual schema fields (`families`, `catalyst_count`). Live operational strip avoids duplicate canary fetch via shared React Query key. |

---

## 2026-08-31 — UI hardening: settings gating, lane drafts, secondary route tests

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/settings`, `ui/workspace-modules`, `ui/tests`, `ui/live-canary` |
| **Summary** | Mode-gated operator settings (Demo/Live read-only; Paper mutations only). Added Paper lane → workspace draft shortcuts via `createLanePaperOrderDraft` and `Draft paper order from lane` link on all workspace modules. Added App integration tests for `/settings`, `/live-canary`, `/diagnostics/provider`, `/assistant/history`, and lane draft navigation. Consolidated all 10 `Mode*WorkspaceRoute` tests into `ModeWorkspaceRoutes.test.tsx`. Fixed Live Canary query-cache shape mismatch with Live Portfolio by sharing `fetchLiveCanarySnapshot`. |
| **Key files** | Created: `operator-settings/operatorSettingsMode.ts`, `OperatorSettingsPage.test.tsx`, `workspace-module-shared/ModeWorkspaceRoutes.test.tsx`. Modified: `OperatorSettingsPage.tsx`, `App.tsx`, `WorkspaceModuleModeShell.tsx`, `paperOrderDraft.ts`, `LiveCanaryControlPlanePage.tsx`, `App.test.tsx`. Deleted: `ModeSqueezeWorkspaceRoute.test.tsx`. |
| **Tests** | `ui`: vitest 283 passed; `npm run build` pass |
| **Related** | [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md) |
| **Notes** | Lane draft pre-fills workspace ticket when Paper authority is available; App tests verify navigation only under current context mock. |

---

## 2026-08-31 — App integration tests for remaining workspace lane modules

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/workspace-modules`, `ui/tests` |
| **Summary** | Extended `App.test.tsx` with table-driven integration tests for the seven remaining workspace lanes (order-book, futures, catalyst, fund-etf, large-transactions, disclosure, institutional-flow) across Demo, Paper, and Live modes. Added missing workspace query hook mocks. All 10 lane modules now have App-level coverage. |
| **Key files** | Modified: `ui/src/App.test.tsx` |
| **Tests** | `ui`: vitest 242 passed (App.test.tsx 52 tests) |
| **Related** | Prior entry "App integration tests for workspace overview and lane routes" |
| **Notes** | Uses `it.each(remainingWorkspaceLanes)` for DRY lane assertions via overview module nav. |

---

## 2026-08-31 — App integration tests for workspace overview and lane routes

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/workspace`, `ui/tests` |
| **Summary** | Added App-level integration tests for `/workspace/BIYA` overview and order-flow/options lane routes in Demo, Paper, and Live modes. Mocked `lightweight-charts` and `LiveMarketPanel` so workspace observability mounts in jsdom; added `ResizeObserver` stub and `useWorkspaceOptionsQuery` mock. |
| **Key files** | Modified: `ui/src/App.test.tsx` |
| **Tests** | `ui`: vitest 221 passed (App.test.tsx 31 tests) |
| **Related** | Prior entry "Workspace module mode copy + App squeeze integration tests" |
| **Notes** | Lane tests navigate via WORKSPACE nav → module nav. Overview tests use `/workspace` redirect to BIYA. |

---

## 2026-08-31 — Workspace module mode copy + App squeeze integration tests

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/workspace-modules` |
| **Summary** | Added per-module Paper and Live description hints via `workspaceModuleModeDescription`, a Paper simulation context note on `WorkspaceModuleModeShell`, and App-level integration tests navigating to `/workspace/GME/squeeze` in Demo, Paper, and Live modes. Extended unit tests for squeeze route and description utility. |
| **Key files** | Created: `workspace-module-shared/workspaceModuleModeDescription.ts`, `workspaceModuleModeDescription.test.ts`. Modified: all 10 `Mode*WorkspaceRoute.tsx`, `WorkspaceModuleModeShell.tsx`, `WorkspaceModuleModeShell.test.tsx`, `ModeSqueezeWorkspaceRoute.test.tsx`, `App.test.tsx`. |
| **Tests** | `ui`: vitest 212 passed; `npm run build` pass |
| **Related** | [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md), prior entry "Mode-specific workspace sub-modules" |
| **Notes** | Demo descriptions unchanged (shell restriction note covers Demo). Paper/Live hints are module-specific with sensible defaults. |

---

## 2026-08-31 — Mode-specific workspace sub-modules

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/workspace-modules` |
| **Summary** | Converted all 10 workspace lane sub-modules (squeeze, order-flow, order-book, futures, catalyst, fund-etf, options, large-transactions, disclosure, institutional-flow) to mode-aware routes via shared `WorkspaceModuleModeShell`. Each module now has `*WorkspaceObservability` (data + panel), `Mode*WorkspaceRoute`, and Demo/Paper/Live chrome with restriction notes, paper overview/portfolio links, and live canary link. Unified overview pages on full `WorkspaceModuleNav`. |
| **Key files** | Created: `workspace-module-shared/WorkspaceModuleModeShell.tsx`, `useWorkspaceInstrumentId.ts`, `styles/workspace-module-mode.css`, per-module `*Observability.tsx` and `Mode*Route.tsx`, tests. Modified: `App.tsx`, `demo-workspace/`, `paper-workspace/`, `live-workspace/`, `WorkspaceObservability.tsx`. Deleted: 10 legacy `*WorkspacePage.tsx` files. |
| **Tests** | `ui`: vitest 202 passed; `npm run build` pass |
| **Related** | [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md) |
| **Notes** | Paper modules link to workspace overview for order ticket. Overview nav now uses complete module list. |

---

## 2026-08-31 — Mode-specific Discover pages

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/discover` |
| **Summary** | Split shared `DiscoverPage` into Demo, Paper, and Live discover pages via `ModeDiscoverRoute`, with shared `DiscoverObservability`. Paper retains full discovery desk mutations (refresh, promote); Demo and Live are read-only with GET polling only and workspace links instead of promote POST. Added NavShell discover mode hints and App integration tests. |
| **Key files** | Created: `discover-shared/DiscoverObservability.tsx`, `demo-discover/`, `paper-discover/`, `live-discover/`, `ModeDiscoverRoute.tsx`, mode CSS files, per-mode tests. Modified: `NavShell.tsx`, `NavShell.test.tsx`, `App.tsx`, `App.test.tsx`, `layout.css`. Deleted: `DiscoverPage.tsx`, `DiscoverPage.test.tsx` (migrated to `PaperDiscoverPage.test.tsx`). |
| **Tests** | `ui`: vitest 198 passed; `npm run build` pass |
| **Related** | [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md) |
| **Notes** | All primary workstation routes now have mode-specific pages. |

---

## 2026-08-31 — Mode-specific Explore and Research pages + mode-aware NavShell

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/explore`, `ui/research`, `ui/nav` |
| **Summary** | Split shared `ExplorePage` and `ResearchPage` into Demo, Paper, and Live mode-specific pages via `ModeExploreRoute` and `ModeResearchRoute`, with shared `ExploreObservability` and `ResearchObservability`. Updated `NavShell` to accept session mode and show per-link hints and accessible labels. Added App integration tests for `/explore` and `/research` per mode. |
| **Key files** | Created: `explore-shared/ExploreObservability.tsx`, `demo-explore/`, `paper-explore/`, `live-explore/`, `ModeExploreRoute.tsx`, `research-shared/ResearchObservability.tsx`, `demo-research/`, `paper-research/`, `live-research/`, `ModeResearchRoute.tsx`, `NavShell.test.tsx`, mode CSS files, per-mode tests. Modified: `NavShell.tsx`, `App.tsx`, `App.test.tsx`, `layout.css`. Deleted: `ExplorePage.tsx`, `ResearchPage.tsx`. |
| **Tests** | `ui`: vitest 193 passed; `npm run build` pass |
| **Related** | [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md) |
| **Notes** | Discover remains a shared route. Paper Research defaults to Simulation tab. Live Explore shows `LiveObservationalPanel`. |

---

## 2026-08-31 — Enforce always-automatic work logging

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Strengthened work-logging Cursor rule (`alwaysApply: true`) and AGENTS/WORK_LOG wording so logging runs automatically every session without user prompts. |
| **Key files** | `.cursor/rules/work-logging.mdc`, `AGENTS.md`, `docs/engineering/WORK_LOG.md` |
| **Tests** | N/A |
| **Related** | User confirmation that logging must always happen automatically |

---

## 2026-08-31 — Work logging and documentation tracking

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `docs` |
| **Summary** | Introduced this work log, a mode-surfaces completion record, and a Cursor rule requiring automatic logging after substantive work. |
| **Key files** | `docs/engineering/WORK_LOG.md`, `docs/superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md`, `.cursor/rules/work-logging.mdc`, `AGENTS.md` |
| **Tests** | N/A (documentation only) |
| **Related** | User request to document all work and track future changes automatically |

---

## 2026-08-31 — Mode-specific workspace pages

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/workspace` |
| **Summary** | Split the monolithic `WorkspacePage` into Demo, Paper, and Live workspace pages with shared `WorkspaceObservability`, mirroring the portfolio and Now dashboard patterns. Paper retains order ticket and execution trace when authority passes; Demo and Live are read-only. |
| **Key files** | Created: `ui/src/components/workspace-shared/WorkspaceObservability.tsx`, `workspace-shared/workspaceHealth.ts`, `demo-workspace/DemoWorkspacePage.tsx`, `paper-workspace/PaperWorkspacePage.tsx`, `live-workspace/LiveWorkspacePage.tsx`, `ModeWorkspacePage.tsx`, `styles/demo-workspace.css`, `paper-workspace.css`, `live-workspace.css`, and per-mode tests. Modified: `WorkspaceRoute.tsx`, `App.tsx`. Deleted: `WorkspacePage.tsx`, `WorkspacePage.test.tsx`. |
| **Tests** | `ui`: vitest 177 passed; `npm run build` pass |
| **Related** | [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md), [Mode-aware workstation plan](../superpowers/plans/2026-08-30-mode-aware-workstation.md) |
| **Notes** | `WorkspaceRoute` still owns instrument/squeeze fetching and Paper draft handoff from router state. |

---

## 2026-08-31 — Mode-specific portfolio pages + App integration tests

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/portfolio` |
| **Summary** | Replaced single `PortfolioPage` with Demo (read-only simulated), Paper (full simulation controls), and Live (broker-observed canary data) portfolio pages via `ModePortfolioRoute`. Extended `LiveCanarySnapshot` for live portfolio fields. Added App-level `/portfolio` navigation tests per mode. |
| **Key files** | Created: `portfolio-shared/PaperPortfolioObservability.tsx`, `demo-portfolio/`, `paper-portfolio/`, `live-portfolio/`, `livePortfolioViewModel.ts`, `ModePortfolioRoute.tsx`, mode CSS files, tests. Modified: `App.tsx`, `App.test.tsx`, `live-now/liveCanarySnapshot.ts`. Deleted: `PortfolioPage.tsx`, `PortfolioPage.test.tsx`. |
| **Tests** | `App.test.tsx`: Demo/Paper/Live portfolio route tests; unit tests per mode page; vitest 177 passed |
| **Related** | [Mode-specific surfaces completion](../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md) |
| **Notes** | Live portfolio reads `/canary/snapshot` and `/canary/reconciliation`. Paper session/order controls still gated by `canUsePaperActions`. |

---

## 2026-08-31 — Live Now dashboard (“Live Watch”)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/now` |
| **Summary** | Replaced generic `NowPage` for Live mode with `LiveNowPage`: provider ribbon, safety/canary snapshot, symbol lookup, and read-only attention feed. Wired through `ModeNowRoute` with canary and provider health queries. |
| **Key files** | Created: `ui/src/components/live-now/` (`LiveNowPage.tsx`, `LiveProviderRibbon.tsx`, `LiveSafetySnapshot.tsx`, `LiveSymbolLookup.tsx`, `liveDashboardViewModel.ts`, `liveCanarySnapshot.ts`, fixtures, tests), `styles/live-now.css`. Modified: `ModeNowRoute.tsx`, `App.tsx`, `App.test.tsx`. |
| **Tests** | `LiveNowPage.test.tsx`, `liveDashboardViewModel.test.ts`, `App.test.tsx` Live mode integration |
| **Related** | [Demo Now plan](../superpowers/plans/2026-08-30-demo-now-dashboard.md), [Paper Now plan](../superpowers/plans/2026-08-31-paper-now-dashboard.md) |
| **Notes** | No separate design spec file; follows Demo/Paper Now patterns. |

---

## 2026-08-31 — Paper Now dashboard (“Paper Command”)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/now` |
| **Summary** | Paper-only Decision Canvas at `/`: risk ribbon, candidate queue, preview composer, and draft handoff to workspace `OrderTicket`. Shared `paperOrderDraft` contract between Now and workspace. |
| **Key files** | See [Paper Now implementation plan](../superpowers/plans/2026-08-31-paper-now-dashboard.md) file structure section |
| **Tests** | `PaperNowPage.test.tsx`, `paperOrderDraft.test.ts`, `PaperPanels.test.tsx`, `WorkspaceRoute.test.tsx`, `OrderTicket.test.tsx` |
| **Related** | [Paper Now plan](../superpowers/plans/2026-08-31-paper-now-dashboard.md), [Paper Now design](../superpowers/specs/2026-08-31-paper-now-dashboard-design.md) |

---

## 2026-08-30 — Demo Now dashboard (“See the market unfold”)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/now` |
| **Summary** | Demo-specific landing at `/` with BIYA replay controls, observational portfolio summary, attention feed, and inspect-next guidance. Introduced `ModeNowRoute` and reusable `AttentionFeed`. |
| **Key files** | See [Demo Now implementation plan](../superpowers/plans/2026-08-30-demo-now-dashboard.md) file structure section |
| **Tests** | `DemoNowPage.test.tsx`, `DemoReplayOverview.test.tsx`, `AttentionFeed.test.tsx`, `App.test.tsx` |
| **Related** | [Demo Now plan](../superpowers/plans/2026-08-30-demo-now-dashboard.md), [Demo Now design](../superpowers/specs/2026-08-30-demo-now-dashboard-design.md) |

---

## 2026-08-30 — Mode-aware workstation (launcher + gating)

| Field | Value |
|-------|-------|
| **Status** | `complete` |
| **Area** | `ui/mode-session` |
| **Summary** | Mode Launcher → session mode (Demo/Paper/Live) with fail-closed `modeAuthority`, persistent `ModeEnvironmentBar`, and gating on portfolio/workspace mutations. Replaced placeholder dashboards with full workstation shell. |
| **Key files** | See [Mode-aware workstation plan](../superpowers/plans/2026-08-30-mode-aware-workstation.md) |
| **Tests** | `modeAuthority.test.ts`, `ModeEnvironmentBar.test.tsx`, `ModeSession.test.tsx`, `App.test.tsx` |
| **Related** | [Mode-aware workstation design](../superpowers/specs/2026-08-30-mode-aware-workstation-design.md) |

---

## 2026-09-07 — G0 post-reconciliation baseline (Wave 0: truth + validation control plane)

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | governance supersession + `validate changed` correctness + repo truth + dev-system corrections |
| **Summary** | Executed G0 per `docs/audits/imp-reconciliation/19-goal-increment-plan.md` §2. Donor-governance records superseded in place (Heller correction; ADR-DONOR-001 handled via the hash-bound supersession notice); `validate changed` now normalizes the `projects/integrated-market-platform/` prefix, owns fixture/config/test-fixture paths by consumer evidence, renames `full_suite_required` → `core_checkpoint_required` with audit-grade `--explain`; short-squeeze snapshot reconciled to child `9de7b2f` with manifest + overlay; roadmap/program status refreshed to the authorized mandate; AGENTS.md states the canonical edit target; `imp.py env` exits non-zero on hard prereq failure; `donor_patterns/` + `tests/gridiq` annotated; empty pytest dir removed; child CI copies replaced with parent-CI pointers. |
| **Key files** | `tools/validate.py`, `tools/validation_manifest.{py,json}`, `tools/imp.py`, `AGENTS.md`, `docs/platform/{MASTER_ROADMAP,PROGRAM_STATUS}.md`, `workspace-manifest.json`, donor-governance docs, `docs/superpowers/governance/2026-09-07-donor-authority-supersession-notice.md` |
| **Tests** | `tests/validation/test_validate_selection.py` (+12 selection-semantics tests), `test_imp_cli.py` (+4 env exit tests), manifest/orchestration updates; full evidence in `docs/audits/imp-reconciliation/15-validation-evidence.md` (G0 section) |
| **Related** | Reconciliation master backlog (`docs/audits/imp-reconciliation/12-master-backlog.md`) BL-0001..0008, BL-0011; recovery roadmap (`13-recovery-roadmap.md`) Wave 0; root-cause register (`16-root-cause-register.md`) RC-012/013/014/020 — parent audit workspace, outside the IMP snapshot |

---

## 2026-09-07 — G1 canonical multi-asset identity foundation (Wave 1: identity slice)

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | `xa01/*`, `paper/contracts.py`, `xa04/codec.py`, identity tests + docs |
| **Summary** | Executed G1 per `docs/audits/imp-reconciliation/19-goal-increment-plan.md` §5. One canonical asset-class vocabulary: `XaAssetClass` gains `CRYPTO` and `BOND`; `InstrumentKind` gains `CRYPTO_PAIR`, `BOND`, `CONTINUOUS_SERIES`, `COMMODITY_SPOT`; `paper.contracts.ASSET_CLASSES` is deprecated as a backward-compat view. Added explicit `Tradability` semantics (TRADABLE / REFERENCE_ONLY / SYNTHETIC / CONTINUOUS_SERIES) on every canonical identity with a fail-closed guard (`xa01.tradability.assert_executable`, `xa01.resolver.resolve_executable_alias`, and `paper.contracts.build_user_order_intent` rejecting non-executable instrument refs). Added builders: `register_crypto_pair` (base/quote/venue/network), `register_bond` (issuer/CUSIP-ISIN/maturity/coupon/par/credit tier), `register_commodity_spot`, `register_commodity_proxy`, `register_continuous_futures_series`, plus `commodity_sector` on economic commodities. Serialization extended additively (XA-04 codec decodes legacy documents with safe defaults). No portfolio, risk, provider-live, or product-surface migration. |
| **Key files** | `src/market_platform_foundation/xa01/{enums,contracts,identity,compatibility,registry,resolver,errors,tradability}.py`, `src/market_platform_foundation/paper/contracts.py`, `src/market_platform_foundation/xa04/codec.py`, `tests/xa01/test_xa01_{crypto_identity,bond_identity,commodity_identity,tradability_guard,cross_asset_collisions,g1_serialization}.py`, XA-01 spec + MASTER_ARCHITECTURE/PROGRAM_STATUS updates |
| **Tests** | tests/xa01 71 passed (12 existing + 59 new); futures 65, options 147, contracts 38, xa02 21, xa03 31, xa04 30, xa05 15, platform paper/operational-identity 114 — all green; see `docs/audits/imp-reconciliation/15-validation-evidence.md` (G1 section) |
| **Related** | Master backlog BL-0101..0104 (updated in `12-master-backlog.md`); RC-004 materially advanced (16); recovery roadmap (`13`) Wave 1 identity slice; next dependent increment BL-0105 (G2 canonical multi-asset portfolio) remains NOT started |

---

## 2026-09-07 — G2 canonical multi-asset portfolio foundation (Wave 1: portfolio core, BL-0105)

| Field | Value |
|-------|-------|
| **Status** | `complete` (working tree; uncommitted alongside pre-existing dirty state) |
| **Area** | `portfolio/canonical.py`, `portfolio/{admission,valuation,fx,provider_normalization,paper_adapter}.py`, `tests/portfolio/*`, docs |
| **Summary** | Executed G2 per `docs/audits/imp-reconciliation/19-goal-increment-plan.md` (BL-0105). Established ONE canonical multi-asset portfolio model (`portfolio.canonical`) scoped by operational account + mode (`PortfolioKey`) and keyed by canonical XA-01 `instrument_id`, with explicit quantity units (SHARES/CONTRACTS/BASE_UNITS/FACE_VALUE), per-currency `CashBalance` (Decimal), a `ValuationMark` contract (currency + provenance + fresh/stale/missing), asset-aware valuation dispatch (equity qty×mark; options contracts×premium×multiplier; futures notional + mark-to-market P&L, never equity-style cash value; crypto base-units × pair price; bonds face × explicit price basis), an explicit FX conversion boundary (no 1:1 fallback; COMPLETE/PARTIAL/MISSING_FX/STALE aggregation), deterministic serialization, and a controlled mutation boundary (`apply_position_input` / `apply_snapshot` / `apply_cash` / `apply_adjustment`). Admission fails closed on reference identities via XA-01 tradability (continuous futures, family/root, economic commodities, spot references, benchmarks, currencies, FX pairs, reference-only bonds rejected). Provider snapshots normalize through XA-01 alias resolution with `UNRESOLVED_INSTRUMENT` fail-closed. Paper equity behavior preserved bit-identical via a dual-run read-side adapter (`paper_snapshot_to_canonical`) with parity tests; the legacy equity ledger remains the Paper execution parity baseline (BL-0106/0107 options/numeric merge remain separate follow-on items). |
| **Key files** | `src/market_platform_foundation/portfolio/{canonical,admission,valuation,fx,provider_normalization,paper_adapter}.py`, `src/market_platform_foundation/portfolio/__init__.py`, `tests/portfolio/test_{canonical_admission,cash_and_fx,valuation,isolation,provider_normalization,persistence,paper_parity}.py`, `tools/validation_manifest.json` (new `portfolio` suite), G2 portfolio spec (`docs/superpowers/specs/2026-09-07-imp-g2-canonical-multi-asset-portfolio-foundation.md`), `MASTER_ARCHITECTURE.md`, `PROGRAM_STATUS.md` |
| **Tests** | tests/portfolio 109 passed (admission 18, cash/FX 21, valuation 34, isolation 15, provider normalization 12, persistence 9, paper parity 7... exact per-suite counts in the FULL run); FAST 21 passed; phase7/platform regression green; see `docs/audits/imp-reconciliation/15-validation-evidence.md` (G2 section) |
| **Related** | Master backlog BL-0105 (`12-master-backlog.md`, updated); RC-001 materially advanced (16); recovery roadmap (`13`) Wave 1 portfolio core; BL-0106 (options ledger merge) and BL-0107 (futures Decimal) remain NOT started after G2 |

---

## Planned (not started)

| Item | Area | Notes |
|------|------|-------|
| Master-account login before Mode Launcher | `ui/auth` | User idea: single login provisions connected broker/data APIs; not concrete yet |
