# IMP Documentation Index

**Status:** Authoritative navigation map (current state).  
**Repository:** Integrated Market Platform (IMP).

This index points to authoritative documents. It does not duplicate their contents.

## Documentation authority hierarchy

When documents disagree, resolve in this order (highest first):

1. **Safety invariants** — [MODE_AUTHORITY.md](architecture/MODE_AUTHORITY.md), [SECURITY.md](engineering/SECURITY.md), env gates in [CONFIGURATION.md](engineering/CONFIGURATION.md)
2. **Always-on agent operating rules** — repo-root `.cursor/rules/imp-*.mdc` and [AGENT_OPERATING_SYSTEM.md](engineering/AGENT_OPERATING_SYSTEM.md)
3. **[AGENTS.md](../AGENTS.md)** — agent entry point (plus repo-root `AGENTS.md`)
4. **Scoped agent files** — `ui/AGENTS.md`, `src/market_platform_foundation/paper/AGENTS.md`
5. **Architecture** — [ARCHITECTURE.md](architecture/ARCHITECTURE.md) and linked specs
6. **Engineering handbook & SOPs** — [ENGINEERING_HANDBOOK.md](engineering/ENGINEERING_HANDBOOK.md), [sops/](engineering/sops/)
7. **Current product/engineering specs** — `docs/superpowers/specs/`, BUILD specs in `docs/engineering/*_V1.md`
8. **Completion records** — `docs/superpowers/plans/*-completion.md` (historical snapshots of delivered work)
9. **Work log** — [WORK_LOG.md](engineering/WORK_LOG.md) (chronological change record)

If two documents at the same layer conflict, identify the conflict and reconcile
it in the authoritative doc — do not silently choose.

**Completion records are not automatically current architecture.** Verify against code and authoritative architecture docs.

| Class | Meaning |
|-------|---------|
| **Authoritative** | Describes current expected behavior; update when behavior changes |
| **Supporting** | Deep reference, BUILD specs, provider docs |
| **Historical** | Plans, completion records, ADRs — preserve; link forward to current docs |
| **Superseded** | Replaced; header points to replacement |

---

## Start here

