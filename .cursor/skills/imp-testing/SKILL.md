---
name: imp-testing
description: Select and run the cheapest safe IMP validation, including focused selectors, affected suites, domain gates, UI checks, and evidence interpretation. Use when testing or verifying changes.
---

# IMP testing

- Use `python tools/imp.py test focused <selector>` for a known regression.
- Use `python tools/imp.py test affected --workers 2` for ordinary changes.
- Use `python tools/imp.py validate domain <name>` at domain milestones.
- Use `python tools/imp.py validate full` once at final closure or for
  cross-cutting safety changes.
- UI changes also require `cd ui && npm test`, `npm run typecheck`, and
  `npm run build`.
- Docs changes require `tools/check_docs_links.py`.
- Treat `full_suite_required=true` as a required later FULL gate.
- Preserve exact counts, skips, failures, errors, and baseline classification.
