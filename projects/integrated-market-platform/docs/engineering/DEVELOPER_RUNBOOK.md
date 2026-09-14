# IMP developer runbook (current)

**Status:** Authoritative **current** local and cloud developer workflow.  
**Scope:** Setup, diagnostics, launch/shutdown, validation, provider/FTEP read-only probes, ports, and logs.  
**Git pin:** After `git fetch origin main`, verify `git rev-parse origin/main` (do not trust stale SHAs in docs). Program truth beyond commands: [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md).

**Historical topology and lane tables** live in [DEVELOPER_OPERATING_SYSTEM.md](DEVELOPER_OPERATING_SYSTEM.md) under *Local lane topology (historical 2026-09-10)* — not current procedure.

Use **`python3`** (CPython 3.11) from an activated project `.venv`. On Windows, `.venv\Scripts\python.exe` is equivalent. Never print or commit secrets.

---

## Repository root

| Layout | Root for all commands below |
|--------|-----------------------------|
| Monorepo (canonical) | `projects/integrated-market-platform/` inside `AdamEddahmouni/market-trading-platform` |
| Legacy standalone clone | Repository root when checked out alone |

Do not edit the leftover nested `integrated-market-platform/` clone at the monorepo root.

---

## One-time setup

### Windows (operator)

Double-click `SETUP_PLATFORM.cmd` at the IMP root (value-blind preflight, `.venv`, `npm ci`, `.local`/`.private`, `.env` syntax check — no secret values).

### Linux / Cursor Cloud

```bash
cd projects/integrated-market-platform   # monorepo path
bash .cursor/install-cloud-deps.sh       # CPython 3.11 venv + tzdata + numpy/pymongo/sklearn + ui npm ci
export PYTHONPATH=src
source .venv/bin/activate
```

Linked Git worktrees: `python3 tools/imp.py env bootstrap --link-venv` when no local `.venv`.

Optional OpenD hop SDK (same IMP interpreter only):

```bash
python3 tools/imp.py env install-opend
```

---

## Environment diagnostics

```bash
export PYTHONPATH=src
python3 tools/imp.py env
python3 tools/imp.py env bootstrap --link-venv   # linked worktree only
```

JSON reports gate **presence** only, never values. Telemetry (optional): `.local/developer-workflow/telemetry.jsonl`.

---

## Start and stop (API + UI)

### Windows (launcher-owned)

| Action | Command |
|--------|---------|
| Start API + UI | `START_PLATFORM.cmd` or `PLATFORM_CONTROL.cmd` |
| Stop launcher trees | `STOP_PLATFORM.cmd` |

### Manual (any OS)

```bash
# API — repo root, terminal 1
export PYTHONPATH=src
python3 tools/ui1/run_ui_api.py --serve --port 8766

# UI — terminal 2
cd ui && npm run dev
```

After env changes on Windows: `powershell -File tools/ui1/restart_ui_api.ps1`.

**Shutdown:** stop the API and UI processes (Ctrl+C in manual mode; `STOP_PLATFORM.cmd` on Windows). Stale launcher state cannot kill unrelated processes when command identity no longer matches (see README).

---

## Ports and endpoints

| Surface | Bind | Notes |
|---------|------|--------|
| UI (Vite) | `http://127.0.0.1:5173` | Dev server |
| UI API | `http://127.0.0.1:8766` | `tools/ui1/run_ui_api.py` |
| Launcher supervisor | `http://127.0.0.1:8767` | Loopback-only; Windows launcher |
| Control center | `http://127.0.0.1:5173/control` | Lifecycle, masked provider config, readiness |
| UI Diagnostics | `http://127.0.0.1:5173/diagnostics/provider` | Operator-only SPA (`NavShell`); not an API route |
| Moomoo OpenD | `127.0.0.1:11111` | Local only; not on cloud VM |
| IBKR TWS socket | `127.0.0.1:4001` | Observational transport; not execution authority |
| IBKR Client Portal | `https://127.0.0.1:5000/v1/api` | Second transport; not TWS |

Read-only API probes (no orders). `/diagnostics/provider` is the UI page on `:5173`, not `:8766`.

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8766/provider/health
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8766/context
```

### Primary UI surfaces (shipped)

Open `http://127.0.0.1:5173` after API + UI start. Use **sidebar labels** from `NavShell`. Do not invent routes.

| Nav label | Route | Operator meaning |
|-----------|-------|------------------|
| **Workspace** | `/workspace` | Decision desk (canonical Paper submit boundary) |
| **Portfolio** | `/portfolio` | Orders history — not the submit surface |
| **Lab** | `/research` | Model and sim labs. `/lab` redirects to `/research` |

A gated **Research** item also opens `/research`. **Risk** in the sidebar is `/control` (control center row above). Live stays observational; this runbook does not enable Live execution.

Source: `ui/src/components/NavShell.tsx` and `ui/src/App.tsx`. Patterns: [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md).

---

## Logs and local state

| Path | Purpose |
|------|---------|
| `.local/platform-backend.log` | API stdout/stderr (launcher) |
| `.local/platform-ui.log` | UI dev server (launcher) |
| `.local/platform-control.log` | Launcher supervisor |
| `.local/platform-launcher.json` | Lifecycle state (gitignored) |

