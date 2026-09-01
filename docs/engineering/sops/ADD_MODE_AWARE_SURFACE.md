# SOP: Add Mode-Aware Surface

## 1. Route wrapper

Create `Mode{Surface}Route.tsx` switching on `session.mode`.

## 2. Pages

`Demo{Surface}Page`, `Paper{Surface}Page`, `Live{Surface}Page`.

## 3. Shared primitives

Extract `*{Surface}Observability` from duplicated tables/metrics.

## 4. Styles

`demo-{surface}.css`, `paper-{surface}.css`, `live-{surface}.css`.

## 5. Wire App.tsx

Replace or add route; lazy if heavy.

## 6. NavShell

Mode hints and `aria-label` if primary nav item.

## 7. Authority

Paper: `canUsePaperActions`; Live: no mutations; Demo: read-only.

## 8. Tests

`App.test.tsx` — navigate surface in each mode.

## 9. Validation

vitest + build + validate changed.

Reference: [mode-specific surfaces completion](../../superpowers/plans/2026-08-31-mode-specific-surfaces-completion.md).
