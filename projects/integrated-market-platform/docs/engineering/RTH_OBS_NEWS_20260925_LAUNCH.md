# Launch handoff — RTH-OBS-NEWS-20260925

**State:** `FROZEN_NOT_ARMED`. This page does not arm the campaign.

**Evidence class of this page:** software coordination. Not empirical.

| Field | Value |
|---|---|
| Campaign ID | `RTH-OBS-NEWS-20260925` |
| Date | `2026-09-25` America/New_York |
| Window | `09:30`–`16:00` ET. Latest safe arm is `09:30` ET. After that, arm is `MISSED_WINDOW`. |
| Runtime SHA | `bd8036a6a010b17c5343f110c8f0fd8be31505fd` |
| Runtime tree | `8be687198a6e62ce292a2923f72828b4956a212c` |
| Freeze | `artifacts/campaign-freeze/RTH-OBS-NEWS-20260925.freeze.json` |
| Freeze sha256 | `76bccf2b83233611d10f3f709c0b58e00c0f44d8ac7bf77967bd600c1bbcd6a8` |
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

From the monorepo, save the freeze, then check out the runtime. The freeze file lives on the later documentation commit. The running tree must be the runtime SHA.

```powershell
git fetch origin main
git show origin/main:projects/integrated-market-platform/artifacts/campaign-freeze/RTH-OBS-NEWS-20260925.freeze.json > $env:TEMP\RTH-OBS-NEWS-20260925.freeze.json
git checkout bd8036a6a010b17c5343f110c8f0fd8be31505fd
cd projects\integrated-market-platform
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git status --porcelain --untracked-files=no
python tools\imp.py env bootstrap --link-venv
```

`HEAD` must be `bd8036a6a010b17c5343f110c8f0fd8be31505fd`. The tree must be `8be687198a6e62ce292a2923f72828b4956a212c`. Tracked status must be empty.

## T-30

```powershell
$env:IMP_STATE_DIR = Join-Path (Get-Location) ".local\rth-campaign-20260925"
$env:IMP_PERSIST_STATE = "1"
$env:IMP_FINVIZ_LIVE = "1"
$env:IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS = "1"
python tools\platform\campaign_supervisor.py go-no-go --freeze $env:TEMP\RTH-OBS-NEWS-20260925.freeze.json --state-dir $env:IMP_STATE_DIR
```

Exit 0 and `disposition=READY_FOR_PRE_RTH_ARM` are required before arm. Any other disposition is NO-GO. Read every name in `blockers`. Do not arm to clear them.

Then start the API with the existing launcher and confirm `127.0.0.1:8766` is this runtime before the final gate:

```powershell
python tools\platform\local_launcher.py start
python tools\platform\local_launcher.py status
```

If port 8766 is already taken by a different SHA, stop that process. Do not arm over it.

## Arm

Only when GO/NO-GO is `READY_FOR_PRE_RTH_ARM`:

```powershell
python tools\platform\campaign_supervisor.py arm --state-dir $env:IMP_STATE_DIR --campaign-id RTH-OBS-NEWS-20260925 --observation-window-id RTH-OBS-NEWS-20260925-A --segment-id A --freeze $env:TEMP\RTH-OBS-NEWS-20260925.freeze.json --require-finviz-live-ingress
python tools\platform\campaign_supervisor.py spawn-detached --state-dir $env:IMP_STATE_DIR -- .venv\Scripts\python.exe tools\platform\campaign_supervisor.py run --state-dir $env:IMP_STATE_DIR
python tools\platform\campaign_supervisor.py spawn-detached --state-dir $env:IMP_STATE_DIR -- .venv\Scripts\python.exe tools\platform\campaign_supervisor.py poll-loop --state-dir $env:IMP_STATE_DIR --live-ingress --campaign-slug FTEP-V1-002
```

Successful arm prints `"status": "ARMED"`. Ownership is `campaign-supervision/ownership.json` with `arm_status=ARMED_RUNNING` and the runtime SHA above. Execution stays `BLOCKED`.

Register the API pid from `local_launcher.py status` (the durable pid, not a spawn shim):

```powershell
python tools\platform\campaign_supervisor.py register-child --state-dir $env:IMP_STATE_DIR --role api --pid <API_PID> --identity-tokens run_ui_api.py
python tools\platform\campaign_supervisor.py status --state-dir $env:IMP_STATE_DIR
```

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
