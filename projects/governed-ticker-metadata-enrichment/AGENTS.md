# Validation cadence

Use the manifest-driven validation ladder for implementation work:

```text
after each edit            -> python tools/validate.py changed
domain milestone           -> python tools/validate.py domain <domain>
major/final checkpoint     -> python tools/validate.py full
live provider modified     -> python tools/validate.py live <provider>
```

Do not run FULL after every intermediate edit. Run it once at the final major checkpoint. A passing CHANGED result is not a substitute for FULL when it reports `full_suite_required=true`.

Run LIVE only for the provider whose live boundary changed, after the applicable offline validation. FULL must remain offline and must never select live suites.

See `docs/engineering/VALIDATION_ARCHITECTURE.md` for selectors, domains, snapshots, safety classes, and result interpretation.

## Local environment (Windows)

This repository targets CPython 3.11, standard-library-only (`phase0-dependency-lock.json`,
`tested_patch: 3.11.15`). The default `python` on PATH is often a different version (e.g. 3.10), which
fails module collection (`enum.StrEnum` ImportError) and cannot resolve `zoneinfo` keys like
`America/New_York` that `market_context`, `short_intelligence`, and `futures` modules load at import time.

Use the repository-local virtual environment for validation and tests:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe tools\validate.py changed          # after each edit
.venv\Scripts\python.exe tools\validate.py full             # final checkpoint (offline only)
.venv\Scripts\python.exe -m unittest tests.research.test_decision_research_p33 -v
.venv\Scripts\python.exe tools/research/run_decision_research_gate_validation.py   # DECISION-RESEARCH-001 gate
```

Note: the validation manifest currently has **no `research` domain** (decision-research tests run under
`validate.py changed` / `full` via the `research` suite, domain `core`, globs
`src/market_platform_foundation/research/decision_research/**` + `tests/research/test_*.py`). Adding a
`research` domain to `tools/validation_manifest.json` is a governed manifest edit — get principal approval
first.
```

`.venv/` is gitignored. One-time setup (CPython 3.11 + `tzdata`, the Windows companion for stdlib
`zoneinfo`):

```bash
uv venv --python <path-to-cpython-3.11-interpreter> .venv
uv pip install --python .venv/Scripts/python.exe tzdata
```

On this machine the uv-managed 3.11 interpreter is
`C:\Users\adame\AppData\Roaming\uv\python\cpython-3.11.15-windows-x86_64-none\python.exe`. uv-managed
interpreters are PEP 668 externally managed, so install `tzdata` into the venv, never into the managed
interpreter. `tzdata` is data-only (read by stdlib `zoneinfo` on Windows); the foundation itself imports no
third-party modules per the dependency lock. On Linux the system tz database satisfies `zoneinfo` without
`tzdata`.
