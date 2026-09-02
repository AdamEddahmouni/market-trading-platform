---
name: imp-bug-fixing
description: Fix an IMP defect using reproduction-first debugging, a regression test, root-cause analysis, and affected validation. Use when correcting a bug or failed check.
---

# IMP bug fixing

1. Reproduce the symptom with the narrowest focused test or command.
2. Read `docs/engineering/sops/DEBUGGING.md`; preserve the current safety
   boundary while isolating the cause.
3. Add a regression test and observe the expected failure before changing code.
4. Fix the root cause without weakening validation, authority, or fixtures.
5. Run focused, then `python tools/imp.py test affected`; classify any existing
   dirty-tree failures as baseline.
6. Update the authoritative doc and work log when behavior or governance changed.
