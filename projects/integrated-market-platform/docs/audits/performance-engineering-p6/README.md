# P6 — CI / Developer Workflow / Agent Efficiency

**Status:** Implemented in `perf/p6-ci-agent-workflow` (locally preserved)
**Base checkpoint:** `ea38fd9e76fcf98ea1495c72f45cb40ed6df39c7` (P4 clean)

## Scope

Reduce worktree bootstrap friction, validation/CI setup duplication, and agent
context overhead without changing P3 selector semantics, P4 fixture semantics,
product behavior, or test inventory.

## Primary changes

1. **`tools/environment.py`** — portable interpreter/worktree discovery, timezone
   verification via resolved Python, and explicit `.venv` junction bootstrap.
2. **`tools/imp.py env`** — enriched diagnostics (`schema_version` 1.1) plus
   `env bootstrap --link-venv`; validation subprocesses use resolved Python.
3. **`tools/validate.py`** — process-local embedding-context cache.
4. **`.github/workflows/imp-python.yml`** — pip cache before dependency install.
5. **Developer docs/rules** — worktree bootstrap guidance in DOS + scoped rule.

## Evidence files

| File | Purpose |
|------|---------|
| `P6_BEFORE_BASELINE.json` | Pre-change workflow measurements |
| `P6_AFTER_BASELINE.json` | Post-change measurements |
| `WORKFLOW_AUDIT.json` | Developer/agent workflow inventory |
| `CI_AUDIT.json` | CI duplication and cache analysis |
| `CONTEXT_RULE_AUDIT.json` | AGENTS/Cursor consolidation record |
| `OPTIMIZATION_LEDGER.json` | Opportunity ledger with status |

## Validation receipts

Local receipts under `.local/developer-workflow/`:

- `p6-changed-after.json`
- `p6-full-closure.json` (when present)
