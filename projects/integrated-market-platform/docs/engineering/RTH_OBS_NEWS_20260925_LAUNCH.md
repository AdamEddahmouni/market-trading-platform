# Launch handoff — RTH-OBS-NEWS-20260925

**State:** `FROZEN_NOT_ARMED`. This page does not arm the campaign.

**Evidence class of this page:** software coordination. Not empirical.

| Field | Value |
|---|---|
| Campaign ID | `RTH-OBS-NEWS-20260925` |
| Date | `2026-09-25` America/New_York |
| Window | `09:30`–`16:00` ET. Latest safe arm is `09:30` ET. After that, arm is `MISSED_WINDOW`. |
| Runtime SHA | `f8f42547293d0f8e84e07a9ecc647f949af60289` |
| Runtime tree | `c3ac61007419d34981f84ce20786bb342048a1b0` |
| Freeze | `artifacts/campaign-freeze/RTH-OBS-NEWS-20260925.freeze.json` |
| Freeze sha256 | `74f49092afc93ee550ffd41e862ec8f76f2ad32637c2194cfd0e0bbd3cba660b` |
| Evidence root | `projects/integrated-market-platform/.local/rth-campaign-20260925` |
| Rehearsal root | `projects/integrated-market-platform/.local/rth-rehearsal-20260925` |
| Provider | Finviz prospective news. Role `prospective_news_ingress`. |
| Live | `OFF` |
| Item 9 calibration | `FORBIDDEN` |
| Full30 | `NOT_RUN` |
| Item 7 corpus | `NOT_ESTABLISHED` |
| Sep 24 | `OPERATIONAL_ONLY` / not armed |
| Sep 23 | `PARTIAL_LATE_ARM` |

Do not arm on any date other than 2026-09-25 before 09:30 ET. Do not write rehearsal files into the evidence root.

## T-60

From the monorepo, save the freeze as UTF-8 without a byte-order mark, then create a dedicated runtime worktree. The freeze file lives on the later documentation commit. Keep the commands in one PowerShell session; the running tree must be the runtime SHA.

```powershell
git fetch origin main
$freezePath = Join-Path $env:TEMP 'RTH-OBS-NEWS-20260925.freeze.json'
$freezeLines = git show origin/main:projects/integrated-market-platform/artifacts/campaign-freeze/RTH-OBS-NEWS-20260925.freeze.json
if ($LASTEXITCODE -ne 0) { throw 'Could not read the canonical freeze' }
[System.IO.File]::WriteAllText($freezePath, ($freezeLines -join "`n"), [System.Text.UTF8Encoding]::new($false))
$runtimePath = Join-Path (Get-Location) '.worktrees\rth-campaign-20260925-runtime'
git worktree add --detach $runtimePath f8f42547293d0f8e84e07a9ecc647f949af60289
if ($LASTEXITCODE -ne 0) { throw 'Could not create the frozen runtime worktree' }
Set-Location $runtimePath
Set-Location projects\integrated-market-platform
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git status --porcelain --untracked-files=no
python tools\imp.py env bootstrap --link-venv
```

`HEAD` must be `f8f42547293d0f8e84e07a9ecc647f949af60289`. The tree must be `c3ac61007419d34981f84ce20786bb342048a1b0`. Tracked status must be empty.

## T-30

```powershell
$env:IMP_STATE_DIR = Join-Path (Get-Location) ".local\rth-campaign-20260925"
$env:IMP_PERSIST_STATE = "1"
$env:IMP_FINVIZ_LIVE = "1"
$env:IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS = "1"
python tools\platform\campaign_supervisor.py go-no-go --freeze $freezePath --state-dir $env:IMP_STATE_DIR
```

Exit 0 and `disposition=READY_FOR_PRE_RTH_ARM` are required before arm. Any other disposition is NO-GO. Read every name in `blockers`. Do not arm to clear them.

Port 8766 must be free for this gate. If another process owns it, identify and stop that process before rerunning GO/NO-GO.

## Arm

Only when GO/NO-GO is `READY_FOR_PRE_RTH_ARM`:

```powershell
python tools\platform\campaign_supervisor.py arm --state-dir $env:IMP_STATE_DIR --campaign-id RTH-OBS-NEWS-20260925 --observation-window-id RTH-OBS-NEWS-20260925-A --segment-id A --freeze $freezePath --require-finviz-live-ingress
python tools\platform\local_launcher.py start
python tools\platform\local_launcher.py status
```

Confirm `127.0.0.1:8766` is this runtime and register the durable API pid from `local_launcher.py status` (not a spawn shim):

```powershell
python tools\platform\campaign_supervisor.py register-child --state-dir $env:IMP_STATE_DIR --role api --pid <API_PID> --identity-tokens run_ui_api.py
python tools\platform\campaign_supervisor.py spawn-detached --state-dir $env:IMP_STATE_DIR -- .venv\Scripts\python.exe tools\platform\campaign_supervisor.py run --state-dir $env:IMP_STATE_DIR
python tools\platform\campaign_supervisor.py spawn-detached --state-dir $env:IMP_STATE_DIR -- .venv\Scripts\python.exe tools\platform\campaign_supervisor.py poll-loop --state-dir $env:IMP_STATE_DIR --live-ingress --campaign-slug FTEP-V1-002
```

Successful arm prints `"status": "ARMED"`. Ownership is `campaign-supervision/ownership.json` with `arm_status=ARMED_RUNNING` and the runtime SHA above. Execution stays `BLOCKED`.

Check supervision and all three registered roles with `python tools\platform\campaign_supervisor.py status --state-dir $env:IMP_STATE_DIR`.

## At the open and during RTH

```powershell
python tools\platform\campaign_supervisor.py status --state-dir $env:IMP_STATE_DIR
Get-Content $env:IMP_STATE_DIR\campaign-supervision\poll-attempts.jsonl -Tail 5
```

A lawful poll is `SUCCESS` or `SUCCESS_EMPTY`. `TOKEN_ABSENT`, `PROVIDER_FAILURE`, `ADMISSION_FAILURE`, and a stuck heartbeat are failures. Do not backfill. Do not restart to hide a gap.

## Close

```powershell
python tools\platform\campaign_supervisor.py shutdown --state-dir $env:IMP_STATE_DIR --rth-close
python tools\platform\local_launcher.py stop
```

Expect `RTH_CLOSE_SHUTDOWN`. Write the closeout under `artifacts/campaign-closeout/`, not by editing this freeze.

## NO-GO

Stop if GO/NO-GO is not `READY_FOR_PRE_RTH_ARM`. In particular: wrong SHA, dirty tree, bad freeze hash, missing or unrecognized Finviz credential, provider flag off, Live on, calibration on, Full30 on, rehearsal path used as the evidence root, already armed, terminal, or clock at or after 09:30 ET.

Credential source on the preparation machine was `SECRET_DIR` (present, not printed). The launch shell must resolve the same way. If GO/NO-GO reports `PROVIDER_CREDENTIAL_ABSENT`, that is an external blocker. Do not invent a token.
