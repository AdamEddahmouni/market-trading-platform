# Accessibility

**Status:** UI expectations for IMP.

## Requirements

- Semantic HTML (`button`, `nav`, `main`, `table`, headings)
- Keyboard operability for interactive controls
- Visible focus indicators (theme tokens)
- Labels for form inputs (`htmlFor` / `aria-label`)
- Status messages use appropriate live regions where dynamic
- Control (`/control`): skip link first; hash deep-links move keyboard focus; loading uses `role="status"` / `aria-busy`; failures use `ErrorState` (`role="alert"`); empty/unavailable providers and feed stay distinct from calendar IDLE waits
- Tables: `th` scope, captions where helpful
- Modals/dialogs: focus trap and escape dismiss where implemented
- Non-modal popovers (`ui/src/lib/useDismiss.ts`): focus moves into the popover on open; Escape anywhere or a press outside closes it; keyboard closes return focus to the trigger
- Tab sets (`role="tablist"`, e.g. the Screener's right rail Preview | AI and Quick Preview's detail tabs): one tab in the Tab order; Left/Right/Home/End move and select; hidden panels keep their state. A shortcut that opens a tab (the AI strip's Open, the dock's Show in right rail) selects it and moves focus to its panel; Escape in the rail closes it and returns focus to the grid
- A tooltip never replaces a control's name: put hints in `aria-describedby`, not `title` on the control
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
