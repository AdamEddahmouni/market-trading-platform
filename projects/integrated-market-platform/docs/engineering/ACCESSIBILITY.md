# Accessibility

**Status:** UI expectations for IMP.

## Requirements

- Semantic HTML (`button`, `nav`, `main`, `table`, headings)
- Keyboard operability for interactive controls
- Visible focus indicators (theme tokens)
- Labels for form inputs (`htmlFor` / `aria-label`)
- Skip link to `#imp-main-content` in `ImpProductChrome`
- Status messages use appropriate live regions where dynamic
- Tables: `th` scope, captions where helpful
- Modals/dialogs: focus trap and escape dismiss where implemented (mobile nav, keyboard shortcuts, Live confirmation)
- Inspector and research assistant remain complementary panels (no focus trap)
- Color not sole indicator of state (use text/icons/badges)
- NavShell: `aria-label` on mode-specific link descriptions
- Global letter shortcuts skip `INPUT`, `TEXTAREA`, `SELECT`, `contenteditable`, and `role="combobox"`

## Shipped operator shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl/Cmd+K` | Focus command search |
| `/` | Focus command search |
| `A` | Toggle research assistant |
| `Esc` | Close shortcuts, mobile menu, or drawers |
| `?` | Keyboard shortcut list |

Mobile navigation (`<900px`) is a dialog: Escape dismisses it, Tab cycles inside it, and focus returns to **Menu**.

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
