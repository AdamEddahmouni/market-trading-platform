# IMP Documentation Index

**Status:** Authoritative navigation map (current state).  
**Repository:** Integrated Market Platform (IMP).

This index points to authoritative documents. It does not duplicate their contents.

## Documentation authority hierarchy

When documents disagree, resolve in this order (highest first):

1. **Safety invariants** — [MODE_AUTHORITY.md](architecture/MODE_AUTHORITY.md), [SECURITY.md](engineering/SECURITY.md), env gates in [CONFIGURATION.md](engineering/CONFIGURATION.md)
2. **[AGENTS.md](../AGENTS.md)** — agent entry point
3. **Scoped agent files** — `ui/AGENTS.md`, `src/market_platform_foundation/paper/AGENTS.md`
4. **Architecture** — [ARCHITECTURE.md](architecture/ARCHITECTURE.md) and linked specs
5. **Engineering handbook & SOPs** — [ENGINEERING_HANDBOOK.md](engineering/ENGINEERING_HANDBOOK.md), [sops/](engineering/sops/)
6. **Current product/engineering specs** — `docs/superpowers/specs/`, BUILD specs in `docs/engineering/*_V1.md`
7. **Completion records** — `docs/superpowers/plans/*-completion.md` (historical snapshots of delivered work)
8. **Work log** — [WORK_LOG.md](engineering/WORK_LOG.md) (chronological change record)

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
| Current status & roadmap | [PROJECT_STATUS.md](PROJECT_STATUS.md) |
| Pre-implementation planning closure | [PREIMPLEMENTATION_PLANNING_CLOSURE_2026-09-11.md](platform/PREIMPLEMENTATION_PLANNING_CLOSURE_2026-09-11.md) |
| FTEP / Paper-validation doctrine | [IMP_SCOPE_FTEP_PAPER_VALIDATION_DOCTRINE.md](architecture/IMP_SCOPE_FTEP_PAPER_VALIDATION_DOCTRINE.md) |
| FTEP activation gates | [FTEP_ACTIVATION_GATES.md](engineering/FTEP_ACTIVATION_GATES.md) |
| Developer setup | [LOCAL_DEVELOPMENT.md](engineering/LOCAL_DEVELOPMENT.md) |
| System architecture | [ARCHITECTURE.md](architecture/ARCHITECTURE.md) |
| Developer operating system | [DEVELOPER_OPERATING_SYSTEM.md](engineering/DEVELOPER_OPERATING_SYSTEM.md) |
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
| Common Opportunity Contract | [OPPORTUNITY_CONTRACT.md](architecture/OPPORTUNITY_CONTRACT.md) |
| Strategy readiness model | [STRATEGY_READINESS_MODEL.md](research/STRATEGY_READINESS_MODEL.md) |
| Mode authority (Demo/Paper/Live) | [MODE_AUTHORITY.md](architecture/MODE_AUTHORITY.md) |
| Paper decision lifecycle | [PAPER_DECISION_LIFECYCLE.md](architecture/PAPER_DECISION_LIFECYCLE.md) |
| Data contracts & timestamps | [DATA_CONTRACTS.md](architecture/DATA_CONTRACTS.md) |
| News/event foundation (deterministic) | [NEWS_EVENT_FOUNDATION.md](architecture/NEWS_EVENT_FOUNDATION.md) |
| News AI intelligence (analysis only) | [NEWS_AI_INTELLIGENCE.md](architecture/NEWS_AI_INTELLIGENCE.md) |
| News strategy evaluation laboratory | [NEWS_STRATEGY_EVALUATION.md](architecture/NEWS_STRATEGY_EVALUATION.md) |
| Paper forward-testing bridge | [PAPER_FORWARD_TESTING_BRIDGE.md](architecture/PAPER_FORWARD_TESTING_BRIDGE.md) |
| Forward-test experimental protocol (preregistered) | [FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md](engineering/FORWARD_TEST_EXPERIMENTAL_PROTOCOL_V1.md) |
| FTEP Core V1 | [FTEP_CORE_V1.md](engineering/ftep/FTEP_CORE_V1.md) |
| Futures FTEP profile V1 | [FUTURES_PROFILE_V1.md](engineering/ftep/assets/FUTURES_PROFILE_V1.md) |
| News/Catalyst FTEP profile V1 | [NEWS_CATALYST_PROFILE_V1.md](engineering/ftep/strategies/NEWS_CATALYST_PROFILE_V1.md) |
| FTEP campaign manifest template | [CAMPAIGN_MANIFEST_TEMPLATE_V1.md](engineering/ftep/CAMPAIGN_MANIFEST_TEMPLATE_V1.md) |
| Threat model (lite) | [THREAT_MODEL.md](architecture/THREAT_MODEL.md) |
| Architecture decisions | [adr/README.md](architecture/adr/README.md) |
| Multi-source data foundation | [MULTI_SOURCE_DATA_FOUNDATION.md](providers/MULTI_SOURCE_DATA_FOUNDATION.md) |
| Foundation Revision 3 | [spec](superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-3.md) |
| Platformization | [roadmap](research/PLATFORMIZATION_ROADMAP.md) |

---

## Engineering

| Topic | Document |
|-------|----------|
| Handbook (primary reference) | [ENGINEERING_HANDBOOK.md](engineering/ENGINEERING_HANDBOOK.md) |
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
| Provider readiness | [PROVIDER_READINESS.md](engineering/PROVIDER_READINESS.md) |
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
- [templates/](engineering/templates/) — completion, handoff, bug report
- [prompts/](engineering/prompts/) — reusable AI task templates

---

## Operations

| Topic | Document |
|-------|----------|
| Runbook | [operations/RUNBOOK.md](operations/RUNBOOK.md) |
| Provider docs | [providers/](providers/) |
| Provider integration foundation | [MULTI_SOURCE_DATA_FOUNDATION.md](providers/MULTI_SOURCE_DATA_FOUNDATION.md) |
| NewsAPI / Finnhub | [NEWS_SOURCES.md](providers/NEWS_SOURCES.md) |
| Cursor Cloud | [CURSOR_CLOUD_ENVIRONMENT.md](engineering/CURSOR_CLOUD_ENVIRONMENT.md) |

---

## Product

| Topic | Document |
|-------|----------|
| Mode-specific surfaces (completion) | [completion record](superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md) |
| UX wireframes | [product/ux/](product/ux/) |
| Product backlog | [PRODUCT_BACKLOG.md](product/PRODUCT_BACKLOG.md) |

---

## Audits

| Topic | Document |
|-------|----------|
| Pre-implementation planning closure (2026-09-11) | [PREIMPLEMENTATION_PLANNING_CLOSURE_2026-09-11.md](platform/PREIMPLEMENTATION_PLANNING_CLOSURE_2026-09-11.md) |
| Post-G15 professor-directed CCN forensic audit | [post-g15-professor-directed/](audits/post-g15-professor-directed/README.md) |
| IMP reconciliation program (G0–G15) | [imp-reconciliation/](audits/imp-reconciliation/README.md) |

---

## Historical

| Topic | Location |
|-------|----------|
| Implementation plans | `docs/superpowers/plans/` |
| Completion records | `docs/superpowers/plans/*-completion.md` |
| BUILD specifications | `docs/engineering/*_V1.md` |
| Phase evidence | `docs/engineering/EVIDENCE_01*.md` |
| ADRs | [architecture/adr/](architecture/adr/) |
