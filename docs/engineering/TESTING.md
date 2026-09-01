# Testing Strategy

**Status:** Authoritative test hierarchy for IMP.

## Test layers

| Layer | Location | Tool | When |
|-------|----------|------|------|
| Pure helpers | `ui/src/**/*.test.ts` | Vitest | View models, parsers, semantics |
| Components | `ui/src/**/*.test.tsx` | Vitest + Testing Library | UI behavior, a11y basics |
| App integration | `ui/src/App.test.tsx` | Vitest | Route navigation, mode switching, handoffs |
| Backend unit | `tests/**` | unittest via validate.py | Domain, projections, paper |
| Boundary / integration | `tests/integration`, live suites | unittest | Provider boundaries (opt-in live) |
| Repository validators | `tools/validate.py` | manifest | CI and local gates |
| Invariants | manifest mandatory selectors | fast/changed | Catastrophic regressions |

## What belongs where

- **Frontend boundary** — Vitest only (`cd ui && npm test`). Not in Python FULL claim for UI package.
- **API contract** — backend tests + frontend schema/hook tests when UI consumes
- **Paper safety** — backend authority tests + UI `canUsePaperActions` + OrderTicket preview tests
- **Mode coverage** — App.test navigates Demo/Paper/Live for primary routes

## Regression rule

Every real bug fix requires a regression test **where practical**. Safety-sensitive bugs **must** have regression coverage.

## Mode rule

Safety-sensitive surfaces require Demo/Paper/Live test coverage (at minimum App integration navigation; deeper for mutations).

## Paper rule

Execution workflow changes require authority-loss and fail-closed coverage (preview stale, authority unavailable).

## Running tests

```powershell
# Frontend
cd ui
npm test
npm run build   # includes bundle budget

# Backend (from repo root)
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py changed
.venv\Scripts\python.exe tools\validate.py full    # checkpoint
```

See [VALIDATION.md](VALIDATION.md).

## Fixtures

Admitted fixtures under `evidence/`, `tests/fixtures/`. Never use live credentials in committed fixtures.

## Live tests

Opt-in: `python tools/validate.py live <provider>`. Never in default CI.
