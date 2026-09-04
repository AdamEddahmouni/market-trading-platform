---
name: imp-investigation
description: Investigate IMP behavior, failures, or architecture boundaries without making speculative changes. Use for repository audits, diagnosis, and evidence gathering.
---

# IMP investigation

1. Start with `python tools/imp.py env` and the root agent router.
2. Map the relevant authority, source roots, test owners, docs, and recent Git
   changes before forming a hypothesis.
3. Prefer focused selectors, `--explain`, and manifest metadata over full-suite
   execution during discovery.
4. Separate observed facts, hypotheses, baseline failures, and missing evidence.
5. Never enable live gates, fabricate data, or edit product behavior as part of
   an investigation unless the user explicitly requests implementation.
6. Record reusable findings in the requested report or authoritative doc.
