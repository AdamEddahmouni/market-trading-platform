# AI Model & Tool Strategy

**Status:** Workload-based guidance — vendor/model-version resilient.

Do not hard-code marketing model names as permanent truth. When the project standardizes specific models, add an easily-updated table below.

## Fast / low-cost model

- Simple edits, formatting
- Repetitive test case expansion
- Straightforward refactors
- CSS adjustments
- Boilerplate adapters

## Strong coding / reasoning model

- Architecture decisions
- Complex debugging (cache, authority, preview state)
- **Paper execution** changes
- Schema migration design
- Security-sensitive work
- Large cross-cutting refactors

## Research / web-capable model

- External library version research
- Broker/API documentation
- CVE / security advisories
- Dependency evaluation

External info must **not** silently override repository contracts.

## Long-context model

- Repository governance audits
- Documentation consolidation
- Large migration planning

## Tool selection

| Need | Tool |
|------|------|
| Internal architecture | Codebase search, read docs |
| Validation | `validate.py`, vitest, build |
| Provider behavior | `docs/providers/`, then web if stale |
| GitHub PR/issues | `gh` CLI |

## Freshness policy

Isolate version-specific tables in one file ([STACK.md](STACK.md), `package.json`). Verify with `npm outdated`, lock files — do not scatter version numbers across many docs.

## Project-specific emphasis

Use highest-reasoning tier for any change touching:

- `modeAuthority.ts` / backend operating context
- Paper preview/submit/intent path
- Query key registry
- Env gates affecting execution
