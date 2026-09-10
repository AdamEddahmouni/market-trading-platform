# Notion Development Lifecycle (IMP)

**Status:** Authoritative developer-operating-system rule (P0 formalization)  
**Scope:** Planning, task state, internship evidence — not implementation truth

## Authority model

| Layer | Role |
|-------|------|
| Local working tree | Current implementation truth |
| Accepted Git history / remote | Source-control truth |
| Tests / validation artifacts | Software acceptance evidence |
| Notion | Planning, roadmap, human context, internship evidence |

If Notion disagrees with the repository, verify code, Git, and validation first,
then update Notion to match verified truth. Document material discrepancies.

## Substantial task startup

When Notion MCP/tools are authenticated:

1. Identify the IMP task and lane (professor-directed vs performance/enabling).
2. Read the **minimum relevant** pages (task, current week slice, roadmap entry).
3. Compare Notion status to local Git/working-tree state.
4. Flag mismatches; proceed from repository truth.
5. Read applicable `AGENTS.md`, rules, and architecture entry docs for the scope.

Do **not** load the entire Notion workspace.

Expected page families (names may vary):

- Integrated Market Platform / Current Status & Roadmap
- Professor-Directed Priority Program
- Performance Engineering & Test Efficiency Program
- Sync Status — Local ↔ GitHub ↔ Notion
- IMP Task Tracker / Current Week

## Material task closure

1. Gather actual implementation state from the working tree.
2. Gather exact validation evidence (command, counts, wall time, caveats).
3. Update the task and materially affected roadmap/week/log pages.
4. Never invent status or fabricate Notion access.
5. Report connector failure as `NOTION_SYNC_BLOCKED` with intended updates.

## Milestone chain

```
IMPLEMENTATION → VALIDATION → CANONICAL REPOSITORY DOCUMENTATION → NOTION STATUS/EVIDENCE
```

Git commit/PR/merge is a separate explicit step governed by user instruction.

## Blocked behavior

| Blocker | Agent behavior |
|---------|----------------|
| `NOTION_CONTEXT_BLOCKED` | Continue from repository; list pages that should have been read |
| `NOTION_SYNC_BLOCKED` | Mark `COMPLETE_WITH_EXPLICIT_EXCEPTIONS` if audit otherwise done |

## P0 status (2026-09-09)

**NOTION_CONTEXT_BLOCKED** and **NOTION_SYNC_BLOCKED** — no Notion MCP namespace
available in this session. Intended reads and updates are listed in
[P0_FORENSIC_AUDIT_2026-09-09.md](P0_FORENSIC_AUDIT_2026-09-09.md).
