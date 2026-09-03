# SOP: Dependency Update

## 1. Research release notes

Breaking changes, security advisories.

## 2. Check breaking changes

API removals, peer dependency shifts.

## 3. Update one logical group

e.g. all Testing Library packages together.

## 4. Targeted tests

`npm test` in `ui/`; Python unchanged unless tools touched.

## 5. Full validation

`npm run build` (bundle budget); `validate.py changed`.

## 6. Inspect bundle

Budget script output for regressions.

## 7. Security audit

`npm audit` — assess fix vs accept risk.

## 8. Document

WORK_LOG entry; update [DEPENDENCIES.md](../DEPENDENCIES.md) if strategic.

**Foundation:** do not add pip dependencies to `market_platform_foundation` without governance approval.
