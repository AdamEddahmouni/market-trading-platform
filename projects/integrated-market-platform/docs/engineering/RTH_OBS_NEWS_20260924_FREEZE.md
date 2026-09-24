# RTH-OBS-NEWS-20260924 freeze

**State:** `FROZEN_NOT_ARMED`

**Preparation verdict:** `READY_FOR_PRE_RTH_ARM`

**Evidence class of this document:** software coordination. It does not arm the campaign and it is not `EMPIRICALLY_PROVEN`.

**Machine freeze:** [RTH-OBS-NEWS-20260924.freeze.json](../../artifacts/campaign-freeze/RTH-OBS-NEWS-20260924.freeze.json)

**Readiness receipt:** [RTH-OBS-NEWS-20260924.pre-rth-readiness.json](../../artifacts/campaign-readiness/RTH-OBS-NEWS-20260924.pre-rth-readiness.json)

**Supersedes:** `02d699768dce2ad2e85d7215f2588fd18a36fcce` (tree `84d254547fa7e209b461c84ce172397f514bc4b9`). Rehearsal on that checkout showed `python tools/platform/local_launcher.py` raised `ModuleNotFoundError: No module named 'tools'`, `readiness` crashed on a relative import, and `local_launcher.py status` did not print the API pid. Do not arm that SHA.

This is the only launch procedure for the next cash session. Closed campaign `RTH-OBS-NEWS-20260923` on `bf405f468bee4e70f8a40e97eaaf6c2d46c75e64` stays read-only.

## Identity

| Field | Value |
|---|---|
| Campaign ID | `RTH-OBS-NEWS-20260924` |
| Observation window | `RTH-OBS-NEWS-20260924-A` |
| Activation slug | `FTEP-V1-002` (existing manifest; not the Sep 23 evidence directory) |
| Session | `2026-09-24` America/New_York |
| Cash RTH | `09:30`–`16:00` ET (`market_sessions` label `REGULAR` at `09:30`, `AFTER_HOURS` at `16:00`) |
| Calendar | `is_trading_day(2026-09-24)` is true. `2026-09-07` is the holiday. `2026-09-26` is not a trading day. |
| Runtime commit | `c15527221a21d7bc88acefbe0971b6de9292247e` |
| Runtime tree | `e77f72208b6547d63dc4b7101c5cfa357114052b` |
| State and evidence namespace | `projects/integrated-market-platform/.local/rth-campaign-20260924` |
| Required roles | `supervisor`, `poller`, `api` |
| Execution | `BLOCKED`. Live **OFF**. |

`IMP_STATE_DIR` must be that namespace. Do not point it at `.local/rth-campaign-20260923` or the shared parent `.local`.

## Before 09:30 ET — hard gate

A manifest file alone is not readiness. SHA, date, preflight, writable state, outage ledger, and execution locks are required before the `arm` command. Supervisor adoption, poller, API, heartbeat, and poll classification are required after `arm` and before `09:30`. If any post-arm row fails, shut down and leave the receipts. Do not backfill.

| Check | Fail closed when |
|---|---|
| Campaign ID | anything other than `RTH-OBS-NEWS-20260924` |
| Runtime SHA | `git rev-parse HEAD` is not `c15527221a21d7bc88acefbe0971b6de9292247e` |
| Tree SHA | `git rev-parse "HEAD^{tree}"` is not `e77f72208b6547d63dc4b7101c5cfa357114052b` |
| Session | wall clock date in America/New_York is not `2026-09-24`, or the clock is not `America/New_York` |
| Environment preflight | exit code is not 0, or `ready_to_arm` is not true |
| UI dependencies | `ui/node_modules` is absent |
| Supervisor | `run` process is dead, or `ownership.supervisor_pid` is still the one-shot arm PID |
| Poller | no live `poll-loop --live-ingress` child |
| API | `127.0.0.1:8766` is not accepting connections, or the registered `api` pid is dead |
| Heartbeat | `last_heartbeat_utc` is not advancing, or status is `STALE` / `PROCESS_DEAD` |
| Poll class | `last_poll_classification` is `NO_POLL`, `POLL_PROCESS_FAILURE`, `PROVIDER_FAILURE`, `ADMISSION_FAILURE`, `TOKEN_ABSENT`, `GATES_INACTIVE`, or `SECRET_DIR_MISSING`. Before the open, `SESSION_UNAVAILABLE` is an attempted poll, not a success. `SOFTWARE_CONTROLLED_CYCLE` is not a market poll. |
| Empty vs failure | `SUCCESS_EMPTY` may advance `last_successful_poll_utc`. Failures must not. |
| Outage ledger | `campaign-supervision/outages.jsonl` is not appendable, or readiness phase is `BLOCKED_STATE_DIR` |
| Evidence path | `IMP_STATE_DIR` is not writable |
| Execution | `execution_authority` is not `BLOCKED`, or Live submit is on |
| Item 9 | any calibration, fit, tune, score, or Full30 command |
| Item 7 | any synthetic governed row |

