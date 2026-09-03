# SOP: Frontend Feature

For substantial UI work.

## 1. Inspect existing patterns

Find nearest `Mode*Route` / `*Observability` example.

## 2. Mode implications

Demo read-only? Paper actions? Live observational only?

## 3. Shared vs mode-specific

Extract observability; separate Demo/Paper/Live pages.

## 4. Pure view models

`build*` / `parse*` modules for non-trivial logic.

## 5. Implement states

Loading, empty, error, authority unavailable.

## 6. Authority check

`canUsePaperActions` for Paper mutations.

## 7. Accessibility

Labels, keyboard, semantic HTML — [ACCESSIBILITY.md](../ACCESSIBILITY.md).

## 8. Responsive design

Follow existing layout tokens.

## 9. Unit tests

Helpers and components.

## 10. App integration tests

`App.test.tsx` for new routes/modes.

## 11. Build / bundle

`npm run build` — budget gate.

## 12. Documentation / work log

Update guide if new pattern; WORK_LOG entry.

See [FRONTEND_FEATURE checklist](../checklists/UI_CHANGE.md).
