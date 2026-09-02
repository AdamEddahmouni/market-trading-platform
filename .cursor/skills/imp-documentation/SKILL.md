---
name: imp-documentation
description: Update IMP authoritative architecture, handbook, SOP, observability, and work-log documentation without duplicating governance. Use when documenting behavior or developer workflow changes.
---

# IMP documentation

1. Use `docs/README.md` to identify the authority for the changed behavior.
2. Update the smallest authoritative document; link to detail instead of
   copying architecture or safety prose into multiple guides.
3. Run `python tools/imp.py format` and
   `python tools/check_docs_links.py` when links or governance docs change.
4. Add a concise newest-first entry to `docs/engineering/WORK_LOG.md` with
   exact commands and baseline limitations.
5. Keep completion records historical and explicitly link them forward.