## Before RTH

Run from `projects/integrated-market-platform` on a clean checkout of the frozen runtime.

```powershell
git fetch origin
git checkout c15527221a21d7bc88acefbe0971b6de9292247e
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
```

`HEAD` must be `c15527221a21d7bc88acefbe0971b6de9292247e`. The tree must be `e77f72208b6547d63dc4b7101c5cfa357114052b`.

```powershell
python tools/imp.py env bootstrap --link-venv
if (-not (Test-Path ui\node_modules)) { npm ci --prefix ui }
$env:IMP_STATE_DIR = Join-Path (Get-Location) ".local\rth-campaign-20260924"
New-Item -ItemType Directory -Force -Path $env:IMP_STATE_DIR | Out-Null
$env:IMP_PERSIST_STATE = "1"
$env:IMP_FINVIZ_LIVE = "1"
$env:IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS = "1"
python -c "from datetime import datetime; from zoneinfo import ZoneInfo; print(datetime.now(ZoneInfo('America/New_York')).isoformat())"
python tools/platform/campaign_supervisor.py environment-preflight --state-dir $env:IMP_STATE_DIR --campaign-id RTH-OBS-NEWS-20260924 --observation-window-id RTH-OBS-NEWS-20260924-A
```

Preflight must exit 0 with `ready_to_arm: true`. `credentials_presence_finviz` may warn in a shell that has no env token. Do not print the token. If the first live poll below classifies `TOKEN_ABSENT`, `GATES_INACTIVE`, or `SECRET_DIR_MISSING`, stop. That is not an armed healthy campaign.

```powershell
python tools/platform/local_launcher.py start
python tools/platform/local_launcher.py status
```

Arm writes ownership. The arm process exits, so start the durable supervisor immediately after. `run` and `poll-loop` refuse to start without that ownership.

```powershell
python tools/platform/campaign_supervisor.py arm --state-dir $env:IMP_STATE_DIR --campaign-id RTH-OBS-NEWS-20260924 --observation-window-id RTH-OBS-NEWS-20260924-A --segment-id A --runtime-sha c15527221a21d7bc88acefbe0971b6de9292247e
python tools/platform/campaign_supervisor.py spawn-detached --state-dir $env:IMP_STATE_DIR -- .venv\Scripts\python.exe tools\platform\campaign_supervisor.py run --state-dir $env:IMP_STATE_DIR
python tools/platform/campaign_supervisor.py spawn-detached --state-dir $env:IMP_STATE_DIR -- .venv\Scripts\python.exe tools\platform\campaign_supervisor.py poll-loop --state-dir $env:IMP_STATE_DIR --live-ingress --campaign-slug FTEP-V1-002
python tools/platform/campaign_supervisor.py register-child --state-dir $env:IMP_STATE_DIR --role api --pid <API_PID> --identity-tokens run_ui_api.py
python tools/platform/campaign_supervisor.py status --state-dir $env:IMP_STATE_DIR
python tools/platform/campaign_supervisor.py readiness --state-dir $env:IMP_STATE_DIR --campaign-id RTH-OBS-NEWS-20260924 --intended-date-et 2026-09-24 --frozen yes --runtime-sha c15527221a21d7bc88acefbe0971b6de9292247e --observation-window-id RTH-OBS-NEWS-20260924-A
```

`<API_PID>` is the integer on the `API pid` line printed by `local_launcher.py status`. Do not use the `SPAWNED` pid from `spawn-detached`; that pid is the Windows interpreter shim. `ownership.supervisor_pid` is the durable `run` process. Do not register the spawn shell as the supervisor.

