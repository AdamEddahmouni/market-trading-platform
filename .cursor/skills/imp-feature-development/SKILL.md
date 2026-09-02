---
name: imp-feature-development
description: Implement an IMP feature with repository discovery, ownership-aware tests, progressive validation, safety preservation, and documented closure. Use when adding or extending IMP behavior.
---

# IMP feature development

1. Read root `AGENTS.md` and `docs/engineering/DEVELOPER_OPERATING_SYSTEM.md`.
2. Inspect the authoritative architecture, source/test ownership, and existing
   patterns before editing.
3. Write a focused regression or contract test first; run it through
   `python tools/imp.py test focused <selector>` when possible.
4. Implement the smallest coherent change. Keep authority in the backend and
   preserve Demo/Paper/Live separation, temporal semantics, persistence, and
   account identity.
5. Run `python tools/imp.py test affected`, then the relevant domain and UI
   checks. Do not run FULL after every edit.
6. Update authoritative docs and `docs/engineering/WORK_LOG.md`.
7. Use `python tools/imp.py closure` only at the final checkpoint.
