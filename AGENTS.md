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

## Cursor Cloud specific instructions

Cloud Agents run on Ubuntu using `.cursor/environment.json`. Install dependencies with:

```bash
bash .cursor/install-cloud-deps.sh
export PYTHONPATH=src
source .venv/bin/activate
```

Intelligence BUILD 04.5–09 additionally requires `numpy`, `pymongo`, and `scikit-learn` (installed by the script above).

Validation in cloud:

```bash
python -m unittest discover -s tests/intelligence -q
python -m unittest tests.platform.test_shadow_p6 -q
python tools/validate.py changed
```

- **MongoDB**: optional. Unit tests use `InMemoryIntelligenceRepository`; Mongo integration tests skip without `IMP_TEST_MONGODB_URI`.
- **Moomoo OpenD / IBKR gateway**: not available on cloud VM. Use fixtures, replay, and mock paths; keep live gates off.
- **Handoff branch**: start from `cloud-handoff/full-state-2026-08-25` and verify against `artifacts/cloud-handoff/CLOUD_FILE_HASHES.json`.
- See `docs/engineering/CURSOR_CLOUD_ENVIRONMENT.md` for secret names (values via Cursor Cloud Secrets only).

## Canonical program and evidence rules

Before editing, recover repository truth: root, branch, HEAD, upstream,
ahead/behind, worktrees, tracked and untracked changes, and recent lineage. Use
a clean worktree for scoped milestone work when the source worktree contains
unrelated changes; never reset, clean, stash, move, or stage someone else's
work merely to make the tree look clean.

Read `docs/platform/README.md` and the canonical document for the subject being
changed. Apply the truth classes and precedence in
`docs/platform/DOCUMENTATION_STANDARD.md`:

- preserve immutable BUILD, Phase, EVIDENCE, prediction-ledger, settlement,
  release, closure, and CLEANUP history;
- use historical artifacts for their accepted subject and cutoff, and current
  canonical documents for current program interpretation;
- reference executable schemas, policies, gates, manifests, and registries
  rather than copying mutable values into prose;
- preserve EVIDENCE-01/01A/01B semantics and keep the active EVIDENCE track
  independent unless a separately approved change explicitly integrates it;
- preserve temporal cutoffs, source/revision provenance, contradictory
  evidence, and authority boundaries;
- never infer trading authority from observation, prediction, qualification,
  release approval, AI/agent output, provider availability, or reconnect;
- update the applicable canonical documents when accepted architecture,
  status, roadmap, authority, boundaries, epistemics, or terminology changes;
- run the required manifest-driven validation and inspect both unstaged and
  staged diffs, including `git diff --check`, before acceptance or commit.

Future-system guidance must be conditional. For example: when a canonical
run, workflow, capability, skill, or SOP registry exists, use or generate from
it. Do not describe a planned Universal Run Ledger, Workflow Engine, registry,
or fabric as a current executable authority.
