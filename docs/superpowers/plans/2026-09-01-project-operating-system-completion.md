# Project Operating System / Engineering Governance — Completion Record

> **Current architecture:** [docs/README.md](../../README.md) · [AGENTS.md](../../../AGENTS.md)

**Date:** 2026-09-01  
**Status:** Complete (historical delivery record)  
**Tracking:** [WORK_LOG.md](../../engineering/WORK_LOG.md)

## Objective

Transform IMP into a self-describing, self-governing engineering system for human developers and AI agents — without documentation bloat.

## Audit findings

- Governance handbook set was **largely absent**; authority scattered across README, AGENTS (validation-only), BUILD specs, and completion records
- Mode-specific UI and Paper lifecycle were implemented but not consolidated in architecture docs
- WORK_LOG links used broken relative paths (`superpowers/` without `../`)
- CI ran Python `fast`+`changed` only — no UI vitest/build gate
- Repository closure inventory required registration for new tooling

## Authoritative docs created

### Index & status

- `docs/README.md`, `docs/PROJECT_STATUS.md`, `docs/GLOSSARY.md`

### Architecture

- `docs/architecture/ARCHITECTURE.md`, `MODE_AUTHORITY.md`, `PAPER_DECISION_LIFECYCLE.md`, `DATA_CONTRACTS.md`, `THREAT_MODEL.md`
- `docs/architecture/adr/` — README, template, ADRs 0001–0005

### Engineering

- Handbook, FRONTEND_GUIDE, BACKEND_GUIDE, TESTING, VALIDATION, DEFINITION_OF_DONE
- CODING_STANDARDS, DEPENDENCIES, STACK, SECURITY, CONFIGURATION, LOCAL_DEVELOPMENT
- PERFORMANCE, ACCESSIBILITY, OBSERVABILITY, AI_AGENT_GUIDE, AI_MODEL_STRATEGY, TECH_DEBT

### SOPs, checklists, templates, prompts

- 9 SOPs, 4 checklists, 3 templates, 6 prompt templates

### Operations & product

- `docs/operations/RUNBOOK.md`, `docs/product/PRODUCT_BACKLOG.md`

## AGENTS & rules

- Overhauled root `AGENTS.md` (mission, safety, validation, doc map)
- Added `ui/AGENTS.md`, `src/market_platform_foundation/paper/AGENTS.md`
- Cursor rules: inspect-before-edit, no-fabricated-data, authoritative-docs, react-query-keys, mode-authority-ui, paper-execution-safety
- Strengthened `work-logging.mdc`

## Automation & CI

- `tools/check_docs_links.py` — governance doc link checker
- CI: added `validate-ui` job (npm ci, test, build); docs link check in Python job
- Registered `check_docs_links.py` in closure inventory + validation manifest

## GitHub

- PR template, bug and safety issue templates

## Stale docs resolved

- README: concise doc entry + mode summary
- WORK_LOG: fixed 30 broken `superpowers/` relative links
- Source-time and source-snapshot completion records: forward links to `PAPER_DECISION_LIFECYCLE.md`

## Files intentionally not created

- `CHANGELOG.md` — WORK_LOG + completion records sufficient
- `CODEOWNERS` — no maintainer roster
- `MIGRATION.md` SOP — no formal DB migration framework; expectations in BACKEND_GUIDE
- Lane/mode canonical registries — duplication risk low; documented in guides
- Mass ADR backfill — only 5 high-value ADRs

## Incorporated source-time semantics

From [source-time completion](2026-09-01-paper-decision-source-time-completion.md):

- `source_time` in DATA_CONTRACTS, PAPER_DECISION_LIFECYCLE, GLOSSARY, API SOP timestamp checks

## Validation

| Suite | Result |
|-------|--------|
| Vitest | **403 passed** (73 files) |
| `npm run build` | pass; **199.17 KiB gzip** |
| `check_docs_links.py` | pass (after this record) |
| Closure audit test | pass |
| `validate.py changed` | re-run after closure inventory fix — **859 passed** |
| `validate.py full` | **2969 passed**, 34 skipped |

## Maintenance model

- Update authoritative docs when behavior changes (not only WORK_LOG)
- `PROJECT_STATUS.md` at milestones
- `TECH_DEBT.md` for concrete debts
- Re-run `check_docs_links.py` when adding governance docs

## Next step

Product increment of choice from [PRODUCT_BACKLOG.md](../../product/PRODUCT_BACKLOG.md) — e.g. Paper history pagination (TD-001).
