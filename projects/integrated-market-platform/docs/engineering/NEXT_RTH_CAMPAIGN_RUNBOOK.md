# Next US equity RTH campaign runbook (post–IMP-EVIDENCE-HARDENING-02)

**Evidence class:** SOFTWARE coordination only. **Live OFF.** No Paper/Live orders. No empirical locks. Do not declare FTEP `EMPIRICAL_ACTIVE`.

This document is the **current-main** operator surface for the **next** US equity regular-hours (RTH) window. It does **not** rewrite Sep 15 empirical findings or Sep 17 frozen receipts.

## Authority layers (do not conflate)

| Label | Git SHA | Role |
|-------|---------|------|
| **CURRENT_MAIN** (`origin/main` / git tip) | `19a5ebd5370cd249bee1cf0cc667a737dec6e634` | Mutable tip after [#253](https://github.com/AdamEddahmouni/market-trading-platform/pull/253) docs post–dual-corpus hygiene (prior IMP-EVIDENCE-HARDENING-02 software [#248](https://github.com/AdamEddahmouni/market-trading-platform/pull/248)–[#252](https://github.com/AdamEddahmouni/market-trading-platform/pull/252)). Docs-only merges advance this label only. |
| **CURRENT_SOFTWARE_IMPLEMENTATION** | `a1b556f89c8e68e84fe7246c6e726359f3a0ebf8` | Last **software-bearing** merge: [#251](https://github.com/AdamEddahmouni/market-trading-platform/pull/251) Item 9 `next-rth-preflight`. Stays pinned until the next software merge. Commands and labels below assume this implementation. |
| **ITEM9_FROZEN_COLLECTOR** | `fed2d9f7e183aecfcac61a7664df69aafc12ea25` | Governed Mode B `--poll` checkout `.imp-actual-01-phase-d/` @ this SHA — **not** **CURRENT_MAIN**. |
| **SEP15_FROZEN_EMPIRICAL_AUTHORITY** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` | Sep 15 observational historical pin — **not** overridden by this runbook. |
| **RTH15 repair train (ancestry)** | merged through `6e9e88b` ([#203](https://github.com/AdamEddahmouni/market-trading-platform/pull/203)–[#218](https://github.com/AdamEddahmouni/market-trading-platform/pull/218), [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205)) | #205/#208 hops are **SOFTWARE**; in-memory OE; acceptance suite ≠ two-process RTH hop; not empirical RTH readiness. |

Canonical status authority: [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md).

**Checklist overlap:** [#207](https://github.com/AdamEddahmouni/market-trading-platform/pull/207) (head `ca3c53a9`) owns deltas to [TUESDAY_RTH_OPERATOR_CHECKLIST.md](TUESDAY_RTH_OPERATOR_CHECKLIST.md), [RTH_EMPIRICAL_OPS_RUNBOOK.md](RTH_EMPIRICAL_OPS_RUNBOOK.md), and `artifacts/ftep-v1-002/SIGNAL_ONLY_LAUNCH_PREP.md`. **Not on `main`** until merge — use current `main` files plus this page.

## Campaign timing (US/Eastern)

| Phase | When | Intent |
|-------|------|--------|
| **Pre-catalyst (optional)** | Before **09:30** cash open (operator choice; e.g. 09:00–09:25) | Finviz prospective ingress when gates enabled — improves catalyst capture without crossing into execution |
| **T−15** | ≈ **09:15** | Preflight, persistence path, temporary session gates |
| **Cash open transition** | **09:30** | Finviz live ingress, Item 9 `--poll` (frozen collector), Item 7 status/collect, ops dry-run bundle |
| **Session close** | **16:00** | Summarize, env cleanup, independent review |

Off-hours `python tools/imp.py item9 next-rth-preflight --json` must show `calendar.rth_active=false` — that is **software success** for the calendar gate, not empirical failure. Overall disposition may be `WRONG_RUNTIME` when the command runs from **CURRENT_MAIN** / a software worktree (`19a5ebd5…`) instead of **ITEM9_FROZEN_COLLECTOR** (`fed2d9f7…`); collection still starts only from the frozen checkout. When runtime matches frozen authority off-hours, disposition is `NOT_RTH` (exit 0). Process listing for duplicate `--poll` is **tools-only** ([#251](https://github.com/AdamEddahmouni/market-trading-platform/pull/251)); `imp.py item9` reports `process_probe_status=COMPLETED`. Do **not** run governed Item 9 prospective collection off-hours.

## Workstation bootstrap (once per day)

```powershell
cd projects\integrated-market-platform
python tools\imp.py env bootstrap --link-venv   # linked worktrees: creates .venv symlink
$report = python tools\state_path_diagnostic.py | ConvertFrom-Json
$env:IMP_STATE_DIR = $report.canonical_state_dir
$env:IMP_PERSIST_STATE = "1"
```

Use the project **CPython 3.11** `.venv` only (`python tools\imp.py env`). Never commit session gates.

## Platform surfaces (**CURRENT_SOFTWARE_IMPLEMENTATION** `a1b556f8`)

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
python tools\imp.py item9 next-rth-preflight --json
```

Delegated preflight (unchanged):

```powershell
python tools\ftep_finviz_prospective_preflight.py FTEP-V1-002 --json
python tools\imp.py ftep integrity-check FTEP-V1-002 --json
python tools\moomoo\opend_bar_1m_prospective_proof.py readiness
$item7CutoffNs = python -c "from market_platform_foundation.clock import monotonic_wall_ns; print(monotonic_wall_ns())"
python tools\item7_corpus_collector.py status --persistence-root $env:IMP_STATE_DIR --training-cutoff-ns $item7CutoffNs
```

Item 9 next-RTH preflight details: [ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md](ITEM9_BAR_OHLCV_PROSPECTIVE_PROOF.md).

### Temporary gates (shell only — never commit)

```powershell
$env:IMP_FINVIZ_LIVE = "1"
$env:IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS = "1"
```

### Observational sequence (≥ 09:30 ET)

Command details: [TUESDAY_RTH_OPERATOR_CHECKLIST.md](TUESDAY_RTH_OPERATOR_CHECKLIST.md) — replace dated `experiment-id` / receipt folder suffix with the **actual session date**.

| Step | Tool | Receipt / honesty |
|------|------|-------------------|
| Item 9 preflight | `python tools\imp.py item9 next-rth-preflight --json` | Read-only; `READY_TO_COLLECT` still requires manual `--poll` start |
| Finviz prospective | `python tools\ftep_watch_catalysts.py FTEP-V1-002 --live-ingress --json` | Not via `rth_empirical_ops` live ingress |
| **Item 9 collection** | Mode B `--poll` from **`.imp-actual-01-phase-d`** @ **ITEM9_FROZEN_COLLECTOR** `fed2d9f7` (`opend_bar_1m_prospective_proof.py prospective --poll …`) | Contract `item9.bar-ohlcv-prospective-proof/1.1.0`; `orders_placed=false`, `calibrated=false` |
| **Item 9 corpus** | `python tools\item9_corpus_status.py corpus-status --receipt-dir artifacts/ftep-v1-002/item9-prospective-proof-receipts` | After receipt; no automatic fitting |
| **Item 7** | `item7_corpus_collector.py status|diagnose|collect …`; optional `item7_opend_capture_append.py` | Governed rows **0** until earned; auto-persist **SOFTWARE/CONTROLLED** only |
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
5. After future **software** merges, update **CURRENT_SOFTWARE_IMPLEMENTATION** in [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) — not here. This runbook tracks operator flow; SHA tables live in program status.

## Historical merge SHAs (not current tip)

| PR | Purpose | Merge SHA on `main` |
|----|---------|---------------------|
| [#251](https://github.com/AdamEddahmouni/market-trading-platform/pull/251) | Item 9 next-RTH preflight (**CURRENT_SOFTWARE_IMPLEMENTATION**) | `a1b556f89c8e68e84fe7246c6e726359f3a0ebf8` |
| [#252](https://github.com/AdamEddahmouni/market-trading-platform/pull/252) | IBKR historical TRADE pagination (Lane C) | `2d4a6d37` |
| [#250](https://github.com/AdamEddahmouni/market-trading-platform/pull/250) | Holdout consumption guards (Lane B) | `f533413e` |
| [#249](https://github.com/AdamEddahmouni/market-trading-platform/pull/249) | Historical session calendar + quality (Lane D) | `3dc472cd` |
| [#248](https://github.com/AdamEddahmouni/market-trading-platform/pull/248) | Path A label linker (Lane A) | `700b5be6` |
| [#246](https://github.com/AdamEddahmouni/market-trading-platform/pull/246) | Dual-corpus historical development e2e demo | `da237fd1` |
| [#210](https://github.com/AdamEddahmouni/market-trading-platform/pull/210) | Item 7 upstream SNAPSHOT_BBO capture envelope | `73da9fdb` |
| [#208](https://github.com/AdamEddahmouni/market-trading-platform/pull/208) | SOFTWARE fullstack acceptance | `6e9e88b` |
| [#207](https://github.com/AdamEddahmouni/market-trading-platform/pull/207) | Finviz ingress reliability / receipts | **OPEN** head `ca3c53a9` — `<pending merge on main>` |

## Pre-RTH verification checklist (off-session)

| Check | Status | Notes |
|-------|--------|-------|
| `origin/main` = **CURRENT_MAIN** `a1b556f8` | Operator | `git fetch origin main && git rev-parse origin/main` |
| **ITEM9_FROZEN_COLLECTOR** worktree | Operator | `.imp-actual-01-phase-d` @ `fed2d9f7` |
| Python 3.11 + `.venv` | Operator | `python tools\imp.py env bootstrap --link-venv` |
| OpenD loopback | Operator | Required for Item 9 collection |
| `item9 next-rth-preflight` | Operator | Off-hours `NOT_RTH` expected |
| Campaign / Live OFF | **Policy** | FTEP not `EMPIRICAL_ACTIVE`; Moomoo/IBKR **`PROVIDER_UNVERIFIED`** unless operator earns live receipts |
| Item 9 / Item 7 gates | **Unearned** | `ITEM9_CALIBRATED`=NO; `ITEM9_DISTINCT_RTH_DATES`=1/3; Item 7 governed rows **0** |

## Recommended next RTH operator actions

1. Night before: `git fetch origin main`; confirm **CURRENT_MAIN** / **CURRENT_SOFTWARE_IMPLEMENTATION** in [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md).
2. Morning: bootstrap venv/state path; start platform; confirm `:8766` / `:5173`.
3. T−15: run full preflight block including `item9 next-rth-preflight`; set temporary Finviz/catalyst gates; confirm OpenD loopback.
4. ≥ 09:30 only: when preflight allows, run Finviz watch → governed Item 9 `--poll` (frozen collector) → `corpus-status` → Item 7 status → ops dry-run; summarize.
5. Confirm empirical gates remain unflipped unless governed JSON receipts exist; Live stays OFF; do not merge [#222](https://github.com/AdamEddahmouni/market-trading-platform/pull/222).
