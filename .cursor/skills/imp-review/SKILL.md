---
name: imp-review
description: Review IMP changes for correctness, safety, ownership, tests, documentation, and frontend state behavior. Use before closure or when reviewing a diff.
---

# IMP review

1. Inspect the complete diff and `python tools/imp.py review`.
2. Check domain-specific risks: risk authority, execution boundaries, account
   identity, Demo/Paper/Live isolation, source-time semantics, append-only
   persistence, and frontend query/state behavior.
3. Confirm changed files have manifest ownership or an intentional docs/tooling
   classification.
4. Confirm tests prove behavior rather than merely implementation details.
5. Report findings by severity with exact file references. Do not silently fix
   unrelated issues or mark baseline failures as regressions.
