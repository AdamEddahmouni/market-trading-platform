# Next US equity RTH campaign runbook (post–`origin/main` `5d8163e`)

**Evidence class:** SOFTWARE coordination only. **Live OFF.** No Paper/Live orders. No empirical locks. Do not declare FTEP `EMPIRICAL_ACTIVE`.

This document is the **current-main** operator surface for the **next** US equity regular-hours (RTH) window after the 2026-09-15 campaign prep. It does **not** rewrite Sep 15 empirical findings.

## Authority layers (do not conflate)

| Layer | Git SHA | Role |
|-------|---------|------|
| **Current implementation** | `5d8163e582e4bceb2354785c75638687d4959fef` (`origin/main`; [#206](https://github.com/AdamEddahmouni/market-trading-platform/pull/206) launcher/Vite routing landed) | Commands, ports, and software labels below |
| **Frozen Sep 15 empirical authority** | `7aade60b…` (historical RTH evidence pin) | Accepted observational receipts and Sep 15 session truth — **not** overridden by this runbook |
| **Repair train (sibling lanes)** | Base `7aade60` on open PRs [#203](https://github.com/AdamEddahmouni/market-trading-platform/pull/203)–[#208](https://github.com/AdamEddahmouni/market-trading-platform/pull/208) | **Not on `main`** until merged; merge SHAs **`<pending>`** per lane — do not assume live OE / Item 9 / Finviz / 8766 fixes are shipped |

**Checklist overlap:** [#207](https://github.com/AdamEddahmouni/market-trading-platform/pull/207) owns small deltas to [TUESDAY_RTH_OPERATOR_CHECKLIST.md](TUESDAY_RTH_OPERATOR_CHECKLIST.md) and [RTH_EMPIRICAL_OPS_RUNBOOK.md](RTH_EMPIRICAL_OPS_RUNBOOK.md). Until #207 merges, use those files plus this page for SHA truth and repair-train placeholders.

## Campaign timing (US/Eastern)

| Phase | When | Intent |
|-------|------|--------|
| **Pre-catalyst (optional)** | Before **09:30** cash open (operator choice; e.g. 09:00–09:25) | Finviz prospective ingress when gates enabled — improves catalyst capture without crossing into execution |
| **T−15** | ≈ **09:15** | Preflight, persistence path, temporary session gates |
| **Cash open transition** | **09:30** | Finviz live ingress, Item 9 `--poll`, Item 7 status/collect, ops dry-run bundle |
| **Session close** | **16:00** | Summarize, env cleanup, independent review |

Off-hours preflight may show `SOFTWARE_READY_RTH_REQUIRED` or `RTH_EMPIRICAL_OPS_BLOCKED` — that is **software success**, not empirical failure.

## Workstation bootstrap (once per day)

```powershell
cd projects\integrated-market-platform
python tools\imp.py env bootstrap --link-venv   # linked worktrees: creates .venv symlink
$report = python tools\state_path_diagnostic.py | ConvertFrom-Json
$env:IMP_STATE_DIR = $report.canonical_state_dir
$env:IMP_PERSIST_STATE = "1"
```

Use the project **CPython 3.11** `.venv` only (`python tools\imp.py env`). Never commit session gates.

## Platform surfaces (`5d8163e` / #206)

| Check | Endpoint / command | Notes |
|-------|-------------------|--------|
| SPA root | `http://127.0.0.1:5173/` | Canonical operator entry (#206); not `/discover` as primary |
| Control center | `http://127.0.0.1:5173/control` | Lifecycle, masked provider config |
| UI Diagnostics | `http://127.0.0.1:5173/diagnostics/provider` | SPA route — **not** `:8766` |
| UI API | `http://127.0.0.1:8766` | `tools\ui1\run_ui_api.py --serve --port 8766` |
| Launcher supervisor | `http://127.0.0.1:8767` | Loopback-only; Windows launcher |
| OE ranked feed API | `GET /opportunities/summary` | Ranked opportunity rows (replay/store projection) |
| EventV1 ingress | `build_production_observation_ingress_router` | Software on `main`; **not** universal on every normalize path; empirical capture **RTH-only** |
| Grok / async enrichment | Durable worker **OFF by default** (#189) | **Not** `GROK_AUTOMATION_PRODUCTION_ACTIVE`; opt-in only |

Start/stop: `START_PLATFORM.cmd` / `STOP_PLATFORM.cmd` or [DEVELOPER_RUNBOOK.md](DEVELOPER_RUNBOOK.md).

### Read-only health probes (no orders)

```powershell
curl -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8766/provider/health
curl -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8766/context
curl -s -o NUL -w "%{http_code}`n" "http://127.0.0.1:8766/opportunities/summary"
```

Control service (when launcher running): `http://127.0.0.1:8767/control/status` (loopback).

## RTH command center

Global `--json` **before** subcommand:

```powershell
python tools\rth_empirical_ops.py --json preflight
python tools\rth_empirical_ops.py --json status
```

Delegated preflight (unchanged):

```powershell
python tools\ftep_finviz_prospective_preflight.py FTEP-V1-002 --json
python tools\imp.py ftep integrity-check FTEP-V1-002 --json
python tools\moomoo\opend_bar_1m_prospective_proof.py readiness
$item7CutoffNs = python -c "from market_platform_foundation.clock import monotonic_wall_ns; print(monotonic_wall_ns())"
python tools\item7_corpus_collector.py status --persistence-root $env:IMP_STATE_DIR --training-cutoff-ns $item7CutoffNs
```

### Temporary gates (shell only — never commit)

```powershell
$env:IMP_FINVIZ_LIVE = "1"
$env:IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS = "1"
```

### Observational sequence (≥ 09:30 ET)

Command details: [TUESDAY_RTH_OPERATOR_CHECKLIST.md](TUESDAY_RTH_OPERATOR_CHECKLIST.md) — replace dated `experiment-id` / receipt folder suffix with the **actual session date**.

| Step | Tool | Receipt / honesty |
|------|------|-------------------|
| Finviz prospective | `python tools\ftep_watch_catalysts.py FTEP-V1-002 --live-ingress --json` | Not via `rth_empirical_ops` live ingress |
| **Item 9** | `python tools\moomoo\opend_bar_1m_prospective_proof.py prospective --poll …` | Contract `item9.bar-ohlcv-prospective-proof/1.1.0`; `orders_placed=false`, `calibrated=false` |
| **Item 7** | `item7_corpus_collector.py status|diagnose|collect …` | `--training-cutoff-ns` required; governed rows **0** on `main` until earned |
| Ops bundle | `python tools\rth_empirical_ops.py --json run-observational` | Optional `--write-run-artifact`; dry-run (`live_ingress=False`) |
| Close | `python tools\rth_empirical_ops.py --json summarize` | |

## Receipts, latency, logs

| Artifact | Path |
|----------|------|
| Item 9 prospective proof | `{IMP root}/artifacts/ftep-v1-002/item9-prospective-proof-receipts/` (or `--receipt-out`) |
| RTH ops run bundle | `$env:IMP_STATE_DIR/rth-empirical-ops/runs/RTHOPS-*.json` with `--write-run-artifact` |
| Finviz / FTEP / Item 7 | JSON stdout; operator copies under governed `.local` policy |
| Hot-path latency evidence | Gate `PROSPECTIVE_HOT_PATH_LATENCY_CAPTURED` — software wired (#166/#154); **no** live RTH receipt until earned |
| API / UI logs (launcher) | `.local/platform-backend.log`, `.local/platform-ui.log`, `.local/platform-control.log` |
| Persistence (FTEP-V1-002) | SQLite under `IMP_STATE_DIR` when `IMP_PERSIST_STATE=1` |

## FTEP / campaign mode

- Campaign: **FTEP-V1-002** (`SIGNAL_ONLY_AUTHORIZED`; **not** `EMPIRICAL_ACTIVE`; locks **0**).
- Sessions (canonical durable state): **BASELINE** `fts-6DB7771FD9B3A991`, **AI_ENHANCED** `fts-D93189A042A1BEF2`.
- Integrity: `python tools\imp.py ftep integrity-check FTEP-V1-002 --json` must **PASS** against canonical `IMP_STATE_DIR` before treating receipts as governed.

## Rollback / recovery

1. `Remove-Item Env:IMP_FINVIZ_LIVE, Env:IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS -ErrorAction SilentlyContinue`
2. `STOP_PLATFORM.cmd` or kill stale `:8766` / `:5173` / `:8767` listeners (`tools\ui1\restart_ui_api.ps1` after env changes).
3. Do **not** delete governed SQLite or empirical receipts; archive operator JSON under `.local` if needed.
4. If preflight `integrity_disposition=FAIL`, fix `IMP_STATE_DIR` / manifest drift before any live ingress.
5. Repair-train merges: after any #203–#208 lands, re-run preflight and update sibling SHA placeholders in [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) — not here.

## Sibling-lane merge SHA placeholders (`main` = `5d8163e` until updated)

| PR | Purpose | Merge SHA on `main` |
|----|---------|---------------------|
| [#206](https://github.com/AdamEddahmouni/market-trading-platform/pull/206) | Launcher / Vite routing | `5d8163e582e4bceb2354785c75638687d4959fef` (**merged**) |
| [#195](https://github.com/AdamEddahmouni/market-trading-platform/pull/195) | Finviz prospective receipt validator (software) | `<pending>` |
| [#196](https://github.com/AdamEddahmouni/market-trading-platform/pull/196) | Evidence capture-context sidecar | `<pending>` |
| [#199](https://github.com/AdamEddahmouni/market-trading-platform/pull/199) | Item 7 corpus evidence validator | `<pending>` |
| [#200](https://github.com/AdamEddahmouni/market-trading-platform/pull/200) | PROGRAM_STATUS pre-RTH sync | `<pending>` (superseded in part by this runbook PR) |
| [#203](https://github.com/AdamEddahmouni/market-trading-platform/pull/203)–[#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205), [#207](https://github.com/AdamEddahmouni/market-trading-platform/pull/207)–[#208](https://github.com/AdamEddahmouni/market-trading-platform/pull/208) | RTH15 repair train (rebased from `7aade60`) | `<pending>` each |

## Pre-RTH verification checklist (Agent H, off-session)

| Check | Status | Notes |
|-------|--------|-------|
| `origin/main` SHA `5d8163e` | **VERIFIED** | `git rev-parse origin/main` |
| Worktree branch clean | **VERIFIED** | `rth15-next-rth-runbook` tracking `origin/main` |
| Python 3.11 interpreter | **VERIFIED** | Primary IMP `.venv` → 3.11.15 |
| Worktree `.venv` link | **UNVERIFIED** | Run `imp.py env bootstrap --link-venv` on workstation |
| Node/npm | **UNVERIFIED** | Not probed this session |
| OpenD `127.0.0.1:11111` | **UNVERIFIED** | Requires local OpenD |
| Finviz credential files (existence) | **UNVERIFIED** | `.private/finviz-login.json` or `.private/finviz-token.txt` — values not read |
| UI API `:8766` health | **UNVERIFIED** | Services not started in prep session |
| Vite `:5173` | **UNVERIFIED** | Services not started |
| Control `:8767` | **UNVERIFIED** | Launcher not started |
| `rth_empirical_ops` preflight | **VERIFIED** (off-hours) | `RTH_EMPIRICAL_OPS_BLOCKED`; `runtime_git_sha=5d8163e` |
| FTEP integrity | **UNVERIFIED** | `integrity_disposition=FAIL` in off-hours preflight (likely state/path); re-check with canonical `IMP_STATE_DIR` |
| Item 9 readiness CLI | **UNVERIFIED** | Not fully captured this session |
| Campaign mode / Live OFF | **VERIFIED** | Policy + docs; FTEP not `EMPIRICAL_ACTIVE` |
| Grok automation production | **VERIFIED** (intended OFF) | Worker default off on `main` |
| Item 9 / Item 7 empirical gates | **VERIFIED** (unearned) | Still **PARTIAL**; no fabricated receipts |

## Recommended next RTH operator actions (current `main` only)

1. Merge or rebase repair train as orchestrator directs; **do not** assume #207 Finviz ingress fixes until SHA is on `main`.
2. Night before: `git fetch origin main`; confirm `git rev-parse origin/main` = `5d8163e` (or newer tip after merges).
3. Morning: bootstrap venv/state path; start platform; confirm `:8766` / `:5173` / SPA at `http://127.0.0.1:5173/`.
4. T−15: run full preflight block; set temporary Finviz/catalyst gates; confirm OpenD loopback.
5. ≥ 09:30: execute Finviz watch → Item 9 poll → Item 7 status → ops dry-run; persist receipts; summarize.
6. Confirm empirical gates remain unflipped unless governed JSON receipts exist; Live stays OFF.
