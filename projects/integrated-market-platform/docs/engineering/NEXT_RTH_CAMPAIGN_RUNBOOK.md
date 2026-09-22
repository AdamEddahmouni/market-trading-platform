# Next US equity RTH campaign runbook (post–IMP-EVIDENCE-HARDENING-02)

**Evidence class:** SOFTWARE coordination only. **Live OFF.** No Paper/Live orders. No empirical locks. Do not declare FTEP `EMPIRICAL_ACTIVE`.

This document is the **current-main** operator surface for the **next** US equity regular-hours (RTH) window. It does **not** rewrite Sep 15 empirical findings or Sep 17 frozen receipts.

**Monday 2026-09-21 mechanical Item 9 checklist** (frozen collector SHA, `$rcpt`, `121031` prohibition, READY_TO_COLLECT vs wait): [MONDAY_ITEM9_PREFLIGHT.md](MONDAY_ITEM9_PREFLIGHT.md). That page does **not** pin **CURRENT_MAIN** — use [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) for the mutable git tip.

## Authority layers (do not conflate)

| Label | Git SHA | Role |
|-------|---------|------|
| **CURRENT_MAIN** (alias **CURRENT_GIT_MAIN** in [PROGRAM_STATUS](../platform/PROGRAM_STATUS.md)) | `5b74876d5f4c48aa1b03ff987e6390469bb08c1c` | Mutable `origin/main` tip after [#380](https://github.com/AdamEddahmouni/market-trading-platform/pull/380) durable serving opportunity book (schema v9; Live **OFF**; parents `b6e8e2b9` / `a2fea490`; ancestry includes [#379](https://github.com/AdamEddahmouni/market-trading-platform/pull/379) progress-aware liveness). **Historical** pin `1cd63fe9` after [#376](https://github.com/AdamEddahmouni/market-trading-platform/pull/376) is **not** the current tip. Confirm with `git rev-parse origin/main` after `git fetch origin main`. **Not** **ITEM9_FROZEN_COLLECTOR**. |
| **CURRENT_SOFTWARE_IMPLEMENTATION** | `5b74876d5f4c48aa1b03ff987e6390469bb08c1c` | Tip software merge [#380](https://github.com/AdamEddahmouni/market-trading-platform/pull/380) (ancestry [#379](https://github.com/AdamEddahmouni/market-trading-platform/pull/379)/[#376](https://github.com/AdamEddahmouni/market-trading-platform/pull/376)). Matches **CURRENT_MAIN**. **Not** empirical evidence. Calibration **not** executed. |
| **ITEM9_FROZEN_COLLECTOR** | `fed2d9f7e183aecfcac61a7664df69aafc12ea25` | Governed Mode B `--poll` checkout `.imp-actual-01-phase-d/` @ this SHA — **not** **CURRENT_MAIN**. |
| **SEP15_FROZEN_EMPIRICAL_AUTHORITY** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` | Sep 15 observational historical pin — **not** overridden by this runbook. |
| **RTH15 repair train (ancestry)** | merged through `6e9e88b` ([#203](https://github.com/AdamEddahmouni/market-trading-platform/pull/203)–[#218](https://github.com/AdamEddahmouni/market-trading-platform/pull/218), [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205)) | #205/#208 hops are **SOFTWARE**; **historical** serving composition was in-memory OE. Current serving book is local_state SQLite schema v9 ([#380](https://github.com/AdamEddahmouni/market-trading-platform/pull/380)); persist-off is `INTENTIONAL_EPHEMERAL`. Acceptance suite ≠ two-process RTH hop; not empirical RTH readiness. |

Canonical status authority: [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) (Item 9 pins and Lane F OpenD v3 closeout: [IMP program status header](../platform/PROGRAM_STATUS.md#imp-program-status) and [Lane F closure](../platform/PROGRAM_STATUS.md#imp-opend-fill-economics-v3--lane-f-statusdocs-closure)). Do **not** retarget **ITEM9_FROZEN_COLLECTOR** when reconciling operator docs.

**Checklist overlap:** [#207](https://github.com/AdamEddahmouni/market-trading-platform/pull/207) (head `ca3c53a9`) owns deltas to [TUESDAY_RTH_OPERATOR_CHECKLIST.md](TUESDAY_RTH_OPERATOR_CHECKLIST.md), [RTH_EMPIRICAL_OPS_RUNBOOK.md](RTH_EMPIRICAL_OPS_RUNBOOK.md), and `artifacts/ftep-v1-002/SIGNAL_ONLY_LAUNCH_PREP.md`. **Not on `main`** until merge — use current `main` files plus this page.

## Campaign timing (US/Eastern)

| Phase | When | Intent |
|-------|------|--------|
| **Pre-catalyst (optional)** | Before **09:30** cash open (operator choice; e.g. 09:00–09:25) | Finviz prospective ingress when gates enabled — improves catalyst capture without crossing into execution |
| **T−15** | ≈ **09:15** | Preflight, persistence path, temporary session gates |
| **Cash open transition** | **09:30** | Finviz live ingress, Item 9 `--poll` (frozen collector), Item 7 status/collect, ops dry-run bundle |
| **Session close** | **16:00** | Summarize, env cleanup, independent review |

Off-hours `python tools/imp.py item9 next-rth-preflight --json` must show `calendar.rth_active=false` — that is **software success** for the calendar gate, not empirical failure. Overall disposition may be `WRONG_RUNTIME` when the command runs from a **CURRENT_GIT_MAIN** / software worktree checkout (e.g. `5b74876d…` on `main`, **not** the frozen collector) instead of **ITEM9_FROZEN_COLLECTOR** (`fed2d9f7…`); collection still starts only from the frozen checkout. When runtime matches frozen authority off-hours, disposition is `NOT_RTH` (exit 0). Process listing for duplicate `--poll` is **tools-only** ([#251](https://github.com/AdamEddahmouni/market-trading-platform/pull/251)); `imp.py item9` reports `process_probe_status=COMPLETED`. Do **not** run governed Item 9 prospective collection off-hours.

**Governed receipt directory:** corpus-admissible Item 9 JSON lives under the **frozen collector IMP root**, not an empty software worktree copy:

`{repo}/.imp-actual-01-phase-d/projects/integrated-market-platform/artifacts/ftep-v1-002/item9-prospective-proof-receipts/`

Post-session read-only status (from any 3.11 `.venv` with `PYTHONPATH=src`):

```powershell
$rcpt = Join-Path (git rev-parse --show-toplevel) ".imp-actual-01-phase-d\projects\integrated-market-platform\artifacts\ftep-v1-002\item9-prospective-proof-receipts"
python tools\item9_corpus_status.py corpus-status --receipt-dir $rcpt
```

Expect **`sample_gate.status=SAMPLE_GATE_MET`** and **`sample_gate_progress.distinct_rth_dates` = `3/3`** after 2026-09-21 (admitted **2026-09-17**, **2026-09-18**, **2026-09-21**). Still **`item9_status=PARTIAL_NOT_CALIBRATED`**, **`calibrated=false`**, **`fitting_allowed=false`**. **`ITEM9_CALIBRATION_RUN` = FORBIDDEN** — no automatic fitting. Do **not** backfill the Sep 21 **≈10:43–13:09 ET** **`NOT_OBSERVED`** gap.

## Workstation bootstrap (once per day)

```powershell
cd projects\integrated-market-platform
python tools\imp.py env bootstrap --link-venv   # linked worktrees: creates .venv symlink
$report = python tools\state_path_diagnostic.py | ConvertFrom-Json
$env:IMP_STATE_DIR = $report.canonical_state_dir
$env:IMP_PERSIST_STATE = "1"
```

Use the project **CPython 3.11** `.venv` only (`python tools\imp.py env`). Never commit session gates.

## Platform surfaces (**CURRENT_SOFTWARE_IMPLEMENTATION** `5b74876d`)

| Check | Endpoint / command | Notes |
|-------|-------------------|--------|
| SPA root | `http://127.0.0.1:5173/` | Canonical operator entry (#206); not `/discover` as primary |
| Control center | `http://127.0.0.1:5173/control` | Lifecycle, masked provider config |
| UI Diagnostics | `http://127.0.0.1:5173/diagnostics/provider` | SPA route — **not** `:8766` |
| UI API | `http://127.0.0.1:8766` | `tools\ui1\run_ui_api.py --serve --port 8766` |
| Operator diagnostics snapshot | `GET http://127.0.0.1:8766/operator/diagnostics` | Read-only aggregate ([#289](https://github.com/AdamEddahmouni/market-trading-platform/pull/289)); **does not** start collectors |
| Launcher supervisor | `http://127.0.0.1:8767` | Loopback-only; Windows launcher |
| OE ranked feed API | `GET /opportunities/summary` | Ranked opportunity rows from serving book (local_state schema v9 when persist on) |
| EventV1 ingress | `POST /intelligence/ingest/news` via `build_production_observation_ingress_router` | Composed hop: news → EventV1/PIT → observational catalyst detector → OpportunityV1. **Not** BUILD 09 `EventDetectorEngine` (`NEWS_EVENT` `INACTIVE_INPUT_UNAVAILABLE`). **Not** `OpportunityEngine.assess`. Empirical capture **RTH-only**. |
| Grok / async enrichment | Durable worker **OFF by default** (#189) | **Not** `GROK_AUTOMATION_PRODUCTION_ACTIVE`; opt-in only |

Start/stop: `START_PLATFORM.cmd` / `STOP_PLATFORM.cmd` or [DEVELOPER_RUNBOOK.md](DEVELOPER_RUNBOOK.md).

### Read-only health probes (no orders)

A bound port or HTTP 200 is **not** HEALTHY ([#379](https://github.com/AdamEddahmouni/market-trading-platform/pull/379)). Inspect `service_liveness` on `/provider/health` and `readiness_vs_liveness` on `/operator/diagnostics`.

```powershell
curl -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8766/provider/health
curl -s http://127.0.0.1:8766/provider/health
curl -s -o NUL -w "%{http_code}`n" http://127.0.0.1:8766/context
curl -s -o NUL -w "%{http_code}`n" "http://127.0.0.1:8766/opportunities/summary"
curl -s -o NUL -w "%{http_code}`n" "http://127.0.0.1:8766/operator/diagnostics"
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

### Item 9 `READY_TO_COLLECT` gate (fail closed — no collection in this doc)

Run only from **`.imp-actual-01-phase-d`** @ **`fed2d9f7`** during **US equity cash RTH** (≥ 09:30 ET). A running `--poll` process alone is **not** sufficient.

| Gate | Required |
|------|----------|
| Calendar | `calendar.rth_active=true`; session date is a **new** distinct US cash RTH date only when collecting beyond the already-admitted set (**2026-09-17**, **2026-09-18**, **2026-09-21**) |
| Runtime | `runtime.runtime_matches_frozen_authority=true`; `current_git_sha` = **`fed2d9f7`** |
| Collector | Exactly **one** governed checkout `.imp-actual-01-phase-d`; **`ACTIVE_COLLECTORS=0`** before start |
| Receipt dir | Writable governed path under frozen collector IMP root (see above) |
| Provider | OpenD loopback reachable; required evidence fresh enough for Mode B |
| Policy | **`ITEM9_CALIBRATION_RUN=FORBIDDEN`**; Live **OFF**; outage epoch **`121031`** **not** backfilled |
| Disposition | Preflight JSON **`disposition=READY_TO_COLLECT`** — operator still starts `--poll` manually |

Off-hours or software-worktree preflight may show **`WRONG_RUNTIME`** or **`NOT_RTH`** — expected; **do not** collect.

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
| **Item 9 corpus** | `python tools\item9_corpus_status.py corpus-status --receipt-dir` → frozen collector path above | After receipt; no automatic fitting; **`ITEM9_CALIBRATION_RUN=FORBIDDEN`** |
| **Item 7** | `item7_corpus_collector.py status|diagnose|collect …`; optional `item7_opend_capture_append.py` | Governed rows **0** until earned; auto-persist **SOFTWARE/CONTROLLED** only |
| Ops bundle | `python tools\rth_empirical_ops.py --json run-observational` | Optional `--write-run-artifact`; dry-run (`live_ingress=False`) |
| Close | `python tools\rth_empirical_ops.py --json summarize` | |

## Receipts, latency, logs

| Artifact | Path |
|----------|------|
| Item 9 prospective proof | `{repo}/.imp-actual-01-phase-d/projects/integrated-market-platform/artifacts/ftep-v1-002/item9-prospective-proof-receipts/` (governed; not an empty software-worktree copy) |
| RTH ops run bundle | `$env:IMP_STATE_DIR/rth-empirical-ops/runs/RTHOPS-*.json` with `--write-run-artifact` |
| Finviz / FTEP / Item 7 | JSON stdout; operator copies under governed `.local` policy |
| Hot-path latency evidence | Gate `PROSPECTIVE_HOT_PATH_LATENCY_CAPTURED` — software wired (#166/#154); **no** live RTH receipt until earned |
| API / UI logs (launcher) | `.local/platform-backend.log`, `.local/platform-ui.log`, `.local/platform-control.log` |
| Persistence (FTEP-V1-002 + serving book) | SQLite `imp-state.sqlite3` under `IMP_STATE_DIR` when `IMP_PERSIST_STATE=1` (**schema v9**). Persist-off: `INTENTIONAL_EPHEMERAL`. |

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
| [#251](https://github.com/AdamEddahmouni/market-trading-platform/pull/251) | Item 9 next-RTH preflight (superseded as software tip by [#271](https://github.com/AdamEddahmouni/market-trading-platform/pull/271)–[#274](https://github.com/AdamEddahmouni/market-trading-platform/pull/274)) | `a1b556f89c8e68e84fe7246c6e726359f3a0ebf8` |
| [#272](https://github.com/AdamEddahmouni/market-trading-platform/pull/272) | Non-stub IBP facts SUT (supersedes closed [#267](https://github.com/AdamEddahmouni/market-trading-platform/pull/267)) | `ccc41a7f` |
| [#274](https://github.com/AdamEddahmouni/market-trading-platform/pull/274) | Lane E OpenD v3 findings (**CURRENT_SOFTWARE_IMPLEMENTATION** landing) | `e0ab919f6bfe0d681f035d7e00c4f609d596f74b` |
| [#252](https://github.com/AdamEddahmouni/market-trading-platform/pull/252) | IBKR historical TRADE pagination (Lane C) | `2d4a6d37` |
| [#250](https://github.com/AdamEddahmouni/market-trading-platform/pull/250) | Holdout consumption guards (Lane B) | `f533413e` |
| [#249](https://github.com/AdamEddahmouni/market-trading-platform/pull/249) | Historical session calendar + quality (Lane D) | `3dc472cd` |
| [#248](https://github.com/AdamEddahmouni/market-trading-platform/pull/248) | Path A label linker (Lane A) | `700b5be6` |
| [#246](https://github.com/AdamEddahmouni/market-trading-platform/pull/246) | Dual-corpus historical development e2e demo | `da237fd1` |
| [#210](https://github.com/AdamEddahmouni/market-trading-platform/pull/210) | Item 7 upstream SNAPSHOT_BBO capture envelope | `73da9fdb` |
| [#208](https://github.com/AdamEddahmouni/market-trading-platform/pull/208) | SOFTWARE fullstack acceptance | `6e9e88b` |
| [#207](https://github.com/AdamEddahmouni/market-trading-platform/pull/207) | Finviz ingress reliability / receipts | **OPEN** head `ca3c53a9` — `<pending merge on main>` |

## Next lawful RTH preopen checklist

**Evidence class:** SOFTWARE coordination. **Live OFF.** Success is the lawful information/decision chain (git pin → providers → EventV1/PIT news hop → ranked book → non-execution WATCH/DISMISS traces/reviews → evidence path), **not** a trade. Zero qualifying events is a valid market result (`EMPTY` / `LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS`). Do **not** backfill missed live-interval market data. Dated 2026-09-15 command tables remain historical: [TUESDAY_RTH_OPERATOR_CHECKLIST.md](TUESDAY_RTH_OPERATOR_CHECKLIST.md).

Run from IMP root `projects/integrated-market-platform/` on the **runtime** checkout (not a dirty detached workspace). Until a later pin, expected software SHA is `5b74876d5f4c48aa1b03ff987e6390469bb08c1c`.

| # | Check | Command / path | Pass token |
|---|-------|----------------|------------|
| 1 | Git SHA | `git fetch origin main`; `git rev-parse origin/main`; `git rev-parse HEAD` | Exact `5b74876d5f4c48aa1b03ff987e6390469bb08c1c` until a later **CURRENT_MAIN** pin. **Not** **ITEM9_FROZEN_COLLECTOR** `fed2d9f7`. |
| 2 | Clean runtime tree | `git status --short --branch` on the runtime checkout | No unrelated dirty/untracked product files. Do not clean another lane's tree. |
| 3 | Clock / timezone | `python -c "from datetime import datetime; from zoneinfo import ZoneInfo; print(datetime.now(ZoneInfo('America/New_York')).isoformat())"` | America/New_York wall clock; session kind from `market_sessions` (`PREMARKET`/`REGULAR`/`AFTER_HOURS`/`CLOSED`). |
| 4 | Provider processes and connectivity | `python tools/provider_readiness.py --probe-local --json`; OpenD loopback `127.0.0.1:11111`; optional `python tools/moomoo/probe.py` | Loopback ports probed only; no external orders. Unreachable OpenD stays fail-closed. |
| 5 | Entitlements | `python tools/provider_readiness.py --json`; `python tools/imp.py providers campaign-readiness FTEP-V1-002 --json` | Capability/entitlement rows present; missing entitlement is `UNAVAILABLE` / `ENTITLEMENT_MISSING`, not HEALTHY. |
| 6 | Secrets presence (no values) | `python tools/imp.py env`; `python tools/provider_readiness.py --json` | Presence/absence only. Payload `secrets_included=false`. Never print `FINVIZ_API_KEY` / `APCA_*` / token files. |
| 7 | API / UI / liveness | `GET http://127.0.0.1:8766/provider/health`, `/context`, `/operator/diagnostics`; UI `http://127.0.0.1:5173/` | Inspect `service_liveness` and `readiness_vs_liveness`. Bound port ≠ HEALTHY. `TRANSPORT_UP_APPLICATION_NOT_PROGRESSED` is UNREADY. |
| 8 | Persistence path | `python tools/imp.py state-path`; `$report = python tools/state_path_diagnostic.py \| ConvertFrom-Json`; persist-on: `$env:IMP_STATE_DIR=$report.canonical_state_dir`; `$env:IMP_PERSIST_STATE='1'`; DB `$env:IMP_STATE_DIR\imp-state.sqlite3` | Persist on → local_state SQLite **schema v9** (`SELECT schema_version FROM schema_meta`). Persist off → `INTENTIONAL_EPHEMERAL`. Empty worktree `.local` is not proof of no FTEP sessions. |
| 9 | Opportunity book health | `GET /opportunities/summary` | `EMPTY` / `UNREADY` / `READY` / `UNAVAILABLE` as honest feed tokens. Persist-on book survives API restart (schema v9). Zero rows is valid. |
| 10 | EventV1 / PIT hop | Serving hop: production news ingress `POST /intelligence/ingest/news` → EventV1/PIT → observational catalyst detector → OpportunityV1. RTH watch: `python tools/ftep_watch_catalysts.py FTEP-V1-002 --live-ingress --json` | Composed news hop only. **Explicit:** BUILD 09 `EventDetectorEngine` remains unwired (`NEWS_EVENT` `INACTIVE_INPUT_UNAVAILABLE`). `OpportunityEngine.assess` remains unwired (needs ForecastV1). Do not describe them as composed. |
| 11 | Ranked API | `GET /opportunities/summary` and `GET /opportunities/{id}` | Ranked projection from serving repository. Fixture/replay cards stay on `DEMO_REPLAY` shelf. |
| 12 | DecisionTrace / TradeReview | Persist-on tables `execution_decision_traces` and `trade_reviews` on `imp-state.sqlite3`; HTTP `GET /intelligence/trade-reviews?opportunity_id=` | WATCH/DISMISS may persist `ExecutionDecisionTraceV1` + `TradeReviewV1` in **non-execution** modes. Not a fill. Persist-off stays ephemeral. |
| 13 | Live safety | `GET /operator/diagnostics` `live-execution`; Live remains **OFF** | `allows_network_submit` remains **false**. `attempt_network_submit` forbidden. Do not set live broker gates. |
| 14 | Paper safety | Do not start Paper EXECUTION from this checklist. Missing Alpaca keys → `COMPARATOR_NOT_CONFIGURED` | Not Paper-validated. Not `CALIBRATED`. Dry-run / SIGNAL_ONLY ≠ Paper submit. |
| 15 | Evidence output path | Finviz/FTEP JSON stdout; optional copies under governed `.local`; Item 9 receipts only under frozen collector `$rcpt` | Do not write receipts onto **CURRENT_MAIN** artifacts copy. Do not rewrite frozen empirical `7aade60`. |
| 16 | Campaign / run id | Campaign **FTEP-V1-002**; sessions **BASELINE** `fts-6DB7771FD9B3A991`, **AI_ENHANCED** `fts-D93189A042A1BEF2`; ops bundle `operator_run_id=RTHOPS-*` | `python tools/imp.py ftep integrity-check FTEP-V1-002 --json` PASS against canonical `IMP_STATE_DIR`. FTEP **not** `EMPIRICAL_ACTIVE`. |
| 17 | Logging | `.local/platform-backend.log`, `.local/platform-ui.log`, `.local/platform-control.log` | Logs exist and rotate under operator policy. No secret values in log paste. |
| 18 | Disk space | `python tools/imp.py storage audit` | Read-only inventory. Output is **not** deletion authority. Act only if warnings block the session. |
| 19 | Recovery | `STOP_PLATFORM.cmd`; `tools/ui1/restart_ui_api.ps1` after env changes; clear `IMP_FINVIZ_LIVE` / `IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS` | Do **not** delete governed SQLite or receipts. Integrity FAIL → fix `IMP_STATE_DIR` before live ingress. |
| 20 | No market-data backfill | If the live interval is missed | Leave `NOT_OBSERVED` / `UNAVAILABLE`. Do not backfill Item 9 gaps, Sep 18 epoch `121031`, or missed news rows. |

Item 9 Mode B `--poll` stays frozen-collector-only. This preopen does **not** authorize calibration fitting, Paper validation claims, Full30, or Live.

## Pre-RTH verification checklist (off-session)

The table above is the **next lawful** preopen. Off-session minimum:

| Check | Status | Notes |
|-------|--------|-------|
| PROGRAM_STATUS header vs `git rev-parse origin/main` | Operator | `git fetch origin main`; confirm **CURRENT_SOFTWARE_IMPLEMENTATION** / **ITEM9_FROZEN_COLLECTOR** in [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) — tip **`5b74876d`** through [#380](https://github.com/AdamEddahmouni/market-trading-platform/pull/380) |
| **ITEM9_FROZEN_COLLECTOR** worktree | Operator | `.imp-actual-01-phase-d` @ `fed2d9f7` |
| Python 3.11 + `.venv` | Operator | `python tools\imp.py env bootstrap --link-venv` |
| OpenD loopback | Operator | Required for Item 9 collection |
| `item9 next-rth-preflight` | Operator | Off-hours `NOT_RTH` expected |
| Campaign / Live OFF | **Policy** | FTEP not `EMPIRICAL_ACTIVE`; Moomoo/IBKR **`PROVIDER_UNVERIFIED`** unless operator earns live receipts |
| Item 9 / Item 7 gates | **Unearned beyond sample gate** | `ITEM9_CALIBRATED`=NO; `SAMPLE_GATE_MET`; `PARTIAL_NOT_CALIBRATED`; `ITEM9_DISTINCT_RTH_DATES`=**3**/3 (admitted **2026-09-17** + **2026-09-18** + **2026-09-21**); `fitting_allowed=false`; calibration **FORBIDDEN**; Item 7 governed rows **0** |

## Recommended next RTH operator actions

1. Night before: `git fetch origin main`; confirm **CURRENT_SOFTWARE_IMPLEMENTATION** `5b74876d` and **ITEM9_FROZEN_COLLECTOR** `fed2d9f7` in [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) (do not conflate git tip with collector pin).
2. Morning: run [next lawful RTH preopen checklist](#next-lawful-rth-preopen-checklist); bootstrap venv/state path; start platform; confirm liveness (`service_liveness` — bound port is not HEALTHY).
3. T−15: run full preflight block including `item9 next-rth-preflight`; set temporary Finviz/catalyst gates; confirm OpenD loopback.
4. ≥ 09:30 only: when preflight allows, run Finviz watch → ranked `/opportunities/summary` (zero rows valid) → governed Item 9 `--poll` (frozen collector) → `corpus-status` → Item 7 status → ops dry-run; summarize. Success is the information/decision chain, not a trade.
5. Confirm empirical gates remain unflipped unless governed JSON receipts exist; Live stays OFF. Do not backfill a missed live interval. [#222](https://github.com/AdamEddahmouni/market-trading-platform/pull/222) is **CLOSED** (not merged); [#370](https://github.com/AdamEddahmouni/market-trading-platform/pull/370) superseded it.
