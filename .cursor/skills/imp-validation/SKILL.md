---
name: imp-validation
description: Discover and run the cheapest safe IMP validation for a change, report exact commands and results, and distinguish new failures from baseline or environment limits. Use when testing, verifying, or claiming a change works.
---

# IMP validation

Never claim a check that was not run. Nested IMP command details also live in
`projects/integrated-market-platform/.cursor/skills/imp-testing/SKILL.md`.

## Choose the cheapest safe stage

From IMP root (`projects/integrated-market-platform`):

1. `python tools/imp.py env` — interpreter/worktree/gates
2. `python tools/imp.py test focused <selector>` — known regression
3. `python tools/imp.py test affected` — ordinary code change
4. `python tools/imp.py validate changed` — canonical affected + cheap checks
5. `python tools/imp.py validate domain <name>` — domain milestone
6. `python tools/imp.py validate full` / `closure` — once at a real checkpoint

UI: `cd ui && npm test && npm run typecheck && npm run build`.
Docs: `python tools/check_docs_links.py`.
Format: `python tools/imp.py format`.

`core_checkpoint_required=true` is a later FULL gate, not permission to skip it.

## Report

```markdown
# Validation
- commands: ...
- result: passed/failed/skipped counts, exit code
- baseline vs new: ...
- not run: ...
- environment limits: ...
```

## Honesty

- Failed stays failed until genuinely resolved.
- Dirty-tree baseline failures are baseline, not new regressions — and not success.
- Credential, tzdata, missing vendor SDK, or cloud-provider absence is
  `ENVIRONMENT` / `UNAVAILABLE`, not a product pass.
- Do not weaken tests, skip gates, or edit the validation manifest to make work look green.
