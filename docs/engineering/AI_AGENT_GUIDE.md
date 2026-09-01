# AI Agent Guide

**Status:** Workflow guide for Cursor/Composer sessions.

## First reads (new session)

1. [AGENTS.md](../../AGENTS.md)
2. [docs/README.md](../README.md)
3. [MODE_AUTHORITY.md](../architecture/MODE_AUTHORITY.md) if touching Paper/Live
4. [WORK_LOG.md](WORK_LOG.md) — recent changes (newest first)

## Establish baseline

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py changed
cd ui && npm test
```

Inspect relevant code before editing — search for existing patterns.

## Inspect before creating

- Mode pages: find existing `Mode*Route` / `Demo|Paper|Live*Page`
- APIs: `ui/src/api/`, `ui_api/`, `manifests/ui1/schemas/`
- Paper: `paper/`, `paper-workspace/`, `paperOrderDraft.ts`
- Query keys: `hooks.ts` `queryKeys`

## Never assume completion reports are current

Verify repository state. Completion records are historical snapshots.

## Never invent APIs or data

Read schemas. No fabricated market prices or authority.

## Never weaken tests to pass

Fix root cause. Add regression test for bugs.

## Safe autonomous changes

- Clear bugs with tests
- Docs aligned to actual code
- Consistency fixes following existing patterns
- Low-risk refactors with test coverage

## Requires explicit user/product direction

- Live production execution authority
- Destructive migrations
- Security model changes
- New external providers
- Trading semantics changes
- Removing safety gates

## Documentation

Substantive work → [WORK_LOG.md](WORK_LOG.md) before ending turn (enforced by Cursor rule).

## Validation reporting

Report exact commands and results — never claim tests you did not run.

## Large tasks

1. Audit relevant docs and code
2. Implement in coherent increments
3. Validate each increment
4. Update authoritative docs (not only completion record)
5. Work log entry per increment

## Avoid duplicate architecture

Link to [ARCHITECTURE.md](../architecture/ARCHITECTURE.md) and handbooks — do not create parallel spec files.

## Prompt templates

Reusable task starters: [prompts/](prompts/)

## Model selection

[AI_MODEL_STRATEGY.md](AI_MODEL_STRATEGY.md)

## Handoff

Long sessions: [templates/AGENT_HANDOFF.md](templates/AGENT_HANDOFF.md)
