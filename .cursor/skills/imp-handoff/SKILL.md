---
name: imp-handoff
description: Produce a compact IMP session handoff covering HEAD, branches, worktrees, validation evidence, blockers, and exact next work. Use at session end, before context reset, or when transferring ownership.
---

# IMP session handoff

Fill [AGENT_HANDOFF.md](../../../projects/integrated-market-platform/docs/engineering/templates/AGENT_HANDOFF.md). Omit empty trivia. Do not claim work or tests that did not happen.

## Required sections

### Canonical state

- repository toplevel
- branch
- HEAD SHA
- upstream / ahead-behind vs `origin/main`
- worktree cleanliness (list unrelated dirty paths)

### Completed

What actually landed (paths + outcome).

### Validated

Exact commands and results. If not run: `NOT_RUN`.

### Active isolated work

Worktrees/branches with purpose, owner, base SHA, status, disposition.

### Evidence-sensitive state

Running/pending forward-test, RTH, heartbeat, scheduler — or `NONE OBSERVED`.
Never upgrade an evidence class in the handoff.

### Blockers

Actual blockers only (auth, evidence gate, upstream, environment).

### Deferred

Intentional deferrals, not forgotten work.

### Next work

One highest-leverage next step, including recommended skill and starting SHA.

### Model/escalation notes

Only if escalation occurred: why, and what problem required Grok 4.6 High.

## Also

Append `docs/engineering/WORK_LOG.md` for substantive work before the final message.