The arm command's pid is not the durable supervisor. Confirm `run` has adopted `ownership.supervisor_pid` and that pid is alive. `ARMED_RUNNING` alone is not healthy. Required status before `09:30` is `HEALTHY` or `STARTING` with supervisor, poller, and API alive.

## At and after 09:30

```powershell
python tools/platform/campaign_supervisor.py status --state-dir $env:IMP_STATE_DIR
Get-Content $env:IMP_STATE_DIR\campaign-supervision\poll-attempts.jsonl -Tail 5
Get-Content $env:IMP_STATE_DIR\campaign-supervision\outages.jsonl -Tail 5 -ErrorAction SilentlyContinue
```

The first lawful market poll receipt must classify as `SUCCESS_EMPTY` or `SUCCESS`. `SUCCESS_EMPTY` is a real observation with zero qualifying rows. `PROVIDER_FAILURE`, `ADMISSION_FAILURE`, and `POLL_PROCESS_FAILURE` are failures. No new line in `poll-attempts.jsonl` is `NO_POLL`. A stuck `last_heartbeat_utc` is `STALE`.

Do not restart to erase a gap. Do not backfill. Leave the outage row in place.

## During the session

| Situation | Action |
|---|---|
| Heartbeat advancing, classification `SUCCESS` or `SUCCESS_EMPTY`, roles alive | Keep watching. No operator action. |
| One `PROVIDER_FAILURE` or `HTTP_429` with the poller still alive | Leave it. Do not immediately retry a 429. The next cadence attempt is the record. |
| `PROCESS_DEAD`, missing role, or heartbeat `STALE` | Campaign-threatening. Read `outages.jsonl`. Do not relaunch over the same ownership to hide the gap. |
| API connection refused (`ADMISSION_FAILURE`) | Campaign-threatening until admit works again. Preserve the receipts. |
| Supervisor pid replaced by a one-shot shell | Stop. That is the Sep 23 defect. Do not continue on the clobbered pid. |
| Automatic recovery | The supervisor loop records an open outage. It does not auto-backfill and it does not create a new segment. |

Monitor with:

```powershell
python tools/platform/campaign_supervisor.py status --state-dir $env:IMP_STATE_DIR
python tools/platform/local_launcher.py status
```

## 16:00 close

```powershell
python tools/platform/campaign_supervisor.py shutdown --state-dir $env:IMP_STATE_DIR --rth-close
python tools/platform/campaign_supervisor.py status --state-dir $env:IMP_STATE_DIR
python tools/platform/local_launcher.py status
python tools/platform/local_launcher.py stop
```

Expect `RTH_CLOSE_SHUTDOWN` and progress `NOT_APPLICABLE`. Copy the terminal status JSON, the last heartbeat, and `outages.jsonl` into the campaign directory. Do not backfill gaps. Write the closeout outside `.local/rth-campaign-20260924`, the same way Sep 23 used `artifacts/campaign-closeout/`.

## Abort before the open

If the hard gate fails, do not arm. If already armed and a required role is dead before `09:30`, shut down and leave the receipts:

```powershell
python tools/platform/campaign_supervisor.py shutdown --state-dir $env:IMP_STATE_DIR
python tools/platform/local_launcher.py stop
```

A replacement runtime requires a new freeze commit before any empirical run. Do not move `c15527221a21d7bc88acefbe0971b6de9292247e` in place.

## Locks that stay closed

`ITEM7_GOVERNED_CORPUS=NOT_ESTABLISHED`. `SEP23_ITEM7_EMPIRICAL_ROWS=0`. `ITEM9_CALIBRATED=NO`. `ITEM9_CALIBRATION_RUN=FORBIDDEN`. `ITEM9_STATUS=PARTIAL_NOT_CALIBRATED`. `FULL30=NOT_RUN`. `FTEP_EMPIRICAL_ACTIVE=NO`. `LIVE_EXECUTION=OFF`. Smoke10 `ibp-smoke10-8C23029DD46FDA78` remains `FAIL 10/10`. Controlled Replay remains `SOFTWARE_CONTROLLED` / `FIXTURE_REPLAY`.

`NEWS_ARTICLE` → `NEWS_EVENT` from [#398](https://github.com/AdamEddahmouni/market-trading-platform/pull/398) is `SOFTWARE_PROVEN` on this runtime. It is not prospective proof until this campaign observes it. Do not fabricate ForecastV1, a champion, Opportunity Engine admission, or a Radar opportunity.