| Topic | Document |
|-------|----------|
| What IMP is | [README.md](../README.md) |
| Agent operating system (models, parallelism, worktrees, handoff) | [AGENT_OPERATING_SYSTEM.md](engineering/AGENT_OPERATING_SYSTEM.md) |
| Current program status (git tip vs frozen collector vs historical pin) | [PROGRAM_STATUS.md](platform/PROGRAM_STATUS.md) |
| FTEP / Paper-validation doctrine | [IMP_SCOPE_FTEP_PAPER_VALIDATION_DOCTRINE.md](architecture/IMP_SCOPE_FTEP_PAPER_VALIDATION_DOCTRINE.md) |
| Developer operating system | [DEVELOPER_OPERATING_SYSTEM.md](engineering/DEVELOPER_OPERATING_SYSTEM.md) |
| Developer runbook (current commands) | [DEVELOPER_RUNBOOK.md](engineering/DEVELOPER_RUNBOOK.md) |
| Next US equity RTH campaign (current `main`) | [NEXT_RTH_CAMPAIGN_RUNBOOK.md](engineering/NEXT_RTH_CAMPAIGN_RUNBOOK.md) |
| RTH15-00 reconciliation target | [RTH15_00_TARGET_STATE.md](engineering/RTH15_00_TARGET_STATE.md) |
| RTH15-00 reconciliation matrix | [RTH15_00_RECONCILIATION_MATRIX.md](engineering/RTH15_00_RECONCILIATION_MATRIX.md) |
| Current agent handoff | [AGENT_HANDOFF.md](engineering/AGENT_HANDOFF.md) |
| Project status snapshot (2026-09-11 @ `a4858103`, **not** current campaign state) | [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| Pre-implementation planning closure | [PREIMPLEMENTATION_PLANNING_CLOSURE_2026-09-11.md](platform/PREIMPLEMENTATION_PLANNING_CLOSURE_2026-09-11.md) |
| FTEP activation gates | [FTEP_ACTIVATION_GATES.md](engineering/FTEP_ACTIVATION_GATES.md) |
| FTEP campaign catalog | [FTEP_CAMPAIGN_CATALOG.md](engineering/FTEP_CAMPAIGN_CATALOG.md) |
| FTEP-V1 activation blockers | [FTEP_V1_ACTIVATION_BLOCKER_REPORT.md](engineering/FTEP_V1_ACTIVATION_BLOCKER_REPORT.md) |
| Provider universe / audit / integration strategy | [PROVIDER_UNIVERSE_AUDIT_INTEGRATION_STRATEGY.md](providers/PROVIDER_UNIVERSE_AUDIT_INTEGRATION_STRATEGY.md) |
| Developer setup | [LOCAL_DEVELOPMENT.md](engineering/LOCAL_DEVELOPMENT.md) |
| System architecture | [ARCHITECTURE.md](architecture/ARCHITECTURE.md) |
| Demo / Paper / Live safety | [MODE_AUTHORITY.md](architecture/MODE_AUTHORITY.md) |
| Engineering rules | [ENGINEERING_HANDBOOK.md](engineering/ENGINEERING_HANDBOOK.md) |
| AI agent workflow | [AI_AGENT_GUIDE.md](engineering/AI_AGENT_GUIDE.md) |
| Work log | [WORK_LOG.md](engineering/WORK_LOG.md) |
| Terminology | [GLOSSARY.md](GLOSSARY.md) |

---

## Architecture

| Topic | Document |
|-------|----------|
| System overview | [ARCHITECTURE.md](architecture/ARCHITECTURE.md) |
| IMP scope / FTEP / Paper-validation doctrine | [IMP_SCOPE_FTEP_PAPER_VALIDATION_DOCTRINE.md](architecture/IMP_SCOPE_FTEP_PAPER_VALIDATION_DOCTRINE.md) |
| Market-data capability contract | [MARKET_DATA_CAPABILITY_CONTRACT.md](architecture/MARKET_DATA_CAPABILITY_CONTRACT.md) |
| Paper simulator calibration contract | [PAPER_SIMULATOR_CALIBRATION_CONTRACT.md](architecture/PAPER_SIMULATOR_CALIBRATION_CONTRACT.md) |
| Item 9 calibration protocol V1 | [ITEM9_CALIBRATION_PROTOCOL_V1.md](architecture/ITEM9_CALIBRATION_PROTOCOL_V1.md) |
| Common Opportunity Contract | [OPPORTUNITY_CONTRACT.md](architecture/OPPORTUNITY_CONTRACT.md) |
| Strategy readiness model | [STRATEGY_READINESS_MODEL.md](research/STRATEGY_READINESS_MODEL.md) |
| Mode authority (Demo/Paper/Live) | [MODE_AUTHORITY.md](architecture/MODE_AUTHORITY.md) |
| Paper decision lifecycle | [PAPER_DECISION_LIFECYCLE.md](architecture/PAPER_DECISION_LIFECYCLE.md) |
| Data contracts & timestamps | [DATA_CONTRACTS.md](architecture/DATA_CONTRACTS.md) |
| News/event foundation (deterministic) | [NEWS_EVENT_FOUNDATION.md](architecture/NEWS_EVENT_FOUNDATION.md) |
| News AI intelligence (analysis only) | [NEWS_AI_INTELLIGENCE.md](architecture/NEWS_AI_INTELLIGENCE.md) |
| Grok/agent intelligence ingest (analysis only) | [GROK_INTELLIGENCE_INGEST_API.md](architecture/GROK_INTELLIGENCE_INGEST_API.md) |
| News strategy evaluation laboratory | [NEWS_STRATEGY_EVALUATION.md](architecture/NEWS_STRATEGY_EVALUATION.md) |
| Paper forward-testing bridge | [PAPER_FORWARD_TESTING_BRIDGE.md](architecture/PAPER_FORWARD_TESTING_BRIDGE.md) |
| Forward-test experimental protocol (preregistered) | [FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md](engineering/FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md) |
| FTEP Core V1 | [FTEP_CORE_V1.md](engineering/ftep/FTEP_CORE_V1.md) |
| Futures FTEP profile V1 | [FUTURES_PROFILE_V1.md](engineering/ftep/assets/FUTURES_PROFILE_V1.md) |
| News/Catalyst FTEP profile V1 | [NEWS_CATALYST_PROFILE_V1.md](engineering/ftep/strategies/NEWS_CATALYST_PROFILE_V1.md) |
| FTEP campaign manifest template | [CAMPAIGN_MANIFEST_TEMPLATE_V1.md](engineering/ftep/CAMPAIGN_MANIFEST_TEMPLATE_V1.md) |
| FTEP-V1 owner decision packet (OD-1 … OD-11) | [FTEP-V1_OWNER_DECISION_PACKET.md](engineering/FTEP-V1_OWNER_DECISION_PACKET.md) |
| Threat model (lite) | [THREAT_MODEL.md](architecture/THREAT_MODEL.md) |
| Architecture decisions | [adr/README.md](architecture/adr/README.md) |
| Multi-source data foundation | [MULTI_SOURCE_DATA_FOUNDATION.md](providers/MULTI_SOURCE_DATA_FOUNDATION.md) |
| Foundation Revision 3 | [spec](superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-3.md) (Heller / GridIQ / DS-340W donor-authorization language superseded by the [Donor Authority Supersession Notice](superpowers/governance/2026-09-07-donor-authority-supersession-notice.md)) |
| Platformization | [roadmap](research/PLATFORMIZATION_ROADMAP.md) |

---

## Engineering

| Topic | Document |
|-------|----------|
| Handbook (primary reference) | [ENGINEERING_HANDBOOK.md](engineering/ENGINEERING_HANDBOOK.md) |
| Agent operating system | [AGENT_OPERATING_SYSTEM.md](engineering/AGENT_OPERATING_SYSTEM.md) |
| Frontend patterns | [FRONTEND_GUIDE.md](engineering/FRONTEND_GUIDE.md) |
| Backend patterns | [BACKEND_GUIDE.md](engineering/BACKEND_GUIDE.md) |
| Testing strategy | [TESTING.md](engineering/TESTING.md) |
| Validation commands | [VALIDATION.md](engineering/VALIDATION.md) |
| Validation system internals | [VALIDATION_ARCHITECTURE.md](engineering/VALIDATION_ARCHITECTURE.md) |
| Current workflow audit | [DEVELOPER_OPERATING_SYSTEM_AUDIT.md](engineering/DEVELOPER_OPERATING_SYSTEM_AUDIT.md) |
| Performance P0 forensic baseline | [performance-engineering-p0/](audits/performance-engineering-p0/README.md) |
| Definition of done | [DEFINITION_OF_DONE.md](engineering/DEFINITION_OF_DONE.md) |
| Coding standards | [CODING_STANDARDS.md](engineering/CODING_STANDARDS.md) |
| Dependencies | [DEPENDENCIES.md](engineering/DEPENDENCIES.md) |
| Stack inventory | [STACK.md](engineering/STACK.md) |
| Configuration / env vars | [CONFIGURATION.md](engineering/CONFIGURATION.md) |
| State path / worktree `.local` convention | [STATE_PATH_OPERATOR_CONVENTION.md](engineering/STATE_PATH_OPERATOR_CONVENTION.md) |
| Provider readiness | [PROVIDER_READINESS.md](engineering/PROVIDER_READINESS.md) |
| Operator probe runbook (FTEP-V1) | [OPERATOR_PROBE_RUNBOOK.md](engineering/OPERATOR_PROBE_RUNBOOK.md) |
| Performance & bundle budget | [PERFORMANCE.md](engineering/PERFORMANCE.md) |
| Accessibility | [ACCESSIBILITY.md](engineering/ACCESSIBILITY.md) |
| Observability & logging | [OBSERVABILITY.md](engineering/OBSERVABILITY.md) |
| Security | [SECURITY.md](engineering/SECURITY.md) |
| AI agent guide | [AI_AGENT_GUIDE.md](engineering/AI_AGENT_GUIDE.md) |
| AI model/tool strategy | [AI_MODEL_STRATEGY.md](engineering/AI_MODEL_STRATEGY.md) |
| Technical debt | [TECH_DEBT.md](engineering/TECH_DEBT.md) |
| P6 Shadow Run 1 protocol | [P6_SHADOW_RUN_1_PROTOCOL.md](engineering/P6_SHADOW_RUN_1_PROTOCOL.md) |
| Forward shadow qualification | [FORWARD_SHADOW_QUALIFICATION_V1.md](engineering/FORWARD_SHADOW_QUALIFICATION_V1.md) |

### SOPs

| SOP | Path |
|-----|------|
| Git worktrees / isolated implementation | [sops/GIT_WORKTREE.md](engineering/sops/GIT_WORKTREE.md) |
| Branch reconciliation onto current main | [sops/BRANCH_RECONCILIATION.md](engineering/sops/BRANCH_RECONCILIATION.md) |
| API / schema change | [sops/API_SCHEMA_CHANGE.md](engineering/sops/API_SCHEMA_CHANGE.md) |
| Frontend feature | [sops/FRONTEND_FEATURE.md](engineering/sops/FRONTEND_FEATURE.md) |
| Paper execution change | [sops/PAPER_EXECUTION_CHANGE.md](engineering/sops/PAPER_EXECUTION_CHANGE.md) |
| Add workspace lane | [sops/ADD_WORKSPACE_LANE.md](engineering/sops/ADD_WORKSPACE_LANE.md) |
| Add mode-aware surface | [sops/ADD_MODE_AWARE_SURFACE.md](engineering/sops/ADD_MODE_AWARE_SURFACE.md) |
| Debugging | [sops/DEBUGGING.md](engineering/sops/DEBUGGING.md) |
| Forward shadow validation (P6) | [sops/FORWARD_SHADOW_VALIDATION.md](engineering/sops/FORWARD_SHADOW_VALIDATION.md) |
| Dependency update | [sops/DEPENDENCY_UPDATE.md](engineering/sops/DEPENDENCY_UPDATE.md) |
| Release | [sops/RELEASE.md](engineering/sops/RELEASE.md) |
| Production bug fix | [sops/BUG_FIX.md](engineering/sops/BUG_FIX.md) |

### Checklists & templates

- [checklists/](engineering/checklists/) — quick verification lists
- [templates/](engineering/templates/) — completion, handoff, task contract, bug report
- [prompts/](engineering/prompts/) — reusable AI task templates

---

## Operations

| Topic | Document |
|-------|----------|
| Runbook | [operations/RUNBOOK.md](operations/RUNBOOK.md) |
| Provider docs | [providers/](providers/) |
| Provider universe / audit / integration strategy | [PROVIDER_UNIVERSE_AUDIT_INTEGRATION_STRATEGY.md](providers/PROVIDER_UNIVERSE_AUDIT_INTEGRATION_STRATEGY.md) |
| Provider integration foundation | [MULTI_SOURCE_DATA_FOUNDATION.md](providers/MULTI_SOURCE_DATA_FOUNDATION.md) |
| NewsAPI / Finnhub | [NEWS_SOURCES.md](providers/NEWS_SOURCES.md) |
| Tradier paper (fail-closed #41) | [TRADIER_PAPER.md](providers/TRADIER_PAPER.md) |
| Alpaca Paper comparator | [ALPACA_PAPER.md](providers/ALPACA_PAPER.md) |
| Cursor Cloud | [CURSOR_CLOUD_ENVIRONMENT.md](engineering/CURSOR_CLOUD_ENVIRONMENT.md) |

---

## Product

| Topic | Document |
|-------|----------|
| Mode-specific surfaces (completion) | [completion record](superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md) |
| UX wireframes | [product/ux/](product/ux/) |
| Product backlog | [PRODUCT_BACKLOG.md](product/PRODUCT_BACKLOG.md) |

---

## Research

| Topic | Document |
|-------|----------|
| Research Export v1 (PIT package + MATLAB handoff) | [RESEARCH_EXPORT_V1.md](research/RESEARCH_EXPORT_V1.md) |
| Strategy readiness model | [STRATEGY_READINESS_MODEL.md](research/STRATEGY_READINESS_MODEL.md) |

MATLAB consumes Research Export v1 JSON. The overnight Parquet-bridge blueprint is historical (`DEFER-MATLAB-BRIDGE`). Do not stamp `PIT-PASS` on fixture exports.

---

## Audits

| Topic | Document |
|-------|----------|
| Pre-implementation planning closure (2026-09-11) | [PREIMPLEMENTATION_PLANNING_CLOSURE_2026-09-11.md](platform/PREIMPLEMENTATION_PLANNING_CLOSURE_2026-09-11.md) |
| Post-G15 professor-directed CCN forensic audit | [post-g15-professor-directed/](audits/post-g15-professor-directed/README.md) |
| IMP reconciliation program (G0–G15) | [imp-reconciliation/](audits/imp-reconciliation/README.md) |
| Sep 15 live-integration test-gap matrix | [rth-live-integration-20260915/](audits/rth-live-integration-20260915/README.md) |
| Next-RTH source→operator latency catalog | [next-rth-source-operator-latency-20260915/](audits/next-rth-source-operator-latency-20260915/README.md) |
| UI/UX redesign v2 plan (implementation isolated) | [ui-redesign-v2/](ui-redesign-v2/README.md) |
| Donor-identity correction (GridIQ / DS-340W) | [Donor Authority Supersession Notice](superpowers/governance/2026-09-07-donor-authority-supersession-notice.md) |

---

## Historical

| Topic | Location |
|-------|----------|
| Implementation plans | `docs/superpowers/plans/` |
| Completion records | `docs/superpowers/plans/*-completion.md` |
| BUILD specifications | `docs/engineering/*_V1.md` |
| Phase evidence | `docs/engineering/EVIDENCE_01*.md` |
| ADRs | [architecture/adr/](architecture/adr/) |
| Sep 15 Item 7 upstream diagnosis | [ITEM7_UPSTREAM_GAP_DIAGNOSIS_20260915.md](engineering/ITEM7_UPSTREAM_GAP_DIAGNOSIS_20260915.md) |
| Sep 15 Item 9 kline P12 review | [ITEM9_KLINE_WINDOW_DIAGNOSIS_P12_REVIEW.md](engineering/ITEM9_KLINE_WINDOW_DIAGNOSIS_P12_REVIEW.md) |
| Sep 15 live OE P12/P13 reviews | [reviews/](engineering/reviews/) |
| Sep 15 Item 7 / provider drafts | [drafts/20260915-rth-runbook-item7-provider/](engineering/drafts/20260915-rth-runbook-item7-provider/README.md) |
