# Definition of Done

**Status:** Authoritative DoD by change class.

## Documentation

- [ ] Authoritative doc updated if behavior/architecture changed
- [ ] [WORK_LOG.md](WORK_LOG.md) entry (substantive work)
- [ ] `python tools/imp.py test affected` and `python tools/check_docs_links.py`
- [ ] Completion record if large feature (`docs/superpowers/plans/*-completion.md`)
- [ ] No stale plan checkboxes claiming incomplete for shipped work
- [ ] `python tools/imp.py closure` / FULL are **not** required for docs-only PRs

## UI

- [ ] Matches mode-specific pattern if user-facing route
- [ ] Vitest for new logic/components
- [ ] `App.test.tsx` updated if routes/nav/handoffs change
- [ ] `npm run build` passes (bundle budget)
- [ ] Accessibility basics (labels, keyboard where interactive)
- [ ] `python tools/imp.py test affected`

## Backend

- [ ] Unittest coverage in manifest-owned suite
- [ ] Backward compatible schema unless migration authorized
- [ ] `validate.py changed`; `full` if cross-cutting

## Developer workflow

- [ ] Changes are classified by the validation pyramid
- [ ] `python tools/imp.py test affected` ran before closure
- [ ] Baseline failures are separated from newly introduced failures
- [ ] `artifacts/developer-workflow/closure-report.json` records final evidence

## API / schema

- [ ] Python type + parser + projection + Zod + JSON schema aligned
- [ ] Fixture/test payloads for old and new shapes
- [ ] Timestamp units verified
- [ ] [API_SCHEMA_CHANGE.md](sops/API_SCHEMA_CHANGE.md) checklist

## Paper execution / safety

- [ ] [PAPER_EXECUTION_CHANGE.md](sops/PAPER_EXECUTION_CHANGE.md) checklist
- [ ] Demo/Live leakage checked
- [ ] Authority loss / stale preview tests
- [ ] `python tools/imp.py validate full` + UI build

## Performance

- [ ] Bundle budget if frontend imports changed
- [ ] No eager heavy imports on entry path

## Release

- [ ] Clean tree (intentional changes only)
- [ ] `python tools/imp.py validate full`
- [ ] UI vitest + build
- [ ] [RELEASE.md](sops/RELEASE.md) checklist
- [ ] [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) if milestone
