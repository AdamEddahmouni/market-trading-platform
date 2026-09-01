# IMP Work Log

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

## Planned (not started)

| Item | Area | Notes |
|------|------|-------|
| Master-account login before Mode Launcher | `ui/auth` | User idea: single login provisions connected broker/data APIs; not concrete yet |