Forward-test **durable** state (when enabled): local SQLite under `IMP_STATE_DIR` / `local_state` (schema v6). See [CONFIGURATION.md](CONFIGURATION.md) (`IMP_PERSIST_STATE`, `IMP_STATE_DIR`) and [PAPER_FORWARD_TESTING_BRIDGE.md](../architecture/PAPER_FORWARD_TESTING_BRIDGE.md). With persistence **off**, forward-test bridge repositories are process-local (`INTENTIONAL_EPHEMERAL`) — that is a runtime mode, not “SQLite unimplemented.” Intelligence unit tests default to `InMemoryIntelligenceRepository`; Mongo remains optional (`IMP_TEST_MONGODB_URI`).

---

## Validation (developer pyramid)

Canonical router: `python3 tools/imp.py` — full matrix in [DEVELOPER_OPERATING_SYSTEM.md](DEVELOPER_OPERATING_SYSTEM.md) and [VALIDATION.md](VALIDATION.md).

```bash
export PYTHONPATH=src
python3 tools/imp.py validate fast
python3 tools/imp.py test focused tests/path/test_file.py::TestClass::test_method
python3 tools/imp.py test affected          # manifest changed scope + mandatory invariants
python3 tools/imp.py validate changed
python3 tools/imp.py validate domain <name> # e.g. core, ui, providers, …
python3 tools/imp.py validate full          # offline full tier; closure / release checkpoint
python3 tools/imp.py review
python3 tools/imp.py closure
```

**UI** (when `ui/` changes or before UI PR):

```bash
cd ui
npm run typecheck
npm test -- --run
npm run build    # includes gzip bundle budget
```

**Docs-only PRs:** `python3 tools/check_docs_links.py`

**CI (monorepo):** `.github/workflows/imp-validate.yml` — nine jobs on `main` / IMP PRs: `validate-workflows`, `validate-python` (fast), `validate-python-changed`, `validate-docs`, `validate-ui`, plus reusable workflow slices (9/9 green required before merge). Jobs still report; expensive UI/docs/replay-fixture steps skip on PRs when those trees are unchanged. Classify slices with `python3 tools/imp.py ci jobs`. Push-to-`main` and `workflow_dispatch` still run every slice.

Lane G cloud verification (2026-09-14 @ `5e0ec717`): `tools/validate.py fast` + `domain core` (**4326** passed / 48 skipped) + `full` (**5202** passed / 48 skipped) via `.venv/bin/python3`; UI **468** vitest + typecheck + build; `check_docs_links.py` OK. Store receipt: Project store `internal/lane-g-runbook.md`.

---

## Provider readiness (read-only)

```bash
export PYTHONPATH=src
python3 tools/provider_readiness.py
python3 tools/provider_readiness.py --probe-local    # loopback ports only
python3 tools/provider_readiness.py --json
python3 tools/provider_readiness.py audit --json
python3 tools/provider_readiness.py gaps --profile FTEP-V1-001 --json
python3 tools/imp.py providers campaign-readiness FTEP-V1-002 --json
python3 tools/providers/capability_matrix.py --output artifacts/wave-a-findings/capability-matrix-snapshot.json
```

Detail: [PROVIDER_READINESS.md](PROVIDER_READINESS.md). Operator probe sequence (Wave A): [OPERATOR_PROBE_RUNBOOK.md](OPERATOR_PROBE_RUNBOOK.md).

---

## FTEP / Paper diagnostics (no governed session)

**Do not** run `python3 tools/imp.py ftep session-start <slug>` without `--dry-run` unless operator authorization and RTH gates are intentionally satisfied. Lane G used **dry-run and read-only** commands only.

```bash
export PYTHONPATH=src
# Optional: match laptop readiness gates without starting a session
export IMP_PERSIST_STATE=1

python3 tools/imp.py ftep integrity-check FTEP-V1-002 --json
python3 tools/imp.py ftep campaign-status FTEP-V1-002 --json
python3 tools/imp.py ftep session-start FTEP-V1-002 --dry-run --json
python3 tools/imp.py ftep opportunity-summaries --sample --json
python3 tools/imp.py ftep watch-catalysts FTEP-V1-002 --fixture --json
python3 tools/imp.py ftep record-prospective-lock FTEP-V1-002 --dry-run --json
```

Path A / OpenD hop CLIs (`tools/path_a_rth_preflight.py`, `tools/path_a_prospective_run.py`, `tools/hop_json_gate_check.py`) are **frozen** behavior; see store weekday hop docs and [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md). Use the IMP `.venv` interpreter on Windows (not bare Store `python3`).

FTEP empirical posture remains **`FTEP_EMPIRICAL_NOT_READY`** until owner gates say otherwise — dry-run success is not activation.

---

## Troubleshooting

See [operations/RUNBOOK.md](../operations/RUNBOOK.md) for UI/API/provider failure playbooks.

---

## Related authorities

- [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) — prerequisites and Windows setup narrative  
- [FRONTEND_GUIDE.md](FRONTEND_GUIDE.md) — shipped primary nav labels and UI patterns
- [CURSOR_CLOUD_ENVIRONMENT.md](CURSOR_CLOUD_ENVIRONMENT.md) — cloud secrets **names** only  
- [AGENTS.md](../../AGENTS.md) — agent entry and safety invariants
