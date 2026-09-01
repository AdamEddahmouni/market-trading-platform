# Definition of Done

**Status:** Authoritative DoD by change class.

## Documentation

- [ ] Authoritative doc updated if behavior/architecture changed
- [ ] [WORK_LOG.md](WORK_LOG.md) entry (substantive work)
- [ ] Completion record if large feature (`docs/superpowers/plans/*-completion.md`)
- [ ] No stale plan checkboxes claiming incomplete for shipped work

## UI

- [ ] Matches mode-specific pattern if user-facing route
- [ ] Vitest for new logic/components
- [ ] `App.test.tsx` updated if routes/nav/handoffs change
- [ ] `npm run build` passes (bundle budget)
- [ ] Accessibility basics (labels, keyboard where interactive)
- [ ] `validate.py changed`

## Backend

- [ ] Unittest coverage in manifest-owned suite
- [ ] Backward compatible schema unless migration authorized
- [ ] `validate.py changed`; `full` if cross-cutting

## API / schema

- [ ] Python type + parser + projection + Zod + JSON schema aligned
- [ ] Fixture/test payloads for old and new shapes
- [ ] Timestamp units verified
- [ ] [API_SCHEMA_CHANGE.md](sops/API_SCHEMA_CHANGE.md) checklist

## Paper execution / safety

- [ ] [PAPER_EXECUTION_CHANGE.md](sops/PAPER_EXECUTION_CHANGE.md) checklist
- [ ] Demo/Live leakage checked
- [ ] Authority loss / stale preview tests
- [ ] `validate.py full` + UI build

## Performance

- [ ] Bundle budget if frontend imports changed
- [ ] No eager heavy imports on entry path

## Release

- [ ] Clean tree (intentional changes only)
- [ ] `validate.py full`
- [ ] UI vitest + build
- [ ] [RELEASE.md](sops/RELEASE.md) checklist
- [ ] [PROJECT_STATUS.md](../PROJECT_STATUS.md) if milestone
