# Next US equity RTH campaign runbook (post–IMP-EVIDENCE-HARDENING-02)

**Current launch authority:** [RTH_OBS_NEWS_20260925_LAUNCH.md](RTH_OBS_NEWS_20260925_LAUNCH.md). The SHA table below is historical and is not the next campaign runtime. Sep 24 `RTH-OBS-NEWS-20260924` remains `OPERATIONAL_ONLY` / not armed. Sep 23 remains `PARTIAL_LATE_ARM`.

**Evidence class:** SOFTWARE coordination only. **Live OFF.** No Paper/Live orders. No empirical locks. Do not declare FTEP `EMPIRICAL_ACTIVE`.

This document is the **current-main** operator surface for the **next** US equity regular-hours (RTH) window. It does **not** rewrite Sep 15 empirical findings or Sep 17 frozen receipts.

**Monday 2026-09-21 mechanical Item 9 checklist** (frozen collector SHA, `$rcpt`, `121031` prohibition, READY_TO_COLLECT vs wait): [MONDAY_ITEM9_PREFLIGHT.md](MONDAY_ITEM9_PREFLIGHT.md). That page does **not** pin **CURRENT_MAIN** — use [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) for the mutable git tip.

## Authority layers (do not conflate)

| Label | Git SHA | Role |
|-------|---------|------|
| **SEP23_CLOSED_RUNTIME** | `bf405f468bee4e70f8a40e97eaaf6c2d46c75e64` | **Closed** observational runtime for campaign `RTH-OBS-NEWS-20260923`. Runtime **tree** SHA `c3b5a08b94e93e4ead3c9802092ecdebea1c3434`. Terminal class **`PARTIAL_LATE_ARM`**. **Do not** retarget this SHA. **Do not** re-arm it. |
| **FROZEN_RUNTIME** (alias **CANDIDATE_RUNTIME**) | `1cbc8b0551179e1724033ee0036fb3366174daca` | **Frozen, not armed** runtime for campaign `RTH-OBS-NEWS-20260924`. Tree `c673ada98b7f3dc56f1073fe65854984259a800d`. The `2026-09-24` cash session closed unarmed (`OPERATIONAL_ONLY`). **Do not** move this SHA. **Do not** treat that session as coverage. A future RTH day is still required. Procedure history: [RTH_OBS_NEWS_20260924_FREEZE.md](RTH_OBS_NEWS_20260924_FREEZE.md). Session record: [RTH_OBS_NEWS_20260924_SESSION.md](RTH_OBS_NEWS_20260924_SESSION.md). |
| **CURRENT_MAIN** (alias **CURRENT_GIT_MAIN**) | `147a248bcc9d00e1edd157868dbd74ba6dfacd06` (confirm with `git rev-parse origin/main`) | Git tip after [#413](https://github.com/AdamEddahmouni/market-trading-platform/pull/413). **Not** the Sep 24 frozen runtime. **Not** **ITEM9_FROZEN_COLLECTOR**. |
| **CURRENT_SOFTWARE_IMPLEMENTATION** | `1cbc8b0551179e1724033ee0036fb3366174daca` | Sep 24 frozen runtime. Software only. **Not** empirical evidence. Calibration **not** executed. Historical Smoke10 `ibp-smoke10-8C23029DD46FDA78` remains **FAIL 10/10** and was not rerun. |
| **ITEM9_FROZEN_COLLECTOR** | `fed2d9f7e183aecfcac61a7664df69aafc12ea25` | Governed Mode B `--poll` checkout `.imp-actual-01-phase-d/` @ this SHA — **not** **CURRENT_MAIN**. |
| **SEP15_FROZEN_EMPIRICAL_AUTHORITY** | `7aade60bf8041df5ebf9f0ac856d5d8802845c8d` | Sep 15 observational historical pin — **not** overridden by this runbook. |
| **RTH15 repair train (ancestry)** | merged through `6e9e88b` ([#203](https://github.com/AdamEddahmouni/market-trading-platform/pull/203)–[#218](https://github.com/AdamEddahmouni/market-trading-platform/pull/218), [#205](https://github.com/AdamEddahmouni/market-trading-platform/pull/205)) | #205/#208 hops are **SOFTWARE**; **historical** serving composition was in-memory OE. Current serving book is local_state SQLite schema v9 ([#380](https://github.com/AdamEddahmouni/market-trading-platform/pull/380)); persist-off is `INTENTIONAL_EPHEMERAL`. Acceptance suite ≠ two-process RTH hop; not empirical RTH readiness. |

Canonical status authority: [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) (Item 9 pins and Lane F OpenD v3 closeout). Do **not** retarget **ITEM9_FROZEN_COLLECTOR** when reconciling operator docs. Supervision contract: [CAMPAIGN_SUPERVISION_HEARTBEAT.md](CAMPAIGN_SUPERVISION_HEARTBEAT.md).

**Closed observational campaign (2026-09-22):** Segments **A** (`24a59220`) and **B** (`8e92bb37`) are **CLOSED** — see [PROGRAM_STATUS RTH-OBS-NEWS-20260922](../platform/PROGRAM_STATUS.md#rth-obs-news-20260922--segment-ab-close-additive). Segment B mid-session gap **`14:26:00.749`–`14:57:27.624` ET** remains **`NOT_OBSERVED`** (root cause **UNKNOWN**). Do **not** rewrite historical Sep 22 docs to claim prevention. **ZERO** prospective-current opportunities on Segment B — do not invent one. Item 9 remains **`PARTIAL_NOT_CALIBRATED`** / **`DO_NOT_PROMOTE`**. Item 7 governed/PIT-valid BBO counts remain **0**.

**Closed campaign `RTH-OBS-NEWS-20260923`:** armed `2026-09-23 13:03:32.789458 -04:00` on runtime `bf405f468bee4e70f8a40e97eaaf6c2d46c75e64`, terminal class **`PARTIAL_LATE_ARM`**, shutdown `RTH_CLOSE_SHUTDOWN`. Pre-arm RTH is **`NOT_OBSERVED`**. Do **not** resume or re-arm this id or this SHA. Closeout: [RTH_OBS_NEWS_20260923_CLOSEOUT.md](RTH_OBS_NEWS_20260923_CLOSEOUT.md). The 2026-09-22 night freeze note (`FROZEN_NOT_ARMED`, freeze timestamp `2026-09-22T23:46:17-04:00`) is the pre-session record only.

**Sep 24 session:** `RTH-OBS-NEWS-20260924` on frozen runtime `1cbc8b0551179e1724033ee0036fb3366174daca` closed **unarmed**. Evidence class **`OPERATIONAL_ONLY`**. Do not arm that id for a missed window. A future trading day needs a new freeze before any arm. History: [RTH_OBS_NEWS_20260924_FREEZE.md](RTH_OBS_NEWS_20260924_FREEZE.md). Record: [RTH_OBS_NEWS_20260924_SESSION.md](RTH_OBS_NEWS_20260924_SESSION.md). [#403](https://github.com/AdamEddahmouni/market-trading-platform/pull/403) is software inside the frozen runtime. It is not Sep 23 proof and not `EMPIRICALLY_PROVEN`.

**PR [#384](https://github.com/AdamEddahmouni/market-trading-platform/pull/384) merged** onto this main: benchmark protocol + deterministic-stub Smoke10 pin (`SOFTWARE_CONTROLLED`). Real-system RTH15-11 Smoke10 remains **NOT_EXECUTED**. Benchmark is still **not** an arm blocker.

**Checklist overlap:** [#207](https://github.com/AdamEddahmouni/market-trading-platform/pull/207) (head `ca3c53a9`) owns deltas to [TUESDAY_RTH_OPERATOR_CHECKLIST.md](TUESDAY_RTH_OPERATOR_CHECKLIST.md), [RTH_EMPIRICAL_OPS_RUNBOOK.md](RTH_EMPIRICAL_OPS_RUNBOOK.md), and `artifacts/ftep-v1-002/SIGNAL_ONLY_LAUNCH_PREP.md`. **Not on `main`** until merge — use current `main` files plus this page.

## Campaign supervision (required before arm)

An observational arm is **unlawful** without durable campaign-supervision state. Detail: [CAMPAIGN_SUPERVISION_HEARTBEAT.md](CAMPAIGN_SUPERVISION_HEARTBEAT.md).

| Concern | Binding on the **next** arm (closed `bf405f46` is not this binding) |
|---------|-----------------------------------------------|
| State directory | `{IMP_STATE_DIR}/campaign-supervision/` → `ownership.json`, `heartbeat.json`, `outages.jsonl` |
| Supervisor identity | `supervisor_identity=imp-campaign-supervisor`; default required roles `supervisor,poller,api` |
| Arm token | `arm_status=ARMED_RUNNING` is **arm only** — **never** proof of liveness |
| Heartbeat defaults | heartbeat cadence **15s**; poll cadence **30s**; stale after **90s**; starting grace **60s** |
| Expected cycle | `expected_next_cycle_utc` / `expected_next_poll_utc` must advance on real progress — **no synthetic polls** |
| Execution authority | `execution_authority=BLOCKED`, `execution_mode=NONE`, `allows_network_submit=false`, `BUILD28_LIVE_SUBMIT_FORBIDDEN` |
| Proven spawn (SOFTWARE_CONTROLLED) | Windows default `CREATE_NEW_PROCESS_GROUP \| CREATE_NO_WINDOW` survives Python **parent-process** exit |
| UNPROVEN | Windows job-kill / terminal independence / `CREATE_BREAKAWAY_FROM_JOB` — product guarantee is **fail-visible** stale/dead detection, not OS detachment |
| Liveness vs freshness | Healthy supervision ≠ fresh provider data ≠ Opportunity Engine quality ≠ Item 9 calibration |

```powershell
# Preflight mechanism (read-only) — does not arm
python tools/platform/campaign_supervisor.py mechanism
python tools/platform/campaign_supervisor.py status --state-dir $env:IMP_STATE_DIR

# Lawful arm shape (DO NOT RUN from this docs-only session; operator only after §26)
# python tools/platform/campaign_supervisor.py arm `
#   --state-dir $env:IMP_STATE_DIR `
#   --campaign-id <id> `
#   --observation-window-id <window> `
#   --segment-id <segment> `
#   --runtime-sha bf405f468bee4e70f8a40e97eaaf6c2d46c75e64 `
#   --poll-cadence-seconds 30 `
#   --heartbeat-cadence-seconds 15 `
#   --stale-after-seconds 90
# python tools/platform/campaign_supervisor.py run --state-dir $env:IMP_STATE_DIR --auto-poll
```

## Campaign timing (US/Eastern)

| Phase | When | Intent |
|-------|------|--------|
| **Pre-catalyst (optional)** | Before **09:30** cash open (operator choice; e.g. 09:00–09:25) | Finviz prospective ingress when gates enabled — improves catalyst capture without crossing into execution |
| **T−15** | ≈ **09:15** | Preflight, persistence path, temporary session gates |
| **Cash open transition** | **09:30** | Finviz live ingress, Item 9 `--poll` (frozen collector), Item 7 status/collect, ops dry-run bundle |
| **Session close** | **16:00** | Summarize, env cleanup, independent review |

Off-hours `python tools/imp.py item9 next-rth-preflight --json` must show `calendar.rth_active=false` — that is **software success** for the calendar gate, not empirical failure. Overall disposition may be `WRONG_RUNTIME` when the command runs from a **CURRENT_GIT_MAIN** / software worktree checkout (e.g. `bf405f46…` on `main`, **not** the frozen collector) instead of **ITEM9_FROZEN_COLLECTOR** (`fed2d9f7…`); collection still starts only from the frozen checkout. When runtime matches frozen authority off-hours, disposition is `NOT_RTH` (exit 0). Process listing for duplicate `--poll` is **tools-only** ([#251](https://github.com/AdamEddahmouni/market-trading-platform/pull/251)); `imp.py item9` reports `process_probe_status=COMPLETED`. Do **not** run governed Item 9 prospective collection off-hours.

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

## Platform surfaces (**FROZEN_RUNTIME** `bf405f46`, **FROZEN_NOT_ARMED** / `frozen=yes`)

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

1. Prefer deliberate campaign shutdown: `python tools/platform/campaign_supervisor.py shutdown --state-dir $env:IMP_STATE_DIR` (add `--rth-close` at session end).
2. `Remove-Item Env:IMP_FINVIZ_LIVE, Env:IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS -ErrorAction SilentlyContinue`
3. `STOP_PLATFORM.cmd` or kill stale `:8766` / `:5173` / `:8767` listeners (`tools\ui1\restart_ui_api.ps1` after env changes).
4. Do **not** delete governed SQLite, empirical receipts, or `campaign-supervision/outages.jsonl`; archive operator JSON under `.local` if needed.
5. If preflight `integrity_disposition=FAIL`, fix `IMP_STATE_DIR` / manifest drift before any live ingress.
6. Deliberate `recover` only — preserves original arm/segment/runtime SHA/outages; does not mint a covering segment.
7. After future **software** merges that must change the armed runtime, **invalidate** this freeze (preserve the record), mint a **new campaign version**, and declare a new freeze — never silently move SHA under `RTH-OBS-NEWS-20260923`. Docs-only tips do not retarget **FROZEN_RUNTIME**. Pin [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) separately when needed.

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

**Evidence class:** SOFTWARE coordination. **Live OFF.** Success is the lawful information/decision chain (git pin → supervision → providers → EventV1/PIT news hop → ranked book → non-execution WATCH/DISMISS traces/reviews → evidence path), **not** a trade. Zero qualifying events is a valid market result (`EMPTY` / `LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS`). Do **not** backfill missed live-interval market data. Dated 2026-09-15 command tables remain historical: [TUESDAY_RTH_OPERATOR_CHECKLIST.md](TUESDAY_RTH_OPERATOR_CHECKLIST.md).

The command order for `RTH-OBS-NEWS-20260924` is [RTH_OBS_NEWS_20260924_FREEZE.md](RTH_OBS_NEWS_20260924_FREEZE.md). This table is the supporting check list for that procedure. Do not invent a second launch path. `RTH-OBS-NEWS-20260923` on `bf405f46` stays closed.

| # | Check | Command / path | Pass token |
|---|-------|----------------|------------|
| 1 | Git SHA | Checkout **FROZEN_RUNTIME** `1cbc8b0551179e1724033ee0036fb3366174daca` (tree `c673ada98b7f3dc56f1073fe65854984259a800d`). Closed campaign runtime `bf405f46` stays read-only. | Exact SHA match. **Not** `bf405f46`. **Not** **ITEM9_FROZEN_COLLECTOR** `fed2d9f7`. |
| 2 | Clean runtime tree | `git status --short --branch` on the runtime checkout | No unrelated dirty/untracked product files. Do not clean another lane's tree. |
| 3 | Clock / timezone | `python -c "from datetime import datetime; from zoneinfo import ZoneInfo; print(datetime.now(ZoneInfo('America/New_York')).isoformat())"` | America/New_York wall clock; session kind from `market_sessions` (`PREMARKET`/`REGULAR`/`AFTER_HOURS`/`CLOSED`). |
| 4 | Provider processes and connectivity | `python tools/provider_readiness.py --probe-local --json`; OpenD loopback `127.0.0.1:11111`; optional `python tools/moomoo/probe.py` | Loopback ports probed only; no external orders. Unreachable OpenD stays fail-closed. |
| 5 | Entitlements | `python tools/provider_readiness.py --json`; `python tools/imp.py providers campaign-readiness FTEP-V1-002 --json` | Capability/entitlement rows present; missing entitlement is `UNAVAILABLE` / `ENTITLEMENT_MISSING`, not HEALTHY. |
| 6 | Secrets presence (no values) | `python tools/imp.py env`; `python tools/provider_readiness.py --json` | Presence/absence only. Payload `secrets_included=false`. Never print `FINVIZ_API_KEY` / `APCA_*` / token files. |
| 7 | API / UI / liveness | `GET http://127.0.0.1:8766/provider/health`, `/context`, `/operator/diagnostics`; UI `http://127.0.0.1:5173/` | Inspect `service_liveness`, `readiness_vs_liveness`, and `sections.runtime.runtime_resilience.campaign_supervision`. Bound port ≠ HEALTHY. |
| 8 | Persistence path | `python tools/imp.py state-path`; `$report = python tools/state_path_diagnostic.py \| ConvertFrom-Json`; persist-on: `$env:IMP_STATE_DIR=$report.canonical_state_dir`; `$env:IMP_PERSIST_STATE='1'`; DB `$env:IMP_STATE_DIR\imp-state.sqlite3` | Persist on → local_state SQLite **schema v9** (`SELECT schema_version FROM schema_meta`). Persist off → `INTENTIONAL_EPHEMERAL`. |
| 9 | Campaign supervision state | `{IMP_STATE_DIR}/campaign-supervision/`; `python tools/platform/campaign_supervisor.py status --state-dir $env:IMP_STATE_DIR` | Before arm: `NOT_ARMED` / absent ownership is fine. **After arm:** durable `ownership.json` + `heartbeat.json` required; `ARMED_RUNNING` alone ≠ HEALTHY. |
| 10 | Opportunity book health | `GET /opportunities/summary` | `EMPTY` / `UNREADY` / `READY` / `UNAVAILABLE` as honest feed tokens. Zero rows is valid. |
| 11 | EventV1 / PIT hop | Serving hop: production news ingress `POST /intelligence/ingest/news` → EventV1/PIT → observational catalyst detector → OpportunityV1. RTH watch: `python tools/ftep_watch_catalysts.py FTEP-V1-002 --live-ingress --json` | Composed news hop only. **Explicit:** BUILD 09 `EventDetectorEngine` remains unwired. `OpportunityEngine.assess` remains unwired. **Currentness stays strict** — retrieval after arm does not make an older publication current. |
| 12 | Ranked API | `GET /opportunities/summary` and `GET /opportunities/{id}` | Ranked projection from serving repository. Fixture/replay cards stay on `DEMO_REPLAY` shelf. |
| 13 | DecisionTrace / TradeReview | Persist-on tables `execution_decision_traces` and `trade_reviews` on `imp-state.sqlite3`; HTTP `GET /intelligence/trade-reviews?opportunity_id=` | WATCH/DISMISS may persist `ExecutionDecisionTraceV1` + `TradeReviewV1` in **non-execution** modes. Not a fill. |
| 14 | Live safety | `GET /operator/diagnostics` `live-execution`; Live remains **OFF** | `allows_network_submit` remains **false**. `execution_authority` remains **BLOCKED**. |
| 15 | Paper safety | Do not start Paper EXECUTION from this checklist. Missing Alpaca keys → `COMPARATOR_NOT_CONFIGURED` | Not Paper-validated. Not `CALIBRATED`. Dry-run / SIGNAL_ONLY ≠ Paper submit. |
| 16 | Evidence output path | Finviz/FTEP JSON stdout; optional copies under governed `.local`; Item 9 receipts only under frozen collector `$rcpt` | Do not write receipts onto **CURRENT_MAIN** artifacts copy. Do not rewrite frozen empirical `7aade60`. |
| 17 | Campaign / run id | Campaign **FTEP-V1-002**; sessions **BASELINE** `fts-6DB7771FD9B3A991`, **AI_ENHANCED** `fts-D93189A042A1BEF2`; ops bundle `operator_run_id=RTHOPS-*` | `python tools/imp.py ftep integrity-check FTEP-V1-002 --json` PASS against canonical `IMP_STATE_DIR`. FTEP **not** `EMPIRICAL_ACTIVE`. |
| 18 | Logging | `.local/platform-backend.log`, `.local/platform-ui.log`, `.local/platform-control.log` | Logs exist and rotate under operator policy. No secret values in log paste. |
| 19 | Disk space | `python tools/imp.py storage audit` | Read-only inventory. Output is **not** deletion authority. |
| 20 | Recovery / shutdown | `campaign_supervisor.py shutdown [--rth-close]`; `STOP_PLATFORM.cmd`; clear Finviz gates | See [arm / close / recovery / no-backfill](#arm--close--recovery--no-backfill-rules). Do **not** delete governed SQLite or receipts. |
| 21 | No market-data backfill | If the live interval is missed | Leave `NOT_OBSERVED` / `UNAVAILABLE`. Do not backfill Item 9 gaps, Sep 18 epoch `121031`, Sep 22 `14:26–14:57` ET, or missed news rows. |
| 22 | Finviz preflight | `python tools/ftep_finviz_prospective_preflight.py FTEP-V1-002 --json` | Credentials present/absent honest; gates inactive off-hours. |
| 23 | OpenD / Item 9 readiness | `python tools/moomoo/opend_bar_1m_prospective_proof.py readiness`; `python tools/imp.py item9 next-rth-preflight --json` | Off-hours `NOT_RTH` / `WRONG_RUNTIME` expected from software worktree. Collection only from frozen collector during RTH. |
| 24 | Classification honesty | Provider/poll failures | `PROVIDER_FAILURE` / `SESSION_UNAVAILABLE` / progress `STALE`/`PROCESS_DEAD` → additive `NOT_OBSERVED` outage; root cause defaults **UNKNOWN**. No false narrative. |
| 25 | Empirical target (observe only) | End-to-end chain when market qualifies | provider receipt → EventV1 → PIT/currentness → detector → OpportunityV1 → ranked card → WATCH or DISMISS → acknowledgement → ExecutionDecisionTraceV1 → TradeReviewV1 → restart/readback. **DO NOT FORCE AN OPPORTUNITY.** |
| 26 | Detachment limitation | `python tools/platform/campaign_supervisor.py mechanism` | Parent-exit survival **PROVEN** (`SOFTWARE_CONTROLLED`). Job/terminal kill / breakaway **UNPROVEN**. Fail-visible detection is the guarantee. |

Item 9 Mode B `--poll` stays frozen-collector-only. This preopen does **not** authorize calibration fitting, Paper validation claims, Full30, or Live. Item 9 empirical receipt and Item 7 lawful BBO are **unmet empirical targets**, not software arm blockers.

## 26. Freeze gate (runtime `bf405f46` — **FROZEN_NOT_ARMED** / **DO NOT ARM**)

**Verdict: FROZEN_NOT_ARMED.** Runtime freeze declared for campaign `RTH-OBS-NEWS-20260923` / FTEP-V1-002. **Do not arm.** Freeze timestamp **`2026-09-22T23:46:17-04:00`** (`2026-09-23T03:46:17Z`). Runtime commit **`bf405f468bee4e70f8a40e97eaaf6c2d46c75e64`**; runtime tree **`c3b5a08b94e93e4ead3c9802092ecdebea1c3434`**. Docs tip may advance (e.g. after [#386](https://github.com/AdamEddahmouni/market-trading-platform/pull/386)); **do not** retarget **FROZEN_RUNTIME** to a docs commit.

### Freeze record (operator manifest)

| Field | Value |
|-------|-------|
| Campaign identity | `RTH-OBS-NEWS-20260923` / FTEP-V1-002 (`SIGNAL_ONLY_AUTHORIZED`; not `EMPIRICAL_ACTIVE`) |
| Freeze state | **`FROZEN_NOT_ARMED`** (`frozen=yes`; never `ARMED_RUNNING` from this act) |
| Runtime commit SHA | `bf405f468bee4e70f8a40e97eaaf6c2d46c75e64` |
| Runtime tree SHA | `c3b5a08b94e93e4ead3c9802092ecdebea1c3434` |
| Freeze timestamp | `2026-09-22T23:46:17-04:00` / `2026-09-23T03:46:17Z` |
| Branch / provenance | Ancestry through [#385](https://github.com/AdamEddahmouni/market-trading-platform/pull/385) supervision + [#384](https://github.com/AdamEddahmouni/market-trading-platform/pull/384) benchmark; freeze declared via runbook operator act (docs PR after independent review) |
| Python / runtime | CPython **3.11** (uv-managed / IMP `.venv`); Windows host |
| UI / build | Operator `:5173` surface on frozen checkout; CI validate-ui on tip; local typecheck requires `npm ci` in worktree |
| Campaign supervisor | `imp-campaign-supervisor` / `tools/platform/campaign_supervisor.py` at frozen SHA; mechanism `IMP_OWNED_SUPERVISOR_CREATE_NEW_PROCESS_GROUP_NO_WINDOW` |
| Provider-mode | Observational; Finviz/OpenD live probes **Operator at arm**; Moomoo/IBKR default unverified until earned |
| Execution authority | `execution_authority=BLOCKED`, `execution_mode=NONE`, `allows_network_submit=false`, `BUILD28_LIVE_SUBMIT_FORBIDDEN` |
| Evidence / state root | Fresh `IMP_STATE_DIR` for tomorrow (do not reuse prior campaign evidence); supervision under `{IMP_STATE_DIR}/campaign-supervision/` |
| Poll / heartbeat / stale | poll **30s**; heartbeat **15s**; stale after **90s**; starting grace **60s** |
| Item 9 mode | Mode B prospective proof; collector pin **ITEM9_FROZEN_COLLECTOR** `fed2d9f7`; status `PARTIAL_NOT_CALIBRATED` / `DO_NOT_PROMOTE` |
| Item 7 capture mode | Lawful `SNAPSHOT_BBO` + `BBO_VALID` only; governed corpus expectation **0** until earned |
| Currentness policy | PIT / available_time honesty; no retrospective market evidence |
| No-backfill policy | Missed intervals `NOT_OBSERVED`; no synthetic polls; Sep 21/22 gaps immutable |
| Safety policy | Live OFF; no Paper calibration; no forced opportunities; no broker submit |
| Calibration / model | Item 9 **NOT_CALIBRATED**; `ITEM9_CALIBRATION_RUN=FORBIDDEN`; no model promotion |
| Freeze does **not** mean | EMPIRICAL_ACTIVE · provider checks passed · Item 7 corpus · Item 9 bar · calibration |
| Invalidation rule | **No silent SHA move** under the same campaign identity. Pre-arm runtime fix requires **invalidate + preserve this freeze record + new campaign version / new freeze**. |

| # | Gate | Result | Evidence |
|---|------|--------|----------|
| 1 | Candidate runtime SHA identified | **PASS** | `bf405f468bee4e70f8a40e97eaaf6c2d46c75e64` (merge [#384](https://github.com/AdamEddahmouni/market-trading-platform/pull/384); prior tip [#385](https://github.com/AdamEddahmouni/market-trading-platform/pull/385)); tree `c3b5a08b…` |
| 2 | Runtime freeze declared | **PASS** | Explicit **`frozen=yes`** / **`FROZEN_NOT_ARMED`** for `RTH-OBS-NEWS-20260923` at timestamp above |
| 3 | Campaign supervision on tip | **PASS** | `CAMPAIGN_SUPERVISION_HEARTBEAT.md`, `campaign_supervisor.py`, `campaign_supervision.py` present on this SHA |
| 4 | Arm requires durable supervision state | **PASS** | This runbook + ownership/heartbeat under `{IMP_STATE_DIR}/campaign-supervision/` |
| 5 | Supervisor identity + roles | **PASS** | `imp-campaign-supervisor`; default roles `supervisor,poller,api` |
| 6 | Heartbeat / poll / stale cadence | **PASS** | Defaults 15s / 30s / 90s (starting grace 60s) in `campaign_supervision.py` |
| 7 | `ARMED_RUNNING` alone ≠ alive | **PASS** | Fail-closed progress evaluation; docs |
| 8 | Liveness ≠ data freshness | **PASS** | [CAMPAIGN_SUPERVISION_HEARTBEAT.md](CAMPAIGN_SUPERVISION_HEARTBEAT.md) |
| 9 | `execution_authority=BLOCKED` | **PASS** | Ownership defaults; Live submit forbidden |
| 10 | Parent-process exit survival | **PASS** | `CREATE_NEW_PROCESS_GROUP \| CREATE_NO_WINDOW` — `SOFTWARE_CONTROLLED_EVIDENCE` |
| 11 | Job-kill / terminal / breakaway survival | **PARTIAL** | Disposable harness (2026-09-22): default children **die with job**; ambient breakaway **not** terminal-independent. Fail-visible stale/dead detection remains the product guarantee. Sep 22 gap root still **UNPROVEN**. |
| 12 | OpenD preflight path | **PARTIAL** | Readiness CLIs on tip; live OpenD reachability **Operator at arm** |
| 13 | Finviz preflight path | **PARTIAL** | Preflight CLI on tip; credentials/live ingress **Operator at arm** |
| 14 | Entitlement / campaign-readiness path | **PARTIAL** | CLI present; live entitlement probe **Operator at arm** |
| 15 | API / UI readiness path | **PARTIAL** | Surfaces documented (`:8766`/`:5173`/`:8767`); live stack **Operator at arm** |
| 16 | Evidence paths + Item 9 collector pin | **PASS** | Frozen collector `fed2d9f7` + governed `$rcpt`; software tip is not the corpus root |
| 17 | Time-sync procedure (America/New_York) | **PASS** | Checklist clock command; session calendar gates |
| 18 | SQLite integrity / schema v9 | **PARTIAL** | Integrity-check + schema v9 on tip; canonical `IMP_STATE_DIR` verify **Operator at arm** |
| 19 | Safe shutdown | **PASS** | `shutdown` / `shutdown --rth-close` → `CLEAN_SHUTDOWN` / `RTH_CLOSE_SHUTDOWN` → progress `NOT_APPLICABLE` (not an outage) |
| 20 | Safe recovery (preserve arm/outages) | **PASS** | `recover` refreshes PIDs; preserves arm timestamp, segment, runtime SHA, outage gaps — does not mint Segment C |
| 21 | No-backfill / no synthetic polls | **PASS** | Additive `outages.jsonl`; `NOT_OBSERVED`; `synthetic_poll_generated=false` |
| 22 | Provider / session / NOT_OBSERVED classification | **PASS** | Progress tokens + outage classification documented; Sep 22 gap stays `NOT_OBSERVED` / UNKNOWN |
| 23 | Benchmark PR #384 not an arm blocker | **PASS** | **Merged** on tip: protocol + deterministic-stub Smoke10 pin (`SOFTWARE_CONTROLLED`). Real-system RTH15-11 Smoke10 **NOT_EXECUTED**. Still not a campaign arm blocker. |
| 24 | Item 9 empirical / calibration | **PARTIAL** | `PARTIAL_NOT_CALIBRATED` / `DO_NOT_PROMOTE`; sample gate met; fitting forbidden — unmet empirical target, not software arm blocker |
| 25 | Item 7 lawful BBO corpus | **PARTIAL** | Governed/PIT-valid counts **0**; first missing link remains lawful BBO — unmet empirical target, not software arm blocker |
| 26 | Sep 22 honesty + zero-opportunity rule | **PASS** | Outage not rewritten; Segment B prospective-current remains ZERO; do not invent opportunities |

**Freeze decision:** **YES — FROZEN_NOT_ARMED.** Software freeze gates that were FAIL (gate 2) are now PASS. Remaining **PARTIAL** rows are either (a) known durable limitations that do not block freeze when fail-visible detection holds (gate 11), or (b) **Operator at arm** / unmet empirical targets (gates 12–15, 18, 24–25) — they block **arm**, not this freeze.

## Arm / close / recovery / no-backfill rules

**Arm (only after §26 freeze + operator authorization — not now):**

1. Checkout clean tree at **FROZEN_RUNTIME** SHA `bf405f468bee4e70f8a40e97eaaf6c2d46c75e64` (`FROZEN_NOT_ARMED` — arm is a separate act).
2. Bootstrap `IMP_STATE_DIR` / `IMP_PERSIST_STATE=1`; pass FTEP integrity-check; OpenD + Finviz + entitlement + API/UI preflight.
3. Write durable supervision via `campaign_supervisor.py arm` then `run` (or supervised spawn). Register child roles. Confirm `status` progresses beyond `ARMED_RUNNING`-only.
4. Temporary shell gates only: `IMP_FINVIZ_LIVE=1`, `IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS=1` — never commit.
5. `execution_authority` stays **BLOCKED**. No Paper/Live orders. No forced opportunities.

**Close:**

1. `python tools/platform/campaign_supervisor.py shutdown --state-dir $env:IMP_STATE_DIR --rth-close`
2. `python tools/rth_empirical_ops.py --json summarize` (optional ops bundle).
3. Clear temporary Finviz/catalyst env vars; `STOP_PLATFORM.cmd` as needed.
4. Intentional RTH close is **`RTH_CLOSE_SHUTDOWN`** / progress **`NOT_APPLICABLE`** — not a `PROCESS_DEAD`/`STALE` outage.

**Recovery:**

1. Detect → fail visible (`STALE` / `PROCESS_DEAD` / `APPLICATION_UNREADY`) → deliberate `recover`.
2. Recovery refreshes PIDs only; preserves original arm timestamp, segment ID, runtime SHA, and additive outage gaps.
3. Do **not** silently create a new segment to hide a gap. Automatic restart is **not** required.

**No-backfill:**

1. Missed intervals stay **`NOT_OBSERVED`** (root cause **UNKNOWN** unless separately proven).
2. No synthetic polls. No rewriting Sep 21 / Sep 22 gaps. No post-arm retrieval of older publications claimed as current.
3. Provider failure and `SESSION_UNAVAILABLE` classify honestly; they do not authorize fill-in.

## Operator action rules

- One primary operator owns the armed campaign; do not dual-arm the same `IMP_STATE_DIR`.
- Inspect-only diagnostics (`/operator/diagnostics`, `campaign_supervisor status`) do not start collectors.
- Zero qualifying events / empty ranked book is a **valid** session outcome — do not manufacture catalyst rows, opportunities, WATCH/DISMISS, or BBO corpus.
- Item 9 stays frozen-collector-only; calibration remains **FORBIDDEN** / **DO_NOT_PROMOTE**.
- Item 7 governed rows stay **0** until earned; do not manufacture corpus.
- Live remains **OFF**. Benchmark [#384](https://github.com/AdamEddahmouni/market-trading-platform/pull/384) is not a prerequisite.

## Pre-RTH verification checklist (off-session)

The table above is the **next lawful** preopen. Off-session minimum:

| Check | Status | Notes |
|-------|--------|-------|
| PROGRAM_STATUS header vs `git rev-parse origin/main` | Operator | Docs tip may lag/ahead of **FROZEN_RUNTIME**; git tip wins for docs. Confirm **ITEM9_FROZEN_COLLECTOR** in [PROGRAM_STATUS.md](../platform/PROGRAM_STATUS.md) |
| **FROZEN_RUNTIME** freeze | **FROZEN_NOT_ARMED** | `frozen=yes`; runtime `bf405f46…` / tree `c3b5a08b…`; campaign `RTH-OBS-NEWS-20260923` |
| Campaign supervision docs/CLI | On frozen SHA | [CAMPAIGN_SUPERVISION_HEARTBEAT.md](CAMPAIGN_SUPERVISION_HEARTBEAT.md) |
| **ITEM9_FROZEN_COLLECTOR** worktree | Operator | `.imp-actual-01-phase-d` @ `fed2d9f7` |
| Python 3.11 + `.venv` | Operator | `python tools\imp.py env bootstrap --link-venv` |
| OpenD loopback | Operator | Required for Item 9 collection |
| `item9 next-rth-preflight` | Operator | Off-hours `NOT_RTH` expected |
| Campaign / Live OFF | **Policy** | FTEP not `EMPIRICAL_ACTIVE`; Moomoo/IBKR **`PROVIDER_UNVERIFIED`** unless operator earns live receipts |
| Item 9 / Item 7 gates | **Unearned beyond sample gate** | `ITEM9_CALIBRATED`=NO; `SAMPLE_GATE_MET`; `PARTIAL_NOT_CALIBRATED`; `ITEM9_DISTINCT_RTH_DATES`=**3**/3; `fitting_allowed=false`; calibration **FORBIDDEN**; Item 7 governed rows **0** |

## Recommended next RTH operator actions

1. Night before: checkout **FROZEN_RUNTIME** `bf405f468bee4e70f8a40e97eaaf6c2d46c75e64` (do not confuse with docs tip). Confirm **ITEM9_FROZEN_COLLECTOR** `fed2d9f7`. Resolve §26 unpaid **Operator at arm** PARTIALS. Freeze is already **`FROZEN_NOT_ARMED`** — **do not arm** without explicit operator authorization.
2. Morning: run [next lawful RTH preopen checklist](#next-lawful-rth-preopen-checklist); bootstrap **fresh** `IMP_STATE_DIR`; start platform; confirm `service_liveness` + campaign-supervision surfaces (bound port is not HEALTHY; `ARMED_RUNNING` is not alive).
3. T−15: full preflight including Finviz, OpenD, entitlement, `item9 next-rth-preflight`; set temporary Finviz/catalyst gates only after arm authorization.
4. ≥ 09:30 only: arm with durable supervision → Finviz watch → ranked `/opportunities/summary` (zero rows valid) → governed Item 9 `--poll` (frozen collector) → `corpus-status` → Item 7 status → ops dry-run; summarize. Success is the information/decision chain, not a trade.
5. Confirm empirical gates remain unflipped unless governed JSON receipts exist; Live stays OFF. Do not backfill a missed live interval. Do not invent opportunities. [#222](https://github.com/AdamEddahmouni/market-trading-platform/pull/222) is **CLOSED** (not merged); [#370](https://github.com/AdamEddahmouni/market-trading-platform/pull/370) superseded it.
