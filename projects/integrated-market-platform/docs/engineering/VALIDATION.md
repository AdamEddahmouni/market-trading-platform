# Validation Guide

**Status:** Authoritative commands and when to run them.  
**Internals:** [VALIDATION_ARCHITECTURE.md](VALIDATION_ARCHITECTURE.md)

Run from repository root unless noted. Use `.venv\Scripts\python.exe` on Windows (CPython 3.11).

## Canonical command interface

Use `python tools/imp.py` for the stable developer surface:

```powershell
python tools/imp.py env
python tools/imp.py format
python tools/imp.py lint
python tools/imp.py test focused <selector>
python tools/imp.py test affected
python tools/imp.py validate changed
python tools/imp.py validate full
python tools/imp.py review
python tools/imp.py closure
```

The router delegates Python execution to the manifest validator and keeps the
existing direct commands below available for compatibility.

## Commands

### Python (manifest)

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py fast
.venv\Scripts\python.exe tools\validate.py changed
.venv\Scripts\python.exe tools\validate.py domain <name>
.venv\Scripts\python.exe tools\validate.py full
.venv\Scripts\python.exe tools\validate.py live <provider>
```

Domains: `core`, `short-intelligence`, `macro`, `energy`, `futures`, `options`, `order-flow`, `participant`, `sec`, `ui`.

### Frontend

```powershell
cd ui
npm test
npm run build    # vite build + bundle budget check
```

### Docs link check (governance)

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools/check_docs_links.py
```

## Validation matrix

| Change type | Unit | App/UI | Build | Bundle | validate changed | validate full |
|-------------|------|--------|-------|--------|------------------|---------------|
| Docs only | — | — | — | — | optional | no |
| UI | vitest | App.test | yes | yes | yes | if cross-cutting |
| Backend | unittest | if API | — | — | yes | if cross-cutting |
| API/schema | both | yes | yes | if UI | yes | recommended |
| Paper safety | both | yes | yes | yes | yes | **yes** |
| Release candidate | all | all | yes | yes | yes | **yes** |

**Note:** `changed` passing with `full_suite_required=true` is not a substitute for `full` at checkpoints.

## CI (GitHub)

`.github/workflows/imp-validate.yml`: cancellable parallel FAST, merge-base
CHANGED, docs-link, and UI typecheck/test/build jobs on PR/push to `main`.
FULL remains the final local closure gate through `python tools/imp.py closure`
unless a release workflow explicitly promotes it.

## Dependency audit

```powershell
cd ui && npm audit
# Foundation: stdlib-only lock — no pip deps in foundation
```

See [DEPENDENCY_UPDATE.md](sops/DEPENDENCY_UPDATE.md).
