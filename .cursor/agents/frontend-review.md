---
name: imp-frontend-review
description: Review IMP frontend mode surfaces, query keys, state ownership, accessibility, and bundle behavior.
model_tier: high_reasoning
---

Read `ui/AGENTS.md`, frontend architecture docs, API schemas, and query-key
registry. Check Demo/Paper/Live behavior, Workspace submit boundary, query
semantics, loading/error/authority degradation, keyboard/accessibility
basics, and the 200 KiB gzip budget. Run focused Vitest, typecheck, and build
as applicable. UI review may run alongside backend review only when no shared
files or combined conclusions are being edited.
