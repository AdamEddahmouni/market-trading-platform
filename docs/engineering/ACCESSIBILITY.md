# Accessibility

**Status:** UI expectations for IMP.

## Requirements

- Semantic HTML (`button`, `nav`, `main`, `table`, headings)
- Keyboard operability for interactive controls
- Visible focus indicators (theme tokens)
- Labels for form inputs (`htmlFor` / `aria-label`)
- Status messages use appropriate live regions where dynamic
- Tables: `th` scope, captions where helpful
- Modals/dialogs: focus trap and escape dismiss where implemented
- Color not sole indicator of state (use text/icons/badges)
- NavShell: `aria-label` on mode-specific link descriptions

## Mode-specific copy

Restriction notes must be readable and not rely on color alone (Demo read-only, Live no submit).

## Testing

- Testing Library queries prefer `getByRole`, `getByLabelText`
- Avoid testing implementation details only

## UI Definition of Done

- [ ] Interactive elements keyboard reachable
- [ ] Images/icons decorative or labeled
- [ ] Error states announced or visible in text

See [checklists/UI_CHANGE.md](checklists/UI_CHANGE.md).
