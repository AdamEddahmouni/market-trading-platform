# IMP Developer Operating System

**Status:** Authoritative developer workflow architecture.
**Scope:** Repository discovery, execution, validation, review, and closure.

The operating system is a thin control plane around existing authorities. The
validation manifest remains the only suite inventory, `tools/validate.py`
remains the Python validator, backend authority remains the safety boundary,
and UI commands remain owned by `ui/package.json`.

## Canonical command interface

Run from the repository root. Prefer the router so command choice, timing, and
evidence are consistent:

| Command | Purpose | Default cost |
|---|---|---|
| `python tools/imp.py env` | Safe runtime, Git, tool, and gate-presence diagnostics | tiny |
| `python tools/imp.py format` | Changed-file whitespace check (`git diff --check`) | tiny |
| `python tools/imp.py lint` | Python compile check and UI typecheck when UI is affected | cheap |
| `python tools/imp.py validate fast` | Run mandatory catastrophic invariants | fast |
| `python tools/imp.py test focused <selector>` | Explicit unittest selector(s) in one isolated worker | focused |
| `python tools/imp.py test affected` | Manifest-selected changed suites and mandatory invariants | affected |
| `python tools/imp.py validate changed` | Canonical changed validation with optional JSON evidence | affected |
| `python tools/imp.py validate domain <name>` | Domain milestone validation | domain |
| `python tools/imp.py validate full` | All offline full-tier suites | expensive |
| `python tools/imp.py review` | Format gate plus fail-fast affected validation | review |
| `python tools/imp.py closure` | Full backend closure, docs/UI gates as applicable, report | most expensive |

`test affected` is an ergonomic alias for manifest `changed` selection. It
does not infer live suites or replace mandatory invariants. `test focused`
requires exact selectors of the form
`tests/path/test_file.py::TestClass::test_method`.

## Validation pyramid

1. **FAST:** catastrophic mandatory invariants only.
2. **FOCUSED:** exact regression selectors while iterating.
3. **AFFECTED:** changed tests, direct source owners, declared offline
   neighbors, and mandatory invariants; safe Python suites run in parallel.
4. **DOMAIN:** all offline full-tier suites for one domain at a milestone.
5. **CHANGED:** the canonical affected result plus cheap checks; a
   `full_suite_required` result is preliminary, never closure evidence.
6. **FULL:** all offline full-tier suites once at final closure.

`SERIAL_REQUIRED`, `GLOBAL_STATE_MUTATION`, and `LIVE_EXCLUSIVE` work stays
serial. `PARALLEL_SAFE` work may use the configured worker count.
`RESOURCE_HEAVY` work is capped by the existing validator. Live validation is
opt-in and never substitutes for offline FULL.

For UI changes, add `cd ui && npm test`, `npm run typecheck`, and
`npm run build`; the build retains the 200 KiB gzip budget. For documentation
changes, run `tools/check_docs_links.py`.

## Agent delegation

Use `.cursor/agents/` for role-specific instructions:

- `architecture` — boundaries, invariants, and design review.
- `implementation` — scoped code changes following existing ownership.
- `testing` — focused/affected validation and evidence interpretation.
- `debugging` — reproduction, root cause, and regression tests.
- `safety-review` — Demo/Paper/Live, risk, execution, account, temporal, and
  persistence review.
- `documentation-review` — authority hierarchy, links, and stale duplication.
- `frontend-review` — query/state semantics, mode surfaces, accessibility, and
  bundle behavior.

Parallel delegation is appropriate only for independent read-only discovery,
independent pure implementation slices, or isolated `PARALLEL_SAFE` tests.
Keep shared files, validation-manifest changes, persistence, authority,
execution, CI, and documentation-index changes serial. A reviewer must inspect
the combined diff after parallel work.

## Model routing

The machine-readable policy is `.cursor/model-routing.json` and the durable
explanation is [AI_MODEL_STRATEGY.md](AI_MODEL_STRATEGY.md):

- **cheap:** exploration, inventory, formatting, mechanical edits, and
  straightforward test expansion;
- **normal:** ordinary implementation, focused debugging, and routine docs;
- **high-reasoning:** architecture, safety, Paper execution, persistence,
  cross-cutting review, and final closure.

Model names are intentionally policy aliases rather than permanent vendor
versions. The task risk determines the tier.

## Evidence and closure

The router records lightweight JSONL command telemetry under
`.local/developer-workflow/telemetry.jsonl` by default; override with
`IMP_TELEMETRY_PATH`. It records command identity, exit status, and wall time,
never environment values or credentials.

`imp closure` writes
`artifacts/developer-workflow/closure-report.json` with changed files/areas,
validation evidence, baseline failure classification, documentation changes,
risk status, and telemetry location. Existing dirty-tree failures must be
carried as baseline evidence rather than silently reclassified.

## Safety and ownership

The control plane does not authorize or execute trades. It preserves
[MODE_AUTHORITY.md](../architecture/MODE_AUTHORITY.md), [SECURITY.md](SECURITY.md),
Paper lifecycle authority, and the validation manifest. Hooks can block
dangerous workflow commands, but hooks are defense-in-depth; backend gates,
offline guards, and persisted audit controls remain authoritative.
